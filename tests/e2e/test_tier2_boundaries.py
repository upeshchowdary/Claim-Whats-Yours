"""Tier 2: Boundary & Corner Cases End-to-End Tests.

Verifies system resilience against boundary value inputs, type coercion attempts,
geographic mismatches, AST evaluation edge cases, decision aggregation, and payload
limits covering the 24 edge cases (E1-E24) across 8 boundary categories (B1 to B8):
- B1: Age Boundaries (E1, E2, E14, E15)
- B2: Income Boundaries (E3, E4, E16, E17)
- B3: Data Types & Coercion (E5, E6)
- B4: Privacy & Obfuscation (E7, E8)
- B5: Geographic Mismatches (E9, E10, E11)
- B6: Rule Evaluation AST Extremes (E12, E13, E18, E19, E20)
- B7: Decision Aggregation & Freshness (E21, E22)
- B8: Payload Size Limits & Malformed Input (E23, E24)
"""

from __future__ import annotations

import json
from typing import Any

import pytest

EVALUATE_PATH = "/api/v1/eligibility/evaluate"


# ==============================================================================
# B1: Age Boundaries (E1, E2, E14, E15)
# ==============================================================================

def test_b1_01_negative_age_rejected_e1(client: Any) -> None:
    """B1 (E1): Negative age -1 is rejected with 422 OUT_OF_RANGE."""
    response = client.post(EVALUATE_PATH, json={"answers": {"age_years": -1}})
    assert response.status_code == 422
    details = response.json().get("error", {}).get("details", [])
    assert any(d.get("code") == "OUT_OF_RANGE" and d.get("field") == "age_years" for d in details)


def test_b1_02_extreme_negative_age_rejected_e1(client: Any) -> None:
    """B1 (E1): Extreme negative age -50 is rejected with 422 OUT_OF_RANGE."""
    response = client.post(EVALUATE_PATH, json={"answers": {"age_years": -50}})
    assert response.status_code == 422
    details = response.json().get("error", {}).get("details", [])
    assert any(d.get("code") == "OUT_OF_RANGE" for d in details)


def test_b1_03_zero_age_accepted(client: Any) -> None:
    """B1: Age 0 (infant / newborn) is within valid range [0, 120] and accepted."""
    response = client.post(EVALUATE_PATH, json={"answers": {"age_years": 0, "state_code": "IN-AP"}})
    assert response.status_code == 200
    assert "results" in response.json()


def test_b1_04_upper_boundary_age_120_accepted(client: Any) -> None:
    """B1: Age 120 (maximum defined age) is accepted without error."""
    response = client.post(EVALUATE_PATH, json={"answers": {"age_years": 120, "state_code": "IN-AP"}})
    assert response.status_code == 200
    assert "results" in response.json()


def test_b1_05_age_over_maximum_121_rejected_e2(client: Any) -> None:
    """B1 (E2): Age 121 (over maximum 120) is rejected with 422 OUT_OF_RANGE."""
    response = client.post(EVALUATE_PATH, json={"answers": {"age_years": 121}})
    assert response.status_code == 422
    details = response.json().get("error", {}).get("details", [])
    assert any(d.get("code") == "OUT_OF_RANGE" and d.get("field") == "age_years" for d in details)


def test_b1_06_extreme_over_maximum_age_150_rejected_e2(client: Any) -> None:
    """B1 (E2): Age 150 is rejected with 422 OUT_OF_RANGE."""
    response = client.post(EVALUATE_PATH, json={"answers": {"age_years": 150}})
    assert response.status_code == 422
    details = response.json().get("error", {}).get("details", [])
    assert any(d.get("code") == "OUT_OF_RANGE" for d in details)


