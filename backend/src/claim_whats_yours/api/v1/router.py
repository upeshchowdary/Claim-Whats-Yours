"""Version 1 API router assembly."""

from fastapi import APIRouter

from claim_whats_yours.api.v1.endpoints import (
    admin,
    assistant,
    eligibility,
    meta,
    schemes,
    tracking,
)


def api_router() -> APIRouter:
    """Return the version 1 API router under /api/v1."""
    router = APIRouter(prefix="/api/v1")
    router.include_router(meta.router)
    router.include_router(schemes.router)
    router.include_router(eligibility.router)
    router.include_router(assistant.router)
    router.include_router(tracking.router)
    router.include_router(admin.router)
    return router
