# Local development setup

This is the current first-install guide. The [main README](../README.md#quick-start--run-locally)
contains the shorter Windows path. The former README is preserved in the
[detailed development reference](development-history.md), including phase-specific
walkthroughs, API descriptions, authorization tests and operational semantics.

## Prerequisites

- Git, Python **3.11+** with pip, Node.js **20.9+**, and npm. The frontend Dockerfile uses Node 22.
- Docker Desktop with Linux containers/Compose on Windows; Docker Engine plus Compose on Linux.
- PowerShell on Windows. Direct venv executables avoid activation-policy changes;
  use `npm.cmd` if PowerShell blocks `npm.ps1`.
- Internet access for initial dependencies, container image and explicit model preparation;
  enough disk/memory for PyTorch, Sentence Transformers and the model cache.
- Free ports 3000 (frontend), 8000 (API) and 5432 (database), unless configured otherwise.

The development [Compose file](../compose.yaml) provides **only PostgreSQL with pgvector**.
Run FastAPI, the worker and Next.js locally. Production has a separate Compose stack;
do not combine production/development files or settings.

## 1. Clone and configure

For a fresh clone, from a directory where `DocuMind` does not already exist:

```powershell
git clone https://github.com/Fizaaahmad/DocuMind-Enterprise-AI.git DocuMind
Set-Location DocuMind
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env.local
```

Do not rerun copy commands over existing local environments. Update individual keys
instead. No real credentials belong in Git, screenshots or `NEXT_PUBLIC_*` variables.

### Mandatory local settings

| File | Keys | Requirement |
|---|---|---|
| Root `.env` | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` | Choose a private local password; the example username/database are `documind`, port 5432. Compose initializes a new volume with these values. |
| `backend/.env` | `DATABASE_URL` | Match the database user/password/name/host port. Use a `postgresql+psycopg://` URL. Prefer host `127.0.0.1` on Windows. URL-encode special characters in the password. |
| `backend/.env` | `AUTH_SECRET` | Generate a random secret of at least 32 bytes; the command below writes one without displaying it. Preserve existing secrets on updates. |
| `backend/.env` | `ENVIRONMENT`, `COOKIE_SECURE`, `CORS_ORIGINS` | Local HTTP: `development`, `false`, and `["http://localhost:3000"]`. Explicit origins are required; wildcard credentialed CORS is rejected. |
| `frontend/.env.local` | `BACKEND_URL` | Server-only API origin, normally `http://127.0.0.1:8000`. Do not add `/api/v1` to this origin. |

Root `.env` configures Compose; it does not configure FastAPI. The backend loads
`backend/.env` independently of shell location, and frontend configuration comes
from `frontend/.env.local`. Process environment variables override dotenv values.
The proxy appends API paths and forwards same-origin browser authentication.

The complete configuration inventories are maintained in the actual examples:
[root](../.env.example), [backend](../backend/.env.example), and
[frontend](../frontend/.env.example). Additional defaults/startup validation are in
[Settings](../backend/app/core/config.py). These are the source of truth; never copy
a private environment file into documentation.

## 2. Start PostgreSQL

From the clone root:

```powershell
docker compose up -d --wait db
docker compose ps
```

The database binds only to `127.0.0.1:${POSTGRES_PORT}` in development and persists
in the named `postgres_data` volume. The image includes pgvector; migrations enable
the extension in the application database. Changing an environment password does
not change credentials in an existing volume—see troubleshooting before resetting anything.

## 3. Install the backend and initialize authentication

```powershell
Set-Location backend
py -3 -m venv .venv
./.venv/Scripts/python.exe -m pip install --upgrade pip
./.venv/Scripts/python.exe -m pip install -e ".[dev]"
./.venv/Scripts/python.exe -c "import secrets; from dotenv import dotenv_values,set_key; dotenv_values('.env').get('AUTH_SECRET') or set_key('.env','AUTH_SECRET',secrets.token_urlsafe(48))"
```

`python-dotenv` is installed through the existing settings dependency. The secret
command keeps a configured value and prints nothing. Installing `.[dev]` includes
pytest and Ruff as well as the runtime dependencies. The separate requirements
lock is used by the backend Docker build; the editable install is the existing
local development workflow.

## 4. Prepare local embeddings and choose a provider

From `backend`, for semantic search and the no-key Assistant preview:

```powershell
./.venv/Scripts/python.exe -m app.intelligence.cli prepare
./.venv/Scripts/python.exe -c "from dotenv import set_key; set_key('.env','EMBEDDINGS_ENABLED','true'); set_key('.env','LLM_PROVIDER','mock'); set_key('.env','LLM_REAL_REQUESTS_ENABLED','false')"
./.venv/Scripts/python.exe -m app.intelligence.cli check
```

`prepare` explicitly downloads the configured model/revision to the local cache
on first use. Runtime inference uses `local_files_only=True`; it does not silently
download a model. The default is `sentence-transformers/all-MiniLM-L6-v2`, pinned to
the example revision, with **384 dimensions**, CPU inference, and bounded batching.
The same profile must be used by the API and worker. No paid embedding API is used.

| Mode | Available behavior |
|---|---|
| `EMBEDDINGS_ENABLED=false`, `LLM_PROVIDER=disabled` | Identity, documents, extraction, deterministic analysis/review and Operations; semantic retrieval/Assistant generation unavailable. Model preparation can be skipped. |
| `EMBEDDINGS_ENABLED=true`, `LLM_PROVIDER=disabled` | Adds indexed semantic search; no generated Assistant response. |
| `EMBEDDINGS_ENABLED=true`, `LLM_PROVIDER=mock` | Adds a clearly labeled extractive development preview, not GPT synthesis. Mock is development-only. |
| Explicitly enabled `LLM_PROVIDER=openai` | Real GPT Q&A; configured GPT extraction, suggestions and comparison explanations. Requires credentials, supported model, positive input/output price settings and explicit real-request enablement. |

For real GPT, use the existing [OpenAI setup and controlled manual test guide](PHASE8.md).
Required provider keys include `LLM_API_KEY` (or supported mounted secret), `LLM_MODEL`,
`LLM_REAL_REQUESTS_ENABLED`, `LLM_INPUT_USD_PER_MILLION` and
`LLM_OUTPUT_USD_PER_MILLION`. Review token/output limits, timeouts, retry behavior,
`AI_DAILY_REQUESTS`, `LLM_DAILY_TOKENS` and `LLM_DAILY_COST_USD` before enabling charges.
Do not assume the historical manual test's estimated cost is current pricing.

GPT is the generative component; embeddings supply retrieval. Structured GPT analysis
uses selected revisions directly and does not require the chat retrieval path.
No OpenAI key is required for the default mock Quick Start. See the
[hybrid architecture](../portfolio/content/architecture-guide.md) for the exact paths.

## 5. Apply migrations and start the API

From `backend`, after checking credentials and database readiness:

```powershell
./.venv/Scripts/python.exe -m alembic heads
./.venv/Scripts/python.exe -m alembic upgrade head --sql
./.venv/Scripts/python.exe -m alembic upgrade head
./.venv/Scripts/python.exe -m alembic check
./.venv/Scripts/python.exe -m uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Offline SQL review does not modify the database. The current chain ends at
`0007_provider_requests`. The application does not auto-reset the database or apply
schema migrations at startup. Back up valuable data before upgrades; downgrades can
lose data. Production recovery/rollback limitations are in the deployment guide.

API liveness: <http://localhost:8000/api/v1/health>. Readiness (database, pgvector,
schema and storage): <http://localhost:8000/api/v1/health/ready>. API docs:
<http://localhost:8000/docs>. Readiness can return 503 with sanitized dependency states.

## 6. Start the worker and frontend

Keep the API terminal running. In terminal 2, starting at the clone root:

```powershell
Set-Location backend
./.venv/Scripts/python.exe -m app.documents.worker
```

In terminal 3, starting at the clone root:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Use <http://localhost:3000> consistently. Register a user, create an organization,
upload a supported file, and wait for processing/indexing before searching or asking
for a mock preview. Authentication tokens stay in HttpOnly cookies. The worker must
remain running for document extraction, indexing, structured analysis and deletion
cleanup. Restart API/worker after changing their settings; restart Next.js after
frontend environment changes. For a production frontend build, rebuild as appropriate.

## Optional PDF OCR

OCR is off by default and applies selectively to PDF pages; native readable text
continues through PyMuPDF. DOCX and TXT do not require Tesseract. Follow the preserved
[Windows Tesseract installation/language instructions](development-history.md#optional-pdf-ocr-windows-installation-and-configuration),
then verify the actual executable and installed languages before enabling:

```powershell
& "C:/Program Files/Tesseract-OCR/tesseract.exe" --version
& "C:/Program Files/Tesseract-OCR/tesseract.exe" --list-langs
```

Update only these keys in the existing `backend/.env`, adjusting paths to the installation:

```dotenv
OCR_ENABLED=true
TESSERACT_CMD='C:/Program Files/Tesseract-OCR/tesseract.exe'
OCR_TESSDATA_DIR='C:/Program Files/Tesseract-OCR/tessdata'
OCR_LANGUAGE=eng
OCR_DPI=200
OCR_MAX_PAGES=20
OCR_PAGE_TIMEOUT_SECONDS=30
OCR_DOCUMENT_TIMEOUT_SECONDS=180
```

The complete backend example also defines text thresholds, pixel and memory limits.
Blank/short native pages are not automatically OCRed; exceeding an OCR limit fails
clearly rather than publishing incomplete extraction. Restart API and worker.
Linux production Docker dependencies and OCR safeguards are covered in the
[preserved OCR reference](development-history.md#ocr-regression-tests-and-linux-deployment).

## Storage, resource limits and indexing

Relative `STORAGE_PATH` and `EMBEDDING_CACHE_PATH` resolve under `backend`, not the
current shell directory. Defaults are `var/documents` and `var/models`, both ignored
by Git. The API and worker must share storage, database and embedding configuration.

The backend example includes configurable upload size (20 MiB default), chunk size
and overlap, extraction/page/chunk limits, processing/analysis/indexing timeouts,
worker polling/retry counts, OCR resource limits, and organization document/storage
quotas. Keep size/overlap coherent; changing model/revision/dimension changes the
embedding profile. Re-prepare the model, restart API/worker and reindex as needed.

To index previously completed documents, from `backend`:

```powershell
./.venv/Scripts/python.exe -m app.intelligence.cli backfill
```

This queues work; it does not replace the worker. The CLI also supports an explicit
`--organization` UUID. Use the organization's indexing controls in the UI for scoped
manual operations. Reviewed data is not silently overwritten by new source revisions.

## Testing

From `backend`, with local PostgreSQL running:

```powershell
$env:LLM_REAL_REQUESTS_ENABLED = 'false'
$env:LLM_PROVIDER = 'mock'
./.venv/Scripts/python.exe scripts/test_postgres.py
./.venv/Scripts/python.exe -m ruff check .
```

Use a dedicated test terminal for these process-level overrides. The isolated
runner creates a uniquely named test database, applies migrations,
checks ORM/migration consistency and runs pytest, then removes only its own database.
The database role needs CREATEDB (the local Compose role has it). Plain `pytest`
without a dedicated `TEST_DATABASE_URL` skips database-dependent tests; do not
interpret those skips as complete integration coverage. Never point a test database
variable at your development database.

From `frontend`:

```powershell
npm test
npm run lint
npm run typecheck
npm run build
```

For real-HTTP proxy/cookie/worker checks, build the frontend first. From `backend`,
with free ports 3001/8001 and cached embeddings:

```powershell
$env:LLM_REAL_REQUESTS_ENABLED = 'false'
$env:LLM_PROVIDER = 'mock'
$env:SMOKE_INTELLIGENCE = '1'
./.venv/Scripts/python.exe scripts/smoke_fullstack.py
```

Use a dedicated test terminal, then close it to avoid keeping its process-level
overrides in a later development session. This test uses a disposable database and
local inference/mock generation, not paid OpenAI. See [UI/browser verification](PHASE9.md)
for isolated fixture-driven responsive checks, and [OpenAI test scope](PHASE8.md#offline-verification)
for provider-specific evidence. Those verification results are historical unless
you rerun the commands; they are not performance benchmarks.

## Troubleshooting

| Symptom | Checks |
|---|---|
| Docker unavailable | Start Docker Desktop, select Linux containers, check `docker info`. |
| PostgreSQL password rejected | Compare root/backend credentials and port. Existing volumes retain their initialized credentials. Identify the actual PostgreSQL instance before changing credentials; do not delete a volume as a shortcut. |
| Slow Windows database connects | Use `127.0.0.1` in the DSN to avoid localhost/IPv6 ambiguity. |
| Auth/configuration startup error | Ensure the generated `AUTH_SECRET` is at least 32 bytes; use explicit JSON CORS origins and local HTTP cookie settings. |
| Frontend cannot reach API | Check API readiness, server-only `BACKEND_URL`, port and proxy route. Restart frontend after environment changes. |
| Document or analysis stays pending | Start the worker against the same DB/storage/config; inspect sanitized worker logs and retry scheduling. OCR is not the cause until a processing job actually starts. |
| Embeddings unavailable | Run `prepare`, enable embeddings, confirm cached model/revision/dimension, restart API/worker and wait for indexing. |
| OCR fails | Check executable, language data and configured page/pixel/time/memory limits. Do not assume a blank page needs OCR. |
| CSRF/session failures | Use `localhost:3000` consistently; preserve proxy cookies, exact CORS origins and matching secure-cookie settings. Do not disable CSRF to work around configuration. |
| Port busy | Change database host port and DSN together. API changes also require `BACKEND_URL`; browser-origin changes require CORS updates. |

Stop each local API/worker/frontend with Ctrl+C. `docker compose stop db` stops the
database without deleting data; `docker compose down` retains the named volume.
Do not use volume-removal commands unless intentionally restoring/deleting data
with a backup and a clear plan.

## Linux/macOS shell differences

The same services/configuration apply. Use `cp` instead of `Copy-Item`, `cd` instead
of `Set-Location`, `python3 -m venv .venv`, and `.venv/bin/python` instead of the
Windows venv executable. Use the same pip, model preparation, Alembic, API and worker
module arguments from the corresponding directories. `npm ci`/`npm run dev` and
Compose commands are unchanged. Install the native Tesseract executable/language
data through your OS tooling if enabling OCR. These shell adaptations are not a
claim that a fresh install on every OS has been independently exercised.

## Production and deeper reference

Use [deployment/backup/restore instructions](../deploy/README.md), the separate
[production Compose file](../compose.production.yaml), and the explicit
[OpenAI configuration/egress guide](PHASE8.md). Production requires generated secrets,
exact HTTPS origins, secure cookies, explicit allowed hosts and shared persistent
storage. Do not use the local HTTP settings in production. No server deployment or
paid service is performed by this guide.

The [development history](development-history.md) retains the full former README,
including manual acceptance scenarios, API routes, review and assignment semantics,
extraction/rule limitations, OCR details and historical migrations. It is supporting
reference, not a replacement for this current first-install sequence.
