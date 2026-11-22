# SYNTHETIC TEST SCENARIOS ONLY.
# These profiles are invented fixtures for exercising validation and rule evaluation.
# They are not eligibility claims, not real people, and not guidance for any scheme.

from __future__ import annotations

from typing import Any

import pytest

from claim_whats_yours.domain.fields import validate_answers
from claim_whats_yours.domain.rules import Tri, evaluate_rule

MIN_AGE_LEAF: dict[str, Any] = {
    "criterion_id": "min_age",
    "field": "age_years",
    "operator": "gte",
    "value": 18,
    "mandatory": True,
    "explanation": "Age at least 18",
    "source_refs": ["s1"],
}

PROFILES: list[tuple[str, dict[str, Any]]] = [
    ("student", {"is_student": True, "occupation": "student", "education_level": "secondary"}),
    ("farmer", {"occupation": "farmer", "is_farmer": True, "landholding_acres": 2.5}),
    ("senior_citizen", {"age_years": 68, "marital_status": "widowed"}),
    ("unemployed", {"occupation": "unemployed"}),
    ("salaried", {"occupation": "salaried", "residence": "urban"}),
    ("self_employed", {"occupation": "self_employed"}),
    (
        "women_led_household",
        {"gender": "female", "family_size": 4},
    ),
    ("person_with_disability", {"disability_status": True}),
    ("rural_household", {"residence": "rural", "state_code": "IN-UP"}),
    (
        "urban_low_income_household",
        {"residence": "urban", "annual_household_income_inr": 150000},
    ),
    ("unorganised_worker", {"is_unorganised_worker": True, "occupation": "daily_wage"}),
    ("large_family", {"family_size": 12}),
    (
        "declined_optional_questions",
        {"gender": "prefer_not_to_say", "annual_household_income_inr": None},
    ),
    ("incomplete_age_only", {"age_years": 30}),
    ("no_age_field", {"residence": "rural"}),
]

PROFILE_PARAMS = [pytest.param(answers, id=label) for label, answers in PROFILES]


@pytest.mark.parametrize("answers", PROFILE_PARAMS)
def test_profile_passes_validation(answers: dict[str, Any]) -> None:
    assert validate_answers(answers) == []


@pytest.mark.parametrize("answers", PROFILE_PARAMS)
def test_min_age_leaf_is_pass_or_unknown_never_fail(answers: dict[str, Any]) -> None:
    result = evaluate_rule(MIN_AGE_LEAF, answers)
    assert result.status in (Tri.PASS, Tri.UNKNOWN)
    assert result.status is not Tri.FAIL


@pytest.mark.parametrize("answers", PROFILE_PARAMS)
def test_min_age_leaf_status_follows_age_presence(answers: dict[str, Any]) -> None:
    expected = Tri.PASS if "age_years" in answers else Tri.UNKNOWN
    assert evaluate_rule(MIN_AGE_LEAF, answers).status is expected


def test_profile_without_age_is_unknown_not_fail() -> None:
    answers: dict[str, Any] = {"gender": "female", "family_size": 4}
    result = evaluate_rule(MIN_AGE_LEAF, answers)
    assert result.status is Tri.UNKNOWN
    assert result.criterion_id == "min_age"
