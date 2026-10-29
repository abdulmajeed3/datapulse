# DataPulse API Reference

Base URL: `/api/v1`

Interactive documentation is available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

---

## Authentication

All protected endpoints require a Bearer token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Access tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 15 minutes). Use the refresh endpoint to obtain a new token pair.

---

## Error Response Format

All errors use a consistent JSON envelope:

```json
{
  "error": {
    "code": "DATASET_NOT_FOUND",
    "message": "Dataset not found.",
    "details": null
  }
}
```

Validation errors include a `details` array:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "details": [
      {"loc": ["body", "email"], "msg": "value is not a valid email address", "type": "value_error.email"}
    ]
  }
}
```

---

## Common HTTP Status Codes

| Code | Meaning |
|---|---|
| 200 | OK |
| 201 | Created |
| 204 | No Content (successful delete) |
| 400 | Bad Request (e.g., empty file, unsupported format) |
| 401 | Unauthorized (missing or invalid token) |
| 403 | Forbidden (authenticated but not authorized for this resource) |
| 404 | Not Found |
| 409 | Conflict (e.g., duplicate email on registration) |
| 422 | Unprocessable Entity (validation error) |
| 500 | Internal Server Error |

---

## Endpoints

### Health

#### `GET /api/v1/health`
Returns application health. Does not require authentication.

**Response 200:**
```json
{"status": "ok", "version": "0.1.0"}
```

#### `GET /api/v1/ready`
Checks database connectivity. Returns `degraded` if the database is unreachable.

**Response 200:**
```json
{"status": "ok", "database": "ok"}
```

---

### Authentication

#### `POST /api/v1/auth/register`

**Request:**
```json
{
  "email": "user@example.com",
  "username": "myuser",
  "password": "MyPassword1"
}
```

Password requirements: ≥8 characters, at least one uppercase, one lowercase, one digit.  
Username: 3–50 characters, alphanumeric plus `_` and `-`.

**Response 201:**
```json
{
  "id": "...",
  "email": "user@example.com",
  "username": "myuser",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### `POST /api/v1/auth/login`

**Request:**
```json
{"email": "user@example.com", "password": "MyPassword1"}
```

**Response 200:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 900
}
```

#### `POST /api/v1/auth/refresh`

Exchange a valid refresh token for a new token pair. The old refresh token is revoked.

**Request:**
```json
{"refresh_token": "..."}
```

#### `POST /api/v1/auth/logout`

Revoke a refresh token.

**Request:**
```json
{"refresh_token": "..."}
```

**Response:** 204 No Content

---

### Users

#### `GET /api/v1/users/me`

Returns the authenticated user's profile.

**Response 200:**
```json
{
  "id": "...",
  "email": "user@example.com",
  "username": "myuser",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

### Datasets

#### `POST /api/v1/datasets/`

Upload a new dataset. Accepts `multipart/form-data`.

**Form fields:**
- `file` — CSV or JSON file (required)
- `name` — dataset name, 1–255 characters (required)
- `description` — optional description, max 2000 characters

**Response 201:** Full `DatasetResponse` including `columns[]` after processing.

#### `GET /api/v1/datasets/`

List the authenticated user's datasets, newest first.

**Query params:** `page` (default: 1), `page_size` (default: 50, max: 500)

**Response 200:**
```json
{
  "items": [...],
  "total": 10,
  "page": 1,
  "page_size": 50,
  "pages": 1
}
```

#### `GET /api/v1/datasets/{dataset_id}`

Retrieve dataset metadata including column information.

#### `PATCH /api/v1/datasets/{dataset_id}`

Update `name` or `description`.

**Request:**
```json
{"name": "new name", "description": "updated description"}
```

#### `DELETE /api/v1/datasets/{dataset_id}`

Delete dataset, its columns, and its uploaded file. Associated reports retain their snapshots.

**Response:** 204 No Content

#### `GET /api/v1/datasets/{dataset_id}/preview`

Paginated row preview.

**Query params:** `page` (default: 1), `page_size` (default: 50, max: 500)

**Response 200:**
```json
{
  "dataset_id": "...",
  "rows": [
    {"index": 0, "data": {"name": "Alice", "age": 30, "score": 95.5}},
    {"index": 1, "data": {"name": "Bob", "age": 25, "score": null}}
  ],
  "total_rows": 1000,
  "page": 1,
  "page_size": 50,
  "pages": 20
}
```

Missing values are serialized as `null`. Dates are ISO 8601 strings.

#### `GET /api/v1/datasets/{dataset_id}/quality`

Data quality analysis.

**Response 200:**
```json
{
  "dataset_id": "...",
  "total_rows": 1000,
  "total_columns": 5,
  "duplicate_rows": 3,
  "findings": [
    {
      "level": "warning",
      "code": "DUPLICATE_ROWS",
      "message": "3 duplicate row(s) detected (0.3%).",
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

Finding levels: `error`, `warning`, `info`.

#### `GET /api/v1/datasets/{dataset_id}/statistics`

Type-appropriate summary statistics per column.

**Response 200:**
```json
{
  "dataset_id": "...",
  "total_rows": 1000,
  "total_columns": 5,
  "columns": [
    {
      "name": "age",
      "inferred_type": "integer",
      "numeric": {
        "count": 988,
        "missing": 12,
        "min": 18,
        "max": 75,
        "mean": 42.3,
        "median": 41.0,
        "std": 12.5,
        "p25": 32.0,
        "p75": 53.0
      }
    },
    {
      "name": "city",
      "inferred_type": "string",
      "categorical": {
        "count": 1000,
        "missing": 0,
        "unique": 42,
        "top_values": [{"value": "London", "count": 150}, ...]
      }
    }
  ]
}
```

---

### Reports

#### `POST /api/v1/reports/`

Generate a report for a dataset. The dataset must be in `ready` status.

**Request:**
```json
{"dataset_id": "...", "title": "Q1 2024 Analysis"}
```

**Response 201:** `ReportResponse` with `snapshot` containing `dataset`, `quality`, and `statistics`.

#### `GET /api/v1/reports/`

List reports. Optionally filter by dataset.

**Query params:** `page`, `page_size`, `dataset_id` (optional UUID filter)

#### `GET /api/v1/reports/{report_id}`

Retrieve a report with its full immutable snapshot.

#### `DELETE /api/v1/reports/{report_id}`

Delete a report.

**Response:** 204 No Content

---

## Pagination

All list endpoints return:

```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "page_size": 50,
  "pages": 1
}
```

Pages are 1-indexed. `pages` is the total number of pages (minimum 1).
