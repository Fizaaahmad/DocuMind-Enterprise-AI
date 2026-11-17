from sqlalchemy import text

import app.models  # noqa: F401
from alembic import context
from app.core.config import MigrationSettings, secret_files
from app.db.base import Base
from app.db.session import build_engine

# Import future model modules here so autogenerate sees their metadata.
target_metadata = Base.metadata
settings = MigrationSettings(**secret_files(("DATABASE_URL",)))
database_url = str(settings.database_url)

if context.is_offline_mode():
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = build_engine(database_url, settings.migration_statement_timeout_ms)
    try:
        with engine.connect() as connection:
            if not connection.scalar(text("SELECT pg_try_advisory_lock(17429, 7)")):
                raise RuntimeError("Another database migration is running")
            connection.commit()
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
