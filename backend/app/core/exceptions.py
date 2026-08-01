"""Application exceptions and FastAPI exception handlers."""

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.error_codes import ErrorCode

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base exception for safe, structured client errors."""

    def __init__(
        self,
        *,
        code: ErrorCode,
        message: str,
        status_code: int,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = dict(details or {})


class DatabaseUnavailableError(AppError):
    """Raised when the configured SQLite database cannot be reached."""

    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.DATABASE_UNAVAILABLE,
            message="数据库暂时不可用",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            retryable=True,
        )


class ThreadNotFoundError(AppError):
    """Raised when a requested thread does not exist."""

    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.THREAD_NOT_FOUND,
            message="会话不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ThreadBusyError(AppError):
    """Raised when an operation conflicts with an active thread run."""

    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.THREAD_BUSY,
            message="会话正在执行任务",
            status_code=status.HTTP_409_CONFLICT,
            retryable=True,
        )


class MessageEmptyError(AppError):
    """Raised when a chat request contains no visible text."""

    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.MESSAGE_EMPTY,
            message="消息不能为空",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))


def _error_response(
    *,
    request: Request,
    status_code: int,
    code: ErrorCode,
    message: str,
    retryable: bool,
    details: Mapping[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code.value,
                "message": message,
                "retryable": retryable,
                "details": dict(details or {}),
                "request_id": _request_id(request),
            }
        },
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Convert a known application error into the public error envelope."""
    return _error_response(
        request=request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        retryable=exc.retryable,
        details=exc.details,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return validation locations without reflecting unsafe input values."""
    safe_errors = [
        {"location": [str(part) for part in error["loc"]], "type": error["type"]}
        for error in exc.errors()
    ]
    return _error_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code=ErrorCode.REQUEST_VALIDATION_ERROR,
        message="请求参数校验失败",
        retryable=False,
        details={"errors": safe_errors},
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log unexpected failures while returning a non-sensitive message."""
    logger.exception(
        "Unhandled application exception",
        extra={"request_id": _request_id(request)},
    )
    return _error_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code=ErrorCode.INTERNAL_ERROR,
        message="服务器内部错误",
        retryable=False,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register the common exception mapping for all API routes."""
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unexpected_error_handler)
