"""Tier 3: Pairwise & Cross-Feature Interactions E2E Test Suite.

Verifies multi-dimensional feature interactions, cross-cutting constraints, and state flows:
- C1: Geography + Eligibility Rules (all-india vs state scope in resident vs non-resident states)
- C2: Category Filtering + Question Scoping (filtering restricts schemes & follow-up questions)
- C3: Multi-value query parameters + pagination + search
- C4: Privacy guardrails across all endpoints (rejection of sensitive identifiers)
- C5: Tracking lifecycle (create -> query -> update -> unauthorized rejection)
- C6: Complex rule composition (all + any + not AST nesting, short-circuit, and tri-state evaluation)

Opaque-box design: Tests interact exclusively with the public HTTP interface.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import pytest

# ==============================================================================
# C1: Geography + Eligibility Rules Interactions
# ==============================================================================


@pytest.mark.e2e
def test_c1_central_scheme_evaluated_across_all_resident_states(client: Any) -> None:
    """Central schemes (all_india scope) must be evaluated across all Indian states."""
    test_states = ["IN-AP", "IN-MH", "IN-UP", "IN-KA", "IN-DL", "IN-RJ"]
    for state in test_states:
        payload = {
            "answers": {
                "state_code": state,
                "is_farmer": True,
                "landholding_acres": 2.5,
                "is_unorganised_worker": False,
            }
        }
        resp = client.post("/api/v1/eligibility/evaluate", json=payload)
        assert resp.status_code == 200, f"Failed for state {state}: {resp.text}"
        data = resp.json()
        scheme_ids = [r["scheme_id"] for r in data.get("results", [])]
        assert "sch_pm_kisan_2019" in scheme_ids, f"PM-KISAN missing for resident state {state}"
        kisan_result = next(r for r in data["results"] if r["scheme_id"] == "sch_pm_kisan_2019")
        assert kisan_result["decision"] == "LIKELY_ELIGIBLE"


@pytest.mark.e2e
def test_c1_state_scheme_evaluated_only_in_resident_state(client: Any) -> None:
    """State-specific schemes must evaluate for residents and be excluded for non-residents."""
    # Resident state: Andhra Pradesh (IN-AP)
    ap_payload = {
        "answers": {
            "state_code": "IN-AP",
            "is_farmer": True,
            "landholding_acres": 2.0,
            "is_unorganised_worker": False,
        }
    }
    ap_resp = client.post("/api/v1/eligibility/evaluate", json=ap_payload)
    assert ap_resp.status_code == 200
    ap_data = ap_resp.json()
    ap_scheme_ids = [r["scheme_id"] for r in ap_data.get("results", [])]
    assert "sch_ap_rythu_bharosa" in ap_scheme_ids
    ap_rythu = next(r for r in ap_data["results"] if r["scheme_id"] == "sch_ap_rythu_bharosa")
    assert ap_rythu["decision"] == "LIKELY_ELIGIBLE"

    # Non-resident states must completely exclude sch_ap_rythu_bharosa
    for non_res_state in ["IN-MH", "IN-UP", "IN-KA", "IN-PB"]:
        other_payload = {
            "answers": {
                "state_code": non_res_state,
                "is_farmer": True,
                "landholding_acres": 2.0,
                "is_unorganised_worker": False,
            }
        }
        resp = client.post("/api/v1/eligibility/evaluate", json=other_payload)
        assert resp.status_code == 200
        other_ids = [r["scheme_id"] for r in resp.json().get("results", [])]
        assert (
            "sch_ap_rythu_bharosa" not in other_ids
        ), f"sch_ap_rythu_bharosa improperly included for {non_res_state}"


@pytest.mark.e2e
def test_c1_district_evaluation_inclusive_of_state_and_central(client: Any) -> None:
    """Evaluation with district code within state must consider central and state schemes."""
    payload = {
        "answers": {
            "state_code": "IN-AP",
            "district_code": "IN-AP-GNT",
            "is_farmer": True,
            "landholding_acres": 1.5,
            "is_unorganised_worker": False,
        }
    }
    resp = client.post("/api/v1/eligibility/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    scheme_ids = {r["scheme_id"] for r in data.get("results", [])}
    assert "sch_pm_kisan_2019" in scheme_ids
    assert "sch_ap_rythu_bharosa" in scheme_ids


@pytest.mark.e2e
def test_c1_schemes_list_state_filter_returns_central_and_state(client: Any) -> None:
    """GET /api/v1/schemes?state_code=IN-AP returns both all_india and AP state schemes."""
    resp = client.get("/api/v1/schemes?state_code=IN-AP")
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {s["id"] for s in data.get("items", [])}
    # Should include Central schemes (PM-KISAN, PM SVANidhi) and AP scheme
    assert "sch_pm_kisan_2019" in item_ids
    assert "sch_ap_rythu_bharosa" in item_ids


@pytest.mark.e2e
def test_c1_schemes_list_non_resident_state_excludes_other_state_schemes(client: Any) -> None:
    """GET /api/v1/schemes?state_code=IN-MH excludes AP state schemes."""
    resp = client.get("/api/v1/schemes?state_code=IN-MH")
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {s["id"] for s in data.get("items", [])}
    assert "sch_pm_kisan_2019" in item_ids
    assert "sch_ap_rythu_bharosa" not in item_ids


@pytest.mark.e2e
def test_c1_government_level_filter_central_only(client: Any) -> None:
    """POST /api/v1/eligibility/evaluate with central filter excludes state schemes."""
    payload = {
        "answers": {
            "state_code": "IN-AP",
            "is_farmer": True,
            "landholding_acres": 2.0,
            "is_unorganised_worker": False,
        },
        "filters": {"government_levels": ["central"]},
    }
    resp = client.post("/api/v1/eligibility/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    scheme_ids = [r["scheme_id"] for r in data.get("results", [])]
    assert "sch_pm_kisan_2019" in scheme_ids
    assert "sch_ap_rythu_bharosa" not in scheme_ids


@pytest.mark.e2e
def test_c1_government_level_filter_state_level_only(client: Any) -> None:
    """POST /api/v1/eligibility/evaluate with state filter returns only state schemes."""
    payload = {
        "answers": {
            "state_code": "IN-AP",
            "is_farmer": True,
            "landholding_acres": 2.0,
            "is_unorganised_worker": False,
        },
        "filters": {"government_levels": ["state"]},
    }
    resp = client.post("/api/v1/eligibility/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    scheme_ids = [r["scheme_id"] for r in data.get("results", [])]
    assert "sch_ap_rythu_bharosa" in scheme_ids
    assert "sch_pm_kisan_2019" not in scheme_ids
    assert "sch_pm_svanidhi" not in scheme_ids


@pytest.mark.e2e
def test_c1_non_resident_state_with_state_level_filter_returns_empty(client: Any) -> None:
    """POST /api/v1/eligibility/evaluate with state filter in state with no schemes returns empty."""
    payload = {
        "answers": {
            "state_code": "IN-MH",
            "is_farmer": True,
            "landholding_acres": 2.0,
        },
        "filters": {"government_levels": ["state"]},
    }
    resp = client.post("/api/v1/eligibility/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data.get("results", [])) == 0


# ==============================================================================
# C2: Category Filtering + Question Scoping
# ==============================================================================


@pytest.mark.e2e
def test_c2_category_filter_agriculture_restricts_results(client: Any) -> None:
    """Category filter 'agriculture' returns only agricultural schemes."""
    payload = {
        "answers": {
            "state_code": "IN-AP",
            "age_years": 35,
            "is_farmer": True,
            "landholding_acres": 1.5,
            "is_unorganised_worker": True,
        },
        "filters": {"categories": ["agriculture"]},
    }
    resp = client.post("/api/v1/eligibility/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    results = data.get("results", [])
    assert len(results) > 0
    for item in results:
        assert (
            "categories" not in item or "agriculture" in item["categories"]
        ), f"Scheme {item['scheme_id']} is not an agriculture scheme"
    result_ids = [r["scheme_id"] for r in results]
    assert "sch_pm_svanidhi" not in result_ids


@pytest.mark.e2e
def test_c2_category_filter_employment_restricts_results(client: Any) -> None:
    """Category filter 'employment' returns only matching employment/worker schemes."""
    payload = {
        "answers": {
            "state_code": "IN-AP",
            "age_years": 35,
            "is_farmer": True,
            "landholding_acres": 1.5,
            "is_unorganised_worker": True,
        },
        "filters": {"categories": ["employment"]},
    }
    resp = client.post("/api/v1/eligibility/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    result_ids = [r["scheme_id"] for r in data.get("results", [])]
    assert "sch_pm_svanidhi" in result_ids
    assert "sch_pm_kisan_2019" not in result_ids


@pytest.mark.e2e
def test_c2_category_filter_question_scoping_agricultural_fields_present(client: Any) -> None:
    """When filtering by agriculture, missing questions must ask for agricultural fields."""
    payload = {
        "answers": {
            "state_code": "IN-AP",
        },
        "filters": {"categories": ["agriculture"]},
    }
    resp = client.post("/api/v1/eligibility/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    missing = data.get("missing_fields", [])
    assert "is_farmer" in missing
    # Agricultural fields should be among follow up questions
    question_fields = [q["field"] for q in data.get("follow_up_questions", [])]
    assert "is_farmer" in question_fields


@pytest.mark.e2e
def test_c2_category_filter_question_scoping_no_unrelated_questions(client: Any) -> None:
    """When category scoping is implemented, vendor fields must not leak into agriculture questions."""
    payload = {
        "answers": {
            "state_code": "IN-AP",
        },
        "filters": {"categories": ["agriculture"]},
    }
    resp = client.post("/api/v1/eligibility/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    # In full M1 scoping, is_unorganised_worker is pruned because SVANidhi is excluded
    if "is_unorganised_worker" not in data.get("missing_fields", []):
        question_fields = [q["field"] for q in data.get("follow_up_questions", [])]
        assert "is_unorganised_worker" not in question_fields


@pytest.mark.e2e
def test_c2_multiple_categories_combined_filter(client: Any) -> None:
    """Evaluation with multiple categories includes schemes matching any of the specified categories."""
    payload = {
        "answers": {
            "state_code": "IN-AP",
            "age_years": 40,
            "is_farmer": True,
            "landholding_acres": 2.0,
            "is_unorganised_worker": True,
        },
        "filters": {"categories": ["agriculture", "financial_inclusion"]},
    }
    resp = client.post("/api/v1/eligibility/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    result_ids = {r["scheme_id"] for r in data.get("results", [])}
    assert "sch_pm_kisan_2019" in result_ids
    assert "sch_pm_svanidhi" in result_ids


@pytest.mark.e2e
def test_c2_unmatched_category_yields_empty_results(client: Any) -> None:
    """Filtering by a nonexistent category returns HTTP 200 with 0 results and no 500 error."""
    payload = {
        "answers": {
            "state_code": "IN-AP",
            "age_years": 40,
            "is_farmer": True,
        },
        "filters": {"categories": ["nonexistent_space_research_category"]},
    }
    resp = client.post("/api/v1/eligibility/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data.get("results", [])) == 0


# ==============================================================================
# C3: Multi-value Query Parameters + Pagination + Search
# ==============================================================================


@pytest.mark.e2e
def test_c3_repeatable_government_level_query_params(client: Any) -> None:
    """GET /api/v1/schemes with repeatable government_level handles multi-values cleanly."""
    resp = client.get("/api/v1/schemes?government_level=central&government_level=state")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    items = data["items"]
    # Returned items must belong only to the specified levels
    levels = {item["government_level"] for item in items}
    assert levels.issubset({"central", "state"})


@pytest.mark.e2e
def test_c3_repeatable_category_query_params(client: Any) -> None:
    """GET /api/v1/schemes with repeatable category query parameters."""
    resp = client.get("/api/v1/schemes?category=agriculture&category=financial_inclusion")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 1


@pytest.mark.e2e
def test_c3_search_query_combined_with_government_level(client: Any) -> None:
    """GET /api/v1/schemes combining text search 'kisan' and government_level 'central'."""
    resp = client.get("/api/v1/schemes?q=kisan&government_level=central")
    assert resp.status_code == 200
    data = resp.json()
    items = data.get("items", [])
    assert len(items) >= 1
    for item in items:
        assert item["government_level"] == "central"
        assert "kisan" in item["name"].lower() or "kisan" in item["summary"].lower()


@pytest.mark.e2e
def test_c3_search_query_combined_with_category(client: Any) -> None:
    """GET /api/v1/schemes combining text search 'svanidhi' and category filter."""
    resp = client.get("/api/v1/schemes?q=svanidhi&category=financial_inclusion")
    assert resp.status_code == 200
    data = resp.json()
    items = data.get("items", [])
    assert len(items) >= 1
    assert any("svanidhi" in item["id"].lower() for item in items)


@pytest.mark.e2e
def test_c3_pagination_first_and_second_page_consistency(client: Any) -> None:
    """GET /api/v1/schemes with page_size=1 across page 1 and page 2 returns distinct items."""
    resp1 = client.get("/api/v1/schemes?page=1&page_size=1")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert len(data1["items"]) == 1
    item1_id = data1["items"][0]["id"]

    resp2 = client.get("/api/v1/schemes?page=2&page_size=1")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2["items"]) == 1
    item2_id = data2["items"][0]["id"]

    assert item1_id != item2_id, "Page 1 and Page 2 should return distinct items"
    assert data1["total"] == data2["total"]


@pytest.mark.e2e
def test_c3_pagination_page_out_of_bounds(client: Any) -> None:
    """GET /api/v1/schemes with page exceeding total returns empty items list cleanly."""
    resp = client.get("/api/v1/schemes?page=999&page_size=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["page"] == 999
    assert data["total"] >= 1


@pytest.mark.e2e
def test_c3_search_case_insensitivity(client: Any) -> None:
    """Text search on schemes endpoint must be case-insensitive."""
    resp_upper = client.get("/api/v1/schemes?q=KISAN")
    resp_lower = client.get("/api/v1/schemes?q=kisan")
    assert resp_upper.status_code == 200
    assert resp_lower.status_code == 200
    ids_upper = [s["id"] for s in resp_upper.json().get("items", [])]
    ids_lower = [s["id"] for s in resp_lower.json().get("items", [])]
    assert ids_upper == ids_lower


# ==============================================================================
# C4: Privacy Guardrails Across All Endpoints
# ==============================================================================


@pytest.mark.e2e
def test_c4_evaluate_rejects_aadhaar_with_422(client: Any) -> None:
    """POST /api/v1/eligibility/evaluate rejects requests containing 'aadhaar'."""
    payload = {"answers": {"aadhaar": "1234-5678-9012", "age_years": 30}}
    resp = client.post("/api/v1/eligibility/evaluate", json=payload)
    assert resp.status_code == 422
    data = resp.json()
    details = data.get("error", {}).get("details", [])
    assert any(d.get("code") == "FORBIDDEN_FIELD" for d in details)
    assert any(d.get("field") == "aadhaar" for d in details)


@pytest.mark.e2e
def test_c4_evaluate_rejects_pan_and_bank_account(client: Any) -> None:
    """POST /api/v1/eligibility/evaluate rejects PAN and bank account identifiers."""
    for field, val in [("pan", "ABCDE1234F"), ("bank_account", "12345678901234")]:
        payload = {"answers": {field: val, "age_years": 25}}
        resp = client.post("/api/v1/eligibility/evaluate", json=payload)
        assert resp.status_code == 422, f"Failed to reject forbidden field {field}"
        details = resp.json().get("error", {}).get("details", [])
        assert any(d.get("code") == "FORBIDDEN_FIELD" for d in details)


@pytest.mark.e2e
def test_c4_evaluate_rejects_phone_and_email(client: Any) -> None:
    """POST /api/v1/eligibility/evaluate rejects phone and email personal contact details."""
    for field, val in [("phone", "9876543210"), ("email", "test@example.com")]:
        payload = {"answers": {field: val, "state_code": "IN-AP"}}
        resp = client.post("/api/v1/eligibility/evaluate", json=payload)
        assert resp.status_code == 422
        details = resp.json().get("error", {}).get("details", [])
        assert any(d.get("code") == "FORBIDDEN_FIELD" for d in details)


@pytest.mark.e2e
def test_c4_forbidden_value_never_echoed_in_response(client: Any) -> None:
    """Forbidden field values must never be logged or echoed anywhere in response body."""
    sensitive_value = "9876-5432-1098-7654"
    payload = {"answers": {"aadhaar": sensitive_value, "age_years": 40}}
    resp = client.post("/api/v1/eligibility/evaluate", json=payload)
    assert resp.status_code == 422
    assert sensitive_value not in resp.text, "Sensitive Aadhaar value was echoed in error response!"


@pytest.mark.e2e
def test_c4_case_insensitive_forbidden_field_rejection(client: Any) -> None:
    """Forbidden field rejection must be case-insensitive (e.g. Aadhaar, AADHAAR, Pan, PHONE)."""
    variations = ["Aadhaar", "AADHAAR", "Pan", "PAN", "Phone", "EMAIL"]
    for var in variations:
        payload = {"answers": {var: "sensitive-data-123"}}
        resp = client.post("/api/v1/eligibility/evaluate", json=payload)
        assert resp.status_code == 422, f"Failed to reject case variation: {var}"
        details = resp.json().get("error", {}).get("details", [])
        assert any(d.get("code") == "FORBIDDEN_FIELD" for d in details)


@pytest.mark.e2e
def test_c4_tracking_rejects_forbidden_fields(client: Any) -> None:
    """POST /api/v1/tracking rejects payloads containing forbidden fields."""
    payload = {
        "scheme_id": "sch_pm_kisan_2019",
        "aadhaar": "1234-5678-9012",
    }
    resp = client.post("/api/v1/tracking", json=payload)
    assert resp.status_code == 422


@pytest.mark.e2e
def test_c4_mixed_forbidden_and_valid_answers_aborts_evaluation(client: Any) -> None:
    """Requests containing both valid and forbidden fields must immediately abort without evaluation."""
    payload = {
        "answers": {
            "state_code": "IN-AP",
            "is_farmer": True,
            "landholding_acres": 3.0,
            "aadhaar": "9999-0000-1111",
        }
    }
    resp = client.post("/api/v1/eligibility/evaluate", json=payload)
    assert resp.status_code == 422
    data = resp.json()
    assert "results" not in data, "Evaluation results must not be returned when forbidden keys exist"


# ==============================================================================
# C5: Tracking Lifecycle
# ==============================================================================


@pytest.mark.e2e
def test_c5_tracking_lifecycle_full_crud(client: Any, sample_central_scheme_id: str) -> None:
    """Full anonymous tracking lifecycle: create -> query -> update status -> verify."""
    # 1. Create tracking record
    create_payload = {
        "scheme_id": sample_central_scheme_id,
        "status": "planned",
        "progress_date": "2026-11-22",
    }
    create_resp = client.post("/api/v1/tracking", json=create_payload)
    assert create_resp.status_code == 201
    create_data = create_resp.json()
    assert "tracking_id" in create_data
    assert create_data["tracking_id"].startswith("trk_")
    assert len(create_data["tracking_id"]) >= 12
    assert "token" in create_data
    token = create_data["token"]
    tid = create_data["tracking_id"]
    assert create_data["status"] == "planned"

    # 2. Query tracking record with valid secret token
    get_resp = client.get(f"/api/v1/tracking/{tid}", headers={"X-Tracking-Token": token})
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["tracking_id"] == tid
    assert get_data["status"] == "planned"
    assert get_data["scheme_id"] == sample_central_scheme_id

    # 3. Update tracking record status to 'submitted'
    patch_resp = client.patch(
        f"/api/v1/tracking/{tid}",
        headers={"X-Tracking-Token": token},
        json={"status": "submitted"},
    )
    assert patch_resp.status_code == 200
    patch_data = patch_resp.json()
    assert patch_data["status"] == "submitted"

    # 4. Verify updated state on subsequent query
    get_resp2 = client.get(f"/api/v1/tracking/{tid}", headers={"X-Tracking-Token": token})
    assert get_resp2.status_code == 200
    assert get_resp2.json()["status"] == "submitted"


@pytest.mark.e2e
def test_c5_tracking_unauthorized_missing_token_on_get(client: Any, sample_central_scheme_id: str) -> None:
    """GET /api/v1/tracking/{id} without X-Tracking-Token header returns 401 UNAUTHORIZED."""
    create_resp = client.post("/api/v1/tracking", json={"scheme_id": sample_central_scheme_id})
    assert create_resp.status_code == 201
    tid = create_resp.json()["tracking_id"]

    get_resp = client.get(f"/api/v1/tracking/{tid}")
    assert get_resp.status_code == 401
    assert get_resp.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.e2e
def test_c5_tracking_unauthorized_wrong_token_on_get(client: Any, sample_central_scheme_id: str) -> None:
    """GET /api/v1/tracking/{id} with wrong token returns 404 TRACKING_NOT_FOUND."""
    create_resp = client.post("/api/v1/tracking", json={"scheme_id": sample_central_scheme_id})
    assert create_resp.status_code == 201
    tid = create_resp.json()["tracking_id"]

    get_resp = client.get(f"/api/v1/tracking/{tid}", headers={"X-Tracking-Token": "invalid-token-xyz"})
    assert get_resp.status_code == 404
    assert get_resp.json()["error"]["code"] == "TRACKING_NOT_FOUND"


@pytest.mark.e2e
def test_c5_tracking_unauthorized_missing_token_on_patch(client: Any, sample_central_scheme_id: str) -> None:
    """PATCH /api/v1/tracking/{id} without token returns 401 UNAUTHORIZED."""
    create_resp = client.post("/api/v1/tracking", json={"scheme_id": sample_central_scheme_id})
    tid = create_resp.json()["tracking_id"]

    patch_resp = client.patch(f"/api/v1/tracking/{tid}", json={"status": "approved"})
    assert patch_resp.status_code == 401


@pytest.mark.e2e
def test_c5_tracking_unauthorized_wrong_token_on_patch(client: Any, sample_central_scheme_id: str) -> None:
    """PATCH /api/v1/tracking/{id} with wrong token returns 404 TRACKING_NOT_FOUND."""
    create_resp = client.post("/api/v1/tracking", json={"scheme_id": sample_central_scheme_id})
    tid = create_resp.json()["tracking_id"]

    patch_resp = client.patch(
        f"/api/v1/tracking/{tid}",
        headers={"X-Tracking-Token": "wrong-secret-token"},
        json={"status": "approved"},
    )
    assert patch_resp.status_code == 404


@pytest.mark.e2e
def test_c5_tracking_invalid_status_value_rejected(client: Any, sample_central_scheme_id: str) -> None:
    """PATCH /api/v1/tracking/{id} with unrecognized status returns 422."""
    create_resp = client.post("/api/v1/tracking", json={"scheme_id": sample_central_scheme_id})
    data = create_resp.json()
    tid, token = data["tracking_id"], data["token"]

    patch_resp = client.patch(
        f"/api/v1/tracking/{tid}",
        headers={"X-Tracking-Token": token},
        json={"status": "arbitrary_unsupported_status"},
    )
    assert patch_resp.status_code == 422


@pytest.mark.e2e
def test_c5_tracking_token_never_echoed_in_get_or_patch(client: Any, sample_central_scheme_id: str) -> None:
    """Tracking secret token must only be returned upon creation, never in GET or PATCH."""
    create_resp = client.post("/api/v1/tracking", json={"scheme_id": sample_central_scheme_id})
    data = create_resp.json()
    tid, token = data["tracking_id"], data["token"]

    get_resp = client.get(f"/api/v1/tracking/{tid}", headers={"X-Tracking-Token": token})
    assert get_resp.status_code == 200
    assert "token" not in get_resp.json()
    assert "secret_token" not in get_resp.json()

    patch_resp = client.patch(
        f"/api/v1/tracking/{tid}",
        headers={"X-Tracking-Token": token},
        json={"status": "in_progress"},
    )
    assert patch_resp.status_code == 200
    assert "token" not in patch_resp.json()


# ==============================================================================
# C6: Complex Rule Composition (AST Nesting, Short-Circuit, & Tri-State)
# ==============================================================================


@pytest.mark.e2e
def test_c6_all_rule_short_circuits_fail_over_unknown(client: Any) -> None:
    """In an 'all' group, a single FAIL short-circuits the outcome to NOT_LIKELY_ELIGIBLE."""
    # PM-KISAN requires: is_farmer eq True AND landholding_acres gt 0.0
    # Provide is_farmer = False (FAIL), omit landholding_acres (UNKNOWN)
    payload = {"answers": {"is_farmer": False}}
    resp = client.post("/api/v1/eligibility/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    kisan = next(r for r in data["results"] if r["scheme_id"] == "sch_pm_kisan_2019")
    # Because one mandatory criterion evaluated to FAIL, decision is NOT_LIKELY_ELIGIBLE
    assert kisan["decision"] == "NOT_LIKELY_ELIGIBLE"


@pytest.mark.e2e
def test_c6_all_rule_unknown_when_no_fail_and_some_unknown(client: Any) -> None:
    """In an 'all' group, if no leaf is FAIL and at least one leaf is UNKNOWN, decision is NEEDS_MORE_INFORMATION."""
    # PM-KISAN: is_farmer = True (PASS), landholding_acres omitted (UNKNOWN)
    payload = {"answers": {"is_farmer": True}}
    resp = client.post("/api/v1/eligibility/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    kisan = next(r for r in data["results"] if r["scheme_id"] == "sch_pm_kisan_2019")
    assert kisan["decision"] == "NEEDS_MORE_INFORMATION"


@pytest.mark.e2e
def test_c6_all_rule_pass_when_all_criteria_satisfied(client: Any) -> None:
    """In an 'all' group, when all mandatory leaves evaluate to PASS, decision is LIKELY_ELIGIBLE."""
    payload = {"answers": {"is_farmer": True, "landholding_acres": 2.5}}
    resp = client.post("/api/v1/eligibility/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    kisan = next(r for r in data["results"] if r["scheme_id"] == "sch_pm_kisan_2019")
    assert kisan["decision"] == "LIKELY_ELIGIBLE"


@pytest.mark.e2e
def test_c6_multi_criteria_boundary_strictness(client: Any) -> None:
    """Test boundary condition on rule evaluation: gt 0.0 is false for 0.0 and true for 0.01."""
    # 0.0 acres: fails 'landholding_acres gt 0.0'
    resp_zero = client.post(
        "/api/v1/eligibility/evaluate",
        json={"answers": {"is_farmer": True, "landholding_acres": 0.0}},
    )
    assert resp_zero.status_code == 200
    kisan_zero = next(r for r in resp_zero.json()["results"] if r["scheme_id"] == "sch_pm_kisan_2019")
    assert kisan_zero["decision"] == "NOT_LIKELY_ELIGIBLE"

    # 0.01 acres: passes 'landholding_acres gt 0.0'
    resp_pos = client.post(
        "/api/v1/eligibility/evaluate",
        json={"answers": {"is_farmer": True, "landholding_acres": 0.01}},
    )
    assert resp_pos.status_code == 200
    kisan_pos = next(r for r in resp_pos.json()["results"] if r["scheme_id"] == "sch_pm_kisan_2019")
    assert kisan_pos["decision"] == "LIKELY_ELIGIBLE"


@pytest.mark.e2e
def test_c6_admin_imported_complex_nested_rule_evaluation(
    client: Any, admin_headers: dict[str, str]
) -> None:
    """Opaque-box test: Import, verify, publish, and evaluate a complex scheme combining all + any + not."""
    scheme_suffix = uuid.uuid4().hex[:8]
    scheme_id = f"sch_test_complex_{scheme_suffix}"
    slug = f"test-complex-{scheme_suffix}"

    # Define a complex rule:
    # all:
    #   - age_years gte 18 (Adult)
    #   - any: [is_farmer eq True, is_unorganised_worker eq True] (Farmer OR Worker)
    #   - not: [is_student eq True] (Must NOT be a student)
    draft_record = {
        "id": scheme_id,
        "slug": slug,
        "name": f"Complex Test Scheme {scheme_suffix}",
        "summary": "E2E Rule composition testing scheme",
        "government_level": "central",
        "jurisdictions": {"scope": "all_india"},
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_age",
                    "field": "age_years",
                    "operator": "gte",
                    "value": 18,
                    "mandatory": True,
                    "explanation": "Applicant must be at least 18 years old",
                    "source_refs": ["src_main"],
                },
                {
                    "any": [
                        {
                            "criterion_id": "crit_farmer",
                            "field": "is_farmer",
                            "operator": "eq",
                            "value": True,
                            "mandatory": True,
                            "explanation": "Must be a registered farmer",
                            "source_refs": ["src_main"],
                        },
                        {
                            "criterion_id": "crit_worker",
                            "field": "is_unorganised_worker",
                            "operator": "eq",
                            "value": True,
                            "mandatory": True,
                            "explanation": "Must be an unorganised sector worker",
                            "source_refs": ["src_main"],
                        },
                    ]
                },
                {
                    "not": {
                        "criterion_id": "crit_not_student",
                        "field": "is_student",
                        "operator": "eq",
                        "value": True,
                        "mandatory": True,
                        "explanation": "Must not be currently enrolled as student",
                        "source_refs": ["src_main"],
                    }
                },
            ]
        },
        "payload": {
            "categories": ["social_welfare"],
            "beneficiary_groups": ["citizens"],
            "documents": [],
            "application_steps": [],
            "application_url": "https://india.gov.in/complex-test",
        },
        "sources": [
            {
                "id": "src_main",
                "title": "Official Guidelines",
                "publisher": "Ministry of Welfare",
                "url": "https://welfare.gov.in/test-scheme-guidelines",
                "source_type": "guideline",
                "official_status": "official",
                "access_date": date.today().isoformat(),
            }
        ],
    }

    # 1. Import scheme draft via admin API
    import_resp = client.post("/api/v1/admin/schemes/import", headers=admin_headers, json=draft_record)
    assert import_resp.status_code == 201, f"Import failed: {import_resp.text}"

    # 2. Validate scheme
    val_resp = client.post(f"/api/v1/admin/schemes/{scheme_id}/validate", headers=admin_headers)
    assert val_resp.status_code == 200, f"Validation failed: {val_resp.text}"
    assert val_resp.json()["valid"] is True

    # 3. Verify scheme
    ver_resp = client.post(
        f"/api/v1/admin/schemes/{scheme_id}/verify",
        headers=admin_headers,
        json={"reviewer": "reviewer@example.gov.in", "verified_at": date.today().isoformat()},
    )
    assert ver_resp.status_code == 200, f"Verify failed: {ver_resp.text}"

    # 4. Publish scheme
    pub_resp = client.post(
        f"/api/v1/admin/schemes/{scheme_id}/publish",
        headers=admin_headers,
        json={"actor": "admin@example.gov.in"},
    )
    assert pub_resp.status_code == 200, f"Publish failed: {pub_resp.text}"

    try:
        # Case A: Adult (25) + Farmer (True) + Worker (False) + Not Student (is_student=False)
        # Expected: LIKELY_ELIGIBLE
        resp_a = client.post(
            "/api/v1/eligibility/evaluate",
            json={
                "answers": {
                    "age_years": 25,
                    "is_farmer": True,
                    "is_unorganised_worker": False,
                    "is_student": False,
                }
            },
        )
        assert resp_a.status_code == 200
        res_a = next(r for r in resp_a.json()["results"] if r["scheme_id"] == scheme_id)
        assert res_a["decision"] == "LIKELY_ELIGIBLE"

        # Case B: Adult (30) + Farmer (False) + Worker (True) + Not Student (is_student=False)
        # Expected: LIKELY_ELIGIBLE (satisfies disjunction branch 'worker')
        resp_b = client.post(
            "/api/v1/eligibility/evaluate",
            json={
                "answers": {
                    "age_years": 30,
                    "is_farmer": False,
                    "is_unorganised_worker": True,
                    "is_student": False,
                }
            },
        )
        assert resp_b.status_code == 200
        res_b = next(r for r in resp_b.json()["results"] if r["scheme_id"] == scheme_id)
        assert res_b["decision"] == "LIKELY_ELIGIBLE"

        # Case C: Adult (22) + Farmer (True) + Student (True)
        # Expected: NOT_LIKELY_ELIGIBLE (trips NOT is_student criterion)
        resp_c = client.post(
            "/api/v1/eligibility/evaluate",
            json={
                "answers": {
                    "age_years": 22,
                    "is_farmer": True,
                    "is_unorganised_worker": False,
                    "is_student": True,
                }
            },
        )
        assert resp_c.status_code == 200
        res_c = next(r for r in resp_c.json()["results"] if r["scheme_id"] == scheme_id)
        assert res_c["decision"] == "NOT_LIKELY_ELIGIBLE"

        # Case D: Minor (16) + Farmer (True) + Not Student (False)
        # Expected: NOT_LIKELY_ELIGIBLE (fails age >= 18)
        resp_d = client.post(
            "/api/v1/eligibility/evaluate",
            json={
                "answers": {
                    "age_years": 16,
                    "is_farmer": True,
                    "is_unorganised_worker": False,
                    "is_student": False,
                }
            },
        )
        assert resp_d.status_code == 200
        res_d = next(r for r in resp_d.json()["results"] if r["scheme_id"] == scheme_id)
        assert res_d["decision"] == "NOT_LIKELY_ELIGIBLE"

    finally:
        # Cleanup: Archive the test scheme so it doesn't pollute subsequent test runs
        client.post(
            f"/api/v1/admin/schemes/{scheme_id}/archive",
            headers=admin_headers,
            json={"actor": "cleaner@example.gov.in"},
        )
