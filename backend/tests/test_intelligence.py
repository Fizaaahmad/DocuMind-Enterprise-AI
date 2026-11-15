import math
import os
import sys
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import now
from app.documents.worker import claim_job, publish, run_once
from app.intelligence.embeddings import EmbeddingUnavailable, Encoder, _load, get_encoder, profile
from app.intelligence.indexing import enqueue
from app.intelligence.providers import (
    MockProvider,
    ProviderResult,
    ProviderUnavailable,
    SupportedClaim,
    get_provider,
)
from app.intelligence.rag import ABSTENTION, answer
from app.models import ChunkEmbedding, Document, DocumentJob
from tests.test_documents import account, mutate, organization, upload


def settings(**kwargs):
    return Settings(
        _env_file=None, database_url="postgresql+psycopg://u:p@localhost/test", **kwargs
    )


def test_mock_grounding_and_abstention():
    config = settings(llm_provider="mock")
    sources = [
        {
            "source_id": "one",
            "text": "Leave entitlement is twenty days.",
            "start_offset": 100,
            "filename": "policy.txt",
            "label": "Section 1",
        }
    ]
    text, citations = answer(MockProvider(), config, "How much leave?", [], sources)
    assert text == "Leave entitlement is twenty days. [1]"
    assert citations[0]["start_offset"] == 100
    assert citations[0]["quote"] in sources[0]["text"]
    assert answer(MockProvider(), config, "anything", [], []) == (ABSTENTION, [])


@pytest.mark.parametrize(
    "claim", [SupportedClaim("wrong", "Leave"), SupportedClaim("one", "Ninety days")]
)
def test_fabricated_citations_rejected(claim):
    class Bad:
        def generate(self, *args):
            return ProviderResult([claim])

    with pytest.raises(ProviderUnavailable, match="unsupported"):
        answer(Bad(), settings(), "q", [], [{"source_id": "one", "text": "Leave"}])


def test_provider_failures_and_missing_configuration():
    with pytest.raises(ProviderUnavailable):
        get_provider(settings())
    with pytest.raises(ValueError, match="development-only"):
        settings(environment="production", llm_provider="mock")

    class Broken:
        def generate(self, *args):
            raise TimeoutError("private provider details")

    with pytest.raises(ProviderUnavailable, match="timed out"):
        answer(Broken(), settings(), "q", [], [{"source_id": "one", "text": "Leave"}])


def test_token_windows_preserve_long_chunk():
    class Tokenizer:
        def encode(self, text, **kwargs):
            return list(range(len(text)))

        def decode(self, tokens):
            return str(tokens[0])

        def num_special_tokens_to_add(self, **kwargs):
            return 2

    class Model:
        tokenizer = Tokenizer()
        max_seq_length = 4

        def get_sentence_embedding_dimension(self):
            return 2

        def encode(self, texts, **kwargs):
            return [[1, 0] if int(text) < 2 else [0, 1] for text in texts]

    assert Encoder(Model(), 2, 2).encode(["abcd"])[0] == pytest.approx([math.sqrt(0.5)] * 2)
    with pytest.raises(EmbeddingUnavailable):
        Encoder(Model(), 3, 2)
    assert profile(settings()) != profile(settings(embedding_revision="another"))


def test_model_loaded_once_and_unavailable_is_actionable(monkeypatch):
    calls = []

    class Model:
        def __init__(self, *args, **kwargs):
            calls.append(kwargs)

        def get_sentence_embedding_dimension(self):
            return 384

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(set_num_threads=lambda _: None))
    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Model)
    )
    _load.cache_clear()
    try:
        config = settings(embeddings_enabled=True)
        assert get_encoder(config) is get_encoder(config)
        assert len(calls) == 1 and calls[0]["local_files_only"] is True
        with pytest.raises(EmbeddingUnavailable, match="disabled"):
            get_encoder(settings())
    finally:
        _load.cache_clear()


class FakeEncoder:
    def encode(self, texts):
        return [[1.0, 0.0, 0.0] if "leave" in text.lower() else [0.0, 1.0, 0.0] for text in texts]


@pytest.fixture
def ai(clients, identity_db, monkeypatch):
    monkeypatch.setattr("app.intelligence.indexing.get_encoder", lambda _: FakeEncoder())
    monkeypatch.setattr("app.intelligence.retrieval.get_encoder", lambda _: FakeEncoder())
    client = clients(embeddings_enabled=True, embedding_dimension=3, llm_provider="mock")
    account(client)
    org = organization(client)
    config = client.app.state.settings
    doc = upload(client, org, b"Annual leave is twenty days.").json()["id"]
    assert run_once(identity_db, config)
    assert run_once(identity_db, config)
    return client, org, doc, config


