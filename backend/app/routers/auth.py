from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.security import create_access_token, create_refresh_token, verify_password
from app.db.session import get_db
from app.models.permission import AppTab, RolePermission
from app.models.role import UserRole
from app.models.user import User
from app.schemas.auth import LoginRequest, MePermissions, TabPermission, TokenResponse, UserOut, VoiceSettingsUpdate
from app.services import permission_service

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    access_token, expires_in = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    response.set_cookie(
        "refresh_token", refresh_token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7
    )
    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(response: Response, db: AsyncSession = Depends(get_db)):
    # Placeholder for MVP: refresh-token cookie parsing is wired the same way as
    # get_current_user's access-token check, decoded separately here.
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="not_implemented_yet")


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("refresh_token")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


@router.patch("/me/voice-settings", response_model=UserOut)
async def update_voice_settings(
    payload: VoiceSettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.voice_assistant_enabled = payload.voice_assistant_enabled
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/me/permissions", response_model=MePermissions)
async def me_permissions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    is_system = await permission_service.is_system_user(db, user)

    tabs_result = await db.execute(select(AppTab))
    tabs = tabs_result.scalars().all()

    tab_perms: dict[str, TabPermission] = {}
    for tab in tabs:
        view = await permission_service.has_tab_permission(db, user, "tab.view", tab.key)
        edit = await permission_service.has_tab_permission(db, user, "tab.edit", tab.key)
        if view or edit:
            tab_perms[tab.key] = TabPermission(view=view, edit=edit)

    global_perms = {
        "order.execute": await permission_service.has_global_permission(db, user, "order.execute"),
        "admin.manage": await permission_service.has_global_permission(db, user, "admin.manage"),
        "recipe.full_view": await permission_service.has_global_permission(db, user, "recipe.full_view"),
    }

    return MePermissions(tabs=tab_perms, global_=global_perms, system_role=is_system)
