"""Integration tests for the tracking endpoints. Synthetic data only."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from claim_whats_yours.db import models

BASE_URL = "/api/v1/tracking"
TOKEN_HEADER = "X-Tracking-Token"
PUBLISHED_ID = "trk-published-scheme"
DRAFT_ID = "trk-draft-scheme"


@pytest.fixture
def schemes(db: Session, scheme_factory: Callable[..., models.Scheme]) -> None:
    """One published and one draft synthetic scheme."""
    scheme_factory(db, PUBLISHED_ID)
    scheme_factory(db, DRAFT_ID, record_status="draft")


def _create(client: Any, body: dict[str, Any] | None = None) -> Any:
    """Create a tracker record and return the parsed 201 response body."""
    payload = body if body is not None else {"status": "planned"}
    response = client.post(BASE_URL, json=payload)
    assert response.status_code == 201
    return response.json()


def _url(tracking_id: str) -> str:
    return f"{BASE_URL}/{tracking_id}"


def test_create_returns_201_with_trk_id_and_token(client: Any, schemes: None) -> None:
    response = client.post(BASE_URL, json={"status": "planned"})

    assert response.status_code == 201
    body = response.json()
    assert body["tracking_id"].startswith("trk_")
    assert isinstance(body["token"], str)
    assert body["token"]


def test_create_with_published_scheme_returns_201(client: Any, schemes: None) -> None:
    response = client.post(BASE_URL, json={"status": "planned", "scheme_id": PUBLISHED_ID})

    assert response.status_code == 201
    assert response.json()["scheme_id"] == PUBLISHED_ID


def test_create_with_unknown_scheme_returns_422(client: Any, schemes: None) -> None:
    response = client.post(BASE_URL, json={"status": "planned", "scheme_id": "no-such-scheme"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_with_draft_scheme_returns_422(client: Any, schemes: None) -> None:
    response = client.post(BASE_URL, json={"status": "planned", "scheme_id": DRAFT_ID})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_with_bogus_status_returns_422(client: Any) -> None:
    response = client.post(BASE_URL, json={"status": "bogus"})

    assert response.status_code == 422


def test_create_with_reminder_before_progress_returns_invalid_reminder_date(
    client: Any,
) -> None:
    response = client.post(
        BASE_URL,
        json={
            "status": "planned",
            "progress_date": "2030-06-01",
            "reminder_date": "2030-05-01",
        },
    )

    assert response.status_code == 422
    assert "INVALID_REMINDER_DATE" in response.text


@pytest.mark.parametrize(
    "status",
    ["planned", "in_progress", "submitted", "approved", "rejected", "withdrawn"],
)
def test_create_accepts_every_tracking_status(client: Any, status: str) -> None:
    response = client.post(BASE_URL, json={"status": status})

    assert response.status_code == 201
    assert response.json()["status"] == status


def test_get_with_token_returns_record_without_secrets(client: Any) -> None:
    created = _create(client)

    response = client.get(_url(created["tracking_id"]), headers={TOKEN_HEADER: created["token"]})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "planned"
    assert "token" not in body
    assert "access_token_hash" not in body


def test_get_without_token_header_returns_401(client: Any) -> None:
    created = _create(client)

    response = client.get(_url(created["tracking_id"]))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_get_with_wrong_token_returns_404(client: Any) -> None:
    created = _create(client)

    response = client.get(_url(created["tracking_id"]), headers={TOKEN_HEADER: "wrong-token"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TRACKING_NOT_FOUND"


def test_get_with_unknown_tracking_id_returns_404(client: Any) -> None:
    created = _create(client)

    response = client.get(_url("trk_does_not_exist"), headers={TOKEN_HEADER: created["token"]})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TRACKING_NOT_FOUND"


def test_patch_with_right_token_updates_status(client: Any) -> None:
    created = _create(client)

    response = client.patch(
        _url(created["tracking_id"]),
        json={"status": "submitted"},
        headers={TOKEN_HEADER: created["token"]},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "submitted"


def test_patch_with_wrong_token_returns_404(client: Any) -> None:
    created = _create(client)

    response = client.patch(
        _url(created["tracking_id"]),
        json={"status": "submitted"},
        headers={TOKEN_HEADER: "wrong-token"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TRACKING_NOT_FOUND"


def test_patch_with_empty_body_returns_422(client: Any) -> None:
    created = _create(client)

    response = client.patch(
        _url(created["tracking_id"]),
        json={},
        headers={TOKEN_HEADER: created["token"]},
    )

    assert response.status_code == 422


def test_patch_with_draft_scheme_id_returns_422(client: Any, schemes: None) -> None:
    created = _create(client)

    response = client.patch(
        _url(created["tracking_id"]),
        json={"scheme_id": DRAFT_ID},
        headers={TOKEN_HEADER: created["token"]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_database_stores_sha256_hash_not_token(client: Any, db: Session) -> None:
    created = _create(client)

    record = db.execute(
        select(models.TrackingRecord).where(
            models.TrackingRecord.tracking_id == created["tracking_id"]
        )
    ).scalar_one()

    assert len(record.access_token_hash) == 64
    assert record.access_token_hash != created["token"]
    assert record.access_token_hash == hashlib.sha256(created["token"].encode("utf-8")).hexdigest()
