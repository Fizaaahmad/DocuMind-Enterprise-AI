import uuid
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import current_user, get_db
from app.core.security import now
from app.documents.schemas import ContentOutput, DocumentList, DocumentOutput, SectionOutput, Status
from app.documents.service import can_manage, find_document, queue_deletion, upload_document
from app.documents.storage import get_storage
from app.documents.validation import MIME_TYPES
from app.models import Document, DocumentJob, DocumentSection, User
from app.services.organizations import membership

router = APIRouter(prefix="/organizations/{organization_id}/documents", tags=["documents"])


@router.get("/config")
def configuration(
    organization_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    return {
        "upload_max_bytes": request.app.state.settings.upload_max_bytes,
        "formats": list(MIME_TYPES),
    }


@router.post("", response_model=DocumentOutput, status_code=202)
def upload(
    organization_id: uuid.UUID,
    file: UploadFile,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    try:
        return upload_document(db, request.app.state.settings, organization_id, user, file)
    finally:
        file.file.close()


@router.get("", response_model=DocumentList)
def library(
    organization_id: uuid.UUID,
    q: str = Query("", max_length=180),
    status: Status | None = None,
    format: Literal["pdf", "docx", "txt"] | None = None,
    sort: Literal["newest", "oldest", "name"] = "newest",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    filters = [Document.organization_id == organization_id, Document.deleted_at.is_(None)]
    if q.strip():
        filters.append(Document.filename.icontains(q.strip(), autoescape=True))
    if status:
        filters.append(Document.status == status)
    if format:
        filters.append(Document.format == format)
    order = {
        "newest": Document.created_at.desc(),
        "oldest": Document.created_at.asc(),
        "name": Document.filename.asc(),
    }[sort]
    total = db.scalar(select(func.count()).select_from(Document).where(*filters))
    items = db.scalars(
        select(Document)
        .where(*filters)
        .order_by(order, Document.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return DocumentList(
        items=[DocumentOutput.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentOutput)
def details(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    return find_document(db, organization_id, document_id)


@router.get("/{document_id}/content", response_model=ContentOutput)
def content(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(5, ge=1, le=10),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    document = find_document(db, organization_id, document_id)
    sections = db.scalars(
        select(DocumentSection)
        .where(
            DocumentSection.document_id == document_id,
            DocumentSection.organization_id == organization_id,
        )
        .order_by(DocumentSection.ordinal)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ContentOutput(
        document_id=document_id,
        total=document.section_count,
        page=page,
        page_size=page_size,
        sections=[SectionOutput.model_validate(item) for item in sections],
    )


@router.get("/{document_id}/download")
def download(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    document = find_document(db, organization_id, document_id)
    if not document.storage_ready:
        raise HTTPException(409, "Original file is not available")
    try:
        source = get_storage(request.app.state.settings).open(organization_id, document_id)
    except OSError:
        raise HTTPException(404, "Original file is not available") from None

    def stream():
        try:
            while block := source.read(64 * 1024):
                yield block
        finally:
            source.close()

    return StreamingResponse(
        stream(),
        media_type=MIME_TYPES[document.format],
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(document.filename)}",
            "Content-Length": str(document.size_bytes),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.delete("/{document_id}", status_code=202)
def remove(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    document = find_document(db, organization_id, document_id, lock=True)
    can_manage(db, organization_id, user, document)
    queue_deletion(db, document)
    return {"status": "deleting"}


@router.post("/{document_id}/retry", response_model=DocumentOutput, status_code=202)
def retry(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    document = find_document(db, organization_id, document_id, lock=True)
    can_manage(db, organization_id, user, document)
    if document.status != "failed" or not document.storage_ready:
        raise HTTPException(409, "Only failed documents with an available original can be retried")
    job = db.scalar(
        select(DocumentJob)
        .where(
            DocumentJob.document_id == document_id, DocumentJob.organization_id == organization_id
        )
        .with_for_update()
    )
    document.status, document.error = "pending", None
    document.chunk_size = request.app.state.settings.chunk_size
    document.chunk_overlap = request.app.state.settings.chunk_overlap
    document.processing_started_at = document.processing_completed_at = None
    job.kind, job.state, job.attempts, job.last_error = "process", "pending", 0, None
    job.available_at, job.lease_token, job.lease_until = now(), None, None
    db.commit()
    return document
