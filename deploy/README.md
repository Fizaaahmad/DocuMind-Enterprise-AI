# Production operations (Phase 7)

This is a single-server Docker Compose deployment. Only NGINX publishes ports;
Next.js, FastAPI, the serial PostgreSQL-backed worker, and pgvector PostgreSQL
communicate privately. There is no paid service or LLM integration. Development
uses the existing root `compose.yaml` and unchanged Windows commands in the
main README. Never merge the production file with the development Compose file.

## First startup from Windows PowerShell

Run from the repository root with Docker Desktop running:

```powershell
.\backend\.venv\Scripts\python.exe deploy/manage.py init
notepad deploy/.env.production
docker compose -f compose.production.yaml --env-file deploy/.env.production build
```

`init` generates independent admin, migration, runtime-database and signing
secrets under `deploy/secrets/`, and refuses to overwrite existing secrets.
The files are ignored by Git and excluded from image build contexts. On Windows,
restrict access to `deploy/secrets`, `deploy/certs` and `backups` to your account
and trusted administrators using NTFS permissions. On Linux, the private secret
directory is mode 0700; file secrets are read-only inside containers. File-backed
Compose secrets protect against accidental environment inspection, but anyone
with host or Docker administrator access can read them.

For an actual server, set `APP_DOMAIN` to its DNS name, `PUBLIC_ORIGIN` to the
exact HTTPS origin (no trailing slash), `HTTP_PORT=80`, and `HTTPS_PORT=443`.
Install a valid certificate and matching private key at
`deploy/certs/fullchain.pem` and `deploy/certs/privkey.pem`. Certificate issuance
and renewal are operator responsibilities. Missing certificates prevent gateway
startup; missing secrets or insecure production auth configuration prevent API
startup. No credentials are baked into images or sent to the browser.

For **local verification only**, keep the example localhost ports and create a
short-lived self-signed certificate without modifying your Windows trust store:

```powershell
docker run --rm --network none --user 0 --mount "type=bind,source=$((Get-Location).Path)\deploy\certs,target=/certs" documind-backend:local openssl req -x509 -newkey rsa:2048 -nodes -days 2 -subj /CN=localhost -addext subjectAltName=DNS:localhost -keyout /certs/privkey.pem -out /certs/fullchain.pem
docker compose -f compose.production.yaml --env-file deploy/.env.production config --quiet
docker compose -f compose.production.yaml --env-file deploy/.env.production up -d db
docker compose -f compose.production.yaml --env-file deploy/.env.production run --rm migrate
docker compose -f compose.production.yaml --env-file deploy/.env.production up -d
docker compose -f compose.production.yaml --env-file deploy/.env.production ps -a
```

Open `https://localhost:8443` for this local setup; a browser warns about the
self-signed certificate. Prefer the automated trusted-certificate smoke test
below. Production must use a valid certificate. Do not disable cookie security or
CSRF checks to work around certificate problems. The production volumes are
separate from your existing development database and documents.

## Configuration and resource limits

Production always uses secure HttpOnly, host-only cookies, explicit HTTPS CSRF
origins, trusted backend hosts and same-origin frontend API proxying. Existing
refresh rotation, membership checks and source authorization remain in place.
Runtime database access has table DML privileges; only the one-shot migrator can
change the schema. The database administrator is reserved for bootstrap/recovery.

`deploy/.env.production` configures upload bytes (default 20 MiB), gateway body
limit (default 21 MiB including multipart overhead), API concurrency (64), CPU,
memory, rate limits and worker stop grace. Keep the gateway limit slightly larger
than the upload limit. Rate limiting is per client IP at the gateway, with bursts
for normal use; tune for shared corporate NATs. It does not replace account-level
failed-login protection. Do not place an unconfigured additional proxy in front
of this gateway: client-IP trust and rate limiting would need explicit review.

