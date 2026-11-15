import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import current_user, get_db
from app.core.security import now
from app.documents.service import can_manage, find_document
from app.intelligence.embeddings import EmbeddingUnavailable, profile
from app.intelligence.indexing import enqueue
from app.intelligence.providers import ProviderUnavailable, get_provider
from app.intelligence.rag import answer
from app.intelligence.retrieval import retrieve, validate_selection
from app.models import AIUsage, Conversation, Document, DocumentChunk, Message, User
from app.services.organizations import membership

router = APIRouter(prefix="/organizations/{organization_id}/intelligence", tags=["intelligence"])


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    document_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)

    @field_validator("question")
    @classmethod
    def meaningful(cls, value):
        if not value.strip():
            raise ValueError("Enter a question")
        return value.strip()


def owned(db, org, user, conversation_id, lock=False):
    membership(db, org, user)
    statement = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.organization_id == org,
        Conversation.user_id == user.id,
    )
    conversation = db.scalar(statement.with_for_update() if lock else statement)
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    return conversation


def live_citations(db, org, citations):
    # Resolve current source content; stored history is never an authorization grant.
    for citation in citations:
        chunk = db.scalar(
            select(DocumentChunk)
            .join(
                Document,
                Document.id == DocumentChunk.document_id,
            )
            .where(
                DocumentChunk.id == uuid.UUID(citation["source_id"]),
                DocumentChunk.organization_id == org,
                Document.deleted_at.is_(None),
                Document.status == "completed",
            )
        )
        if not chunk or citation["quote"] not in chunk.text:
            return False
    return True


def output(db, org, item):
    valid = live_citations(db, org, item.citations)
    state = item.state
    if state == "pending" and item.created_at < now() - timedelta(seconds=120):
        state = "interrupted"
    return {
        "id": item.id,
        "question": item.question,
        "state": state,
        "answer": item.answer if valid else "Source documents changed or were deleted; ask again.",
        "citations": item.citations if valid else [],
        "is_mock": item.is_mock,
        "created_at": item.created_at,
    }


@router.get("/status")
def status(
    organization_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    settings = request.app.state.settings
    docs = db.scalars(
        select(Document)
        .where(
            Document.organization_id == organization_id,
            Document.deleted_at.is_(None),
        )
        .order_by(Document.created_at.desc())
        .limit(500)
    ).all()
    return {
        "embeddings_enabled": settings.embeddings_enabled,
        "provider": settings.llm_provider,
        "is_mock": settings.llm_provider == "mock",
        "documents": [
            {
                "id": d.id,
                "filename": d.filename,
                "status": d.status,
                "index_status": d.index_status
                if d.index_profile == profile(settings)
                else "unindexed",
                "index_error": d.index_error,
            }
            for d in docs
        ],
    }


@router.post("/documents/{document_id}/index", status_code=202)
def index(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    if not request.app.state.settings.embeddings_enabled:
        raise HTTPException(503, "Enable EMBEDDINGS_ENABLED before indexing")
    document = find_document(db, organization_id, document_id, lock=True)
    can_manage(db, organization_id, user, document)
    enqueue(db, document, request.app.state.settings)
    db.commit()
    return {"status": "pending"}


@router.post("/search")
def search(
    organization_id: uuid.UUID,
    body: Question,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    try:
        sources = retrieve(
            db, request.app.state.settings, organization_id, body.question, body.document_ids
        )
        current_user(request, db)
        membership(db, organization_id, user)
        return {"sources": sources}
    except EmbeddingUnavailable as exc:
        raise HTTPException(503, str(exc)) from None


@router.get("/conversations")
def conversations(
    organization_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    membership(db, organization_id, user)
    return db.scalars(
        select(Conversation)
        .where(
            Conversation.organization_id == organization_id,
            Conversation.user_id == user.id,
        )
        .order_by(Conversation.created_at.desc())
        .limit(100)
    ).all()


@router.post("/conversations", status_code=201)
def create(
    organization_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    membership(db, organization_id, user)
    item = Conversation(organization_id=organization_id, user_id=user.id, title="New conversation")
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "title": item.title}


@router.delete("/conversations/{conversation_id}")
def remove(
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    db.delete(owned(db, organization_id, user, conversation_id, lock=True))
    db.commit()
    return {"status": "deleted"}


@router.get("/conversations/{conversation_id}/messages")
def history(
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    owned(db, organization_id, user, conversation_id)
    items = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id)
        .limit(100)
    ).all()
    return [output(db, organization_id, item) for item in reversed(items)]


@router.post("/conversations/{conversation_id}/messages")
def ask(
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    body: Question,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    settings = request.app.state.settings
    owned(db, organization_id, user, conversation_id)
    validate_selection(db, organization_id, body.document_ids)
    try:
        provider = get_provider(settings)
        sources = retrieve(db, settings, organization_id, body.question, body.document_ids)
    except (ProviderUnavailable, EmbeddingUnavailable) as exc:
        raise HTTPException(503, str(exc)) from None
    # Serialize quota reservations per user across all their organizations.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    conversation = owned(db, organization_id, user, conversation_id, lock=True)
    previous = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(10)
    ).all()
    if any(
        m.state == "pending" and m.created_at > now() - timedelta(seconds=120) for m in previous
    ):
        raise HTTPException(409, "An answer is already in progress")
    usage = db.get(AIUsage, (user.id, now().date()))
    if not usage:
        usage = AIUsage(user_id=user.id, day=now().date(), requests=0)
        db.add(usage)
    if usage.requests >= settings.ai_daily_requests:
        raise HTTPException(429, "Daily assistant request limit reached")
    usage.requests += 1
    conversation.title = body.question.strip()[:100] or "Document question"
    item = Message(
        conversation_id=conversation_id,
        question=body.question,
        provider=settings.llm_provider,
        is_mock=provider.is_mock,
    )
    db.add(item)
    db.flush()
    item_id = item.id
    # Only current authorized evidence goes to the provider; old source-bearing
    # answers are excluded, preventing deleted/unselected content re-entering context.
    prior = [(m.question, "") for m in reversed(previous) if m.state == "completed"]
    db.commit()  # no locks held during model/provider inference
    try:
        text, citations = answer(provider, settings, body.question, prior, sources)
    except ProviderUnavailable as exc:
        item = db.get(Message, item_id)
        if item:
            item.state, item.answer = "failed", str(exc)
            db.commit()
        raise HTTPException(503, str(exc)) from None
    # Recheck live session, membership, source existence after the external boundary.
    current_user(request, db)
    owned(db, organization_id, user, conversation_id, lock=True)
    validate_selection(db, organization_id, body.document_ids)
    if not live_citations(db, organization_id, citations):
        db.rollback()
        raise HTTPException(409, "Source documents changed while answering; ask again")
    item = db.get(Message, item_id)
    item.answer, item.citations, item.state = text, citations, "completed"
    db.commit()
    db.refresh(item)
    return output(db, organization_id, item)