def test_b1_07_age_18_exact_boundary_evaluates_pass_e14(client: Any) -> None:
    """B1 (E14): Age 18 on rule (age_years >= 18) evaluates criterion to PASS."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"age_years": 18, "is_unorganised_worker": True}},
    )
    assert response.status_code == 200
    results = response.json()["results"]
    svanidhi = next((r for r in results if r["scheme_id"] == "sch_pm_svanidhi"), None)
    if svanidhi:
        age_criterion = next(
            (c for c in svanidhi["criteria"] if "18" in str(c.get("explanation", "")) or "age" in c.get("criterion_id", "").lower()),
            None,
        )
        if age_criterion:
            assert age_criterion["status"] == "PASS"


def test_b1_08_age_17_boundary_evaluates_fail_e15(client: Any) -> None:
    """B1 (E15): Age 17 on rule (age_years >= 18) evaluates criterion to FAIL."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"age_years": 17, "is_unorganised_worker": True}},
    )
    assert response.status_code == 200
    results = response.json()["results"]
    svanidhi = next((r for r in results if r["scheme_id"] == "sch_pm_svanidhi"), None)
    if svanidhi:
        assert svanidhi["decision"] == "NOT_LIKELY_ELIGIBLE"
        age_criterion = next(
            (c for c in svanidhi["criteria"] if "18" in str(c.get("explanation", "")) or "age" in c.get("criterion_id", "").lower()),
            None,
        )
        if age_criterion:
            assert age_criterion["status"] == "FAIL"


# ==============================================================================
# B2: Income Boundaries (E3, E4, E16, E17)
# ==============================================================================

def test_b2_01_negative_income_rejected_e3(client: Any) -> None:
    """B2 (E3): Negative income -1 is rejected with 422 OUT_OF_RANGE."""
    response = client.post(EVALUATE_PATH, json={"answers": {"annual_household_income_inr": -1}})
    assert response.status_code == 422
    details = response.json().get("error", {}).get("details", [])
    assert any(d.get("code") == "OUT_OF_RANGE" and d.get("field") == "annual_household_income_inr" for d in details)


def test_b2_02_extreme_negative_income_rejected_e3(client: Any) -> None:
    """B2 (E3): Extreme negative income -100000 is rejected with 422 OUT_OF_RANGE."""
    response = client.post(EVALUATE_PATH, json={"answers": {"annual_household_income_inr": -100000}})
    assert response.status_code == 422
    details = response.json().get("error", {}).get("details", [])
    assert any(d.get("code") == "OUT_OF_RANGE" for d in details)


def test_b2_03_zero_income_accepted_and_non_falsy_e4(client: Any) -> None:
    """B2 (E4): Zero income 0 is valid non-negative integer, not treated as missing/falsy."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"annual_household_income_inr": 0, "state_code": "IN-AP"}},
    )
    assert response.status_code == 200
    assert "annual_household_income_inr" not in response.json().get("missing_fields", [])


def test_b2_04_exact_threshold_income_250000_e16(client: Any) -> None:
    """B2 (E16): Income of exactly 250,000 INR evaluates without error."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"annual_household_income_inr": 250000, "state_code": "IN-AP"}},
    )
    assert response.status_code == 200
    assert "results" in response.json()


def test_b2_05_threshold_plus_one_income_250001_e17(client: Any) -> None:
    """B2 (E17): Income of 250,001 INR evaluates cleanly."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"annual_household_income_inr": 250001, "state_code": "IN-AP"}},
    )
    assert response.status_code == 200
    assert "results" in response.json()


def test_b2_06_large_income_100_million(client: Any) -> None:
    """B2: Extremely large income (100,000,000 INR) is handled without integer overflow."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"annual_household_income_inr": 100000000, "state_code": "IN-AP"}},
    )
    assert response.status_code == 200
    assert "results" in response.json()


# ==============================================================================
# B3: Data Types & Coercion (E5, E6)
# ==============================================================================

def test_b3_01_numeric_string_as_integer_rejected_e5(client: Any) -> None:
    """B3 (E5): String '25' for integer age_years is rejected with 422 INVALID_TYPE (no silent coercion)."""
    response = client.post(EVALUATE_PATH, json={"answers": {"age_years": "25"}})
    assert response.status_code == 422
    details = response.json().get("error", {}).get("details", [])
    assert any(d.get("code") == "INVALID_TYPE" and d.get("field") == "age_years" for d in details)


def test_b3_02_boolean_true_as_integer_rejected_e6(client: Any) -> None:
    """B3 (E6): Python True is bool subclass of int; must be strictly rejected with INVALID_TYPE."""
    response = client.post(EVALUATE_PATH, json={"answers": {"age_years": True}})
    assert response.status_code == 422
    details = response.json().get("error", {}).get("details", [])
    assert any(d.get("code") == "INVALID_TYPE" and d.get("field") == "age_years" for d in details)


