"""Offline-only Phase 8 contracts. No real OpenAI HTTP transport is allowed."""

import json
import uuid
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.worker import run_once
from app.intelligence.openai_provider import Answer, OpenAIProvider
from app.intelligence.provider_usage import provider_scope
from app.intelligence.providers import ProviderUnavailable, get_provider
from app.intelligence.rag import ABSTENTION, answer
from app.models import ProviderRequest
from app.structured.engine import analyze
from app.structured.worker import run_analysis_once
from tests.test_documents import account, mutate, organization, upload


@pytest.fixture(autouse=True)
def forbid_openai_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Real HTTP transport forbidden in OpenAI tests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)


def configured(clients, **extra):
    return clients(
        llm_provider="openai",
        llm_real_requests_enabled=True,
        llm_api_key=SecretStr("offline-test-key"),
        llm_model="test-structured-model",
        llm_input_usd_per_million=1,
        llm_output_usd_per_million=2,
        llm_max_retries=0,
        **extra,
    )


def response(data, **extra):
    return httpx.Response(
        200,
        json={
            "status": "completed",
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "output": [{"content": [{"type": "output_text", "text": json.dumps(data)}]}],
            **extra,
        },
    )


def seed(client, engine):
    account(client)
    org = organization(client)
    document = upload(client, org, b"The fee is USD 50,000. Acme must pay by 2030-01-01.").json()[
        "id"
    ]
    assert run_once(engine, client.app.state.settings)
    client.get(f"/api/v1/organizations/{org}/structured/documents/{document}/revisions")
    return org, document


def invoke(client, engine, org, doc, handler, key=None):
    provider = OpenAIProvider(client.app.state.settings, httpx.MockTransport(handler))
    with provider_scope(
        engine,
        uuid.UUID(org),
        client.get("/api/v1/auth/me").json()["id"],
        key or str(uuid.uuid4()),
        [doc],
    ):
        return provider.request(Answer, {"question": "fee", "sources": []})


def test_optional_configuration_and_offline_synthesis(clients):
    from app.core.config import Settings

    config = Settings(
        _env_file=None, database_url="postgresql+psycopg://u:p@localhost/db", llm_provider="openai"
    )
    with pytest.raises(ProviderUnavailable, match="disabled"):
        get_provider(config)
    source = {"source_id": "s", "text": "The fee is USD 50,000.", "start_offset": 0}

    class Synthesizer:
        def generate(self, *args):
            from app.intelligence.providers import ProviderResult, SupportedClaim

            return ProviderResult(
                [SupportedClaim("s", source["text"], "The agreement sets a USD 50,000 fee.")]
            )

    text, refs = answer(Synthesizer(), config, "fee?", [], [source])
    assert "agreement sets" in text and refs[0]["quote"] == source["text"]
    assert answer(Synthesizer(), config, "fee?", [], []) == (ABSTENTION, [])


def test_http_contract_usage_cache_and_uncertain_recovery(clients, identity_db):
    client = configured(clients)
    org, doc = seed(client, identity_db)
    calls = []

    def handler(request):
        calls.append(request)
        body = json.loads(request.content)
        assert request.url == "https://api.openai.com/v1/responses"
        assert body["store"] is False and body["text"]["format"]["strict"] is True
        assert "temperature" not in body and "tools" not in body
        return response({"claims": []})

    key = str(uuid.uuid4())
    invoke(client, identity_db, org, doc, handler, key)
    invoke(client, identity_db, org, doc, handler, key)
    assert len(calls) == 1
    with Session(identity_db) as db:
        row = db.scalar(select(ProviderRequest).where(ProviderRequest.operation_key == key))
        assert (row.input_tokens, row.output_tokens, row.attempts) == (100, 50, 1)
        assert float(row.estimated_cost) == pytest.approx(0.0002)
        assert row.response == {"claims": []}
    unknown = str(uuid.uuid4())

    def timeout(request):
        raise httpx.ReadTimeout("sensitive provider detail")

    with pytest.raises(ProviderUnavailable, match="uncertain"):
        invoke(client, identity_db, org, doc, timeout, unknown)
    with pytest.raises(ProviderUnavailable, match="explicit retry"):
        invoke(client, identity_db, org, doc, handler, unknown)
    assert len(calls) == 1


