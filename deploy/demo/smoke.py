"""Verify ONLY the local demo; never disables TLS verification or contacts an LLM."""

import json
import ssl
import subprocess
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
ORG = "d09a0000-0000-4000-8000-000000000001"
COMPOSE = [
    "docker",
    "compose",
    "-f",
    "compose.demo.yaml",
    "--env-file",
    "deploy/demo/.env.local",
]


def database_check():
    statement = """SELECT
      has_table_privilege('documind_demo_app', 'documents', 'SELECT'),
      has_table_privilege('documind_demo_app', 'documents', 'INSERT'),
      has_table_privilege('documind_demo_app', 'analysis_items', 'UPDATE'),
      has_table_privilege('documind_demo_app', 'auth_sessions', 'INSERT'),
      has_table_privilege('documind_demo_app', 'refresh_tokens', 'UPDATE'),
      (SELECT count(*) FROM provider_requests),
      (SELECT count(*) FROM document_jobs WHERE state IN ('pending','running')),
      (SELECT count(*) FROM analysis_runs WHERE state IN ('pending','processing'))"""
    result = subprocess.run(
        COMPOSE
        + [
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "documind_demo_admin",
            "-d",
            "documind_demo",
            "-Atc",
            statement,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "t|f|f|t|t|0|0|0", (
        "Database demo permissions/job state failed"
    )


def main():
    certificate = ROOT / "deploy/demo/certs/fullchain.pem"
    tls = ssl.create_default_context(cafile=str(certificate))
    report = {"local_only": True, "tls_verified": True, "paid_calls": 0, "checks": []}
    with httpx.Client(
        base_url="https://localhost:8448",
        verify=tls,
        headers={"Origin": "https://localhost:8448"},
        timeout=20,
    ) as client:

        def mutate(path, method="POST"):
            csrf = client.get("/api/backend/auth/csrf").json()["csrf_token"]
            return client.request(
                method, "/api/backend" + path, headers={"X-CSRF-Token": csrf}, json={}
            )

        assert client.get("/api/backend/health/ready").status_code == 200
        login = client.get("/login")
        assert "Explore the demo" in login.text
        assert client.post("/api/backend/demo/enter").status_code == 403
        entered = mutate("/demo/enter")
        assert entered.status_code == 200, "Demo entry failed"
        for cookie in entered.headers.get_list("set-cookie"):
            assert (
                "Secure" in cookie and "HttpOnly" in cookie and "Domain=" not in cookie
            )
        assert client.get("/dashboard").status_code == 200
        report["checks"].append("HTTPS, SSR guard, CSRF, secure cookies and entry")
        base = f"/organizations/{ORG}"
        docs = client.get("/api/backend" + base + "/documents").json()["items"]
        assert len(docs) == 6
        for document in docs:
            response = client.get(
                "/api/backend" + base + f"/documents/{document['id']}/download"
            )
            assert response.status_code == 200 and response.content
        report["checks"].append("Six authorized original sample downloads")
        conversations = client.get(
            "/api/backend" + base + "/intelligence/conversations"
        ).json()
        history = client.get(
            "/api/backend"
            + base
            + f"/intelligence/conversations/{conversations[0]['id']}/messages"
        ).json()
        assert history[0]["is_mock"] and history[0]["citations"]
        report["checks"].append("Stored mock answer with live-validated citations")
        for path in [
            "/structured/runs",
            "/structured/obligations",
            "/operations/summary",
            "/operations/items",
            "/operations/activity",
            "/operations/export?format=csv",
        ]:
            assert client.get("/api/backend" + base + path).status_code == 200
        for path, method in [
            ("/auth/register", "POST"),
            ("/auth/login", "POST"),
            (base + "/documents", "POST"),
            (base + "/intelligence/search", "POST"),
            (base + "/structured/runs", "POST"),
            (base + f"/documents/{docs[0]['id']}", "DELETE"),
        ]:
            assert mutate(path, method).status_code == 403, path
        report["checks"].append(
            "Business reads/exports allowed; writes and expensive operations denied"
        )
        assert mutate("/auth/logout").status_code == 204
        assert client.get("/api/backend/auth/me").status_code == 401
    database_check()
    report["checks"].append(
        "Least-privilege role; zero provider requests/unfinished jobs; logout"
    )
    output = ROOT / "deploy/demo/verification"
    output.mkdir(exist_ok=True)
    (output / "http-smoke.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(
        "Local HTTPS demo smoke checks passed; no credentials or source contents printed."
    )


if __name__ == "__main__":
    main()