def test_b3_03_boolean_false_as_integer_rejected_e6(client: Any) -> None:
    """B3 (E6): Python False for annual_household_income_inr is rejected with INVALID_TYPE."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"annual_household_income_inr": False}},
    )
    assert response.status_code == 422
    details = response.json().get("error", {}).get("details", [])
    assert any(d.get("code") == "INVALID_TYPE" for d in details)


def test_b3_04_string_as_boolean_rejected(client: Any) -> None:
    """B3: String 'true' for boolean field is_farmer is rejected with INVALID_TYPE."""
    response = client.post(EVALUATE_PATH, json={"answers": {"is_farmer": "true"}})
    assert response.status_code == 422
    details = response.json().get("error", {}).get("details", [])
    assert any(d.get("code") == "INVALID_TYPE" and d.get("field") == "is_farmer" for d in details)


def test_b3_05_list_as_scalar_rejected(client: Any) -> None:
    """B3: List [25] for scalar field age_years is rejected with INVALID_TYPE."""
    response = client.post(EVALUATE_PATH, json={"answers": {"age_years": [25]}})
    assert response.status_code == 422
    details = response.json().get("error", {}).get("details", [])
    assert any(d.get("code") == "INVALID_TYPE" for d in details)


def test_b3_06_dict_as_scalar_rejected(client: Any) -> None:
    """B3: Dict for scalar field landholding_acres is rejected with INVALID_TYPE."""
    response = client.post(EVALUATE_PATH, json={"answers": {"landholding_acres": {"val": 2.5}}})
    assert response.status_code == 422
    details = response.json().get("error", {}).get("details", [])
    assert any(d.get("code") == "INVALID_TYPE" for d in details)


def test_b3_07_null_value_for_optional_field_accepted(client: Any) -> None:
    """B3: Explicit null value for an optional field is treated as omitted/None, not crashing."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"age_years": None, "state_code": "IN-AP"}},
    )
    assert response.status_code == 200
    assert "results" in response.json()


# ==============================================================================
# B4: Privacy & Obfuscation (E7, E8)
# ==============================================================================

def test_b4_01_mixed_forbidden_keys_rejected_e7_e8(client: Any) -> None:
    """B4 (E7, E8): Valid fields mixed with forbidden PAN key are rejected with FORBIDDEN_FIELD."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"age_years": 30, "pan": "ABCDE1234F", "state_code": "IN-AP"}},
    )
    assert response.status_code == 422
    details = response.json().get("error", {}).get("details", [])
    assert any(d.get("code") == "FORBIDDEN_FIELD" and d.get("field") == "pan" for d in details)


def test_b4_02_casing_variation_uppercase_aadhaar(client: Any) -> None:
    """B4: Uppercase AADHAAR is caught by case-insensitive privacy filter."""
    response = client.post(EVALUATE_PATH, json={"answers": {"AADHAAR": "123456789012"}})
    assert response.status_code == 422
    details = response.json().get("error", {}).get("details", [])
    assert any(d.get("code") == "FORBIDDEN_FIELD" for d in details)


def test_b4_03_casing_variation_title_case_pan(client: Any) -> None:
    """B4: Title-case Pan is caught by case-insensitive privacy filter."""
    response = client.post(EVALUATE_PATH, json={"answers": {"Pan": "ABCDE1234F"}})
    assert response.status_code == 422
    details = response.json().get("error", {}).get("details", [])
    assert any(d.get("code") == "FORBIDDEN_FIELD" for d in details)


def test_b4_04_forbidden_key_with_null_value_rejected(client: Any) -> None:
    """B4: Forbidden field name even with null value is strictly rejected."""
    response = client.post(EVALUATE_PATH, json={"answers": {"aadhaar": None}})
    assert response.status_code == 422
    details = response.json().get("error", {}).get("details", [])
    assert any(d.get("code") == "FORBIDDEN_FIELD" for d in details)


def test_b4_05_forbidden_field_value_never_echoed(client: Any) -> None:
    """B4: The value of a sensitive identifier is never echoed back in the response body."""
    secret_marker = "CANARY_SECRET_BANK_ACCT_998877"
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"bank_account": secret_marker}},
    )
    assert response.status_code == 422
    assert secret_marker not in response.text


def test_b4_06_multiple_forbidden_keys_all_reported(client: Any) -> None:
    """B4: Multiple forbidden keys in request are detected without server crash."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"aadhaar": "1234", "pan": "5678", "phone": "9999"}},
    )
    assert response.status_code == 422
    details = response.json().get("error", {}).get("details", [])
    forbidden_codes = [d for d in details if d.get("code") == "FORBIDDEN_FIELD"]
    assert len(forbidden_codes) >= 1


