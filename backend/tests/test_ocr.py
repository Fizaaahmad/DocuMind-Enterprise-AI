"""Synthetic raster PDFs plus deterministic Tesseract failures; real OCR is optional."""

import json
import os
import shutil
import subprocess
import sys

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import now
from app.documents import ocr
from app.documents.extraction import ExtractionError, extract
from app.documents.worker import claim_job, processing_timeout, run_once
from app.models import DocumentChunk, DocumentJob, DocumentSection


def settings(**overrides):
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@localhost/test",
        ocr_enabled=True,
        **overrides,
    )


def pdf_fixture(path, kinds):
    import pymupdf

    # Build a real rasterized text image using only the existing PyMuPDF dependency.
    with pymupdf.open() as source:
        page = source.new_page(width=600, height=240)
        page.insert_text((35, 75), "DOCUMIND SCANNED DOCUMENT", fontsize=22)
        page.insert_text((35, 120), "Revenue report number 12345", fontsize=22)
        image = page.get_pixmap(dpi=150).tobytes("png")
    with pymupdf.open() as document:
        for kind in kinds:
            page = document.new_page(width=600, height=240)
            if kind in {"scan", "scan-footer"}:
                page.insert_image(page.rect, stream=image)
                if kind == "scan-footer":
                    page.insert_text((5, 235), "1", fontsize=6)
            elif kind == "native":
                page.insert_text(
                    (30, 70), "Normal native document text remains unchanged.", fontsize=18
                )
            elif kind == "small":
                page.insert_text((30, 70), "Hi", fontsize=18)
            elif kind == "small-logo":
                page.insert_text((30, 70), "Q1", fontsize=18)
                page.insert_image(pymupdf.Rect(520, 5, 590, 30), stream=image)
            elif kind in {"white-image", "white-image-footer"}:
                pixmap = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 100, 100), False)
                pixmap.clear_with(255)
                page.insert_image(page.rect, stream=pixmap.tobytes("png"))
                if kind == "white-image-footer":
                    page.insert_text((5, 235), "1", fontsize=8)
            elif kind == "huge":
                page.set_mediabox(pymupdf.Rect(0, 0, 5000, 5000))
                page.insert_image(page.rect, stream=image)
        document.save(path)


@pytest.fixture
def fake_tesseract(monkeypatch):
    calls = []
    monkeypatch.setattr(ocr.shutil, "which", lambda _: "tesseract")

    def command(args, **kwargs):
        calls.append((args, kwargs))
        if "--list-langs" in args:
            return subprocess.CompletedProcess(args, 0, b"Available languages:\neng\n", b"")
        return subprocess.CompletedProcess(args, 0, b"Recognized scanned revenue 12345\n", b"")

    monkeypatch.setattr(ocr.subprocess, "run", command)
    return calls


def test_scanned_pdf_uses_ocr_and_preserves_real_page_numbers(tmp_path, fake_tesseract):
    path = tmp_path / "scanned.pdf"
    pdf_fixture(path, ["scan", "scan"])
    result = extract(path, "pdf", settings())
    assert [s["page_number"] for s in result["sections"]] == [1, 2]
    assert all("OCR" in s["label"] and "12345" in s["text"] for s in result["sections"])
    assert result["metadata"]["ocr_page_count"] == 2
    assert result["metadata"]["ocr_page_numbers"] == "1, 2"
    assert len(fake_tesseract) == 3  # One lazy language check, then two pages.
    for _, kwargs in fake_tesseract:
        assert kwargs["env"]["OMP_THREAD_LIMIT"] == "1"


def test_mixed_pdf_only_ocrs_scanned_pages(tmp_path, fake_tesseract):
    path = tmp_path / "mixed.pdf"
    pdf_fixture(path, ["native", "scan-footer", "small", "blank", "white-image", "small-logo"])
    result = extract(path, "pdf", settings())
    assert result["metadata"]["ocr_page_count"] == 1
    assert result["metadata"]["ocr_page_numbers"] == "2"
    assert "Normal native" in result["sections"][0]["text"]
    assert "native" in result["sections"][0]["label"]
    assert "OCR" in result["sections"][1]["label"]
    assert result["sections"][2]["text"].strip() == "Hi"
    assert result["sections"][5]["text"].strip() == "Q1"
    assert len(fake_tesseract) == 2


def test_native_small_and_blank_pages_need_no_tesseract(tmp_path, monkeypatch):
    path = tmp_path / "normal.pdf"
    pdf_fixture(
        path, ["native", "small", "blank", "white-image", "small-logo", "white-image-footer"]
    )

    def forbidden(*args):
        pytest.fail("Tesseract must not be checked or invoked for native/blank pages")

    monkeypatch.setattr(ocr.shutil, "which", forbidden)
    assert extract(path, "pdf", settings())["metadata"]["ocr_page_count"] == 0


