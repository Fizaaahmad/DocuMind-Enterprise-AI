"""enterprise_operations

Revision ID: 0006_operations
Revises: 0005_structured
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0006_operations"
down_revision: Union[str, Sequence[str], None] = "0005_structured"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Reviewed additive change: two nullable columns, a membership FK, and scope indexes.
    op.add_column("analysis_items", sa.Column("assignee_membership_id", sa.Uuid(), nullable=True))
    op.add_column("analysis_items", sa.Column("assignment_due_date", sa.Date(), nullable=True))
    op.create_index(
        "ix_analysis_items_assignment",
        "analysis_items",
        ["organization_id", "assignee_membership_id", "assignment_due_date"],
        unique=False,
    )
    op.create_index(
        "ix_analysis_items_work",
        "analysis_items",
        ["organization_id", "kind", "review_status"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_analysis_items_assignee_membership_id_memberships"),
        "analysis_items",
        "memberships",
        ["assignee_membership_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Explicit downgrade removes only Phase 6 assignment metadata.
    op.drop_constraint(
        op.f("fk_analysis_items_assignee_membership_id_memberships"),
        "analysis_items",
        type_="foreignkey",
    )
    op.drop_index("ix_analysis_items_work", table_name="analysis_items")
    op.drop_index("ix_analysis_items_assignment", table_name="analysis_items")
    op.drop_column("analysis_items", "assignment_due_date")
    op.drop_column("analysis_items", "assignee_membership_id")
