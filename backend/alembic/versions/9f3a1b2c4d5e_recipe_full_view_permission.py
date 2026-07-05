"""recipe full view permission

Revision ID: 9f3a1b2c4d5e
Revises: 7e9c2a4f6b31
Create Date: 2026-07-05 04:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f3a1b2c4d5e"
down_revision: Union[str, None] = "7e9c2a4f6b31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


permission_defs_table = sa.table(
    "permission_defs",
    sa.column("code", sa.String),
    sa.column("label", sa.String),
    sa.column("scope_type", sa.String),
)


def upgrade() -> None:
    op.bulk_insert(
        permission_defs_table,
        [
            {
                "code": "recipe.full_view",
                "label": "Полный просмотр рецептуры",
                "scope_type": "global",
            }
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_code = 'recipe.full_view'")
    op.execute("DELETE FROM permission_defs WHERE code = 'recipe.full_view'")
