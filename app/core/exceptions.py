from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | list[Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


def error_response(
    code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | list[Any] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=body.model_dump())


# ─── Domain exceptions ──────────────────────────────────────────────


class DataPulseError(Exception):
    """Base exception for DataPulse domain errors."""

    http_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"
    default_message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class NotFoundError(DataPulseError):
    http_status = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"
    default_message = "Resource not found."


class UnauthorizedError(DataPulseError):
    http_status = status.HTTP_401_UNAUTHORIZED
    error_code = "UNAUTHORIZED"
    default_message = "Authentication required."


class ForbiddenError(DataPulseError):
    http_status = status.HTTP_403_FORBIDDEN
    error_code = "FORBIDDEN"
    default_message = "You do not have permission to access this resource."


class ConflictError(DataPulseError):
    http_status = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"
    default_message = "A conflict occurred."


class ValidationError(DataPulseError):
    http_status = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = "VALIDATION_ERROR"
    default_message = "Validation failed."


class UploadError(DataPulseError):
    http_status = status.HTTP_400_BAD_REQUEST
    error_code = "UPLOAD_ERROR"
    default_message = "File upload failed."


class ProcessingError(DataPulseError):
    http_status = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = "PROCESSING_ERROR"
    default_message = "Dataset processing failed."


# ─── FastAPI exception handlers ─────────────────────────────────────


async def datapulse_exception_handler(request: Request, exc: DataPulseError) -> JSONResponse:
    return error_response(
        code=exc.error_code,
        message=exc.message,
        status_code=exc.http_status,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        413: "PAYLOAD_TOO_LARGE",
        422: "UNPROCESSABLE_ENTITY",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR",
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    return error_response(code=code, message=str(exc.detail), status_code=exc.status_code)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]} for err in exc.errors()
    ]
    return error_response(
        code="VALIDATION_ERROR",
        message="Request validation failed.",
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        details=details,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return error_response(
        code="INTERNAL_ERROR",
        message="An internal server error occurred.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
