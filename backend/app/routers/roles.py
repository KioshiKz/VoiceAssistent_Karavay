import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.permission import AppTab, PermissionDef, RolePermission
from app.models.role import Role
from app.schemas.role import (
    AppTabOut,
    PermissionDefOut,
    RoleCreate,
    RoleOut,
    RolePermissionOut,
    RolePermissionsReplace,
    RoleUpdate,
)

router = APIRouter(prefix="/api", tags=["roles"])

ADMIN_ONLY = require_permission("admin.manage")


@router.get("/permission-defs", response_model=list[PermissionDefOut], dependencies=[Depends(ADMIN_ONLY)])
async def list_permission_defs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PermissionDef))
    return result.scalars().all()


@router.get("/tabs", response_model=list[AppTabOut])
async def list_tabs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppTab).order_by(AppTab.order_index))
    return result.scalars().all()


@router.get("/roles", response_model=list[RoleOut], dependencies=[Depends(ADMIN_ONLY)])
async def list_roles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Role))
    return result.scalars().all()


@router.post("/roles", response_model=RoleOut, status_code=201, dependencies=[Depends(ADMIN_ONLY)])
async def create_role(payload: RoleCreate, db: AsyncSession = Depends(get_db)):
    role = Role(name=payload.name, description=payload.description)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


async def _get_role_or_404(db: AsyncSession, role_id: uuid.UUID) -> Role:
    role = await db.get(Role, role_id)
    if role is None:
        raise HTTPException(404, detail="role_not_found")
    return role


@router.patch("/roles/{role_id}", response_model=RoleOut, dependencies=[Depends(ADMIN_ONLY)])
async def update_role(role_id: uuid.UUID, payload: RoleUpdate, db: AsyncSession = Depends(get_db)):
    role = await _get_role_or_404(db, role_id)
    if role.is_system:
        raise HTTPException(409, detail="system_role_immutable")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(role, key, value)
    await db.commit()
    await db.refresh(role)
    return role


@router.delete("/roles/{role_id}", status_code=204, dependencies=[Depends(ADMIN_ONLY)])
async def delete_role(role_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    role = await _get_role_or_404(db, role_id)
    if role.is_system:
        raise HTTPException(409, detail="system_role_immutable")
    await db.delete(role)
    await db.commit()


@router.get(
    "/roles/{role_id}/permissions",
    response_model=list[RolePermissionOut],
    dependencies=[Depends(ADMIN_ONLY)],
)
async def get_role_permissions(role_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _get_role_or_404(db, role_id)
    result = await db.execute(select(RolePermission).where(RolePermission.role_id == role_id))
    return result.scalars().all()


@router.put(
    "/roles/{role_id}/permissions",
    response_model=list[RolePermissionOut],
    dependencies=[Depends(ADMIN_ONLY)],
)
async def replace_role_permissions(
    role_id: uuid.UUID, payload: RolePermissionsReplace, db: AsyncSession = Depends(get_db)
):
    role = await _get_role_or_404(db, role_id)
    if role.is_system:
        raise HTTPException(409, detail="system_role_immutable")

    await db.execute(RolePermission.__table__.delete().where(RolePermission.role_id == role_id))
    for entry in payload.entries:
        db.add(
            RolePermission(
                role_id=role_id,
                permission_code=entry.permission_code,
                tab_id=entry.tab_id,
                folder_id=entry.folder_id,
                granted=entry.granted,
            )
        )
    await db.commit()

    result = await db.execute(select(RolePermission).where(RolePermission.role_id == role_id))
    return result.scalars().all()
