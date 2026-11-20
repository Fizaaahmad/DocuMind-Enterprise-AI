# DocuMind — portfolio showcase

A personal engineering project demonstrating production-oriented document intelligence
and operations. This package does not claim commercial deployment or customers.

Designed & Developed by **Fiza Ahmad**. Personal credits appear on the case study
cover, first carousel slide, and understated page/slide footers. DocuMind remains
the primary visual identity. Editable layouts preserve these credits on regeneration.

## Final exports

`DocuMind-Portfolio-Package.zip` contains the complete package, including editable
sources and verification notes. It is a local distribution export, not a Git asset.
Individual files below are also available directly.
The ZIP, any older extracted copy, and generated verification PNG previews stay
local and are excluded from Git. The bundler also excludes the extracted copy and
verification previews to prevent stale assets and duplicate nesting. Final carousel
PNGs, architecture images and product screenshots remain included.

| File/folder | Use |
|---|---|
| `case-study/DocuMind-Engineering-Case-Study.pdf` | Eight-page project case study; attach to a portfolio or LinkedIn Featured |
| `carousel/DocuMind-LinkedIn-Carousel.pdf` | Eight-page LinkedIn document carousel |
| `carousel/png/slide-01.png` … `slide-08.png` | Individual 1080 × 1350 slides |
| `architecture/documind-architecture.png` | High-resolution architecture image |
| `architecture/documind-architecture.svg` | Editable vector architecture source |
| `screenshots/` | Real application screenshots, with focused `-detail` crops |
| `content/linkedin-post.md` | Main first-person announcement, with publishing notes |
| `content/linkedin-short.md` | Shorter alternative |
| `content/engineering-notes.md` | Code-to-claim references, test provenance and limitations |
| `verification/` | Capture provenance, live API test record and authored review notes; generated reports/previews stay local |
| `source/` | Editable Python/HTML-template sources and generation/capture scripts; generated HTML and demo files stay local |

## Publishing

Dark-mode captures are in `screenshots/dark/`; light-mode versions remain directly
in `screenshots/`. The PDF cover, Assistant images and Operations image use selected
dark-mode views, while other screens retain light mode for contrast and variety.
For a concise two-post strategy and the four recommended follow-up images, see
`content/publishing-plan.md`. The four selected viewport-sized follow-up images are under
`screenshots/post-ready/`. The other capture variants remain local only.

1. Open both PDFs and review all eight pages before publishing.
2. Replace `[INSERT ACTUAL GITHUB REPOSITORY URL]` in the chosen post.
3. Adjust the first-person motivation to match your own experience. No biographical
   details or employment claims are inferred.
4. Upload the carousel PDF as a LinkedIn document, or use individual PNGs elsewhere.
5. Retain the mock/demo captions. Do not describe the Assistant screenshot as a
   genuine OpenAI response or remove its development-mock label.

## Screenshot and AI provenance

The screenshots show the actual Phase 9 frontend connected to the actual FastAPI
backend and an isolated PostgreSQL database. Fictional files were uploaded through
the existing APIs and processed by the existing worker. Local cached embeddings,
pgvector retrieval, deterministic extraction, comparison, review, assignment and
mock RAG were exercised. No screenshot UI was drawn or substituted by an API fixture.

All names, organizations and contractual terms are fictional. Screenshot totals are
real counts of these demo records, not business-impact metrics. OCR is implemented
and tested in the application but was not invoked by these native-text demo PDFs.

Fiza Ahmad completed a genuine paid OpenAI Responses API Q&A test locally using
GPT-6 Luna (`gpt-6-luna`). The recorded example returned citations, 434 input tokens,
210 output tokens and an application-estimated cost of USD 0.0001484. See
`content/live-validation.md` and `verification/live-openai-validation.json`.

Verification has three distinct layers: local application/pipeline testing;
recorded automated tests with mocked provider responses; and successful real paid
OpenAI Q&A validation. Only that Q&A example is claimed as manually validated—this
does not establish that every GPT-powered feature was manually tested or benchmarked.

OpenAI was disabled specifically during portfolio capture and asset generation.
No additional paid requests were made to generate or revise these assets. Product
screenshots retain their mock labels; the live request is shown as a transcribed
manual test record supplied by the developer. No authentic screenshot or raw log
for that exact request was located in the repository. No API key is included.

The demo database, storage and owned processes are removed after capture. Existing
application data and source code are not changed. Demo session cookies exist only
in memory and are never written to this directory.

## Hybrid architecture: complementary roles

Local Sentence Transformers uses all-MiniLM-L6-v2 (384 dimensions by default) for
chunk and question vectors. pgvector retrieves authorized evidence by cosine
similarity. These vectors do not generate natural-language answers or require a
paid embedding API. OpenAI GPT provides grounded answer synthesis and configured
AI extraction, risk/obligation suggestions and comparison explanations.

Chat receives retrieved chunks; structured AI receives selected authorized revisions
through the worker. Source validation precedes publication. Human review and
assignments apply to analysis candidates; chat answers do not require a formal
approval step. Deterministic analysis has its own source-driven path. GPT requests
have token accounting, estimated costs and organization-level budgets, and paid Q&A
was successfully validated locally. See `content/architecture-guide.md` for code
references and the distinction between configurable providers and their actual roles.

## Reproduce on Windows

Use the existing prepared backend virtual environment, a completed frontend build,
running local PostgreSQL, and the locally cached default embedding model. Ports
3004/8004 must be free. The database role must have CREATEDB. The capture script
applies migrations and runs `alembic check` only in its new disposable database.

From the repository root:

```powershell
# Browser tooling is separate from application dependencies.
npm install --prefix .production-smoke/ui-tools --no-save --package-lock=false playwright
.\backend\.venv\Scripts\python.exe -u portfolio/source/demo_capture.py
.\backend\.venv\Scripts\python.exe -B portfolio/source/design.py
node portfolio/source/render.mjs
.\backend\.venv\Scripts\python.exe -B portfolio/source/verify.py
```

Microsoft Edge is used for capture/rendering. PyMuPDF is already an application
dependency. The sources use local system fonts and no remote image/font services.
Regeneration overwrites portfolio exports only. Do not run concurrent captures.
If forcefully interrupted, inspect owned demo processes/database before cleanup;
never delete a database or storage volume merely because it belongs to development.

## Verification boundaries

Prior implementation runs recorded 73 passing frontend tests and 155 passing backend
tests with one optional integration skip, plus lint, type/build, migration and HTTP
checks. These are attributed historical results, not a fresh full-suite run for
portfolio generation. The current capture and export checks are recorded separately.
There are no performance benchmarks, customer outcomes or deployment claims here.

## Curated Git assets

`source/assets.py` is the explicit screenshot selection: eight screenshots/crops
referenced by the approved case study and carousel, plus the four images recommended
in `content/publishing-plan.md`. Original capture variants are not all versioned.
The retained sources regenerate HTML, fictional demo documents and verification
previews/reports when needed. Run `design.py`, then `render.mjs`, then `verify.py`
for an export-only rebuild using the committed screenshots; this needs no API or
database. Run `demo_capture.py` only if you want a fresh isolated product capture.
The bundler follows the same curation and excludes generated intermediates. No files
need to be deleted from your local workspace.
