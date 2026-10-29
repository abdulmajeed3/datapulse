from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DB
from app.schemas.common import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check(db: DB) -> ReadinessResponse:
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return ReadinessResponse(status="ok" if db_status == "ok" else "degraded", database=db_status)
