import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("id", "organization_id"),
        CheckConstraint("status IN ('pending','processing','completed','failed')", name="status"),
        CheckConstraint("format IN ('pdf','docx','txt')", name="format"),
        Index("ix_documents_org_created", "organization_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    uploader_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    filename: Mapped[str] = mapped_column(String(180))
    format: Mapped[str] = mapped_column(String(8))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    checksum: Mapped[str | None] = mapped_column(String(64))
    storage_ready: Mapped[bool] = mapped_column(default=False, server_default="false")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    error: Mapped[str | None] = mapped_column(String(500))
    section_count: Mapped[int] = mapped_column(default=0, server_default="0")
    chunk_count: Mapped[int] = mapped_column(default=0, server_default="0")
    character_count: Mapped[int] = mapped_column(default=0, server_default="0")
    chunk_size: Mapped[int] = mapped_column(Integer)
    chunk_overlap: Mapped[int] = mapped_column(Integer)
    source_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentSection(Base):
    __tablename__ = "document_sections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["documents.id", "documents.organization_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "document_id", "organization_id"),
        UniqueConstraint("document_id", "ordinal"),
        Index("ix_document_sections_org_doc", "organization_id", "document_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column()
    organization_id: Mapped[uuid.UUID] = mapped_column()
    ordinal: Mapped[int] = mapped_column()
    page_number: Mapped[int | None] = mapped_column()
    label: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["section_id", "document_id", "organization_id"],
            [
                "document_sections.id",
                "document_sections.document_id",
                "document_sections.organization_id",
            ],
            ondelete="CASCADE",
        ),
        UniqueConstraint("document_id", "ordinal"),
        Index("ix_document_chunks_org_doc", "organization_id", "document_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    section_id: Mapped[uuid.UUID] = mapped_column()
    document_id: Mapped[uuid.UUID] = mapped_column()
    organization_id: Mapped[uuid.UUID] = mapped_column()
    ordinal: Mapped[int] = mapped_column()
    start_offset: Mapped[int] = mapped_column()
    end_offset: Mapped[int] = mapped_column()
    text: Mapped[str] = mapped_column(Text)


class DocumentJob(Base):
    __tablename__ = "document_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["documents.id", "documents.organization_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("document_id"),
        CheckConstraint("kind IN ('process','delete')", name="kind"),
        CheckConstraint("state IN ('pending','running','completed','failed')", name="state"),
        Index("ix_document_jobs_claim", "state", "available_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column()
    organization_id: Mapped[uuid.UUID] = mapped_column()
    kind: Mapped[str] = mapped_column(String(10), default="process")
    state: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[uuid.UUID | None] = mapped_column()
    last_error: Mapped[str | None] = mapped_column(String(500))
