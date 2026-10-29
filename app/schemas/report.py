import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReportCreateRequest(BaseModel):
    dataset_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID | None
    owner_id: uuid.UUID
    title: str
    snapshot: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_orm_with_snapshot(cls, report: Any, snapshot: dict[str, Any]) -> "ReportResponse":
        return cls(
            id=report.id,
            dataset_id=report.dataset_id,
            owner_id=report.owner_id,
            title=report.title,
            snapshot=snapshot,
            created_at=report.created_at,
        )


class ReportListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID | None
    title: str
    created_at: datetime
