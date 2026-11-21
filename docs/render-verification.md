# Managed free-demo implementation evidence

> Historical local implementation results below predate the approved Supabase
> preparation. Supabase TLS/identity, roles, seven migrations and fictional import
> have since passed verification. Render/Vercel deployment remains pending.
> See [current operator runbook](render-deployment.md) and
> [publishing review](deployment-publish-review.md). Do not rerun bootstrap/import.

No live Supabase connection or modification, hosting-resource creation, deployment,
OpenAI request, commit or push was performed. Existing local data and environment
files were preserved. Existing development/demo Compose files and dependency pins
were not replaced. Pre-existing portfolio changes remain untouched.

## Checks

| Check | Result |
| --- | --- |
| Full backend regressions | 177 passed, 1 skipped: optional local embedding integration not enabled |
| Final focused managed-demo tests | 10 passed, including actual database/role identity rejection, exact project/role/TLS pins, immutable import roundtrip, overwrite refusal, role grants and concurrent/global entry limits |
| Frontend regressions | 84 passed across 20 files, including bounded wake reads, no entry mutation after wake failure, healthy-401 login protection and open-redirect rejection |
| Frontend lint/types | ESLint and TypeScript passed |
| Production builds | Normal and demo-enabled Next.js builds passed; demo wake page is dynamic in demo mode |
| Backend checks | Ruff passed; two new disposable local databases migrated to the existing head and Alembic checks found no new schema operations |
| Offline fixture verification | Passed; no passwords/hashes, sessions, refresh tokens or provider ledgers exported |
| Deployment examples | JSON/YAML syntax and Free-only/no-worker/no-disk settings checked; dataset hash matches packaged files |
| Resource-capped candidate | Passed at 512 MiB / 0.1 CPU; peak 140.1 MiB, no OOM. Fresh local import, exact record comparison, six original downloads, saved results/exports and denied upload verified; only its owned container/database removed afterward. |

The full backend run preceded the last focused privilege/identity assertions;
the final 10-test run covers those additions. Do not describe these as a single
180-test full-suite run. Tests use illustrative Supabase URLs for pure validation
only and real localhost databases for import/SQL connection behavior.

The immutable package has six original files totaling **38,050 bytes**, with
`records.json` and its manifest bringing the package to **92,595 bytes**. Its
non-secret record hash is
`3606715a11369a933e786bd2a07f13e0d2dabab59916fc9afbd14fc2063b1462`.
Git attributes preserve exact bytes across Windows/Linux, including TXT originals.

## Files created or updated for this implementation

- `backend/app/demo/target.py`: exact managed-project/session/TLS/role validation.
- `backend/app/demo/bundle.py`: allowlisted credential-free records, file checks,
  atomic empty-target import, immutable comparison and runtime-role privilege checks.
- `backend/app/demo/package.py`: disposable-local-database fixture generation only.
- `backend/app/demo/supabase.py`: offline verification by default; explicit
  project-confirmed bootstrap/import, hidden credential prompts, SCRAM role-password
  derivation through libpq, application-only grants and no overwrite/reset path.
- `backend/render-demo-assets/`: canonical six originals and two JSON fixture files.
- `backend/app/core/config.py`, `core/demo.py`, `main.py`, `db/session.py`,
  `api/routes/demo.py`, `backend/alembic/env.py`: opt-in managed pins, bounded DB
  pooling/session setup and global demo-entry admission control.
- `backend/tests/test_demo.py`, `test_managed_demo.py`,
  `deploy/demo/verify_local.py`: direct entry throttling and focused/local-only
  verification support alongside existing regressions.
- `frontend/src/lib/demo-wake.ts`, `demo-wake.test.ts`, `server-auth.ts`,
  `server-auth.test.ts`, `proxy.ts`: short readiness probes, protected-page wake
  routing, safe return paths, unchanged 401 handling and Retry-After forwarding.
- `frontend/src/components/demo-mode.tsx`, `demo-mode.test.tsx`,
  `frontend/src/app/demo-wake/page.tsx`, and the Assistant/Documents/Intelligence/
  Operations page guards: read-only wake UX and module-preserving return paths.
- `backend/Dockerfile.render-demo.example`, `deploy/render/render.yaml.example`,
  `deploy/render/verify_local.py`: image-baked originals, explicit Free deployment
  settings and a locally constrained candidate verifier.
- `.gitattributes`, `backend/.env.example`, `README.md`,
  `docs/render-free-demo.md`, `render-deployment.md`, `render-verification.md`:
  checksum safety, configuration examples and current operator guidance.

Generated `frontend/next-env.d.ts` can be refreshed by Next.js checks; it is not a
business-logic change. No existing application behavior is intentionally changed
when demo mode and managed pins are disabled.

## Remaining live checks

The selected Supabase project has deliberately not been inspected. An existing
populated public schema or existing demo roles will stop bootstrap; they will
not be reset. The operator must confirm a dedicated approved target first.
Provider permissions, custom-role/session-pooler behavior, the actual CA/TLS
chain, Render/Vercel cold starts, cookies/origins and account billing controls
remain live verification gates requiring explicit approval. No claim of tested
cloud compatibility or guaranteed free uptime is made.

The full runtime lock remains large even though no model is loaded. First image
builds may consume meaningful free build quota. No slim-lock change, paid storage,
worker, model download or paid API integration was introduced. Local Docker
resource measurements cannot establish a production SLA or test native ARM.

The memory verifier used loopback-only HTTP/development cookies on its owned
container; managed production cookie settings are tested separately. No claim of
Render TLS, Supabase pooler connectivity, or end-to-end cloud deployment follows
from this local result. The final operator bootstrap identity checks are covered
by the focused tests; no bootstrap/import command was applied to a cloud database.
