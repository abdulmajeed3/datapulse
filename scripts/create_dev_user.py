#!/usr/bin/env python
"""Create a development user in the DataPulse database.

Run after migrations:
    uv run python scripts/create_dev_user.py

Override defaults with environment variables:
    DEV_EMAIL, DEV_USERNAME, DEV_PASSWORD
"""

import asyncio
import os
import sys


async def main() -> None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

    from sqlalchemy import select

    from app.core.security import hash_password
    from app.db.session import get_session_factory
    from app.models.user import User

    email = os.getenv("DEV_EMAIL", "dev@datapulse.local")
    username = os.getenv("DEV_USERNAME", "devuser")
    password = os.getenv("DEV_PASSWORD", "DevPassword1")

    factory = get_session_factory()
    async with factory() as session:
        existing = await session.scalar(select(User).where(User.email == email))
        if existing is not None:
            print(f"User already exists: {email}")
            return

        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
        )
        session.add(user)
        await session.commit()
        print("Created dev user:")
        print(f"  Email    : {email}")
        print(f"  Username : {username}")
        print(f"  Password : {password}")
        print(f"  ID       : {user.id}")


if __name__ == "__main__":
    asyncio.run(main())
