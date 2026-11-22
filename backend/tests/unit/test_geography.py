"""Unit tests for jurisdiction lookup and geographic applicability."""

import json
from pathlib import Path

import pytest

from claim_whats_yours.domain.geography import (
    applicable,
    district_parent_state,
    geographic_status,
    is_valid_district_code,
    is_valid_jurisdiction_code,
    known_district_codes,
    known_state_codes,
    validate_state_district_pair,
)
from claim_whats_yours.domain.rules import Tri

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "jurisdictions.json"


# ---------------------------------------------------------------- state/UT scope tests


@pytest.mark.parametrize(
    ("scope", "state_codes", "profile_state", "expected"),
    [
        ("all_india", [], None, Tri.PASS),
        ("all_india", [], "IN-AP", Tri.PASS),
        ("state", ["IN-AP"], None, Tri.UNKNOWN),
        ("state", ["IN-AP"], "IN-KA", Tri.FAIL),
        ("state", ["IN-AP"], "IN-AP", Tri.PASS),
        ("ut", ["IN-DL"], "IN-DL", Tri.PASS),
        ("ut", ["IN-DL"], "IN-AP", Tri.FAIL),
    ],
)
def test_state_scope_geographic_status(
    scope: str,
    state_codes: list[str],
    profile_state: str | None,
    expected: Tri,
) -> None:
    result = geographic_status(scope, state_codes, [], profile_state, None)
    assert result is expected


# ---------------------------------------------------------------- district scope tests


@pytest.mark.parametrize(
    ("scheme_districts", "profile_state", "profile_district", "expected"),
    [
        # No district in profile → UNKNOWN (can't determine yet)
        (["IN-AP-VSP"], "IN-AP", None, Tri.UNKNOWN),
        # District missing, state also missing → UNKNOWN
        (["IN-AP-VSP"], None, None, Tri.UNKNOWN),
        # Correct district, correct state, district in list → PASS
        (["IN-AP-VSP"], "IN-AP", "IN-AP-VSP", Tri.PASS),
        # Different district in same state, not in scheme list → FAIL
        (["IN-AP-VSP"], "IN-AP", "IN-AP-GNT", Tri.FAIL),
        # Correct district in list, but state is wrong state → FAIL (cross-validation)
        (["IN-AP-VSP"], "IN-KA", "IN-AP-VSP", Tri.FAIL),
        # District provided, state not provided, district in catalogue
        # → UNKNOWN (can't confirm parent)
        (["IN-AP-VSP"], None, "IN-AP-VSP", Tri.UNKNOWN),
        # Unknown district code (not in catalogue) → FAIL
        (["IN-AP-XXX"], "IN-AP", "IN-AP-XXX", Tri.FAIL),
        # Unknown district code regardless of state → FAIL
        ([], "IN-AP", "IN-XX-999", Tri.FAIL),
        # District from different state than profile state → FAIL even if in scheme list
        (["IN-AP-VSP"], "IN-TG", "IN-AP-VSP", Tri.FAIL),
    ],
)
def test_district_scope_geographic_status(
    scheme_districts: list[str],
    profile_state: str | None,
    profile_district: str | None,
    expected: Tri,
) -> None:
    result = geographic_status("district", [], scheme_districts, profile_state, profile_district)
    assert result is expected


def test_unknown_scope_raises_value_error() -> None:
    with pytest.raises(ValueError):
        geographic_status("galaxy", [], [], None, None)


# ---------------------------------------------------------------- jurisdiction registry tests


def test_registry_has_correct_total_entries() -> None:
    records = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    # 1 all-India + 28 states + 8 UTs + 13 AP districts = 50
    assert len(records) == 50


def test_registry_level_counts() -> None:
    records = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for r in records:
        counts[r["level"]] = counts.get(r["level"], 0) + 1
    assert counts["all_india"] == 1
    assert counts["state"] == 28
    assert counts["ut"] == 8
    assert counts["district"] == 13  # 13 official AP districts


