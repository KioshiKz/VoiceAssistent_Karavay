"""force-complete marker and legacy workshop normalization

Revision ID: d7f1a3c5e902
Revises: c2d8e4f6a901
Create Date: 2026-07-13 17:15:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7f1a3c5e902"
down_revision: Union[str, None] = "c2d8e4f6a901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


folders_table = sa.table(
    "folders",
    sa.column("id", sa.Uuid),
    sa.column("parent_id", sa.Uuid),
    sa.column("name", sa.String),
    sa.column("materialized_path", sa.String),
    sa.column("depth", sa.Integer),
    sa.column("created_by", sa.Uuid),
)

orders_table = sa.table(
    "orders",
    sa.column("id", sa.Uuid),
    sa.column("workshop_folder_id", sa.Uuid),
)

app_tabs_table = sa.table(
    "app_tabs",
    sa.column("id", sa.Uuid),
    sa.column("key", sa.String),
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


def _grant_folder_view(bind, folder_id: uuid.UUID, role_ids: set[uuid.UUID]) -> None:
    if not role_ids:
        return

    existing_rows = bind.execute(
        sa.select(role_permissions_table).where(
            role_permissions_table.c.role_id.in_(role_ids),
            role_permissions_table.c.permission_code == "folder.view",
            role_permissions_table.c.tab_id.is_(None),
            role_permissions_table.c.folder_id == folder_id,
        )
    ).mappings().all()
    existing_by_role = {row["role_id"]: row for row in existing_rows}

    for role_id in role_ids:
        existing = existing_by_role.get(role_id)
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
                permission_code="folder.view",
                tab_id=None,
                folder_id=folder_id,
                granted=True,
            )
        )


def _preserve_nested_order_visibility(bind) -> None:
    """Copy effective nested-folder visibility to each normalized root."""
    assigned_folders = bind.execute(
        sa.select(folders_table.c.id, folders_table.c.materialized_path)
        .select_from(
            orders_table.join(
                folders_table,
                orders_table.c.workshop_folder_id == folders_table.c.id,
            )
        )
        .where(folders_table.c.parent_id.is_not(None))
        .distinct()
    ).all()
    if not assigned_folders:
        return

    paths_by_folder: dict[uuid.UUID, list[uuid.UUID]] = {}
    all_ancestor_ids: set[uuid.UUID] = set()
    for folder_id, materialized_path in assigned_folders:
        path = [uuid.UUID(part) for part in materialized_path.split("/") if part]
        if not path:
            continue
        paths_by_folder[folder_id] = path
        all_ancestor_ids.update(path)

    permission_rows = bind.execute(
        sa.select(
            role_permissions_table.c.role_id,
            role_permissions_table.c.folder_id,
            role_permissions_table.c.granted,
        ).where(
            role_permissions_table.c.permission_code == "folder.view",
            role_permissions_table.c.tab_id.is_(None),
            role_permissions_table.c.folder_id.in_(all_ancestor_ids),
        )
    ).all()
    permissions_by_folder: dict[uuid.UUID, list[tuple[uuid.UUID, bool]]] = {}
    for role_id, permission_folder_id, granted in permission_rows:
        permissions_by_folder.setdefault(permission_folder_id, []).append((role_id, bool(granted)))

    grants_by_root: dict[uuid.UUID, set[uuid.UUID]] = {}
    for path in paths_by_folder.values():
        effective_by_role: dict[uuid.UUID, tuple[int, bool]] = {}
        for depth, ancestor_id in enumerate(path):
            for role_id, granted in permissions_by_folder.get(ancestor_id, []):
                effective_by_role[role_id] = (depth, granted)
        root_id = path[0]
        grants_by_root.setdefault(root_id, set()).update(
            role_id for role_id, (_, granted) in effective_by_role.items() if granted
        )

    for root_id, role_ids in grants_by_root.items():
        _grant_folder_view(bind, root_id, role_ids)


def _roles_with_order_access(bind) -> set[uuid.UUID]:
    order_tab_ids = set(
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
    if order_tab_ids:
        conditions.append(
            sa.and_(
                role_permissions_table.c.permission_code.in_(("tab.view", "tab.edit")),
                role_permissions_table.c.tab_id.in_(order_tab_ids),
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


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column("orders", sa.Column("force_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("force_completed_by", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_orders_force_completed_by_users"),
        "orders",
        "users",
        ["force_completed_by"],
        ["id"],
    )

    _preserve_nested_order_visibility(bind)
    op.execute(
        """
        UPDATE orders AS orders_to_fix
        SET workshop_folder_id = split_part(trim(both '/' from assigned_folder.materialized_path), '/', 1)::uuid
        FROM folders AS assigned_folder
        WHERE orders_to_fix.workshop_folder_id = assigned_folder.id
          AND assigned_folder.parent_id IS NOT NULL
        """
    )

    null_workshop_orders = bind.execute(
        sa.select(sa.func.count()).select_from(orders_table).where(orders_table.c.workshop_folder_id.is_(None))
    ).scalar_one()
    if null_workshop_orders:
        bind.execute(
            sa.insert(folders_table).values(
                id=LEGACY_WORKSHOP_ID,
                parent_id=None,
                name="Нераспределённые заявки",
                materialized_path=f"/{LEGACY_WORKSHOP_ID}/",
                depth=0,
                created_by=None,
            )
        )
        bind.execute(
            sa.update(orders_table)
            .where(orders_table.c.workshop_folder_id.is_(None))
            .values(workshop_folder_id=LEGACY_WORKSHOP_ID)
        )
        _grant_folder_view(bind, LEGACY_WORKSHOP_ID, _roles_with_order_access(bind))


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.update(orders_table)
        .where(orders_table.c.workshop_folder_id == LEGACY_WORKSHOP_ID)
        .values(workshop_folder_id=None)
    )
    bind.execute(sa.delete(folders_table).where(folders_table.c.id == LEGACY_WORKSHOP_ID))

    op.drop_constraint(op.f("fk_orders_force_completed_by_users"), "orders", type_="foreignkey")
    op.drop_column("orders", "force_completed_by")
    op.drop_column("orders", "force_completed_at")
