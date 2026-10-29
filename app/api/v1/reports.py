import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DB, CurrentUser
from app.core.exceptions import ForbiddenError, NotFoundError, ProcessingError
from app.schemas.common import PaginatedResponse
from app.schemas.report import ReportCreateRequest, ReportListItem, ReportResponse
from app.services.report_service import (
    create_report,
    delete_report,
    get_report_for_user,
    list_reports,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _handle_errors(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    if isinstance(exc, ForbiddenError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.message) from exc
    if isinstance(exc, ProcessingError):
        raise HTTPException(status_code=exc.http_status, detail=exc.message) from exc
    raise exc


@router.post("/", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report_endpoint(
    data: ReportCreateRequest,
    current_user: CurrentUser,
    db: DB,
) -> ReportResponse:
    try:
        return await create_report(db, current_user, data)
    except Exception as exc:
        _handle_errors(exc)
        raise


@router.get("/", response_model=PaginatedResponse[ReportListItem])
async def list_reports_endpoint(
    current_user: CurrentUser,
    db: DB,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    dataset_id: uuid.UUID | None = Query(None),
) -> PaginatedResponse[ReportListItem]:
    items, total = await list_reports(db, current_user.id, page, page_size, dataset_id)
    return PaginatedResponse.create(items=items, total=total, page=page, page_size=page_size)


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report_endpoint(
    report_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
) -> ReportResponse:
    try:
        return await get_report_for_user(db, report_id, current_user.id)
    except Exception as exc:
        _handle_errors(exc)
        raise


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report_endpoint(
    report_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
) -> None:
    try:
        await delete_report(db, report_id, current_user.id)
    except Exception as exc:
        _handle_errors(exc)