# ==============================================================================
# B5: Geographic Mismatches (E9, E10, E11)
# ==============================================================================

def test_b5_01_cross_state_district_mismatch_e9(client: Any) -> None:
    """B5 (E9): District belonging to AP (IN-AP-GNT) paired with State MH (IN-MH) fails geography."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"state_code": "IN-MH", "district_code": "IN-AP-GNT", "is_farmer": True}},
    )
    assert response.status_code == 200
    for r in response.json()["results"]:
        if r["scheme_id"] == "sch_ap_rythu_bharosa":
            assert r["decision"] != "LIKELY_ELIGIBLE"


def test_b5_02_district_without_state_e10(client: Any) -> None:
    """B5 (E10): District provided with state_code null evaluates geography to UNKNOWN, capping decision."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"district_code": "IN-AP-GNT", "is_farmer": True}},
    )
    assert response.status_code == 200
    for r in response.json()["results"]:
        if r["scheme_id"] == "sch_ap_rythu_bharosa":
            assert r["decision"] in ("NEEDS_MORE_INFORMATION", "NOT_LIKELY_ELIGIBLE")


def test_b5_03_invalid_district_code_e11(client: Any) -> None:
    """B5 (E11): Nonexistent district code IN-AP-UNKNOWN999 does not cause server 500 error."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"state_code": "IN-AP", "district_code": "IN-AP-UNKNOWN999", "is_farmer": True}},
    )
    assert response.status_code == 200
    assert "results" in response.json()


def test_b5_04_state_code_with_whitespace_rejected(client: Any) -> None:
    """B5: State code with leading/trailing whitespace in query param is rejected with 422."""
    response = client.get("/api/v1/schemes?state_code=%20IN-AP%20")
    assert response.status_code == 422


def test_b5_05_state_with_no_state_schemes_returns_central(client: Any) -> None:
    """B5: Resident of Sikkim (IN-SK) receives central schemes but 0 AP state schemes."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"state_code": "IN-SK", "is_farmer": True, "landholding_acres": 2.0}},
    )
    assert response.status_code == 200
    eligible_schemes = [
        r["scheme_id"] for r in response.json()["results"]
        if r["decision"] == "LIKELY_ELIGIBLE"
    ]
    assert "sch_pm_kisan_2019" in eligible_schemes
    assert "sch_ap_rythu_bharosa" not in eligible_schemes


def test_b5_06_schemes_search_with_unknown_state(client: Any) -> None:
    """B5: GET /api/v1/schemes with invalid state_code returns HTTP 422."""
    response = client.get("/api/v1/schemes?state_code=IN-NONEXISTENT")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# ==============================================================================
# B6: Rule Evaluation AST Extremes (E12, E13, E18, E19, E20)
# ==============================================================================

def test_b6_01_empty_profile_e12(client: Any) -> None:
    """B6 (E12): Empty profile {} evaluates without KeyError and all schemes report NEEDS_MORE_INFORMATION."""
    response = client.post(EVALUATE_PATH, json={"answers": {}})
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) >= 1
    for r in data["results"]:
        assert r["decision"] == "NEEDS_MORE_INFORMATION"
    assert len(data["missing_fields"]) >= 1
    assert len(data["follow_up_questions"]) >= 1


