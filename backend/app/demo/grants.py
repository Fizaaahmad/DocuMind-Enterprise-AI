"""One-shot migrator command; the running API never receives these privileges."""

from sqlalchemy import text

from app.core.config import MigrationSettings, secret_files
from app.db.session import build_engine


def main():
    settings = MigrationSettings(**secret_files(("DATABASE_URL",)))
    engine = build_engine(str(settings.database_url))
    if engine.url.database != "documind_demo":
        raise SystemExit("Demo grants require the isolated documind_demo database")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER "
                    "ON ALL TABLES IN SCHEMA public FROM documind_demo_app"
                )
            )
            connection.execute(
                text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO documind_demo_app")
            )
            connection.execute(
                text(
                    "GRANT INSERT, UPDATE, DELETE ON auth_sessions, refresh_tokens "
                    "TO documind_demo_app"
                )
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
