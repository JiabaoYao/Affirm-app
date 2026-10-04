"""One error shape for every failure: {"detail": "...", "code": "..."} (+ "errors" for validation)."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class FieldError(BaseModel):
    field: str
    message: str


class ErrorOut(BaseModel):
    detail: str
    code: str
    errors: list[FieldError] | None = None


class AppError(Exception):
    """A business error the client can act on, rendered with a machine-readable `code`."""

    def __init__(self, status_code: int, code: str, detail: str, headers: dict[str, str] | None = None):
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.headers = headers


def unauthorized(code: str, detail: str) -> AppError:
    return AppError(401, code, detail, headers={"WWW-Authenticate": "Bearer"})


_DEFAULT_CODES = {
    400: "BAD_REQUEST",
    401: "NOT_AUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
}

_DESCRIPTIONS = {
    400: "Business rule violation",
    401: "Missing, invalid, expired or revoked token",
    403: "Your role can't use this endpoint",
    404: "Not found, or it belongs to another user",
    409: "Conflicts with the resource's current state",
    422: "Validation failed",
}


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses=` entries so Swagger documents each error with the ErrorOut shape."""
    return {code: {"model": ErrorOut, "description": _DESCRIPTIONS[code]} for code in status_codes}


def _error(status_code: int, code: str, detail: str, *, errors=None, headers=None) -> JSONResponse:
    content: dict[str, Any] = {"detail": detail, "code": code}
    if errors is not None:
        content["errors"] = errors
    return JSONResponse(status_code=status_code, content=content, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.detail, headers=exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _DEFAULT_CODES.get(exc.status_code, "HTTP_ERROR")
        return _error(exc.status_code, code, str(exc.detail), headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": ".".join(str(part) for part in err["loc"] if part != "body"), "message": err["msg"]}
            for err in exc.errors()
        ]
        return _error(422, "VALIDATION_ERROR", "Request validation failed.", errors=errors)

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return _error(500, "INTERNAL_ERROR", "Something went wrong.")
