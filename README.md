# DocuMind

Enterprise document intelligence platform. Phase 2 adds secure authentication, multi-organization membership, and organization-level Admin/Member authorization to the Next.js/TypeScript/Tailwind, FastAPI, PostgreSQL, and pgvector foundation. Document workflows, RAG, and agents are deferred.

## Phase 2: Windows quick start

Preserve your existing `.env` files and database volume. From the project root, start PostgreSQL:

```powershell
docker compose up -d --wait db
```

In a backend terminal:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
# Generate a secret only if one is not already configured; this does not print it.
.\.venv\Scripts\python.exe -c "import secrets; from dotenv import dotenv_values,set_key; dotenv_values('.env').get('AUTH_SECRET') or set_key('.env','AUTH_SECRET',secrets.token_urlsafe(48))"
.\.venv\Scripts\python.exe -m alembic upgrade head --sql
# Review the SQL above before applying the additive migration.
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

The local secret was generated during Phase 2 implementation if missing. Do not replace it during routine restarts. Use `COOKIE_SECURE=false` for local HTTP and `CORS_ORIGINS=["http://localhost:3000"]` in `backend/.env`. No JWT secrets belong in frontend variables. When viewing migration SQL on an already upgraded database, use `alembic upgrade 0001_enable_pgvector:head --sql` to review only the Phase 2 change.

In a frontend terminal:

```powershell
cd frontend
npm ci
# Add BACKEND_URL=http://127.0.0.1:8000 to .env.local if it is absent.
npm run dev
```

Open <http://localhost:3000/signup>. Register a name, email, and 12–128 character password. Signup starts a session and opens the dashboard. Create an organization; you become its Admin. Sign out and sign back in at <http://localhost:3000/login>. The public system status page remains at `/`.

### Verify organization permissions locally

1. Use separate browser profiles (or a normal and private window) for two accounts, Alice and Bob. Tabs in the same profile share cookies and therefore share a login.
2. Register Bob before trying to add him. As Alice, create organization A and add Bob by his registered email with the Member role. No email is sent.
3. As Bob, create organization B. Bob is Member in A and Admin in B. Switching organizations changes both the member list and available controls.
4. Bob can read A's members but cannot add/remove members or change roles there. Alice cannot read B or its members. The API enforces these restrictions even if a request bypasses the UI.
5. Promote Bob to Admin in A, then demote Alice. Her existing session immediately loses Admin permissions there. Removing a membership immediately removes access to that organization.
6. Removing or demoting the last Admin returns HTTP 409. Unknown organizations and organizations outside your memberships return HTTP 404.
7. Sign out and revisit `/dashboard`: it redirects to login. Test token expiry by temporarily setting `ACCESS_TOKEN_MINUTES=1`, restarting the backend, and logging in again. After expiry, opening `/dashboard` renews the session through `/session` and returns to the guarded page.

### Authentication and cookie architecture

Browser authentication requests use same-origin `/api/backend/...` Next.js route handlers. The proxy forwards only approved identity/organization paths and the Cookie, Origin, CSRF, and content-type headers to the server-only `BACKEND_URL`. It forwards each `Set-Cookie` header separately. Authentication tokens are never returned in JSON or stored in localStorage/sessionStorage. The existing health page continues using `NEXT_PUBLIC_API_URL` directly.

FastAPI sets host-only HttpOnly cookies for access, refresh, and CSRF. The browser reads a signed CSRF value from `GET /auth/csrf` into memory and sends it in `X-CSRF-Token` on every mutation. FastAPI requires a trusted Origin plus a matching, signed, session-bound CSRF token, including for registration, login, refresh, and logout. CORS uses explicit origins and credentials; wildcard origins are rejected. The proxy preserves the original Origin rather than inventing a trusted one.

The dashboard's server component forwards its request cookies to FastAPI `/auth/me` with caching disabled. FastAPI verifies the JWT signature, issuer, audience, expiry, user, and live database session. Missing/invalid authentication redirects to login. Expired access with a refresh cookie redirects to `/session`, whose client performs a CSRF-protected POST refresh and re-enters the server guard. Server components never attempt to mutate cookies. Backend outages show an error boundary instead of rendering protected data.

Access JWTs last 10 minutes by default. Refresh sessions have a fixed seven-day absolute expiry (`SESSION_DAYS`), which rotation does not extend. Refresh tokens are random values stored only as SHA-256 hashes. Rotation locks the session row and consumes each refresh token once. Reuse of a consumed token revokes the entire session, including already issued access JWTs. Browser refresh is coordinated within a tab and across tabs using Web Locks where supported. Strict replay detection means clients must not independently retry an already consumed refresh token; browsers without Web Locks should avoid simultaneous refreshes across tabs.

Logout revokes the current session and clears cookies; other logged-in devices retain their independent sessions. Every protected API request checks current session revocation and current organization membership; role claims and frontend organization selection never grant access. Five failed password attempts lock an existing account for five minutes. Passwords use Argon2id, and validation errors never echo password inputs.

