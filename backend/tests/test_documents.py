import io
import subprocess
import uuid
import zipfile
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import now
from app.documents.chunking import chunk_text
from app.documents.extraction import ExtractionError, extract
from app.documents.storage import LocalStorage
from app.documents.validation import MIME_TYPES, InvalidDocument, safe_filename, validate_file
from app.documents.worker import claim_job, extract_in_process, publish, run_once
from app.models import Document, DocumentChunk, DocumentJob, DocumentSection


def mutate(client, path, data=None, method="POST", files=None):
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return client.request(
        method,
        "/api/v1" + path,
        headers={"X-CSRF-Token": csrf},
        **({"files": files} if files else {"json": data}),
    )


def account(client, name="Alice"):
    response = mutate(
        client,
        "/auth/register",
        {
            "name": name,
            "email": f"{name.lower()}@example.com",
            "password": "document tests secure passphrase",
        },
    )
    assert response.status_code == 201
    return response.json()


def organization(client, name="Research"):
    response = mutate(client, "/organizations", {"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def upload(client, org, data=b"Useful source text. " * 200, filename="notes.txt", mime=None):
    mime = mime or MIME_TYPES.get(filename.rsplit(".", 1)[-1], "application/octet-stream")
    return mutate(client, f"/organizations/{org}/documents", files={"file": (filename, data, mime)})


def fixture_bytes(format):
    if format == "pdf":
        import pymupdf

        with pymupdf.open() as document:
            for text in ["First page source text", "Second page source text"]:
                document.new_page().insert_text((40, 40), text)
            return document.tobytes()
    if format == "docx":
        from docx import Document as WordDocument

        document = WordDocument()
        document.add_heading("Research overview", 1)
        document.add_paragraph("Useful paragraph content. " * 50)
        table = document.add_table(rows=1, cols=2)
        table.cell(0, 0).text, table.cell(0, 1).text = "Metric", "Revenue"
        stream = io.BytesIO()
        document.save(stream)
        return stream.getvalue()
    return b"Useful source text. " * 200


@pytest.mark.parametrize("format", ["pdf", "docx", "txt"])
def test_upload_process_download_sources_and_chunks(clients, identity_db, format):
    client = clients()
    account(client)
    org = organization(client)
    raw = fixture_bytes(format)
    response = upload(client, org, raw, f"source.{format}")
    assert response.status_code == 202, response.text
    doc = response.json()
    assert doc["status"] == "pending" and doc["size_bytes"] == len(raw)
    assert "storage_path" not in doc and "storage_key" not in doc
    base = f"/api/v1/organizations/{org}/documents/{doc['id']}"
    assert client.get(base + "/content").json()["sections"] == []
    assert run_once(identity_db, client.app.state.settings)
    details = client.get(base).json()
    assert details["status"] == "completed", details
    assert details["chunk_count"] > 0 and details["section_count"] > 0
    sources = client.get(base + "/content").json()["sections"]
    if format == "pdf":
        assert [section["page_number"] for section in sources] == [1, 2]
    else:
        assert all(section["page_number"] is None for section in sources)
    if format == "docx":
        assert "Revenue" in "".join(section["text"] for section in sources)
    downloaded = client.get(base + "/download")
    assert downloaded.status_code == 200 and downloaded.content == raw
    assert "attachment" in downloaded.headers["content-disposition"]
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    with Session(identity_db) as db:
        for chunk in db.scalars(select(DocumentChunk)):
            source = db.get(DocumentSection, chunk.section_id)
            assert source.text[chunk.start_offset : chunk.end_offset] == chunk.text
            assert str(chunk.organization_id) == org
            assert source.document_id == chunk.document_id


@pytest.mark.parametrize(
    "filename,raw,mime",
    [
        ("script.exe", b"MZ executable", "application/octet-stream"),
        ("fake.pdf", b"<html>not a PDF</html>", "application/pdf"),
        ("bad.docx", b"not a zip", MIME_TYPES["docx"]),
        ("binary.txt", b"\x00\x01binary", "text/plain"),
        ("empty.txt", b"", "text/plain"),
        ("fake.txt", b"text", "image/png"),
    ],
)
def test_invalid_uploads_are_rejected_without_storage(clients, identity_db, filename, raw, mime):
    client = clients()
    account(client)
    org = organization(client)
    assert upload(client, org, raw, filename, mime).status_code == 422
    with Session(identity_db) as db:
        assert db.scalar(select(func.count()).select_from(Document)) == 0
    assert not client.app.state.settings.storage_path.exists()


def test_configurable_file_limit_and_body_limit(clients):
    client = clients(upload_max_bytes=1024)
    account(client)
    org = organization(client)
    assert (
        client.get(f"/api/v1/organizations/{org}/documents/config").json()["upload_max_bytes"]
        == 1024
    )
    assert upload(client, org, b"x" * 2048).status_code == 413
    assert upload(client, org, b"x" * 70000).status_code == 413


def test_cross_org_all_endpoints_and_owner_admin_policy(clients, identity_db):
    admin, owner, peer, outsider = clients(), clients(), clients(), clients()
    account(admin)
    owner_user = account(owner, "Bob")
    account(peer, "Carol")
    account(outsider, "Dan")
    org = organization(admin)
    other = organization(outsider, "Other")
    for email in ["bob@example.com", "carol@example.com"]:
        assert (
            mutate(
                admin, f"/organizations/{org}/members", {"email": email, "role": "member"}
            ).status_code
            == 201
        )
    doc = upload(owner, org).json()
    path = f"/organizations/{org}/documents/{doc['id']}"
    for suffix in ["", "/content", "/download"]:
        assert outsider.get("/api/v1" + path + suffix).status_code == 404
        assert (
            outsider.get(
                f"/api/v1/organizations/{other}/documents/{doc['id']}" + suffix
            ).status_code
            == 404
        )
    assert outsider.get(f"/api/v1/organizations/{org}/documents").status_code == 404
    assert outsider.get(f"/api/v1/organizations/{org}/documents/config").status_code == 404
    assert upload(outsider, org).status_code == 404
    for client in [outsider, peer]:
        expected = 404 if client is outsider else 403
        assert mutate(client, path, method="DELETE").status_code == expected
        assert mutate(client, path + "/retry").status_code == expected
    assert peer.get("/api/v1" + path + "/download").status_code == 200
    assert (
        mutate(
            admin, f"/organizations/{org}/members/{owner_user['id']}", method="DELETE"
        ).status_code
        == 204
    )
    assert owner.get("/api/v1" + path).status_code == 404
    assert mutate(admin, path, method="DELETE").status_code == 202
    assert run_once(identity_db, admin.app.state.settings)


def test_failed_extraction_retry_and_no_partial_results(clients, identity_db):
    client = clients()
    account(client)
    org = organization(client)
    doc = upload(client, org, b"%PDF-1.7\ncorrupt content", "broken.pdf").json()
    assert run_once(identity_db, client.app.state.settings)
    path = f"/organizations/{org}/documents/{doc['id']}"
    response = client.get("/api/v1" + path).json()
    assert response["status"] == "failed" and response["error"]
    assert str(client.app.state.settings.storage_path) not in response["error"]
    assert response["chunk_count"] == 0
    assert mutate(client, path + "/retry").status_code == 202
    assert client.get("/api/v1" + path).json()["status"] == "pending"
    assert run_once(identity_db, client.app.state.settings)
    assert client.get("/api/v1" + path).json()["status"] == "failed"


def test_deletion_removes_original_and_cascades_extracted_data(clients, identity_db):
    client = clients()
    account(client)
    org = organization(client)
    doc = upload(client, org, filename="../../CON.txt").json()
    assert doc["filename"] == "_CON.txt"
    assert run_once(identity_db, client.app.state.settings)
    path = f"/organizations/{org}/documents/{doc['id']}"
    storage = LocalStorage(client.app.state.settings.storage_path)
    assert storage.path(uuid.UUID(org), uuid.UUID(doc["id"])).exists()
    assert mutate(client, path, method="DELETE").status_code == 202
    for suffix in ["", "/content", "/download"]:
        assert client.get("/api/v1" + path + suffix).status_code == 404
    assert run_once(identity_db, client.app.state.settings)
    assert not storage.path(uuid.UUID(org), uuid.UUID(doc["id"])).exists()
    with Session(identity_db) as db:
        for model in [Document, DocumentSection, DocumentChunk, DocumentJob]:
            assert db.scalar(select(func.count()).select_from(model)) == 0


def test_delete_during_processing_fences_stale_worker(clients, identity_db):
    client = clients()
    account(client)
    org = organization(client)
    doc = upload(client, org).json()
    settings = client.app.state.settings
    claim = claim_job(identity_db, settings)
    assert (
        client.get(f"/api/v1/organizations/{org}/documents/{doc['id']}").json()["status"]
        == "processing"
    )
    result = extract_in_process(LocalStorage(settings.storage_path), claim, settings)
    assert (
        mutate(client, f"/organizations/{org}/documents/{doc['id']}", method="DELETE").status_code
        == 202
    )
    assert not publish(identity_db, claim, result, settings)
    assert run_once(identity_db, settings)
    assert not publish(identity_db, claim, result, settings)


def test_restart_recovery_and_attempt_limit(clients, identity_db):
    client = clients()
    account(client)
    org = organization(client)
    doc = upload(client, org).json()
    settings = client.app.state.settings
    old = claim_job(identity_db, settings)
    with Session(identity_db) as db:
        job = db.scalar(select(DocumentJob))
        job.lease_until = now() - timedelta(seconds=1)
        db.commit()
    assert run_once(identity_db, settings)
    assert (
        client.get(f"/api/v1/organizations/{org}/documents/{doc['id']}").json()["status"]
        == "completed"
    )
    assert not publish(identity_db, old, {"sections": []}, settings)


def test_timeout_and_retry_budget_are_bounded(clients, identity_db):
    client = clients()
    account(client)
    org = organization(client)
    doc = upload(client, org).json()

    def timeout(*args):
        raise subprocess.TimeoutExpired("parser", 1)

    assert run_once(identity_db, client.app.state.settings, extractor=timeout)
    path = f"/organizations/{org}/documents/{doc['id']}"
    assert "time limit" in client.get("/api/v1" + path).json()["error"]
    assert mutate(client, path + "/retry").status_code == 202
    claim_job(identity_db, client.app.state.settings)
    with Session(identity_db) as db:
        job = db.scalar(select(DocumentJob))
        job.attempts = client.app.state.settings.worker_max_attempts
        job.lease_until = now() - timedelta(seconds=1)
        db.commit()
    assert not run_once(identity_db, client.app.state.settings)
    assert client.get("/api/v1" + path).json()["status"] == "failed"


def test_cleanup_storage_failure_retries_and_hides_document(clients, identity_db, monkeypatch):
    client = clients()
    account(client)
    org = organization(client)
    doc = upload(client, org).json()
    path = f"/organizations/{org}/documents/{doc['id']}"
    assert mutate(client, path, method="DELETE").status_code == 202
    original = LocalStorage.delete
    monkeypatch.setattr(
        LocalStorage, "delete", lambda *args: (_ for _ in ()).throw(PermissionError())
    )
    assert run_once(identity_db, client.app.state.settings)
    assert client.get("/api/v1" + path).status_code == 404
    with Session(identity_db) as db:
        job = db.scalar(select(DocumentJob))
        assert job.state == "pending" and job.last_error
        job.available_at = now()
        db.commit()
    monkeypatch.setattr(LocalStorage, "delete", original)
    assert run_once(identity_db, client.app.state.settings)


def test_library_search_filters_and_literal_wildcards(clients, identity_db):
    client = clients()
    account(client)
    org = organization(client)
    upload(client, org, filename="Report_100%.txt")
    upload(client, org, filename="Other.txt")
    base = f"/api/v1/organizations/{org}/documents"
    assert client.get(base + "?q=report").json()["total"] == 1
    assert client.get(base + "?q=%25").json()["total"] == 1
    assert client.get(base + "?format=pdf").json()["total"] == 0
    assert client.get(base + "?status=pending&page_size=1").json()["total"] == 2
    assert len(client.get(base + "?page=2&page_size=1").json()["items"]) == 1
    assert run_once(identity_db, client.app.state.settings)
    assert client.get(base + "?status=completed").json()["total"] == 1


def test_composite_foreign_keys_prevent_cross_org_source_rows(clients, identity_db):
    client = clients()
    account(client)
    org_a, org_b = organization(client, "A"), organization(client, "B")
    doc = upload(client, org_a).json()
    with Session(identity_db) as db:
        db.add(
            DocumentSection(
                document_id=uuid.UUID(doc["id"]),
                organization_id=uuid.UUID(org_b),
                ordinal=0,
                label="Forged",
                text="No access",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_chunk_offsets_overlap_and_invalid_settings():
    chunks = list(chunk_text("abcdefghij", 5, 2))
    assert chunks == [(0, 5, "abcde"), (3, 8, "defgh"), (6, 10, "ghij")]
    with pytest.raises(ValueError):
        list(chunk_text("text", 5, 5))


def test_docx_archive_limits_and_text_encoding(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@localhost/test",
        docx_max_uncompressed_bytes=1024,
    )
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "x")
        z.writestr("word/document.xml", "a" * 2048)
    archive.seek(0)
    with pytest.raises(InvalidDocument):
        validate_file(archive, "docx", MIME_TYPES["docx"], settings)
    path = tmp_path / "encoded.txt"
    path.write_bytes("Unicode source: café".encode("utf-16"))
    assert "café" in extract(path, "txt", settings)["sections"][0]["text"]
    path.write_text(" ", encoding="utf-8")
    with pytest.raises(ExtractionError):
        extract(path, "txt", settings)
    assert safe_filename("C:\\private\\name.PDF") == ("name.pdf", "pdf")


def test_incomplete_upload_reservation_is_reclaimed(clients, identity_db):
    client = clients()
    account(client)
    org = organization(client)
    doc = upload(client, org).json()
    with Session(identity_db) as db:
        record = db.get(Document, uuid.UUID(doc["id"]))
        record.storage_ready = False
        db.commit()
    assert run_once(identity_db, client.app.state.settings)
    path = f"/api/v1/organizations/{org}/documents/{doc['id']}"
    assert "interrupted" in client.get(path).json()["error"]
    assert (
        not LocalStorage(client.app.state.settings.storage_path)
        .path(uuid.UUID(org), uuid.UUID(doc["id"]))
        .exists()
    )


def test_chunk_limit_rolls_back_and_retry_uses_new_configuration(clients, identity_db):
    client = clients(chunk_size=100, chunk_overlap=99, processing_max_chunks=100)
    account(client)
    org = organization(client)
    doc = upload(client, org, b"x" * 1000).json()
    settings = client.app.state.settings
    assert run_once(identity_db, settings)
    path = f"/organizations/{org}/documents/{doc['id']}"
    assert client.get("/api/v1" + path).json()["status"] == "failed"
    with Session(identity_db) as db:
        assert db.scalar(select(func.count()).select_from(DocumentSection)) == 0
        assert db.scalar(select(func.count()).select_from(DocumentChunk)) == 0
    settings.chunk_overlap = 0
    assert mutate(client, path + "/retry").status_code == 202
    assert run_once(identity_db, settings)
    assert client.get("/api/v1" + path).json()["status"] == "completed"


def test_upload_storage_failure_keeps_durable_cleanup(clients, identity_db, monkeypatch):
    client = clients()
    account(client)
    org = organization(client)

    def unavailable(*args):
        raise PermissionError("private storage path")

    monkeypatch.setattr(LocalStorage, "save", unavailable)
    response = upload(client, org)
    assert response.status_code == 503 and "private storage path" not in response.text
    assert client.get(f"/api/v1/organizations/{org}/documents").json()["total"] == 0
    assert run_once(identity_db, client.app.state.settings)
    with Session(identity_db) as db:
        assert db.scalar(select(func.count()).select_from(Document)) == 0


def test_multipart_upload_requires_csrf_and_streamed_body_limit(clients):
    client = clients(upload_max_bytes=1024)
    account(client)
    org = organization(client)
    path = f"/api/v1/organizations/{org}/documents"
    assert (
        client.post(path, files={"file": ("notes.txt", b"text", "text/plain")}).status_code == 403
    )
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    boundary = "documind-boundary"

    def chunks():
        yield (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            'filename="notes.txt"\r\nContent-Type: text/plain\r\n\r\n'
        ).encode()
        for _ in range(80):
            yield b"x" * 1024
        yield f"\r\n--{boundary}--\r\n".encode()

    response = client.post(
        path,
        content=chunks(),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-CSRF-Token": token,
        },
    )
    assert response.status_code == 413
