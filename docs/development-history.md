# Development history and detailed feature reference

This preserves the former repository README and its detailed phase-by-phase setup,
manual acceptance workflows, API descriptions, data-lifecycle decisions and tests.
For a **fresh installation**, use [the current setup guide](setup.md). For production,
use [deployment and recovery](../deploy/README.md).

Some sections describe earlier milestones, not the current feature set. The initial
foundation's `NEXT_PUBLIC_API_URL`/browser-origin and “AI deferred” text is historical.
The current frontend uses server-only `BACKEND_URL` and the same-origin proxy.
Phase-specific migrations are upgrade history; fresh databases use `alembic upgrade
head` after reviewing migrations. Replace old absolute Windows paths with your clone
location. Never overwrite existing environments or remove database volumes merely
to follow historical setup examples.

Reference sections:

- [Organization workflows and counting semantics](#phase-6-enterprise-operations-and-portfolio-intelligence)
- [Structured extraction, rules and review](#phase-5-structured-document-intelligence)
- [Semantic search and indexing](#phase-4-local-semantic-search-and-provider-neutral-assistant)
- [Windows OCR installation and safeguards](#optional-pdf-ocr-windows-installation-and-configuration)
- [Document processing and storage](#phase-3-windows-setup-and-startup)
- [Authentication and permissions](#phase-2-windows-quick-start)

---

# DocuMind

## Phase 9: enterprise UI/UX

The shared enterprise workspace now covers authentication, overview, documents,
Knowledge Assistant, Intelligence, and Operations. See [Phase 9 setup and UI
verification](PHASE9.md) for local commands, browser checks, and manual
acceptance steps. Existing APIs, authentication, provider settings, and local
development workflow are preserved; no new migration is required.

## Phase 8: optional OpenAI document intelligence

See [Phase 8 setup and controlled first test](PHASE8.md) for the additive
`0007_provider_requests` migration, explicit enable flags, secure key setup,
budgets, grounded GPT answers, structured analysis and production outbound access.
OpenAI remains disabled by default; deterministic/mock workflows remain available.
Automated verification uses mocked responses and makes no paid API requests.

## Phase 7: production readiness

Production uses the separate [production Compose file](../compose.production.yaml).
See [deployment and recovery instructions](../deploy/README.md) for exact Windows
PowerShell commands, private secret initialization, TLS, migrations, backups,
fresh-target restoration, diagnostics, and isolated HTTPS verification.
Existing local development commands below remain unchanged. Phase 7 adds no
database schema migration and no paid provider integration.

## Phase 6: enterprise operations and portfolio intelligence

Open **http://localhost:3000/operations** or choose **Enterprise overview** from
the dashboard. The workspace provides organization-wide inventory, filtered
record totals, centralized obligations, a review queue, a risk register,
assignments, workflow activity, and CSV/JSON reports. Existing organization
management and Phase 5 analysis screens remain available.

### Windows setup

No new dependency, service, API key, environment variable, or background job is
required. Stop the old API and worker with Ctrl+C before applying the additive
assignment migration, then use separate PowerShell terminals:

```powershell
# Terminal 1: PostgreSQL, migration, and API
Set-Location 'C:\Users\fizaa\Projects\Side Projects\DocuMind'
docker compose up -d db
Set-Location backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload
```

```powershell
# Terminal 2: existing document/indexing/analysis worker
Set-Location 'C:\Users\fizaa\Projects\Side Projects\DocuMind\backend'
.\.venv\Scripts\python.exe -m app.documents.worker
```

```powershell
# Terminal 3: frontend
Set-Location 'C:\Users\fizaa\Projects\Side Projects\DocuMind\frontend'
npm run dev
```

### Counting and deadline semantics

Portfolio totals count **analysis records**, not deduplicated real-world risks
or commitments. Current records come from the latest successful extraction run
for each source revision, template family, and engine. Template families follow
the immutable `parent_id` version chain. Repeated analyses and revised versions
of the same template family replace earlier runs in current totals. Independent
templates remain separate families: overlapping findings/obligations can therefore
count separately, and the UI/reports explicitly disclose this. Comparison changes
remain in Phase 5 and are not counted as extraction risk or obligation records.

Default filters select deterministic records on current source revisions of live,
completed documents. Mock records are excluded unless explicitly selected and
are labeled **DEVELOPMENT MOCK**. Superseded scope includes older successful runs
and older/reprocessing source revisions; the two reasons are flagged separately.
Assignments and approvals are not automatically copied onto replacement results.
Deleted-source records are excluded from every portfolio scope/export, while
unavailable analysis counts and redacted activity metadata remain visible.

Inventory counts are labeled **organization-wide**, include historical/mock
analysis runs, and are separate from filtered item totals. Physically deleted
documents are not retained as a document inventory count. Dashboard drilldowns,
lists, and exports share SQL selection/filtering and metric predicates. Counts
can change between requests when another user updates the organization.

Contract deadlines come from Phase 5's validated ISO obligation dates. Assignment
due dates are separate workflow metadata and never change contract text or dates.
Open obligations use the existing `open`/`in_progress` lifecycle; unreviewed or
rejected candidates keep that lifecycle until explicitly completed/dismissed.
Review work completes on approval/rejection; a corrected result still awaits
approval. Completion time derives from existing audit events. Unknown deadlines
are not overdue. Deadline classification uses a UTC date: overdue means strictly
before the reference date, upcoming means that date through seven days ahead.
Changing the reference date changes classification of **current stored state**;
it does not reconstruct a historical point-in-time portfolio.

### Manual verification

1. Complete a deterministic Phase 5 extraction with fields, risk findings, and
   an obligation. Open Operations and inspect overview counts and matching rows.
2. Repeat the same analysis. Current counts must stay stable; the earlier results
   move to superseded scope. Create a child template version and repeat: the family
   still contributes only its latest results. An independent copied template may
   add overlapping records and must not be interpreted as unique business items.
3. Use Obligations, Review queue, and Risk register tabs. Test responsible party,
   document, severity, review/lifecycle status, assignment, deadline range, and
   overdue/upcoming/unknown filters. Filename search finds document options across
   the organization (up to 50 matching choices at once). Tables are paginated.
4. Click a nonzero overview metric to drill into its records without dropping
   existing filters. Reset filters to leave the drilldown. Export CSV/JSON and
   compare row totals and filters with the displayed list, across all pages.
5. Inspect a record as its uploader or Admin. Assign it to an organization member
   with a workflow due date different from its contract deadline. Verify both
   dates remain distinct. Assigning an external/nonmember user is rejected.
6. Log in as the assignee. Filter by your name, inspect evidence, and use the
   existing approve/reject/correct or obligation status actions. You may act only
   on assigned current items (unless independently uploader/Admin). Assignment
   grants no document deletion, template administration, or reassignment rights.
7. Open the same item in two tabs and submit an older version after another write.
   The stale update returns 409 and refreshes the record rather than overwriting.
8. Complete a review/obligation. Check review queue membership, completion time,
   and activity. Review actions remain the original Phase 5 `ReviewEvent` records;
   assignment/date changes add one event each. There is no duplicate activity store.
9. Remove an assignee's membership as Admin. Assignments and workflow due dates
   clear atomically; prior review actors and activity identities remain. The former
   member loses access. An assigned task on an older result does not become a
   delegation to the replacement result after reprocessing/reanalysis.
10. Delete a source. No portfolio list/export may expose its values or evidence.
    Activity retains actor/action/time/version metadata with redacted content and
    an unavailable-source label. Check another organization to verify isolation.

### Implementation and limits

`0006_operations` adds two nullable `analysis_items` columns (membership assignee
and workflow due date), a membership foreign key, and scope indexes. Existing
results, revisions, and review values are preserved. `app/operations/queries.py`
contains the shared portfolio projection, lineage ranking, and filters;
`assignments.py` records assignment changes; existing Phase 5 actions remain the
single review/status implementation. Membership changes and assignment/review
writes use organization locking, item locking, and the existing version counter.
Only active members may be assigned; membership removal also clears completed
assignment pointers, with the original identities retained in audit history.

Organization-scoped APIs under `/api/v1/organizations/{id}/operations`:
`GET summary`, `GET items`, `GET members`, `GET activity`, `GET export`, and
`PATCH items/{item_id}/assignment`. All reuse live authentication and membership;
mutations retain CSRF protection. The existing server guard and proxy allowlist
protect `/operations`. Original-result links open the selected organization,
analysis, and item in Phase 5. Shared review controls and evidence validation are
reused. Activity is explicitly organization-wide and does not inherit item filters.

Lists use 20 records per page (API maximum 100); activity uses 30. Reports include
all matching rows up to 5000; exceeding that limit returns a clear error requiring
narrower filters, without silently truncating. CSV uses the existing formula-safe
formatter. JSON includes original/corrected values, evidence, provenance, assignment,
and scope. Expensive materialized dashboards, cross-template semantic deduplication,
automatic task carry-forward, custom workflow states, holiday calendars, notifications,
and scheduled reports are deferred. No GPT or paid provider integration is added.

```powershell
# From backend/: isolated database regressions and migration checks
.\.venv\Scripts\python.exe scripts/test_postgres.py
.\.venv\Scripts\python.exe -m ruff check .
# Optional full regression with cached real local embeddings
$env:EMBEDDING_INTEGRATION = '1'
.\.venv\Scripts\python.exe scripts/test_postgres.py
Remove-Item Env:EMBEDDING_INTEGRATION
# Build frontend first, then run HTTP smoke tests on free ports 3001/8001
$env:SMOKE_INTELLIGENCE = '1'
.\.venv\Scripts\python.exe scripts/smoke_fullstack.py
Remove-Item Env:SMOKE_INTELLIGENCE
# From frontend/
npm test
npm run lint
npm run typecheck
npm run build
```

Tests cover version/family counting, metric/list/export consistency, deadlines,
cross-organization assignment rejection, delegated actions, stale updates,
membership removal, audit identity, mock exclusion, source supersession/deletion,
and operations UI permissions/filters/evidence. Smoke tests use disposable servers,
storage, and databases and leave development data intact.

## Phase 5: structured document intelligence

Open **http://localhost:3000/intelligence** or select **Structured intelligence**
on the dashboard. This phase works without an LLM, API key, embeddings, or model
downloads. It provides literal field extraction, typed validation, text comparison,
configurable rule findings, obligation candidates, review history, and CSV/JSON
exports. It does **not** provide semantic contract interpretation or legal advice.

### Windows startup

No additional package or service is needed beyond the existing installation.
Stop the old API and worker with Ctrl+C before applying the additive migration:

```powershell
Set-Location 'C:\Users\fizaa\Projects\Side Projects\DocuMind'
docker compose up -d db
Set-Location backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload
```

Run the **same existing worker command** in another PowerShell terminal:

```powershell
Set-Location 'C:\Users\fizaa\Projects\Side Projects\DocuMind\backend'
.\.venv\Scripts\python.exe -m app.documents.worker
```

Run the frontend in a third terminal:

```powershell
Set-Location 'C:\Users\fizaa\Projects\Side Projects\DocuMind\frontend'
npm run dev
```

Deterministic extraction needs no environment changes. Optional limits in
`backend/.env` (restart API/worker after changes):

```dotenv
ANALYSIS_MAX_CHARACTERS=500000
ANALYSIS_TIMEOUT_SECONDS=120
ANALYSIS_MAX_ITEMS=500
```

The development-only structured mock requires `LLM_PROVIDER=mock` and
`ENVIRONMENT=development`. Choose **Development mock simulation** in the workspace.
It exercises the optional structured-provider capability without API calls and
is labeled in history/results/exports. Existing Phase 4 provider settings remain
unchanged; deterministic analysis also works with `LLM_PROVIDER=disabled`.

### Manual acceptance workflow

Create two sample documents using PowerShell:

```powershell
$contractA = Join-Path $env:TEMP 'documind-contract-a.txt'
$contractB = Join-Path $env:TEMP 'documind-contract-b.txt'
@'
Party: Acme Ltd
Effective Date: 2026-11-01
Fee: USD 15000
Acme shall deliver reports by 2026-12-01.
Supplier accepts unlimited liability.
'@ | Set-Content -LiteralPath $contractA -Encoding utf8
(Get-Content -LiteralPath $contractA -Raw).Replace('USD 15000', 'USD 18000') + "`nTermination: thirty days" |
    Set-Content -LiteralPath $contractB -Encoding utf8
Write-Output $contractA
Write-Output $contractB
```

1. Upload both files through **Documents** and wait for extraction to complete.
   PDF, OCR PDF, and DOCX use the same already-extracted source pipeline.
2. As an organization Admin, open **Structured intelligence → Configure templates
   & rules**. Save the supplied contract example. Template editing uses validated
   JSON; copying an existing version and saving creates a new immutable definition.
3. Select document A, the template, and the deterministic engine. Queue analysis.
   Expect `party`, `effective_date`, and `fee` values; high-fee and liability review
   candidates; a termination-term-not-detected finding; and a delivery obligation.
   Open references and compare their exact quotations and offsets with the source.
4. In each category, approve/reject a candidate with a reason. Correct a literal
   field using one of its passages, then inspect original/corrected values and
   review history. A correction without supporting text is a **manual assertion**
   and cannot be approved as verified. Missing/invalid fields also cannot be approved
   until corrected with valid evidence. Open the revision coverage browser, select
   source text and click **Use selected text ... as correction evidence**. Then
   choose that coverage passage in the correction form. This also supports fixing
   previously missing fields. The API validates the revision and exact offsets.
5. Under **Obligations**, update status to in-progress/completed/dismissed. Responsible
   parties are literal prefixes before obligation keywords, and deadlines are
   explicit ISO dates after “by” or “on”; verify both manually.
6. Select **Compare revisions**, choose A and B, and queue a comparison. Check
   side-by-side fee changes and the added termination line with correct source sides.
   Different retained extraction revisions of one document may also be selected.
7. Export JSON and CSV. JSON includes coverage, source metadata, review history,
   and original/corrected results. The Obligations CSV button filters to obligations.
   CSV cells are escaped against spreadsheet formula execution.
8. Open the same result in two browser tabs, save a review in one, then submit an
   older version from the other: the API returns a conflict rather than overwriting.
   Polling normally refreshes the other tab automatically.
9. Retry an eligible failed document through the existing document flow. Successful
   reprocessing creates a new source revision; old reviewed analyses are labeled
   historical. New analysis does not update previous items or reviews.
10. Delete a source document. Its analyses become unavailable immediately; results,
    exports, and evidence endpoints return 410. Retained source text, values,
    corrections, quotes, reviewer notes, and comparison results are purged/redacted.
    Audit IDs, actions, actor IDs, versions, and timestamps remain. The worker still
    handles physical file cleanup. Repeated analyses referencing the other side of
    a deleted comparison cannot reveal the deleted source.
11. Test another organization and an ordinary Member account. Members can read
    organization results/export but cannot analyze or review another uploader's
    documents unless Admin. Both sources of a comparison require management rights.
    Admins alone create template/rule versions. Cross-organization IDs return 404.
12. Stop the worker, queue analysis, then restart it. Pending jobs survive; expired
    leases are recovered with the existing retry budget. Analysis failures leave
    document extraction/indexing unchanged and publish no partial results.

### Architecture, rules, and limitations

`0005_structured` adds six tables: `source_revisions`, `revision_sections`,
`analysis_templates`, `analysis_runs`, `analysis_items`, and
`analysis_review_events`. Source snapshots are made on successful extraction;
existing completed documents are snapshotted lazily when selected. Revision IDs
identify immutable text and OCR/page provenance; source file checksums are retained.
Original Phase 3 sections/chunks and Phase 4 vectors continue serving existing APIs.

`analysis_runs` doubles as the durable analysis queue. The existing worker handles
one document job then one analysis job per loop, with separate fenced leases,
retry scheduling, atomic publication, and source checks before publication. A
bounded analysis can delay the next job on a single worker but never blocks upload
requests. No Redis, Celery, agents, or workflow engine is introduced.

Field strategies are deliberately explicit: a literal `Label: value` on one line,
strict `YYYY-MM-DD` dates, finite decimal values, currency-coded money such as
`USD 15000` or `USD 50,000.00` (commas must group exactly three digits), yes/no or
true/false booleans, and semicolon lists. Descriptions do not execute instructions.
Ambiguous repeated values remain review candidates. Configurable rules support
literal case-insensitive `contains`, full-revision `missing`, numeric `threshold`
(money/decimal), and repeated-value `inconsistent`. There is no arbitrary code or
user-supplied regex execution. Limits include 40 fields/rules, 50 occurrences per
field, and 100 positive passages per keyword rule; exceeding limits fails clearly.

Missing values and missing-term rules have **coverage evidence**, not fabricated
positive quotes. They identify the complete inspected revision and are labeled
“not detected”, never proof of absence. Analysis is not based on top-k search.
Comparison uses line alignment with whitespace normalization, preserves exact
source passages, and caps input at 1500 nonempty lines per side and 10000 characters
per line. Lexical significance flags are review hints, not semantic judgments.
Layout changes, OCR errors, synonyms, implicit obligations, relative dates, and
paraphrased clauses require human review or later real-provider evaluation.

The optional `StructuredProvider` protocol is separate from the unchanged chat
contract and reuses provider settings, evidence, and the registry. All suggestions
must pass application-side source/value checks. The mock tests orchestration only;
no genuine AI-generated structured analysis is currently enabled. New modules are
under `app/structured/`; organization routes are under
`/api/v1/organizations/{id}/structured`: templates, document revisions, runs,
run sections/retries, item reviews, obligations, and exports. Source checks and
permission checks apply to exports too. UI lists the latest 100 runs/templates,
50 documents, and 100 revisions per document; this initial workspace tracks
obligations per analysis. There is no notification/reminder service.

### Automated verification

```powershell
# From backend/
.\.venv\Scripts\python.exe scripts/test_postgres.py
.\.venv\Scripts\python.exe -m ruff check .
# Optional real local embeddings in the full regression suite (cached model required)
$env:EMBEDDING_INTEGRATION = '1'
.\.venv\Scripts\python.exe scripts/test_postgres.py
Remove-Item Env:EMBEDDING_INTEGRATION
# Production frontend must be built first; ports 3001/8001 must be free.
$env:SMOKE_INTELLIGENCE = '1'
.\.venv\Scripts\python.exe scripts/smoke_fullstack.py
Remove-Item Env:SMOKE_INTELLIGENCE
# From frontend/ in a separate terminal
npm test
npm run lint
npm run typecheck
npm run build
```

Database tests and HTTP smoke tests use disposable databases and storage; they do
not delete development data. Tests cover typed normalization, extraction evidence,
comparison, coverage rules, mock provenance, optimistic reviews, old-revision
preservation, redaction, worker fencing/recovery, CSV safety, permissions, and UI.

## Phase 4: local semantic search and provider-neutral assistant

Phase 4 adds Sentence Transformers CPU embeddings, pgvector cosine retrieval, a
PostgreSQL indexing stage, private organization-bound conversations, and an
assistant at **http://localhost:3000/assistant**. Existing health, authentication,
organization, document, and OCR features remain available.

Phase 4's offline answer provider is a **development mock**. It
selects exact retrieved passages, makes no API calls, and is labeled in the UI
and every stored response. It is an extractive preview, not generative AI or a
claim that the question was answered. Production rejects the mock provider.
No paid provider or provider SDK is required for this workflow. Phase 8 adds
optional OpenAI synthesis; see [the Phase 8 guide](PHASE8.md).

### Windows setup and startup

From the repository root in PowerShell, install CPU-only PyTorch first, then the
backend dependencies. This avoids downloading GPU dependencies unnecessarily:

```powershell
Set-Location 'C:\Users\fizaa\Projects\Side Projects\DocuMind'
docker compose up -d db
.\backend\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\backend\.venv\Scripts\python.exe -m pip install -e './backend[dev]'
Set-Location backend
.\.venv\Scripts\python.exe -m app.intelligence.cli prepare
```

`prepare` explicitly downloads the configured model into `backend/var/models`
(ignored by Git), checks its dimension, and requires internet access. Runtime
inference uses cached files only. The default model is English, 384-dimensional,
with a pinned revision. Model downloads and a first cold load can take time.

Add or update these keys in **backend/.env**, preserving existing secrets:

```dotenv
EMBEDDINGS_ENABLED=true
LLM_PROVIDER=mock
LLM_MODEL=extractive-mock-v1
```

Other settings and their defaults are listed in `backend/.env.example`. API and
worker must use the same embedding model, revision, dimension, and cache path.
Changing the profile requires backfilling; old-profile vectors are never used
with the new query encoder. Dimensions must match the model's native output;
arbitrary truncation is not enabled. No LLM API key is needed for the mock.

Before starting the API/worker, stop old instances with Ctrl+C, then run from
`backend/`:

```powershell
# Validate migrations against a disposable test database first.
.\.venv\Scripts\python.exe scripts/test_postgres.py
# Apply the reviewed additive migration to the development database.
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m app.intelligence.cli check
# Enqueue existing completed documents; safe to rerun, skips active/current jobs.
.\.venv\Scripts\python.exe -m app.intelligence.cli backfill
# Optionally restrict the local administrative backfill command:
# .\.venv\Scripts\python.exe -m app.intelligence.cli backfill --organization <organization-UUID>
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload
```

In a **second PowerShell terminal**, run the existing worker continuously:

```powershell
Set-Location 'C:\Users\fizaa\Projects\Side Projects\DocuMind\backend'
.\.venv\Scripts\python.exe -m app.documents.worker
```

In a **third PowerShell terminal**, run the frontend:

```powershell
Set-Location 'C:\Users\fizaa\Projects\Side Projects\DocuMind\frontend'
npm install
npm run dev
```

### Test the complete workflow

1. Log in and upload a TXT/PDF/DOCX containing a clear fact, such as
   “Employees receive twenty days of annual leave each year.”
2. Open **AI assistant** from the dashboard. Select the organization. Extraction
   completes first; indexing then progresses through pending/processing/completed.
   Existing documents need backfill or **Index document** (uploader/Admin only).
3. Enter “How much vacation can employees take?” and click **Semantic search**.
   Open a hit to inspect the exact source text and original page/section label.
4. Click **Preview mock answer**. Verify its development label, exact passages,
   clickable references, and persisted conversation after refresh. Select one or
   more documents to restrict retrieval; no selection searches all indexed documents.
5. Try an unrelated question: sufficiently low-scoring evidence is excluded and
   the assistant abstains when nothing qualifies. Similarity is not a calibrated
   confidence score; tune `RETRIEVAL_MIN_SIMILARITY` for your corpus.
6. Switch organizations or log in as another user. Documents and conversations
   must remain isolated. Conversations are private to their creator even among
   members of the same organization. Removing membership revokes access.
7. Delete a cited document. Search excludes it immediately; history hides affected
   answers/citations and reports unavailable sources. The worker removes files,
   sections, chunks, and vectors. Indexing failures preserve readable extracted text.

Automated checks, from `backend/` and `frontend/` respectively:

```powershell
# backend
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe scripts/test_postgres.py
# Opt-in real-model integration: cached local inference, no paid API calls.
$env:EMBEDDING_INTEGRATION = '1'
.\.venv\Scripts\python.exe scripts/test_postgres.py -q tests/test_intelligence.py
Remove-Item Env:EMBEDDING_INTEGRATION
# Optional real HTTP test against production Next.js on ports 3001/8001.
# Run npm run build in frontend first; the cached embedding model is required.
$env:SMOKE_INTELLIGENCE = '1'
.\.venv\Scripts\python.exe scripts/smoke_fullstack.py
Remove-Item Env:SMOKE_INTELLIGENCE
# frontend (a separate terminal in frontend/)
npm test
npm run lint
npm run typecheck
npm run build
```

### Architecture and extension points

`app/intelligence/embeddings.py` lazily caches one CPU model per process, limits
threads/batch size, and pools token windows so existing long character chunks
are not silently truncated. `indexing.py` reuses `document_jobs` with `embed`
jobs, expiring fenced leases, retry budgets, atomic publication, and separate
index status/errors. No Redis, Celery, or additional service is introduced.

The additive `0004_intelligence` migration adds `chunk_embeddings`,
`ai_conversations`, `ai_messages`, `ai_usage`, and document index metadata.
Vectors use organization/document/chunk composite foreign keys and profile hashes.
Exact cosine retrieval filters organization, document selection, live document
state, and model profile before returning results. Relational scope indexes
support filtering. There is no approximate vector index yet: large corpora need
measured performance tuning and a dimension/profile-specific ANN index later.

`providers.py` defines the provider protocol, generation settings (model, secret,
deadline, temperature, output budget), trusted system instructions, evidence,
and supported-claim result. Implement an adapter and register it explicitly to
add a real provider; API/frontend/retrieval need no provider-specific changes.
Adapters must treat question/history/passages as untrusted data and honor network
deadlines. Keep credentials in backend environment variables only. Exceptions
are sanitized; neither credentials nor extracted content are logged.

`rag.py` validates every source ID and exact quote against the authorized context.
Only verified quoted claims are published. Supporting arbitrary generated
paraphrases requires a separately validated grounding strategy; a matching source
ID alone is not proof of support. No provider-native citation feature is used.
Historical source-bearing answers are not supplied as fresh evidence: only recent
questions and currently selected retrieved passages reach the provider. Automatic
follow-up query rewriting and conversational pronoun resolution are not included.

Assistant endpoints live under `/api/v1/organizations/{id}/intelligence`:
`GET status`, `POST search`, `POST documents/{id}/index`,
`GET/POST conversations`, `DELETE conversations/{id}`, and
`GET/POST conversations/{id}/messages`. All reuse live authentication/membership;
mutations retain CSRF validation. Next.js uses its existing server guard and
cookie proxy, with explicit AI paths, bounded bodies, and a 120-second deadline.

Usage reservations are serialized per user and persist separately from deletable
history. `AI_DAILY_REQUESTS` caps answer attempts across organizations per UTC day;
failed/interrupted attempts count. Context, output, retrieval, and concurrency
limits also apply. The current mock has no billable token usage. Real adapters
will need provider usage reconciliation before implementing monetary budgets.
The UI lists the latest 100 conversations and up to 500 documents per organization.

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

Browser requests use same-origin `/api/backend/...` Next.js route handlers. The proxy forwards only approved paths and the Cookie, Origin, CSRF, content-type and request-ID headers to the server-only `BACKEND_URL`. It forwards each `Set-Cookie` header separately. Authentication tokens are never returned in JSON or stored in localStorage/sessionStorage. Health checks also use this proxy so the backend can remain private; `NEXT_PUBLIC_API_URL` is no longer needed.

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
