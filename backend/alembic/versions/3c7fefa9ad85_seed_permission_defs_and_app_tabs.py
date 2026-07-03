"""seed permission_defs and app_tabs

Revision ID: 3c7fefa9ad85
Revises: a8befdc02545
Create Date: 2026-07-04 03:33:28.510565

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3c7fefa9ad85'
down_revision: Union[str, None] = 'a8befdc02545'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERMISSION_DEFS = [
    ("tab.view", "Просмотр вкладки", "tab"),
    ("tab.edit", "Редактирование вкладки", "tab"),
    ("folder.view", "Просмотр папки", "folder"),
    ("folder.create", "Создание внутри папки", "folder"),
    ("folder.edit", "Редактирование внутри папки", "folder"),
    ("order.execute", "Исполнение заявок/планов", "global"),
    ("admin.manage", "Управление пользователями и ролями", "global"),
]

APP_TABS = [
    ("dashboard", "Главная", 0),
    ("file_manager", "Файлы", 1),
    ("roles_permissions", "Роли и права", 2),
    ("users", "Пользователи", 3),
    ("upload_order", "Загрузить заявку", 4),
    ("current_order", "Текущая заявка", 5),
]

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


def upgrade() -> None:
    op.bulk_insert(
        permission_defs_table,
        [{"code": code, "label": label, "scope_type": scope} for code, label, scope in PERMISSION_DEFS],
    )
    op.bulk_insert(
        app_tabs_table,
        [
            {"id": uuid.uuid4(), "key": key, "label": label, "order_index": idx}
            for key, label, idx in APP_TABS
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM app_tabs")
    op.execute("DELETE FROM permission_defs")
