# Read-only portfolio demo: local verification

The full application remains the default (`DEMO_MODE=false`). This separate
demo shows fictional documents and **stored extractive mock previews**, not
live GPT answers. It allows authorized browsing, original downloads, evidence,
comparison results, reviews/history, Operations filtering and CSV/JSON exports.
It denies uploads, mutations, live semantic queries and generation in FastAPI,
including direct API calls. No worker, model preparation service or OpenAI
egress overlay is included in `compose.demo.yaml`.

This is a local implementation, **not an Oracle deployment**. Docker gateway
ports bind to `127.0.0.1` by default. Do not change that for public access until
the remaining deployment checks are completed and deployment is approved.

## First setup from Windows PowerShell

Run from the repository root with Docker Desktop running. Existing development
containers, files and database are not reused. Independent volumes are named
under the `documind-demo` project. Do not combine this file with other Compose files.

```powershell
.\backend\.venv\Scripts\python.exe deploy/demo/manage.py
Copy-Item deploy/demo/.env.example deploy/demo/.env.local
docker compose -f compose.demo.yaml --env-file deploy/demo/.env.local config --quiet
docker compose -f compose.demo.yaml --env-file deploy/demo/.env.local build
```

Initialization refuses to overwrite existing secrets. If already initialized,
skip it; preserve `.env.local`, secrets and volumes. On Linux, the secret parent
is private; on Windows, keep its ACL limited to your account and trusted
administrators. Docker Desktop must be able to read the secret files under your
account. No secret is printed or embedded in an image.

Create a short-lived localhost certificate **only when no certificate files
already exist**:

```powershell
$demoCertPath = (Resolve-Path deploy/demo/certs).Path
if ((Test-Path "$demoCertPath/privkey.pem") -or (Test-Path "$demoCertPath/fullchain.pem")) {
    throw "Existing certificate files were preserved. Reuse or renew them explicitly."
}
docker run --rm --network none --user 0 --mount "type=bind,source=$demoCertPath,target=/certs" documind-demo-backend:local openssl req -x509 -newkey rsa:2048 -nodes -days 2 -subj /CN=localhost -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" -keyout /certs/privkey.pem -out /certs/fullchain.pem
```

This certificate is for isolated local testing only. A browser will warn because
it is self-signed. An automated test client can explicitly trust this certificate
as its CA file; public deployment requires valid trusted TLS and renewal. Do not
disable secure cookies or change Windows trust settings to make the demo work.

Initialize the **new** database and seed it once:

```powershell
docker compose -f compose.demo.yaml --env-file deploy/demo/.env.local up -d --wait db
docker compose -f compose.demo.yaml --env-file deploy/demo/.env.local run --rm migrate
docker compose -f compose.demo.yaml --env-file deploy/demo/.env.local run --rm seed
docker compose -f compose.demo.yaml --env-file deploy/demo/.env.local up -d api frontend gateway
docker compose -f compose.demo.yaml --env-file deploy/demo/.env.local ps -a
```

Open **https://localhost:8448/login** and choose **Explore the demo**. No password
is needed. Each entry issues an independent existing-style authentication session
for a dedicated Member identity; no session or credential is shared between
visitors. The viewer belongs only to the fictional organization. Conversations
are intentionally seeded for that viewer and read-only.

Seeding refuses a populated database or nonempty storage; it never resets or
deletes existing data. If it fails partway, inspect the isolated demo and retain
it for diagnosis. Do not rerun by dropping a volume or deleting files. The seed
database name must begin with `documind_demo`; it cannot target the normal
development database. The seed CLI does not create databases or run migrations.

## Subsequent startup and shutdown

Once seeded, do not run the seed step again:

```powershell
docker compose -f compose.demo.yaml --env-file deploy/demo/.env.local up -d api frontend gateway
docker compose -f compose.demo.yaml --env-file deploy/demo/.env.local ps -a
# Stop only demo services; retains all volumes and files:
docker compose -f compose.demo.yaml --env-file deploy/demo/.env.local stop
```

Inspect sanitized startup errors if necessary:

```powershell
docker compose -f compose.demo.yaml --env-file deploy/demo/.env.local logs --tail 50 api
docker compose -f compose.demo.yaml --env-file deploy/demo/.env.local logs --tail 50 gateway
docker compose -f compose.demo.yaml --env-file deploy/demo/.env.local run --rm migrate python -m alembic current
docker compose -f compose.demo.yaml --env-file deploy/demo/.env.local run --rm migrate python -m alembic check
```

Do not paste rendered Compose configuration, secret files, cookie headers or
connection strings into public troubleshooting reports.

## Dataset and provenance

`app.demo.seed` prepares six small original PDF/DOCX/TXT files, including two
agreement versions. It uses the existing upload validation, actual extraction
and chunking, immutable revisions, deterministic analysis worker, comparison,
review action and assignment logic offline. It stores extracted terms, threshold
and keyword risk candidates, obligations, a reviewed field, an assignment with a
separate workflow due date, and a cited conversation.

All content is authored fictional material, dated as a **2026-11-21 snapshot**.
Dates are deliberate examples, not current customer activity. Counts reflect
existing record-selection rules. The TXT/PDF agreement copies are distinct
library documents; only the PDF is used for the agreement extraction run to
avoid duplicate agreement findings from those copies.