@pytest.mark.parametrize("kind", ["refusal", "incomplete", "schema", "secret_error", "oversize"])
def test_provider_failures_are_safe(kind, clients, identity_db):
    client = configured(clients)
    org, doc = seed(client, identity_db)

    def handler(request):
        if kind == "refusal":
            return httpx.Response(
                200, json={"status": "completed", "output": [{"content": [{"type": "refusal"}]}]}
            )
        if kind == "incomplete":
            return httpx.Response(200, json={"status": "incomplete"})
        if kind == "secret_error":
            return httpx.Response(401, text="secret-key private document")
        if kind == "oversize":
            return httpx.Response(200, content=b"x" * 2_000_001)
        return response({"claims": [{"text": "invented", "evidence": [], "extra": "bad"}]})

    with pytest.raises(ProviderUnavailable) as caught:
        invoke(client, identity_db, org, doc, handler)
    assert "secret-key" not in str(caught.value) and "private document" not in str(caught.value)


def test_budgets_and_known_rate_limit_retry(clients, identity_db, monkeypatch):
    client = configured(clients)
    org, doc = seed(client, identity_db)
    calls = []
    client.app.state.settings.llm_max_retries = 1
    monkeypatch.setattr("app.intelligence.openai_provider.time.sleep", lambda _: None)

    def handler(request):
        calls.append(request)
        return (
            httpx.Response(429, headers={"retry-after": "0.1"})
            if len(calls) == 1
            else response({"claims": []})
        )

    invoke(client, identity_db, org, doc, handler)
    assert len(calls) == 2
    for field, limit in [("llm_daily_cost_usd", 0.000001), ("llm_daily_tokens", 1000)]:
        old = getattr(client.app.state.settings, field)
        setattr(client.app.state.settings, field, limit)
        with pytest.raises(ProviderUnavailable, match="budget"):
            invoke(client, identity_db, org, doc, handler)
        setattr(client.app.state.settings, field, old)
    assert len(calls) == 2


def test_cross_org_and_deleted_cache_isolation(clients, identity_db):
    alice = configured(clients)
    org, doc = seed(alice, identity_db)
    key = str(uuid.uuid4())
    invoke(alice, identity_db, org, doc, lambda _: response({"claims": []}), key)
    bob = configured(clients)
    account(bob, "Bob")
    other = organization(bob)
    assert (
        bob.get(f"/api/v1/organizations/{org}/structured/documents/{doc}/revisions").status_code
        == 404
    )
    with pytest.raises(ProviderUnavailable):
        invoke(bob, identity_db, other, doc, lambda _: pytest.fail("Unauthorized network"), key)
    assert (
        mutate(alice, f"/organizations/{org}/documents/{doc}", method="DELETE").status_code == 202
    )
    with Session(identity_db) as db:
        row = db.scalar(select(ProviderRequest).where(ProviderRequest.operation_key == key))
        assert row.response is None and row.state == "redacted"


