"""Run migrations and tests in a fresh, isolated PostgreSQL database.

Run from backend: .venv/Scripts/python.exe scripts/test_postgres.py
Only the uniquely named database created by this invocation is removed.
"""

import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402


def main() -> int:
    url = make_url(str(get_settings().database_url))
    database = "documind_test_" + uuid.uuid4().hex
    with psycopg.connect(
        host=url.host,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        dbname=url.database,
        connect_timeout=5,
        autocommit=True,
    ) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        print("Created isolated test database:", database, flush=True)
        env = os.environ.copy()
        env["DATABASE_URL"] = url.set(database=database).render_as_string(hide_password=False)
        env["TEST_DATABASE_URL"] = env["DATABASE_URL"]
        try:
            for command in [
                ["alembic", "upgrade", "head"],
                ["alembic", "check"],
                [
                    "pytest",
                    *(sys.argv[1:] or ["-q"]),
                    "-p",
                    "no:cacheprovider",
                    "-o",
                    "faulthandler_timeout=60",
                ],
            ]:
                result = subprocess.run([sys.executable, "-m", *command], env=env, cwd=BACKEND)
                if result.returncode:
                    return result.returncode
            return 0
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))
            print("Removed this run's temporary test database.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
