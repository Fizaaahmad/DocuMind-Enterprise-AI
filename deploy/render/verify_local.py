"""512 MiB / 0.1 CPU candidate test. Creates only owned localhost DB/container resources.

Requires the existing local development PostgreSQL Docker container. No cloud URL
is accepted. Runtime credentials go through subprocess environment, never output.
"""

import json
import os
import secrets
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def docker(*args, **kwargs):
    return subprocess.run(
        ["docker", *args], check=True, capture_output=True, text=True, **kwargs
    ).stdout.strip()


def main():
    import httpx
    import psycopg
    from app.core.config import MigrationSettings, secret_files
    from app.db.session import build_engine
    from app.demo.bundle import import_records, validate_installed_bundle
    from app.demo.seed import ORG, VIEWER
    from psycopg import sql
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session

    settings = MigrationSettings(
        **secret_files(("DATABASE_URL",)), demo_supabase_project_ref=None
    )
    url = make_url(str(settings.database_url))
    if url.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Verification accepts a LOCAL database only")
    url = url.set(host="127.0.0.1")
    assets = ROOT / "backend/render-demo-assets"
    digest = json.loads((assets / "demo-manifest.json").read_text())["records_sha256"]
    name = "documind_demo_render_" + uuid.uuid4().hex
    container = "documind-render-check-" + uuid.uuid4().hex
    created, started = False, False
    # Find the existing local database's network without changing that container.
    networks = json.loads(
        docker(
            "inspect", "--format", "{{json .NetworkSettings.Networks}}", "documind-db-1"
        )
    )
    network = next(iter(networks))
    with psycopg.connect(
        url.set(drivername="postgresql").render_as_string(hide_password=False),
        autocommit=True,
        connect_timeout=3,
    ) as admin:
        try:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            created = True
            local_url = url.set(database=name).render_as_string(hide_password=False)
            migration_env = {**os.environ, "DATABASE_URL": local_url}
            for key in ["DEMO_SUPABASE_PROJECT_REF", "DATABASE_URL_FILE"]:
                migration_env.pop(key, None)
            subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=ROOT / "backend",
                env=migration_env,
                capture_output=True,
                check=True,
            )
            engine = build_engine(local_url, statement_timeout_ms=120000)
            try:
                with Session(engine) as db:
                    import_records(db, assets, digest)
                    db.commit()
                    from types import SimpleNamespace

                    validate_installed_bundle(
                        db,
                        SimpleNamespace(
                            storage_path=assets, demo_dataset_sha256=digest
                        ),
                    )
            finally:
                engine.dispose()
            values = {
                "DATABASE_URL": url.set(
                    host="documind-db-1", database=name
                ).render_as_string(hide_password=False),
                "AUTH_SECRET": secrets.token_urlsafe(48),
                "ENVIRONMENT": "development",
                "DEMO_MODE": "true",
                "DEMO_ORGANIZATION_ID": str(ORG),
                "DEMO_VIEWER_ID": str(VIEWER),
                "DEMO_DATASET_SHA256": digest,
                "CORS_ORIGINS": '["http://localhost:3000"]',
                "ALLOWED_HOSTS": '["127.0.0.1","localhost"]',
                "COOKIE_SECURE": "false",
                "LLM_PROVIDER": "disabled",
                "LLM_REAL_REQUESTS_ENABLED": "false",
                "EMBEDDINGS_ENABLED": "false",
                "OCR_ENABLED": "false",
                "OMP_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
            }
            env_args = [arg for key in values for arg in ["--env", key]]
            # Mark owned container name before run so an interrupted startup can be cleaned up.
            started = True
            docker(
                "run",
                "-d",
                "--name",
                container,
                "--network",
                network,
                "--memory=512m",
                "--cpus=0.1",
                "--pids-limit=128",
                "--read-only",
                "--tmpfs",
                "/tmp:size=64m",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                "-p",
                "127.0.0.1::10000",
                *env_args,
                "documind-render-demo:local",
                env={**os.environ, **values},
            )
            port = docker("port", container, "10000/tcp").split(":")[-1]
            base = "http://127.0.0.1:" + port
            deadline = time.monotonic() + 150
            while True:
                try:
                    if (
                        httpx.get(base + "/api/v1/health/ready", timeout=3).status_code
                        == 200
                    ):
                        break
                except httpx.HTTPError:
                    pass
                if time.monotonic() > deadline:
                    raise RuntimeError(
                        "Candidate startup failed under the configured resource cap"
                    )
                time.sleep(1)
            with httpx.Client(
                base_url=base, headers={"Origin": "http://localhost:3000"}, timeout=30
            ) as client:
                token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
                assert (
                    client.post(
                        "/api/v1/demo/enter", headers={"X-CSRF-Token": token}
                    ).status_code
                    == 200
                )
                root = f"/api/v1/organizations/{ORG}"
                documents = client.get(root + "/documents").json()["items"]
                assert len(documents) == 6
                for document in documents:
                    assert (
                        client.get(
                            root + f"/documents/{document['id']}/download"
                        ).status_code
                        == 200
                    )
                for path in [
                    "/structured/runs",
                    "/operations/summary",
                    "/operations/export?format=csv",
                ]:
                    assert client.get(root + path).status_code == 200
                assert (
                    client.post(root + "/documents", content=b"not allowed").status_code
                    == 403
                )
            peak = int(docker("exec", container, "cat", "/sys/fs/cgroup/memory.peak"))
            state = json.loads(
                docker("inspect", "--format", "{{json .State}}", container)
            )
            assert not state["OOMKilled"] and peak < 512 * 1024**2
            output = ROOT / "deploy/render/verification"
            output.mkdir(exist_ok=True)
            report = {
                "local_only": True,
                "limit_bytes": 512 * 1024**2,
                "peak_bytes": peak,
                "cpu_limit": 0.1,
                "oom_killed": False,
                "documents": 6,
                "record_hash": digest,
                "tls": "Local HTTP only; platform TLS and pooler remain untested",
            }
            (output / "memory-check.json").write_text(json.dumps(report, indent=2))
            print(
                f"Local resource-capped check passed. Peak: {peak / 1024**2:.1f} MiB / 512 MiB."
            )
        finally:
            if started:
                docker("rm", "-f", container)
            if created:
                admin.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                        sql.Identifier(name)
                    )
                )


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - never emit an operator database URL in a traceback
        raise SystemExit(
            "Local candidate verification failed; no cloud connection attempted. "
            "Check Docker, the isolated inputs and candidate configuration."
        ) from None
