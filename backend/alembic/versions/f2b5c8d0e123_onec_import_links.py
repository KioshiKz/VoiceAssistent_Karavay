"""Links between 1C references and imported products/ingredients."""
from alembic import op
import sqlalchemy as sa

revision = "f2b5c8d0e123"
down_revision = "e1a4b7c9d012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "onec_links",
        sa.Column("source", sa.String(64), primary_key=True),
        sa.Column("entity", sa.String(32), primary_key=True),
        sa.Column("ref", sa.Uuid(), primary_key=True),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("source_hash", sa.String(64)),
        sa.Column("local_hash", sa.String(64)),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("onec_links")
