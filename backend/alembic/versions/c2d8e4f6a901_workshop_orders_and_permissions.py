"""workshop orders and action permissions

Revision ID: c2d8e4f6a901
Revises: b4c1d9e2f7a3
Create Date: 2026-07-13 16:30:00.000000

"""
import uuid
from collections import defaultdict
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d8e4f6a901"
down_revision: Union[str, None] = "b4c1d9e2f7a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


permission_defs_table = sa.table(
    "permission_defs",
    sa.column("code", sa.String),
    sa.column("label", sa.String),
    sa.column("scope_type", sa.String),
)

app_tabs_table = sa.table(
    "app_tabs",
    sa.column("id", sa.Uuid),
    sa.column("key", sa.String),
    sa.column("label", sa.String),
    sa.column("order_index", sa.Integer),
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

NEW_PERMISSION_DEFS = [
    ("order.line.create", "Добавление продукции в заявку", "global"),
    ("order.line.delete", "Удаление продукции из заявки", "global"),
    ("order.history.view", "Просмотр истории заявок", "global"),
    ("order.force_complete", "Принудительное завершение заявки", "global"),
]


def _tab_id(bind, key: str):
    return bind.execute(sa.select(app_tabs_table.c.id).where(app_tabs_table.c.key == key)).scalar_one_or_none()


def _merge_tab_permissions(bind, source_tab_id, target_tab_id) -> None:
    if source_tab_id is None or target_tab_id is None:
        return

    relevant_codes = ("tab.view", "tab.edit")
    target_rows = bind.execute(
        sa.select(role_permissions_table).where(
            role_permissions_table.c.tab_id == target_tab_id,
            role_permissions_table.c.permission_code.in_(relevant_codes),
        )
    ).mappings().all()

    grouped_targets: dict[tuple[uuid.UUID, str], list] = defaultdict(list)
    for row in target_rows:
        grouped_targets[(row["role_id"], row["permission_code"])].append(row)

    target_by_key = {}
    for key, rows in grouped_targets.items():
        keeper = rows[0]
        granted = any(bool(row["granted"]) for row in rows)
        bind.execute(
            sa.update(role_permissions_table)
            .where(role_permissions_table.c.id == keeper["id"])
            .values(granted=granted)
        )
        if len(rows) > 1:
            bind.execute(
                sa.delete(role_permissions_table).where(
                    role_permissions_table.c.id.in_([row["id"] for row in rows[1:]])
                )
            )
        target_by_key[key] = {"id": keeper["id"], "granted": granted}

    source_rows = bind.execute(
        sa.select(role_permissions_table).where(
            role_permissions_table.c.tab_id == source_tab_id,
            role_permissions_table.c.permission_code.in_(relevant_codes),
        )
    ).mappings().all()
    source_grants: dict[tuple[uuid.UUID, str], bool] = defaultdict(bool)
    for row in source_rows:
        source_grants[(row["role_id"], row["permission_code"])] |= bool(row["granted"])

    for (role_id, permission_code), granted in source_grants.items():
        existing = target_by_key.get((role_id, permission_code))
        if existing is not None:
            bind.execute(
                sa.update(role_permissions_table)
                .where(role_permissions_table.c.id == existing["id"])
                .values(granted=bool(existing["granted"]) or granted)
            )
            continue
        bind.execute(
            sa.insert(role_permissions_table).values(
                id=uuid.uuid4(),
                role_id=role_id,
                permission_code=permission_code,
                tab_id=target_tab_id,
                folder_id=None,
                granted=granted,
            )
        )


def _migrate_monitoring_to_history(bind, monitoring_tab_id) -> None:
    if monitoring_tab_id is None:
        return

    role_ids = set(
        bind.execute(
            sa.select(role_permissions_table.c.role_id).where(
                role_permissions_table.c.tab_id == monitoring_tab_id,
                role_permissions_table.c.permission_code.in_(("tab.view", "tab.edit")),
                role_permissions_table.c.granted.is_(True),
            )
        ).scalars()
    )

    existing_rows = bind.execute(
        sa.select(role_permissions_table).where(
            role_permissions_table.c.permission_code == "order.history.view",
            role_permissions_table.c.tab_id.is_(None),
            role_permissions_table.c.folder_id.is_(None),
        )
    ).mappings().all()
    grouped_existing: dict[uuid.UUID, list] = defaultdict(list)
    for row in existing_rows:
        grouped_existing[row["role_id"]].append(row)

    existing_role_ids: set[uuid.UUID] = set()
    for role_id, rows in grouped_existing.items():
        keeper = rows[0]
        granted = any(bool(row["granted"]) for row in rows) or role_id in role_ids
        bind.execute(
            sa.update(role_permissions_table)
            .where(role_permissions_table.c.id == keeper["id"])
            .values(granted=granted)
        )
        if len(rows) > 1:
            bind.execute(
                sa.delete(role_permissions_table).where(
                    role_permissions_table.c.id.in_([row["id"] for row in rows[1:]])
                )
            )
        existing_role_ids.add(role_id)

    for role_id in role_ids - existing_role_ids:
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


def _merge_monitoring_into_orders_view(bind, monitoring_tab_id, orders_tab_id) -> None:
    """Preserve access to the UI that absorbed the old monitoring tab."""
    if monitoring_tab_id is None or orders_tab_id is None:
        return

    source_rows = bind.execute(
        sa.select(role_permissions_table).where(
            role_permissions_table.c.tab_id == monitoring_tab_id,
            role_permissions_table.c.permission_code.in_(("tab.view", "tab.edit")),
        )
    ).mappings().all()
    source_grants: dict[uuid.UUID, bool] = defaultdict(bool)
    for row in source_rows:
        source_grants[row["role_id"]] |= bool(row["granted"])

    target_rows = bind.execute(
        sa.select(role_permissions_table).where(
            role_permissions_table.c.tab_id == orders_tab_id,
            role_permissions_table.c.permission_code == "tab.view",
        )
    ).mappings().all()
    targets_by_role: dict[uuid.UUID, list] = defaultdict(list)
    for row in target_rows:
        targets_by_role[row["role_id"]].append(row)

    target_by_role = {}
    for role_id, rows in targets_by_role.items():
        keeper = rows[0]
        granted = any(bool(row["granted"]) for row in rows)
        bind.execute(
            sa.update(role_permissions_table)
            .where(role_permissions_table.c.id == keeper["id"])
            .values(granted=granted)
        )
        if len(rows) > 1:
            bind.execute(
                sa.delete(role_permissions_table).where(
                    role_permissions_table.c.id.in_([row["id"] for row in rows[1:]])
                )
            )
        target_by_role[role_id] = {"id": keeper["id"], "granted": granted}

    for role_id, granted in source_grants.items():
        existing = target_by_role.get(role_id)
        if existing is not None:
            bind.execute(
                sa.update(role_permissions_table)
                .where(role_permissions_table.c.id == existing["id"])
                .values(granted=bool(existing["granted"]) or granted)
            )
            continue
        bind.execute(
            sa.insert(role_permissions_table).values(
                id=uuid.uuid4(),
                role_id=role_id,
                permission_code="tab.view",
                tab_id=orders_tab_id,
                folder_id=None,
                granted=granted,
            )
        )


def _deduplicate_role_permissions(bind) -> None:
    rows = bind.execute(sa.select(role_permissions_table)).mappings().all()
    grouped: dict[tuple[uuid.UUID, str, uuid.UUID | None, uuid.UUID | None], list] = defaultdict(list)
    for row in rows:
        key = (row["role_id"], row["permission_code"], row["tab_id"], row["folder_id"])
        grouped[key].append(row)

    for duplicate_rows in grouped.values():
        if len(duplicate_rows) <= 1:
            continue
        keeper = duplicate_rows[0]
        bind.execute(
            sa.update(role_permissions_table)
            .where(role_permissions_table.c.id == keeper["id"])
            .values(granted=any(bool(row["granted"]) for row in duplicate_rows))
        )
        bind.execute(
            sa.delete(role_permissions_table).where(
                role_permissions_table.c.id.in_([row["id"] for row in duplicate_rows[1:]])
            )
        )


def upgrade() -> None:
    bind = op.get_bind()

    op.alter_column("orders", "source_filename", existing_type=sa.String(length=255), nullable=True)

    op.bulk_insert(
        permission_defs_table,
        [{"code": code, "label": label, "scope_type": scope} for code, label, scope in NEW_PERMISSION_DEFS],
    )

    upload_tab_id = _tab_id(bind, "upload_order")
    orders_tab_id = _tab_id(bind, "orders_list")
    monitoring_tab_id = _tab_id(bind, "order_monitoring")
    _merge_tab_permissions(bind, upload_tab_id, orders_tab_id)
    _merge_monitoring_into_orders_view(bind, monitoring_tab_id, orders_tab_id)
    _migrate_monitoring_to_history(bind, monitoring_tab_id)
    _deduplicate_role_permissions(bind)

    op.drop_constraint("uq_role_perm_scope", "role_permissions", type_="unique")
    op.create_unique_constraint(
        "uq_role_perm_scope",
        "role_permissions",
        ["role_id", "permission_code", "tab_id", "folder_id"],
        postgresql_nulls_not_distinct=True,
    )

    bind.execute(
        sa.update(app_tabs_table).where(app_tabs_table.c.key == "orders_list").values(label="Заявки")
    )
    bind.execute(sa.delete(app_tabs_table).where(app_tabs_table.c.key.in_(("upload_order", "order_monitoring"))))

    op.execute(
        """
        UPDATE order_line_history AS history
        SET order_id = COALESCE(history.order_id, line.order_id),
            product_name_raw = COALESCE(history.product_name_raw, line.product_name_raw)
        FROM order_lines AS line
        WHERE history.order_line_id = line.id
          AND (history.order_id IS NULL OR history.product_name_raw IS NULL)
        """
    )

    op.create_index(
        "ix_orders_workshop_date_uploaded",
        "orders",
        ["workshop_folder_id", "execution_date", "uploaded_at"],
        unique=False,
    )
    op.create_index(
        "ix_order_lines_order_id_status",
        "order_lines",
        ["order_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_order_line_history_order_date",
        "order_line_history",
        ["order_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_constraint("uq_role_perm_scope", "role_permissions", type_="unique")
    op.create_unique_constraint(
        "uq_role_perm_scope",
        "role_permissions",
        ["role_id", "permission_code", "tab_id", "folder_id"],
    )

    op.drop_index("ix_order_line_history_order_date", table_name="order_line_history")
    op.drop_index("ix_order_lines_order_id_status", table_name="order_lines")
    op.drop_index("ix_orders_workshop_date_uploaded", table_name="orders")

    bind.execute(
        sa.insert(app_tabs_table),
        [
            {"id": uuid.uuid4(), "key": "upload_order", "label": "Загрузить заявку", "order_index": 4},
            {"id": uuid.uuid4(), "key": "order_monitoring", "label": "Мониторинг заявок", "order_index": 8},
        ],
    )
    bind.execute(
        sa.update(app_tabs_table).where(app_tabs_table.c.key == "orders_list").values(label="Все заявки")
    )

    new_codes = [code for code, _, _ in NEW_PERMISSION_DEFS]
    bind.execute(
        sa.delete(role_permissions_table).where(role_permissions_table.c.permission_code.in_(new_codes))
    )
    bind.execute(sa.delete(permission_defs_table).where(permission_defs_table.c.code.in_(new_codes)))

    op.execute("UPDATE orders SET source_filename = 'manual-order' WHERE source_filename IS NULL")
    op.alter_column("orders", "source_filename", existing_type=sa.String(length=255), nullable=False)
