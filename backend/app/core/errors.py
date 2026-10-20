"""
GlucoTwin AI - Standardized Error Handling & Envelopes
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppException(Exception):
    """Base application exception with structured code and status."""
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[List[Dict[str, Any]]] = None
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []


class NotFoundException(AppException):
    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            code="RESOURCE_NOT_FOUND",
            message=f"{resource} with ID '{resource_id}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            details=[{"resource": resource, "id": resource_id}]
        )


class ValidationException(AppException):
    def __init__(self, message: str, details: Optional[List[Dict[str, Any]]] = None):
        super().__init__(
            code="VALIDATION_FAILED",
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details or []
        )


def build_error_response(
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    details: Optional[List[Dict[str, Any]]] = None
) -> JSONResponse:
    """Constructs the canonical JSON error envelope."""
    now_iso = datetime.now(timezone.utc).isoformat()
    content = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "details": details or []
        },
        "metadata": {
            "timestamp": now_iso,
            "request_id": request_id
        }
    }
    return JSONResponse(status_code=status_code, content=content)


def register_error_handlers(app: FastAPI) -> None:
    """Registers global exception handlers for the FastAPI application."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "req-unknown")
        return build_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
            details=exc.details
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "req-unknown")
        # Map common status codes to codes
        code_mapping = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            500: "INTERNAL_SERVER_ERROR",
            503: "SERVICE_UNAVAILABLE"
        }
        code = code_mapping.get(exc.status_code, "HTTP_ERROR")
        return build_error_response(
            status_code=exc.status_code,
            code=code,
            message=str(exc.detail),
            request_id=request_id
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "req-unknown")
        formatted_details = []
        for error in exc.errors():
            formatted_details.append({
                "field": ".".join(str(loc) for loc in error.get("loc", [])),
                "issue": error.get("type", "INVALID_VALUE"),
                "message": error.get("msg", "Invalid value")
            })

        return build_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="REQUEST_VALIDATION_ERROR",
            message="The request payload failed schema validation.",
            request_id=request_id,
            details=formatted_details
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "req-unknown")
        # Suppress stack trace in response to prevent information disclosure
        return build_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected server error occurred. Please contact the research system administrator.",
            request_id=request_id
        )
