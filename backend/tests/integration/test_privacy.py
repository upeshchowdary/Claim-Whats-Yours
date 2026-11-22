"""Integration tests for privacy and security guarantees. All data here is synthetic."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy.orm import Session

from claim_whats_yours.db import models
from claim_whats_yours.db.base import Base

EVALUATE_PATH = "/api/v1/eligibility/evaluate"
SCHEMES_PATH = "/api/v1/schemes"
ADMIN_TOKEN = "test-admin-token-123"
SENSITIVE_VALUE = "SECRETVALUE-QZX"
FULL_PROFILE: dict[str, Any] = {
    "age_years": 25,
    "state_code": "IN-AP",
    "annual_household_income_inr": 150000,
}
# Request body size limit is specified in docs/backend/PRIVACY_SECURITY.md. If the app does
# not enforce it, the oversized-body test below must fail honestly rather than be skipped.
OVERSIZED_NOTE_LENGTH = 70000


@pytest.mark.parametrize(
    "field",
    [
        "aadhaar",
        "pan",
        "bank_account",
        "password",
        "phone",
        "email",
        "government_id",
    ],
)
def test_sensitive_identifier_keys_are_rejected_without_echo(client: Any, field: str) -> None:
    response = client.post(EVALUATE_PATH, json={"answers": {field: SENSITIVE_VALUE}})

    assert response.status_code == 422
    assert SENSITIVE_VALUE not in response.text


def test_unknown_answer_key_is_rejected_without_echo(client: Any) -> None:
    response = client.post(EVALUATE_PATH, json={"answers": {"favourite_colour": "blue"}})

    assert response.status_code == 422
    assert "blue" not in response.text


def test_evaluation_is_stateless(client: Any, db: Session) -> None:
    tracking_before = db.query(models.TrackingRecord).count()
    schemes_before = db.query(models.Scheme).count()

    response = client.post(EVALUATE_PATH, json={"answers": FULL_PROFILE})

    assert response.status_code == 200
    assert db.query(models.TrackingRecord).count() == tracking_before
    assert db.query(models.Scheme).count() == schemes_before


def test_no_citizen_profile_or_answer_table_exists() -> None:
    table_names = list(Base.metadata.tables.keys())

    offending = [name for name in table_names if "profile" in name or "answer" in name]
    assert offending == []


@pytest.mark.parametrize("scheme_id", ["%00", "a" * 100])
def test_malformed_scheme_id_does_not_leak_traceback(client: Any, scheme_id: str) -> None:
    response = client.get(f"{SCHEMES_PATH}/{scheme_id}")

    assert response.status_code in (404, 422)
    assert "Traceback" not in response.text


def test_oversized_body_is_refused_without_traceback(client: Any) -> None:
    oversized = {"answers": {"note": "x" * OVERSIZED_NOTE_LENGTH}}

    response = client.post(EVALUATE_PATH, json=oversized)

    assert response.status_code in (413, 422)
    assert "Traceback" not in response.text


def test_admin_token_never_appears_in_public_responses(
    client: Any, db: Session, scheme_factory: Callable[..., Any]
) -> None:
    scheme_factory(db, "PRIV-PUBLIC")

    listing = client.get(SCHEMES_PATH)
    evaluation = client.post(EVALUATE_PATH, json={"answers": FULL_PROFILE})

    assert ADMIN_TOKEN not in listing.text
    assert ADMIN_TOKEN not in evaluation.text


@pytest.mark.parametrize("route", ["schemes", "eligibility"])
def test_token_headers_are_not_echoed_back(client: Any, route: str) -> None:
    if route == "schemes":
        response = client.get(
            SCHEMES_PATH,
            headers={"X-Admin-Token": ADMIN_TOKEN, "X-Tracking-Token": "tracking-test-value"},
        )
    else:
        response = client.post(
            EVALUATE_PATH,
            json={"answers": FULL_PROFILE},
            headers={"X-Admin-Token": ADMIN_TOKEN, "X-Tracking-Token": "tracking-test-value"},
        )

    response_header_names = {name.lower() for name in response.headers.keys()}
    assert "x-admin-token" not in response_header_names
    assert "x-tracking-token" not in response_header_names
