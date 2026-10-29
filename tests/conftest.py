"""Shared test configuration.

Unit tests (tests/unit/) do NOT require a database.
API/integration tests (tests/api/) use tests/api/conftest.py for DB setup.
"""

from __future__ import annotations

import os

# Patch settings before any app import so the test DB/env is used everywhere.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://datapulse:datapulse@localhost:5432/datapulse_test",
)
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-only")
os.environ.setdefault("UPLOAD_DIR", "/tmp/datapulse_test_uploads")

# ─── Shared test data ────────────────────────────────────────────────

SAMPLE_CSV = b"""name,age,city,score
Alice,30,New York,95.5
Bob,25,London,87.2
Charlie,,Paris,
Diana,35,Tokyo,92.1
Eve,28,Berlin,78.9
"""

SMALL_CSV = b"col_a,col_b\n1,foo\n2,bar\n3,baz\n"
EMPTY_CSV = b""
HEADER_ONLY_CSV = b"name,age,city\n"