def test_ai_worker_fields_rules_obligations_and_portfolio(clients, identity_db, monkeypatch):
    client = configured(clients)
    org, doc = seed(client, identity_db)

    def handler(request):
        data = json.loads(json.loads(request.content)["input"][0]["content"])
        source = data["sources"][0]
        ref = {"source_id": source["id"], "quote": source["text"]}
        return response(
            {
                "fields": [
                    {
                        "name": "contract_value",
                        "raw": "USD 50,000",
                        "normalized": "USD 50000",
                        "evidence": [ref],
                    }
                ],
                "risks": [
                    {
                        "name": "Payment exposure",
                        "severity": "medium",
                        "rationale": "The fee creates payment exposure.",
                        "evidence": [ref],
                    }
                ],
                "obligations": [
                    {
                        "action": "Acme must pay by 2030-01-01.",
                        "responsible_party": "Acme",
                        "deadline": "2030-01-01",
                        "conditions": None,
                        "uncertainty": None,
                        "evidence": [ref],
                    }
                ],
                "explanations": [],
            }
        )

    original = OpenAIProvider.__init__
    monkeypatch.setattr(
        OpenAIProvider,
        "__init__",
        lambda self, settings: original(self, settings, httpx.MockTransport(handler)),
    )
    template = mutate(
        client,
        f"/organizations/{org}/structured/templates",
        {
            "name": "Contract",
            "fields": [{"name": "contract_value", "label": "Value", "type": "money"}],
            "rules": [
                {
                    "name": "High value",
                    "type": "threshold",
                    "field": "contract_value",
                    "threshold": 40000,
                }
            ],
        },
    ).json()["id"]
    run = mutate(
        client,
        f"/organizations/{org}/structured/runs",
        {
            "document_id": doc,
            "template_id": template,
            "engine": "openai",
        },
    )
    assert run.status_code == 202, run.text
    assert run_analysis_once(identity_db, client.app.state.settings)
    result = client.get(f"/api/v1/organizations/{org}/structured/runs/{run.json()['id']}").json()
    assert result["run"]["state"] == "completed", result["run"].get("error")
    assert len(result["items"]) == 4 and result["usage"]["input_tokens"] == 100
    assert all(i["review_status"] == "pending" for i in result["items"])
    finding = next(i for i in result["items"] if i["kind"] == "field")
    assert finding["original"]["value"]["amount"] == "50000"
    query = client.get(f"/api/v1/organizations/{org}/operations/items?engine=openai")
    assert query.status_code == 200 and "openai" in query.text


@pytest.mark.parametrize(
    "quote,raw", [("invented passage", "USD 50,000"), ("The fee is USD 50,000.", "USD 90000")]
)
def test_structured_unsupported_fields_rejected(quote, raw, clients, monkeypatch):
    from app.intelligence.openai_provider import Analysis

    class Fake:
        def analyze(self, data):
            return Analysis.model_validate(
                {
                    "fields": [
                        {
                            "name": "value",
                            "raw": raw,
                            "normalized": None,
                            "evidence": [{"source_id": "s", "quote": quote}],
                        }
                    ],
                    "risks": [],
                    "obligations": [],
                    "explanations": [],
                }
            )

    monkeypatch.setattr("app.structured.ai.get_provider", lambda _: Fake())
    config = configured(clients).app.state.settings
    section = SimpleNamespace(
        id="s", text="The fee is USD 50,000.", revision_id="r", page_number=1, label="Page 1"
    )
    with pytest.raises(ProviderUnavailable):
        analyze(
            [section],
            [],
            {"fields": [{"name": "value", "type": "money", "required": False}]},
            "extract",
            "openai",
            config,
        )


def test_generated_numbers_must_be_in_evidence():
    from app.intelligence.rag import validate_facts

    with pytest.raises(ProviderUnavailable):
        validate_facts("Pay USD 90,000.", "Pay USD 50,000.")


def test_real_rag_http_path_synthesizes_and_keeps_authorized_citations(
    clients,
    identity_db,
    monkeypatch,
):
    from app.models import DocumentChunk

    client = configured(clients)
    org, doc = seed(client, identity_db)
    with Session(identity_db) as db:
        chunk = db.scalar(select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(doc)))
        source = {
            "source_id": str(chunk.id),
            "document_id": doc,
            "text": chunk.text,
            "filename": "contract.txt",
            "label": "Section 1",
            "page_number": None,
            "start_offset": chunk.start_offset,
        }
    monkeypatch.setattr("app.api.routes.intelligence.retrieve", lambda *args: [source])
    calls = []

    def handler(request):
        calls.append(request)
        return response(
            {
                "claims": [
                    {
                        "text": "The agreement requires Acme to pay USD 50,000.",
                        "evidence": [{"source_id": source["source_id"], "quote": source["text"]}],
                    }
                ]
            }
        )

    original = OpenAIProvider.__init__
    monkeypatch.setattr(
        OpenAIProvider,
        "__init__",
        lambda self, settings: original(self, settings, httpx.MockTransport(handler)),
    )
    base = f"/organizations/{org}/intelligence"
    conv = mutate(client, base + "/conversations").json()["id"]
    result = mutate(
        client, base + f"/conversations/{conv}/messages", {"question": "What fee is due?"}
    )
    assert result.status_code == 200, result.text
    assert "agreement requires" in result.json()["answer"]
    assert result.json()["citations"][0]["quote"] == source["text"]
    assert result.json()["usage"]["input_tokens"] == 100
    assert len(calls) == 1
    mutate(client, base + f"/conversations/{conv}", method="DELETE")
    with Session(identity_db) as db:
        assert db.scalar(select(ProviderRequest)).response is None


