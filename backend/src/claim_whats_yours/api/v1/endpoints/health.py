"""Liveness and readiness probes."""

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from claim_whats_yours.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    """Report that the process is running."""
    return {"status": "ok"}


@router.get("/health/ready", response_model=None)
def ready(db: Session = Depends(get_db)) -> dict[str, str] | JSONResponse:
    """Report whether the database answers a trivial query."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        body: dict[str, Any] = {"status": "unavailable"}
        return JSONResponse(status_code=503, content=body)
    return {"status": "ok"}
