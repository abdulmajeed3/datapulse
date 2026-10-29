# Changelog

All notable changes to DataPulse are documented here.

## [Unreleased]

## [0.1.0] — 2024-10-29

### Added
- User registration and authentication (JWT + Argon2id)
- Access and refresh token management with rotation
- Dataset upload (CSV and JSON)
- File-size, row-count, and column-count limits
- Column type inference (integer, float, datetime, string, boolean, empty)
- Data quality analysis (missing values, duplicates, empty columns, structural findings)
- Summary statistics (numeric, categorical, datetime)
- Paginated dataset preview
- Persisted report snapshots (immutable JSON)
- Resource-level ownership authorization for all endpoints
- OpenAPI documentation at `/docs` and `/redoc`
- Health and readiness endpoints
- Alembic database migrations
- Comprehensive test suite (unit + API + authorization)
- GitHub Actions CI
- Full technical documentation
