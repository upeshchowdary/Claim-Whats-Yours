"""Unit tests for profile field validation (domain/fields.py)."""

from typing import Any

import pytest

from claim_whats_yours.domain.fields import validate_answers


def _codes(answers: dict[str, Any]) -> list[str]:
    return [error["code"] for error in validate_answers(answers)]


@pytest.mark.parametrize(
    "key",
    ["aadhaar", "pan", "bank_account", "password", "phone", "email"],
)
def test_forbidden_field_is_rejected(key: str) -> None:
    assert _codes({key: "x"}) == ["FORBIDDEN_FIELD"]


def test_unknown_field_is_rejected() -> None:
    assert _codes({"favourite_colour": "blue"}) == ["UNKNOWN_FIELD"]


@pytest.mark.parametrize("value", ["12", True])
def test_age_years_wrong_type_is_rejected(value: Any) -> None:
    assert _codes({"age_years": value}) == ["INVALID_TYPE"]


@pytest.mark.parametrize("value", [-1, 121])
def test_age_years_out_of_range_is_rejected(value: int) -> None:
    assert _codes({"age_years": value}) == ["OUT_OF_RANGE"]


def test_valid_answer_set_has_no_errors() -> None:
    answers = {"age_years": 25, "state_code": "IN-AP", "is_farmer": True}
    assert validate_answers(answers) == []


def test_none_value_is_accepted() -> None:
    assert validate_answers({"age_years": None}) == []


def test_prefer_not_to_say_gender_is_accepted() -> None:
    assert validate_answers({"gender": "prefer_not_to_say"}) == []


def test_unknown_gender_value_is_not_allowed() -> None:
    assert _codes({"gender": "other_thing"}) == ["NOT_ALLOWED_VALUE"]
