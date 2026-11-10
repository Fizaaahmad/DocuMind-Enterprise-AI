# DocuMind

Enterprise document intelligence platform. Phase 1 provides a Next.js/TypeScript/Tailwind frontend, a modular FastAPI backend, and PostgreSQL with pgvector. Authentication, document workflows, RAG, and agents are intentionally deferred.

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

Unit tests override database sessions and need no running PostgreSQL. They exercise liveness, readiness, database failures, missing pgvector, sanitized errors, and CORS. Offline migration SQL verifies migration rendering without modifying a database.

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

Future application use cases and AI adapters should be separate from HTTP and database code. Organization authorization and document retrieval permissions must be introduced before document or AI endpoints. Phase 1 exposes only health routes and development API documentation.

## Stopping and troubleshooting

Press Ctrl+C in the frontend and backend terminals. Run `docker compose stop` to stop the database, or `docker compose down` to remove containers while retaining the database volume. Do not remove the volume unless you intend to delete local database data.

- Docker connection errors: launch Docker Desktop, select Linux containers, and verify `docker info` works.
- Port conflicts: change `POSTGRES_PORT` and `DATABASE_URL` together; frontend/backend port changes also require API URL and CORS changes.
- Database authentication errors after changing `.env`: PostgreSQL initialization credentials apply only to a new volume. Update credentials inside PostgreSQL for an existing database.
- Database operational but pgvector unavailable: run `alembic upgrade head` against the same database used by the API.
- Registry or installation failures: check network access, permissions, and free disk space before retrying.
