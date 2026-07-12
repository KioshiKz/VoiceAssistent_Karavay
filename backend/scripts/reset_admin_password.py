"""Idempotent: makes sure INITIAL_ADMIN_EMAIL can log in with INITIAL_ADMIN_PASSWORD.
Unlike seed_admin.py, this overwrites the password of an already-existing user.
Run once after changing .env: python -m scripts.reset_admin_password
"""
import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import async_session_maker
from app.models.role import Role, UserRole
from app.models.user import User


async def main() -> None:
    async with async_session_maker() as db:
        result = await db.execute(select(Role).where(Role.is_system.is_(True)))
        admin_role = result.scalar_one_or_none()
        if admin_role is None:
            admin_role = Role(name="Administrator", description="Full system access", is_system=True)
            db.add(admin_role)
            await db.flush()
            print(f"Created system role 'Administrator' ({admin_role.id})")

        email = settings.initial_admin_email.lower()
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(settings.initial_admin_password),
                full_name="Administrator",
                is_active=True,
            )
            db.add(user)
            await db.flush()
            db.add(UserRole(user_id=user.id, role_id=admin_role.id))
            print(f"Created admin user {email}")
        else:
            user.password_hash = hash_password(settings.initial_admin_password)
            user.is_active = True
            result = await db.execute(
                select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == admin_role.id)
            )
            if result.scalar_one_or_none() is None:
                db.add(UserRole(user_id=user.id, role_id=admin_role.id))
            print(f"Reset password for existing admin user {email}")

        await db.commit()
        print(f"You can now log in with: {email} / <INITIAL_ADMIN_PASSWORD from .env>")


if __name__ == "__main__":
    asyncio.run(main())
