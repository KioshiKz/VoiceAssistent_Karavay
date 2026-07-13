"""current order selection

Revision ID: a1d5e7f9b906
Revises: f0c4d6e8a905
Create Date: 2026-07-13 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1d5e7f9b906"
down_revision: Union[str, None] = "f0c4d6e8a905"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


permission_defs_table = sa.table(
    "permission_defs",
    sa.column("code", sa.String),
    sa.column("label", sa.String),
    sa.column("scope_type", sa.String),
)

role_permissions_table = sa.table(
    "role_permissions",
    sa.column("permission_code", sa.String),
)


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_orders_id_workshop_execution_date",
        "orders",
        ["id", "workshop_folder_id", "execution_date"],
    )
    op.create_table(
        "current_order_selections",
        sa.Column("workshop_folder_id", sa.UUID(), nullable=False),
        sa.Column("execution_date", sa.Date(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("selected_by", sa.UUID(), nullable=True),
        sa.Column("selected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id", "workshop_folder_id", "execution_date"],
            ["orders.id", "orders.workshop_folder_id", "orders.execution_date"],
            name="fk_current_order_selections_order_context",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["selected_by"],
            ["users.id"],
            name=op.f("fk_current_order_selections_selected_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workshop_folder_id"],
            ["folders.id"],
            name=op.f("fk_current_order_selections_workshop_folder_id_folders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "workshop_folder_id",
            "execution_date",
            name=op.f("pk_current_order_selections"),
        ),
    )
    op.create_index(
        "ix_current_order_selections_order_id",
        "current_order_selections",
        ["order_id"],
        unique=False,
    )

    op.bulk_insert(
        permission_defs_table,
        [
            {
                "code": "orders.select_current",
                "label": "Назначение актуальной заявки",
                "scope_type": "global",
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        role_permissions_table.delete().where(
            role_permissions_table.c.permission_code == "orders.select_current"
        )
    )
    op.execute(
        permission_defs_table.delete().where(
            permission_defs_table.c.code == "orders.select_current"
        )
    )

    op.drop_index("ix_current_order_selections_order_id", table_name="current_order_selections")
    op.drop_table("current_order_selections")
    op.drop_constraint("uq_orders_id_workshop_execution_date", "orders", type_="unique")
