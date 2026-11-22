"""Tracking endpoints. The access token is returned only by POST; GET and PATCH never echo it."""

from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from claim_whats_yours.core.errors import AppError
from claim_whats_yours.db.models import Scheme, TrackingRecord
from claim_whats_yours.db.session import get_db
from claim_whats_yours.schemas.tracking import TrackingCreate, TrackingUpdate
from claim_whats_yours.services.tracking_service import (
    create_tracking,
    get_tracking,
    update_tracking,
)

router = APIRouter(prefix="/tracking", tags=["tracking"])

_VALUE_ERROR_MESSAGES: dict[str, str] = {
    "INVALID_STATUS": "status is not a recognised tracking status.",
    "INVALID_REMINDER_DATE": "reminder_date must not be earlier than progress_date.",
    "UNKNOWN_FIELD": "The request contains a field that cannot be updated.",
}


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _require_token(token: str | None) -> str:
    if not token:
        raise AppError(401, "UNAUTHORIZED", "A tracking token is required.")
    return token


def _ensure_published(session: Session, scheme_id: str | None) -> None:
    if scheme_id is None:
        return
    found = session.execute(
        select(Scheme.id).where(Scheme.id == scheme_id, Scheme.record_status == "published")
    ).scalar_one_or_none()
    if found is None:
        raise AppError(422, "VALIDATION_ERROR", "scheme_id must reference a published scheme.")


def _map_value_error(exc: ValueError) -> AppError:
    code = str(exc)
    message = _VALUE_ERROR_MESSAGES.get(code, "The tracking request is invalid.")
    return AppError(422, code, message)


def _record_view(record: TrackingRecord) -> dict[str, Any]:
    return {
        "tracking_id": record.tracking_id,
        "status": record.status,
        "scheme_id": record.scheme_id,
        "progress_date": _iso(record.progress_date),
        "reminder_date": _iso(record.reminder_date),
        "created_at": _iso(record.created_at),
        "updated_at": _iso(record.updated_at),
    }


@router.post("", status_code=201)
def create(body: TrackingCreate, session: Session = Depends(get_db)) -> dict[str, Any]:
    """Create a tracker record. The plain access token is returned here and nowhere else."""
    _ensure_published(session, body.scheme_id)
    now = datetime.now(UTC)
    try:
        record, token = create_tracking(
            session,
            body.scheme_id,
            body.status,
            body.progress_date,
            body.reminder_date,
            now,
        )
    except ValueError as exc:
        raise _map_value_error(exc) from exc
    session.commit()
    return {
        "tracking_id": record.tracking_id,
        "token": token,
        "status": record.status,
        "scheme_id": record.scheme_id,
        "progress_date": _iso(record.progress_date),
        "reminder_date": _iso(record.reminder_date),
    }


@router.get("/{tracking_id}")
def read(
    tracking_id: str,
    x_tracking_token: str | None = Header(default=None, alias="X-Tracking-Token"),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return a tracker record the presented token can access."""
    token = _require_token(x_tracking_token)
    record = get_tracking(session, tracking_id, token)
    if record is None:
        raise AppError(404, "TRACKING_NOT_FOUND", "Tracking record not found.")
    return _record_view(record)


@router.patch("/{tracking_id}")
def patch(
    tracking_id: str,
    body: TrackingUpdate,
    x_tracking_token: str | None = Header(default=None, alias="X-Tracking-Token"),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Apply a partial update to a tracker record the presented token can access."""
    token = _require_token(x_tracking_token)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("scheme_id") is not None:
        _ensure_published(session, changes["scheme_id"])
    try:
        record = update_tracking(session, tracking_id, token, changes, datetime.now(UTC))
    except ValueError as exc:
        raise _map_value_error(exc) from exc
    if record is None:
        raise AppError(404, "TRACKING_NOT_FOUND", "Tracking record not found.")
    session.commit()
    return _record_view(record)
