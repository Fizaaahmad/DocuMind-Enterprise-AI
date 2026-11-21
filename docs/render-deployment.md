# Prepared Vercel / Render / Supabase demo: operator runbook

**Status: Supabase preparation has completed with explicit approval; Render and
Vercel services have not been deployed.** The dedicated Free project was verified
empty before writes. pgvector 0.8.2, both restricted roles, seven migrations
(head `0007_provider_requests`), and the pinned fictional package were verified.
Runtime privilege and record/file checks passed. **Do not rerun bootstrap or
import on this populated database.** Sections 3�4 are retained as recovery/setup
reference for a new empty approved target, not the next deployment steps.
Local development remains available; dependency pins and revisions are unchanged.

## Implemented protections

- The original named-local-demo-database safeguard is retained.
- Managed mode requires production/secure cookies, an exact 20-character
  `DEMO_SUPABASE_PROJECT_REF`, the matching `documind_demo_app.<ref>` username,
  database `postgres`, an AWS shared session-pooler hostname/port 5432, and
  `sslmode=verify-full` with an explicit `sslrootcert` path.
- The runtime role must be non-administrative, have no role memberships, SELECT
  on application tables, and DML only on session/refresh-token tables. Startup
  refuses unexpected privileges, wrong database identity or mutable business access.
- An explicit `DEMO_DATASET_SHA256` pins the immutable `records.json`. Original
  file hashes and all exported business rows must match at startup. Auth sessions,
  passwords and provider ledgers are excluded from the comparison/package.
- The existing backend route allowlist, organization/source checks, secure cookies,
  CSRF, rotating refresh tokens and replay protection remain active.
- Demo entry is capped at 12 admissions per rolling minute per API process, with
  `Retry-After`. This is deliberately a **global** limit, not a per-IP claim.
  Forwarded-IP headers cannot bypass it. Deploy exactly one API worker. Existing
  persistent session caps and refresh bounds still apply across process restarts.
- Demo DB pooling is limited to 2 pooled + 1 overflow connections. Managed session
  connections apply existing SQL timeouts after connection establishment instead
  of sending the libpq `options` startup parameter. Migration advisory locks still
  use a session connection; transaction pooling is not supported for this runbook.
- Login entry performs at most five short readiness reads, with a 25-second total
  budget, then submits one entry mutation. It never blindly retries entry/login/
  refresh. Sleeping-backend errors during a protected page's server guard lead to
  `/demo-wake`, with an allowlisted return path and explicit check/resume control.
  A healthy 401 still requires login/refresh. Normal mode behavior is unchanged.

## 1. Review the prepared fictional package locally

Canonical assets are under `backend/render-demo-assets/`:

- Six authored PDF/DOCX/TXT originals under organization/document UUID paths.
- `demo-manifest.json`: provenance, snapshot, filenames, checksums and record hash.
- `records.json`: source sections/chunks/revisions, deterministic analyses,
  comparison, review/assignment history and a clearly labeled saved mock answer.

The package was generated in a **new disposable local database**, not copied from
the development database or the existing Supabase project. User password hashes,
sessions, refresh tokens, provider request/usage ledgers and embeddings are absent.
The importer generates fresh random Argon2id password hashes; it preserves IDs,
sources and review identities. No real OpenAI answer or paid usage is fabricated.

Verify offline, from the repository root:

```powershell
$demoHash = (Get-Content backend/render-demo-assets/demo-manifest.json | ConvertFrom-Json).records_sha256
Push-Location backend
.\.venv\Scripts\python.exe -m app.demo.supabase verify --bundle render-demo-assets --sha256 $demoHash
Pop-Location
```

Without `--apply` the operator tool only verifies local files, even for the
bootstrap/import command names. It does not open a database connection.

To generate a *new version* later, choose a new output directory rather than
overwriting the approved package:

```powershell
Push-Location backend
.\.venv\Scripts\python.exe -m app.demo.package --output render-demo-assets-next
Pop-Location
```

That generator refuses non-local database hosts, uses a new random database,
cleans up only its own database, and refuses an existing output directory. New
versions get new IDs/hashes; deploy their files and records as one coordinated
release. Do not mix versions or regenerate assets automatically during builds.

## 2. Local regression and resource checks

```powershell
.\backend\.venv\Scripts\python.exe deploy/demo/verify_local.py

Push-Location frontend
npm test
npm run lint
npm run typecheck
npm run build
Pop-Location

docker build -f backend/Dockerfile.render-demo.example -t documind-render-demo:local backend
.\backend\.venv\Scripts\python.exe deploy/render/verify_local.py
```

