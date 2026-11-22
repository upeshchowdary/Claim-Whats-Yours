"""Tracking service: one-time access tokens and tracker record lifecycle.

Only a SHA-256 hash of the access token is stored. The plain token is returned
once, by ``create_tracking``, and is never persisted or logged. The caller owns
the transaction: these functions use ``session.add`` and ``session.flush`` only.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from claim_whats_yours.db.models import TrackingRecord

TRACKING_STATUSES: frozenset[str] = frozenset(
    {"planned", "in_progress", "submitted", "approved", "rejected", "withdrawn"}
)

_UPDATABLE_FIELDS: frozenset[str] = frozenset(
    {"status", "scheme_id", "progress_date", "reminder_date"}
)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _validate_status(status: str) -> None:
    if status not in TRACKING_STATUSES:
        raise ValueError("INVALID_STATUS")


def _validate_dates(progress_date: date | None, reminder_date: date | None) -> None:
    if progress_date is not None and reminder_date is not None and reminder_date < progress_date:
        raise ValueError("INVALID_REMINDER_DATE")


def create_tracking(
    session: Session,
    scheme_id: str | None,
    status: str,
    progress_date: date | None,
    reminder_date: date | None,
    now: datetime,
) -> tuple[TrackingRecord, str]:
    """Create a tracker record and return it with its one-time plain access token."""
    _validate_status(status)
    _validate_dates(progress_date, reminder_date)

    token = secrets.token_urlsafe(32)
    record = TrackingRecord(
        tracking_id="trk_" + secrets.token_urlsafe(12),
        access_token_hash=_hash_token(token),
        scheme_id=scheme_id,
        status=status,
        progress_date=progress_date,
        reminder_date=reminder_date,
        created_at=now,
        updated_at=now,
    )
    session.add(record)
    session.flush()
    return record, token


def get_tracking(session: Session, tracking_id: str, token: str) -> TrackingRecord | None:
    """Return the record only when the presented token matches. Missing id and wrong token
    both return None, so callers cannot tell them apart."""
    record = session.execute(
        select(TrackingRecord).where(TrackingRecord.tracking_id == tracking_id)
    ).scalar_one_or_none()
    if record is None:
        return None
    presented = _hash_token(token)
    if not hmac.compare_digest(presented, record.access_token_hash):
        return None
    return record


def update_tracking(
    session: Session,
    tracking_id: str,
    token: str,
    changes: dict[str, Any],
    now: datetime,
) -> TrackingRecord | None:
    """Apply whitelisted changes to a tracker record the token can access."""
    unknown = set(changes) - _UPDATABLE_FIELDS
    if unknown:
        raise ValueError("UNKNOWN_FIELD")

    record = get_tracking(session, tracking_id, token)
    if record is None:
        return None

    new_status = changes.get("status", record.status)
    new_progress = changes.get("progress_date", record.progress_date)
    new_reminder = changes.get("reminder_date", record.reminder_date)
    _validate_status(new_status)
    _validate_dates(new_progress, new_reminder)

    if "scheme_id" in changes:
        record.scheme_id = changes["scheme_id"]
    record.status = new_status
    record.progress_date = new_progress
    record.reminder_date = new_reminder
    record.updated_at = now
    session.flush()
    return record
