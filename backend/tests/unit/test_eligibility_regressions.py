"""Regression tests for exists-operator status, decision ordering, and OR combination."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.orm import Session

from claim_whats_yours.domain.decisions import Decision, decide
from claim_whats_yours.domain.rules import (
    MAX_RULE_DEPTH,
    MAX_RULE_LEAVES,
    Tri,
    check_rule,
    evaluate_rule,
)
from claim_whats_yours.services.eligibility_service import evaluate_profile


def _leaf(
    field: str,
    operator: str,
    value: Any = None,
    criterion_id: str = "c1",
    mandatory: bool = True,
) -> dict[str, Any]:
    node: dict[str, Any] = {
        "criterion_id": criterion_id,
        "field": field,
        "operator": operator,
        "mandatory": mandatory,
        "explanation": f"{field} {operator}",
        "source_refs": ["s1"],
    }
    if operator != "exists":
        node["value"] = value
    return node


# ---------------------------------------------------------------- exists operator


def test_exists_with_key_absent_is_unknown() -> None:
    result = evaluate_rule(_leaf("aadhaar_linked", "exists"), {})
    assert result.status is Tri.UNKNOWN


def test_exists_with_value_none_is_unknown() -> None:
    result = evaluate_rule(_leaf("income", "exists"), {"income": None})
    assert result.status is Tri.UNKNOWN


def test_exists_with_prefer_not_to_say_is_unknown() -> None:
    result = evaluate_rule(_leaf("income", "exists"), {"income": "prefer_not_to_say"})
    assert result.status is Tri.UNKNOWN


def test_exists_with_valid_present_value_is_pass() -> None:
    result = evaluate_rule(_leaf("income", "exists"), {"income": 120000})
    assert result.status is Tri.PASS


# ---------------------------------------------------------------- decision ordering


def test_geo_unknown_with_mandatory_fail_needs_more_information() -> None:
    # geo UNKNOWN is checked before mandatory FAIL, so the result is not NOT_LIKELY_ELIGIBLE.
    assert decide(Tri.UNKNOWN, [Tri.FAIL], True, False) == Decision.NEEDS_MORE_INFORMATION


def test_mandatory_fail_with_known_geo_is_not_likely_eligible() -> None:
    assert decide(Tri.PASS, [Tri.FAIL], True, False) == Decision.NOT_LIKELY_ELIGIBLE


def test_verification_false_returns_verification_required() -> None:
    assert decide(Tri.PASS, [Tri.PASS], False, False) == Decision.VERIFICATION_REQUIRED


def test_verification_false_takes_precedence_over_mandatory_fail() -> None:
    assert decide(Tri.PASS, [Tri.FAIL], False, False) == Decision.VERIFICATION_REQUIRED


# ---------------------------------------------------------------- OR combination


def test_any_group_passes_when_one_branch_passes_and_other_fails() -> None:
    rule = {
        "any": [
            _leaf("age", "gte", 18, criterion_id="age"),
            _leaf("student", "eq", True, criterion_id="student"),
        ]
    }
    result = evaluate_rule(rule, {"age": 25, "student": False})
    assert result.status is Tri.PASS


def test_any_group_fails_when_all_branches_fail() -> None:
    rule = {
        "any": [
            _leaf("age", "gte", 18, criterion_id="age"),
            _leaf("student", "eq", True, criterion_id="student"),
        ]
    }
    result = evaluate_rule(rule, {"age": 10, "student": False})
    assert result.status is Tri.FAIL


# ---------------------------------------------------------------- scheme-level decision tree

# Catalogue field ids from backend/data/profile_fields.json.
_AGE = "age_years"
_STUDENT = "is_student"
_INCOME = "annual_household_income_inr"


def _decide_scheme(
    db: Session,
    scheme_factory: Callable[..., Any],
    rule: dict[str, Any],
    answers: dict[str, Any],
) -> dict[str, Any]:
    """Build one published, verified, in-scope scheme with the rule and return its result."""
    scheme = scheme_factory(db, "s-tree", scope="state", state_codes=("IN-AP",))
    scheme.eligibility_rule = rule
    db.commit()
    evaluated = evaluate_profile(db, answers, datetime.now(UTC), None)
    (scheme_result,) = evaluated["results"]
    return dict(scheme_result)


def test_any_with_one_mandatory_branch_passing_is_likely_eligible(
    db: Session, scheme_factory: Callable[..., Any]
) -> None:
    rule = {
        "any": [
            _leaf(_AGE, "gte", 18, criterion_id="age"),
            _leaf(_STUDENT, "eq", True, criterion_id="student"),
        ]
    }
    answers = {"state_code": "IN-AP", _AGE: 25, _STUDENT: False}
    result = _decide_scheme(db, scheme_factory, rule, answers)
    assert result["decision"] == "LIKELY_ELIGIBLE"


def test_not_over_passing_mandatory_leaf_is_likely_eligible(
    db: Session, scheme_factory: Callable[..., Any]
) -> None:
    rule = {
        "all": [
            _leaf("state_code", "eq", "IN-AP", criterion_id="state"),
            {"not": _leaf(_INCOME, "gte", 500000, criterion_id="income")},
        ]
    }
    answers = {"state_code": "IN-AP", _INCOME: 150000}
    result = _decide_scheme(db, scheme_factory, rule, answers)
    assert result["decision"] == "LIKELY_ELIGIBLE"


def test_not_over_failing_mandatory_leaf_is_not_likely_eligible(
    db: Session, scheme_factory: Callable[..., Any]
) -> None:
    rule = {
        "all": [
            _leaf("state_code", "eq", "IN-AP", criterion_id="state"),
            {"not": _leaf(_INCOME, "gte", 500000, criterion_id="income")},
        ]
    }
    answers = {"state_code": "IN-AP", _INCOME: 600000}
    result = _decide_scheme(db, scheme_factory, rule, answers)
    assert result["decision"] == "NOT_LIKELY_ELIGIBLE"


def test_advisory_failing_leaf_does_not_change_decision_but_is_reported(
    db: Session, scheme_factory: Callable[..., Any]
) -> None:
    rule = {
        "all": [
            _leaf(_AGE, "gte", 18, criterion_id="age"),
            _leaf(_INCOME, "gte", 500000, criterion_id="income", mandatory=False),
        ]
    }
    answers = {"state_code": "IN-AP", _AGE: 25, _INCOME: 100}
    result = _decide_scheme(db, scheme_factory, rule, answers)
    assert result["decision"] == "LIKELY_ELIGIBLE"
    statuses = {c["criterion_id"]: c["status"] for c in result["criteria"]}
    assert statuses["income"] == "FAIL"


def test_any_with_all_mandatory_branches_failing_is_not_likely_eligible(
    db: Session, scheme_factory: Callable[..., Any]
) -> None:
    rule = {
        "any": [
            _leaf(_AGE, "gte", 65, criterion_id="age"),
            _leaf(_STUDENT, "eq", True, criterion_id="student"),
        ]
    }
    answers = {"state_code": "IN-AP", _AGE: 25, _STUDENT: False}
    result = _decide_scheme(db, scheme_factory, rule, answers)
    assert result["decision"] == "NOT_LIKELY_ELIGIBLE"


# ---------------------------------------------------------------- effective dates and verification

_TODAY = date(2025, 6, 1)
_NOW = datetime(2025, 6, 1, 12, tzinfo=UTC)
_FUTURE = datetime(2030, 1, 1, tzinfo=UTC)
_PAST = datetime(2024, 1, 1, tzinfo=UTC)
_OLD = datetime(2020, 1, 1, tzinfo=UTC)
_AGE_RULE: dict[str, Any] = {"all": [_leaf(_AGE, "gte", 18, criterion_id="age")]}


def _evaluate_on_today(
    db: Session,
    scheme_factory: Callable[..., Any],
    answers: dict[str, Any],
    rule: dict[str, Any] = _AGE_RULE,
    **fields: Any,
) -> list[dict[str, Any]]:
    """Build one published all-India scheme, set the given fields, and evaluate on _TODAY."""
    scheme = scheme_factory(db, "s-dated", review_due_at=_FUTURE)
    scheme.eligibility_rule = rule
    for name, value in fields.items():
        setattr(scheme, name, value)
    db.commit()
    evaluated = evaluate_profile(db, answers, _NOW, None, today=_TODAY)
    return [dict(item) for item in evaluated["results"]]


def test_effective_to_in_past_excludes_scheme(
    db: Session, scheme_factory: Callable[..., Any]
) -> None:
    answers = {"state_code": "IN-AP", _AGE: 25}
    results = _evaluate_on_today(db, scheme_factory, answers, effective_to=date(2025, 5, 31))
    assert results == []


def test_effective_from_in_future_excludes_scheme(
    db: Session, scheme_factory: Callable[..., Any]
) -> None:
    answers = {"state_code": "IN-AP", _AGE: 25}
    results = _evaluate_on_today(db, scheme_factory, answers, effective_from=date(2025, 7, 1))
    assert results == []


def test_today_inside_effective_period_is_evaluated(
    db: Session, scheme_factory: Callable[..., Any]
) -> None:
    answers = {"state_code": "IN-AP", _AGE: 25}
    results = _evaluate_on_today(
        db,
        scheme_factory,
        answers,
        effective_from=date(2025, 1, 1),
        effective_to=date(2025, 12, 31),
    )
    assert len(results) == 1
    assert results[0]["decision"] == "LIKELY_ELIGIBLE"
    assert results[0]["verification_current"] is True


def test_old_last_verified_with_future_review_due_is_evaluated(
    db: Session, scheme_factory: Callable[..., Any]
) -> None:
    answers = {"state_code": "IN-AP", _AGE: 25}
    results = _evaluate_on_today(
        db, scheme_factory, answers, last_verified_at=_OLD, review_due_at=_FUTURE
    )
    assert len(results) == 1
    assert results[0]["decision"] == "LIKELY_ELIGIBLE"
    assert results[0]["verification_current"] is True
    assert str(results[0]["last_verified_at"]).startswith("2020-01-01")


def test_review_due_in_past_requires_verification_even_when_criteria_pass(
    db: Session, scheme_factory: Callable[..., Any]
) -> None:
    answers = {"state_code": "IN-AP", _AGE: 25}
    results = _evaluate_on_today(db, scheme_factory, answers, review_due_at=_PAST)
    assert len(results) == 1
    assert results[0]["decision"] == "VERIFICATION_REQUIRED"
    assert results[0]["verification_current"] is False


def test_missing_last_verified_at_requires_verification(
    db: Session, scheme_factory: Callable[..., Any]
) -> None:
    answers = {"state_code": "IN-AP", _AGE: 25}
    results = _evaluate_on_today(db, scheme_factory, answers, last_verified_at=None)
    assert len(results) == 1
    assert results[0]["decision"] == "VERIFICATION_REQUIRED"
    assert results[0]["verification_current"] is False
    assert results[0]["last_verified_at"] is None


def test_criterion_fail_with_current_review_is_not_likely_eligible(
    db: Session, scheme_factory: Callable[..., Any]
) -> None:
    answers = {"state_code": "IN-AP", _AGE: 10}
    results = _evaluate_on_today(db, scheme_factory, answers)
    assert len(results) == 1
    assert results[0]["decision"] == "NOT_LIKELY_ELIGIBLE"
    assert results[0]["verification_current"] is True


# ---------------------------------------------------------------- rule validation limits


def _nested(leaf: dict[str, Any], groups: int) -> dict[str, Any]:
    """Wrap a leaf in `groups` all-groups. The leaf then sits at depth groups + 1."""
    node = leaf
    for _ in range(groups):
        node = {"all": [node]}
    return node


def _codes(rule: dict[str, Any]) -> set[str]:
    return {error.code for error in check_rule(rule)}


def test_string_operand_for_numeric_field_is_rejected_and_evaluation_does_not_raise(
    db: Session, scheme_factory: Callable[..., Any]
) -> None:
    rule = {"all": [_leaf(_AGE, "gte", "18", criterion_id="age")]}
    errors = check_rule(rule)
    assert [error.code for error in errors] == ["invalid_operand_type"]
    assert errors[0].path == "$.all[0].value"
    scheme = scheme_factory(db, "s-string-operand", review_due_at=_FUTURE)
    scheme.eligibility_rule = rule
    db.commit()
    evaluated = evaluate_profile(db, {"state_code": "IN-AP", _AGE: 25}, _NOW, None, today=_TODAY)
    assert evaluated["results"] == []
    (excluded,) = evaluated["excluded_schemes"]
    assert excluded["reason"] == "rule_invalid"


def test_boolean_operand_for_numeric_field_is_rejected() -> None:
    assert _codes({"all": [_leaf(_AGE, "gte", True)]}) == {"invalid_operand_type"}


def test_rule_one_level_deeper_than_max_is_rejected() -> None:
    assert _codes(_nested(_leaf(_AGE, "gte", 18), MAX_RULE_DEPTH)) == {"rule_too_deep"}


def test_more_than_max_leaves_is_rejected() -> None:
    leaves = [_leaf(_AGE, "gte", 18, criterion_id=f"c{i}") for i in range(MAX_RULE_LEAVES + 1)]
    assert _codes({"all": leaves}) == {"too_many_leaves"}


def test_unknown_field_id_is_rejected() -> None:
    assert _codes({"all": [_leaf("no_such_field", "eq", "x")]}) == {"unknown_field"}


def test_rule_at_exactly_max_depth_is_valid() -> None:
    assert check_rule(_nested(_leaf(_AGE, "gte", 18), MAX_RULE_DEPTH - 1)) == []


def test_stored_invalid_rule_is_excluded_as_rule_invalid_not_likely_eligible(
    db: Session, scheme_factory: Callable[..., Any]
) -> None:
    scheme = scheme_factory(db, "s-stored-invalid", review_due_at=_FUTURE)
    scheme.eligibility_rule = {"all": [_leaf("no_such_field", "gte", 18, criterion_id="age")]}
    db.commit()
    evaluated = evaluate_profile(db, {"state_code": "IN-AP", _AGE: 25}, _NOW, None, today=_TODAY)
    assert evaluated["results"] == []
    (excluded,) = evaluated["excluded_schemes"]
    assert excluded["reason"] == "rule_invalid"
    assert {error["code"] for error in excluded["errors"]} == {"unknown_field"}
