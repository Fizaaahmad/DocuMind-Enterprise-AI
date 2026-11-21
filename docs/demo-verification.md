# Local demo implementation verification

No Oracle resources or other hosting services were created. No paid OpenAI
requests, commits or pushes were made. Normal development `.env` files and the
existing development database/documents were preserved. Dependency pins and
existing Alembic migrations were not changed; no new migration is needed.

## Results

| Check | Result |
| --- | --- |
| Full backend suite | 168 passed, 1 skipped. The skip is the optional real Tesseract test because Tesseract was unavailable to the Windows test process. A pytest cache permission warning did not affect results. |
| Final demo security suite | 14 passed, after adding secure-cookie/capacity checks and immediate replay detection. Includes actual extraction/analysis of fictional fixtures and direct FastAPI access. |
| Frontend suite | 77 passed across 19 files, including four new demo UI tests and all existing regressions. |
| Lint | Backend Ruff and frontend ESLint passed. |
| Types/builds | TypeScript, normal Next.js production build and demo Docker frontend/backend builds passed on AMD64. |
| Migrations | Existing seven migrations upgraded two new disposable databases; Alembic schema checks found no new operations. The separate Docker demo was also migrated and seeded successfully. |
| HTTPS smoke | Passed through the actual Next.js proxy and NGINX gateway, explicitly trusting the local certificate. Secure cookies, CSRF, SSR guard, downloads, stored citations, exports, denial of writes and logout checked. |
| Database role | Business reads allowed; document INSERT and analysis UPDATE denied by privileges; authentication session/token writes allowed. Zero provider-request rows and unfinished jobs. |
| Browser | 15 page/viewport combinations at 1440, 768 and 390 px plus a desktop dark-mode citation dialog; no horizontal overflow or page errors. Screenshots visually inspected; clipped demo banner corrected and rechecked. |
| Isolation | Dedicated `documind-demo` Docker project/volumes. Only gateway ports published, bound to 127.0.0.1:8088 and 127.0.0.1:8448. No worker service in demo Compose. |
| Secret exclusion | Generated demo secrets, certificates, environment configuration and verification images/reports are ignored by Git. No secret values printed. |

The full backend run preceded the final additional secure-cookie test; the
final 14-test demo-only rerun covered the finished demo implementation. Do not
describe these as a single 169-test full-suite run.

## Created files

- `backend/app/core/demo.py`: explicit route policy, dataset checks and session limits.
- `backend/app/api/routes/demo.py`: capabilities and CSRF-protected visitor entry.
- `backend/app/demo/{__init__.py,seed.py,grants.py}`: offline fictional preparation
  and one-shot database privilege setup.
- `backend/tests/test_demo.py`: configuration, isolation, read-only and session regressions.
- `frontend/src/components/demo-mode.tsx` and `demo-mode.test.tsx`: mode context,
  notice, visitor entry and tests.
- `compose.demo.yaml`: separate local HTTPS demo with private API/database,
  read-only document mount and no worker/model/provider services.
- `deploy/demo/.env.example`, `init-db.sql`, `manage.py`, `nginx.conf.template`:
  local configuration, independent database roles/secrets and gateway.
- `deploy/demo/verify_local.py`, `smoke.py`, `visual-check.mjs`: disposable database
  regressions, real HTTPS smoke and optional operator browser verification.
- `docs/demo-local.md`, `docs/demo-verification.md`: exact runbook and evidence summary.

## Modified files

- `.gitignore`, `README.md`, backend/frontend `.env.example`: safe defaults,
  generated-file exclusions and documentation navigation.
- `backend/app/core/config.py`, `main.py`, `api/dependencies.py`: validated
  opt-in mode, startup checks, request policy and restricted viewer identity.
- `backend/app/api/routes/auth.py`, `health.py`: bounded demo refresh and
  read-only storage readiness, retaining normal behavior outside demo mode.
- `backend/app/documents/worker.py`, `structured/worker.py`,
  `intelligence/providers.py`: explicit refusal in demo mode.
- `frontend/Dockerfile`, `src/app/layout.tsx`, `src/lib/proxy.ts`: safe demo
  build flag, context and proxy routes.
- `frontend/src/components/workspace-shell.tsx`, `auth-form.tsx`, `assistant.tsx`,
  `dashboard.tsx`, `structured-workspace.tsx`, `operations-workspace.tsx`,
  `documents/upload-zone.tsx`, `documents/document-details.tsx`: demo notices,
  stored-history access and unavailable actions.
- `docs/free-deployment-plan.md`: link to the approved implementation follow-up.

Pre-existing portfolio edits and untracked screenshots/scripts were left alone.
Generated Next.js type-reference changes from building were restored to their
original content; they are not part of this implementation.

## Remaining limits

Default fixture preparation does not load the embedding model: live retrieval is
disabled. Optional offline `--index` preparation is available but was not exercised
in this verification. Saved mock passages are intentionally extractive and may
end at the mock provider's existing passage limit. They are not genuine GPT prose.

The full image still contains the unchanged pinned processing/ML dependencies;
they are not invoked by public requests. Native ARM64 image/wheel compatibility
and performance are **not verified** by the AMD64 build. No pins were changed to
work around that. Native ARM validation, actual free capacity/quotas, public
DNS/TLS renewal, server hardening and an off-host restore rehearsal remain before
any separately approved Oracle deployment. The generated localhost certificate
expires after two days and is not suitable for public deployment.
