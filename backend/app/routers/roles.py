import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.folder import Folder
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
    role = Role(
        name=payload.name,
        description=payload.description,
        order_visibility_ahead=payload.order_visibility_ahead,
    )
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

    permission_codes = {entry.permission_code for entry in payload.entries}
    definitions_result = await db.execute(
        select(PermissionDef).where(PermissionDef.code.in_(permission_codes))
    )
    definitions = {definition.code: definition for definition in definitions_result.scalars().all()}
    if set(definitions) != permission_codes:
        raise HTTPException(400, detail="unknown_permission_code")

    seen_entries: set[tuple[str, uuid.UUID | None, uuid.UUID | None]] = set()
    tab_ids: set[uuid.UUID] = set()
    folder_ids: set[uuid.UUID] = set()
    for entry in payload.entries:
        key = (entry.permission_code, entry.tab_id, entry.folder_id)
        if key in seen_entries:
            raise HTTPException(400, detail="duplicate_permission_scope")
        seen_entries.add(key)

        scope_type = definitions[entry.permission_code].scope_type
        valid_scope = (
            (scope_type == "global" and entry.tab_id is None and entry.folder_id is None)
            or (scope_type == "tab" and entry.tab_id is not None and entry.folder_id is None)
            or (scope_type == "folder" and entry.tab_id is None and entry.folder_id is not None)
        )
        if not valid_scope:
            raise HTTPException(400, detail="permission_scope_mismatch")
        if entry.tab_id is not None:
            tab_ids.add(entry.tab_id)
        if entry.folder_id is not None:
            folder_ids.add(entry.folder_id)

    if tab_ids:
        existing_tab_ids = set(
            (await db.execute(select(AppTab.id).where(AppTab.id.in_(tab_ids)))).scalars().all()
        )
        if existing_tab_ids != tab_ids:
            raise HTTPException(400, detail="unknown_tab_id")
    if folder_ids:
        existing_folder_ids = set(
            (await db.execute(select(Folder.id).where(Folder.id.in_(folder_ids)))).scalars().all()
        )
        if existing_folder_ids != folder_ids:
            raise HTTPException(400, detail="unknown_folder_id")

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
