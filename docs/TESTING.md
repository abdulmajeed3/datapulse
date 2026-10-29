# DataPulse Testing Guide

## Test Organization

```
tests/
├── conftest.py       # Shared fixtures, test database setup
├── unit/             # Pure function tests — no database required
│   ├── test_parser.py
│   ├── test_quality.py
│   ├── test_statistics.py
│   └── test_security.py
└── api/              # HTTP API tests — require PostgreSQL
    ├── test_auth.py
    ├── test_datasets.py
    ├── test_reports.py
    └── test_authorization.py
```

---

## Test Database Setup

API tests require a PostgreSQL database named `datapulse_test`.

### Create the test database

```bash
# Using the setup script (creates both datapulse and datapulse_test)
PGPASSWORD=your_postgres_password uv run python scripts/setup_db.py

# Or manually in psql
psql -U postgres -c "CREATE DATABASE datapulse_test OWNER datapulse;"
```

### Configure the test database URL

By default, `conftest.py` uses:
```
postgresql+asyncpg://datapulse:datapulse@localhost:5432/datapulse_test
```

Override with the `DATABASE_URL` environment variable:
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/mytest_db uv run pytest
```

---

## Running Tests

```bash
# All tests
uv run pytest

# Unit tests only (no database)
uv run pytest tests/unit/ -v

# API tests only
uv run pytest tests/api/ -v

# Specific test file
uv run pytest tests/api/test_authorization.py -v

# With coverage report
uv run pytest --cov=app --cov-report=term-missing

# Stop after first failure
uv run pytest -x
```

---

## Test Isolation

- **Unit tests** (`tests/unit/`) use no database, no filesystem, and no network. They test pure Python functions from `app/analytics/` and `app/core/security.py` directly.

- **API tests** (`tests/api/`) use a real PostgreSQL test database. Each test receives a fresh `AsyncSession`; the session is rolled back (not committed) after each test to prevent data leaking between tests. The `create_tables` fixture (session-scoped) drops and recreates all tables once per test session.

- **Uploaded files** in API tests are written to `/tmp/datapulse_test_uploads` (configurable). This directory is not automatically cleaned up after tests.

---

## What the Tests Cover

### Unit tests

| File | What is tested |
|---|---|
| `test_parser.py` | CSV parsing, encoding, row/column limits, malformed input, type inference |
| `test_quality.py` | Missing values, duplicates, empty columns, high-missing warnings |
| `test_statistics.py` | Numeric, categorical, datetime stats; edge cases (empty, single-value, non-finite) |
| `test_security.py` | Password hash/verify, JWT creation/decoding, refresh token hashing |

### API tests

| File | What is tested |
|---|---|
| `test_auth.py` | Registration, login, duplicate detection, weak passwords, refresh/logout, /users/me |
| `test_datasets.py` | Upload, list, get, update, delete, preview pagination, quality, statistics |
| `test_reports.py` | Create, get, list, delete, snapshot immutability |
| `test_authorization.py` | Cross-user access (all dataset + report operations), invalid/missing/malformed tokens |

---

## Test Quality Guidelines

- Test names describe the behavior being verified, not the implementation
- Edge cases are explicit: empty file, header-only CSV, single-value column, all-missing column
- Authorization tests explicitly check that `403` (not just `4xx`) is returned for cross-user access
- No tests verify only imports or object construction

---

## Known Limitations

- Tests do not cover concurrent request behavior
- API tests run database operations serially (no parallel test execution via `pytest-xdist`)
- Test coverage is not automatically enforced at a specific threshold in CI
