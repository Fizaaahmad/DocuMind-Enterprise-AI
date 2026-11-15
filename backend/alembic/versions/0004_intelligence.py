"""Add local vectors, indexing state, and private assistant history.

Revision ID: 0004_intelligence
Revises: 0003_documents
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004_intelligence"
down_revision = "0003_documents"
branch_labels = None
depends_on = None


def upgrade():
    # Additive: preserve originals, extracted content, identity, and memberships.
    op.add_column(
        "documents",
        sa.Column("index_status", sa.String(16), server_default="unindexed", nullable=False),
    )
    op.add_column("documents", sa.Column("index_error", sa.String(500)))
    op.add_column("documents", sa.Column("index_profile", sa.String(64)))
    op.create_unique_constraint(
        "uq_chunk_identity_scope", "document_chunks", ["id", "document_id", "organization_id"]
    )
    op.drop_constraint(op.f("ck_document_jobs_kind"), "document_jobs", type_="check")
    op.create_check_constraint("kind", "document_jobs", "kind IN ('process','delete','embed')")
    op.create_table(
        "chunk_embeddings",
        sa.Column("chunk_id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("profile", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.ForeignKeyConstraint(
            ["chunk_id", "document_id", "organization_id"],
            [
                "document_chunks.id",
                "document_chunks.document_id",
                "document_chunks.organization_id",
            ],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_chunk_embeddings_scope",
        "chunk_embeddings",
        ["organization_id", "profile", "document_id"],
    )
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_ai_conversations_owner", "ai_conversations", ["organization_id", "user_id"])
    op.create_table(
        "ai_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("is_mock", sa.Boolean(), nullable=False),
        sa.Column("citations", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_ai_messages_conversation", "ai_messages", ["conversation_id", "created_at"])
    op.create_table(
        "ai_usage",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("requests", sa.Integer(), nullable=False),
    )


def downgrade():
    # Explicit downgrade removes only Phase 4 data; never called automatically.
    op.drop_table("ai_usage")
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
    op.drop_table("chunk_embeddings")
    op.drop_constraint(op.f("ck_document_jobs_kind"), "document_jobs", type_="check")
    op.create_check_constraint("kind", "document_jobs", "kind IN ('process','delete')")
    op.drop_constraint("uq_chunk_identity_scope", "document_chunks", type_="unique")
    for column in ["index_profile", "index_error", "index_status"]:
        op.drop_column("documents", column)
