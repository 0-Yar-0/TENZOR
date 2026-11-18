"""Единый формат ошибок и исключения приложения."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

class AppError(HTTPException):
    """Базовое доменное исключение с машинным кодом."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_payload(self, request_id: str) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
                "request_id": request_id,
            }
        }

# --- готовые фабрики ---

def bad_request(message: str = "Некорректный запрос", code: str = "BAD_REQUEST", details=None):
    return AppError(400, code, message, details)

def unauthorized(message: str = "Требуется авторизация", code: str = "UNAUTHORIZED", details=None):
    return AppError(401, code, message, details)

def forbidden(message: str = "Доступ запрещён", code: str = "FORBIDDEN", details=None):
    return AppError(403, code, message, details)

def not_found(message: str = "Объект не найден", code: str = "NOT_FOUND", details=None):
    return AppError(404, code, message, details)

def conflict(message: str = "Конфликт", code: str = "CONFLICT", details=None):
    return AppError(409, code, message, details)

def unprocessable(message: str = "Ошибка валидации", code: str = "VALIDATION_ERROR", details=None):
    return AppError(422, code, message, details)

async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    rid = getattr(request.state, "request_id", "unknown")
    return JSONResponse(status_code=exc.status_code, content=exc.to_payload(rid))

async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    rid = getattr(request.state, "request_id", "unknown")
    code = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
    }.get(exc.status_code, "ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": str(exc.detail),
                "details": {},
                "request_id": rid,
            }
        },
    )
