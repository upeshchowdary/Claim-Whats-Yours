"""Shared FastAPI dependencies. The admin token is compared in constant time and never logged."""

import hmac

from fastapi import Header

from claim_whats_yours.core.config import get_settings
from claim_whats_yours.core.errors import AppError


def require_admin(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    """Allow the request only when the configured admin token is present and matches."""
    configured = get_settings().admin_api_token
    if not configured:
        raise AppError(403, "ADMIN_DISABLED", "Admin endpoints are disabled.")
    if x_admin_token is None:
        raise AppError(403, "ADMIN_TOKEN_INVALID", "Admin token required.")
    if not hmac.compare_digest(x_admin_token.encode(), configured.encode()):
        raise AppError(403, "ADMIN_TOKEN_INVALID", "Admin token invalid.")
