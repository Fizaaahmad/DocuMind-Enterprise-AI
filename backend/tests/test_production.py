import json
import logging
import signal
import tarfile
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.core.archive import validate_members
from app.core.body_limit import BodyLimit
from app.core.config import Settings, get_settings
from app.core.observability import SafeJSON
from app.core.worker_runtime import WorkerRuntime
from app.main import create_app
from tests.test_documents import account, mutate, organization, upload


def config(**values):
    return Settings(
        _env_file=None, database_url="postgresql+psycopg://test:private@localhost/test", **values
    )


def test_production_requires_hosts_and_exact_origins_and_redacts_inputs():
    common = {
        "environment": "production",
        "auth_secret": "secret-input-for-test-" * 3,
        "cookie_secure": True,
    }
    for values in [
        {"cors_origins": []},
        {"cors_origins": ["https://app.test/path"], "allowed_hosts": ["app.test"]},
        {"cors_origins": ["https://app.test"]},
    ]:
        with pytest.raises(ValidationError) as caught:
            config(**common, **values)
        assert common["auth_secret"] not in str(caught.value)
        assert "private@" not in str(caught.value)


def test_secret_file_configuration(monkeypatch, tmp_path):
    path = tmp_path / "secret"
    path.write_text("file-based-test-secret-" * 3)
    monkeypatch.setenv("AUTH_SECRET_FILE", str(path))
    get_settings.cache_clear()
    try:
        assert get_settings().auth_secret.get_secret_value() == path.read_text()
    finally:
        get_settings.cache_clear()


def test_body_limits_and_trusted_host():
    with TestClient(create_app(config(allowed_hosts=["testserver"]))) as client:
        assert client.get("/api/v1/health", headers={"host": "untrusted.test"}).status_code == 400
        response = client.post("/api/v1/auth/register", content=b"x" * 70000)
        assert response.status_code == 413
        assert uuid.UUID(response.headers["x-request-id"])


def test_database_errors_are_sanitized():
    app = create_app(config())

    @app.get("/test-failure")
    def failure():
        raise OperationalError("private SQL", {"password": "do-not-log"}, Exception("secret"))

    with TestClient(app) as client:
        response = client.get("/test-failure?password=not-logged")
    assert response.status_code == 503
    assert "private" not in response.text and "secret" not in response.text


def test_log_formatter_ignores_exception_values_and_unapproved_fields():
    record = logging.LogRecord(
        "app.test",
        logging.ERROR,
        "",
        0,
        "job_failed",
        (),
        (ValueError, ValueError("sensitive content"), None),
    )
    record.password = "sensitive password"
    record.document_id = str(uuid.uuid4())
    encoded = SafeJSON().format(record)
    assert "sensitive" not in encoded
    assert json.loads(encoded)["document_id"] == record.document_id


def test_sigterm_drains_worker_and_restores_handler(tmp_path):
    previous = signal.getsignal(signal.SIGTERM)
    path = tmp_path / "heartbeat.json"
    with WorkerRuntime(path) as runtime:
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        assert runtime.stopping.is_set()
    assert signal.getsignal(signal.SIGTERM) == previous


@pytest.mark.parametrize(
    "name,kind",
    [
        ("../outside", tarfile.REGTYPE),
        ("/absolute", tarfile.REGTYPE),
        ("safe/link", tarfile.SYMTYPE),
        ("safe/hardlink", tarfile.LNKTYPE),
        ("..\\outside", tarfile.REGTYPE),
    ],
)
def test_restore_rejects_unsafe_archive_members(name, kind):
    member = tarfile.TarInfo(name)
    member.type = kind
    with pytest.raises(ValueError, match="Unsafe"):
        validate_members([member])


def test_body_limit_counts_stream_without_declared_length():
    import asyncio

    async def exercise():
        sent = []
        messages = iter(
            [
                {"type": "http.request", "body": b"12345", "more_body": True},
                {"type": "http.request", "body": b"67890", "more_body": False},
            ]
        )

        async def receive():
            return next(messages)

        async def send(message):
            sent.append(message)

        async def downstream(*_):
            pytest.fail("Oversized stream reached parser")

        await BodyLimit(downstream, 8)(
            {"type": "http", "method": "POST", "path": "/api/v1/auth/login", "headers": []},
            receive,
            send,
        )
        assert sent[0]["status"] == 413

    asyncio.run(exercise())


def test_org_quota_and_admin_diagnostics(clients):
    client = clients(organization_max_documents=1)
    account(client)
    org = organization(client)
    assert upload(client, org).status_code == 202
    assert upload(client, org).status_code == 413
    assert client.get(f"/api/v1/organizations/{org}/operations/diagnostics").status_code == 200
    other = clients()
    account(other, "Bob")
    assert other.get(f"/api/v1/organizations/{org}/operations/diagnostics").status_code == 404
    mutate(client, f"/organizations/{org}/members", {"email": "bob@example.com", "role": "member"})
    assert other.get(f"/api/v1/organizations/{org}/operations/diagnostics").status_code == 403
