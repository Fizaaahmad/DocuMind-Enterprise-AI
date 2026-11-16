"""Immutable source revisions, versioned definitions, and append-only review history."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SourceRevision(Base):
    __tablename__ = "source_revisions"
    __table_args__ = (
        UniqueConstraint("id", "organization_id"),
        UniqueConstraint("document_id", "fingerprint"),
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["documents.id", "documents.organization_id"],
            ondelete="CASCADE",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column()
    document_id: Mapped[uuid.UUID] = mapped_column()
    fingerprint: Mapped[str] = mapped_column(String(64))
    checksum: Mapped[str | None] = mapped_column(String(64))
    provenance: Mapped[dict] = mapped_column(JSONB)
    current: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RevisionSection(Base):
    __tablename__ = "revision_sections"
    __table_args__ = (
        UniqueConstraint("id", "revision_id", "organization_id"),
        UniqueConstraint("revision_id", "ordinal"),
        ForeignKeyConstraint(
            ["revision_id", "organization_id"],
            ["source_revisions.id", "source_revisions.organization_id"],
            ondelete="CASCADE",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column()
    organization_id: Mapped[uuid.UUID] = mapped_column()
    ordinal: Mapped[int] = mapped_column()
    label: Mapped[str] = mapped_column(String(200))
    page_number: Mapped[int | None] = mapped_column()
    text: Mapped[str] = mapped_column(Text)


class AnalysisTemplate(Base):
    __tablename__ = "analysis_templates"
    __table_args__ = (Index("ix_analysis_templates_org", "organization_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("analysis_templates.id"))
    name: Mapped[str] = mapped_column(String(100))
    definition: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        UniqueConstraint("id", "organization_id"),
        Index("ix_analysis_runs_claim", "state", "available_at"),
        Index("ix_analysis_runs_org", "organization_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    creator_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # Source deletion redacts the entire run before these nullable pointers clear.
    left_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_revisions.id", ondelete="SET NULL")
    )
    right_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_revisions.id", ondelete="SET NULL")
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("analysis_templates.id"))
    mode: Mapped[str] = mapped_column(String(20))
    engine: Mapped[str] = mapped_column(String(20))
    state: Mapped[str] = mapped_column(String(20), default="pending")
    error: Mapped[str | None] = mapped_column(String(500))
    coverage: Mapped[dict] = mapped_column(JSONB, default=dict)
    attempts: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[uuid.UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisItem(Base):
    __tablename__ = "analysis_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "organization_id"],
            ["analysis_runs.id", "analysis_runs.organization_id"],
            ondelete="CASCADE",
        ),
        Index("ix_analysis_items_run", "organization_id", "run_id"),
        Index("ix_analysis_items_work", "organization_id", "kind", "review_status"),
        Index(
            "ix_analysis_items_assignment",
            "organization_id",
            "assignee_membership_id",
            "assignment_due_date",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column()
    organization_id: Mapped[uuid.UUID] = mapped_column()
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    original: Mapped[dict] = mapped_column(JSONB)
    corrected: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    evidence: Mapped[list] = mapped_column(JSONB)
    validation: Mapped[str] = mapped_column(String(30))
    review_status: Mapped[str] = mapped_column(String(20), default="pending")
    obligation_status: Mapped[str] = mapped_column(String(20), default="open")
    version: Mapped[int] = mapped_column(default=1)
    assignee_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memberships.id", ondelete="SET NULL")
    )
    assignment_due_date: Mapped[date | None] = mapped_column(Date)


class ReviewEvent(Base):
    __tablename__ = "analysis_review_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analysis_items.id", ondelete="CASCADE"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(20))
    before: Mapped[dict] = mapped_column(JSONB)
    after: Mapped[dict] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
