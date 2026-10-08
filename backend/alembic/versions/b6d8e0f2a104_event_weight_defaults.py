"""Store reusable weight check settings on event templates."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b6d8e0f2a104"
down_revision = "a1d5e7f9b906"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("event_templates", sa.Column("default_params", postgresql.JSONB(), nullable=True))


def downgrade():
    op.drop_column("event_templates", "default_params")