def test_disabled_ocr_preserves_existing_scan_failure(tmp_path, monkeypatch):
    path = tmp_path / "scanned.pdf"
    pdf_fixture(path, ["scan"])
    monkeypatch.setattr(ocr.shutil, "which", lambda _: pytest.fail("OCR is disabled"))
    with pytest.raises(ExtractionError, match="not enabled"):
        extract(path, "pdf", settings().model_copy(update={"ocr_enabled": False}))


def test_missing_installation_has_actionable_error(tmp_path, monkeypatch):
    path = tmp_path / "scanned.pdf"
    pdf_fixture(path, ["scan"])
    monkeypatch.setattr(ocr.shutil, "which", lambda _: None)
    with pytest.raises(ocr.OCRError, match="TESSERACT_CMD"):
        extract(path, "pdf", settings())


@pytest.mark.parametrize(
    "mode,match",
    [
        ("language", "language data"),
        ("failure", "page 1"),
        ("timeout", "OCR_PAGE_TIMEOUT_SECONDS"),
        ("empty", "clearer scan"),
    ],
)
def test_ocr_failures_are_sanitized(tmp_path, monkeypatch, mode, match):
    path = tmp_path / "scan.pdf"
    pdf_fixture(path, ["scan"])
    monkeypatch.setattr(ocr.shutil, "which", lambda _: "tesseract")

    def command(args, **kwargs):
        if "--list-langs" in args:
            return subprocess.CompletedProcess(
                args, 0, b"eng\n" if mode != "language" else b"fra\n", b""
            )
        if mode == "timeout":
            raise subprocess.TimeoutExpired(args, 1)
        return subprocess.CompletedProcess(
            args, 1 if mode == "failure" else 0, b"", b"private source content and machine path"
        )

    monkeypatch.setattr(ocr.subprocess, "run", command)
    with pytest.raises(ocr.OCRError, match=match) as error:
        extract(path, "pdf", settings())
    assert "private source" not in str(error.value)


def test_page_limit_fails_instead_of_returning_partial_text(tmp_path, fake_tesseract):
    path = tmp_path / "long.pdf"
    pdf_fixture(path, ["native", "scan", "scan"])
    with pytest.raises(ocr.OCRError, match="OCR_MAX_PAGES"):
        extract(path, "pdf", settings(ocr_max_pages=1))


def test_pixel_limit_is_checked_before_full_render(tmp_path, fake_tesseract):
    path = tmp_path / "oversized.pdf"
    pdf_fixture(path, ["huge"])
    with pytest.raises(ocr.OCRError, match="OCR_MAX_PIXELS"):
        extract(path, "pdf", settings())
    assert len(fake_tesseract) == 0  # No installation probe or full render for an oversized page.


def test_document_budget_is_enforced(monkeypatch):
    engine = ocr.PDFOCR(settings(ocr_document_timeout_seconds=1))
    times = iter([1.0, 1.0, 3.0])
    monkeypatch.setattr(ocr.time, "monotonic", lambda: next(times))
    assert engine.remaining() == 1
    with pytest.raises(ocr.OCRError, match="document time budget"):
        engine.remaining()


@pytest.mark.parametrize(
    "overrides",
    [
        {"ocr_language": "../eng"},
        {"ocr_language": "eng --unsafe"},
        {"ocr_dpi": 900},
        {"ocr_max_pages": 0},
        {"ocr_memory_limit_mb": 1},
    ],
)
def test_invalid_ocr_configuration_is_rejected(overrides):
    with pytest.raises(ValidationError):
        settings(**overrides)


def test_ocr_is_disabled_by_default_and_optional_tessdata_is_empty():
    config = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@localhost/test",
        ocr_tessdata_dir="",
    )
    assert config.ocr_enabled is False and config.ocr_tessdata_dir is None
    assert processing_timeout(config, "pdf") == config.processing_timeout_seconds
    enabled = settings()
    assert processing_timeout(enabled, "pdf") == 240
    assert processing_timeout(enabled, "docx") == 60


