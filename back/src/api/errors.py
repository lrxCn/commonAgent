"""Unified API error responses (PRD demo-admin-console)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """Application error with PRD-shaped JSON body."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        field_errors: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.field_errors = field_errors or {}


def register_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApiError)
    async def handle_api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "field_errors": exc.field_errors,
            },
        )


def unauthorized(message: str = "未登录或会话已失效") -> ApiError:
    return ApiError(status_code=401, code="UNAUTHORIZED", message=message)


def invalid_credentials() -> ApiError:
    return ApiError(status_code=401, code="UNAUTHORIZED", message="用户名或密码错误")


def not_found(message: str = "资源不存在") -> ApiError:
    return ApiError(status_code=404, code="NOT_FOUND", message=message)


def conflict(
    message: str,
    *,
    field_errors: dict[str, str] | None = None,
) -> ApiError:
    return ApiError(
        status_code=409,
        code="CONFLICT",
        message=message,
        field_errors=field_errors,
    )
