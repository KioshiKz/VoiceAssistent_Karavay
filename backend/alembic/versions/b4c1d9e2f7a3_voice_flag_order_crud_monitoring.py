"""voice flag, order-line crud, cross-order monitoring

Revision ID: b4c1d9e2f7a3
Revises: 9f3a1b2c4d5e
Create Date: 2026-07-13 05:00:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4c1d9e2f7a3"
down_revision: Union[str, None] = "9f3a1b2c4d5e"
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
    op.add_column(
        "users",
        sa.Column("voice_assistant_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
    )

    op.add_column("order_line_history", sa.Column("order_id", sa.UUID(), nullable=True))
    op.add_column("order_line_history", sa.Column("product_name_raw", sa.String(length=255), nullable=True))
    op.create_foreign_key(
        op.f("fk_order_line_history_order_id_orders"),
        "order_line_history",
        "orders",
        ["order_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint(
        op.f("fk_order_line_history_order_line_id_order_lines"), "order_line_history", type_="foreignkey"
    )
    op.alter_column("order_line_history", "order_line_id", existing_type=sa.UUID(), nullable=True)
    op.create_foreign_key(
        op.f("fk_order_line_history_order_line_id_order_lines"),
        "order_line_history",
        "order_lines",
        ["order_line_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.bulk_insert(
        app_tabs_table,
        [
            {"id": uuid.uuid4(), "key": "orders_list", "label": "Все заявки", "order_index": 7},
            {"id": uuid.uuid4(), "key": "order_monitoring", "label": "Мониторинг заявок", "order_index": 8},
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM app_tabs WHERE key IN ('orders_list', 'order_monitoring')")

    op.drop_constraint(
        op.f("fk_order_line_history_order_line_id_order_lines"), "order_line_history", type_="foreignkey"
    )
    op.execute("DELETE FROM order_line_history WHERE order_line_id IS NULL")
    op.alter_column("order_line_history", "order_line_id", existing_type=sa.UUID(), nullable=False)
    op.create_foreign_key(
        op.f("fk_order_line_history_order_line_id_order_lines"),
        "order_line_history",
        "order_lines",
        ["order_line_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(op.f("fk_order_line_history_order_id_orders"), "order_line_history", type_="foreignkey")
    op.drop_column("order_line_history", "product_name_raw")
    op.drop_column("order_line_history", "order_id")

    op.drop_column("users", "voice_assistant_enabled")
