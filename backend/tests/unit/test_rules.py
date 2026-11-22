"""Unit tests for the tri-state rules evaluator in claim_whats_yours.domain.rules."""

from __future__ import annotations

from typing import Any

import pytest

from claim_whats_yours.domain.rules import Tri, evaluate_rule, validate_rule


def _leaf(
    field: str = "age_years",
    operator: str = "gte",
    value: Any = 18,
    criterion_id: str = "c1",
) -> dict[str, Any]:
    return {
        "criterion_id": criterion_id,
        "field": field,
        "operator": operator,
        "value": value,
        "mandatory": True,
        "explanation": f"{field} {operator} {value}",
        "source_refs": ["s1"],
    }


# Fixed leaves whose outcome is controlled by the profile passed in.
PASS_LEAF = _leaf(field="flag", operator="eq", value=1, criterion_id="pass")
FAIL_LEAF = _leaf(field="flag", operator="eq", value=2, criterion_id="fail")
UNKNOWN_LEAF = _leaf(field="missing", operator="eq", value=1, criterion_id="unk")
PROFILE_ALL = {"flag": 1}  # PASS_LEAF -> PASS, FAIL_LEAF -> FAIL, UNKNOWN_LEAF -> UNKNOWN


# ---------------------------------------------------------------- leaf boundaries


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (18, Tri.PASS),
        (17, Tri.FAIL),
        (19, Tri.PASS),
    ],
)
def test_min_age_boundary(age: int, expected: Tri) -> None:
    leaf = _leaf(field="age_years", operator="gte", value=18)
    result = evaluate_rule(leaf, {"age_years": age})
    assert result.status is expected
    assert result.criterion_id == "c1"
    assert result.mandatory is True
    assert result.source_refs == ("s1",)


@pytest.mark.parametrize(
    ("income", "expected"),
    [
        (300000, Tri.PASS),
        (300001, Tri.FAIL),
    ],
)
def test_income_ceiling_boundary(income: int, expected: Tri) -> None:
    leaf = _leaf(field="annual_household_income_inr", operator="lte", value=300000)
    result = evaluate_rule(leaf, {"annual_household_income_inr": income})
    assert result.status is expected


@pytest.mark.parametrize(
    "profile",
    [
        {},
        {"age_years": None},
        {"age_years": "prefer_not_to_say"},
    ],
)
def test_missing_or_declined_field_is_unknown(profile: dict[str, Any]) -> None:
    leaf = _leaf(field="age_years", operator="gte", value=18)
    assert evaluate_rule(leaf, profile).status is Tri.UNKNOWN


def test_prefer_not_to_say_is_unknown_for_equality_leaf() -> None:
    leaf = _leaf(field="state", operator="eq", value="KA")
    assert evaluate_rule(leaf, {"state": "prefer_not_to_say"}).status is Tri.UNKNOWN


# ---------------------------------------------------------------- group truth tables


def _node_for(status: str) -> dict[str, Any]:
    return {"PASS": PASS_LEAF, "FAIL": FAIL_LEAF, "UNKNOWN": UNKNOWN_LEAF}[status]


@pytest.mark.parametrize(
    ("children", "expected"),
    [
        (["PASS", "PASS"], Tri.PASS),
        (["PASS", "FAIL"], Tri.FAIL),
        (["FAIL", "UNKNOWN"], Tri.FAIL),
        (["PASS", "UNKNOWN"], Tri.UNKNOWN),
        (["UNKNOWN", "UNKNOWN"], Tri.UNKNOWN),
    ],
)
def test_all_truth_table(children: list[str], expected: Tri) -> None:
    node = {"all": [_node_for(c) for c in children]}
    assert evaluate_rule(node, PROFILE_ALL).status is expected


@pytest.mark.parametrize(
    ("children", "expected"),
    [
        (["PASS", "FAIL"], Tri.PASS),
        (["UNKNOWN", "PASS"], Tri.PASS),
        (["FAIL", "FAIL"], Tri.FAIL),
        (["FAIL", "UNKNOWN"], Tri.UNKNOWN),
        (["UNKNOWN", "UNKNOWN"], Tri.UNKNOWN),
    ],
)
def test_any_truth_table(children: list[str], expected: Tri) -> None:
    node = {"any": [_node_for(c) for c in children]}
    assert evaluate_rule(node, PROFILE_ALL).status is expected


@pytest.mark.parametrize(
    ("child", "expected"),
    [
        ("PASS", Tri.FAIL),
        ("FAIL", Tri.PASS),
        ("UNKNOWN", Tri.UNKNOWN),
    ],
)
def test_not_truth_table(child: str, expected: Tri) -> None:
    node = {"not": _node_for(child)}
    assert evaluate_rule(node, PROFILE_ALL).status is expected


# ---------------------------------------------------------------- validate_rule


@pytest.mark.parametrize(
    "node",
    [
        _leaf(operator="between"),
        {k: v for k, v in _leaf().items() if k != "criterion_id"},
        {"xor": [PASS_LEAF]},
        {"all": []},
    ],
    ids=["invalid_operator", "missing_criterion_id", "unknown_group_key", "empty_all_list"],
)
def test_validate_rule_reports_errors_without_raising(node: dict[str, Any]) -> None:
    errors = validate_rule(node)
    assert isinstance(errors, list)
    assert errors, "expected at least one validation error"
    assert all(isinstance(e, str) and e for e in errors)


def test_validate_rule_accepts_valid_leaf() -> None:
    assert validate_rule(_leaf()) == []


# ---------------------------------------------------------------- explanation validation (regress)


def test_empty_explanation_is_rejected() -> None:
    """Regression: explanation must be a non-empty string, not merely a str instance."""
    node = {**_leaf(), "explanation": ""}
    errors = validate_rule(node)
    assert any("explanation" in e for e in errors), (
        "expected a validation error for empty explanation"
    )


def test_whitespace_only_explanation_is_rejected() -> None:
    """Regression: whitespace-only strings are not meaningful explanations."""
    node = {**_leaf(), "explanation": "   "}
    errors = validate_rule(node)
    assert any("explanation" in e for e in errors)


def test_missing_explanation_is_rejected() -> None:
    node = {k: v for k, v in _leaf().items() if k != "explanation"}
    errors = validate_rule(node)
    assert any("explanation" in e for e in errors)
