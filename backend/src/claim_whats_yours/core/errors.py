"""Application error type and the public error envelope helper."""

from typing import Any

VALIDATION_ERROR: str = "VALIDATION_ERROR"
NOT_FOUND: str = "NOT_FOUND"
SCHEME_NOT_FOUND: str = "SCHEME_NOT_FOUND"
UNAUTHORIZED: str = "UNAUTHORIZED"
ADMIN_DISABLED: str = "ADMIN_DISABLED"
INVALID_QUERY: str = "INVALID_QUERY"
RATE_LIMITED: str = "RATE_LIMITED"
INTERNAL_ERROR: str = "INTERNAL_ERROR"
INVALID_TRANSITION: str = "INVALID_TRANSITION"
TRACKING_NOT_FOUND: str = "TRACKING_NOT_FOUND"
PAYLOAD_TOO_LARGE: str = "PAYLOAD_TOO_LARGE"
INVALID_JSON: str = "INVALID_JSON"


class AppError(Exception):
    """Expected, client-safe error carrying an HTTP status and a stable code."""

    status_code: int
    code: str
    message: str

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def error_body(code: str, message: str, request_id: str) -> dict[str, Any]:
    """Build the standard error response body."""
    return {"error": {"code": code, "message": message, "request_id": request_id}}
