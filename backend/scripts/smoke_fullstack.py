"""Exercise the production Next.js build and FastAPI over real HTTP.

Requires npm run build in frontend and free ports 3001/8001. All test users
and organizations live in a newly created temporary database, never the dev DB.
"""

import os
import secrets
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import jwt
import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"
sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402

ORIGIN = "http://localhost:3001"


def wait_for(url: str, process: subprocess.Popen):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Test server exited during startup")
        try:
            if httpx.get(url, timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise RuntimeError("Test server did not become ready")


def mutate(client: httpx.Client, path: str, data=None, method="POST"):
    token = client.get("/api/backend/auth/csrf")
    assert token.status_code == 200
    return client.request(
        method,
        "/api/backend" + path,
        json=data,
        headers={"X-CSRF-Token": token.json()["csrf_token"]},
    )


def exercise(secret: str):
    password = secrets.token_urlsafe(24)
    with (
        httpx.Client(base_url=ORIGIN, headers={"Origin": ORIGIN}, timeout=15) as alice,
        httpx.Client(base_url=ORIGIN, headers={"Origin": ORIGIN}, timeout=15) as bob,
    ):
        assert alice.get("/").status_code == 200
        assert alice.get("/signup").status_code == 200
        assert alice.get("/login").status_code == 200
        guard = alice.get("/dashboard")
        assert guard.status_code == 307 and guard.headers["location"] == "/login"
        for client, name in [(alice, "Alice"), (bob, "Bob")]:
            response = mutate(
                client,
                "/auth/register",
                {
                    "name": name,
                    "email": f"{name.lower()}@example.com",
                    "password": password,
                },
            )
            assert response.status_code == 201
            assert len(response.headers.get_list("set-cookie")) == 3
            for cookie in response.headers.get_list("set-cookie"):
                assert "HttpOnly" in cookie and "SameSite=lax" in cookie
        assert "Welcome" in alice.get("/dashboard").text
        a = mutate(alice, "/organizations", {"name": "Smoke A"}).json()["id"]
        b = mutate(bob, "/organizations", {"name": "Smoke B"}).json()["id"]
        assert (
            mutate(
                alice,
                f"/organizations/{a}/members",
                {
                    "email": "bob@example.com",
                    "role": "member",
                },
            ).status_code
            == 201
        )
        assert alice.get(f"/api/backend/organizations/{b}").status_code == 404
        assert (
            mutate(
                bob,
                f"/organizations/{a}/members",
                {
                    "email": "alice@example.com",
                    "role": "admin",
                },
            ).status_code
            == 403
        )
        assert len(bob.get("/api/backend/organizations").json()) == 2
        assert alice.post("/api/backend/auth/logout").status_code == 403
        print("HTTP smoke: signup, server guard, cookie proxy, CSRF, multi-org isolation passed.")

        refresh = alice.cookies.get("dm_refresh")
        claims = jwt.decode(alice.cookies["dm_access"], options={"verify_signature": False})
        claims["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        for cookie in list(alice.cookies.jar):
            if cookie.name == "dm_access":
                alice.cookies.set(
                    cookie.name,
                    jwt.encode(claims, secret, algorithm="HS256"),
                    domain=cookie.domain,
                    path=cookie.path,
                )
        expired = alice.get("/dashboard")
        assert expired.status_code == 307 and expired.headers["location"] == "/session"
        assert mutate(alice, "/auth/refresh").status_code == 200
        assert alice.cookies.get("dm_refresh") != refresh
        assert alice.get("/dashboard").status_code == 200
        with httpx.Client(base_url=ORIGIN, headers={"Origin": ORIGIN}, timeout=15) as replay:
            replay.cookies.set("dm_refresh", refresh)
            assert mutate(replay, "/auth/refresh").status_code == 401
        assert alice.get("/api/backend/auth/me").status_code == 401
        assert (
            mutate(
                alice,
                "/auth/login",
                {
                    "email": "alice@example.com",
                    "password": password,
                },
            ).status_code
            == 200
        )
        assert mutate(alice, "/auth/logout").status_code == 204
        assert alice.get("/dashboard").headers["location"] == "/login"
        print("HTTP smoke: expired SSR guard, refresh rotation/replay, login and logout passed.")


def main() -> int:
    for port in (3001, 8001):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(f"Port {port} must be free; no existing servers will be stopped")
    url = make_url(str(get_settings().database_url))
    database = "documind_test_" + uuid.uuid4().hex
    processes = []
    secret = secrets.token_urlsafe(48)
    with psycopg.connect(
        host=url.host,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        dbname=url.database,
        autocommit=True,
        connect_timeout=5,
    ) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        env = os.environ.copy()
        test_url = url.set(
            database=database, host="127.0.0.1" if url.host == "localhost" else url.host
        )
        env.update(
            DATABASE_URL=test_url.render_as_string(hide_password=False),
            AUTH_SECRET=secret,
            ENVIRONMENT="development",
            COOKIE_SECURE="false",
            CORS_ORIGINS='["http://localhost:3001"]',
            BACKEND_URL="http://127.0.0.1:8001",
        )
        try:
            subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=BACKEND,
                env=env,
                check=True,
            )
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            for command, cwd in [
                (
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "app.main:create_app",
                        "--factory",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8001",
                    ],
                    BACKEND,
                ),
                (["node", "node_modules/next/dist/bin/next", "start", "-p", "3001"], FRONTEND),
            ]:
                processes.append(
                    subprocess.Popen(
                        command,
                        cwd=cwd,
                        env=env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=flags,
                    )
                )
            wait_for("http://127.0.0.1:8001/api/v1/health/ready", processes[0])
            wait_for(ORIGIN, processes[1])
            exercise(secret)
            return 0
        finally:
            for process in reversed(processes):
                if os.name == "nt":
                    # The venv launcher has a child interpreter on Windows.
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True
                    )
                else:
                    process.terminate()
                process.wait(timeout=10)
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))
            print("Removed smoke-test servers and their temporary database; dev data untouched.")


if __name__ == "__main__":
    raise SystemExit(main())
