"""FastAPI application factory."""

import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from claim_whats_yours import __version__
from claim_whats_yours.api.v1.endpoints import health
from claim_whats_yours.api.v1.router import api_router
from claim_whats_yours.core.config import get_settings
from claim_whats_yours.core.errors import AppError, error_body

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
MAX_BODY_BYTES = 65536


def _request_id(request: Request) -> str:
    """Return the request ID stored by the middleware."""
    return str(getattr(request.state, "request_id", ""))


class RequestSizeLimitMiddleware:
    """Pure ASGI guard that rejects oversized bodies before the app sees them."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = scope.get("headers", [])
        request_id = "unknown"
        declared_length: int | None = None
        for name, value in headers:
            if name == b"content-length":
                try:
                    declared_length = int(value)
                except ValueError:
                    declared_length = None
            elif name == b"x-request-id":
                request_id = value.decode("latin-1") or "unknown"

        if declared_length is not None and declared_length > self.max_bytes:
            await self._send_too_large(scope, receive, send, request_id)
            return

        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            body = message.get("body", b"")
            total += len(body)
            if total > self.max_bytes:
                await self._send_too_large(scope, receive, send, request_id)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break

        body_bytes = b"".join(chunks)
        replayed = False

        async def replay_receive() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body_bytes, "more_body": False}
            return {"type": "http.disconnect"}

        await self.app(scope, replay_receive, send)

    async def _send_too_large(
        self, scope: Scope, receive: Receive, send: Send, request_id: str
    ) -> None:
        """Send the 413 envelope without logging the request body."""
        response = JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": "Request body is too large.",
                    "request_id": request_id,
                }
            },
        )
        await response(scope, receive, send)


def _register_middleware(app: FastAPI) -> None:
    """Attach CORS and request-ID middleware."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "X-Request-ID", "X-Tracking-Token", "X-Admin-Token"],
    )

    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=MAX_BODY_BYTES)

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def _register_exception_handlers(app: FastAPI) -> None:
    """Map errors to the public error envelope."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, _request_id(request)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        body = error_body("VALIDATION_ERROR", "Request validation failed.", _request_id(request))
        body["error"]["details"] = [
            {"loc": list(err.get("loc", ())), "msg": err.get("msg", "")} for err in exc.errors()
        ]
        return JSONResponse(status_code=422, content=body)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, "Request could not be completed.", _request_id(request)),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        logger.error(
            "unhandled_exception request_id=%s exc_type=%s", request_id, type(exc).__name__
        )
        return JSONResponse(
            status_code=500,
            content=error_body("INTERNAL_ERROR", "An unexpected error occurred.", request_id),
        )


def create_app() -> FastAPI:
    """Build the FastAPI application with middleware, handlers and routers."""
    app = FastAPI(title=get_settings().app_name, version=__version__)
    _register_middleware(app)
    _register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(api_router())
    return app
