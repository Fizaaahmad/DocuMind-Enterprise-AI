"""Provider request accounting and explicit analysis retry generations.

Revision ID: 0007_provider_requests
Revises: 0006_operations
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007_provider_requests"
down_revision = "0006_operations"
branch_labels = depends_on = None


def upgrade():
    # Additive only; existing analysis/review data is not rewritten.
    op.add_column(
        "analysis_runs",
        sa.Column("provider_generation", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "provider_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("operation_key", sa.String(180), nullable=False, unique=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("document_ids", postgresql.JSONB(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False),
        sa.Column("reserved_cost", sa.Numeric(16, 8), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("estimated_cost", sa.Numeric(16, 8)),
        sa.Column("response", postgresql.JSONB()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_provider_requests_budget", "provider_requests", ["organization_id", "created_at"]
    )


def downgrade():
    # Explicit downgrade discards Phase 8 accounting/cache, never document/review tables.
    op.drop_table("provider_requests")
    op.drop_column("analysis_runs", "provider_generation")
