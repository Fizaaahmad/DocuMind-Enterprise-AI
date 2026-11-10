"""Enable pgvector; no application tables in Phase 1."""
from alembic import op

revision = "0001_enable_pgvector"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # Preserve a potentially shared extension and any future dependent data.
    # Resetting this revision does not uninstall pgvector.
    pass
