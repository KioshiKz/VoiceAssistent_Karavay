"""Prevent concurrent duplicate overlays for one source line."""

from alembic import op

revision = "d9f2a5b3c806"
down_revision = "c8e1f4a2b705"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_order_lines_emergency_source",
        "order_lines",
        ["emergency_schedule_id", "emergency_source_line_id"],
    )


def downgrade():
    op.drop_constraint("uq_order_lines_emergency_source", "order_lines", type_="unique")
