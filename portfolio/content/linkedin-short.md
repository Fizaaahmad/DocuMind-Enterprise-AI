# Short alternative

I built DocuMind, a personal full-stack document intelligence and operations platform, and developed and tested it locally.

I also successfully validated document-grounded Q&A with a real, paid OpenAI Responses API request using GPT-6 Luna (`gpt-6-luna`). One recorded test returned citations, 434 input tokens, 210 output tokens and an estimated cost of USD 0.0001484.

My goal was cost-conscious synthesis: local Sentence Transformers embeddings, pgvector retrieval, bounded context and organization-level token/cost budgets. This is a practical model-selection tradeoff, not a quality benchmark or a claim of parity with higher-cost models.

Beyond chat: PDF/DOCX/TXT processing, selective OCR, extraction, comparison, rule-based findings, obligation candidates, human review and assignments. Local embeddings retrieve evidence; GPT generates answers and configured AI analysis. The provider remains configurable.

Stack: Next.js/TypeScript/Tailwind, FastAPI, PostgreSQL/pgvector, SQLAlchemy/Alembic, Sentence Transformers, PyMuPDF/Tesseract and Docker Compose.

Personal project, not commercial deployment. The carousel distinguishes automated tests from the real manual test record; UI screenshots remain fictional-data mock captures. No additional paid calls were made for these assets.

Code: [INSERT ACTUAL GITHUB REPOSITORY URL]

What would you challenge first: retrieval quality, evidence validation, or the cost controls?

#SoftwareEngineering #RAG #FullStackDevelopment
