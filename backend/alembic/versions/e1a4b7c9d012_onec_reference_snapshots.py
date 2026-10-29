"""Read-only 1C reference snapshots, isolated from production data."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e1a4b7c9d012"
down_revision = "d9f2a5b3c806"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "onec_records",
        sa.Column("source", sa.String(64), primary_key=True),
        sa.Column("entity", sa.String(100), primary_key=True),
        sa.Column("ref", sa.Uuid(), primary_key=True),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("onec_records")
