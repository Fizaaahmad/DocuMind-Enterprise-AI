# Phase 8: controlled OpenAI document intelligence

OpenAI is optional. Deterministic analysis, the development mock, embeddings,
search, review, obligations and portfolio workflows remain available without a
paid provider. No real OpenAI requests were made during implementation/testing.

## Architecture and safeguards

- `OpenAIProvider` implements the existing provider contract using HTTPS
  `POST https://api.openai.com/v1/responses`, strict JSON schemas, no tools,
  no provider-managed conversation, and `store=false`. Chat sends authorized
  retrieved passages and at most three prior questions; old source-bearing
  answers are excluded. Structured analysis sends only the selected authorized
  revisions and template. No PDFs/files or embeddings are uploaded to OpenAI.
- Answers synthesize evidence in prose with claim-level supporting quotations.
  Source names, page labels, UUIDs and offsets are application-managed. Unknown
  source IDs, nonexact quotations and unsupported numeric claims are rejected.
  Empty evidence or empty claims produces an explicit abstention.
- GPT extraction selects raw source values semantically; backend type/money/date
  normalization remains authoritative. Missing fields remain missing. Configured
  deterministic rules evaluate the normalized results, and carry
  `provenance=configured_rule`; GPT suggestions carry `provenance=openai`.
  All candidates enter the existing pending human-review lifecycle.
- Comparison keeps actual deterministic differences. GPT explanations can only
  cite passages within those differences. Parties, actions and conditions in
  obligation records must occur in the supporting quote. Contract deadlines are
  separate from assignment due dates.
- Source existence/membership is checked before dispatch and source validity is
  checked before publication. Deletion redacts cached provider output while
  retaining nonsensitive accounting metadata; conversation deletion also clears
  its provider caches. Revision/review history is not overwritten.
- Migration `0007_provider_requests` adds a provider request ledger and an
  explicit retry generation to analysis runs. It is additive; review/document
  tables and existing data are preserved. Downgrading it loses Phase 8 accounting
  and cached responses. Review SQL before applying it to a valuable database.

## Windows local setup: keep real calls disabled initially

