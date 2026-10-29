# DataPulse

> **Reference Only — All Rights Reserved**
>
> This repository is publicly available for portfolio presentation and technical evaluation only. Public visibility does not grant permission to deploy, operate, commercially use, modify, redistribute, or create derivative works from this software. Any additional use requires prior written authorization under the applicable license and subject to applicable law. All rights not expressly granted are reserved.
>
> See [LICENSE](LICENSE). To request permission for additional use, contact majeed.developer0@gmail.com.

A professional, maintainable data analytics and reporting API built with FastAPI, PostgreSQL, and Python 3.12.

DataPulse lets authenticated users upload CSV and JSON datasets, inspect data quality, compute summary statistics, and generate persisted analytical reports — all through a well-documented REST API.

---

## Key Features

- **Secure authentication** — JWT access tokens (15 min) + refresh-token rotation with SHA-256 hashed storage; Argon2id password hashing
- **Dataset upload** — CSV and JSON; content validation, encoding detection, configurable size and row limits
- **Data quality analysis** — missing-value counts, duplicate detection, empty-column detection, structured findings
- **Summary statistics** — numeric (mean, median, std, percentiles), categorical (top values, unique count), datetime (range)
- **Persisted reports** — immutable snapshots combining metadata, quality, and statistics; survives dataset deletion
- **Resource-level authorization** — every endpoint checks ownership; users cannot access each other's data
- **OpenAPI documentation** — interactive docs at `/docs` and `/redoc`

---

## Technology Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI 0.115+ |
| Language | Python 3.12 |
| Database | PostgreSQL 16+ |
| ORM | SQLAlchemy 2.x (async) |
| Migrations | Alembic |
| Data processing | Pandas 2.x |
| Password hashing | Argon2-CFFI |
| JWT | python-jose |
| Settings | pydantic-settings |
| Package manager | uv |
| Linting | Ruff |
| Type checking | Mypy (strict) |
| Testing | Pytest + HTTPX |
| CI | GitHub Actions |

---

## Architecture

```mermaid
graph TD
    Client -->|HTTP| FastAPI
    FastAPI --> Router[API Router /api/v1]
    Router --> Auth[auth.py]
    Router --> Users[users.py]
    Router --> Datasets[datasets.py]
    Router --> Reports[reports.py]

    Auth --> AuthSvc[AuthService]
    Datasets --> DatasetSvc[DatasetService]
    Reports --> ReportSvc[ReportService]

    AuthSvc --> DB[(PostgreSQL)]
    DatasetSvc --> DB
    DatasetSvc --> Parser[analytics/parser.py]
    DatasetSvc --> Quality[analytics/quality.py]
    DatasetSvc --> Stats[analytics/statistics.py]
    DatasetSvc --> Storage[storage/local.py]
    ReportSvc --> DB
    ReportSvc --> DatasetSvc
```

---

## Data-Processing Workflow

```
Upload CSV/JSON
     │
     ▼
Size & extension validation
     │
     ▼
Save to data/uploads/{user_id}/{dataset_id}/
     │
     ▼
Parse (encoding detection, column name normalization)
     │
     ▼
Infer column types (integer / float / datetime / string / boolean)
     │
     ▼
Persist column metadata → datasets + dataset_columns tables
     │
     ▼
Dataset status: ready
     │
     ├─► GET /datasets/{id}/preview     → paginated rows
     ├─► GET /datasets/{id}/quality     → missing values, duplicates, findings
     ├─► GET /datasets/{id}/statistics  → per-column statistics
     └─► POST /reports/                 → persisted snapshot report
```

---

## Repository Structure

