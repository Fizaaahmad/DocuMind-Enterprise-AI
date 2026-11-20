# Real-world AI integration & cost optimization

Fiza Ahmad developed and tested DocuMind locally and successfully completed a real,
paid document-Q&A request through the OpenAI Responses API using **GPT-6 Luna**
(`gpt-6-luna`). This manual validation is separate from mocked automated provider
tests and from the fictional-data screenshots generated for this portfolio.

## Recorded manual example

- Question: “What must Acme pay, and when?”
- Answer: “Acme must pay USD 50,000 by 2030-01-01; the supplier must deliver the software before payment.”
- Input tokens: **434**
- Output tokens: **210**
- Estimated request cost displayed by the application: **USD 0.0001484**
- The application retrieved relevant document information and displayed source
  citations, token usage and the cost estimate.

These are the developer's recorded results from an actual local test. They are not
benchmark averages, a simulated response, a billed invoice, or current model-pricing
advice. The question and source terms also appear in `docs/PHASE8.md`. The repository
contains the Responses API integration, retrieval, citation checks and usage ledger.
An authentic screenshot or raw provider response for this exact request was not
located in the repository, so the figures are presented as a developer-provided
test record—not as a fabricated application screenshot or independently replayed log.

## Engineering decision

GPT-6 Luna was selected with cost efficiency as an engineering objective: balance
useful grounded synthesis with controlled inference spend. There is no claim of
equal quality to more expensive models, comparative accuracy, or formal benchmarking.

Local Sentence Transformers embeddings avoid paid embedding API requests. Scoped
pgvector retrieval supplies relevant passages instead of whole-document context.
OpenAI GPT synthesizes those passages through the provider-independent interface; the application validates source
IDs and exact quotations, checks unsupported numeric facts, and manages citations.
Those safeguards improve traceability but do not establish complete semantic truth.

Token accounting, configurable price-based cost estimates, organization-level daily
token/cost budgets and bounded requests make usage explicit. A provider-independent
interface keeps retrieval and workflows separate from the selected model. No measured
cost savings are claimed; these are implemented controls and architectural choices.

## Three distinct verification layers

1. **Local development/testing:** document processing, OCR, database, embeddings,
   retrieval and enterprise workflows were developed/tested locally. The portfolio
   capture additionally exercised actual APIs and the worker with fictional data.
2. **Automated verification:** recorded implementation runs show 73 frontend tests
   passed and 155 backend tests passed with one optional skip, plus recorded build,
   lint, type, migration and HTTP checks. Automated provider tests use mocked responses.
   No new full regression run is claimed for this editorial revision.
3. **Real paid OpenAI validation:** the Q&A example above confirms the developer's
   successful end-to-end manual test. It does not imply every GPT extraction, risk,
   obligation or comparison feature was manually validated.

**No additional paid requests were made to generate or revise the portfolio.**
Existing screenshots retain their development-mock labels and remain separate from
the real-request record. See `verification/live-openai-validation.json` for the
machine-readable record and its evidence limitations.

## Complementary architecture

Local all-MiniLM-L6-v2 embeddings (384 dimensions by default) and pgvector handle
retrieval, not answer generation. GPT supplies generative intelligence; deterministic
rules and human workflows add control. Chat uses retrieved chunks; configured AI
extraction, risk/obligation suggestions and comparison explanations use selected
authorized revisions directly. See `architecture-guide.md` and the updated diagrams.
