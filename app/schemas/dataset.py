import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ColumnInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    inferred_type: str
    position: int
    missing_count: int


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    original_filename: str
    file_size_bytes: int
    status: str
    error_message: str | None
    row_count: int | None
    column_count: int | None
    created_at: datetime
    updated_at: datetime
    columns: list[ColumnInfo] = []


class DatasetCreateResponse(BaseModel):
    """Returned immediately after upload before processing completes."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: str
    message: str


class DatasetUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)


class DatasetListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    original_filename: str
    file_size_bytes: int
    status: str
    row_count: int | None
    column_count: int | None
    created_at: datetime


class PreviewRow(BaseModel):
    index: int
    data: dict[str, Any]


class DatasetPreviewResponse(BaseModel):
    dataset_id: uuid.UUID
    rows: list[PreviewRow]
    total_rows: int
    page: int
    page_size: int
    pages: int


# ─── Quality schemas ─────────────────────────────────────────────────


class QualityFinding(BaseModel):
    level: str  # error | warning | info
    code: str
    message: str
    column: str | None = None
    details: dict[str, Any] | None = None


class ColumnQuality(BaseModel):
    name: str
    inferred_type: str
    total_count: int
    missing_count: int
    missing_pct: float
    unique_count: int | None = None


class QualityResponse(BaseModel):
    dataset_id: uuid.UUID
    total_rows: int
    total_columns: int
    duplicate_rows: int
    findings: list[QualityFinding]
    columns: list[ColumnQuality]


# ─── Statistics schemas ───────────────────────────────────────────────


class NumericStats(BaseModel):
    count: int
    missing: int
    min: float | None
    max: float | None
    mean: float | None
    median: float | None
    std: float | None
    p25: float | None
    p75: float | None


class CategoricalStats(BaseModel):
    count: int
    missing: int
    unique: int
    top_values: list[dict[str, Any]]


class DatetimeStats(BaseModel):
    count: int
    missing: int
    earliest: str | None
    latest: str | None


class ColumnStats(BaseModel):
    name: str
    inferred_type: str
    numeric: NumericStats | None = None
    categorical: CategoricalStats | None = None
    datetime: DatetimeStats | None = None


class StatisticsResponse(BaseModel):
    dataset_id: uuid.UUID
    total_rows: int
    total_columns: int
    columns: list[ColumnStats]