For production, set `ENVIRONMENT=production`, a strong `AUTH_SECRET` of at least 32 bytes, `COOKIE_SECURE=true`, HTTPS-only explicit `CORS_ORIGINS`, and an appropriate server-only `BACKEND_URL`. Cookies use `SameSite=Lax`, `Secure`, and the `__Host-` prefix with no Domain attribute. Serve Next.js through HTTPS. Non-development configurations missing these safeguards are rejected. Shared gateway rate limiting remains a deployment responsibility; the implemented account lockout persists across API workers.

### Phase 2 data model and API

Migration `0002_identity` adds five tables without changing existing pgvector data:

| Table | Purpose |
| --- | --- |
| `users` | Normalized unique email, display name, password hash, login lockout |
| `organizations` | Independent team workspaces |
| `memberships` | Unique user/organization pairs with a checked `admin` or `member` role |
| `auth_sessions` | User session families, absolute expiry, revocation |
| `refresh_tokens` | Hashed refresh history and consumption timestamps for replay detection |

All API paths below have the `/api/v1` prefix; the browser proxy uses `/api/backend` instead:

| Method | Endpoint | Access |
| --- | --- | --- |
| GET | `/auth/csrf` | Public CSRF bootstrap; no-store |
| POST | `/auth/register`, `/auth/login` | Public, trusted Origin + CSRF |
| POST | `/auth/refresh`, `/auth/logout` | Refresh session cookie + trusted Origin + CSRF |
| GET | `/auth/me` | Valid access JWT and active database session |
| GET / POST | `/organizations` | List own memberships / create as Admin |
| GET | `/organizations/{id}` | Member of the specified organization |
| GET / POST | `/organizations/{id}/members` | Read as Member; add existing users as Admin |
| PATCH / DELETE | `/organizations/{id}/members/{user_id}` | Organization Admin; last Admin protected |
| GET | `/health`, `/health/ready` | Public Phase 1 endpoints, preserved |

Foreign keys and uniqueness/check constraints enforce structural integrity. Membership mutations lock the organization row before authorization and last-Admin checks, preventing concurrent demotions/removals from leaving zero Admins. UUIDs are identifiers, not authorization. No global user directory, invitation emails, verification, password recovery, MFA, SSO, documents, RAG, or agents are included.

### Phase 2 automated checks

From `backend`, with PostgreSQL running:

```powershell
.\.venv\Scripts\python.exe scripts/test_postgres.py
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m alembic check
```

The test runner uses configured local database credentials to create a uniquely named `documind_test_...` database, applies both migrations, checks ORM/migration consistency, and runs the complete pytest suite. It removes only its own test database afterward. Your database role needs `CREATEDB` (the local Compose role has it). Each integration test gets an isolated schema with separate connections, enabling real transaction and concurrency tests. IPv4 is used for local test connections to avoid Windows IPv6 connection delays.

Alternatively, provide `TEST_DATABASE_URL` pointing to a dedicated database whose name starts with `documind_test_`, then run `python -m pytest`; it must never point at the development database. Plain `pytest` without that variable runs Phase 1 and security-configuration tests and explicitly skips PostgreSQL integration tests. Do not interpret those skips as a complete authentication test pass.

From `frontend`:

```powershell
npm test
npm run lint
npm run typecheck
npm run build
```

To verify the production frontend, cookie proxy, server-side guards, and API together over real HTTP, build the frontend first, then run from `backend`:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_fullstack.py
```

This starts temporary servers on ports 3001 and 8001 and uses a separate temporary database. Those ports must be free. It tests registration, login, logout, refresh/replay, CSRF, and organization isolation, then removes its own servers and database. Existing services on ports 3000 and 8000 are preserved.

Tests cover password hashing/validation, secure cookies, CSRF/origin/session binding, login lockout, JWT expiry/signatures, refresh rotation/replay/concurrency, logout revocation, multiple organizations, immediate role changes, cross-organization denials, and concurrent last-Admin protection. Frontend tests cover forms/errors/loading, the server guard, cookie proxying, coordinated refresh, and organization switching. The existing health/status tests remain in place. A third-party Starlette test-client deprecation warning may appear with the installed HTTPX version.

## Project structure

```text
frontend/
  src/app/             Next.js App Router pages and global styles
  src/components/      Status UI
  src/lib/             API client and tests
backend/
  app/api/             HTTP routes and dependencies
  app/core/            Environment-based settings
  app/db/              SQLAlchemy engine, sessions, model base
  app/models/          Identity and organization ORM models
  app/services/        Authentication and authorization use cases
  alembic/             Database migrations
  tests/               API tests
compose.yaml           Local PostgreSQL with pgvector
```

## Windows prerequisites

- Node.js 22 LTS or newer supported LTS (minimum 20.9).
- Python 3.11+ with pip and the Python launcher (`py`).
- Docker Desktop running with Linux containers and WSL 2 enabled.
- PowerShell. Use `npm.cmd` if your execution policy blocks `npm.ps1`.
- Sufficient free disk space for dependencies and the PostgreSQL image.

Run all commands from the project root unless a step changes directory. No Git initialization is required.

## 1. Configure the environment

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env.local
```

