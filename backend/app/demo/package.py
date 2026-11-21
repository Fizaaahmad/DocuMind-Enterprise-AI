"""Generate portable fixtures in a NEW disposable LOCAL database; never export development data."""

import argparse
import os
import secrets
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import BACKEND_ROOT, MigrationSettings, Settings, secret_files
from app.db.session import build_engine
from app.demo.bundle import write_bundle
from app.demo.seed import seed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BACKEND_ROOT / "render-demo-assets")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Package output already exists; it was preserved")
    settings = MigrationSettings(**secret_files(("DATABASE_URL",)), demo_supabase_project_ref=None)
    url = make_url(str(settings.database_url))
    if url.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Package generation requires a LOCAL PostgreSQL connection")
    url = url.set(host="127.0.0.1")
    name = "documind_demo_package_" + uuid.uuid4().hex
    created = False
    with psycopg.connect(
        url.set(drivername="postgresql").render_as_string(hide_password=False),
        autocommit=True,
        connect_timeout=3,
    ) as admin:
        try:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            created = True
            target = url.set(database=name).render_as_string(hide_password=False)
            env = {**os.environ, "DATABASE_URL": target}
            # Migrations only read DB settings; omit inherited cloud demo pins.
            for key in ["DEMO_SUPABASE_PROJECT_REF", "DATABASE_URL_FILE"]:
                env.pop(key, None)
            result = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=BACKEND_ROOT,
                env=env,
                capture_output=True,
                check=False,
            )
            if result.returncode:
                raise ValueError("Local package migration failed")
            with tempfile.TemporaryDirectory(prefix="documind-authored-fixtures-") as storage:
                config = Settings(
                    _env_file=None,
                    database_url=target,
                    storage_path=Path(storage),
                    auth_secret=secrets.token_urlsafe(48),
                )
                engine = build_engine(target, statement_timeout_ms=120000)
                try:
                    seed(engine, config)
                    with Session(engine) as db:
                        digest = write_bundle(db, Path(storage), args.output)
                finally:
                    engine.dispose()
                print("Fictional package created. Non-secret DEMO_DATASET_SHA256:", digest)
        except Exception:
            raise SystemExit(
                "Local fixture preparation failed; existing data was not reset. "
                "Review isolated inputs; partial output is preserved."
            ) from None
        finally:
            if created:
                admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
