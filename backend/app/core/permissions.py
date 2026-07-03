import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import permission_service


def require_permission(code: str, folder_param: str | None = None, tab_key: str | None = None):
    async def checker(
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if folder_param:
            from app.services.folder_service import get_folder_or_404

            folder_id = uuid.UUID(request.path_params[folder_param])
            folder = await get_folder_or_404(db, folder_id)
            ok = await permission_service.has_folder_permission(db, user, code, folder)
        elif tab_key:
            ok = await permission_service.has_tab_permission(db, user, code, tab_key)
        else:
            ok = await permission_service.has_global_permission(db, user, code)

        if not ok:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="permission_denied")
        return user

    return checker
