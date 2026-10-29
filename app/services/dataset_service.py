"""Dataset service: upload, processing, access, management."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.analytics.parser import parse_file
from app.analytics.quality import analyze_quality
from app.analytics.statistics import compute_statistics
from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, NotFoundError, ProcessingError, UploadError
from app.models.dataset import Dataset, DatasetColumn, ProcessingStatus
from app.models.user import User
from app.schemas.dataset import (
    DatasetPreviewResponse,
    DatasetUpdateRequest,
    PreviewRow,
    QualityResponse,
    StatisticsResponse,
)
from app.storage.local import delete_upload, load_upload, save_upload


async def create_dataset(
    db: AsyncSession,
    owner: User,
    name: str,
    description: str | None,
    file_content: bytes,
    original_filename: str,
) -> Dataset:
    settings = get_settings()

    if len(file_content) == 0:
        raise UploadError("Uploaded file is empty.")

    if len(file_content) > settings.max_upload_size_bytes:
        limit_mb = settings.max_upload_size_bytes // 1_048_576
        raise UploadError(
            f"File size {len(file_content):,} bytes exceeds the "
            f"limit of {settings.max_upload_size_bytes:,} bytes ({limit_mb} MB)."
        )

    # Validate extension
    filename_lower = original_filename.lower()
    if not (filename_lower.endswith(".csv") or filename_lower.endswith(".json")):
        raise UploadError("Unsupported file type. Only CSV and JSON files are accepted.")

    # Create DB record in PENDING state
    dataset = Dataset(
        owner_id=owner.id,
        name=name,
        description=description,
        original_filename=original_filename,
        file_size_bytes=len(file_content),
        storage_path="",
        status=ProcessingStatus.PENDING,
    )
    db.add(dataset)
    await db.flush()  # get the ID

    try:
        # Save file to storage
        storage_path = save_upload(file_content, owner.id, dataset.id, original_filename)
        dataset.storage_path = storage_path

        # Parse and process
        dataset.status = ProcessingStatus.PROCESSING
        await db.flush()

        result = parse_file(
            file_content, original_filename, settings.max_rows, settings.max_columns
        )

        # Persist column metadata
        for position, col_name in enumerate(result.df.columns):
            col_type = result.inferred_types.get(col_name, "string")
            missing = int(result.df[col_name].isna().sum())
            col = DatasetColumn(
                dataset_id=dataset.id,
                name=col_name,
                inferred_type=col_type,
                position=position,
                missing_count=missing,
            )
            db.add(col)

        dataset.row_count = len(result.df)
        dataset.column_count = len(result.df.columns)
        dataset.status = ProcessingStatus.READY

    except (UploadError, ProcessingError):
        dataset.status = ProcessingStatus.FAILED
        raise
    except Exception as exc:
        dataset.status = ProcessingStatus.FAILED
        dataset.error_message = str(exc)
        raise ProcessingError(f"Unexpected processing error: {exc}") from exc

    await db.flush()
    # Re-query to pick up server-side timestamps and eagerly load the columns relationship
    # so Pydantic can serialize them outside the async greenlet.
    loaded = await db.scalar(
        select(Dataset).options(selectinload(Dataset.columns)).where(Dataset.id == dataset.id)
    )
    assert loaded is not None
    return loaded


async def get_dataset_for_user(
    db: AsyncSession, dataset_id: uuid.UUID, user_id: uuid.UUID
) -> Dataset:
    dataset = await db.scalar(
        select(Dataset).options(selectinload(Dataset.columns)).where(Dataset.id == dataset_id)
    )
    if dataset is None:
        raise NotFoundError("Dataset not found.")
    if dataset.owner_id != user_id:
        raise ForbiddenError("You do not have access to this dataset.")
    return dataset


async def list_datasets(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[Dataset], int]:
    total: int = (
        await db.scalar(select(func.count(Dataset.id)).where(Dataset.owner_id == user_id)) or 0
    )

    datasets = list(
        await db.scalars(
            select(Dataset)
            .where(Dataset.owner_id == user_id)
            .order_by(Dataset.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return datasets, total


async def update_dataset(
    db: AsyncSession,
    dataset_id: uuid.UUID,
    user_id: uuid.UUID,
    data: DatasetUpdateRequest,
) -> Dataset:
    dataset = await get_dataset_for_user(db, dataset_id, user_id)
    if data.name is not None:
        dataset.name = data.name
    if data.description is not None:
        dataset.description = data.description
    await db.flush()
    loaded = await db.scalar(
        select(Dataset).options(selectinload(Dataset.columns)).where(Dataset.id == dataset.id)
    )
    assert loaded is not None
    return loaded


async def delete_dataset(db: AsyncSession, dataset_id: uuid.UUID, user_id: uuid.UUID) -> None:
    dataset = await get_dataset_for_user(db, dataset_id, user_id)
    storage_path = dataset.storage_path
    await db.delete(dataset)
    await db.flush()
    # Clean up file after DB delete succeeds
    if storage_path:
        try:
            delete_upload(storage_path)
        except Exception:  # noqa: S110
            pass  # File already gone; not a failure


def _serialize_value(v: Any) -> Any:
    """Convert pandas/numpy values to JSON-safe Python types."""
    import math

    import numpy as np

    if v is None:
        return None
    if type(v).__name__ in ("NAType", "NaTType"):  # pandas pd.NA / pd.NaT
        return None
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(v, np.bool_):
        return bool(v)
    if hasattr(v, "isoformat"):  # datetime/date/Timestamp
        try:
            return v.isoformat()
        except Exception:
            return str(v)
    if isinstance(v, float):
        return None if (math.isnan(v) or math.isinf(v)) else v
    return v


async def get_dataset_preview(
    db: AsyncSession,
    dataset_id: uuid.UUID,
    user_id: uuid.UUID,
    page: int,
    page_size: int,
) -> DatasetPreviewResponse:
    dataset = await get_dataset_for_user(db, dataset_id, user_id)

    if dataset.status != ProcessingStatus.READY:
        raise ProcessingError(f"Dataset is not ready for preview (status: {dataset.status}).")

    content = load_upload(dataset.storage_path)
    settings = get_settings()
    result = parse_file(content, dataset.original_filename, settings.max_rows, settings.max_columns)

    df = result.df
    total_rows = len(df)
    pages = max(1, -(-total_rows // page_size))
    offset = (page - 1) * page_size
    page_df = df.iloc[offset : offset + page_size]

    rows = [
        PreviewRow(
            index=offset + i,
            data={col: _serialize_value(page_df.iloc[i][col]) for col in df.columns},
        )
        for i in range(len(page_df))
    ]

    return DatasetPreviewResponse(
        dataset_id=dataset_id,
        rows=rows,
        total_rows=total_rows,
        page=page,
        page_size=page_size,
        pages=pages,
    )


async def get_quality_analysis(
    db: AsyncSession,
    dataset_id: uuid.UUID,
    user_id: uuid.UUID,
) -> QualityResponse:
    dataset = await get_dataset_for_user(db, dataset_id, user_id)

    if dataset.status != ProcessingStatus.READY:
        raise ProcessingError(f"Dataset is not ready (status: {dataset.status}).")

    content = load_upload(dataset.storage_path)
    settings = get_settings()
    parsed = parse_file(content, dataset.original_filename, settings.max_rows, settings.max_columns)
    report = analyze_quality(parsed.df, parsed.inferred_types)

    from app.schemas.dataset import ColumnQuality
    from app.schemas.dataset import QualityFinding as QFinding

    return QualityResponse(
        dataset_id=dataset_id,
        total_rows=report.total_rows,
        total_columns=report.total_columns,
        duplicate_rows=report.duplicate_rows,
        findings=[
            QFinding(
                level=f.level,
                code=f.code,
                message=f.message,
                column=f.column,
                details=f.details,
            )
            for f in report.findings
        ],
        columns=[
            ColumnQuality(
                name=c.name,
                inferred_type=c.inferred_type,
                total_count=c.total_count,
                missing_count=c.missing_count,
                missing_pct=c.missing_pct,
                unique_count=c.unique_count,
            )
            for c in report.columns
        ],
    )


async def get_statistics(
    db: AsyncSession,
    dataset_id: uuid.UUID,
    user_id: uuid.UUID,
) -> StatisticsResponse:
    dataset = await get_dataset_for_user(db, dataset_id, user_id)

    if dataset.status != ProcessingStatus.READY:
        raise ProcessingError(f"Dataset is not ready (status: {dataset.status}).")

    content = load_upload(dataset.storage_path)
    settings = get_settings()
    parsed = parse_file(content, dataset.original_filename, settings.max_rows, settings.max_columns)
    stats_report = compute_statistics(parsed.df, parsed.inferred_types)

    from app.schemas.dataset import (
        CategoricalStats,
        ColumnStats,
        DatetimeStats,
        NumericStats,
    )

    col_stats = []
    for cs in stats_report.columns:
        numeric = None
        categorical = None
        dt = None
        if cs.numeric:
            n = cs.numeric
            numeric = NumericStats(
                count=n.count,
                missing=n.missing,
                min=n.min,
                max=n.max,
                mean=n.mean,
                median=n.median,
                std=n.std,
                p25=n.p25,
                p75=n.p75,
            )
        if cs.categorical:
            c = cs.categorical
            categorical = CategoricalStats(
                count=c.count,
                missing=c.missing,
                unique=c.unique,
                top_values=c.top_values,
            )
        if cs.datetime:
            d = cs.datetime
            dt = DatetimeStats(
                count=d.count, missing=d.missing, earliest=d.earliest, latest=d.latest
            )
        col_stats.append(
            ColumnStats(
                name=cs.name,
                inferred_type=cs.inferred_type,
                numeric=numeric,
                categorical=categorical,
                datetime=dt,
            )
        )

    return StatisticsResponse(
        dataset_id=dataset_id,
        total_rows=stats_report.total_rows,
        total_columns=stats_report.total_columns,
        columns=col_stats,
    )
