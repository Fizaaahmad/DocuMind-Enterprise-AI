# LinkedIn announcement

I built DocuMind to explore what happens after an AI finds an answer in a document.

A useful workflow also needs to know where that answer came from, who can see it, what needs review, and who owns the next action.

DocuMind is my personal full-stack document intelligence and operations project, developed and tested locally.

I also validated the OpenAI integration with a real, paid request through the Responses API using GPT-6 Luna (`gpt-6-luna`). For one recorded document question—“What must Acme pay, and when?”—the application returned a grounded answer with source citations, reported 434 input tokens and 210 output tokens, and displayed an estimated request cost of USD 0.0001484.

That is one successful manual test, not an accuracy benchmark or a promise about every document.

Choosing the model was an engineering tradeoff: I wanted useful grounded synthesis with controlled inference spend. I combined it with local Sentence Transformers embeddings, organization-scoped pgvector retrieval, bounded context, token tracking, estimated costs, and organization-level usage budgets. I did not assume a more expensive model was automatically necessary, or claim that this choice matched its quality.

Local embeddings provide semantic retrieval, not natural-language answers. GPT is the generative engine. Structured AI reads selected authorized revisions directly; chat uses retrieved chunks.

The rest of the platform supports PDF/DOCX/TXT processing, selective Tesseract OCR, extraction templates, comparisons, rule-based findings, obligation candidates, human review, assignments, and operational dashboards. Deterministic workflows remain available without GPT; the LLM provider stays behind an interface.

The most valuable work was at the boundaries: authorization, source revisions, stale evidence, job recovery, session rotation and optimistic concurrency. Exact source checks improve traceability, but people still need to review interpretations.

Stack: Next.js, React, TypeScript, Tailwind, FastAPI, SQLAlchemy/Alembic, PostgreSQL/pgvector, Sentence Transformers, PyMuPDF, Tesseract, OpenAI and Docker Compose.

This is a personal engineering project, not a commercially deployed product. The carousel separates recorded automated verification from my paid manual Q&A test. UI captures use fictional data and labeled mock output; the live example is a transcribed test record. No additional paid calls were made to create these assets.

Repository: [INSERT ACTUAL GITHUB REPOSITORY URL]

I'd welcome technical feedback on the retrieval, evidence-validation and cost-control tradeoffs.

#SoftwareEngineering #RAG #FullStackDevelopment

---

Publishing note: the live figures were supplied by Fiza Ahmad from a successful local test. No authentic screenshot/raw provider log for that exact request was found in the repository. Preserve the distinction between the transcribed manual record and mock UI captures. Replace the repository placeholder before posting.