def test_real_child_memory_guard():
    # The test runner never joins a job or changes its own resource limits.
    code = (
        "from app.documents.process_limits import apply_memory_limit; "
        "apply_memory_limit(256)\n"
        "try:\n x=bytearray(300*1024*1024)\n"
        "except MemoryError:\n raise SystemExit(0)\n"
        "raise SystemExit(1)\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=15)
    assert result.returncode == 0, "The OS memory guard failed to enforce its configured limit"


def test_worker_native_pdf_with_ocr_enabled_needs_no_installation(clients, identity_db):
    from test_documents import account, fixture_bytes, organization, upload

    client = clients(ocr_enabled=True, tesseract_cmd="missing-test-tesseract")
    account(client)
    org = organization(client)
    response = upload(client, org, fixture_bytes("pdf"), "native.pdf")
    assert response.status_code == 202
    claim_job(identity_db, client.app.state.settings)
    with Session(identity_db) as db:
        job = db.scalar(select(DocumentJob))
        assert (job.lease_until - now()).total_seconds() > 250
        job.state, job.lease_token, job.lease_until = "pending", None, None
        db.commit()
    assert run_once(identity_db, client.app.state.settings)
    doc = client.get(f"/api/v1/organizations/{org}/documents/{response.json()['id']}").json()
    assert doc["status"] == "completed", doc["error"]
    assert doc["source_metadata"]["ocr_page_count"] == 0


def test_worker_publishes_ocr_sources_and_chunks_atomically(
    clients, identity_db, tmp_path, fake_tesseract
):
    from test_documents import account, organization, upload

    path = tmp_path / "mixed.pdf"
    pdf_fixture(path, ["native", "scan", "blank"])
    client = clients(ocr_enabled=True)
    account(client)
    org = organization(client)
    response = upload(client, org, path.read_bytes(), "mixed.pdf")
    assert response.status_code == 202

    def in_process(storage, claim, limits):
        with storage.materialize(claim.organization_id, claim.document_id) as original:
            return extract(original, claim.format, limits)

    assert run_once(identity_db, client.app.state.settings, extractor=in_process)
    record = client.get(f"/api/v1/organizations/{org}/documents/{response.json()['id']}").json()
    assert record["status"] == "completed"
    assert record["source_metadata"]["ocr_page_count"] == 1
    with Session(identity_db) as db:
        sections = db.scalars(select(DocumentSection).order_by(DocumentSection.ordinal)).all()
        assert sections[1].page_number == 2 and "OCR" in sections[1].label
        chunks = db.scalars(
            select(DocumentChunk).where(DocumentChunk.section_id == sections[1].id)
        ).all()
        assert chunks and all("12345" in chunk.text for chunk in chunks)
        assert all(chunk.organization_id == sections[1].organization_id for chunk in chunks)


def test_worker_ocr_limit_failure_publishes_nothing_and_can_retry(
    clients, identity_db, tmp_path, fake_tesseract
):
    from test_documents import account, mutate, organization, upload

    path = tmp_path / "too-many-scans.pdf"
    pdf_fixture(path, ["native", "scan", "scan"])
    client = clients(ocr_enabled=True, ocr_max_pages=1)
    account(client)
    org = organization(client)
    doc_id = upload(client, org, path.read_bytes(), "limit.pdf").json()["id"]

    def in_process(storage, claim, limits):
        with storage.materialize(claim.organization_id, claim.document_id) as original:
            return extract(original, claim.format, limits)

    assert run_once(identity_db, client.app.state.settings, extractor=in_process)
    base = f"/organizations/{org}/documents/{doc_id}"
    failed = client.get("/api/v1" + base).json()
    assert failed["status"] == "failed" and "OCR_MAX_PAGES" in failed["error"]
    with Session(identity_db) as db:
        assert not db.scalars(select(DocumentSection)).all()
        assert not db.scalars(select(DocumentChunk)).all()
    client.app.state.settings.ocr_max_pages = 2
    assert mutate(client, base + "/retry").status_code == 202
    assert run_once(identity_db, client.app.state.settings, extractor=in_process)
    assert client.get("/api/v1" + base).json()["status"] == "completed"


def test_real_ocr_scanned_and_mixed_pdf(tmp_path):
    configured = get_settings()
    # Use explicit test overrides when Tesseract is installed outside PATH.
    executable = os.environ.get("TEST_TESSERACT_CMD", configured.tesseract_cmd)
    directory = os.environ.get("TEST_OCR_TESSDATA_DIR", configured.ocr_tessdata_dir)
    if not shutil.which(executable):
        pytest.skip("Tesseract not installed; set TEST_TESSERACT_CMD for real OCR tests")
    config = settings(tesseract_cmd=executable, ocr_tessdata_dir=directory)
    path = tmp_path / "real-mixed.pdf"
    pdf_fixture(path, ["native", "scan"])
    # Run the actual parser child, including OS memory limits and the native CLI.
    values = config.model_dump(mode="json")
    limits = {
        key: value
        for key, value in values.items()
        if key.startswith("ocr_")
        or key
        in {
            "tesseract_cmd",
            "extraction_max_characters",
            "extraction_max_pages",
            "docx_max_uncompressed_bytes",
        }
    }
    result = subprocess.run(
        [sys.executable, "-m", "app.documents.extraction", str(path), "pdf"],
        input=json.dumps(limits),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, "Real Tesseract integration failed; verify eng language data"
    output = json.loads(result.stdout)["result"]
    assert output["metadata"]["ocr_page_count"] == 1
    assert output["sections"][1]["page_number"] == 2
    assert "DOCUMIND" in output["sections"][1]["text"].upper()
