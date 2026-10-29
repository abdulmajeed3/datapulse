"""Report service: create, retrieve, list, delete persisted report snapshots."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError, ProcessingError
from app.models.dataset import ProcessingStatus
from app.models.report import Report
from app.models.user import User
from app.schemas.report import ReportCreateRequest, ReportListItem, ReportResponse
from app.services.dataset_service import (
    get_dataset_for_user,
    get_quality_analysis,
    get_statistics,
)


async def create_report(db: AsyncSession, owner: User, data: ReportCreateRequest) -> ReportResponse:
    # Verify ownership and readiness
    dataset = await get_dataset_for_user(db, data.dataset_id, owner.id)
    if dataset.status != ProcessingStatus.READY:
        raise ProcessingError(f"Dataset is not ready (status: {dataset.status}).")

    quality = await get_quality_analysis(db, data.dataset_id, owner.id)
    statistics = await get_statistics(db, data.dataset_id, owner.id)

    snapshot: dict[str, Any] = {
        "dataset": {
            "id": str(dataset.id),
            "name": dataset.name,
            "description": dataset.description,
            "original_filename": dataset.original_filename,
            "file_size_bytes": dataset.file_size_bytes,
            "row_count": dataset.row_count,
            "column_count": dataset.column_count,
            "created_at": dataset.created_at.isoformat(),
        },
        "quality": quality.model_dump(),
        "statistics": statistics.model_dump(),
    }

    report = Report(
        dataset_id=data.dataset_id,
        owner_id=owner.id,
        title=data.title,
        snapshot_json=json.dumps(snapshot, default=str),
    )
    db.add(report)
    await db.flush()

    return ReportResponse.from_orm_with_snapshot(report, snapshot)


async def get_report_for_user(
    db: AsyncSession, report_id: uuid.UUID, user_id: uuid.UUID
) -> ReportResponse:
    report = await db.get(Report, report_id)
    if report is None:
        raise NotFoundError("Report not found.")
    if report.owner_id != user_id:
        raise ForbiddenError("You do not have access to this report.")

    snapshot = json.loads(report.snapshot_json)
    return ReportResponse.from_orm_with_snapshot(report, snapshot)


async def list_reports(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int,
    page_size: int,
    dataset_id: uuid.UUID | None = None,
) -> tuple[list[ReportListItem], int]:
    query = select(Report).where(Report.owner_id == user_id)
    count_query = select(func.count(Report.id)).where(Report.owner_id == user_id)

    if dataset_id is not None:
        query = query.where(Report.dataset_id == dataset_id)
        count_query = count_query.where(Report.dataset_id == dataset_id)

    total: int = await db.scalar(count_query) or 0
    reports = list(
        await db.scalars(
            query.order_by(Report.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    )

    items = [
        ReportListItem(
            id=r.id,
            dataset_id=r.dataset_id,
            title=r.title,
            created_at=r.created_at,
        )
        for r in reports
    ]
    return items, total


async def delete_report(db: AsyncSession, report_id: uuid.UUID, user_id: uuid.UUID) -> None:
    report = await db.get(Report, report_id)
    if report is None:
        raise NotFoundError("Report not found.")
    if report.owner_id != user_id:
        raise ForbiddenError("You do not have permission to delete this report.")
    await db.delete(report)
    await db.flush()