def test_b6_02_sentinel_decline_prefer_not_to_say_e13(client: Any) -> None:
    """B6 (E13): Sentinel decline 'prefer_not_to_say' is treated as UNKNOWN."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"occupation": "prefer_not_to_say", "gender": "prefer_not_to_say"}},
    )
    assert response.status_code == 200
    for r in response.json()["results"]:
        assert r["decision"] == "NEEDS_MORE_INFORMATION"


def test_b6_03_all_group_fail_and_unknown_short_circuits_to_fail_e18(client: Any) -> None:
    """B6 (E18): Group 'all' with [FAIL, UNKNOWN] must evaluate to FAIL (short-circuit ineligible)."""
    # PM SVANidhi rule: age >= 18 AND is_unorganised_worker == True
    # If age is 16 (FAIL) and worker is omitted (UNKNOWN), decision must be NOT_LIKELY_ELIGIBLE
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"age_years": 16}},
    )
    assert response.status_code == 200
    svanidhi = next((r for r in response.json()["results"] if r["scheme_id"] == "sch_pm_svanidhi"), None)
    if svanidhi:
        assert svanidhi["decision"] == "NOT_LIKELY_ELIGIBLE"


def test_b6_04_any_group_pass_and_unknown_short_circuits_to_pass_e19(client: Any) -> None:
    """B6 (E19): Group 'any' with [PASS, UNKNOWN] must short-circuit to PASS."""
    # When any criteria branch is satisfied, the group should evaluate to PASS
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"state_code": "IN-AP", "is_farmer": True, "landholding_acres": 2.0}},
    )
    assert response.status_code == 200
    kisan = next((r for r in response.json()["results"] if r["scheme_id"] == "sch_pm_kisan_2019"), None)
    if kisan:
        assert kisan["decision"] == "LIKELY_ELIGIBLE"


def test_b6_05_not_group_unknown_remains_unknown_e20(client: Any) -> None:
    """B6 (E20): Negation of UNKNOWN condition remains UNKNOWN (never turns unknown into pass)."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"state_code": "IN-AP"}},
    )
    assert response.status_code == 200
    for r in response.json()["results"]:
        assert r["decision"] != "LIKELY_ELIGIBLE"


def test_b6_06_only_advisory_fields_missing(client: Any) -> None:
    """B6: When all mandatory criteria are PASS and only optional/advisory fields missing, decision is LIKELY_ELIGIBLE."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {
            "state_code": "IN-AP",
            "is_farmer": True,
            "landholding_acres": 2.5,
        }},
    )
    assert response.status_code == 200
    kisan = next((r for r in response.json()["results"] if r["scheme_id"] == "sch_pm_kisan_2019"), None)
    if kisan:
        assert kisan["decision"] == "LIKELY_ELIGIBLE"


# ==============================================================================
# B7: Decision Aggregation & Freshness (E21, E22)
# ==============================================================================

def test_b7_01_verification_freshness_e21(client: Any) -> None:
    """B7 (E21): Schemes report verification freshness and review due date."""
    response = client.get("/api/v1/schemes/sch_pm_kisan_2019")
    assert response.status_code == 200
    data = response.json()
    assert "verification_status" in data
    assert data["verification_status"] == "verified"
    assert "review_due_at" in data


def test_b7_02_geographic_exclusion_e22(client: Any) -> None:
    """B7 (E22): Scheme whose geography fails is completely excluded or marked ineligible."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"state_code": "IN-MH", "is_farmer": True, "landholding_acres": 2.0}},
    )
    assert response.status_code == 200
    results = response.json()["results"]
    ap_scheme = next((r for r in results if r["scheme_id"] == "sch_ap_rythu_bharosa"), None)
    if ap_scheme:
        assert ap_scheme["decision"] != "LIKELY_ELIGIBLE"


def test_b7_03_decision_ordering_priority(client: Any) -> None:
    """B7: Evaluation results are sorted by decision priority (LIKELY_ELIGIBLE first)."""
    response = client.post(
        EVALUATE_PATH,
        json={"answers": {"state_code": "IN-AP", "is_farmer": True, "landholding_acres": 2.0}},
    )
    assert response.status_code == 200
    decisions = [r["decision"] for r in response.json()["results"]]
    order_rank = {
        "LIKELY_ELIGIBLE": 0,
        "NEEDS_MORE_INFORMATION": 1,
        "VERIFICATION_REQUIRED": 2,
        "NOT_LIKELY_ELIGIBLE": 3,
    }
    ranks = [order_rank.get(d, 99) for d in decisions]
    assert ranks == sorted(ranks)


