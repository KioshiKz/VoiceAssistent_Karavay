import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import require_permission
from app.core.security import hash_password
from app.db.session import get_db
from app.models.role import Role, UserRole
from app.models.user import User
from app.schemas.user import UserCreate, UserListOut, UserRolesSet, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])

ADMIN_ONLY = require_permission("admin.manage")


@router.get("", response_model=list[UserListOut], dependencies=[Depends(ADMIN_ONLY)])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    users = result.scalars().all()
    return [
        UserListOut(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            voice_assistant_enabled=u.voice_assistant_enabled,
            role_names=[ur.role.name for ur in u.user_roles if ur.role],
        )
        for u in users
    ]


@router.post("", response_model=UserListOut, status_code=201, dependencies=[Depends(ADMIN_ONLY)])
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == payload.email.lower()))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(409, detail="email_already_exists")

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        is_active=payload.is_active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserListOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        voice_assistant_enabled=user.voice_assistant_enabled,
        role_names=[],
    )


async def _get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id, options=[selectinload(User.user_roles).selectinload(UserRole.role)])
    if user is None:
        raise HTTPException(404, detail="user_not_found")
    return user


@router.patch("/{user_id}", response_model=UserListOut, dependencies=[Depends(ADMIN_ONLY)])
async def update_user(user_id: uuid.UUID, payload: UserUpdate, db: AsyncSession = Depends(get_db)):
    user = await _get_user_or_404(db, user_id)
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        password = data.pop("password")
        if password:
            user.password_hash = hash_password(password)
    for key, value in data.items():
        setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return UserListOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        voice_assistant_enabled=user.voice_assistant_enabled,
        role_names=[ur.role.name for ur in user.user_roles if ur.role],
    )


@router.put("/{user_id}/roles", response_model=UserListOut, dependencies=[Depends(ADMIN_ONLY)])
async def set_user_roles(user_id: uuid.UUID, payload: UserRolesSet, db: AsyncSession = Depends(get_db)):
    user = await _get_user_or_404(db, user_id)

    valid_roles = await db.execute(select(Role.id).where(Role.id.in_(payload.role_ids)))
    valid_ids = {row[0] for row in valid_roles.all()}
    if valid_ids != set(payload.role_ids):
        raise HTTPException(400, detail="unknown_role_id")

    await db.execute(UserRole.__table__.delete().where(UserRole.user_id == user_id))
    for role_id in payload.role_ids:
        db.add(UserRole(user_id=user_id, role_id=role_id))
    await db.commit()

    refreshed = await _get_user_or_404(db, user_id)
    return UserListOut(
        id=refreshed.id,
        email=refreshed.email,
        full_name=refreshed.full_name,
        is_active=refreshed.is_active,
        voice_assistant_enabled=refreshed.voice_assistant_enabled,
        role_names=[ur.role.name for ur in refreshed.user_roles if ur.role],
    )
