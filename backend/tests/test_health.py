from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.dependencies import get_db
from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@localhost/test",
    )
    app = create_app(settings)
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client, db


def test_liveness_does_not_query_database(client):
    http, db = client
    response = http.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    db.execute.assert_not_called()


def test_ready_when_database_and_vector_available(client):
    http, db = client
    db.execute.return_value.scalar_one.return_value = True
    response = http.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "pgvector": "ok"}


def test_not_ready_without_vector_extension(client):
    http, db = client
    db.execute.return_value.scalar_one.return_value = False
    response = http.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "ok", "pgvector": "unavailable"}


def test_database_failure_does_not_leak_connection_details(client):
    http, db = client
    db.execute.side_effect = OperationalError("secret connection details", {}, Exception())
    response = http.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded", "database": "unavailable", "pgvector": "unavailable"
    }
    assert "secret" not in response.text


def test_allowed_cors_origin(client):
    http, _ = client
    response = http.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unknown_cors_origin_not_allowed(client):
    http, _ = client
    response = http.get("/api/v1/health", headers={"Origin": "https://example.com"})
    assert "access-control-allow-origin" not in response.headers
