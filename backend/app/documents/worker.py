"""Durable PostgreSQL queue. Run: python -m app.documents.worker [--once]."""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import Engine, and_, delete, or_, select
from sqlalchemy.orm import Session

from app.core.config import BACKEND_ROOT, Settings, get_settings
from app.core.security import now
from app.db.session import build_engine
from app.documents.chunking import chunk_text
from app.documents.storage import Storage, get_storage
from app.models import Document, DocumentChunk, DocumentJob, DocumentSection

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Claim:
    document_id: uuid.UUID
    organization_id: uuid.UUID
    token: uuid.UUID
    kind: str
    ready: bool
    format: str
    chunk_size: int
    chunk_overlap: int


def claim_job(engine: Engine, settings: Settings) -> Claim | None:
    with Session(engine) as db:
        job = db.scalar(
            select(DocumentJob)
            .where(
                DocumentJob.available_at <= now(),
                or_(
                    DocumentJob.state == "pending",
                    and_(DocumentJob.state == "running", DocumentJob.lease_until < now()),
                ),
            )
            .order_by(DocumentJob.available_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return None
        # Never wait for a document lock while holding a job lock (delete uses doc -> job).
        document = db.scalar(
            select(Document)
            .where(
                Document.id == job.document_id,
                Document.organization_id == job.organization_id,
            )
            .with_for_update(skip_locked=True)
        )
        if not document:
            return None
        if job.kind == "process" and job.attempts >= settings.worker_max_attempts:
            document.status, document.error = (
                "failed",
                "Processing interrupted too many times; retry this document",
            )
            document.processing_completed_at = now()
            job.state, job.last_error = "failed", document.error
            job.lease_token = job.lease_until = None
            db.commit()
            return None
        token = uuid.uuid4()
        job.state, job.lease_token = "running", token
        job.lease_until = now() + timedelta(seconds=settings.processing_timeout_seconds + 30)
        job.attempts += 1
        if job.kind == "process":
            document.status, document.error = "processing", None
            document.processing_started_at = now()
        claim = Claim(
            document.id,
            document.organization_id,
            token,
            job.kind,
            document.storage_ready,
            document.format,
            document.chunk_size,
            document.chunk_overlap,
        )
        db.commit()
        return claim


def active_claim(db: Session, claim: Claim):
    document = db.scalar(
        select(Document)
        .where(
            Document.id == claim.document_id,
            Document.organization_id == claim.organization_id,
        )
        .with_for_update()
    )
    if not document:
        return None, None
    job = db.scalar(
        select(DocumentJob)
        .where(
            DocumentJob.document_id == claim.document_id,
            DocumentJob.organization_id == claim.organization_id,
        )
        .with_for_update()
    )
    if (
        not job
        or job.lease_token != claim.token
        or job.state != "running"
        or job.kind != claim.kind
        or not job.lease_until
        or job.lease_until <= now()
    ):
        return None, None
    if document.deleted_at and claim.kind != "delete":
        return None, None
    return document, job


def extract_in_process(storage: Storage, claim: Claim, settings: Settings) -> dict:
    limits = {
        key: getattr(settings, key)
        for key in (
            "extraction_max_characters",
            "extraction_max_pages",
            "docx_max_uncompressed_bytes",
        )
    }
    # Native parsers consume a path supplied by the authorized storage adapter.
    with storage.materialize(claim.organization_id, claim.document_id) as path:
        process = subprocess.Popen(
            [sys.executable, "-m", "app.documents.extraction", str(path), claim.format],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            cwd=BACKEND_ROOT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            stdout, _ = process.communicate(
                json.dumps(limits), timeout=settings.processing_timeout_seconds
            )
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            # Windows venv launchers have a child interpreter: terminate the whole owned tree.
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True
                )
            else:
                process.kill()
            process.communicate()
            raise
    if process.returncode not in (0, 2):
        raise ValueError("Document parser stopped unexpectedly; retry or replace the file")
    payload = json.loads(stdout)
    if "error" in payload:
        raise ValueError(payload["error"])
    return payload["result"]


def publish(engine: Engine, claim: Claim, result: dict, settings: Settings) -> bool:
    with Session(engine) as db:
        document, job = active_claim(db, claim)
        if not document:
            return False
        db.execute(
            delete(DocumentSection).where(
                DocumentSection.document_id == claim.document_id,
                DocumentSection.organization_id == claim.organization_id,
            )
        )  # Cascades any previous chunks for an idempotent retry.
        ordinal = 0
        for index, source in enumerate(result["sections"]):
            section_id = uuid.uuid4()
            db.add(
                DocumentSection(
                    id=section_id,
                    document_id=claim.document_id,
                    organization_id=claim.organization_id,
                    ordinal=index,
                    page_number=source["page_number"],
                    label=source["label"],
                    text=source["text"],
                )
            )
            db.flush()
            for start, end, text in chunk_text(
                source["text"], claim.chunk_size, claim.chunk_overlap
            ):
                if ordinal >= settings.processing_max_chunks:
                    raise ValueError("Too many chunks; increase chunk size or reduce overlap")
                db.add(
                    DocumentChunk(
                        section_id=section_id,
                        document_id=claim.document_id,
                        organization_id=claim.organization_id,
                        ordinal=ordinal,
                        start_offset=start,
                        end_offset=end,
                        text=text,
                    )
                )
                ordinal += 1
        document.status, document.error = "completed", None
        document.section_count, document.chunk_count = len(result["sections"]), ordinal
        document.character_count, document.source_metadata = (
            result["character_count"],
            result["metadata"],
        )
        document.processing_completed_at = now()
        job.state, job.last_error = "completed", None
        job.lease_until = job.lease_token = None
        db.commit()
        return True


def fail(engine: Engine, claim: Claim, settings: Settings, message: str, transient=False):
    with Session(engine) as db:
        document, job = active_claim(db, claim)
        if not document:
            return
        job.last_error = message
        job.lease_token = job.lease_until = None
        if claim.kind == "delete" or (transient and job.attempts < settings.worker_max_attempts):
            job.state = "pending"
            job.available_at = now() + timedelta(seconds=min(300, 2 ** min(job.attempts, 8)))
            if claim.kind == "process":
                document.status = "pending"
        else:
            job.state = "failed"
            document.status, document.error = "failed", message
            document.processing_completed_at = now()
        db.commit()


def run_once(engine: Engine, settings: Settings, extractor=extract_in_process) -> bool:
    claim = claim_job(engine, settings)
    if not claim:
        return False
    storage = get_storage(settings)
    try:
        if claim.kind == "delete":
            with Session(engine) as db:
                document, job = active_claim(db, claim)
                if document:
                    storage.delete(claim.organization_id, claim.document_id)
                    db.delete(document)
                    db.commit()
        elif not claim.ready:
            storage.delete(claim.organization_id, claim.document_id)
            fail(engine, claim, settings, "Upload was interrupted; please upload the file again")
        else:
            publish(engine, claim, extractor(storage, claim, settings), settings)
    except subprocess.TimeoutExpired:
        fail(engine, claim, settings, "Document processing exceeded the configured time limit")
    except ValueError as exc:
        fail(engine, claim, settings, str(exc)[:500])
    except OSError:
        fail(engine, claim, settings, "File storage is temporarily unavailable", transient=True)
    except Exception:
        logger.warning("Document job failed: document=%s", claim.document_id)
        fail(engine, claim, settings, "Document processing failed; please retry", transient=True)
    return True


def main():
    parser = argparse.ArgumentParser(description="DocuMind document-processing worker")
    parser.add_argument("--once", action="store_true", help="Handle at most one available job")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()
    engine = build_engine(str(settings.database_url))
    logger.info("Document worker started; storage=%s", settings.storage_path)
    try:
        while True:
            try:
                handled = run_once(engine, settings)
            except Exception:
                logger.warning("Worker database unavailable; will retry")
                handled = False
            if args.once:
                break
            if not handled:
                time.sleep(settings.worker_poll_seconds)
    except KeyboardInterrupt:
        logger.info("Worker stopped; interrupted leases will be reclaimed")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
