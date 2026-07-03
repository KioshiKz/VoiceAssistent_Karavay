import uuid
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    ttl_seconds = settings.jwt_access_ttl_minutes * 60
    expire = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    payload = {"sub": str(user_id), "type": "access", "exp": expire}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)
    return token, ttl_seconds


def create_refresh_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_ttl_days)
    payload = {"sub": str(user_id), "type": "refresh", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
