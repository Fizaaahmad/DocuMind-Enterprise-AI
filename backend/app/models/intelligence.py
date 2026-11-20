"""Tenant-bound vectors and private assistant history."""

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["chunk_id", "document_id", "organization_id"],
            [
                "document_chunks.id",
                "document_chunks.document_id",
                "document_chunks.organization_id",
            ],
            ondelete="CASCADE",
        ),
        Index("ix_chunk_embeddings_scope", "organization_id", "profile", "document_id"),
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column()
    organization_id: Mapped[uuid.UUID] = mapped_column()
    profile: Mapped[str] = mapped_column(String(64))
    # Unconstrained pgvector dimensions allow explicit model changes without DDL.
    embedding: Mapped[list[float]] = mapped_column(Vector())


class Conversation(Base):
    __tablename__ = "ai_conversations"
    __table_args__ = (Index("ix_ai_conversations_owner", "organization_id", "user_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIUsage(Base):
    __tablename__ = "ai_usage"
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    requests: Mapped[int] = mapped_column(default=0)


class Message(Base):
    __tablename__ = "ai_messages"
    __table_args__ = (Index("ix_ai_messages_conversation", "conversation_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE")
    )
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[str] = mapped_column(String(16), default="pending")
    provider: Mapped[str] = mapped_column(String(100))
    is_mock: Mapped[bool] = mapped_column(default=False)
    citations: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProviderRequest(Base):
    """No prompts/credentials. Cached output is source-bearing and redacted on deletion."""

    __tablename__ = "provider_requests"
    __table_args__ = (Index("ix_provider_requests_budget", "organization_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    operation_key: Mapped[str] = mapped_column(String(180), unique=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    model: Mapped[str] = mapped_column(String(100))
    fingerprint: Mapped[str] = mapped_column(String(64))
    document_ids: Mapped[list] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(20), default="started")
    attempts: Mapped[int] = mapped_column(default=0)
    reserved_tokens: Mapped[int] = mapped_column()
    reserved_cost: Mapped[float] = mapped_column(Numeric(16, 8))
    input_tokens: Mapped[int | None] = mapped_column()
    output_tokens: Mapped[int | None] = mapped_column()
    estimated_cost: Mapped[float | None] = mapped_column(Numeric(16, 8))
    response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
