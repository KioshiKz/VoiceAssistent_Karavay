"""decimal quantities and count measure

Revision ID: 4d2f6b7c9a10
Revises: 3c7fefa9ad85
Create Date: 2026-07-04 23:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4d2f6b7c9a10"
down_revision: Union[str, None] = "3c7fefa9ad85"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE ingredients DROP CONSTRAINT ck_ingredients_measure_type_valid")
    op.execute(
        "ALTER TABLE ingredients ADD CONSTRAINT ck_ingredients_measure_type_valid "
        "CHECK (measure_type IN ('weight','volume','time','temperature','count'))"
    )
    op.alter_column(
        "recipe_steps",
        "quantity_canonical",
        existing_type=sa.Integer(),
        type_=sa.Numeric(14, 3),
        existing_nullable=True,
        postgresql_using="quantity_canonical::numeric(14,3)",
    )
    op.alter_column(
        "execution_plan_steps",
        "quantity_canonical_computed",
        existing_type=sa.Integer(),
        type_=sa.Numeric(14, 3),
        existing_nullable=True,
        postgresql_using="quantity_canonical_computed::numeric(14,3)",
    )


def downgrade() -> None:
    op.alter_column(
        "execution_plan_steps",
        "quantity_canonical_computed",
        existing_type=sa.Numeric(14, 3),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="round(quantity_canonical_computed)::integer",
    )
    op.alter_column(
        "recipe_steps",
        "quantity_canonical",
        existing_type=sa.Numeric(14, 3),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="round(quantity_canonical)::integer",
    )
    op.execute("ALTER TABLE ingredients DROP CONSTRAINT ck_ingredients_measure_type_valid")
    op.execute(
        "ALTER TABLE ingredients ADD CONSTRAINT ck_ingredients_measure_type_valid "
        "CHECK (measure_type IN ('weight','volume','time','temperature'))"
    )