From the repository root, stop the existing backend and worker with Ctrl+C, then:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
# Review the additive SQL without changing the database:
.\.venv\Scripts\python.exe -m alembic upgrade 0006_operations:0007_provider_requests --sql
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
```

Back up valuable data before applying migrations. Leave existing database, auth,
storage and embedding settings unchanged. Open `backend/.env` locally and add:

```dotenv
LLM_PROVIDER=openai
LLM_REAL_REQUESTS_ENABLED=false
LLM_MODEL=YOUR_SUPPORTED_STRUCTURED_OUTPUT_MODEL
LLM_INPUT_USD_PER_MILLION=YOUR_VERIFIED_INPUT_PRICE
LLM_OUTPUT_USD_PER_MILLION=YOUR_VERIFIED_OUTPUT_PRICE
LLM_MAX_INPUT_TOKENS=16000
LLM_MAX_OUTPUT_TOKENS=1024
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=0
AI_DAILY_REQUESTS=2
LLM_DAILY_TOKENS=40000
LLM_DAILY_COST_USD=0.25
LLM_SEND_TEMPERATURE=false
```

Replace the model and price placeholders with valid values before starting the
backend; numeric placeholders cannot be parsed. Select a model your API project
can access that supports Responses and strict structured output. Obtain current
input/output prices from the official OpenAI pricing page, including any context
length tier applicable to your request. Prices are not hardcoded in DocuMind.
Do not set `temperature` unless the chosen model supports it. The default request
omits that parameter for reasoning-model compatibility.

Set the key securely in **each** backend/worker PowerShell terminal before starting
that process; it is never echoed or placed in shell command history:

```powershell
$documindKey = Read-Host 'OpenAI API key' -AsSecureString
$env:LLM_API_KEY = [System.Net.NetworkCredential]::new('', $documindKey).Password
Remove-Variable documindKey
```

Alternatively use a private ignored file and set `LLM_API_KEY_FILE` to its absolute
path, or place `LLM_API_KEY` in ignored `backend/.env` through your editor. Use
only one key source. Never put keys into frontend files, public environment
variables, Git, screenshots, or commands containing the literal key.

Use separate terminals as before:

```powershell
# Backend terminal, from backend/, after setting the key:
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload
```

```powershell
# Worker terminal, from backend/, after setting the key:
.\.venv\Scripts\python.exe -m app.documents.worker
```

```powershell
# Frontend terminal, from frontend/:
npm run dev
```

The disabled flag prevents dispatch even with a valid key. Enabling real calls
requires `LLM_PROVIDER=openai`, `LLM_REAL_REQUESTS_ENABLED=true`, a nonempty key,
an explicit model and positive pricing. Misconfigured enabled settings fail at
startup without printing credentials. Existing `LLM_PROVIDER=mock` continues to
work in development; `LLM_PROVIDER=disabled` leaves semantic search available.

## First controlled real GPT test (manual, may incur charges)

1. Register a fresh local test account and create a test organization so earlier
   mock requests do not consume its per-user daily limit. Use a synthetic TXT
   document, not sensitive business data. Example:

   ```text
   Acme shall pay USD 50,000 by 2030-01-01.
   The supplier must deliver the software before payment.
   Liability is capped at USD 10,000.
   ```

2. Verify it finishes processing and indexing in the correct test organization.
   Local embeddings still require the existing prepared model and
   `EMBEDDINGS_ENABLED=true`; GPT does not replace embeddings.
3. Confirm the configured price/model and small budgets. In `backend/.env`, change
   **only** `LLM_REAL_REQUESTS_ENABLED=true`; restart both backend and worker.
   Select the synthetic document in Assistant and ask: “What must Acme pay, and
   when?” Expect synthesized prose, clickable exact source passages, an OpenAI
   label, and actual token counts when returned by the provider.
4. Verify each material statement against the quote. Ask an unsupported question
   such as “What is Acme's registered office?” Expect an abstention. Checking the
   abstention may itself consume the second request; stop if the budget is reached.
5. To test extraction in the same UTC day, explicitly increase the request/token/
   cost budgets after reviewing usage. Create a template with a money field
   `contract_value`, a meaningful description and required flag, and a threshold
   rule above 40,000. Exact label matching is unnecessary for the OpenAI engine.
   Submit with **OpenAI GPT**. Expect the normalized amount, configured-rule risk,
   separately labeled AI risk candidates, and cited obligation candidates. Review
   and approve/correct through the existing workflow before relying on them.
6. For comparison, upload a version changing the fee to USD 60,000. Select both
   revisions and **Text differences + GPT explanations**. Actual before/after text
   remains visible; explanations are review candidates tied to those passages.
7. In Enterprise operations, select **OpenAI GPT review candidates** or **All
   engines**. Default portfolio views remain deterministic. Independent engines
   and template families can overlap; totals count analysis records, not unique
   real-world business items. Check exports and existing assignment/review actions.
8. Turn `LLM_REAL_REQUESTS_ENABLED=false` again and restart API/worker when finished.
   If the key was set in the terminal, clear it with `Remove-Item Env:LLM_API_KEY`
   after stopping that process. Never retry blindly after an uncertain outcome.

## Budgets, usage and recovery

Budgets are per organization per **UTC day**, shared across chat and structured
analysis. The existing per-user assistant limit remains in addition. A row lock
serializes organization budget reservations across simultaneous requests.

Input is bounded conservatively using full request UTF-8 bytes plus framing,
without another tokenizer dependency. This can reject a request that would fit a
model's token window. No silent truncation of structured revisions occurs: split
large documents or deliberately raise the limit/budget after review. Output is
bounded by `LLM_MAX_OUTPUT_TOKENS`, including model reasoning usage where applicable.

Daily enforcement uses conservative reservations for input, output and configured
retry allowance. Reservations are retained until the UTC day rolls over, even if
actual usage is lower or a failure occurs; no automatic credit/refund is assumed.
Actual input/output tokens and a separate estimated USD cost are recorded when
reported. Estimates use configured full input/output rates (no assumed cached
token discounts), not an invoice or a guarantee of the provider's final billing.
These controls do not constrain other applications using the same API key; set
appropriate project limits/alerts in OpenAI as well.

Only explicit HTTP 429 rejections are retried, bounded by count and deadline.
Timeouts, connection errors and 5xx are not automatically resent because they may
have incurred cost. Completed provider output can be reused after worker recovery
without another dispatch. An interrupted dispatch with no durable response stops
with an explicit-retry error. The analysis Retry button creates a new generation;
it may incur another charge. A chat resubmission is also a new request. Exactly-once
external billing cannot be guaranteed across a crash after sending a request.

Provider caches contain source-bearing JSON; protect database backups accordingly.
Prompts, keys, raw provider errors, responses and document text are never logged.
`store=false` disables Responses application-state storage; it does not by itself
establish a zero-retention agreement. Review OpenAI's applicable data controls
before sending sensitive documents.

## Production outbound access and secrets

The base Phase 7 deployment stays offline from OpenAI. The optional
`compose.openai.yaml` overlay grants outbound networking only to API and worker;
their ports remain private. PostgreSQL and the gateway receive no added network.
The adapter uses a fixed OpenAI HTTPS endpoint, verifies TLS, ignores environment
proxy settings, and refuses redirects. Docker networking is service-scoped, not a
destination firewall; strict outbound domain allowlisting is a host-network policy.

Create the private mounted key from PowerShell without displaying it:

```powershell
$documindKey = Read-Host 'OpenAI API key' -AsSecureString
$documindKeyPath = Join-Path (Get-Location) 'deploy/secrets/llm_api_key'
[System.IO.File]::WriteAllText($documindKeyPath, [System.Net.NetworkCredential]::new('', $documindKey).Password)
Remove-Variable documindKey
Remove-Variable documindKeyPath
```

Use existing private directory/NTFS protections. On Linux, keep the parent secret
directory 0700 and make the mounted file readable by container UID 10001; the file
is mounted read-only. Add nonsecret model, pricing, budgets and enabled flag to
`deploy/.env.production`. Build, migrate and start using the same pair of files:

```powershell
docker compose -f compose.production.yaml -f compose.openai.yaml --env-file deploy/.env.production config --quiet
docker compose -f compose.production.yaml -f compose.openai.yaml --env-file deploy/.env.production build
docker compose -f compose.production.yaml -f compose.openai.yaml --env-file deploy/.env.production run --rm migrate
docker compose -f compose.production.yaml -f compose.openai.yaml --env-file deploy/.env.production up -d
```

Before upgrades stop writers/take backups as documented in `deploy/README.md`.
The migrator needs no OpenAI key or egress. Backend and worker read the mounted
key; frontend and browser never receive it. Use the base Compose file alone for
an installation that does not enable OpenAI.

## Offline verification

```powershell
Set-Location backend
.\.venv\Scripts\python.exe scripts/test_postgres.py -q
.\.venv\Scripts\python.exe -m ruff check app tests scripts alembic
Set-Location ../frontend
npm test
npm run lint
npm run typecheck
npm run build
```

Phase 8 tests inject `httpx.MockTransport` and forbid real HTTP transport. They
cover request schemas, synthesized citations, refusals/incomplete/malformed
responses, budgets, rate limits, uncertain recovery, source deletion,
organization isolation and worker-to-portfolio integration. No test requires
a real key. Existing optional real local-embedding integration is unchanged.

Limitations: schema/quote/offset/numeric validation proves reference integrity,
not semantic entailment of arbitrary generated prose. GPT can still misinterpret
conditions or miss findings; verify cited passages and complete human review.
Non-ISO source deadlines and complex monetary/date wording may require manual
normalization; invalid fields retain raw evidence for correction. AI explanations
are optional per change. No agents, streaming, automatic provider/model selection,
or extra paid verification call is introduced.

Official references:
[Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create),
[Pricing](https://developers.openai.com/api/docs/pricing),
[Data controls](https://developers.openai.com/api/docs/guides/your-data).

## Implementation verification results

- Backend: **155 passed, 1 skipped**. The skip is the existing opt-in real local
  embedding test, not an OpenAI test. All OpenAI tests used offline transports.
- Frontend: **59 passed**; ESLint, TypeScript and the production build passed.
- Migration upgrade through `0007_provider_requests` and Alembic schema-drift
  checks passed in disposable PostgreSQL databases. Your development database
  still needs the explicit migration command above before starting updated code.
- Both production Docker images built. Linux dependency consistency and provider
  imports passed with networking disabled.
- Full-stack HTTP smoke passed for auth/CSRF, refresh rotation, document handling,
  structured analysis, reviews, comparison, assignments and exports.
- Isolated production HTTPS smoke passed for secure cookies, authorization,
  uploads/processing/downloads, protected pages, worker restart, private ports,
  rate limits and safe logs. Its temporary containers/volumes were removed.
- The OpenAI Compose overlay rendered successfully; only API/worker gained the
  extra network and key mount, retained their base configuration, and published
  no ports. Real requests remained disabled throughout verification.

The first real model/account compatibility, output quality and actual billing
checks remain manual. No keys were configured for you, no paid API calls were
made, and no changes were committed or pushed.
