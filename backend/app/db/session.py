from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session


def build_engine(
    database_url: str,
    statement_timeout_ms: int = 3000,
    *,
    demo_pool: bool = False,
    session_pooler: bool = False,
) -> Engine:
    connect_args = {"connect_timeout": 3}
    if not session_pooler:
        connect_args["options"] = (
            f"-c statement_timeout={statement_timeout_ms} -c lock_timeout=5000"
        )
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args=connect_args,
        **({"pool_size": 2, "max_overflow": 1, "pool_timeout": 5} if demo_pool else {}),
    )
    if session_pooler:
        # Supavisor need not accept libpq's options startup parameter. Apply the
        # same limits after TLS/session establishment, outside a transaction.
        @event.listens_for(engine, "connect")
        def configure_session(connection, record):
            previous = connection.autocommit
            connection.autocommit = True
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('statement_timeout', %s, false)",
                        (str(statement_timeout_ms),),
                    )
                    cursor.execute("SELECT set_config('lock_timeout', '5000', false)")
            finally:
                connection.autocommit = previous

    return engine


def session_scope(engine: Engine) -> Iterator[Session]:
    """Yield a session; callers explicitly commit successful writes."""
    with Session(engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
