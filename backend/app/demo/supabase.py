"""Operator-only bootstrap/import. Default is OFFLINE verification, never a cloud connection.

Every live command needs --apply and --confirm-project. Run only after approval.
Admin URLs and new passwords are entered with getpass, never CLI arguments/logs.
"""

import argparse
import getpass
import os
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import MigrationSettings, secret_files
from app.db.base import Base
from app.db.session import build_engine
from app.demo.bundle import import_records, read_bundle
from app.demo.target import validate_supabase_target


def bootstrap(url, project):
    validate_supabase_target(url, project, "postgres")
    migration_password = getpass.getpass("New migrator password (not displayed): ")
    app_password = getpass.getpass("New runtime password (not displayed): ")
    if len(migration_password) < 32 or len(app_password) < 32 or migration_password == app_password:
        raise ValueError("Use two independent generated passwords of at least 32 characters")
    from psycopg import sql

    engine = build_engine(url, session_pooler=True)
    try:
        with engine.begin() as connection:
            if tuple(connection.execute(text("SELECT current_database(), current_user")).one()) != (
                "postgres",
                "postgres",
            ):
                raise ValueError("Bootstrap connected to the wrong database or admin role")
            # Dedicated project only. Do not overwrite existing roles, tables or schemas.
            existing = connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            ).all()
            roles = connection.execute(
                text(
                    "SELECT rolname FROM pg_roles WHERE rolname IN "
                    "('documind_demo_app','documind_demo_migrator')"
                )
            ).all()
            vector = connection.execute(
                text(
                    "SELECT n.nspname FROM pg_extension e "
                    "JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector'"
                )
            ).scalar()
            if existing or roles or vector not in {"extensions", "public"}:
                raise ValueError(
                    "Bootstrap needs empty public schema, unused demo roles and pgvector enabled"
                )
            cursor = connection.connection.driver_connection.cursor()
            try:
                for role, password in [
                    ("documind_demo_migrator", migration_password),
                    ("documind_demo_app", app_password),
                ]:
                    # Let libpq derive SCRAM; plaintext passwords never enter SQL text.
                    verifier = connection.connection.driver_connection.pgconn.encrypt_password(
                        password.encode(), role.encode(), b"scram-sha-256"
                    ).decode()
                    cursor.execute(
                        sql.SQL(
                            "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB "
                            "NOCREATEROLE NOREPLICATION NOINHERIT PASSWORD {}"
                        ).format(sql.Identifier(role), sql.Literal(verifier))
                    )
                    cursor.execute(
                        sql.SQL("GRANT CONNECT ON DATABASE postgres TO {}").format(
                            sql.Identifier(role)
                        )
                    )
                    cursor.execute(
                        sql.SQL("GRANT USAGE ON SCHEMA public, extensions TO {}").format(
                            sql.Identifier(role)
                        )
                    )
                    cursor.execute(
                        sql.SQL("ALTER ROLE {} SET search_path TO public, extensions").format(
                            sql.Identifier(role)
                        )
                    )
                cursor.execute("GRANT CREATE ON SCHEMA public TO documind_demo_migrator")
            finally:
                cursor.close()
    finally:
        engine.dispose()


def grant_runtime(db):
    # Exact application-table allowlist, never Supabase-managed tables/schemas.
    names = [table.name for table in Base.metadata.sorted_tables] + ["alembic_version"]
    for table_name in names:
        name = 'public."' + table_name + '"'
        db.execute(text(f"REVOKE ALL ON TABLE {name} FROM documind_demo_app, anon, authenticated"))
        db.execute(text(f"GRANT SELECT ON TABLE {name} TO documind_demo_app"))
    db.execute(
        text(
            "GRANT INSERT, UPDATE, DELETE ON public.auth_sessions, public.refresh_tokens "
            "TO documind_demo_app"
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["verify", "bootstrap", "import"])
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-project")
    args = parser.parse_args()
    # Verify the package before considering any network operation.
    read_bundle(args.bundle, args.sha256)
    if not args.apply:
        print("Offline fixture verification passed. No connection or database change made.")
        return
    project = os.environ.get("DEMO_SUPABASE_PROJECT_REF")
    if not project or args.confirm_project != project or args.command == "verify":
        raise SystemExit("Live operations require an exact confirmed project and explicit command")
    try:
        if args.command == "bootstrap":
            url = getpass.getpass(
                "Project admin SQLAlchemy URL with verified TLS (not displayed): "
            )
            bootstrap(url, project)
        else:
            settings = MigrationSettings(**secret_files(("DATABASE_URL",)))
            if (
                settings.demo_supabase_project_ref != project
                or settings.demo_dataset_sha256 != args.sha256
            ):
                raise ValueError("Import needs explicit project and dataset pins")
            validate_supabase_target(settings.database_url, project, "documind_demo_migrator")
            engine = build_engine(
                str(settings.database_url), statement_timeout_ms=120000, session_pooler=True
            )
            try:
                with Session(engine) as db:
                    if tuple(db.execute(text("SELECT current_database(), current_user")).one()) != (
                        "postgres",
                        "documind_demo_migrator",
                    ):
                        raise ValueError("Import connected to the wrong database or migrator role")
                    expected = {table.name for table in Base.metadata.sorted_tables} | {
                        "alembic_version"
                    }
                    actual = set(
                        db.execute(
                            text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                        ).scalars()
                    )
                    from app.api.routes.health import schema_head

                    if (
                        actual != expected
                        or db.execute(
                            text("SELECT version_num FROM public.alembic_version")
                        ).scalar_one()
                        != schema_head()
                    ):
                        raise ValueError(
                            "Import requires only the fully migrated application schema"
                        )
                    import_records(db, args.bundle, args.sha256)
                    grant_runtime(db)
                    db.commit()
            finally:
                engine.dispose()
    except Exception:
        raise SystemExit(
            "Managed demo operation failed. No credentials printed; "
            "review target, privileges, TLS and operator settings."
        ) from None
    print("Explicitly approved operation completed. No credentials displayed.")


if __name__ == "__main__":
    main()
