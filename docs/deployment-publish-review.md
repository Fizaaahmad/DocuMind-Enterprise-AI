# Deployment publishing review

Reviewed 21 November 2026. No staging, commit, push or deployment performed.

## Recommendation

Publish the explicit files below as one cohesive read-only-demo deployment commit.
Do not use `git add .`. Existing Phase 8, Phase 9 and finalized portfolio commits
are already present; this commit adds the separately approved demo implementation.

The working tree is intentionally dirty. Portfolio screenshot/capture work and
the generated Next.js declaration change are excluded and preserved.

## Security and environment review

- Git-visible tracked/untracked files were scanned against configured local secret
  values and private-key/provider-token patterns: no matches found. This is a
  point-in-time content check, not a guarantee about all historical Git objects.
- Real `.env` files, Supabase role passwords/URLs, signing secret, private operator
  files and local verification outputs remain ignored. Only safe examples belong
  in this selection. No database dump, session export or operational archive is included.
- The six original files and records/manifest are authored fictional fixtures,
  not development database exports. Saved mock results retain their labels.
- `backend/render-demo-ca.crt` is a public CA certificate, not a private key.
- Root `render.yaml`: one Free web service, manual deploys, no worker/disk/database
  service or migration hook. Provider, OCR and embeddings disabled; pinned dataset.
- Runtime project identity, restricted DB role, TLS and immutable dataset checks
  remain enforced. Supply only the runtime URL in Render, never admin/migrator.
- The Vercel project root must be `frontend`; `frontend/vercel.json` is active.
  Configure `DEMO_MODE=true` and server-only `BACKEND_URL` for Production only.
- Normal development defaults stay unchanged: demo mode false, existing Docker
  workflow retained, no dependency pin or migration revision changes.

## Verification during this review

- Secret scan: 282 Git-visible files before preparation, zero matches.
- Focused backend demo tests: 16 passed, 9 skipped (database-dependent tests not
  enabled in this invocation). Run from `backend`: `.\.venv\Scripts\python.exe -m
  pytest tests/test_demo.py tests/test_managed_demo.py -q`. An initial invocation
  from the repository root failed test imports; rerunning from backend passed.
- Root Blueprint constraints, Vercel JSON, public CA PEM and pinned records SHA
  validated locally. `git diff --check` passed (Windows line-ending notices only).
- Prior full regression/build/resource evidence is in `render-verification.md`;
  those full checks were not repeated during this publishing review.

## Remaining deployment gates

Code is ready for explicit-path staging/review after publishing approval. Cloud
runtime readiness still requires exact Render/Vercel hostnames, allowed origins,
Production environment variables and runtime URL with
`sslrootcert=/app/render-demo-ca.crt`. Never copy the local Windows CA path to Render.
The Supabase roles, migration head and fictional import have already been verified;
**do not rerun bootstrap/import** on that populated target. No further DB writes
were performed during this review.

Confirm Render Free and Vercel Hobby selections and applicable quotas at creation.
After publishing, verify deployed cookies, CSRF, refresh/logout, backend denials,
citations, downloads, real cold starts and resource usage before sharing the URL.
No cloud success or guaranteed $0 uptime is claimed by local tests.

## Exact proposed commit scope (79 files)

```text
.gitattributes
.gitignore
README.md
backend/.env.example
backend/Dockerfile.render-demo.example
backend/alembic/env.py
backend/app/api/dependencies.py
backend/app/api/routes/auth.py
backend/app/api/routes/demo.py
backend/app/api/routes/health.py
backend/app/core/config.py
backend/app/core/demo.py
backend/app/db/session.py
backend/app/demo/__init__.py
backend/app/demo/bundle.py
backend/app/demo/grants.py
backend/app/demo/package.py
backend/app/demo/seed.py
backend/app/demo/supabase.py
backend/app/demo/target.py
backend/app/documents/worker.py
backend/app/intelligence/providers.py
backend/app/main.py
backend/app/structured/worker.py
backend/render-demo-assets/d09a0000-0000-4000-8000-000000000001/1b23c7d7-a93d-44d5-bda1-e4d5b110fd96/original
backend/render-demo-assets/d09a0000-0000-4000-8000-000000000001/54261c2a-df7b-4c38-b870-c36c015a31b9/original
backend/render-demo-assets/d09a0000-0000-4000-8000-000000000001/a88c13cf-2294-49a1-9321-9312ba12c9aa/original
backend/render-demo-assets/d09a0000-0000-4000-8000-000000000001/aabea096-e270-41dd-a022-9ba92a5a4c4b/original
backend/render-demo-assets/d09a0000-0000-4000-8000-000000000001/c59e9cb4-dbf5-4087-b696-64ab7f128696/original
backend/render-demo-assets/d09a0000-0000-4000-8000-000000000001/ed614178-17db-4407-8244-3ce86add2a74/original
backend/render-demo-assets/demo-manifest.json
backend/render-demo-assets/records.json
backend/render-demo-ca.crt
backend/tests/test_demo.py
backend/tests/test_managed_demo.py
compose.demo.yaml
deploy/demo/.env.example
deploy/demo/init-db.sql
deploy/demo/manage.py
deploy/demo/nginx.conf.template
deploy/demo/smoke.py
deploy/demo/verify_local.py
deploy/demo/visual-check.mjs
deploy/render/frontend.env.example
deploy/render/render.yaml.example
deploy/render/vercel.json.example
deploy/render/verify_local.py
docs/demo-local.md
docs/demo-verification.md
docs/deployment-publish-review.md
docs/free-deployment-plan.md
docs/render-deployment.md
docs/render-free-demo.md
docs/render-verification.md
frontend/.env.example
frontend/Dockerfile
frontend/src/app/assistant/page.tsx
frontend/src/app/demo-wake/page.tsx
frontend/src/app/documents/page.tsx
frontend/src/app/intelligence/page.tsx
frontend/src/app/layout.tsx
frontend/src/app/operations/page.tsx
frontend/src/components/assistant.tsx
frontend/src/components/auth-form.tsx
frontend/src/components/dashboard.tsx
frontend/src/components/demo-mode.test.tsx
frontend/src/components/demo-mode.tsx
frontend/src/components/documents/document-details.tsx
frontend/src/components/documents/upload-zone.tsx
frontend/src/components/operations-workspace.tsx
frontend/src/components/structured-workspace.tsx
frontend/src/components/workspace-shell.tsx
frontend/src/lib/demo-wake.test.ts
frontend/src/lib/demo-wake.ts
frontend/src/lib/proxy.ts
frontend/src/lib/server-auth.test.ts
frontend/src/lib/server-auth.ts
frontend/vercel.json
render.yaml
```

## Intentionally excluded working changes

```text
frontend/next-env.d.ts
portfolio/linkedin-application-eight/01-assistant-dark.png
portfolio/linkedin-application-eight/02-dashboard-light.png
portfolio/linkedin-application-eight/03-login-dark.png
portfolio/linkedin-application-eight/04-documents-light.png
portfolio/linkedin-application-eight/05-extraction-dark.png
portfolio/linkedin-application-eight/06-comparison-light.png
portfolio/linkedin-application-eight/07-risks-dark.png
portfolio/linkedin-application-eight/08-operations-light.png
portfolio/linkedin-application-eight/README.md
portfolio/linkedin-application-eight/capture-checks.json
portfolio/linkedin-application-eight/provenance.json
portfolio/source/demo_capture.py
portfolio/source/linkedin_capture.mjs
```

Ignored credentials, local environment files, verification previews, certificates
with private keys, dumps and archives must remain excluded even if later generated.
