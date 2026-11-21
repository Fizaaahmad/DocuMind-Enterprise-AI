"""Read-only regressions use only separately created demo/test databases."""

import os
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.demo import allowed, validate_dataset
from app.core.security import now
from app.db.session import build_engine
from app.demo.seed import ORG, VIEWER, seed
from app.main import create_app
from app.models import AnalysisItem, Conversation, Document, Message, RefreshToken
from tests.test_documents import mutate


def config(**overrides):
    values = dict(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@localhost/documind_demo_test",
        auth_secret="demo-tests-only-" + "x" * 48,
        demo_mode=True,
        demo_organization_id=ORG,
        demo_viewer_id=VIEWER,
    )
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"llm_provider": "mock"},
        {"llm_real_requests_enabled": True},
        {"llm_api_key": "not-a-real-key"},
        {"embeddings_enabled": True},
        {"ocr_enabled": True},
        {"demo_viewer_id": None},
        {"database_url": "postgresql+psycopg://test:test@localhost/documind"},
    ],
)
def test_demo_config_fails_closed(overrides):
    with pytest.raises(ValueError):
        config(**overrides)


def test_allowlist_is_explicit():
    assert allowed("GET", f"/api/v1/organizations/{ORG}/documents")
    assert allowed("POST", "/api/v1/demo/enter")
    for method in ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]:
        assert not allowed(method, "/api/v1/new-feature")
    assert not allowed("POST", f"/api/v1/organizations/{ORG}/intelligence/search")
    assert not allowed("GET", f"/api/v1/organizations/{ORG}/operations/diagnostics")


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    url = os.environ.get("DEMO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Run deploy/demo/verify_local.py for isolated demo integration tests")
    settings = config(database_url=url, storage_path=tmp_path_factory.mktemp("public-demo"))
    engine = build_engine(url, statement_timeout_ms=120000)
    manifest = seed(engine, settings)
    yield engine, settings, manifest
    engine.dispose()


@pytest.fixture
def visitor(dataset):
    _, settings, _ = dataset
    with TestClient(create_app(settings), base_url="http://localhost:3000") as client:
        client.headers["Origin"] = "http://localhost:3000"
        yield client


def enter(client):
    response = mutate(client, "/demo/enter")
    assert response.status_code == 200, response.text


def test_backend_entry_throttle_cannot_be_bypassed_with_forwarded_ip(visitor):
    from app.core.demo import DemoEntryLimiter

    visitor.app.state.demo_entry_limiter = DemoEntryLimiter(1)
    enter(visitor)
    visitor.headers["X-Forwarded-For"] = "198.51.100.12"
    response = mutate(visitor, "/demo/enter")
    assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0


def test_entry_csrf_reads_citations_and_export(visitor, dataset):
    assert visitor.post("/api/v1/demo/enter").status_code == 403
    enter(visitor)
    assert visitor.get("/api/v1/auth/me").json()["id"] == str(VIEWER)
    base = f"/api/v1/organizations/{ORG}"
    documents = visitor.get(base + "/documents").json()["items"]
    assert len(documents) == 6
    for doc in documents:
        assert visitor.get(base + f"/documents/{doc['id']}/download").status_code == 200
    conversations = visitor.get(base + "/intelligence/conversations").json()
    history = visitor.get(
        base + f"/intelligence/conversations/{conversations[0]['id']}/messages"
    ).json()
    assert history[0]["is_mock"] and history[0]["citations"]
    assert "[1]" in history[0]["answer"]
    for path in [
        "/structured/runs",
        "/structured/obligations",
        "/operations/summary",
        "/operations/items",
        "/operations/activity",
        "/operations/export?format=csv",
    ]:
        assert visitor.get(base + path).status_code == 200, path


