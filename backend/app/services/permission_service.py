import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.folder import Folder
from app.models.permission import AppTab, RolePermission
from app.models.role import UserRole
from app.models.user import User


def ancestor_ids_incl_self(folder: Folder) -> list[uuid.UUID]:
    """Parse '/<id1>/<id2>/.../<id>/' into a list of UUIDs, root first."""
    return [uuid.UUID(part) for part in folder.materialized_path.split("/") if part]


async def _user_role_ids(db: AsyncSession, user: User) -> list[uuid.UUID]:
    if user.user_roles:
        return [ur.role_id for ur in user.user_roles]
    result = await db.execute(select(UserRole.role_id).where(UserRole.user_id == user.id))
    return [row[0] for row in result.all()]


async def is_system_user(db: AsyncSession, user: User) -> bool:
    for ur in user.user_roles:
        if ur.role is not None and ur.role.is_system:
            return True
    return False


async def has_global_permission(db: AsyncSession, user: User, code: str) -> bool:
    if await is_system_user(db, user):
        return True
    role_ids = await _user_role_ids(db, user)
    if not role_ids:
        return False
    result = await db.execute(
        select(RolePermission).where(
            RolePermission.role_id.in_(role_ids),
            RolePermission.permission_code == code,
            RolePermission.tab_id.is_(None),
            RolePermission.folder_id.is_(None),
            RolePermission.granted.is_(True),
        )
    )
    return result.first() is not None


async def has_tab_permission(db: AsyncSession, user: User, code: str, tab_key: str) -> bool:
    if await is_system_user(db, user):
        return True
    role_ids = await _user_role_ids(db, user)
    if not role_ids:
        return False
    tab_result = await db.execute(select(AppTab).where(AppTab.key == tab_key))
    tab = tab_result.scalar_one_or_none()
    if tab is None:
        return False
    result = await db.execute(
        select(RolePermission).where(
            RolePermission.role_id.in_(role_ids),
            RolePermission.permission_code == code,
            RolePermission.tab_id == tab.id,
            RolePermission.granted.is_(True),
        )
    )
    return result.first() is not None


async def has_folder_permission(db: AsyncSession, user: User, code: str, folder: Folder) -> bool:
    if await is_system_user(db, user):
        return True
    role_ids = await _user_role_ids(db, user)
    if not role_ids:
        return False

    ancestor_ids = ancestor_ids_incl_self(folder)
    result = await db.execute(
        select(RolePermission).where(
            RolePermission.role_id.in_(role_ids),
            RolePermission.permission_code == code,
            RolePermission.folder_id.in_(ancestor_ids),
        )
    )
    rows = result.scalars().all()
    if not rows:
        return False

    # nearest-ancestor-wins: pick the row whose folder_id is deepest in the path
    depth_by_id = {fid: idx for idx, fid in enumerate(ancestor_ids)}
    deepest = max(rows, key=lambda r: depth_by_id.get(r.folder_id, -1))
    return deepest.granted