Backend settings also support `JSON_MAX_BYTES` (64 KiB),
`ORGANIZATION_MAX_DOCUMENTS` (10,000), and `ORGANIZATION_MAX_STORAGE_BYTES` (10 GiB).
Add overrides to the shared application environment in production Compose as
needed. Pending uploads reserve their size against organization quotas. Existing
extraction, OCR, indexing and analysis limits remain active. Worker concurrency
is one job per process. The default 11-minute stop grace permits normal jobs to
finish after SIGTERM; if increasing indexing/analysis timeouts, increase this
grace too. A forced kill relies on lease recovery and publication fencing.

OCR and embeddings are off initially, independently of local development `.env`.
English Tesseract is installed in the backend image; enable `OCR_ENABLED=true`
and recreate API/worker to use it. Other languages require installing their
Tesseract language packages in the image. For embeddings, prepare the pinned model
using the explicit tool service with internet access:

```powershell
docker compose -f compose.production.yaml --env-file deploy/.env.production --profile tools run --rm --no-deps prepare-model
# Set EMBEDDINGS_ENABLED=true in deploy/.env.production, then:
docker compose -f compose.production.yaml --env-file deploy/.env.production up -d api worker
```

API/worker have no public ports and use an internal network; the model cache is
persistent. `LLM_PROVIDER=disabled` is intentional in production; the existing
development-only mock remains available in the local development workflow.

## Upgrades and migrations

Review migration SQL and take a consistent backup before upgrades. Keep the old
application image tag/digest available. Do not run old writers against a changing
schema:

```powershell
.\backend\.venv\Scripts\python.exe deploy/manage.py backup
docker compose -f compose.production.yaml --env-file deploy/.env.production stop api worker
docker compose -f compose.production.yaml --env-file deploy/.env.production build
docker compose -f compose.production.yaml --env-file deploy/.env.production run --rm migrate
docker compose -f compose.production.yaml --env-file deploy/.env.production run --rm migrate python -m alembic check
docker compose -f compose.production.yaml --env-file deploy/.env.production up -d
```

The migrator takes a PostgreSQL advisory lock to reject concurrent migration
processes, uses a bounded statement timeout, and never resets the database.
Readiness checks the expected migration head, pgvector, DB availability and storage
permissions. Phase 7 adds no schema migration. Avoid blind `alembic downgrade`:
older phases have downgrade operations that remove tables and their contents.
Prefer a forward fix; restoring a backup loses writes after that backup. Existing
database passwords are not changed merely by editing secret files: coordinate
role password rotation in PostgreSQL and the corresponding files while writers
are stopped. Do not delete volumes to resolve credential errors.

## Consistent backups and fresh-target restoration

```powershell
.\backend\.venv\Scripts\python.exe deploy/manage.py backup --directory backups/pre-upgrade
```

The helper drains/stops API and worker, takes a custom-format `pg_dump`, archives
the document volume, writes a SHA-256 manifest, then restarts only writers that
were running. Expect a brief maintenance window. A failed backup without a
complete manifest is unusable. Backups contain sensitive documents, password
hashes and session metadata: restrict their ACLs, encrypt and copy them off-host
using your organization's tooling. Back up configuration, TLS keys and secrets
separately with equivalent protection. The model cache is reproducible and is not
included. Do not use PowerShell 5 output redirection for binary database dumps.

Restore into a **new Compose project with empty database and document volumes**.
Keep the same database role names; bootstrap creates them before restoration.
Do not run migrations before restoring the old schema. Example maintenance drill:

```powershell
# Stop the old gateway first to release ports; retain the original volumes.
docker compose -f compose.production.yaml --env-file deploy/.env.production stop
docker compose -p documind-recovery -f compose.production.yaml --env-file deploy/.env.production up -d --wait db
.\backend\.venv\Scripts\python.exe deploy/manage.py --project documind-recovery restore --directory backups/pre-upgrade --confirm-new-target
docker compose -p documind-recovery -f compose.production.yaml --env-file deploy/.env.production run --rm migrate
docker compose -p documind-recovery -f compose.production.yaml --env-file deploy/.env.production up -d
```

