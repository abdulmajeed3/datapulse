import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from app.api.deps import DB, CurrentUser
from app.core.exceptions import (
    ForbiddenError,
    NotFoundError,
    ProcessingError,
    UploadError,
)
from app.schemas.common import PaginatedResponse
from app.schemas.dataset import (
    DatasetListItem,
    DatasetPreviewResponse,
    DatasetResponse,
    DatasetUpdateRequest,
    QualityResponse,
    StatisticsResponse,
)
from app.services.dataset_service import (
    create_dataset,
    delete_dataset,
    get_dataset_for_user,
    get_dataset_preview,
    get_quality_analysis,
    get_statistics,
    list_datasets,
    update_dataset,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _handle_dataset_errors(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    if isinstance(exc, ForbiddenError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.message) from exc
    if isinstance(exc, (UploadError, ProcessingError)):
        raise HTTPException(status_code=exc.http_status, detail=exc.message) from exc
    raise exc


@router.post("/", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    current_user: CurrentUser,
    db: DB,
    file: UploadFile = File(..., description="CSV or JSON file to upload"),
    name: str = Form(..., min_length=1, max_length=255, description="Dataset name"),
    description: str | None = Form(None, max_length=2000, description="Optional description"),
) -> DatasetResponse:
    content = await file.read()
    original_filename = file.filename or "upload"
    try:
        dataset = await create_dataset(
            db, current_user, name, description, content, original_filename
        )
        return DatasetResponse.model_validate(dataset)
    except Exception as exc:
        _handle_dataset_errors(exc)
        raise  # unreachable; satisfies mypy


@router.get("/", response_model=PaginatedResponse[DatasetListItem])
async def list_user_datasets(
    current_user: CurrentUser,
    db: DB,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
) -> PaginatedResponse[DatasetListItem]:
    datasets, total = await list_datasets(db, current_user.id, page, page_size)
    items = [DatasetListItem.model_validate(d) for d in datasets]
    return PaginatedResponse.create(items=items, total=total, page=page, page_size=page_size)


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
) -> DatasetResponse:
    try:
        dataset = await get_dataset_for_user(db, dataset_id, current_user.id)
        return DatasetResponse.model_validate(dataset)
    except Exception as exc:
        _handle_dataset_errors(exc)
        raise


@router.patch("/{dataset_id}", response_model=DatasetResponse)
async def update_dataset_endpoint(
    dataset_id: uuid.UUID,
    data: DatasetUpdateRequest,
    current_user: CurrentUser,
    db: DB,
) -> DatasetResponse:
    try:
        dataset = await update_dataset(db, dataset_id, current_user.id, data)
        return DatasetResponse.model_validate(dataset)
    except Exception as exc:
        _handle_dataset_errors(exc)
        raise


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset_endpoint(
    dataset_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
) -> None:
    try:
        await delete_dataset(db, dataset_id, current_user.id)
    except Exception as exc:
        _handle_dataset_errors(exc)


@router.get("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
async def preview_dataset(
    dataset_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
) -> DatasetPreviewResponse:
    try:
        return await get_dataset_preview(db, dataset_id, current_user.id, page, page_size)
    except Exception as exc:
        _handle_dataset_errors(exc)
        raise


@router.get("/{dataset_id}/quality", response_model=QualityResponse)
async def quality_analysis(
    dataset_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
) -> QualityResponse:
    try:
        return await get_quality_analysis(db, dataset_id, current_user.id)
    except Exception as exc:
        _handle_dataset_errors(exc)
        raise


@router.get("/{dataset_id}/statistics", response_model=StatisticsResponse)
async def statistics(
    dataset_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
) -> StatisticsResponse:
    try:
        return await get_statistics(db, dataset_id, current_user.id)
    except Exception as exc:
        _handle_dataset_errors(exc)
        raise
