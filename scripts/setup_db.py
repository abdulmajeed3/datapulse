#!/usr/bin/env python
"""Create the DataPulse database user and database in a local PostgreSQL instance.

Run once before first migration:
    uv run python scripts/setup_db.py

Requires the postgres superuser to be accessible.
Set PGPASSWORD environment variable if needed.
"""

import asyncio
import os
import sys


async def main() -> None:
    try:
        import asyncpg
    except ImportError:
        print("asyncpg not installed. Run: uv sync")
        sys.exit(1)

    pg_host = os.getenv("PGHOST", "localhost")
    pg_port = int(os.getenv("PGPORT", "5432"))
    pg_superuser = os.getenv("PGUSER", "postgres")
    pg_superpassword = os.getenv("PGPASSWORD", "")

    db_name = os.getenv("DB_NAME", "datapulse")
    db_user = os.getenv("DB_USER", "datapulse")
    db_password = os.getenv("DB_PASSWORD", "datapulse")

    print(f"Connecting to PostgreSQL at {pg_host}:{pg_port} as {pg_superuser}...")

    conn = await asyncpg.connect(
        host=pg_host,
        port=pg_port,
        user=pg_superuser,
        password=pg_superpassword,
        database="postgres",
    )

    try:
        # Create user if not exists
        exists = await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", db_user)
        if not exists:
            await conn.execute(f"CREATE USER {db_user} WITH PASSWORD '{db_password}'")
            print(f"Created user: {db_user}")
        else:
            print(f"User already exists: {db_user}")

        # Create database if not exists
        db_exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if not db_exists:
            await conn.execute(f"CREATE DATABASE {db_name} OWNER {db_user}")
            print(f"Created database: {db_name}")
        else:
            print(f"Database already exists: {db_name}")

        # Create test database if not exists
        test_db = f"{db_name}_test"
        test_exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", test_db)
        if not test_exists:
            await conn.execute(f"CREATE DATABASE {test_db} OWNER {db_user}")
            print(f"Created test database: {test_db}")
        else:
            print(f"Test database already exists: {test_db}")

    finally:
        await conn.close()

    print("\nDatabase setup complete.")
    print(f"  Main DB  : postgresql://{db_user}:{db_password}@{pg_host}:{pg_port}/{db_name}")
    print(f"  Test DB  : postgresql://{db_user}:{db_password}@{pg_host}:{pg_port}/{test_db}")
    print("\nNext steps:")
    print("  1. Copy .env.example to .env and update DATABASE_URL")
    print("  2. Run: uv run alembic upgrade head")
    print("  3. Run: uv run python scripts/create_dev_user.py")


if __name__ == "__main__":
    asyncio.run(main())