def test_search_rag_history_and_deletion(ai, identity_db):
    client, org, doc, config = ai
    base = f"/organizations/{org}/intelligence"
    result = mutate(client, base + "/search", {"question": "annual leave"})
    assert result.status_code == 200, result.text
    assert result.json()["sources"][0]["document_id"] == doc
    conversation = mutate(client, base + "/conversations").json()["id"]
    path = base + f"/conversations/{conversation}/messages"
    response = mutate(client, path, {"question": "leave policy"})
    assert response.status_code == 200, response.text
    assert response.json()["is_mock"]
    assert response.json()["citations"][0]["quote"] == "Annual leave is twenty days."
    assert client.get("/api/v1" + path).json()[0]["answer"] == response.json()["answer"]
    mutate(client, f"/organizations/{org}/documents/{doc}", method="DELETE")
    assert not mutate(client, base + "/search", {"question": "leave"}).json()["sources"]
    assert client.get("/api/v1" + path).json()[0]["citations"] == []
    assert run_once(identity_db, config)
    with Session(identity_db) as db:
        assert db.scalar(select(func.count()).select_from(ChunkEmbedding)) == 0


def test_cross_org_selection_and_private_history(ai, clients):
    client, org, doc, _ = ai
    other = clients(embeddings_enabled=True, embedding_dimension=3, llm_provider="mock")
    account(other, "Bob")
    other_org = organization(other, "Other")
    foreign = f"/organizations/{other_org}/intelligence"
    assert (
        mutate(other, foreign + "/search", {"question": "leave", "document_ids": [doc]}).status_code
        == 404
    )
    assert (
        mutate(
            other, f"/organizations/{org}/intelligence/search", {"question": "leave"}
        ).status_code
        == 404
    )
    base = f"/organizations/{org}/intelligence"
    conversation = mutate(client, base + "/conversations").json()["id"]
    assert other.get(f"/api/v1{foreign}/conversations/{conversation}/messages").status_code == 404
    assert mutate(other, foreign + f"/documents/{doc}/index").status_code == 404
    assert (
        mutate(
            client, f"/organizations/{org}/members", {"email": "bob@example.com", "role": "member"}
        ).status_code
        == 201
    )
    assert other.get(f"/api/v1{base}/conversations/{conversation}/messages").status_code == 404
    assert mutate(other, base + f"/documents/{doc}/index").status_code == 403


def test_index_failures_backfill_and_lease_recovery(ai, identity_db, monkeypatch):
    _, _, doc_id, config = ai
    with Session(identity_db) as db:
        document = db.get(Document, uuid.UUID(doc_id))
        enqueue(db, document, config)
        db.commit()
    claim = claim_job(identity_db, config)
    assert claim.kind == "embed"
    with Session(identity_db) as db:
        job = db.scalar(select(DocumentJob).where(DocumentJob.document_id == claim.document_id))
        job.lease_until = now() - timedelta(seconds=1)
        db.commit()

    def missing(_):
        raise EmbeddingUnavailable("Model unavailable")

    monkeypatch.setattr("app.intelligence.indexing.get_encoder", missing)
    assert run_once(identity_db, config)
    with Session(identity_db) as db:
        document = db.get(Document, claim.document_id)
        assert document.status == "completed"
        assert document.index_status in {"pending", "failed"}
        assert db.scalar(select(func.count()).select_from(ChunkEmbedding)) == 0
    assert not publish(identity_db, claim, {}, config)


def test_no_evidence_and_quota(ai):
    client, org, _, config = ai
    config.ai_daily_requests = 1
    base = f"/organizations/{org}/intelligence"
    conv = mutate(client, base + "/conversations").json()["id"]
    path = base + f"/conversations/{conv}/messages"
    response = mutate(client, path, {"question": "database"})
    assert response.status_code == 200
    assert response.json()["answer"] == ABSTENTION
    assert not response.json()["citations"]
    assert mutate(client, path, {"question": "leave"}).status_code == 429
    assert mutate(client, base + f"/conversations/{conv}", method="DELETE").status_code == 200
    conv = mutate(client, base + "/conversations").json()["id"]
    assert (
        mutate(client, base + f"/conversations/{conv}/messages", {"question": "leave"}).status_code
        == 429
    )


@pytest.mark.skipif(
    os.environ.get("EMBEDDING_INTEGRATION") != "1",
    reason="Set EMBEDDING_INTEGRATION=1 after preparing the local model",
)
def test_real_local_embedding_search_and_mock_rag(clients, identity_db):
    client = clients(embeddings_enabled=True, llm_provider="mock")
    account(client)
    org = organization(client)
    config = client.app.state.settings
    upload(client, org, b"Employees receive twenty days of annual leave each year.")
    assert run_once(identity_db, config)
    assert run_once(identity_db, config)
    base = f"/organizations/{org}/intelligence"
    response = mutate(
        client, base + "/search", {"question": "How much vacation can employees take?"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["sources"], response.text
    conv = mutate(client, base + "/conversations").json()["id"]
    response = mutate(
        client,
        base + f"/conversations/{conv}/messages",
        {"question": "How much vacation can employees take?"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_mock"] and response.json()["citations"]
