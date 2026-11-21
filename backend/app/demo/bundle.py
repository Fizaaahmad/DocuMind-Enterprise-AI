"""Portable fictional data only: no sessions, password hashes or provider records."""

import hashlib
import json
import secrets
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select, text

from app.core.security import passwords
from app.db.base import Base
from app.demo.seed import ORG, VIEWER

TABLE_NAMES = {
    "users",
    "organizations",
    "memberships",
    "documents",
    "document_sections",
    "document_chunks",
    "document_jobs",
    "source_revisions",
    "revision_sections",
    "analysis_templates",
    "analysis_runs",
    "analysis_items",
    "analysis_review_events",
    "ai_conversations",
    "ai_messages",
}
USER_COLUMNS = {"id", "name", "email", "created_at"}


def tables():
    return [table for table in Base.metadata.sorted_tables if table.name in TABLE_NAMES]


def json_value(value):
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value)
    raise TypeError("Unsupported fixture value")


def encoded(value):
    return json.dumps(
        value,
        default=json_value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode()


def records(db):
    output = {}
    for table in tables():
        rows = db.execute(select(table).order_by(*table.primary_key.columns)).mappings().all()
        output[table.name] = [
            {
                key: value
                for key, value in row.items()
                if table.name != "users" or key in USER_COLUMNS
            }
            for row in rows
        ]
    return json.loads(encoded(output))


def write_bundle(db, source, destination):
    """Only used by fresh local package generation, not a general database dump."""
    import shutil

    from app.core.config import Settings
    from app.core.demo import validate_dataset
    from app.documents.storage import LocalStorage

    payload = records(db)
    if {row["id"] for row in payload["organizations"]} != {str(ORG)} or {
        row["email"] for row in payload["users"]
    } != {"jordan@example.com", "visitor@example.com"}:
        raise ValueError("Only the authored fictional dataset can be packaged")
    # Source database/file checks use exactly the normal local demo constraints.
    settings = Settings(
        _env_file=None,
        database_url=str(db.bind.url),
        demo_mode=True,
        demo_organization_id=ORG,
        demo_viewer_id=VIEWER,
        storage_path=source,
    )
    validate_dataset(db, settings)
    source_manifest = json.loads((source / "demo-manifest.json").read_text(encoding="utf-8"))
    destination.mkdir(parents=True, exist_ok=False)
    for doc in source_manifest["documents"]:
        org, document = ORG, uuid.UUID(doc["id"])
        original = LocalStorage(source).path(org, document)
        target = LocalStorage(destination).path(org, document)
        target.parent.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(original, target)
    content = encoded(
        {"format": 1, "organization_id": str(ORG), "viewer_id": str(VIEWER), "tables": payload}
    )
    digest = hashlib.sha256(content).hexdigest()
    (destination / "records.json").write_bytes(content)
    (destination / "demo-manifest.json").write_bytes(
        encoded(
            {
                **source_manifest,
                "records_sha256": digest,
                "format": 1,
            }
        )
    )
    return digest


def read_bundle(folder, expected_hash):
    folder = Path(folder)
    if (folder / "records.json").stat().st_size > 2_000_000:
        raise ValueError("Fictional dataset exceeds the package limit")
    content = (folder / "records.json").read_bytes()
    if len(content) > 2_000_000 or hashlib.sha256(content).hexdigest() != expected_hash:
        raise ValueError("Fictional dataset does not match its explicit hash pin")
    manifest = json.loads((folder / "demo-manifest.json").read_text(encoding="utf-8"))
    payload = json.loads(content)
    if (
        payload.get("format") != 1
        or manifest.get("records_sha256") != expected_hash
        or payload.get("organization_id") != str(ORG)
        or payload.get("viewer_id") != str(VIEWER)
        or set(payload.get("tables", {})) != TABLE_NAMES
    ):
        raise ValueError("Unsupported fictional dataset manifest")
    for table in tables():
        allowed_columns = USER_COLUMNS if table.name == "users" else set(table.columns.keys())
        for row in payload["tables"][table.name]:
            if set(row) != allowed_columns:
                raise ValueError("Fixture has unexpected columns; no credentials may be imported")
    from app.documents.storage import LocalStorage

    document_rows = {row["id"]: row for row in payload["tables"]["documents"]}
    if set(document_rows) != {row["id"] for row in manifest["documents"]}:
        raise ValueError("Fixture documents do not match the manifest")
    for doc in manifest["documents"]:
        path = LocalStorage(folder).path(ORG, uuid.UUID(doc["id"]))
        content = path.read_bytes()
        record = document_rows[doc["id"]]
        if (
            record["organization_id"] != str(ORG)
            or record["source_metadata"].get("public_demo") is not True
            or len(content) != doc["size_bytes"]
            or hashlib.sha256(content).hexdigest() != doc["sha256"]
            or record["checksum"] != doc["sha256"]
        ):
            raise ValueError("Fixture original file, database record and checksum disagree")
    return payload


def import_records(db, folder, expected_hash):
    payload = read_bundle(folder, expected_hash)
    # Transaction lock and emptiness check cover ALL application tables, not just
    # those imported. Never overwrite an existing account/dataset/provider ledger.
    db.execute(text("SELECT pg_advisory_xact_lock(74021964)"))
    for table in Base.metadata.sorted_tables:
        if db.execute(select(table).limit(1)).first():
            raise ValueError("Import requires empty application tables; existing data preserved")
    for table in tables():
        for source in payload["tables"][table.name]:
            row = dict(source)
            for column in table.columns:
                if row.get(column.name) is None:
                    continue
                kind = column.type.python_type
                value = row[column.name]
                if kind is uuid.UUID:
                    row[column.name] = uuid.UUID(value)
                elif kind is datetime:
                    row[column.name] = datetime.fromisoformat(value)
                elif kind is date:
                    row[column.name] = date.fromisoformat(value)
                elif kind is Decimal:
                    row[column.name] = Decimal(value)
            if table.name == "users":
                row["password_hash"] = passwords.hash(secrets.token_urlsafe(48))
            db.execute(table.insert().values(**row))
    if records(db) != payload["tables"]:
        raise ValueError("Imported records differ from the pinned dataset")
    # Caller owns commit; errors roll back every row.


def validate_installed_bundle(db, settings):
    payload = read_bundle(settings.storage_path, settings.demo_dataset_sha256)
    if records(db) != payload["tables"]:
        raise ValueError("Managed demo database is not the pinned immutable dataset")


def validate_runtime_role(db):
    role = db.execute(text("SELECT current_database(), current_user")).one()
    if tuple(role) != ("postgres", "documind_demo_app"):
        raise ValueError("Managed demo connection uses the wrong database or role")
    privileged = db.execute(
        text(
            "SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication "
            "FROM pg_roles WHERE rolname=current_user"
        )
    ).scalar_one()
    if privileged:
        raise ValueError("Demo runtime role must not have administrative privileges")
    if db.execute(
        text(
            "SELECT EXISTS(SELECT 1 FROM pg_auth_members "
            "WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user))"
        )
    ).scalar():
        raise ValueError("Demo runtime role must not inherit other roles")
    names = [table.name for table in Base.metadata.sorted_tables] + ["alembic_version"]
    for table_name in names:
        name = "public." + table_name
        if not db.scalar(
            text("SELECT has_table_privilege(current_user, :table, 'SELECT')"), {"table": name}
        ):
            raise ValueError("Demo runtime is missing read permissions")
        for privilege in ["INSERT", "UPDATE", "DELETE", "TRUNCATE", "TRIGGER", "REFERENCES"]:
            permitted = table_name in {"auth_sessions", "refresh_tokens"} and privilege in {
                "INSERT",
                "UPDATE",
                "DELETE",
            }
            actual = db.scalar(
                text("SELECT has_table_privilege(current_user, :table, :priv)"),
                {"table": name, "priv": privilege},
            )
            if actual != permitted:
                raise ValueError("Demo runtime table privileges differ from the read-only policy")
