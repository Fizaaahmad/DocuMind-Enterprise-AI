"""Isolated local HTTPS deployment and recovery drill; never uses development volumes.

Build both production images first. Requires Docker Desktop and backend dev dependencies.
All generated credentials stay in the gitignored .production-smoke directory.
"""

import argparse
import importlib.util
import json
import secrets
import socket
import ssl
import subprocess
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("manage", ROOT / "deploy/manage.py")
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def prepare(directory):
    manage.initialize(directory)
    https, http = port(), port()
    origin = f"https://localhost:{https}"
    args = SimpleNamespace(
        file=ROOT / "compose.production.yaml",
        env_file=directory / ".env.production",
        project="documind-smoke-" + uuid.uuid4().hex[:12],
        directory=None,
        confirm_new_target=True,
    )
    config = json.loads(manage.compose(args, "config", "--format", "json", capture=True))
    for name, secret in config["secrets"].items():
        secret["file"] = str(directory / "secrets" / name)
    for group in ("volumes", "networks"):
        for name, entry in config[group].items():
            entry["name"] = args.project + "_" + name
    gateway = config["services"]["gateway"]
    gateway["environment"]["PUBLIC_ORIGIN"] = origin
    for binding in gateway["ports"]:
        binding["host_ip"] = "127.0.0.1"
        binding["published"] = str(https if binding["target"] == 443 else http)
    for volume in gateway["volumes"]:
        if volume["target"] == "/etc/nginx/certs":
            volume["source"] = str(directory / "certs")
    for name in ("api", "worker"):
        config["services"][name]["environment"]["CORS_ORIGINS"] = json.dumps([origin])
    config["name"] = args.project
    args.file = directory / "compose.json"
    args.file.write_text(json.dumps(config, indent=2), encoding="utf-8")
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--user",
            "0",
            "-v",
            f"{directory / 'certs'}:/certs",
            "documind-backend:local",
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "2",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost",
            "-keyout",
            "/certs/privkey.pem",
            "-out",
            "/certs/fullchain.pem",
        ],
        check=True,
        capture_output=True,
    )
    return args, origin, http, config


def wait(client):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            response = client.get("/api/backend/health/ready")
            if response.status_code == 200:
                assert response.json()["schema"] == "ok"
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError("Isolated HTTPS services did not become ready")


def client_for(args, origin):
    context = ssl.create_default_context(cafile=str(args.file.parent / "certs/fullchain.pem"))
    return httpx.Client(base_url=origin, verify=context, headers={"Origin": origin}, timeout=60)


def mutate(client, path, data=None, method="POST", files=None):
    csrf = client.get("/api/backend/auth/csrf")
    assert csrf.status_code == 200
    return client.request(
        method,
        "/api/backend" + path,
        headers={"X-CSRF-Token": csrf.json()["csrf_token"]},
        **({"files": files} if files else {"json": data}),
    )


