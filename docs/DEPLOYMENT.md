# DataPulse Deployment Guide

> **Reference only:** this guide documents how the system is designed to run. Deploying or operating this software requires prior written authorization under the [LICENSE](../LICENSE).

## Prerequisites

- Python 3.12+
- PostgreSQL 16+
- Persistent storage volume mounted at `UPLOAD_DIR`
- `SECRET_KEY` generated securely

## Environment Configuration

Copy `.env.example` to `.env` (or set environment variables directly):

```bash
APP_ENV=production
APP_DEBUG=false
SECRET_KEY=<64-char hex string>
DATABASE_URL=postgresql+asyncpg://datapulse:<password>@<host>:5432/datapulse
UPLOAD_DIR=/var/datapulse/uploads
CORS_ORIGINS=https://your-frontend.example.com
```

## Database Setup

```bash
# Create database user and database
psql -U postgres -c "CREATE USER datapulse WITH PASSWORD 'your-password';"
psql -U postgres -c "CREATE DATABASE datapulse OWNER datapulse;"

# Run migrations
uv run alembic upgrade head
```

## Starting the Application

```bash
# Production — use multiple workers
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Health Checks

- `GET /api/v1/health` — application is alive
- `GET /api/v1/ready` — application + database are ready

## Persistent Storage

`UPLOAD_DIR` must point to a directory that persists across deployments and process restarts. On a single-server deployment, this is a directory on the host filesystem. On a container platform, mount a persistent volume.

**Warning:** if `UPLOAD_DIR` is ephemeral (e.g., inside a container without a volume), all uploaded files are lost on container restart. Dataset records in the database will have `storage_path` values that point to non-existent files.

## Rollback

To roll back one migration:
```bash
uv run alembic downgrade -1
```

Do not run `downgrade` on a production database without a backup.

## Known Limitations

- No horizontal scaling without a shared filesystem or cloud storage backend
- No built-in TLS termination — use a reverse proxy (nginx, Caddy, etc.)
- No rate limiting middleware in the current version
