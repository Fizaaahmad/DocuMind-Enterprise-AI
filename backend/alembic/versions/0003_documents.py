"""document_library

Revision ID: 0003_documents
Revises: 0002_identity
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_documents"
down_revision: Union[str, Sequence[str], None] = "0002_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Reviewed additive migration: only Phase 3 tables, indexes, and constraints.
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("uploader_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(length=180), nullable=False),
        sa.Column("format", sa.String(length=8), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("storage_ready", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("section_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("character_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("chunk_overlap", sa.Integer(), nullable=False),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("format IN ('pdf','docx','txt')", name=op.f("ck_documents_format")),
        sa.CheckConstraint(
            "status IN ('pending','processing','completed','failed')",
            name=op.f("ck_documents_status"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_documents_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["uploader_id"],
            ["users.id"],
            name=op.f("fk_documents_uploader_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("id", "organization_id", name=op.f("uq_documents_id")),
    )
    op.create_index(
        "ix_documents_org_created", "documents", ["organization_id", "created_at"], unique=False
    )
    op.create_table(
        "document_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.CheckConstraint("kind IN ('process','delete')", name=op.f("ck_document_jobs_kind")),
        sa.CheckConstraint(
            "state IN ('pending','running','completed','failed')",
            name=op.f("ck_document_jobs_state"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["documents.id", "documents.organization_id"],
            name=op.f("fk_document_jobs_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_jobs")),
        sa.UniqueConstraint("document_id", name=op.f("uq_document_jobs_document_id")),
    )
    op.create_index(
        "ix_document_jobs_claim", "document_jobs", ["state", "available_at"], unique=False
    )
    op.create_table(
        "document_sections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["documents.id", "documents.organization_id"],
            name=op.f("fk_document_sections_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_sections")),
        sa.UniqueConstraint(
            "document_id", "ordinal", name=op.f("uq_document_sections_document_id")
        ),
        sa.UniqueConstraint(
            "id", "document_id", "organization_id", name=op.f("uq_document_sections_id")
        ),
    )
    op.create_index(
        "ix_document_sections_org_doc",
        "document_sections",
        ["organization_id", "document_id"],
        unique=False,
    )
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("section_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["section_id", "document_id", "organization_id"],
            [
                "document_sections.id",
                "document_sections.document_id",
                "document_sections.organization_id",
            ],
            name=op.f("fk_document_chunks_section_id_document_sections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunks")),
        sa.UniqueConstraint("document_id", "ordinal", name=op.f("uq_document_chunks_document_id")),
    )
    op.create_index(
        "ix_document_chunks_org_doc",
        "document_chunks",
        ["organization_id", "document_id"],
        unique=False,
    )


def downgrade() -> None:
    # Explicit downgrade removes Phase 3 data; never use it as a setup/reset step.
    op.drop_index("ix_document_chunks_org_doc", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_document_sections_org_doc", table_name="document_sections")
    op.drop_table("document_sections")
    op.drop_index("ix_document_jobs_claim", table_name="document_jobs")
    op.drop_table("document_jobs")
    op.drop_index("ix_documents_org_created", table_name="documents")
    op.drop_table("documents")