The saved conversation is generated offline with `MockProvider` from a selected
real chunk through the existing grounding/citation validator. It is labeled
mock; there are no synthetic OpenAI usage/cost records. Original files and the
checksum manifest live together under the demo document volume. Source IDs and
revision relationships are retained, and startup checks original checksums.

The default dataset does **not** generate or falsely claim precomputed vectors.
No public workflow needs them. Optional offline indexing is supported by
`python -m app.demo.seed --index` in a **new isolated preparation database** with
the model already cached. This runs real local embeddings through the existing
worker functions and requires writable model cache access. It is not a public
worker or an additional API. Do not run model preparation or indexing in the
read-only public container. No embedding dependency pin was changed.

Genuine historical GPT answers may be imported later only with their actual
sanitized stored response, usage and matching evidence. The manual portfolio
test note is not sufficient to reconstruct a genuine GPT message record.

## Backend controls and configuration

The central route/method allowlist defaults to denial for unknown endpoints in
demo mode. Normal authentication, CSRF, refresh rotation/replay protection,
organization membership and source validation remain active on allowed routes.
The API runtime database role can SELECT business tables and modify only
`auth_sessions` and `refresh_tokens`. Migrator credentials are absent from the
running API. The original-file mount is read-only. API/DB ports are not published.

Backend demo startup requires:

- `DEMO_MODE=true`, explicit `DEMO_ORGANIZATION_ID` and `DEMO_VIEWER_ID` matching
  the dataset (the Compose file supplies the stable fixture IDs).
- A separate `documind_demo*` database containing exactly one fictional organization,
  one Member membership for the viewer, completed marked documents and no
  unfinished document/analysis jobs. Stored originals must match their checksums.
- `LLM_PROVIDER=disabled`, `LLM_REAL_REQUESTS_ENABLED=false`, no `LLM_API_KEY`,
  `EMBEDDINGS_ENABLED=false` and `OCR_ENABLED=false`.
- Existing production signing secret, secure cookies, exact HTTPS origins and
  explicit trusted hosts. Production mock-provider rejection remains unchanged.

`DEMO_SESSION_MINUTES` defaults to 60 (10–120 supported), and
`DEMO_MAX_SESSIONS` defaults to 200 (1–1000). Entry serializes capacity reservation
and expires/revoked-session cleanup with a PostgreSQL advisory transaction lock.
Only bounded numbers of session rows can exist for the visitor; each session has
at most 24 refresh tokens and a 20-second refresh cooldown. Consumed tokens remain
available for replay detection during the session lifetime. The gateway also
rate-limits demo entry. Reaching capacity returns an explicit 429; do not raise
limits indiscriminately to compensate for abuse.

The frontend's server-side `DEMO_MODE` controls appearance only and is supplied
at **build and runtime** by demo Compose because login/signup pages are statically
rendered. Rebuild when changing deployment mode. It does not authorize requests.
Normal builds default to false; local `.env` files are not edited by these tools.

## Tests

Existing development environment and local PostgreSQL must be available:

```powershell
# Creates TWO new random local databases, migrates them, runs all backend tests,
# and removes only the databases created by this invocation. Never resets your DB.
.\backend\.venv\Scripts\python.exe deploy/demo/verify_local.py

Push-Location frontend
npm test
npm run lint
npm run typecheck
npm run build
Pop-Location
```

The verification helper refuses remote database hosts. The normal test schemas
and demo fixture use different new databases. Tests cover configuration refusal,
all existing business-write routes, direct access, source downloads/citations,
foreign IDs, session independence/rotation/replay/logout, secure cookies,
capacity, seed refusal, and worker/provider refusal. UI tests cover regular login,
visitor entry/errors and unavailable uploads alongside the existing regressions.

For a running Docker demo, `deploy/demo/smoke.py` verifies HTTPS, cookies,
downloads, stored evidence, write denials and database-role permissions. See its
command below; only the local self-signed certificate is explicitly trusted:

```powershell
.\backend\.venv\Scripts\python.exe deploy/demo/smoke.py
```

Generated verification screenshots/reports are ignored under
`deploy/demo/verification/`; secrets, certificates and `.env.local` are ignored too.

## Backups, ARM and remaining deployment work

Retain a database dump and matching document-volume archive together, outside Git.
For this immutable demo, take them after verified seeding and every controlled
dataset update. Existing production backup tooling targets a different topology;
do not point it at the demo without adapting its project/database names. Restore
into a **new target** only, reapply restricted runtime privileges, revoke restored
sessions, and verify source checksums before opening traffic. Never restore over
development data. No automatic reset or destructive restore command is provided.

The current full pinned backend image deliberately retains processing/ML
dependencies even though none run publicly. ARM64 compatibility is **not certified
by an AMD64 Docker Desktop build**. Before Oracle deployment, verify the exact
native ARM images/wheels and native startup, then measure memory/disk usage. If a
pin lacks an ARM wheel, stop and agree a dependency/build approach; do not silently
change pins or emulate x86 in production.

Also pending: actual Always Free capacity/quotas, a trusted free/existing public
hostname, renewable public TLS, firewall/SSH configuration, off-host backup and
restore rehearsal, and explicit approval to provision/deploy. No cloud resources
have been created by this implementation.
