# DataPulse Troubleshooting

## Python / Environment

**`python: command not found`**
Ensure Python 3.12+ is on your PATH. On Windows, the installer may add `python` under the user profile directory. Restart your terminal after installation or run `uv python install 3.12` to install through uv.

**`uv: command not found`**
Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh` (macOS/Linux) or `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"` (Windows). Restart your terminal.

**`OSError: Readme file does not exist: README.md`** (during `uv sync`)
The `pyproject.toml` references `README.md` which must exist. If you deleted it, create an empty one: `echo "# DataPulse" > README.md`.

## PostgreSQL

**`connection refused` / `could not connect to server`**
- Verify PostgreSQL is running: `pg_isready -h localhost -p 5432`
- On Windows: check `Services` for `postgresql-x64-XX` and start it if stopped
- Verify the `DATABASE_URL` in `.env` matches your credentials

**`password authentication failed for user "datapulse"`**
The `datapulse` database user was not created, or the password in `DATABASE_URL` is wrong. Run `scripts/setup_db.py` or create the user manually.

**`database "datapulse" does not exist`**
Run `scripts/setup_db.py` or: `psql -U postgres -c "CREATE DATABASE datapulse OWNER datapulse;"`

## Migrations

**`alembic: No module named 'app'`**
Run alembic from the project root (where `alembic.ini` lives): `uv run alembic upgrade head`

**`Target database is not up to date`**
Run `uv run alembic upgrade head` to apply pending migrations.

**`Can't locate revision identified by '...'`**
The migration file may be missing from `alembic/versions/`. Ensure you pulled the latest code.

## Upload Errors

**`400 File size exceeds limit`**
Increase `MAX_UPLOAD_SIZE_BYTES` in `.env`, or split your file.

**`400 Unsupported file type`**
Only `.csv` and `.json` files are accepted. Rename or convert your file.

**`422 CSV file has headers but no data rows`**
Your file has column headers but no data. Add at least one data row.

**`422 Failed to parse CSV`**
The file may be malformed, binary, or have inconsistent quoting. Inspect the file in a text editor to confirm it is valid CSV.

## API / Authentication

**`401 Authentication required`**
Include the `Authorization: Bearer <token>` header. Ensure the token has not expired (default: 15 minutes).

**`401 Invalid or expired access token`**
Use the refresh endpoint (`POST /api/v1/auth/refresh`) to get a new access token.

**`403 You do not have access to this dataset`**
You are authenticated, but the dataset belongs to another user.

## Type Checking

**`mypy: error: Cannot find implementation or library stub for module named "..."`**
This is expected for third-party libraries without stubs. Add them to `ignore_missing_imports = true` or install type stubs. The `pyproject.toml` already sets `ignore_missing_imports = true` globally.