```
DataPulse/
├── app/
│   ├── api/
│   │   ├── deps.py          # FastAPI dependency injection
│   │   ├── router.py        # Top-level API router
│   │   └── v1/
│   │       ├── auth.py      # /auth endpoints
│   │       ├── datasets.py  # /datasets endpoints
│   │       ├── health.py    # /health, /ready
│   │       ├── reports.py   # /reports endpoints
│   │       └── users.py     # /users/me
│   ├── analytics/
│   │   ├── parser.py        # CSV/JSON parsing, type inference
│   │   ├── quality.py       # Data quality analysis
│   │   └── statistics.py    # Summary statistics
│   ├── core/
│   │   ├── config.py        # pydantic-settings configuration
│   │   ├── exceptions.py    # Domain exceptions + error handlers
│   │   ├── logging_config.py
│   │   └── security.py      # Argon2id + JWT
│   ├── db/
│   │   ├── base.py          # SQLAlchemy declarative base
│   │   └── session.py       # Async engine + session factory
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/            # Business logic layer
│   ├── storage/
│   │   └── local.py         # Local filesystem storage abstraction
│   └── main.py              # FastAPI app factory
├── alembic/                 # Database migrations
├── tests/
│   ├── unit/                # Pure function tests (no DB)
│   └── api/                 # API tests (require PostgreSQL)
├── docs/                    # Technical documentation
├── scripts/                 # Setup and utility scripts
├── .github/
│   ├── workflows/ci.yml     # GitHub Actions CI
│   └── ISSUE_TEMPLATE/
├── docker-compose.yml       # PostgreSQL service
├── pyproject.toml
└── .env.example
```

---

## Prerequisites