@pytest.mark.parametrize(
    "kind", ["party", "deadline", "unknown_source", "wrong_change", "valid_change"]
)
def test_ai_obligations_and_comparison_reject_unsupported_evidence(kind, clients, monkeypatch):
    from app.intelligence.openai_provider import Analysis

    config = configured(clients).app.state.settings
    left = SimpleNamespace(
        id="before",
        text="Acme must pay by 2030-01-01.",
        revision_id="r1",
        page_number=1,
        label="Before",
    )
    right = SimpleNamespace(
        id="after",
        text="Acme must pay by 2031-01-01.",
        revision_id="r2",
        page_number=1,
        label="After",
    )
    ref = {"source_id": "before", "quote": left.text}
    values = {"fields": [], "risks": [], "obligations": [], "explanations": []}
    mode = "extract"
    if kind in {"wrong_change", "valid_change"}:
        mode = "compare"
        values["explanations"] = [
            {
                "change_index": 0 if kind == "valid_change" else 99,
                "explanation": "Changed deadline",
                "evidence": [ref],
            }
        ]
    else:
        if kind == "unknown_source":
            ref["source_id"] = "other-organization-section"
        values["obligations"] = [
            {
                "action": left.text,
                "responsible_party": "Invented" if kind == "party" else "Acme",
                "deadline": "2040-01-01" if kind == "deadline" else None,
                "conditions": None,
                "uncertainty": None,
                "evidence": [ref],
            }
        ]
    fake = SimpleNamespace(analyze=lambda _: Analysis.model_validate(values))
    monkeypatch.setattr("app.structured.ai.get_provider", lambda _: fake)

    def perform():
        return analyze(
            [left],
            [right] if mode == "compare" else [],
            {"obligations": True},
            mode,
            "openai",
            config,
        )

    if kind == "valid_change":
        result, _ = perform()
        assert result[0]["original"]["before"] == left.text
        assert result[0]["original"]["ai_explanation"] == "Changed deadline"
    else:
        with pytest.raises(ProviderUnavailable):
            perform()


def test_concurrent_budget_reservations_are_serialized(clients, identity_db):
    from concurrent.futures import ThreadPoolExecutor

    from app.intelligence.provider_usage import reserve

    client = configured(clients, llm_daily_tokens=3000)
    org, doc = seed(client, identity_db)
    user = client.get("/api/v1/auth/me").json()["id"]

    def request(_):
        with provider_scope(identity_db, uuid.UUID(org), user, str(uuid.uuid4()), [doc]):
            try:
                reserve(client.app.state.settings, "f" * 64, 1000)
                return "reserved"
            except ProviderUnavailable:
                return "limited"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(request, range(2))) == ["limited", "reserved"]


def test_enabled_configuration_requires_pricing_and_redacts_secret():
    from pydantic import ValidationError

    from app.core.config import Settings

    secret = "sensitive-test-key-never-display"
    with pytest.raises(ValidationError) as caught:
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://u:p@localhost/db",
            llm_provider="openai",
            llm_real_requests_enabled=True,
            llm_api_key=SecretStr(secret),
            llm_model="test-model",
        )
    assert secret not in str(caught.value)
