# One hybrid system: local retrieval + GPT intelligence

The two approaches are complementary components, not competing answer engines.
**Local embeddings retrieve evidence. GPT generates natural-language intelligence.
Deterministic rules and human workflows add reliability and control.**

## 1. Local embeddings and deterministic processing

The existing PostgreSQL-backed worker parses uploaded PDF, DOCX and TXT documents,
uses selective OCR for PDF pages when necessary, and creates source-linked chunks.
Sentence Transformers runs `all-MiniLM-L6-v2` locally, producing 384-dimensional
vectors in the default configuration. Chunk embeddings are stored in PostgreSQL
through pgvector; sections and immutable revisions retain source references.

Questions use the same configured local embedding profile. The backend performs
cosine-distance retrieval with similarity thresholds, retrieval limits, organization
and document-selection checks, live-document status and embedding-profile filters.
This produces relevant authorized passages. Neither these vectors nor pgvector
generate natural-language answers. No paid embedding API is used.

Deterministic extraction, configured rules, text differences and literal commitment
candidates can run without an LLM. They operate on selected source revisions through
the existing worker and publish source-linked review records.

## 2. OpenAI GPT-powered intelligence

For chat, the question and retrieved evidence flow through the provider interface to
OpenAI's Responses API. GPT synthesizes grounded prose with supporting source IDs
and quotations. The backend checks authorized source references, exact quotations
and numeric consistency, then creates application-managed citations. It abstains
when evidence is insufficient; validation is not a proof of complete semantic truth.

Configured GPT extraction, risk/obligation suggestions and comparison explanations
are a second input path: the worker sends selected authorized revision sections
directly to the structured provider. They do not all pass through chat retrieval.
Comparison starts from deterministic differences. AI suggestions remain candidates,
and human review/assignments use the existing workflow. Chat responses do not require
a formal approval step before display; human review actions apply to analysis items.

GPT requests have token accounting, configurable cost estimates, organization-level
token/cost budgets and request recovery safeguards. OpenAI is a prominent generative
component when enabled, not merely a reviewer. The interface remains configurable,
and deterministic workflows and the clearly labeled development mock remain available.

Fiza Ahmad successfully completed the real paid local GPT Q&A validation recorded
in `live-validation.md`. That manual evidence is distinct from mocked automated
provider tests and the mock screenshot capture. No new paid requests were made for
the architecture revision.

## Implementation references

- Default encoder/dimensions: `backend/app/core/config.py`.
- Local cached CPU encoding: `backend/app/intelligence/embeddings.py`.
- Worker extraction/index publication: `backend/app/documents/worker.py`,
  `backend/app/intelligence/indexing.py`.
- Query encoding, cosine distance and authorization: `backend/app/intelligence/retrieval.py`.
- Provider generation, grounding and citation construction:
  `backend/app/intelligence/rag.py`, `openai_provider.py`, `api/routes/intelligence.py`.
- Direct-revision structured AI: `backend/app/structured/ai.py`, `engine.py`, `worker.py`.
- Evidence validity/review: `backend/app/structured/sources.py`, `api/routes/structured.py`.
- Token/cost controls: `backend/app/intelligence/provider_usage.py`.

The 384-dimensional MiniLM setup is the implemented configurable default, not a
claim that every future model must have 384 dimensions. No ANN index, quality
benchmark or provider-equivalence claim is implied by the diagram.
