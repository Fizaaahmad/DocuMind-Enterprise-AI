"""Run regression tests against NEW disposable local databases, then remove only those.

Reads the local database connection privately; never logs its URL or password.
"""

import argparse
import os
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo-only", action="store_true")
    parser.add_argument("--managed-only", action="store_true")
    args = parser.parse_args()
    import psycopg
    from app.core.config import MigrationSettings, secret_files
    from psycopg import sql
    from sqlalchemy.engine import make_url

    settings = MigrationSettings(**secret_files(("DATABASE_URL",)))
    url = make_url(str(settings.database_url))
    if url.host not in {"localhost", "127.0.0.1"}:
        raise SystemExit("Local verification requires a localhost database")
    url = url.set(host="127.0.0.1")
    names = [
        "documind_test_demo_" + uuid.uuid4().hex,
        "documind_demo_verify_" + uuid.uuid4().hex,
    ]
    created = []
    with psycopg.connect(
        url.set(drivername="postgresql").render_as_string(hide_password=False),
        autocommit=True,
    ) as admin:
        try:
            env = {
                **os.environ,
                "PYTHONPATH": str(ROOT / "backend"),
                "LLM_PROVIDER": "disabled",
                "LLM_REAL_REQUESTS_ENABLED": "false",
                "LLM_API_KEY": "",
                "DEMO_MODE": "false",
            }
            for name in names:
                admin.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name))
                )
                created.append(name)
                target = url.set(database=name).render_as_string(hide_password=False)
                migration_env = {**env, "DATABASE_URL": target}
                for migration_args in [("upgrade", "head"), ("check",)]:
                    subprocess.run(
                        [sys.executable, "-m", "alembic", *migration_args],
                        cwd=ROOT / "backend",
                        env=migration_env,
                        check=True,
                    )
            env["TEST_DATABASE_URL"] = url.set(database=names[0]).render_as_string(
                hide_password=False
            )
            env["DEMO_TEST_DATABASE_URL"] = url.set(database=names[1]).render_as_string(
                hide_password=False
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/test_managed_demo.py"
                    if args.managed_only
                    else "tests/test_demo.py"
                    if args.demo_only
                    else "tests",
                    "-q",
                    "-rs",
                    "-p",
                    "no:cacheprovider",
                ],
                check=False,
                cwd=ROOT / "backend",
                env=env,
            )
            return result.returncode
        finally:
            for name in created:
                # These exact names were created by this invocation; never enumerate/drop existing data.
                admin.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                        sql.Identifier(name)
                    )
                )


if __name__ == "__main__":
    raise SystemExit(main())
