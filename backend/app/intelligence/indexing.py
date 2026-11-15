"""Index jobs reuse the document queue and its lease fencing."""

import time
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import now
from app.intelligence.embeddings import get_encoder, profile
from app.models import ChunkEmbedding, DocumentChunk, DocumentJob


def enqueue(db, document, settings):
    if document.status != "completed" or document.deleted_at:
        raise HTTPException(409, "Only completed documents can be indexed")
    job = db.scalar(
        select(DocumentJob)
        .where(
            DocumentJob.document_id == document.id,
            DocumentJob.organization_id == document.organization_id,
        )
        .with_for_update()
    )
    if job.state in {"pending", "running"}:
        raise HTTPException(409, "Document already has an active job")
    document.index_status, document.index_error = "pending", None
    document.index_profile = profile(settings)
    db.execute(delete(ChunkEmbedding).where(ChunkEmbedding.document_id == document.id))
    job.kind, job.state, job.attempts = "embed", "pending", 0
    job.available_at, job.lease_until, job.lease_token = now(), None, None
    job.last_error = None


def index_document(engine, claim, settings):
    from app.documents.worker import active_claim

    deadline = time.monotonic() + settings.indexing_timeout_seconds
    encoder = get_encoder(settings)
    vectors = []
    with Session(engine) as db:
        rows = db.execute(
            select(DocumentChunk.id, DocumentChunk.text)
            .where(
                DocumentChunk.document_id == claim.document_id,
                DocumentChunk.organization_id == claim.organization_id,
            )
            .order_by(DocumentChunk.ordinal)
        ).all()
    for start in range(0, len(rows), settings.embedding_batch_size):
        if time.monotonic() > deadline:
            raise ValueError("Indexing exceeded its time limit; increase INDEXING_TIMEOUT_SECONDS")
        with Session(engine) as db:
            document, job = active_claim(db, claim)
            if not document:
                return False
            if document.index_profile != profile(settings):
                raise ValueError(
                    "Embedding configuration changed; reindex with matching API/worker settings"
                )
            document.index_status = "processing"
            job.lease_until = now() + timedelta(seconds=settings.indexing_timeout_seconds + 30)
            db.commit()
        group = rows[start : start + settings.embedding_batch_size]
        encoded = encoder.encode([row.text for row in group])
        vectors.extend(zip([row.id for row in group], encoded, strict=True))
    with Session(engine) as db:
        document, job = active_claim(db, claim)
        if not document:
            return False
        if time.monotonic() > deadline:
            raise ValueError("Indexing exceeded its time limit; increase INDEXING_TIMEOUT_SECONDS")
        if document.index_profile != profile(settings):
            raise ValueError("Embedding profile changed; reindex this document")
        db.execute(
            delete(ChunkEmbedding).where(
                ChunkEmbedding.document_id == claim.document_id,
                ChunkEmbedding.organization_id == claim.organization_id,
            )
        )
        for chunk_id, vector in vectors:
            db.add(
                ChunkEmbedding(
                    chunk_id=chunk_id,
                    document_id=claim.document_id,
                    organization_id=claim.organization_id,
                    profile=profile(settings),
                    embedding=vector,
                )
            )
        document.index_status, document.index_error = "completed", None
        job.state, job.last_error = "completed", None
        job.lease_until = job.lease_token = None
        db.commit()
        return True
