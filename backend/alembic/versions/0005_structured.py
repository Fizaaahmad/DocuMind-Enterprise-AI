"""structured_intelligence

Revision ID: 0005_structured
Revises: 0004_intelligence
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_structured"
down_revision: Union[str, Sequence[str], None] = "0004_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Reviewed additive migration: new Phase 5 tables only; existing data is preserved.
    op.create_table(
        "analysis_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_analysis_templates_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["analysis_templates.id"],
            name=op.f("fk_analysis_templates_parent_id_analysis_templates"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_templates")),
    )
    op.create_index(
        "ix_analysis_templates_org",
        "analysis_templates",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "source_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("current", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["documents.id", "documents.organization_id"],
            name=op.f("fk_source_revisions_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_revisions")),
        sa.UniqueConstraint(
            "document_id", "fingerprint", name=op.f("uq_source_revisions_document_id")
        ),
        sa.UniqueConstraint("id", "organization_id", name=op.f("uq_source_revisions_id")),
    )
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("creator_id", sa.Uuid(), nullable=True),
        sa.Column("left_revision_id", sa.Uuid(), nullable=True),
        sa.Column("right_revision_id", sa.Uuid(), nullable=True),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("engine", sa.String(length=20), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("coverage", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["users.id"],
            name=op.f("fk_analysis_runs_creator_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["left_revision_id"],
            ["source_revisions.id"],
            name=op.f("fk_analysis_runs_left_revision_id_source_revisions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_analysis_runs_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["right_revision_id"],
            ["source_revisions.id"],
            name=op.f("fk_analysis_runs_right_revision_id_source_revisions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["analysis_templates.id"],
            name=op.f("fk_analysis_runs_template_id_analysis_templates"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_runs")),
        sa.UniqueConstraint("id", "organization_id", name=op.f("uq_analysis_runs_id")),
    )
    op.create_index(
        "ix_analysis_runs_claim", "analysis_runs", ["state", "available_at"], unique=False
    )
    op.create_index(
        "ix_analysis_runs_org", "analysis_runs", ["organization_id", "created_at"], unique=False
    )
    op.create_table(
        "revision_sections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["revision_id", "organization_id"],
            ["source_revisions.id", "source_revisions.organization_id"],
            name=op.f("fk_revision_sections_revision_id_source_revisions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_revision_sections")),
        sa.UniqueConstraint(
            "id", "revision_id", "organization_id", name=op.f("uq_revision_sections_id")
        ),
        sa.UniqueConstraint(
            "revision_id", "ordinal", name=op.f("uq_revision_sections_revision_id")
        ),
    )
    op.create_table(
        "analysis_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("original", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("corrected", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validation", sa.String(length=30), nullable=False),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.Column("obligation_status", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id", "organization_id"],
            ["analysis_runs.id", "analysis_runs.organization_id"],
            name=op.f("fk_analysis_items_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_items")),
    )
    op.create_index(
        "ix_analysis_items_run", "analysis_items", ["organization_id", "run_id"], unique=False
    )
    op.create_table(
        "analysis_review_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_analysis_review_events_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["analysis_items.id"],
            name=op.f("fk_analysis_review_events_item_id_analysis_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_review_events")),
    )


def downgrade() -> None:
    # Explicit downgrade removes Phase 5 data only; never invoked automatically.
    op.drop_table("analysis_review_events")
    op.drop_index("ix_analysis_items_run", table_name="analysis_items")
    op.drop_table("analysis_items")
    op.drop_table("revision_sections")
    op.drop_index("ix_analysis_runs_org", table_name="analysis_runs")
    op.drop_index("ix_analysis_runs_claim", table_name="analysis_runs")
    op.drop_table("analysis_runs")
    op.drop_table("source_revisions")
    op.drop_index("ix_analysis_templates_org", table_name="analysis_templates")
    op.drop_table("analysis_templates")