Use these copy commands only on first setup; preserve any existing local configuration. Set a local `POSTGRES_PASSWORD` in `.env` and put the same credentials into `DATABASE_URL` in `backend/.env`. URL-encode special characters in the connection URL's password. If you change `POSTGRES_PORT`, update the URL too.

The root `.env` configures Compose. The backend reads `backend/.env` independently of its working directory. Next.js reads `frontend/.env.local`; `NEXT_PUBLIC_API_URL` is a browser-visible backend origin, not a secret. Restart the frontend after changing it (rebuild for a production build). Use `localhost` consistently: CORS allows `http://localhost:3000` by default. Add other origins to the JSON array in `CORS_ORIGINS` when needed.

Never put secrets in `NEXT_PUBLIC_*` variables. Local environment files are ignored; examples are tracked.

## 2. Start PostgreSQL

```powershell
docker compose up -d --wait db
docker compose ps
```

PostgreSQL is bound to `127.0.0.1:5432`, with a named volume for persistence. This is a development service, not production infrastructure. The image contains pgvector; the Alembic migration enables it in the selected database.

## 3. Install and start the backend

In a PowerShell terminal:

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -c "import secrets; from dotenv import dotenv_values,set_key; dotenv_values('.env').get('AUTH_SECRET') or set_key('.env','AUTH_SECRET',secrets.token_urlsafe(48))"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Using the virtual environment executable directly avoids PowerShell activation-policy changes. If `py` or `python` opens the Microsoft Store, install Python or use the actual installed `python.exe` path to create the virtual environment.

- API liveness: <http://localhost:8000/api/v1/health>
- Database/pgvector readiness: <http://localhost:8000/api/v1/health/ready>
- Interactive API docs: <http://localhost:8000/docs>

Liveness returns HTTP 200 without querying PostgreSQL. Readiness returns HTTP 200 only when the database is reachable and the vector extension is enabled; otherwise HTTP 503 with sanitized service statuses. Connection and statement timeouts bound database probe delays. Backend startup creates an engine without requiring a live connection, so database outages can be diagnosed through readiness.

## 4. Start the frontend

Open another terminal at the project root:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. The page fetches live API and readiness responses from the browser, displays unavailable services, and supports manual refresh. The initial display is a loading state. If the API is stopped, the frontend still renders and reports the failure. Requests time out after five seconds.

After a package lock has been generated, use `npm ci` for repeat installations.

## Checks and tests

Backend (from `backend`):

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m alembic upgrade head --sql
```

Phase 1 health tests override database sessions and need no running PostgreSQL. They exercise liveness, readiness, database failures, missing pgvector, sanitized errors, and CORS. Use the Phase 2 PostgreSQL test runner above to run authentication and organization integration tests too. Offline migration SQL verifies migration rendering without modifying a database.

Frontend (from `frontend`):

```powershell
npm test
npm run typecheck
npm run lint
npm run build
```

Tests cover healthy/degraded responses, network and response failures, UI status display, and refreshing. To serve the production frontend after building, use `npm start`.

For a live database smoke check, start PostgreSQL, apply migrations, and start the backend as above, then run:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
Invoke-RestMethod http://localhost:8000/api/v1/health/ready
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT extname FROM pg_extension;"'
```

## Migrations and architecture

SQLAlchemy owns persistence; route modules access sessions through an injectable FastAPI dependency. Sessions close after each request and roll back on errors; future write operations must commit explicitly. The declarative base defines stable constraint names. Import future model modules in `alembic/env.py` before generating migrations:

```powershell
# From backend, after adding/importing ORM models:
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe schema change"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Review generated migrations before applying them. Schema changes are explicit, not performed during application startup. The initial migration enables pgvector without adding premature domain tables. Its downgrade preserves the extension because it may be shared or have dependent data. Backend dependencies use bounded compatible ranges; frontend installations produce a package lock for reproducibility.

Application use cases live separately from HTTP and database code. Organization authorization is implemented in Phase 2; future document retrieval must enforce those permissions before content reaches any AI adapter. No document or AI endpoints are included yet.

## Stopping and troubleshooting

Press Ctrl+C in the frontend and backend terminals. Run `docker compose stop` to stop the database, or `docker compose down` to remove containers while retaining the database volume. Do not remove the volume unless you intend to delete local database data.

- Docker connection errors: launch Docker Desktop, select Linux containers, and verify `docker info` works.
- Port conflicts: change `POSTGRES_PORT` and `DATABASE_URL` together; frontend/backend port changes also require API URL and CORS changes.
- Database authentication errors after changing `.env`: PostgreSQL initialization credentials apply only to a new volume. Update credentials inside PostgreSQL for an existing database.
- Database operational but pgvector unavailable: run `alembic upgrade head` against the same database used by the API.
- Registry or installation failures: check network access, permissions, and free disk space before retrying.
