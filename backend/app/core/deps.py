import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import decode_token
from app.db.session import get_db
from app.models.role import UserRole
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_token_type")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="user_inactive_or_not_found")
    return user
