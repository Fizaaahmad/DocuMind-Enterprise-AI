"""Capture the real app against an owned, disposable PostgreSQL database.

Run with backend/.venv/Scripts/python.exe portfolio/source/demo_capture.py.
No application files are changed; no external LLM requests are enabled.
"""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OUT = ROOT / "portfolio"
sys.path.insert(0, str(BACKEND))
os.environ.update(LLM_REAL_REQUESTS_ENABLED="false", LLM_PROVIDER="mock", LLM_API_KEY="")
import fitz
import httpx
import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url
from app.core.config import get_settings

def wait(predicate, seconds=300):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            value = predicate()
            if value:
                return value
        except httpx.HTTPError:
            pass
        time.sleep(.5)
    raise RuntimeError("Demo operation exceeded its bounded wait")

def main():
    for port in (3004, 8004):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(f"Demo port {port} is occupied; no existing server was stopped")
    for directory in ("screenshots", "source/demo-documents", "verification", "content", "architecture", "case-study", "carousel/png"):
        (OUT / directory).mkdir(parents=True, exist_ok=True)
    url = make_url(str(get_settings().database_url))
    database = "documind_portfolio_" + uuid.uuid4().hex
    processes = []
    with tempfile.TemporaryDirectory(prefix="documind-portfolio-") as storage, psycopg.connect(
        host="127.0.0.1" if url.host == "localhost" else url.host, port=url.port or 5432, user=url.username, password=url.password,
        dbname=url.database, autocommit=True, connect_timeout=5
    ) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        try:
            env = os.environ.copy()
            env.update(DATABASE_URL=url.set(database=database, host="127.0.0.1" if url.host == "localhost" else url.host).render_as_string(hide_password=False),
                AUTH_SECRET=secrets.token_urlsafe(48), ENVIRONMENT="development", COOKIE_SECURE="false",
                CORS_ORIGINS='["http://127.0.0.1:3004"]', BACKEND_URL="http://127.0.0.1:8004",
                STORAGE_PATH=storage, WORKER_POLL_SECONDS="0.1", EMBEDDINGS_ENABLED="true",
                RETRIEVAL_MIN_SIMILARITY="0.1", HF_HUB_OFFLINE="1", OCR_ENABLED="false",
                LLM_PROVIDER="mock", LLM_MODEL="extractive-mock-v1", LLM_REAL_REQUESTS_ENABLED="false", LLM_API_KEY="",
                OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2")
            subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True, stdout=subprocess.DEVNULL)
            subprocess.run([sys.executable, "-m", "alembic", "check"], cwd=BACKEND, env=env, check=True, stdout=subprocess.DEVNULL)
            for command, cwd in [
                ([sys.executable, "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "127.0.0.1", "--port", "8004"], BACKEND),
                (["node", "node_modules/next/dist/bin/next", "start", "-p", "3004", "-H", "127.0.0.1"], ROOT / "frontend"),
                ([sys.executable, "-m", "app.documents.worker"], BACKEND),
            ]:
                processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
            origin = "http://127.0.0.1:3004"
            wait(lambda: httpx.get(origin, timeout=5).status_code == 200, 60)
            wait(lambda: httpx.get("http://127.0.0.1:8004/api/v1/health/ready", timeout=5).status_code == 200, 60)
            with httpx.Client(base_url=origin, headers={"Origin": origin}, timeout=180) as client:
                def mutate(path, data, method="POST"):
                    csrf = client.get("/api/backend/auth/csrf").json()["csrf_token"]
                    r = client.request(method, "/api/backend" + path, json=data, headers={"X-CSRF-Token": csrf})
                    if r.status_code >= 400:
                        raise RuntimeError(f"Demo API {path}: {r.status_code} {r.text[:200]}")
                    return r.json() if r.content else None
                mutate("/auth/register", {"name": "Alex Morgan", "email": "alex@northstar.example", "password": secrets.token_urlsafe(32)})
                org = mutate("/organizations", {"name": "Northstar Research · Demo"})["id"]
                base = f"/organizations/{org}"
                first = """FICTIONAL PORTFOLIO DEMONSTRATION — NOT A REAL CONTRACT
MASTER SERVICES AGREEMENT
Customer: Northstar Research
Supplier: Meridian Systems
Contract value: USD 50,000
Effective date: 2026-01-15
Renewal date: 2027-01-15
The annual service fee is USD 50,000, payable within 30 days of invoice.
Meridian Systems shall deliver a security assessment by 2026-10-30.
Meridian Systems must provide quarterly security reviews by 2026-12-15.
Northstar Research shall appoint a service owner by 2026-12-01.
The supplier must notify the customer of material security incidents within 48 hours.
Payment terms: Net 30 days. No automatic renewal applies.
Termination requires 60 days written notice. Liability is capped at annual fees.
All extracted commitments and rule matches require human review.
"""
                second = first.replace("50,000", "65,000").replace("30 days of invoice", "15 days of invoice").replace("48 hours", "24 hours").replace("60 days written notice", "30 days written notice")
                sources = [
                    ("Master Services Agreement.pdf", first),
                    ("Master Services Agreement — proposed revision.pdf", second),
                    ("Security Review Schedule.pdf", "FICTIONAL DEMO\nSECURITY REVIEW SCHEDULE\nOwner: Meridian Systems\nMeridian Systems shall deliver a security assessment by 2026-12-15.\nSecurity reviews include access controls, incident response and recovery exercises."),
                    ("Data Processing Addendum.txt", "FICTIONAL DEMO\nDATA PROCESSING ADDENDUM\nSupplier: Meridian Systems\nThe processor must notify Northstar Research of a data incident within 24 hours.\nThe processor shall provide deletion confirmation by 2026-12-20."),
                    ("Supplier Governance Policy.txt", "FICTIONAL DEMO\nSUPPLIER GOVERNANCE POLICY\nSupplier owners must review open commitments before approving a contract renewal.\nHigh-value contracts require procurement review.\nReview candidates are not final legal conclusions."),
                    ("Procurement Approval Guide.txt", "FICTIONAL DEMO\nPROCUREMENT APPROVAL GUIDE\nContracts exceeding USD 40,000 require finance review.\nFinance must complete the annual portfolio assessment by 2026-12-31."),
                ]
                documents = []
                for name, text in sources:
                    path = OUT / "source/demo-documents" / name
                    if name.endswith(".pdf"):
                        pdf = fitz.open(); page = pdf.new_page()
                        page.insert_textbox(fitz.Rect(48, 45, 547, 795), text, fontsize=12, lineheight=1.65)
                        pdf.save(path); pdf.close(); mime = "application/pdf"
                    else:
                        path.write_text(text, encoding="utf-8"); mime = "text/plain"
                    csrf = client.get("/api/backend/auth/csrf").json()["csrf_token"]
                    r = client.post("/api/backend" + base + "/documents", files={"file": (name, path.read_bytes(), mime)}, headers={"X-CSRF-Token": csrf})
                    r.raise_for_status(); documents.append(r.json()["id"])
                print("Fictional source documents uploaded through actual APIs.", flush=True)
                for doc in documents:
                    def indexed():
                        status = client.get("/api/backend" + base + "/intelligence/status").json()
                        record = next(item for item in status["documents"] if item["id"] == doc)
                        if record.get("status") == "failed" or record.get("index_status") == "failed":
                            raise RuntimeError("Demo processing/indexing failed: " + str(record.get("error") or record.get("index_error")))
                        return record if record.get("index_status") == "completed" else False
                    wait(indexed, 600)
                print("Actual worker extraction, local embeddings and pgvector indexing completed.", flush=True)
                template = mutate(base + "/structured/templates", {"name": "Commercial terms · Review checklist", "fields": [
                    {"name": "customer", "label": "Customer", "type": "text", "required": True},
                    {"name": "supplier", "label": "Supplier", "type": "text", "required": True},
                    {"name": "contract_value", "label": "Contract value", "type": "money", "required": True},
                    {"name": "effective_date", "label": "Effective date", "type": "date"},
                    {"name": "renewal_date", "label": "Renewal date", "type": "date"}], "rules": [
                        {"name": "Contract value exceeds review threshold", "type": "threshold", "field": "contract_value", "threshold": 40000, "severity": "medium"},
                        {"name": "Incident response commitment", "type": "contains", "term": "security incidents", "severity": "low"}], "obligations": True})
                def analysis(data):
                    run = mutate(base + "/structured/runs", data)["id"]
                    def finished():
                        result = client.get("/api/backend" + base + f"/structured/runs/{run}").json()
                        if result["run"]["state"] == "failed": raise RuntimeError("Demo analysis failed")
                        return result if result["run"]["state"] == "completed" else False
                    return run, wait(finished, 150)
                extract_id, result = analysis({"document_id": documents[0], "template_id": template["id"], "engine": "deterministic"})
                compare_id, _ = analysis({"document_id": documents[0], "other_document_id": documents[1], "mode": "compare", "engine": "deterministic"})
                field = next(i for i in result["items"] if i["kind"] == "field" and i["name"] == "supplier")
                mutate(base + f"/structured/runs/{extract_id}/items/{field['id']}/review", {"version": 1, "action": "approve", "reason": "Fictional demo: verified against the source passage"})
                me = client.get("/api/backend/auth/me").json()
                obligation = next(i for i in result["items"] if i["kind"] == "obligation")
                mutate(base + f"/operations/items/{obligation['id']}/assignment", {"version": obligation["version"], "assignee_id": me["id"], "due_date": "2026-12-01"}, "PATCH")
                conversation = mutate(base + "/intelligence/conversations", {})["id"]
                answer = mutate(base + f"/intelligence/conversations/{conversation}/messages", {"question": "What are the service fees and supplier obligations?", "document_ids": [documents[0]]})
                if not answer["is_mock"] or not answer["citations"]: raise RuntimeError("Mock answer did not return validated evidence")
                summary = client.get("/api/backend" + base + "/operations/summary?engine=all").json()
                provenance = {"environment": "isolated actual Next.js + FastAPI + PostgreSQL + worker", "fictional_data": True,
                    "provider": "mock", "paid_api_calls_during_portfolio_capture": 0, "embeddings": "actual locally cached Sentence Transformer",
                    "migration_check": "passed on disposable database", "document_count": len(documents),
                    "answer_citations": len(answer["citations"]), "analysis_items": len(result["items"]),
                    "test_evidence": "Prior recorded runs: 73 frontend passed; 155 backend passed, 1 optional skip. Not rerun for portfolio generation.",
                    "live_openai": "Fiza Ahmad completed a real paid local Q&A test; see live-openai-validation.json for the separate developer-supplied manual record. No paid request is made by this capture."}
                (OUT / "verification/capture-provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
                cookies = [{"name": c.name, "value": c.value, "domain": "127.0.0.1", "path": "/", "httpOnly": True, "sameSite": "Lax"} for c in client.cookies.jar]
                payload = {"cookies": cookies, "org": org, "extract": extract_id, "compare": compare_id, "conversation": conversation}
                subprocess.run(["node", str(OUT / "source/capture.mjs")], cwd=ROOT, input=json.dumps(payload), text=True, check=True)
                print("Actual application screenshots captured; all AI responses are labeled mock.", flush=True)
        finally:
            for process in reversed(processes):
                if os.name == "nt": subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
                else: process.terminate()
                process.wait(timeout=15)
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (database,))
            if not database.startswith("documind_portfolio_"): raise RuntimeError("Unexpected cleanup target")
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))
            print("Removed only the owned demo database and processes; existing data unchanged.", flush=True)

if __name__ == "__main__": main()
