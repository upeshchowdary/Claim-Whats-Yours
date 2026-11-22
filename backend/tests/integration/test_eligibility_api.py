"""Integration tests for POST /api/v1/eligibility/evaluate. All scheme data is synthetic."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

EVALUATE_PATH = "/api/v1/eligibility/evaluate"


def _future_review() -> datetime:
    return datetime.now(UTC) + timedelta(days=30)


def _evaluate(client: Any, body: dict[str, Any], headers: dict[str, str] | None = None) -> Any:
    return client.post(EVALUATE_PATH, json=body, headers=headers or {})


def _result_for(body: dict[str, Any], scheme_id: str) -> dict[str, Any]:
    matches = [item for item in body["results"] if item["scheme_id"] == scheme_id]
    assert len(matches) == 1
    return matches[0]


def _count(db: Session, sql: str) -> int:
    return int(db.execute(text(sql)).scalar_one())


def test_evaluate_returns_envelope_and_likely_eligible(
    client: Any, db: Session, scheme_factory: Callable[..., Any]
) -> None:
    scheme_factory(db, "ELIG-ENVELOPE", review_due_at=_future_review())

    response = _evaluate(client, {"answers": {"age_years": 25}})

    assert response.status_code == 200
    body = response.json()
    assert {"request_id", "evaluation_date", "results", "disclaimer"} <= body.keys()
    assert _result_for(body, "ELIG-ENVELOPE")["decision"] == "LIKELY_ELIGIBLE"


@pytest.mark.parametrize(
    ("age_years", "expected_decision"),
    [(18, "LIKELY_ELIGIBLE"), (17, "NOT_LIKELY_ELIGIBLE")],
)
def test_age_boundary_drives_decision(
    client: Any,
    db: Session,
    scheme_factory: Callable[..., Any],
    age_years: int,
    expected_decision: str,
) -> None:
    scheme_factory(db, "ELIG-AGE", review_due_at=_future_review(), rule_age_min=18)

    response = _evaluate(client, {"answers": {"age_years": age_years}})

    assert response.status_code == 200
    assert _result_for(response.json(), "ELIG-AGE")["decision"] == expected_decision


def test_empty_answers_need_more_information(
    client: Any, db: Session, scheme_factory: Callable[..., Any]
) -> None:
    scheme_factory(db, "ELIG-EMPTY", review_due_at=_future_review())

    response = _evaluate(client, {"answers": {}})

    assert response.status_code == 200
    body = response.json()
    assert _result_for(body, "ELIG-EMPTY")["decision"] == "NEEDS_MORE_INFORMATION"
    assert "age_years" in body["missing_fields"]


def test_unverified_scheme_requires_verification(
    client: Any, db: Session, scheme_factory: Callable[..., Any]
) -> None:
    scheme_factory(
        db,
        "ELIG-UNVERIFIED",
        verification_status="needs_review",
        review_due_at=_future_review(),
    )

    response = _evaluate(client, {"answers": {"age_years": 25}})

    assert response.status_code == 200
    assert _result_for(response.json(), "ELIG-UNVERIFIED")["decision"] == "VERIFICATION_REQUIRED"


@pytest.mark.parametrize(
    ("state_code", "included"),
    [("IN-KA", False), ("IN-AP", True)],
)
def test_state_scheme_included_only_for_its_state(
    client: Any,
    db: Session,
    scheme_factory: Callable[..., Any],
    state_code: str,
    included: bool,
) -> None:
    scheme_factory(
        db,
        "ELIG-STATE-AP",
        scope="state",
        state_codes=("IN-AP",),
        government_level="state",
        review_due_at=_future_review(),
    )

    response = _evaluate(client, {"answers": {"age_years": 25, "state_code": state_code}})

    assert response.status_code == 200
    scheme_ids = [item["scheme_id"] for item in response.json()["results"]]
    assert ("ELIG-STATE-AP" in scheme_ids) is included


@pytest.mark.parametrize(
    ("categories", "included"),
    [(["farm"], False), (["education"], True)],
)
def test_category_filter_narrows_results(
    client: Any,
    db: Session,
    scheme_factory: Callable[..., Any],
    categories: list[str],
    included: bool,
) -> None:
    scheme_factory(
        db,
        "ELIG-CATEGORY",
        categories=("education",),
        review_due_at=_future_review(),
    )

    response = _evaluate(
        client,
        {"answers": {"age_years": 25}, "filters": {"categories": categories}},
    )

    assert response.status_code == 200
    scheme_ids = [item["scheme_id"] for item in response.json()["results"]]
    assert ("ELIG-CATEGORY" in scheme_ids) is included


def test_invalid_answer_type_returns_422_without_echoing_value(
    client: Any, db: Session, scheme_factory: Callable[..., Any]
) -> None:
    scheme_factory(db, "ELIG-TYPE", review_due_at=_future_review())

    response = _evaluate(client, {"answers": {"age_years": "x"}})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert isinstance(body["error"]["details"], list)
    assert body["error"]["details"]
    assert '"x"' not in response.text


def test_forbidden_field_returns_422_without_echoing_value(
    client: Any, db: Session, scheme_factory: Callable[..., Any]
) -> None:
    scheme_factory(db, "ELIG-FORBIDDEN", review_due_at=_future_review())

    response = _evaluate(client, {"answers": {"aadhaar": "SECRETVALUE-QZX"}})

    assert response.status_code == 422
    assert "SECRETVALUE-QZX" not in response.text


def test_unknown_top_level_key_returns_422(client: Any) -> None:
    response = _evaluate(client, {"answers": {}, "unexpected": True})

    assert response.status_code == 422


def test_request_id_header_is_echoed(client: Any) -> None:
    response = _evaluate(client, {"answers": {}}, headers={"X-Request-ID": "abc123"})

    assert response.headers["X-Request-ID"] == "abc123"


def test_evaluation_persists_nothing(
    client: Any, db: Session, scheme_factory: Callable[..., Any]
) -> None:
    scheme_factory(db, "ELIG-STATELESS", review_due_at=_future_review())
    schemes_before = _count(db, "SELECT COUNT(*) FROM schemes")
    tracking_before = _count(db, "SELECT COUNT(*) FROM tracking_records")

    response = _evaluate(client, {"answers": {"age_years": 25}})

    assert response.status_code == 200
    assert _count(db, "SELECT COUNT(*) FROM schemes") == schemes_before
    assert _count(db, "SELECT COUNT(*) FROM tracking_records") == tracking_before
