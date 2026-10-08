"""Add emergency schedule overlay and statistics permissions."""

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c8e1f4a2b705"
down_revision = "b6d8e0f2a104"
branch_labels = None
depends_on = None


permission_defs = sa.table(
    "permission_defs",
    sa.column("code", sa.String),
    sa.column("label", sa.String),
    sa.column("scope_type", sa.String),
)
role_permissions = sa.table(
    "role_permissions",
    sa.column("id", sa.Uuid),
    sa.column("role_id", sa.Uuid),
    sa.column("permission_code", sa.String),
    sa.column("tab_id", sa.Uuid),
    sa.column("folder_id", sa.Uuid),
    sa.column("granted", sa.Boolean),
)


def upgrade():
    op.create_table(
        "emergency_schedules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", name="uq_emergency_schedules_order_id"),
    )
    op.create_index("ix_emergency_schedules_created_at", "emergency_schedules", ["created_at"])

    op.add_column("order_lines", sa.Column("emergency_schedule_id", sa.UUID(), nullable=True))
    op.add_column("order_lines", sa.Column("emergency_source_line_id", sa.UUID(), nullable=True))
    op.add_column("order_lines", sa.Column("emergency_action", sa.String(length=20), nullable=True))
    op.add_column(
        "order_lines",
        sa.Column("emergency_active", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_foreign_key(
        "fk_order_lines_emergency_schedule_id_emergency_schedules",
        "order_lines",
        "emergency_schedules",
        ["emergency_schedule_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_order_lines_emergency_source_line_id_order_lines",
        "order_lines",
        "order_lines",
        ["emergency_source_line_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_order_lines_emergency_action_valid",
        "order_lines",
        "emergency_action IS NULL OR emergency_action IN ('add','replace','remove')",
    )
    op.create_index(
        "ix_order_lines_emergency_schedule_active",
        "order_lines",
        ["emergency_schedule_id", "emergency_active"],
    )

    op.create_table(
        "emergency_schedule_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("schedule_id", sa.UUID(), nullable=True),
        sa.Column("order_id", sa.UUID(), nullable=True),
        sa.Column("order_line_id", sa.UUID(), nullable=True),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("old_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column("note", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_line_id"], ["order_lines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["schedule_id"], ["emergency_schedules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_emergency_schedule_history_created_at", "emergency_schedule_history", ["created_at"])
    op.create_index("ix_emergency_schedule_history_order_id", "emergency_schedule_history", ["order_id"])

    op.bulk_insert(
        permission_defs,
        [
            {"code": "emergency.manage", "label": "Управление экстренным расписанием", "scope_type": "global"},
            {"code": "statistics.view", "label": "Просмотр статистики и полного журнала", "scope_type": "global"},
        ],
    )

    # Roles that already administer the system retain immediate access. Other
    # users receive the new capabilities explicitly in the role editor.
    admin_roles = op.get_bind().execute(
        sa.select(role_permissions.c.role_id).where(
            role_permissions.c.permission_code == "admin.manage",
            role_permissions.c.tab_id.is_(None),
            role_permissions.c.folder_id.is_(None),
            role_permissions.c.granted.is_(True),
        )
    ).scalars().all()
    for role_id in set(admin_roles):
        for code in ("emergency.manage", "statistics.view"):
            op.get_bind().execute(
                sa.insert(role_permissions).values(
                    id=uuid.uuid4(),
                    role_id=role_id,
                    permission_code=code,
                    tab_id=None,
                    folder_id=None,
                    granted=True,
                )
            )


def downgrade():
    op.execute(
        "DELETE FROM role_permissions WHERE permission_code IN ('emergency.manage', 'statistics.view')"
    )
    op.execute(
        "DELETE FROM permission_defs WHERE code IN ('emergency.manage', 'statistics.view')"
    )
    op.drop_index("ix_emergency_schedule_history_order_id", table_name="emergency_schedule_history")
    op.drop_index("ix_emergency_schedule_history_created_at", table_name="emergency_schedule_history")
    op.drop_table("emergency_schedule_history")
    op.drop_index("ix_order_lines_emergency_schedule_active", table_name="order_lines")
    op.drop_constraint("ck_order_lines_emergency_action_valid", "order_lines", type_="check")
    op.drop_constraint("fk_order_lines_emergency_source_line_id_order_lines", "order_lines", type_="foreignkey")
    op.drop_constraint("fk_order_lines_emergency_schedule_id_emergency_schedules", "order_lines", type_="foreignkey")
    op.drop_column("order_lines", "emergency_active")
    op.drop_column("order_lines", "emergency_action")
    op.drop_column("order_lines", "emergency_source_line_id")
    op.drop_column("order_lines", "emergency_schedule_id")
    op.drop_index("ix_emergency_schedules_created_at", table_name="emergency_schedules")
    op.drop_table("emergency_schedules")
