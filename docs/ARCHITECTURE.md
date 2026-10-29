# DataPulse Architecture

## Overview

DataPulse is structured as a **modular monolith**: all business logic lives in a single deployable process, divided into clearly bounded modules with explicit dependency rules. This keeps the codebase navigable and testable without the operational complexity of microservices.

---

## Module Responsibilities

| Module | Responsibility |
|---|---|
| `app/main.py` | FastAPI app factory, middleware, exception handlers, lifespan |
| `app/core/config.py` | Centralized configuration via `pydantic-settings` |
| `app/core/security.py` | Password hashing (Argon2id), JWT creation/validation, refresh-token hashing |
| `app/core/exceptions.py` | Domain exception hierarchy + FastAPI error handlers |
| `app/db/` | SQLAlchemy async engine, session factory, declarative base |
| `app/models/` | ORM table definitions (never exposed directly to API consumers) |
| `app/schemas/` | Pydantic v2 request and response models (API contract) |
| `app/services/` | Business logic — the only layer that writes to the database |
| `app/analytics/` | Pure data-processing functions; no I/O, no FastAPI dependencies |
| `app/storage/` | File persistence abstraction (local filesystem today, swappable) |
| `app/api/` | Thin FastAPI route handlers that delegate to services |
| `tests/` | Unit and API test suites |

---

## Dependency Flow

```
HTTP Request
    │
    ▼
app/api/v1/*.py      (route handlers — thin; validate input, call service)
    │
    ▼
app/services/*.py    (business logic — owns DB transactions)
    │
    ├──► app/db/session.py      (AsyncSession)
    ├──► app/models/*.py        (ORM objects)
    ├──► app/analytics/*.py     (pure functions)
    └──► app/storage/local.py   (file I/O)
```

**Rule:** no module imports upward. `analytics/` and `storage/` do not import from `services/`. `services/` does not import from `api/`. Route handlers do not contain business logic.

---

## Authentication Flow

```
POST /auth/login
    │
    ▼
auth_service.login_user()
    ├── verify Argon2id password hash
    ├── create_access_token()   → signed HS256 JWT, 15 min
    ├── create_refresh_token()  → 48-byte random token (raw)
    ├── hash_refresh_token()    → SHA-256 hex digest
    └── store RefreshToken{token_hash, expires_at} in DB

GET /api/v1/datasets/ (protected)
    │
    ▼
app/api/deps.get_authenticated_user()
    ├── extract Bearer token from Authorization header
    ├── decode_access_token()   → verify signature + expiry
    └── load User from DB by subject claim
```

**Why HS256 (symmetric) instead of RS256?** For a single-service deployment with a single secret key, symmetric signing is simpler to operate and equally secure. RS256 would be appropriate if tokens needed verification by multiple independent services.

**Why SHA-256 for refresh tokens?** Storing the raw token would expose all user sessions if the database were read. SHA-256 is fast enough for single-token lookups and prevents offline brute-force attacks on the stored value.

---

## Data-Processing Pipeline

```
upload bytes
    │
    ▼
app/storage/local.save_upload()          → persist raw bytes to filesystem
    │
    ▼
app/analytics/parser.parse_file()
    ├── detect encoding (utf-8-sig, utf-8, latin-1)
    ├── pd.read_csv() with dtype=str, then coerce types
    ├── _infer_column_type() per column
    └── returns ParseResult{df, inferred_types, warnings}
    │
    ▼
persist DatasetColumn rows               → column names, types, missing counts
    │
    ▼
dataset.status = "ready"

(On preview / quality / statistics requests)
    │
    ▼
reload file bytes from storage           → re-parse on demand
    │
    ├──► quality.analyze_quality(df)     → QualityReport
    ├──► statistics.compute_statistics() → StatisticsReport
    └──► row slice for preview
```

**Why re-parse on demand instead of caching results?** In this version, analysis results are computed on request and not cached (except in reports). This avoids stale-cache issues and keeps storage requirements minimal. For large datasets this adds latency; a background task queue and result caching layer would be the natural next step.

---

## Database Design

See [DATABASE.md](DATABASE.md) for the complete schema.

Five tables:
- `users` — accounts
- `datasets` — upload metadata and processing state
- `dataset_columns` — per-column metadata for each dataset
- `reports` — immutable analysis snapshots (JSON text)
- `refresh_tokens` — hashed refresh tokens with expiry

**Deletion policy:**
- Deleting a user cascades to datasets, reports, and refresh tokens
- Deleting a dataset cascades to dataset_columns; reports retain their snapshot via `SET NULL` on `dataset_id`
- Uploaded files are deleted from the filesystem after the dataset row is removed from the DB

---

## Error Handling

All errors are normalized to the same JSON envelope:

```json
{
  "error": {
    "code": "DATASET_NOT_FOUND",
    "message": "Dataset not found.",
    "details": null
  }
}
```

Domain exceptions (`DataPulseError` subclasses) carry their own HTTP status code. FastAPI `HTTPException` and `RequestValidationError` are caught by separate handlers. Unhandled exceptions return `500 INTERNAL_ERROR` with no stack trace.

---

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Async everywhere | `asyncio` + `asyncpg` | FastAPI is async-native; asyncpg is the fastest PostgreSQL driver for asyncio |
| SQLAlchemy 2.x mapped_column | Modern declarative style | Type-safe, IDE-friendly, recommended for new code |
| Pydantic v2 | `model_validate`, `model_dump` | Significantly faster than v1; explicit ORM mode |
| Local storage | `data/uploads/` | Simple, zero-dependency, replaceable via `storage/` abstraction |
| Argon2id | `argon2-cffi` | OWASP-recommended KDF; resistant to GPU and side-channel attacks |
| Re-parse on analysis | No analysis cache | Eliminates stale-cache bugs; acceptable for current scale |
| Report snapshots as JSON text | `Text` column | Avoids a complex JSONB schema; trivially queryable for reading back |
