# Claim provenance and editorial limits

This package describes a personal engineering project. It does not claim customer
adoption, commercial deployment, legal correctness, throughput, accuracy percentages,
latency improvements, revenue, or independent security certification.

| Claim | Implementation evidence |
|---|---|
| Next.js/React/TypeScript/Tailwind UI | `frontend/package.json`, `frontend/src/app`, `frontend/src/components` |
| FastAPI, SQLAlchemy, Alembic, pgvector | `backend/pyproject.toml`, `backend/app/db`, seven migrations in `backend/alembic/versions` |
| Argon2id, JWT, rotating sessions, CSRF | `backend/app/core/security.py`, `backend/app/services/auth.py`, `backend/tests/test_identity.py` |
| Scoped documents and configurable local storage | `backend/app/documents/service.py`, `storage.py`, `validation.py` |
| Native PDF/DOCX/TXT extraction; selective OCR | `backend/app/documents/extraction.py`, `ocr.py`, `process_limits.py`, `backend/tests/test_ocr.py` |
| Existing PostgreSQL job leases/retries | `backend/app/documents/worker.py`, `backend/app/structured/worker.py` |
| Local MiniLM embeddings, default 384 dimensions | `backend/app/core/config.py`, `backend/app/intelligence/embeddings.py` |
| Profile-aware organization-scoped cosine search | `backend/app/intelligence/retrieval.py`, migration `0004_intelligence` |
| Provider-independent RAG and mock | `backend/app/intelligence/providers.py`, `rag.py` |
| Optional Responses API and structured outputs | `backend/app/intelligence/openai_provider.py`, `contracts.py`, `backend/tests/test_openai.py` |
| Source IDs/exact quotes/numeric validation | `backend/app/intelligence/rag.py`, `backend/app/structured/sources.py`, `ai.py` |
| Templates, deterministic rules, obligation candidates | `backend/app/structured/engine.py`, `schemas.py` |
| Review history, revisions, comparisons | `backend/app/models/structured.py`, `backend/app/api/routes/structured.py` |
| Assignments, queues, reporting, audit identity | `backend/app/operations`, `backend/tests/test_operations.py` |
| Request ledger and usage budgets | `backend/app/intelligence/provider_usage.py`, migration `0007_provider_requests` |
| Separate production Compose, private services, persistence | `compose.production.yaml`, `compose.openai.yaml`, `deploy/README.md` |
| Light/dark/system appearance | `frontend/src/components/theme-selector.tsx`, `frontend/src/app/theme.css` |

## Important distinctions

- Retrieval currently uses pgvector cosine distance with profile and organization
  filters. Do not describe it as a deployed HNSW/ANN system.
- OCR is selective and configurable; it is not run on every PDF page.
- Deterministic extraction/rules/comparison do not require GPT or RAG. Structured
  AI analysis uses selected authorized revisions, not the chat retrieval path.
- Exact evidence checks cannot establish complete semantic entailment. Review is
  still required, particularly for risks and obligations.
- Risk findings and obligation candidates are not legal or compliance conclusions.
- The local mock selects source passages. It is not a substitute for GPT synthesis.
- No LangGraph agent framework, Claude integration, Redis, Celery, or Kubernetes is
  claimed. They are not part of the implemented architecture shown here.

## Verification evidence

Prior implementation runs recorded 73 passing frontend tests; 155 passing backend
tests with one optional integration skip; successful lint, type checks, production
builds, migration checks, and isolated HTTP tests. The browser suite previously
checked both themes at three viewport sizes. These are recorded implementation
results, not a new full-suite run for portfolio generation and not performance data.

The portfolio capture runs actual uploads, extraction, local embeddings, indexing,
deterministic analysis/comparison, one human review, one assignment, and mock RAG
through the existing APIs. See `verification/capture-provenance.json` for this run.
Screenshots are actual rendered app screens backed by an isolated database;
no API fixture server supplies them. All organizations, documents, people and
contract terms are fictional.

Fiza Ahmad supplied a recorded successful paid OpenAI Responses API Q&A test using
GPT-6 Luna (`gpt-6-luna`): 434 input tokens, 210 output tokens, and USD 0.0001484
estimated request cost. The grounded answer and source citations were displayed in
the local app. This is manual application validation, separate from mocked automated
tests and the isolated mock screenshot capture. See `live-validation.md` and
`../verification/live-openai-validation.json` for the exact question, answer and scope.

The model, usage and cost figures are developer-provided test evidence. Repository
code confirms the implementation; `docs/PHASE8.md` corroborates the Acme question and
source terms. No raw response log or authentic screenshot for the exact request was
located, and no new paid request was made to reproduce it. The record is not a model
benchmark, current pricing advice, an invoice or validation of every AI workflow.

The cost-conscious design uses local embeddings, scoped retrieval, bounded generation,
request accounting, configurable price-based estimates and organization-level daily
token/cost budgets (`backend/app/intelligence/provider_usage.py`). It makes no claim
of measured savings or equal accuracy to higher-cost models.

## Architecture diagram revision

The revised diagram separates local chunk/query encoding and pgvector retrieval
from OpenAI GPT generation. Local vectors are not answer generators, and GPT is not
merely a reviewer. Source-driven deterministic analysis is a separate path; selected
revision sections also feed configured GPT analysis directly, rather than all AI
features passing through chat retrieval. Human review applies to analysis candidates;
it is not a mandatory chat-approval gate. See `architecture-guide.md` for exact code
references. The configurable default encoder is all-MiniLM-L6-v2 / 384 dimensions.
