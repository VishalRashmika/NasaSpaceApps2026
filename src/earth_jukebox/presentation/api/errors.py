"""RFC 7807 problem details error handling (F-066).

Maps domain and HTTP errors to standard problem responses without leaking tracebacks.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from earth_jukebox.domain.errors import (
    InvalidImageError,
    InvalidLegendError,
    JukeboxError,
    NotFoundError,
    RecoveryError,
)

logger = logging.getLogger("earth_jukebox.api")


def _get_request_id(request: Request) -> str:
    req_id = getattr(request.state, "request_id", None)
    if not req_id:
        req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.state.request_id = req_id
    return str(req_id)


def problem_response(
    status: int,
    title: str,
    detail: str,
    code: str,
    request_id: str,
) -> JSONResponse:
    content: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "request_id": request_id,
    }
    return JSONResponse(
        status_code=status,
        content=content,
        media_type="application/problem+json",
        headers={"X-Request-Id": request_id},
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(JukeboxError)
    async def jukebox_error_handler(request: Request, exc: JukeboxError) -> JSONResponse:
        req_id = _get_request_id(request)
        status = 422
        title = "Unprocessable Entity"

        if isinstance(exc, NotFoundError):
            status = 404
            title = "Not Found"
        elif isinstance(exc, InvalidImageError):
            msg = str(exc).lower()
            if "exceeds maximum size" in msg or "too large" in msg:
                status = 413
                title = "Payload Too Large"
            elif "unsupported image format" in msg or "unrecognized image format" in msg:
                status = 415
                title = "Unsupported Media Type"
            else:
                status = 422
                title = "Unprocessable Entity"
        elif isinstance(exc, (InvalidLegendError, RecoveryError)):
            status = 422
            title = "Unprocessable Entity"

        return problem_response(
            status=status,
            title=title,
            detail=str(exc),
            code=exc.code,
            request_id=req_id,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        req_id = _get_request_id(request)
        error_msgs = [
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()
        ]
        detail = "; ".join(error_msgs) if error_msgs else "Validation error"
        return problem_response(
            status=422,
            title="Unprocessable Entity",
            detail=detail,
            code="validation_error",
            request_id=req_id,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        req_id = _get_request_id(request)
        code = f"http_{exc.status_code}"
        if exc.status_code == 404:
            code = "not_found"
        elif exc.status_code == 413:
            code = "payload_too_large"
        elif exc.status_code == 415:
            code = "unsupported_media_type"
        elif exc.status_code == 501:
            code = "not_implemented"

        detail = str(exc.detail) if exc.detail else "HTTP error"
        title = detail if exc.status_code != 500 else "Internal Server Error"
        return problem_response(
            status=exc.status_code,
            title=title,
            detail=detail,
            code=code,
            request_id=req_id,
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        req_id = _get_request_id(request)
        logger.exception("Unhandled server error: %s (request_id=%s)", exc, req_id)
        return problem_response(
            status=500,
            title="Internal Server Error",
            detail="An unexpected error occurred. Please try again later.",
            code="internal_error",
            request_id=req_id,
        )
