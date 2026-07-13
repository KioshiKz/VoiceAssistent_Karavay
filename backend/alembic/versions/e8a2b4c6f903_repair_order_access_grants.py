"""repair order access grants after workshop migration

Revision ID: e8a2b4c6f903
Revises: d7f1a3c5e902
Create Date: 2026-07-13 18:10:00.000000

"""
import uuid
from collections import defaultdict
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8a2b4c6f903"
down_revision: Union[str, None] = "d7f1a3c5e902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


app_tabs_table = sa.table(
    "app_tabs",
    sa.column("id", sa.Uuid),
    sa.column("key", sa.String),
)

folders_table = sa.table(
    "folders",
    sa.column("id", sa.Uuid),
    sa.column("parent_id", sa.Uuid),
    sa.column("materialized_path", sa.String),
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


def _tab_id(bind, key: str):
    return bind.execute(
        sa.select(app_tabs_table.c.id).where(app_tabs_table.c.key == key)
    ).scalar_one_or_none()


def _repair_monitoring_access(bind) -> None:
    """Recover grants when the earlier data migration was already applied.

    A granted global history permission is the durable trace left by the old
    monitoring tab after that tab and its scoped rows were cascade-deleted.
    """
    orders_tab_id = _tab_id(bind, "orders_list")
    if orders_tab_id is None:
        raise RuntimeError("orders_list tab is required to repair order access")

    desired_orders_view: dict[uuid.UUID, bool] = defaultdict(bool)
    monitoring_tab_id = _tab_id(bind, "order_monitoring")
    if monitoring_tab_id is not None:
        monitoring_rows = bind.execute(
            sa.select(
                role_permissions_table.c.role_id,
                role_permissions_table.c.granted,
            ).where(
                role_permissions_table.c.tab_id == monitoring_tab_id,
                role_permissions_table.c.permission_code.in_(("tab.view", "tab.edit")),
            )
        ).all()
        for role_id, granted in monitoring_rows:
            desired_orders_view[role_id] |= bool(granted)

        granted_monitoring_roles = {
            role_id for role_id, granted in monitoring_rows if granted
        }
        existing_history = {
            row["role_id"]: row
            for row in bind.execute(
                sa.select(role_permissions_table).where(
                    role_permissions_table.c.role_id.in_(tuple(granted_monitoring_roles)),
                    role_permissions_table.c.permission_code == "order.history.view",
                    role_permissions_table.c.tab_id.is_(None),
                    role_permissions_table.c.folder_id.is_(None),
                )
            ).mappings().all()
        } if granted_monitoring_roles else {}
        for role_id in granted_monitoring_roles:
            existing = existing_history.get(role_id)
            if existing is not None:
                if not existing["granted"]:
                    bind.execute(
                        sa.update(role_permissions_table)
                        .where(role_permissions_table.c.id == existing["id"])
                        .values(granted=True)
                    )
                continue
            bind.execute(
                sa.insert(role_permissions_table).values(
                    id=uuid.uuid4(),
                    role_id=role_id,
                    permission_code="order.history.view",
                    tab_id=None,
                    folder_id=None,
                    granted=True,
                )
            )

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
    for role_id in history_roles:
        desired_orders_view[role_id] = True

    if not desired_orders_view:
        if monitoring_tab_id is not None:
            bind.execute(
                sa.delete(app_tabs_table).where(app_tabs_table.c.id == monitoring_tab_id)
            )
        return
    existing_view = {
        row["role_id"]: row
        for row in bind.execute(
            sa.select(role_permissions_table).where(
                role_permissions_table.c.role_id.in_(tuple(desired_orders_view)),
                role_permissions_table.c.permission_code == "tab.view",
                role_permissions_table.c.tab_id == orders_tab_id,
                role_permissions_table.c.folder_id.is_(None),
            )
        ).mappings().all()
    }
    for role_id, desired_grant in desired_orders_view.items():
        existing = existing_view.get(role_id)
        if existing is not None:
            # A scoped row may have been explicitly changed after c2. Only
            # fill a missing row; never reverse an explicit deny here.
            continue
        bind.execute(
            sa.insert(role_permissions_table).values(
                id=uuid.uuid4(),
                role_id=role_id,
                permission_code="tab.view",
                tab_id=orders_tab_id,
                folder_id=None,
                granted=desired_grant,
            )
        )

    if monitoring_tab_id is not None:
        bind.execute(
            sa.delete(app_tabs_table).where(app_tabs_table.c.id == monitoring_tab_id)
        )


def _roles_with_order_access(bind) -> set[uuid.UUID]:
    tab_ids = set(
        bind.execute(
            sa.select(app_tabs_table.c.id).where(
                app_tabs_table.c.key.in_(("orders_list", "current_order", "execution_queue"))
            )
        ).scalars()
    )
    conditions = [
        sa.and_(
            role_permissions_table.c.permission_code == "order.execute",
            role_permissions_table.c.tab_id.is_(None),
            role_permissions_table.c.folder_id.is_(None),
        )
    ]
    if tab_ids:
        conditions.append(
            sa.and_(
                role_permissions_table.c.permission_code.in_(("tab.view", "tab.edit")),
                role_permissions_table.c.tab_id.in_(tuple(tab_ids)),
                role_permissions_table.c.folder_id.is_(None),
            )
        )
    return set(
        bind.execute(
            sa.select(role_permissions_table.c.role_id).where(
                role_permissions_table.c.granted.is_(True),
                sa.or_(*conditions),
            )
        ).scalars()
    )


def _repair_workshop_visibility(bind) -> None:
    role_ids = _roles_with_order_access(bind)
    if not role_ids:
        return
    legacy_has_orders = bind.execute(
        sa.select(orders_table.c.id)
        .where(orders_table.c.workshop_folder_id == LEGACY_WORKSHOP_ID)
        .limit(1)
    ).first()
    if legacy_has_orders is None:
        return
    existing_pairs = {
        role_id
        for role_id in bind.execute(
            sa.select(role_permissions_table.c.role_id).where(
                role_permissions_table.c.role_id.in_(tuple(role_ids)),
                role_permissions_table.c.permission_code == "folder.view",
                role_permissions_table.c.tab_id.is_(None),
                role_permissions_table.c.folder_id == LEGACY_WORKSHOP_ID,
            )
        ).scalars()
    }
    for role_id in role_ids - existing_pairs:
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


def upgrade() -> None:
    bind = op.get_bind()
    _repair_monitoring_access(bind)
    _repair_workshop_visibility(bind)


def downgrade() -> None:
    # This repair only fills missing grants and cannot distinguish them from
    # permissions later confirmed by an administrator.
    pass
