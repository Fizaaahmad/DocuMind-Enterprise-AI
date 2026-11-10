from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session


def build_engine(database_url: str) -> Engine:
    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
    )


def session_scope(engine: Engine) -> Iterator[Session]:
    """Yield a session; callers explicitly commit successful writes."""
    with Session(engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
