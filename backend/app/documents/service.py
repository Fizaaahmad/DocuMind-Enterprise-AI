import uuid
from datetime import timedelta

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import now
from app.documents.storage import UploadTooLarge, get_storage
from app.documents.validation import InvalidDocument, safe_filename, validate_file
from app.models import Document, DocumentJob, User
from app.services.organizations import membership


def find_document(db: Session, org_id: uuid.UUID, doc_id: uuid.UUID, lock=False) -> Document:
    query = select(Document).where(
        Document.id == doc_id, Document.organization_id == org_id, Document.deleted_at.is_(None)
    )
    if lock:
        query = query.with_for_update()
    document = db.scalar(query)
    if not document:
        raise HTTPException(404, "Document not found")
    return document


def can_manage(db: Session, org_id: uuid.UUID, user: User, document: Document):
    member = membership(db, org_id, user)
    if document.uploader_id != user.id and member.role != "admin":
        raise HTTPException(
            403, "Only the uploader or an organization Admin can manage this document"
        )


def queue_deletion(db: Session, document: Document):
    document.deleted_at = now()
    job = db.scalar(
        select(DocumentJob)
        .where(
            DocumentJob.document_id == document.id,
            DocumentJob.organization_id == document.organization_id,
        )
        .with_for_update()
    )
    job.kind, job.state, job.attempts = "delete", "pending", 0
    job.available_at, job.lease_until, job.lease_token = now(), None, None
    db.commit()


def upload_document(
    db: Session, settings: Settings, org_id: uuid.UUID, user: User, file: UploadFile
) -> Document:
    membership(db, org_id, user)
    try:
        filename, format = safe_filename(file.filename)
        if file.size and file.size > settings.upload_max_bytes:
            raise UploadTooLarge()
        validate_file(file.file, format, file.content_type, settings)
    except UploadTooLarge:
        raise HTTPException(413, "File exceeds the configured upload limit") from None
    except InvalidDocument as exc:
        raise HTTPException(422, str(exc)) from None
    document = Document(
        organization_id=org_id,
        uploader_id=user.id,
        filename=filename,
        format=format,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    db.add(document)
    db.flush()
    # Durable reservation: an interrupted file copy is reclaimed by the worker.
    job = DocumentJob(
        document_id=document.id, organization_id=org_id, available_at=now() + timedelta(minutes=10)
    )
    db.add(job)
    db.commit()
    storage = get_storage(settings)
    document_id = document.id
    try:
        # Lock the authorized reservation during the bounded disk copy. Deletion
        # cannot remove the row and then race a late file rename into an orphan.
        membership(db, org_id, user, lock=True)
        document = find_document(db, org_id, document_id, lock=True)
        if document.status != "pending":
            raise HTTPException(409, "Upload reservation expired; please upload again")
        size, checksum = storage.save(org_id, document_id, file.file, settings.upload_max_bytes)
        document.size_bytes, document.checksum, document.storage_ready = size, checksum, True
        job = db.scalar(
            select(DocumentJob)
            .where(DocumentJob.document_id == document.id, DocumentJob.organization_id == org_id)
            .with_for_update()
        )
        job.available_at = now()
        db.commit()
        return document
    except Exception as exc:
        db.rollback()
        # Retain a durable cleanup job if storage or finalization failed.
        pending = db.scalar(
            select(Document)
            .where(Document.id == document_id, Document.organization_id == org_id)
            .with_for_update()
        )
        if pending:
            queue_deletion(db, pending)
        if isinstance(exc, HTTPException):
            raise
        if isinstance(exc, UploadTooLarge):
            raise HTTPException(413, "File exceeds the configured upload limit") from None
        raise HTTPException(503, "File storage is unavailable; please try again") from None