def test_all_business_writes_blocked_before_work(visitor, dataset, monkeypatch):
    engine, _, _ = dataset

    def forbidden(*args, **kwargs):
        pytest.fail("Read-only request invoked processing/provider/storage code")

    monkeypatch.setattr("app.intelligence.retrieval.get_encoder", forbidden)
    monkeypatch.setattr("app.api.routes.intelligence.get_provider", forbidden)
    monkeypatch.setattr("app.documents.storage.LocalStorage.save", forbidden)
    enter(visitor)
    with Session(engine) as db:
        counts = [
            db.scalar(select(func.count()).select_from(model))
            for model in [Document, AnalysisItem, Conversation, Message]
        ]
    base = f"/organizations/{ORG}"
    routes = [
        ("POST", "/auth/register"),
        ("POST", "/auth/login"),
        ("POST", "/organizations"),
        ("POST", base + "/members"),
        ("PATCH", base + f"/members/{VIEWER}"),
        ("DELETE", base + f"/members/{VIEWER}"),
        ("POST", base + "/documents"),
        ("DELETE", base + f"/documents/{VIEWER}"),
        ("POST", base + f"/documents/{VIEWER}/retry"),
        ("POST", base + f"/intelligence/documents/{VIEWER}/index"),
        ("POST", base + "/intelligence/search"),
        ("POST", base + "/intelligence/conversations"),
        ("DELETE", base + f"/intelligence/conversations/{VIEWER}"),
        ("POST", base + f"/intelligence/conversations/{VIEWER}/messages"),
        ("POST", base + "/structured/templates"),
        ("POST", base + "/structured/runs"),
        ("POST", base + f"/structured/runs/{VIEWER}/retry"),
        ("POST", base + f"/structured/runs/{VIEWER}/items/{VIEWER}/review"),
        ("PATCH", base + f"/operations/items/{VIEWER}/assignment"),
    ]
    for method, path in routes:
        response = mutate(visitor, path, {}, method=method)
        assert response.status_code == 403, (method, path, response.text)
    with Session(engine) as db:
        assert counts == [
            db.scalar(select(func.count()).select_from(model))
            for model in [Document, AnalysisItem, Conversation, Message]
        ]


def test_foreign_ids_denied(visitor):
    enter(visitor)
    other = uuid.uuid4()
    for path in [
        f"/organizations/{other}/documents",
        f"/organizations/{other}/operations/items",
        f"/organizations/{ORG}/intelligence/conversations/{other}/messages",
        f"/organizations/{ORG}/documents/{other}/download",
        f"/organizations/{ORG}/structured/runs/{other}",
    ]:
        assert visitor.get("/api/v1" + path).status_code in {403, 404}


def test_independent_sessions_rotation_replay_and_logout(visitor, dataset):
    engine, settings, _ = dataset
    enter(visitor)
    old_token = visitor.cookies.get("dm_refresh")
    with Session(engine) as db:
        token = db.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash.is_not(None))
            .order_by(RefreshToken.created_at.desc())
        )
        token.created_at = now() - timedelta(seconds=30)
        db.commit()
    assert mutate(visitor, "/auth/refresh").status_code == 200
    assert visitor.cookies.get("dm_refresh") != old_token
    with TestClient(create_app(settings), base_url="http://localhost:3000") as second:
        second.headers["Origin"] = "http://localhost:3000"
        enter(second)
        assert mutate(second, "/auth/logout").status_code == 204
        assert visitor.get("/api/v1/auth/me").status_code == 200
    # Immediate replay bypasses throttling and must revoke the token family.
    visitor.cookies.set("dm_refresh", old_token, domain="localhost.local", path="/")
    assert mutate(visitor, "/auth/refresh").status_code == 401


def test_seed_and_startup_safeguards(dataset):
    engine, settings, _ = dataset
    with pytest.raises(ValueError, match="empty migrated"):
        seed(engine, settings)
    with Session(engine) as db:
        validate_dataset(db, settings)
    from app.documents.worker import run_once
    from app.intelligence.providers import ProviderUnavailable, get_provider
    from app.structured.worker import run_analysis_once

    for worker in [run_once, run_analysis_once]:
        with pytest.raises(RuntimeError, match="disabled"):
            worker(engine, settings)
    with pytest.raises(ProviderUnavailable):
        get_provider(settings)


def test_secure_cookies_and_session_capacity(dataset):
    _, settings, _ = dataset
    secure = config(
        database_url=str(settings.database_url),
        storage_path=settings.storage_path,
        environment="production",
        cookie_secure=True,
        cors_origins=["https://app.example.test"],
        allowed_hosts=["app.example.test"],
    )
    with TestClient(create_app(secure), base_url="https://app.example.test") as client:
        client.headers["Origin"] = "https://app.example.test"
        enter(client)
        assert client.cookies.get("__Host-dm_access")
        assert client.cookies.get("__Host-dm_refresh")
        response = mutate(client, "/demo/enter")
        for cookie in response.headers.get_list("set-cookie"):
            assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
            assert "Domain=" not in cookie
        secure.demo_max_sessions = 1
        assert mutate(client, "/demo/enter").status_code == 429
