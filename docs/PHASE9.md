# Phase 9: enterprise UI/UX

DocuMind now uses a shared, light-first enterprise interface across authentication,
the overview, document library, Knowledge Assistant, Document Intelligence, and
Enterprise Operations. Indigo/violet accents, compact navigation, consistent forms,
status badges, responsive tables, confirmation dialogs, and accessible focus states
replace the earlier standalone page layouts. No backend API, database migration,
runtime dependency, or provider configuration is required by this phase.

## What changed

- A shared workspace shell provides organization-aware navigation, mobile navigation,
  account details, and sign-out. The preferred organization ID is remembered in
  session storage and checked against authorized memberships. Authentication tokens
  remain in the existing HttpOnly cookies.
- The overview uses existing APIs for document counts, pending reviews, obligations,
  recent documents, processing states, and activity. Unavailable metrics show a dash.
  Workflow totals count current analysis records across engines/templates; they are
  not deduplicated business items. Links carry the corresponding filters.
- The Assistant has a conversation sidebar, searchable document scope, compact usage
  details, readable conversation bubbles, inline source buttons, and evidence dialogs.
  Existing mock/GPT provenance labels and insufficient-evidence behavior remain.
- Intelligence presents extracted values as labeled business information, with raw
  provenance available in expandable details. A form-based template editor retains
  the advanced JSON editor. Risks, obligations, comparisons, evidence, review actions,
  optimistic concurrency, and original values retain their existing workflows.
- Operations uses the same components, compact filters, readable record details,
  assignment controls, and existing export/review endpoints.
- Empty, error, processing, and confirmation states are consistent. Dialogs use native
  browser focus containment and restore focus when closed. Motion respects the
  reduced-motion preference. Loading indicators stay within workspaces so protected
  server-side redirects retain their existing behavior.

## Windows local development

Existing configuration and commands are unchanged. Use separate PowerShell terminals:

```powershell
# PostgreSQL
Set-Location 'C:\Users\fizaa\Projects\Side Projects\DocuMind'
docker compose up -d db
```

```powershell
# API
Set-Location 'C:\Users\fizaa\Projects\Side Projects\DocuMind\backend'
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload
```

```powershell
# Existing processing/indexing/analysis worker
Set-Location 'C:\Users\fizaa\Projects\Side Projects\DocuMind\backend'
.\.venv\Scripts\python.exe -m app.documents.worker
```

```powershell
# Frontend
Set-Location 'C:\Users\fizaa\Projects\Side Projects\DocuMind\frontend'
npm run dev
```

Open <http://localhost:3000>. No Phase 9 migration is necessary. Keep existing
Phase 8 provider settings; viewing stored answers does not create a paid request.
Submitting a new GPT answer/analysis can incur costs if OpenAI is enabled.

## Verification

From the repository root:

```powershell
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
```

The isolated browser checks use synthetic fixtures, never your backend or OpenAI.
Fixtures are only imported by the verification server and excluded from the Docker
image. They do not populate production views or your database.

```powershell
# Optional browser-check tooling, kept outside application dependencies
npm install --prefix .production-smoke/ui-tools --no-save --package-lock=false playwright @axe-core/playwright
node frontend/scripts/visual-check.mjs
```

The browser check requires a completed frontend build, Microsoft Edge on Windows,
and free local ports 3002/8002. It starts and closes its own preview and fixture
server. Screenshots and the accessibility report are written to
`.production-smoke/phase9-visual`. Desktop (1440px), tablet (1024px), and mobile
(390px) checks cover the eight main screens, source-dialog keyboard behavior,
empty/error states, and account controls. Other installed Chromium channels can
be selected with `DOCUMIND_BROWSER_CHANNEL`.

For the existing isolated full-stack HTTP check, with local PostgreSQL running:

```powershell
Set-Location backend
$env:LLM_REAL_REQUESTS_ENABLED = 'false'
$env:LLM_PROVIDER = 'mock'
$env:EMBEDDINGS_ENABLED = 'false' # Deterministic UI smoke; skip model warm-up
.\.venv\Scripts\python.exe scripts\smoke_fullstack.py
```

It requires free ports 3001/8001 and a database role with CREATEDB. It creates and
removes its own temporary database and processes; existing application data is
preserved. Full backend regression and migration checks use the existing
`scripts/test_postgres.py` runner documented in the main README.

For manual acceptance, sign in and switch between authorized organizations. Check
overview links, upload and open a document, inspect processing states, open an
existing Assistant conversation and its citations, review extraction/comparison
results, update an assignment, and export Operations records. Repeat with a narrow
browser window and keyboard-only navigation. Check the empty state in an organization
without documents and confirm deletion cancellation leaves data untouched.

## Verification results

Implementation verification: 73 frontend tests passed; lint, TypeScript, and the
production build passed. The backend regression runner passed 155 tests with one
optional integration test skipped, including migration consistency checks. Browser
verification passed 30 main/empty/error screen checks across the three sizes with
zero automated WCAG A/AA findings and no runtime errors. Source-dialog focus
containment, Escape/focus restoration, mobile navigation, and account controls were
also exercised. Synthetic screenshots are verification artifacts, not customer data.
The isolated HTTP smoke test also passed authentication/session rotation, CSRF,
organization isolation, document processing/download/deletion, structured reviews,
comparison, exports, and Operations assignments/audit identity. That UI smoke run
explicitly disabled embedding model loading; embedding behavior remains covered by
the backend regression suite and existing Phase 4/8 verification procedures.

## Theme settings

Use the bottom-right **Color theme** selector on any page to choose **Light mode**,
**Dark mode**, or **System theme**. System is the default and follows device changes.
The preference is stored locally under `documind.theme`, synchronized between tabs,
and applied before page paint. No authentication tokens are stored with it. If
browser storage is blocked, selection still works for the current page.

To repeat the isolated browser checks in dark mode:

```powershell
$env:VISUAL_THEME = 'dark'
node frontend/scripts/visual-check.mjs
Remove-Item Env:VISUAL_THEME
```

Dark screenshots and reports are stored in `.production-smoke/phase9-dark`.
Both palettes passed 30 screen checks each at desktop/tablet/mobile widths, with
zero automated WCAG A/AA findings or browser runtime errors. Real browser checks
also verified changing themes and preserving the choice across page reloads.
The three theme-specific unit tests cover persisted selection, live system changes,
cross-tab synchronization, and blocked storage.

## Limits

Automated browser checks use Edge/Chromium and synthetic records. They supplement
the real backend regressions and HTTP smoke test, but do not certify accessibility
or replace Safari/Firefox, screen-reader, and real-user acceptance testing. There
are no paid AI calls in the verification workflow.
