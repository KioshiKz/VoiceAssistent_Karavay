"""orders roles voice execution

Revision ID: 7e9c2a4f6b31
Revises: 4d2f6b7c9a10
Create Date: 2026-07-05 01:15:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "7e9c2a4f6b31"
down_revision: Union[str, None] = "4d2f6b7c9a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


app_tabs_table = sa.table(
    "app_tabs",
    sa.column("id", sa.Uuid),
    sa.column("key", sa.String),
    sa.column("label", sa.String),
    sa.column("order_index", sa.Integer),
)


def upgrade() -> None:
    op.add_column("roles", sa.Column("order_visibility_ahead", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f("ck_roles_order_visibility_positive"),
        "roles",
        "order_visibility_ahead IS NULL OR order_visibility_ahead > 0",
    )

    op.add_column("orders", sa.Column("workshop_folder_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_orders_workshop_folder_id_folders"),
        "orders",
        "folders",
        ["workshop_folder_id"],
        ["id"],
    )

    op.add_column("order_lines", sa.Column("status", sa.String(length=20), server_default="pending", nullable=False))
    op.add_column("order_lines", sa.Column("cancellation_reason", sa.String(length=1000), nullable=True))
    op.add_column("order_lines", sa.Column("cancelled_by", sa.UUID(), nullable=True))
    op.add_column("order_lines", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("order_lines", sa.Column("last_advanced_by", sa.UUID(), nullable=True))
    op.add_column("order_lines", sa.Column("last_advanced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "order_lines",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_order_lines_order_line_status_valid"),
        "order_lines",
        "status IN ('pending','in_progress','completed','cancelled')",
    )
    op.create_foreign_key(
        op.f("fk_order_lines_cancelled_by_users"),
        "order_lines",
        "users",
        ["cancelled_by"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_order_lines_last_advanced_by_users"),
        "order_lines",
        "users",
        ["last_advanced_by"],
        ["id"],
    )

    op.create_table(
        "order_line_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_line_id", sa.UUID(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("note", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_order_line_history_actor_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["order_line_id"],
            ["order_lines.id"],
            name=op.f("fk_order_line_history_order_line_id_order_lines"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_line_history")),
    )

    op.drop_constraint(op.f("ck_recipe_steps_step_shape"), "recipe_steps", type_="check")
    op.create_check_constraint(
        op.f("ck_recipe_steps_step_shape"),
        "recipe_steps",
        "(step_type = 'ingredient' AND ingredient_id IS NOT NULL AND event_template_id IS NULL "
        "AND quantity_canonical IS NOT NULL) OR "
        "(step_type = 'event' AND event_template_id IS NOT NULL AND ingredient_id IS NULL) OR "
        "(step_type = 'ingredient_event' AND ingredient_id IS NOT NULL AND event_template_id IS NOT NULL "
        "AND quantity_canonical IS NOT NULL)",
    )
    op.drop_constraint(op.f("ck_execution_plan_steps_exec_step_type_valid"), "execution_plan_steps", type_="check")
    op.create_check_constraint(
        op.f("ck_execution_plan_steps_exec_step_type_valid"),
        "execution_plan_steps",
        "step_type IN ('ingredient','event','ingredient_event')",
    )

    op.bulk_insert(
        app_tabs_table,
        [{"id": uuid.uuid4(), "key": "execution_queue", "label": "Выполнение заявки", "order_index": 6}],
    )


def downgrade() -> None:
    op.execute("DELETE FROM app_tabs WHERE key = 'execution_queue'")

    op.drop_constraint(op.f("ck_execution_plan_steps_exec_step_type_valid"), "execution_plan_steps", type_="check")
    op.create_check_constraint(
        op.f("ck_execution_plan_steps_exec_step_type_valid"),
        "execution_plan_steps",
        "step_type IN ('ingredient','event')",
    )
    op.drop_constraint(op.f("ck_recipe_steps_step_shape"), "recipe_steps", type_="check")
    op.create_check_constraint(
        op.f("ck_recipe_steps_step_shape"),
        "recipe_steps",
        "(step_type = 'ingredient' AND ingredient_id IS NOT NULL AND event_template_id IS NULL "
        "AND quantity_canonical IS NOT NULL) OR "
        "(step_type = 'event' AND event_template_id IS NOT NULL AND ingredient_id IS NULL)",
    )

    op.drop_table("order_line_history")

    op.drop_constraint(op.f("fk_order_lines_last_advanced_by_users"), "order_lines", type_="foreignkey")
    op.drop_constraint(op.f("fk_order_lines_cancelled_by_users"), "order_lines", type_="foreignkey")
    op.drop_constraint(op.f("ck_order_lines_order_line_status_valid"), "order_lines", type_="check")
    op.drop_column("order_lines", "updated_at")
    op.drop_column("order_lines", "last_advanced_at")
    op.drop_column("order_lines", "last_advanced_by")
    op.drop_column("order_lines", "cancelled_at")
    op.drop_column("order_lines", "cancelled_by")
    op.drop_column("order_lines", "cancellation_reason")
    op.drop_column("order_lines", "status")

    op.drop_constraint(op.f("fk_orders_workshop_folder_id_folders"), "orders", type_="foreignkey")
    op.drop_column("orders", "workshop_folder_id")

    op.drop_constraint(op.f("ck_roles_order_visibility_positive"), "roles", type_="check")
    op.drop_column("roles", "order_visibility_ahead")
