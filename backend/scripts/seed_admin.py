"""Idempotent: creates the system 'Administrator' role (if missing) and the
first admin user from INITIAL_ADMIN_EMAIL/INITIAL_ADMIN_PASSWORD (if missing).
Run once after the first deploy: python -m scripts.seed_admin
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
        else:
            print(f"System role already exists ({admin_role.id})")

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
            print(f"Admin user already exists: {email}")

        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