Restore validates checksums, refuses nonempty targets/running writers, rejects
unsafe archive paths and links, restores ownership, and revokes all restored
sessions. Users log in again. Review readiness, log in, download a restored
document, and confirm queued work recovers before routing traffic. A failed
restore may leave a partial target: keep it offline and use another empty target;
the helper does not erase data or retry destructively. Never use `down --volumes`
on valuable deployments. Recovery is not automatic failover or point-in-time
recovery.

## Diagnostics and verification

```powershell
docker compose -f compose.production.yaml --env-file deploy/.env.production logs --tail 100 api worker gateway
docker compose -f compose.production.yaml --env-file deploy/.env.production exec api python -m app.core.diagnostics dependencies
docker compose -f compose.production.yaml --env-file deploy/.env.production exec worker python -m app.core.diagnostics worker-health
# Complete local HTTPS + independent-volume backup/restore drill:
.\backend\.venv\Scripts\python.exe backend/scripts/smoke_production.py
# Existing backend suite, migrations and model/schema drift checks:
Set-Location backend
.\.venv\Scripts\python.exe scripts/test_postgres.py
Set-Location ../frontend
npm test
npm run lint
npm run typecheck
npm run build
```

The smoke test generates private disposable projects, loopback-only ports and a
certificate trusted only by its HTTP client. It removes only its own test volumes
and leaves ignored `.production-smoke` artifacts for inspection. It never accesses
development volumes. Build the images first; allow enough Docker Desktop memory
for the source and recovery stacks.

Application logs contain fixed events, request IDs, route templates, job IDs and
timings, without exception values, query strings, credentials or document text.
NGINX logs only request IDs/status/timing. Docker rotates logs. PostgreSQL keeps
fatal server diagnostics but suppresses routine SQL errors, statements, bind
parameters and detailed failing rows, which can include document text. Use the
application's sanitized failure events and health checks to diagnose SQL errors;
do not enable verbose SQL logging on sensitive production data.
Readiness failure does not restart a container automatically: inspect `ps -a`, logs, disk/memory,
schema and secret mounts. Worker heartbeat detects process/DB failure, not a
guarantee that every job is making progress; lease deadlines govern recovery.
Admins can inspect organization job counts and failed jobs at the authenticated
`GET /api/backend/organizations/{id}/operations/diagnostics` endpoint.

Remaining operator responsibilities: domain/TLS renewal, firewall/host patching,
dependency/image updates and digest pinning for releases, backup scheduling and
restore drills, disk monitoring, and business-appropriate quota/rate tuning.
This phase does not add HA, malware scanning, external monitoring, or a full
nonce-based script CSP. The supplied CSP prevents framing and object embedding
without breaking the existing Next.js UI.

## Verification results

Phase 7 verification on Windows/Docker Desktop:

- Backend: 134 passed, one opt-in real-embedding integration test skipped.
  The real Tesseract scanned/mixed-PDF test passed.
- Frontend: 57 passed; ESLint, TypeScript and the production build passed.
- Fresh-database Alembic upgrades and schema-drift checks passed; no new migration.
- Both Linux images built; runtime dependency checks and parser/embedding imports passed.
- Frontend production dependency audit reported zero known vulnerabilities.
- The isolated HTTPS smoke and complete fresh-volume recovery drill passed,
  including secure cookies/CSRF, cross-organization access denial, processing,
  downloads, protected pages, worker restart, runtime DDL denial, rate limiting,
  and log checks against test credentials/document text/SQL-error values.

The optional existing embedding test can be enabled after preparing the local
model, independently of the Docker deployment:

```powershell
Set-Location backend
$env:EMBEDDING_INTEGRATION = '1'
.\.venv\Scripts\python.exe scripts/test_postgres.py -q tests/test_intelligence.py
Remove-Item Env:EMBEDDING_INTEGRATION
```

These checks verify the application and local deployment; they are not a
penetration test, uptime guarantee, or production load certification.