The resource verifier uses a new localhost database and an owned temporary Docker
container, limited to 512 MiB and 0.1 CPU. It imports/compares the package, reads
the six originals, exercises saved results/exports and checks denied upload, OOM
state and cgroup peak memory. It removes only its own container/database, leaving
existing application data untouched. It requires the existing local development
PostgreSQL container `documind-db-1`.

Recorded local result: **140.1 MiB peak under the 512 MiB / 0.1 CPU cap**, no OOM,
with the fixture import/download/read/denial checks passing. The unchanged full
dependency image built successfully. See [verification evidence and changed
files](render-verification.md) for the complete test results and scope.

This test uses local HTTP/development cookies for resource measurement; it is
not proof of Render TLS or live Supabase pooler compatibility. Production cookie
configuration and target pinning are separately regression-tested. Reports are
ignored under `deploy/render/verification/`.

## 3. Supabase preparation — ONLY after explicit approval

Do not run these steps now. The selected project must be dedicated to the demo.
If the existing project contains application tables, **stop**: the bootstrap and
importer intentionally refuse populated public/application tables and existing
demo roles. There is no automatic reset, role replacement or destructive recovery.

Before any writes, verify with the owner:

1. The exact project reference and that modifying this project is approved.
2. Free plan, suitable region, empty public schema and no real customer data.
3. pgvector enabled in `public` or `extensions`; no ownership changes to managed
   schemas. Disable application-schema Data API exposure before import.
4. Working shared **session** pooler, its actual hostname, and the matching CA
   certificate. No paid IPv4 add-on or transaction pooler is needed.

The admin connection is used only by the explicit bootstrap tool, through a
hidden prompt. Neither admin nor migrator credentials belong on Render or Vercel.
Have two independent generated passwords of at least 32 characters ready in a
password manager; bootstrap prompts for both without printing or saving them.

Future approved bootstrap command:

```powershell
$env:DEMO_SUPABASE_PROJECT_REF = Read-Host "Exact approved Supabase project reference"
$env:DEMO_DATASET_SHA256 = $demoHash
Push-Location backend
.\.venv\Scripts\python.exe -m app.demo.supabase bootstrap --bundle render-demo-assets --sha256 $demoHash --apply --confirm-project $env:DEMO_SUPABASE_PROJECT_REF
Pop-Location
```

The hidden admin URL must have the form
`postgresql+psycopg://postgres.<ref>:<encoded-password>@<session-pooler>:5432/postgres?sslmode=verify-full&sslrootcert=<local-CA-path>`.
Use URL-encoded passwords/paths as required. The prompt will not echo the URL.
Do not put an actual connection string in CLI arguments, screenshots or Git.

Bootstrap checks for empty public tables, absent demo roles and an existing
vector extension **before** creating anything. It creates two non-superuser,
non-inheriting roles with minimal schema access; it does not drop/reset data.
Any provider permission incompatibility is a stop condition, not a reason to
grant superuser/owner credentials to the API.

## 4. Migrate and import — ONLY after separate database-write approval

Use the `documind_demo_migrator.<ref>` connection via the session pooler and
verified TLS. `MigrationSettings` checks this exact project and role. To avoid
putting a secret URL in PowerShell history, use a hidden child-process prompt:

```powershell
# Project/hash environment values were set above; these are non-secret pins.
.\backend\.venv\Scripts\python.exe -c "import os,getpass,subprocess,sys; os.environ['DATABASE_URL']=getpass.getpass('Migrator SQLAlchemy URL (hidden): '); sys.exit(subprocess.call([sys.executable,'-m','alembic','upgrade','head'],cwd='backend'))"
.\backend\.venv\Scripts\python.exe -c "import os,getpass,subprocess,sys; os.environ['DATABASE_URL']=getpass.getpass('Migrator SQLAlchemy URL (hidden): '); sys.exit(subprocess.call([sys.executable,'-m','alembic','check'],cwd='backend'))"
```

The URL must include `sslmode=verify-full&sslrootcert=<local-CA-path>` and the
correct session endpoint. Confirm migration head `0007_provider_requests` using
`alembic current`/`heads` in the same way. No new migration was added. Render Free
has no pre-deploy migration job, so do not place migrations in its start command.

Then explicitly import using a hidden URL prompt in the child process:

