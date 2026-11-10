import os
import uuid
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import Settings
from app.db.base import Base
from app.main import create_app


@pytest.fixture
def identity_db():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a separate PostgreSQL test database")
    parsed = make_url(url)
    if not (parsed.database or "").startswith("documind_test_"):
        pytest.fail("TEST_DATABASE_URL must identify a dedicated documind_test_ database")
    schema = "test_" + uuid.uuid4().hex
    connection_args = {"connect_timeout": 3}
    if parsed.host == "localhost":
        connection_args["hostaddr"] = "127.0.0.1"
    admin = create_engine(url, connect_args=connection_args)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        url, connect_args={**connection_args, "options": f"-c search_path={schema}"}
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def clients(identity_db):
    with ExitStack() as stack:

        def factory(secure=False):
            origin = "https://app.example.test" if secure else "http://localhost:3000"
            settings = Settings(
                _env_file=None,
                database_url=os.environ["TEST_DATABASE_URL"],
                auth_secret=SecretStr("test-only-signing-key-" + "x" * 40),
                cookie_secure=secure,
                environment="production" if secure else "development",
                cors_origins=[origin],
            )
            app = create_app(settings)

            def db_session():
                with Session(identity_db) as session:
                    yield session

            app.dependency_overrides[get_db] = db_session
            client = stack.enter_context(TestClient(app, base_url=origin))
            client.headers["Origin"] = origin
            return client

        yield factory
