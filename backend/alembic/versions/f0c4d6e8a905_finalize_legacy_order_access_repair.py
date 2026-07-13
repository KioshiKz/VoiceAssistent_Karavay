"""finalize legacy order access repair

Revision ID: f0c4d6e8a905
Revises: e9b3c5d7a904
Create Date: 2026-07-13 18:45:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f0c4d6e8a905"
down_revision: Union[str, None] = "e9b3c5d7a904"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


app_tabs_table = sa.table(
    "app_tabs",
    sa.column("id", sa.Uuid),
    sa.column("key", sa.String),
)

orders_table = sa.table(
    "orders",
    sa.column("id", sa.Uuid),
    sa.column("workshop_folder_id", sa.Uuid),
)

role_permissions_table = sa.table(
    "role_permissions",
    sa.column("id", sa.Uuid),
    sa.column("role_id", sa.Uuid),
    sa.column("permission_code", sa.String),
    sa.column("tab_id", sa.Uuid),
    sa.column("folder_id", sa.Uuid),
    sa.column("granted", sa.Boolean),
)

LEGACY_WORKSHOP_ID = uuid.UUID("8f3f94cf-4db4-4a40-9bd9-f9d15cc7d9d1")


def _tab_ids(bind) -> dict[str, uuid.UUID]:
    return {
        key: tab_id
        for tab_id, key in bind.execute(
            sa.select(app_tabs_table.c.id, app_tabs_table.c.key).where(
                app_tabs_table.c.key.in_(("orders_list", "current_order", "execution_queue"))
            )
        ).all()
    }


def upgrade() -> None:
    bind = op.get_bind()
    tab_ids = _tab_ids(bind)
    orders_tab_id = tab_ids.get("orders_list")
    if orders_tab_id is None:
        raise RuntimeError("orders_list tab is required to repair order access")

    history_roles = set(
        bind.execute(
            sa.select(role_permissions_table.c.role_id).where(
                role_permissions_table.c.permission_code == "order.history.view",
                role_permissions_table.c.tab_id.is_(None),
                role_permissions_table.c.folder_id.is_(None),
                role_permissions_table.c.granted.is_(True),
            )
        ).scalars()
    )
    explicit_orders_view_roles = set()
    if history_roles:
        explicit_orders_view_roles = set(
            bind.execute(
                sa.select(role_permissions_table.c.role_id).where(
                    role_permissions_table.c.role_id.in_(tuple(history_roles)),
                    role_permissions_table.c.permission_code == "tab.view",
                    role_permissions_table.c.tab_id == orders_tab_id,
                    role_permissions_table.c.folder_id.is_(None),
                )
            ).scalars()
        )
    for role_id in history_roles - explicit_orders_view_roles:
        bind.execute(
            sa.insert(role_permissions_table).values(
                id=uuid.uuid4(),
                role_id=role_id,
                permission_code="tab.view",
                tab_id=orders_tab_id,
                folder_id=None,
                granted=True,
            )
        )

    legacy_has_orders = bind.execute(
        sa.select(orders_table.c.id)
        .where(orders_table.c.workshop_folder_id == LEGACY_WORKSHOP_ID)
        .limit(1)
    ).first()
    if legacy_has_orders is None:
        return

    order_tab_ids = tuple(tab_ids.values())
    relevant_conditions = [
        sa.and_(
            role_permissions_table.c.permission_code == "order.execute",
            role_permissions_table.c.tab_id.is_(None),
            role_permissions_table.c.folder_id.is_(None),
        )
    ]
    if order_tab_ids:
        relevant_conditions.append(
            sa.and_(
                role_permissions_table.c.permission_code.in_(("tab.view", "tab.edit")),
                role_permissions_table.c.tab_id.in_(order_tab_ids),
                role_permissions_table.c.folder_id.is_(None),
            )
        )
    relevant_roles = set(
        bind.execute(
            sa.select(role_permissions_table.c.role_id).where(
                role_permissions_table.c.granted.is_(True),
                sa.or_(*relevant_conditions),
            )
        ).scalars()
    )
    if not relevant_roles:
        return
    explicit_legacy_roles = set(
        bind.execute(
            sa.select(role_permissions_table.c.role_id).where(
                role_permissions_table.c.role_id.in_(tuple(relevant_roles)),
                role_permissions_table.c.permission_code == "folder.view",
                role_permissions_table.c.tab_id.is_(None),
                role_permissions_table.c.folder_id == LEGACY_WORKSHOP_ID,
            )
        ).scalars()
    )
    for role_id in relevant_roles - explicit_legacy_roles:
        bind.execute(
            sa.insert(role_permissions_table).values(
                id=uuid.uuid4(),
                role_id=role_id,
                permission_code="folder.view",
                tab_id=None,
                folder_id=LEGACY_WORKSHOP_ID,
                granted=True,
            )
        )


def downgrade() -> None:
    # Data-only repair; do not remove administrator-confirmed permissions.
    pass
