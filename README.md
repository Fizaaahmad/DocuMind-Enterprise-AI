# DocuMind

Enterprise document intelligence platform. Phase 3 adds organization-scoped document storage, a document library, source-aware text extraction, optional selective Tesseract OCR, chunking, and durable PostgreSQL-backed processing to the authenticated full-stack foundation. Embeddings, Claude, RAG, and agents are not implemented.

## Optional PDF OCR: Windows installation and configuration

OCR is **disabled by default**. Normal PDF extraction, DOCX, TXT, authentication, and document permissions do not require Tesseract. Install the native executable separately; no Python OCR wrapper or new service is needed.

### Install and verify Tesseract

In PowerShell:

```powershell
winget install --exact --id UB-Mannheim.TesseractOCR --source winget
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --tessdata-dir "C:\Program Files\Tesseract-OCR\tessdata" --list-langs
```

Allow the installer elevation prompt if requested. The package is published in the [Microsoft WinGet community repository](https://github.com/microsoft/winget-pkgs/tree/master/manifests/u/UB-Mannheim/TesseractOCR). If WinGet is unavailable, use the Windows installer linked by the [Tesseract installation documentation](https://tesseract-ocr.github.io/tessdoc/Installation.html) at [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki). Adjust paths below if you chose another installation folder. Explicit paths work without restarting your shell to refresh PATH.

Confirm that `eng` appears in the language list. Select English during installation. Additional languages need their matching `.traineddata` files. Language data can alternatively live in a private project directory. For example, from the project root:

```powershell
New-Item -ItemType Directory -Force .\backend\var\tessdata | Out-Null
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/eng.traineddata" -OutFile ".\backend\var\tessdata\eng.traineddata"
```

These are official [Tesseract fast language models](https://github.com/tesseract-ocr/tessdata_fast). If you use that directory, configure `OCR_TESSDATA_DIR=var/tessdata` rather than the installation's directory. For `eng+urd`, install both `eng.traineddata` and `urd.traineddata` into the selected directory. Up to three language codes are supported; language packs consume additional memory and processing time.

### Enable OCR without changing secrets

After the executable and language checks succeed, add or update these values in `backend/.env`:

```dotenv
OCR_ENABLED=true
TESSERACT_CMD='C:/Program Files/Tesseract-OCR/tesseract.exe'
OCR_TESSDATA_DIR='C:/Program Files/Tesseract-OCR/tessdata'
OCR_LANGUAGE=eng
OCR_DPI=200
OCR_MIN_TEXT_CHARACTERS=20
OCR_MAX_PAGES=20
OCR_MAX_PIXELS=12000000
OCR_PAGE_TIMEOUT_SECONDS=30
OCR_DOCUMENT_TIMEOUT_SECONDS=180
OCR_MEMORY_LIMIT_MB=512
```

Or apply the essential values from PowerShell at the project root, preserving all existing database/authentication configuration:

```powershell
cd backend
@'
from dotenv import set_key
for key, value in {
    "OCR_ENABLED": "true",
    "TESSERACT_CMD": "C:/Program Files/Tesseract-OCR/tesseract.exe",
    "OCR_TESSDATA_DIR": "C:/Program Files/Tesseract-OCR/tessdata",
    "OCR_LANGUAGE": "eng",
    "OCR_DPI": "200",
}.items():
    set_key(".env", key, value)
'@ | .\.venv\Scripts\python.exe -
```

If using `backend/var/tessdata`, change the directory value in that command to `var/tessdata`. Relative tessdata paths resolve against `backend/`. The remaining OCR values use the defaults shown above. The executable is discovered via PATH when `TESSERACT_CMD=tesseract`; installation/language checks run only when a page needs OCR, never just because OCR is enabled.

Stop the old worker with Ctrl+C in its terminal, then restart it from `backend`:

```powershell
.\.venv\Scripts\python.exe -m app.documents.worker
```

Also restart the backend after changing shared environment settings:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

No database migration is needed. Keep the normal frontend and PostgreSQL processes running. Set `OCR_ENABLED=false` and restart the worker to disable OCR again.

### Test scanned and mixed PDFs

1. Sign in at <http://localhost:3000>, open Documents, and select an organization.
2. Upload an image-based/scanned PDF. It should move from Pending through Processing to Completed, unless the scan is unreadable or a resource limit is exceeded.
3. Open details: source labels show `Page N · OCR`; chunk counts and extracted text include the recognized content. Original page numbers are retained. Source metadata records OCR engine, language, DPI, page count, and the original page numbers that used OCR.
4. Upload a mixed PDF: native pages show `Page N · native`, scanned pages show `Page N · OCR`. Short native titles and small logos should not trigger OCR; truly blank pages and white scanned pages are skipped.
5. After enabling OCR, select Retry processing on a previously Failed scanned PDF. Completed documents are not automatically reprocessed; upload again if you need to change their extraction.
6. Set `OCR_MAX_PAGES=1`, restart the worker, and upload a PDF with two scanned pages. It must become Failed with a clear limit error, not Completed with partial content. Restore the setting afterward. Limits/errors publish no partial sections or chunks.

To create a synthetic scanned/mixed PDF without another image library, run from `backend`:

```powershell
@'
from pathlib import Path
import pymupdf
with pymupdf.open() as source:
    page = source.new_page(width=600, height=240)
    page.insert_text((35, 75), "DOCUMIND SCANNED DOCUMENT", fontsize=22)
    page.insert_text((35, 120), "Revenue report number 12345", fontsize=22)
    image = page.get_pixmap(dpi=150).tobytes("png")
Path("var").mkdir(exist_ok=True)
with pymupdf.open() as document:
    document.new_page(width=600, height=240).insert_image(pymupdf.Rect(0, 0, 600, 240), stream=image)
    document.save("var/ocr-sample.pdf")
    document.new_page(width=600, height=240).insert_text((35, 75), "Native text stays native.", fontsize=22)
    document.save("var/ocr-mixed-sample.pdf")
print("Upload backend/var/ocr-sample.pdf and backend/var/ocr-mixed-sample.pdf")
'@ | .\.venv\Scripts\python.exe -
```

### OCR safeguards, behavior, and limitations

Native PyMuPDF text remains preferred. Pages below the meaningful-text threshold are OCR candidates only when substantial image/vector content suggests a scan or the extracted text is corrupt. Short native-text-only pages and small logos stay native. A bounded grayscale thumbnail detects white/empty scans before checking Tesseract. This is a page-selection heuristic, not a general image classifier: unusual layouts may need threshold adjustment, and text-heavy pages containing additional scanned regions are not independently OCRed region by region.

Only selected pages are rendered at `OCR_DPI` (72–400). Dimensions are checked before full rendering; `OCR_MAX_PIXELS` defaults to 12 megapixels. Pages are rendered one at a time in grayscale, Tesseract is restricted to one OpenMP thread, and PNG/text travel through process pipes instead of temporary image files. `OCR_MAX_PAGES` counts actual OCR pages, excluding native/blank pages; the default is 20, with a validated maximum of 200. The total OCR budget includes checks, rendering, and recognition from the first candidate page.

The OCR-enabled PDF parser applies OS memory limits before importing PyMuPDF: Windows uses a Job Object covering the parser and its OCR descendants; Linux uses an inherited per-process address-space limit. The default is 512 MiB (configurable 256–2048 MiB). On Linux this bounds each process, rather than an aggregate container memory quota. A host that cannot establish the memory guard fails closed with an actionable error. This is resource containment, not an OS security sandbox.

Each Tesseract invocation has a page deadline (default 30 seconds), within a document OCR budget (default 180 seconds). The outer parser timeout and queue lease are extended consistently: with default OCR-enabled PDF settings, processing can take up to `PROCESSING_TIMEOUT_SECONDS + OCR_DOCUMENT_TIMEOUT_SECONDS` = 240 seconds, with a 270-second lease. DOCX/TXT and OCR-disabled PDFs keep their existing budgets. Interrupted jobs resume only after their previous lease expires. Windows closes/kills the job's OCR descendants when the parser exits; outer timeout/cancellation terminates the owned process tree. Linux parser trees run in their own process group and are killed together on timeout/cancellation.

Missing executables/languages, OCR failures, no recognized text on a nonblank candidate page, and exceeded page/pixel/time limits produce sanitized Failed states. Fix the installation/settings/scan and use the existing authorized Retry action. Extraction still publishes atomically and remains bound to the same organization, document, sections, and chunk references. OCR does not change storage permissions, membership checks, downloads, or deletion fencing. OCR accuracy depends on scan quality, orientation, and installed language models; handwriting and complex layouts may be imperfect. OCR does not create a searchable replacement PDF; the original stays unchanged.

### OCR regression tests and Linux deployment

From `backend`, run the complete existing and OCR test suite against an isolated database:

```powershell
.\.venv\Scripts\python.exe scripts/test_postgres.py
.\.venv\Scripts\python.exe -m ruff check .
```

The real OCR test discovers Tesseract from `backend/.env` or PATH. Optional explicit overrides are:

```powershell
$env:TEST_TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
$env:TEST_OCR_TESSDATA_DIR = "C:\Program Files\Tesseract-OCR\tessdata"
.\.venv\Scripts\python.exe -m pytest tests/test_ocr.py -q
```

That test uses a real rasterized scanned page and the actual parser child with OS resource limits. It is explicitly skipped when the executable is unavailable; broken installations or missing English data fail instead of being reported as a pass. Tests without `TEST_DATABASE_URL` skip PostgreSQL-dependent tests; use the isolated runner for complete verification. Mocked OCR tests cover page selection, blank/short-native pages, provenance, missing languages, failures, page/pixel/time limits, worker publication/rollback/retry, and resource-budget configuration. A separate real child-process test checks OS memory-limit enforcement without limiting the test runner itself.

On Debian/Ubuntu, install `tesseract-ocr` and `tesseract-ocr-eng` in the worker host/image, set `TESSERACT_CMD=tesseract`, and use its installed tessdata directory (or leave `OCR_TESSDATA_DIR` empty). The Python code uses the same CLI adapter and PostgreSQL worker on Windows and Linux. No Redis, Celery, cloud OCR, Claude, embeddings, RAG, or agents are introduced.

## Phase 3: Windows setup and startup

Keep existing environment files and database volumes. From the project root:

```powershell
docker compose up -d --wait db
cd backend
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
# Review the additive Phase 3 SQL before applying it:
.\.venv\Scripts\python.exe -m alembic upgrade 0002_identity:head --sql
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Open a second PowerShell terminal at the project root for the worker:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.documents.worker
```

Open a third PowerShell terminal at the project root for Next.js:

```powershell
cd frontend
npm ci
npm run dev
```

Visit <http://localhost:3000>, sign in, and select **Documents** from the dashboard. The library is at `/documents`; organization context is checked against your live memberships. Team management stays at `/dashboard`, and the Phase 1 status page stays at `/`.

The worker is a separate Python process, not an API background thread. It uses the existing PostgreSQL database; no Redis, Celery, extra container, or third-party queue service is required. Both the API and worker must run for the complete workflow. Without a worker, valid uploads remain Pending and deletions remain queued for cleanup.

### Manually test the complete document workflow

1. Create or select an organization. Upload a UTF-8 `.txt`, a `.docx` containing paragraphs and a table, and a text-based `.pdf` with multiple pages. Drag-and-drop and file selection both work, with up to ten sequential uploads per batch.
2. Watch transfer progress, then Pending/Processing/Completed. Transfer progress measures bytes sent to the frontend server; **Saving…** means the server has not yet accepted the document. Queued processing is separate from transfer progress.
3. Click a filename. Confirm original byte size, source/chunk counts, metadata, and extracted content. PDFs preserve actual page numbers. DOCX uses heading/block references and includes table text; TXT uses a text-source section. DOCX/TXT do not receive invented page numbers.
4. Search by filename and filter by format/status; change sorting and browse pages. This is ordinary filename search, not semantic search. The library refreshes while visible; details poll during processing.
5. Download the original and compare it with the uploaded file. Originals are attachments, not public/static assets or inline HTML previews.
6. Try an empty file, `.exe`, a renamed non-PDF, and a file above the configured limit. They should be rejected. A damaged PDF with a recognizable PDF header may be accepted but then become Failed during extraction. Image-only PDFs need the optional OCR setup above; with OCR disabled they fail with an explanation.
7. On a Failed document, inspect the sanitized error and select **Retry processing** after fixing a relevant configuration issue. A damaged source must be replaced with a new upload. Retry uses the current API chunking settings; worker parsing limits apply when the worker processes it.
8. Delete a document as its uploader or an organization Admin. It disappears immediately and all content/download endpoints deny further access. The worker removes its original file, sections, chunks, and database record. Other ordinary Members can read/download but cannot delete or retry someone else's document.
9. Use a different browser profile/private window for a second account. Verify that files from an organization it has not joined are absent and inaccessible, even with a known document ID. A user belonging to two organizations sees a separate library for each.
10. Stop the worker, upload a file, and restart it: the Pending job survives and completes. For a worker terminated during processing, the existing lease must expire before reclamation (default maximum 90 seconds). A late result from a deleted or superseded job cannot restore content.

### Configurable storage, limits, and chunking

Add overrides to `backend/.env` only when changing defaults. Restart the API and worker after environment changes. Do not overwrite existing database or authentication secrets.

| Variable | Default | Meaning |
| --- | --- | --- |
| `STORAGE_PATH` | `var/documents` under `backend/` | Private local file storage; absolute paths also supported |
| `UPLOAD_MAX_BYTES` | `20971520` | Maximum original file size: 20 MiB |
| `CHUNK_SIZE` | `1200` | Maximum characters per chunk |
| `CHUNK_OVERLAP` | `200` | Overlap in characters; must be smaller than chunk size |
| `EXTRACTION_MAX_CHARACTERS` | `2000000` | Maximum extracted text per document |
| `EXTRACTION_MAX_PAGES` | `1000` | Maximum PDF pages |
| `DOCX_MAX_UNCOMPRESSED_BYTES` | `41943040` | Maximum declared expanded DOCX archive size |
| `PROCESSING_MAX_CHUNKS` | `10000` | Maximum chunks published per document |
| `PROCESSING_TIMEOUT_SECONDS` | `60` | Parser subprocess time limit |
| `WORKER_POLL_SECONDS` | `2` | Idle queue polling interval |
| `WORKER_MAX_ATTEMPTS` | `3` | Processing retry/recovery budget |

The browser discovers the file limit through an authorized API configuration endpoint. The Next.js upload proxy obtains the same limit directly from FastAPI, so no separate frontend limit variable is needed. Both proxy and API enforce bounded request bodies, including chunked requests without Content-Length; multipart framing has a separate 64 KiB allowance. Originals themselves must still fit `UPLOAD_MAX_BYTES`.

Storage uses generated organization/document UUID keys, sanitized display filenames, atomic file replacement, and SHA-256 checksums. The folder is ignored by Git and never served as a static directory. API/storage calls derive keys from authorized records, not user-supplied paths. Relative `STORAGE_PATH` values resolve against `backend/` regardless of the launch directory. API and worker must share the same configured storage. For multiple hosts, supply shared private storage or a future cloud adapter through the `Storage` interface/factory; a cloud provider is not implemented yet. Back up the database and file directory together.

PDF extraction uses PyMuPDF in a dedicated child process, with optional selective Tesseract OCR as documented above; DOCX uses python-docx; TXT accepts UTF-8 (with/without BOM) or BOM-marked UTF-16. DOCX archives are checked for unsafe paths, excessive expansion, encryption, and macros. Processing is bounded by text/page/chunk limits and a parser timeout. This is parser isolation, not an operating-system sandbox or malware scanner. DOCX headers/footnotes are not extracted in this phase.

### Processing and deletion architecture

Migration `0003_documents` adds `documents`, `document_sections`, `document_chunks`, and `document_jobs`. Composite foreign keys bind sections/chunks/jobs to their document and organization. Existing user, session, membership, pgvector, and health behavior is retained.

Uploads reserve a document and job before storing the original, then make the job available after the file is complete. A short organization/document lock protects the bounded local file copy against membership/deletion races. Interrupted reservations are reclaimed after ten minutes. Original files never use their display filenames as storage paths.

The worker claims jobs using PostgreSQL row locks with `SKIP LOCKED` and an expiring lease token. It commits Processing before parsing, holds no database locks during parsing, and publishes sections/chunks atomically only while it still owns the lease. Parser children are terminated on timeout, including the Windows venv child-process tree. Restarted workers reclaim expired leases; stale workers cannot publish after reclamation or deletion. Chunk offsets reference extracted source sections and never cross section boundaries.

Transient failures retry with backoff up to the processing budget; invalid documents and parser timeouts become Failed and allow explicit retry. Deletion first hides a document and replaces its processing job with a cleanup job, fencing late results. Cleanup tolerates missing files and retries storage/permission errors with capped backoff until cleanup succeeds. On Windows, an open download/file handle may temporarily delay removal. Filesystem and PostgreSQL updates cannot be a single transaction, so durable reservations and idempotent cleanup bridge the two systems.

### Document API and tests

All paths below are relative to `/api/v1/organizations/{organization_id}/documents`. Every route requires an active authenticated session and membership in that organization. The browser uses the same paths under `/api/backend`, with the existing HttpOnly cookie/CSRF flow.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/config` | Authorized file-size limit and supported formats |
| POST | base path | One multipart `file`; HTTP 202 after storage and queueing |
| GET | base path | `q`, `status`, `format`, `sort`, `page`, `page_size` |
| GET | `/{id}` | Metadata and processing status/error |
| GET | `/{id}/content` | Paginated extracted source sections |
| GET | `/{id}/download` | Authorized original attachment |
| POST | `/{id}/retry` | Uploader/Admin retries a Failed document |
| DELETE | `/{id}` | Uploader/Admin hides document and queues cleanup; HTTP 202 |

From `backend`, run the complete PostgreSQL-backed suite and backend checks:

```powershell
.\.venv\Scripts\python.exe scripts/test_postgres.py
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m alembic check
```

From `frontend`:

```powershell
npm test
npm run lint
npm run typecheck
npm run build
```

After building the frontend, run from `backend`:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_fullstack.py
```

The HTTP smoke test starts its own API, production Next.js server, and worker, using a temporary database and storage directory. Ports 3001/8001 must be free. It verifies Phase 2 auth plus multipart upload, actual processing, content references, filename filters, download bytes, organization restrictions, and deletion cleanup. It removes only its own temporary resources. The backend suite also covers invalid/oversized files, PDF/DOCX/TXT extraction, failed extraction, source/chunk integrity, rollback, timeout/recovery, deletion races, and storage failures. Frontend tests cover upload progress/cancellation, validation/errors, library filters, organization switching, details, and deletion controls.

To process at most one ready job for diagnosis, run `python -m app.documents.worker --once` with the backend virtual environment. A Pending document with no worker is expected; a Failed document has a user-facing explanation. Worker logs identify jobs by document UUID and do not print credentials or extracted content.

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

Foreign keys and uniqueness/check constraints enforce structural integrity. Membership mutations lock the organization row before authorization and last-Admin checks, preventing concurrent demotions/removals from leaving zero Admins. UUIDs are identifiers, not authorization. Documents are added in Phase 3 above. No global user directory, invitation emails, verification, password recovery, MFA, SSO, RAG, or agents are included.

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

Application use cases live separately from HTTP and database code. Organization authorization is implemented in Phase 2 and enforced by Phase 3 document retrieval. Future AI adapters must preserve these checks before consuming source content. AI endpoints remain deferred.

## Stopping and troubleshooting

Press Ctrl+C in the frontend and backend terminals. Run `docker compose stop` to stop the database, or `docker compose down` to remove containers while retaining the database volume. Do not remove the volume unless you intend to delete local database data.

- Docker connection errors: launch Docker Desktop, select Linux containers, and verify `docker info` works.
- Port conflicts: change `POSTGRES_PORT` and `DATABASE_URL` together; frontend/backend port changes also require API URL and CORS changes.
- Database authentication errors after changing `.env`: PostgreSQL initialization credentials apply only to a new volume. Update credentials inside PostgreSQL for an existing database.
- Database operational but pgvector unavailable: run `alembic upgrade head` against the same database used by the API.
- Registry or installation failures: check network access, permissions, and free disk space before retrying.