```powershell
.\backend\.venv\Scripts\python.exe -c "import os,getpass,subprocess,sys; os.environ['DATABASE_URL']=getpass.getpass('Migrator SQLAlchemy URL (hidden): '); sys.exit(subprocess.call([sys.executable,'-m','app.demo.supabase','import','--bundle','render-demo-assets','--sha256',os.environ['DEMO_DATASET_SHA256'],'--apply','--confirm-project',os.environ['DEMO_SUPABASE_PROJECT_REF']],cwd='backend'))"
```

The importer verifies hashes and table/column allowlists, locks the import,
refuses any nonempty application table, imports in dependency order, regenerates
inaccessible user passwords, and compares the result before commit. Runtime
grants and removal of unintended anon/authenticated table grants occur in the
same transaction. Failure rolls back the import. It does not import sessions or
provider records. Supabase-managed schemas are not modified.

## 5. Render Free configuration — resource creation requires approval

Use the reviewed root `render.yaml` as the manual Blueprint source;
it disables auto-deploys. The template remains in `deploy/render/`. It
declares one Free Docker web service, no disk/database/worker/cron/pre-deploy hook.
The Dockerfile/context are repo-relative, with context `backend/`. Files are baked
read-only, the process is non-root, and startup refuses `DEMO_MODE` other than true.

Set the following operator values in Render, without printing them:

| Variable | Value/source |
| --- | --- |
| `DATABASE_URL` | Runtime role `documind_demo_app.<ref>`, exact session pooler/5432, database `postgres`, `sslmode=verify-full&sslrootcert=/app/render-demo-ca.crt` |
| CA file | Public provider CA packaged as `backend/render-demo-ca.crt`; no private key or database credentials are included |
| `DEMO_SUPABASE_PROJECT_REF` | Exact approved project reference |
| `DEMO_DATASET_SHA256` | Exact hash in the packaged manifest; the YAML contains the current non-secret fixture hash |
| `AUTH_SECRET` | New independently generated signing secret (Blueprint generates one); never the local signing key |
| `CORS_ORIGINS` | JSON array containing the exact stable HTTPS Vercel production origin |
| `ALLOWED_HOSTS` | JSON array containing the exact Render service hostname, `localhost`, `127.0.0.1` |

Keep all supplied demo/provider-disable settings. Do not set `LLM_API_KEY`, any
provider secret file, or model download flags. The Render service has outbound
connectivity, so application refusal/no key is essential. Its health endpoint is
`/api/v1/health/ready`; cold startup also verifies source files, runtime privileges
and pinned records. The source bundle is approximately 39 KB of originals plus
the small records/manifest files, not a persistent disk or storage bucket.

## 6. Vercel Hobby — resource creation requires approval

Set project Root Directory `frontend`, standard Next.js build and a supported
Node runtime. `frontend/vercel.json` now activates the reviewed deployment
headers and build settings; its source example remains in `deploy/render/`.

Set these for **Production build and runtime**:

```dotenv
DEMO_MODE=true
BACKEND_URL=https://<exact-service>.onrender.com
```

No database URL, signing secret, Supabase key or OpenAI key belongs on Vercel.
No `NEXT_PUBLIC_*` credential or shared cookie Domain is needed. Keep previews
disconnected from the public demo database/secrets; only the stable production
origin is authorized. The browser calls the existing same-origin proxy, which
forwards HttpOnly cookies, Origin and CSRF. Cloud-managed HTTPS replaces NGINX
TLS; the Vercel example carries over practical security headers.

No resource creation or deployment is authorized simply by completing local
tests. Git review/commit/push are also separate actions and have not been done.

## 7. Final live gates — require explicit approval to run

1. Supabase pooler TLS, runtime role, migrations and imported records have passed
   live verification. Recheck runtime startup from Render without rerunning setup.
2. Verify Vercel → Render cookies, CSRF, refresh rotation/logout, exact origins and
   server guard behavior. Check a real cold wake with an expired access token.
3. Open saved history, citations, comparison, review history, obligation filters
   and exports. Compare dataset hash, counts and originals with the package.
4. Test business writes directly against Render as well as the proxy; confirm
   403, backend entry 429/Retry-After, runtime denial of business DML and no jobs.
5. Observe actual memory/CPU and provider dashboards. No paid upgrade, disk,
   worker, API request, keepalive scheduler or automatic scaling is allowed.
6. Record off-platform backup/restore and Supabase pause/resume procedures. Keep
   immutable files and record package together. Session backups remain private.

Free Render sleeps and Supabase can pause; the wake UI is bounded, not an uptime
guarantee. API sign-in is unavailable while the database is paused. Strict $0
requires accepting suspension rather than paid overage and checking account
billing settings before creating services. Native provider limits and terms must
be rechecked at the separately approved deployment step.
