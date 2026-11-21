import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import MigrationSettings
from app.core.demo import DemoEntryLimiter
from app.db.session import build_engine
from app.demo.bundle import import_records, read_bundle, records, validate_runtime_role
from app.demo.supabase import grant_runtime
from app.demo.target import validate_supabase_target
from tests.test_demo import config

REF = "abcdefghijklmnopqrst"


@pytest.mark.parametrize("identity", [("other", "documind_demo_app"), ("postgres", "postgres")])
def test_runtime_verifies_actual_database_identity_before_reading_records(identity):
    class WrongIdentity:
        def execute(self, statement):
            return self

        def one(self):
            return identity

    with pytest.raises(ValueError, match="wrong database or role"):
        validate_runtime_role(WrongIdentity())


def test_runtime_grants_include_readiness_schema_version_without_business_writes():
    statements = []

    class Recorder:
        def execute(self, statement):
            statements.append(str(statement))

    grant_runtime(Recorder())
    assert 'GRANT SELECT ON TABLE public."alembic_version" TO documind_demo_app' in statements
    writes = [value for value in statements if value.startswith("GRANT INSERT")]
    assert len(writes) == 1 and "auth_sessions, public.refresh_tokens" in writes[0]


def url(role="documind_demo_app", ref=REF):
    return (
        f"postgresql+psycopg://{role}.{ref}:unit-test-placeholder@"
        "aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
        "?sslmode=verify-full&sslrootcert=/test-only/ca.crt"
    )


def test_managed_runtime_requires_exact_project_role_tls_and_dataset():
    values = dict(
        database_url=url(),
        demo_supabase_project_ref=REF,
        demo_dataset_sha256="a" * 64,
        environment="production",
        cookie_secure=True,
        cors_origins=["https://app.example.test"],
        allowed_hosts=["app.example.test"],
    )
    assert config(**values).demo_mode
    for change in [
        {"demo_dataset_sha256": None},
        {"demo_supabase_project_ref": "z" * 20},
        {"database_url": url("postgres")},
        {"database_url": url("documind_demo_migrator")},
        {"database_url": url().replace(":5432/", ":6543/")},
        {"database_url": url().replace("verify-full", "require")},
        {"database_url": url().replace("&sslrootcert=/test-only/ca.crt", "")},
        {"database_url": url().replace("pooler.supabase.com", "pooler.supabase.com.evil.test")},
        {"environment": "development", "cookie_secure": False},
        {"demo_mode": False},
    ]:
        with pytest.raises(ValueError):
            config(**{**values, **change})
    # Existing named-database isolation is not relaxed without an explicit managed pin.
    with pytest.raises(ValueError):
        config(database_url="postgresql+psycopg://u:p@localhost/postgres")


def test_migration_identity_cannot_use_runtime_or_admin_credentials():
    assert MigrationSettings(
        _env_file=None, database_url=url("documind_demo_migrator"), demo_supabase_project_ref=REF
    )
    for role in ["postgres", "documind_demo_app"]:
        with pytest.raises(ValueError):
            MigrationSettings(_env_file=None, database_url=url(role), demo_supabase_project_ref=REF)
    with pytest.raises(ValueError):
        validate_supabase_target(url(), REF.upper(), "documind_demo_app")


def test_entry_limiter_is_bounded_global_and_recovers():
    clock = [0]
    limiter = DemoEntryLimiter(3, clock=lambda: clock[0])
    for _ in range(3):
        limiter.check()
    with pytest.raises(HTTPException) as error:
        limiter.check()
    assert error.value.status_code == 429 and error.value.headers["Retry-After"] == "60"
    assert len(limiter.entries) == 3
    clock[0] = 60
    limiter.check()
    assert len(limiter.entries) == 1


def test_entry_limiter_serializes_concurrent_reservations():
    limiter = DemoEntryLimiter(4)

    def reserve(_):
        try:
            limiter.check()
            return True
        except HTTPException:
            return False

    with ThreadPoolExecutor(max_workers=12) as executor:
        assert sum(executor.map(reserve, range(40))) == 4


@pytest.fixture(scope="module")
def package():
    folder = Path(__file__).resolve().parents[1] / "render-demo-assets"
    manifest = json.loads((folder / "demo-manifest.json").read_text())
    return folder, manifest["records_sha256"]


def test_package_contains_no_auth_credentials_or_paid_results(package):
    folder, digest = package
    payload = read_bundle(folder, digest)
    assert "password_hash" not in json.dumps(payload)
    assert not {"auth_sessions", "refresh_tokens", "provider_requests"}.intersection(
        payload["tables"]
    )
    assert all(row["is_mock"] for row in payload["tables"]["ai_messages"])
    with pytest.raises(ValueError, match="hash pin"):
        read_bundle(folder, "0" * 64)


def test_import_preserves_ids_sources_and_refuses_overwrite(package, identity_db):
    folder, digest = package
    expected = read_bundle(folder, digest)
    with Session(identity_db) as db:
        import_records(db, folder, digest)
        db.commit()
        assert records(db) == expected["tables"]
        assert db.execute(text("SELECT count(*) FROM auth_sessions")).scalar() == 0
        hashes = db.execute(text("SELECT password_hash FROM users")).scalars().all()
        assert all(value.startswith("$argon2id$") for value in hashes)
        with pytest.raises(ValueError, match="empty application tables"):
            import_records(db, folder, digest)
        db.rollback()


def test_session_pooler_applies_timeouts_and_demo_pool_locally(identity_db):
    # Uses the local test URL; never connects to the illustrative Supabase host.
    engine = build_engine(
        identity_db.url.render_as_string(hide_password=False), demo_pool=True, session_pooler=True
    )
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SHOW statement_timeout")).scalar() == "3s"
            assert connection.execute(text("SHOW lock_timeout")).scalar() == "5s"
        assert engine.pool.size() == 2 and engine.pool._max_overflow == 1
    finally:
        engine.dispose()