- Python 3.12+
- PostgreSQL 16+ (local install or Docker)
- [uv](https://docs.astral.sh/uv/) package manager

### Install uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

## Local Installation

### 1. Clone the repository

```bash
git clone https://github.com/AMSoft/DataPulse.git
cd DataPulse
```

### 2. Set up the virtual environment and install dependencies

```bash
uv sync
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your values — at minimum, set SECRET_KEY and DATABASE_URL
```

Generate a secure `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Set up PostgreSQL

**Option A — Docker (recommended):**

```bash
docker compose up -d postgres
```

**Option B — Local PostgreSQL (already installed):**

```bash
# Run the setup script to create the database user and databases
PGPASSWORD=your_postgres_password uv run python scripts/setup_db.py
```

The script creates:
- User `datapulse` with password `datapulse`
- Database `datapulse`
- Database `datapulse_test` (for tests)

### 5. Run migrations

```bash
uv run alembic upgrade head
```

### 6. Create a development user (optional)

```bash
uv run python scripts/create_dev_user.py
# Default: dev@datapulse.local / DevPassword1
```

### 7. Start the API

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

---

## Example Workflow

### Register and log in

```bash
# Register
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","username":"myuser","password":"MyPassword1"}' | jq

# Login — save the access token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"MyPassword1"}' | jq -r .access_token)
```

### Upload a dataset

```bash
curl -s -X POST http://localhost:8000/api/v1/datasets/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/your/data.csv" \
  -F "name=My Dataset" \
  -F "description=Sales data Q1 2024" | jq

# Save the dataset ID
DATASET_ID=<id from response>
```

### Inspect data quality

```bash
curl -s http://localhost:8000/api/v1/datasets/$DATASET_ID/quality \
  -H "Authorization: Bearer $TOKEN" | jq
```

Example response:
```json
{
  "dataset_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "total_rows": 1000,
  "total_columns": 5,
  "duplicate_rows": 3,
  "findings": [
    {
      "level": "warning",
      "code": "DUPLICATE_ROWS",
      "message": "3 duplicate row(s) detected (0.3% of total).",
      "column": null,
      "details": {"count": 3, "pct": 0.3}
    }
  ],
  "columns": [
    {
      "name": "age",
      "inferred_type": "integer",
      "total_count": 1000,
      "missing_count": 12,
      "missing_pct": 1.2,
      "unique_count": 45
    }
  ]
}
```

### Get summary statistics

```bash
curl -s http://localhost:8000/api/v1/datasets/$DATASET_ID/statistics \
  -H "Authorization: Bearer $TOKEN" | jq '.columns[] | select(.name == "age")'
```

### Generate a report

```bash
curl -s -X POST http://localhost:8000/api/v1/reports/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"dataset_id\":\"$DATASET_ID\",\"title\":\"Q1 2024 Analysis\"}" | jq
```

---

## Testing

```bash
# Unit tests only (no database required)
uv run pytest tests/unit/ -v

# All tests (requires PostgreSQL with datapulse_test database)
uv run pytest -v

# With coverage
uv run pytest --cov=app --cov-report=term-missing
```

See [docs/TESTING.md](docs/TESTING.md) for test database setup and test organization.

---

## Code Quality

```bash
# Lint
uv run ruff check .

# Fix lint issues automatically
uv run ruff check . --fix

# Format
uv run ruff format .

# Type check
uv run mypy app/
```

---

## Configuration Reference

All settings are loaded from environment variables (or a `.env` file). See [`.env.example`](.env.example) for all options.

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | Environment (`development`, `production`, `testing`) |
| `SECRET_KEY` | *(required)* | JWT signing key — generate with `secrets.token_hex(32)` |
| `DATABASE_URL` | `postgresql+asyncpg://datapulse:datapulse@localhost:5432/datapulse` | Async PostgreSQL URL |
| `UPLOAD_DIR` | `data/uploads` | Directory for uploaded files |
| `MAX_UPLOAD_SIZE_BYTES` | `52428800` | Maximum upload size (50 MB) |
| `MAX_ROWS` | `1000000` | Maximum rows processed per dataset |
| `MAX_COLUMNS` | `500` | Maximum columns per dataset |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:8000` | Allowed CORS origins |

---

## API Documentation

Interactive OpenAPI documentation is available at `/docs` (Swagger UI) and `/redoc` (ReDoc) when the server is running.

See [docs/API.md](docs/API.md) for the complete endpoint reference.

---

## Data Storage and Processing Limits

| Limit | Default | Configurable |
|---|---|---|
| Maximum file size | 50 MB | `MAX_UPLOAD_SIZE_BYTES` |
| Maximum rows | 1,000,000 | `MAX_ROWS` |
| Maximum columns | 500 | `MAX_COLUMNS` |
| Supported formats | CSV, JSON | — |
| Max top categorical values returned | 20 | — |

**Storage note:** Uploaded files are stored on the local filesystem at `UPLOAD_DIR`. This is not suitable for multi-instance deployments without a shared persistent volume. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for deployment guidance.

---

## Security Considerations

- Passwords are hashed with Argon2id (64 MB memory, 2 iterations, 2 parallelism)
- Refresh tokens are stored as SHA-256 hashes; the raw token is never persisted
- Every dataset and report endpoint validates ownership
- Internal storage paths are never exposed in API responses
- See [docs/SECURITY.md](docs/SECURITY.md) for the full threat model and known limitations

---

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common issues including database connection problems, migration errors, and upload failures.

---

## Deployment

> **Reference only:** the guidance below documents how the system is designed to run. Deploying or operating this software requires prior written authorization under the [LICENSE](LICENSE).

DataPulse is designed for straightforward deployment on any platform that provides:
- A Python 3.12 runtime
- A persistent PostgreSQL 16+ database
- A persistent filesystem volume for uploads (or a cloud storage backend)

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for configuration, migration, health checks, and rollback guidance.

---

## Known Limitations

- Local file storage is not suitable for deployments without a persistent filesystem
- No multi-instance / distributed file storage support
- No background task queue; dataset processing happens synchronously during upload
- No rate limiting beyond what is documented in the configuration
- No PDF export or scheduled reporting
- CSV type inference is heuristic-based; ambiguous columns default to `string`

---

## Contributing

This project is published for reference and portfolio evaluation and is not open to outside contributions or pull requests. See [LICENSE](LICENSE) for the use that is permitted, and contact me to request any additional permission.

## License

Copyright (c) 2026 Abdul Majeed. All rights reserved.

This project is published under a custom **Reference-Only Source-Available License**. It is **not** an open-source license. See [LICENSE](LICENSE). Deployment, commercial use, modification and redistribution require prior written authorization. Permission requests: majeed.developer0@gmail.com

## Roadmap

- [ ] Cloud storage abstraction (S3-compatible)
- [ ] Background processing queue for large uploads
- [ ] Excel (.xlsx) support
- [ ] Rate limiting middleware
- [ ] PDF report export
- [ ] Admin user management
