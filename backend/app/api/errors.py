"""Uniform error contract and exception handlers.

Every error response is shaped as::

    { "error": { "code": "string", "message": "string", "details": {} } }

Keys are camelCase because the models inherit `ApiModel`.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field

from app.exceptions import (
    ChatMessageNotFound,
    ChatNoReport,
    InvalidObjectId,
    ReportNotFound,
    RunNotFound,
    SessionAlreadyRunning,
    SessionNotFound,
    SessionNotResumable,
    WorkflowUnavailable,
)
from app.logging_config import get_logger
from app.models.base import ApiModel

log = get_logger("api.errors")


class ErrorDetail(ApiModel):
    """The body of an error response."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(ApiModel):
    """Top-level error envelope."""

    error: ErrorDetail


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a serialized (camelCase) error envelope.

    The active request id (bound by :class:`RequestIDMiddleware`) is folded into
    ``details.requestId`` so a user-facing error is traceable to its server logs
    (PLAN_PART_5 §2.1).
    """
    merged = dict(details or {})
    request_id = structlog.contextvars.get_contextvars().get("request_id")
    if request_id and "requestId" not in merged:
        merged["requestId"] = request_id
    body = ErrorResponse(error=ErrorDetail(code=code, message=message, details=merged))
    return body.model_dump(by_alias=True)


def error_json(
    status_code: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    """Construct a `JSONResponse` carrying the standard error envelope."""
    return JSONResponse(status_code=status_code, content=_envelope(code, message, details))


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers for validation, HTTP, and unexpected errors."""

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        log.info("request_validation_error", errors=exc.errors())
        return error_json(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="validation_error",
            message="Request validation failed.",
            details={"errors": exc.errors()},
        )

    @app.exception_handler(SessionNotFound)
    async def _session_not_found_handler(
        request: Request, exc: SessionNotFound
    ) -> JSONResponse:
        return error_json(
            status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=str(exc),
        )

    @app.exception_handler(InvalidObjectId)
    async def _invalid_id_handler(request: Request, exc: InvalidObjectId) -> JSONResponse:
        return error_json(
            status.HTTP_400_BAD_REQUEST,
            code="invalid_id",
            message=str(exc),
        )

    @app.exception_handler(RunNotFound)
    async def _run_not_found_handler(request: Request, exc: RunNotFound) -> JSONResponse:
        return error_json(
            status.HTTP_404_NOT_FOUND, code="run_not_found", message=str(exc)
        )

    @app.exception_handler(ReportNotFound)
    async def _report_not_found_handler(
        request: Request, exc: ReportNotFound
    ) -> JSONResponse:
        return error_json(
            status.HTTP_404_NOT_FOUND, code="report_not_found", message=str(exc)
        )

    @app.exception_handler(SessionAlreadyRunning)
    async def _already_running_handler(
        request: Request, exc: SessionAlreadyRunning
    ) -> JSONResponse:
        return error_json(
            status.HTTP_409_CONFLICT, code="session_already_running", message=str(exc)
        )

    @app.exception_handler(SessionNotResumable)
    async def _not_resumable_handler(
        request: Request, exc: SessionNotResumable
    ) -> JSONResponse:
        return error_json(
            status.HTTP_409_CONFLICT, code="session_not_resumable", message=str(exc)
        )

    @app.exception_handler(WorkflowUnavailable)
    async def _workflow_unavailable_handler(
        request: Request, exc: WorkflowUnavailable
    ) -> JSONResponse:
        return error_json(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            code="workflow_unavailable",
            message=str(exc),
        )

    @app.exception_handler(ChatNoReport)
    async def _chat_no_report_handler(
        request: Request, exc: ChatNoReport
    ) -> JSONResponse:
        return error_json(
            status.HTTP_409_CONFLICT, code="chat_no_report", message=str(exc)
        )

    @app.exception_handler(ChatMessageNotFound)
    async def _chat_message_not_found_handler(
        request: Request, exc: ChatMessageNotFound
    ) -> JSONResponse:
        return error_json(
            status.HTTP_404_NOT_FOUND,
            code="chat_message_not_found",
            message=str(exc),
        )

    @app.exception_handler(HTTPException)
    async def _http_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return error_json(
            exc.status_code,
            code="http_error",
            message=str(exc.detail),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_exception")
        return error_json(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="An unexpected error occurred.",
        )