def test_known_state_codes_has_36_entries() -> None:
    assert len(known_state_codes()) == 36


def test_known_district_codes_contains_ap_districts() -> None:
    districts = known_district_codes()
    ap_districts = {d for d in districts if d.startswith("IN-AP-")}
    assert len(ap_districts) >= 13, f"Expected at least 13 AP districts, got {len(ap_districts)}"


def test_every_state_ut_code_is_valid() -> None:
    records = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    for record in records:
        if record["level"] in ("all_india", "state", "ut"):
            assert is_valid_jurisdiction_code(record["code"]), record["code"]


def test_every_district_code_is_valid() -> None:
    records = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    for record in records:
        if record["level"] == "district":
            assert is_valid_jurisdiction_code(record["code"]), record["code"]
            assert is_valid_district_code(record["code"]), record["code"]


def test_unknown_jurisdiction_code_is_invalid() -> None:
    assert is_valid_jurisdiction_code("IN-XX") is False


def test_known_state_code_is_valid() -> None:
    assert is_valid_jurisdiction_code("IN-AP") is True


def test_state_code_is_not_a_district() -> None:
    assert is_valid_district_code("IN-AP") is False


# ---------------------------------------------------------------- district parent / cross-valid


@pytest.mark.parametrize(
    ("district", "expected_parent"),
    [
        ("IN-AP-VSP", "IN-AP"),
        ("IN-AP-GNT", "IN-AP"),
        ("IN-AP-VJA", "IN-AP"),
        ("IN-AP-ANT", "IN-AP"),
        ("IN-AP-KNL", "IN-AP"),
    ],
)
def test_district_parent_state(district: str, expected_parent: str) -> None:
    assert district_parent_state(district) == expected_parent


def test_unknown_district_has_no_parent() -> None:
    assert district_parent_state("IN-XX-999") is None


@pytest.mark.parametrize(
    ("state", "district", "expected"),
    [
        ("IN-AP", "IN-AP-VSP", True),  # correct pair
        ("IN-AP", "IN-AP-GNT", True),  # correct pair
        ("IN-KA", "IN-AP-VSP", False),  # wrong state for this district
        ("IN-AP", "IN-KA-999", False),  # unknown district
        ("IN-AP", "IN-AP-XXX", False),  # unknown district code
    ],
)
def test_validate_state_district_pair(state: str, district: str, expected: bool) -> None:
    assert validate_state_district_pair(state, district) is expected


# ---------------------------------------------------------------- applicable


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (Tri.FAIL, False),
        (Tri.PASS, True),
        (Tri.UNKNOWN, True),
    ],
)
def test_applicable(status: Tri, expected: bool) -> None:
    assert applicable(status) is expected


# ---------------------------------------------------------------- regression tests


def test_district_from_different_state_is_rejected() -> None:
    """Regression: a district belonging to AP must not PASS for a KA-state profile."""
    result = geographic_status(
        "district",
        [],
        ["IN-AP-VSP"],  # scheme is for Visakhapatnam
        "IN-KA",  # profile says Karnataka
        "IN-AP-VSP",  # district is actually in AP — mismatch
    )
    assert result is Tri.FAIL


def test_unregistered_district_code_returns_fail_not_unknown() -> None:
    """Regression: an unrecognised district code must not silently become UNKNOWN."""
    result = geographic_status(
        "district",
        [],
        ["IN-AP-FAKE"],
        "IN-AP",
        "IN-AP-FAKE",  # not in catalogue
    )
    assert result is Tri.FAIL


def test_district_scope_without_state_is_unknown_even_when_district_matches() -> None:
    """Without state_code we cannot fully verify geography → UNKNOWN."""
    result = geographic_status(
        "district",
        [],
        ["IN-AP-VSP"],
        None,  # no state
        "IN-AP-VSP",  # district is valid
    )
    assert result is Tri.UNKNOWN