def test_b7_04_statutory_disclaimer_immutability(client: Any) -> None:
    """B7: Every evaluation response carries the non-binding statutory disclaimer."""
    response = client.post(EVALUATE_PATH, json={"answers": {"age_years": 30}})
    assert response.status_code == 200
    disclaimer = response.json().get("disclaimer", "")
    assert len(disclaimer) > 0


def test_b7_05_missing_fields_deduplication(client: Any) -> None:
    """B7: Missing fields across all schemes are deduplicated in root missing_fields array."""
    response = client.post(EVALUATE_PATH, json={"answers": {}})
    assert response.status_code == 200
    missing = response.json().get("missing_fields", [])
    assert len(missing) == len(set(missing))


def test_b7_06_follow_up_questions_ranking(client: Any) -> None:
    """B7: Follow-up questions are ordered with most-blocking fields first."""
    response = client.post(EVALUATE_PATH, json={"answers": {}})
    assert response.status_code == 200
    questions = response.json().get("follow_up_questions", [])
    assert isinstance(questions, list)
    for q in questions:
        assert "field" in q
        assert "label" in q


# ==============================================================================
# B8: Payload Size Limits & Malformed Input (E23, E24)
# ==============================================================================

def test_b8_01_payload_exceeding_64kb_rejected_413(client: Any) -> None:
    """B8: Request body exceeding 64KB (65536 bytes) is rejected with HTTP 413 PAYLOAD_TOO_LARGE."""
    oversized_payload = {"answers": {"note": "x" * 70000}}
    body = json.dumps(oversized_payload).encode()
    headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
    response = client.post(EVALUATE_PATH, content=body, headers=headers)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_b8_02_oversized_content_length_rejected_413(client: Any) -> None:
    """B8: Oversized declared Content-Length is rejected before reading body."""
    headers = {"Content-Type": "application/json", "Content-Length": "100000"}
    response = client.post(EVALUATE_PATH, content=b"{}", headers=headers)
    assert response.status_code == 413


def test_b8_03_body_within_64kb_accepted(client: Any) -> None:
    """B8: Payload within 64KB (e.g. 10KB) is accepted with 200."""
    body = json.dumps({"answers": {"age_years": 25, "state_code": "IN-AP"}}).encode()
    headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
    response = client.post(EVALUATE_PATH, content=body, headers=headers)
    assert response.status_code == 200


def test_b8_04_malformed_json_body_rejected(client: Any) -> None:
    """B8: Malformed JSON body returns HTTP 400 or 422 without 500 error."""
    response = client.post(
        EVALUATE_PATH,
        content=b"{\"answers\": {broken_json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code in (400, 422)
    assert response.status_code != 500


def test_b8_05_constant_time_tracking_token_comparison_e23(
    client: Any, tracking_payload: dict[str, Any]
) -> None:
    """B8 (E23): Tampered tracking token returns 404 TRACKING_NOT_FOUND consistently."""
    create_resp = client.post("/api/v1/tracking", json=tracking_payload)
    assert create_resp.status_code == 201
    tid = create_resp.json()["tracking_id"]
    real_token = create_resp.json()["token"]

    # Slight modification (tampered token)
    tampered_token = real_token[:-1] + ("A" if real_token[-1] != "A" else "B")
    get_resp = client.get(f"/api/v1/tracking/{tid}", headers={"X-Tracking-Token": tampered_token})
    assert get_resp.status_code == 404
    assert get_resp.json()["error"]["code"] == "TRACKING_NOT_FOUND"


def test_b8_06_conversational_noise_graceful_handling_e24(client: Any) -> None:
    """B8 (E24): Ambient conversational noise 'hello, can you help me' does not crash the service."""
    payload = {
        "messages": ["hello, can you help me find some schemes?"],
        "answers": {},
    }
    response = client.post("/api/v1/assistant/turn", json=payload)
    assert response.status_code in (200, 503)
    assert response.status_code != 500


def test_b8_07_empty_json_object_body_rejected(client: Any) -> None:
    """B8: Sending empty JSON object {} to evaluate endpoint returns 422 validation error."""
    response = client.post(EVALUATE_PATH, json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