def verify(args, origin, http, config):
    password = secrets.token_urlsafe(32)
    content = b"Private smoke evidence. Contract value: USD 50,000. Deadline: 2030-01-01."
    with client_for(args, origin) as alice, client_for(args, origin) as bob:
        wait(alice)
        response = alice.get("/")
        for header in ("strict-transport-security", "content-security-policy", "x-frame-options"):
            assert header in response.headers
        assert httpx.get(f"http://localhost:{http}/login").headers["location"] == origin + "/login"
        assert alice.get("/dashboard").status_code == 307
        assert alice.get("/api/v1/health").status_code == 404
        assert alice.post("/api/backend/auth/logout").status_code == 403
        for client, name in ((alice, "Alice"), (bob, "Bob")):
            response = mutate(
                client,
                "/auth/register",
                {
                    "name": name,
                    "email": f"{name.lower()}@example.com",
                    "password": password,
                },
            )
            assert response.status_code == 201, f"Registration HTTP {response.status_code}"
            for cookie in response.headers.get_list("set-cookie"):
                assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
                assert cookie.startswith("__Host-")
        org = mutate(alice, "/organizations", {"name": "Production smoke"}).json()["id"]
        assert bob.get(f"/api/backend/organizations/{org}/documents").status_code == 404
        response = mutate(
            alice,
            f"/organizations/{org}/documents",
            files={
                "file": ("contract.txt", content, "text/plain"),
            },
        )
        assert response.status_code == 202, f"Upload HTTP {response.status_code}"
        doc = response.json()["id"]
        path = f"/api/backend/organizations/{org}/documents/{doc}"
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            response = alice.get(path)
            if response.json()["status"] == "completed":
                break
            assert response.json()["status"] != "failed", "Worker extraction failed"
            time.sleep(1)
        assert response.json()["status"] == "completed"
        assert bob.get(path + "/download").status_code == 404
        assert alice.get(path + "/download").content == content
        assert (
            alice.get(f"/api/backend/organizations/{org}/operations/diagnostics").status_code == 200
        )
        for page in ("/dashboard", "/documents", "/assistant", "/intelligence", "/operations"):
            assert alice.get(page).status_code == 200, page
        assert mutate(alice, "/auth/refresh").status_code == 200
        for service in ("db", "api", "worker", "frontend"):
            assert not config["services"][service].get("ports")
        manage.compose(args, "stop", "worker")
        manage.compose(args, "start", "worker")
        manage.compose(
            args, "exec", "-T", "api", "python", "-m", "app.core.diagnostics", "dependencies"
        )
        # Runtime role cannot create tables; migrator remains a separate identity.
        manage.compose(
            args,
            "exec",
            "-T",
            "api",
            "python",
            "-c",
            "from app.core.config import get_settings; from app.db.session import build_engine; "
            "from sqlalchemy import text; e=build_engine(str(get_settings().database_url)); "
            'c=e.connect(); assert not c.scalar(text("SELECT '
            "has_schema_privilege(current_user, 'public', 'CREATE')\"))",
        )
        for _ in range(15):
            rate = alice.get("/api/backend/auth/login")
        assert rate.status_code == 429, "Gateway auth rate limit not enforced"
        manage.compose(
            args,
            "exec",
            "-T",
            "api",
            "python",
            "-c",
            "from app.core.config import get_settings\n"
            "from app.db.session import build_engine\n"
            "from sqlalchemy import text\n"
            "from sqlalchemy.exc import SQLAlchemyError\n"
            "e=build_engine(str(get_settings().database_url))\n"
            "try:\n"
            " with e.connect() as c:\n"
            "  c.execute(text('SELECT CAST(:value AS integer)'), "
            "{'value': 'private-sql-probe'})\n"
            "except SQLAlchemyError: pass\n",
        )
        logs = manage.compose(args, "logs", "--no-color", capture=True)
        forbidden = [
            password,
            content.decode(),
            *[p.read_text() for p in (args.file.parent / "secrets").iterdir()],
        ]
        forbidden.append("private-sql-probe")
        assert not any(value in logs for value in forbidden), "Sensitive data detected in logs"
        return password, org, doc, content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-recovery", action="store_true")
    options = parser.parse_args()
    directory = ROOT / ".production-smoke" / uuid.uuid4().hex
    projects = []
    try:
        args, origin, http, config = prepare(directory / "source")
        projects.append(args)
        manage.compose(args, "up", "-d", "--no-build", "gateway", "worker")
        password, org, doc, content = verify(args, origin, http, config)
        print(
            "PASS: HTTPS, cookies/CSRF, isolation, document workflow, pages, "
            "rate limits, private services, safe logs"
        )
        if not options.skip_recovery:
            args.directory = directory / "backup"
            manage.backup(args)
            recovered, recovered_origin, _, _ = prepare(directory / "recovered")
            projects.append(recovered)
            manage.compose(recovered, "up", "-d", "db")
            manage.compose(
                recovered,
                "exec",
                "-T",
                "db",
                "sh",
                "-c",
                "until pg_isready -U documind_admin -d documind; do sleep 1; done",
            )
            recovered.directory = args.directory
            manage.restore(recovered)
            manage.compose(recovered, "up", "-d", "--no-build", "gateway", "worker")
            with client_for(recovered, recovered_origin) as client:
                wait(client)
                assert (
                    mutate(
                        client, "/auth/login", {"email": "alice@example.com", "password": password}
                    ).status_code
                    == 200
                )
                assert (
                    client.get(f"/api/backend/organizations/{org}/documents/{doc}/download").content
                    == content
                )
            print(
                "PASS: consistent backup, fresh-volume restore, migrations "
                "and restored document download"
            )
    finally:
        # Only disposable projects generated above; no development/production volume names.
        for args in reversed(projects):
            manage.compose(args, "down", "--volumes", "--remove-orphans")
        print(
            "Disposable containers and volumes removed; "
            "private test files remain under .production-smoke"
        )


if __name__ == "__main__":
    main()
