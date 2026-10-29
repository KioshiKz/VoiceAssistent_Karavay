"""Product yield unit (pieces or kilograms) and fractional quantities.

Weight products (creams, dough, fillings) are produced and ordered in
kilograms, often fractional; piece products keep whole quantities, which the
application enforces.
"""
from alembic import op
import sqlalchemy as sa

revision = "a7c3e9f1b246"
down_revision = "f2b5c8d0e123"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("yield_unit", sa.String(8), nullable=False, server_default="pcs"))
    op.create_check_constraint(op.f("ck_products_yield_unit_valid"), "products", "yield_unit IN ('pcs','kg')")
    op.alter_column("products", "base_quantity", type_=sa.Numeric(12, 3), existing_type=sa.Integer(), existing_nullable=False)
    op.alter_column("order_lines", "quantity", type_=sa.Numeric(12, 3), existing_type=sa.Integer(), existing_nullable=False)


def downgrade():
    # Fractional values cannot be represented as integers; refuse silently losing them.
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM products WHERE base_quantity <> trunc(base_quantity)) "
               "OR EXISTS (SELECT 1 FROM order_lines WHERE quantity <> trunc(quantity)) "
               "THEN RAISE EXCEPTION 'fractional quantities present'; END IF; END $$")
    op.alter_column("order_lines", "quantity", type_=sa.Integer(), existing_type=sa.Numeric(12, 3), existing_nullable=False,
                    postgresql_using="quantity::integer")
    op.alter_column("products", "base_quantity", type_=sa.Integer(), existing_type=sa.Numeric(12, 3), existing_nullable=False,
                    postgresql_using="base_quantity::integer")
    op.drop_constraint(op.f("ck_products_yield_unit_valid"), "products", type_="check")
    op.drop_column("products", "yield_unit")
