import uuid

from fastapi import HTTPException
from sqlalchemy import case, select

from app.intelligence.embeddings import get_encoder, profile
from app.models import ChunkEmbedding, Document, DocumentChunk, DocumentSection


def validate_selection(db, org, ids):
    if not ids:
        return
    found = set(
        db.scalars(
            select(Document.id).where(
                Document.organization_id == org,
                Document.id.in_(ids),
                Document.deleted_at.is_(None),
            )
        )
    )
    if found != set(ids):
        raise HTTPException(404, "Selected document not found")


def retrieve(db, settings, org: uuid.UUID, question, ids, limit=None):
    validate_selection(db, org, ids)
    vector = get_encoder(settings).encode([question])[0]
    # CASE prevents evaluating distance against another profile's dimensions,
    # regardless of the query planner's ordering of WHERE predicates.
    distance = case(
        (
            ChunkEmbedding.profile == profile(settings),
            ChunkEmbedding.embedding.cosine_distance(vector),
        ),
        else_=None,
    )
    conditions = [
        ChunkEmbedding.organization_id == org,
        ChunkEmbedding.profile == profile(settings),
        Document.organization_id == org,
        Document.deleted_at.is_(None),
        Document.status == "completed",
        Document.index_status == "completed",
        Document.index_profile == profile(settings),
        distance <= 1 - settings.retrieval_min_similarity,
    ]
    if ids:
        conditions.append(Document.id.in_(ids))
    rows = db.execute(
        select(
            DocumentChunk,
            DocumentSection,
            Document.filename,
            distance.label("distance"),
        )
        .select_from(ChunkEmbedding)
        .join(
            DocumentChunk,
            (
                (DocumentChunk.id == ChunkEmbedding.chunk_id)
                & (DocumentChunk.document_id == ChunkEmbedding.document_id)
                & (DocumentChunk.organization_id == org)
            ),
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(
            DocumentSection,
            (DocumentSection.id == DocumentChunk.section_id)
            & (DocumentSection.organization_id == org),
        )
        .where(*conditions)
        .order_by(distance, DocumentChunk.id)
        .limit(min(limit or settings.retrieval_limit, settings.retrieval_limit))
    ).all()
    sources, budget = [], settings.rag_context_characters
    for chunk, section, filename, dist in rows:
        if budget <= 0:
            break
        text = chunk.text[:budget]
        sources.append(
            {
                "source_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "filename": filename,
                "page_number": section.page_number,
                "label": section.label,
                "start_offset": chunk.start_offset,
                "text": text,
                "similarity": round(1 - float(dist), 5),
            }
        )
        budget -= len(text)
    return sources
