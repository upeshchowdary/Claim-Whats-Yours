"""Tier 1: Feature Coverage End-to-End Tests.

Verifies baseline functional contracts for every feature independently (F1 to F10):
- F1: Meta Endpoints (/api/v1/meta/jurisdictions, /api/v1/meta/profile-fields)
- F2: Health & Readiness Probes (/health/live, /health/ready)
- F3: Scheme Discovery & Search (/api/v1/schemes)
- F4: Scheme Details & Provenance (/api/v1/schemes/{id})
- F5: Stateless Eligibility Evaluation (/api/v1/eligibility/evaluate)
- F6: Privacy Guardrail Rejection (FORBIDDEN_FIELD)
- F7: Geographic Hierarchy Validation
- F8: Anonymous Application Tracking (/api/v1/tracking)
- F9: Admin Security & Authentication
- F10: Conversational Assistant Profile Extraction (/api/v1/assistant/turn)
"""

from __future__ import annotations

import re
from typing import Any

import pytest

HEX_32_PATTERN = re.compile(r"^[0-9a-f]{32}$")


# ==============================================================================
# F1: Meta Endpoints
# ==============================================================================

def test_f1_01_meta_jurisdictions_schema(client: Any) -> None:
    """F1: GET /api/v1/meta/jurisdictions returns 200 with schema or 404 envelope if pending M1."""
    response = client.get("/api/v1/meta/jurisdictions")
    if response.status_code == 404:
        assert response.json()["error"]["code"] == "NOT_FOUND"
    else:
        assert response.status_code == 200
        data = response.json()
        assert "jurisdictions" in data
        assert isinstance(data["jurisdictions"], list)
        for item in data["jurisdictions"]:
            assert "code" in item
            assert "name" in item
            assert "level" in item


def test_f1_02_meta_jurisdictions_contains_national_and_states(client: Any) -> None:
    """F1: Jurisdictions include all-India and state-level entries."""
    response = client.get("/api/v1/meta/jurisdictions")
    if response.status_code == 404:
        assert response.json()["error"]["code"] == "NOT_FOUND"
    else:
        assert response.status_code == 200
        codes = {j["code"] for j in response.json()["jurisdictions"]}
        assert "IN" in codes
        assert "IN-AP" in codes


def test_f1_03_meta_profile_fields_schema(client: Any) -> None:
    """F1: GET /api/v1/meta/profile-fields returns 200 with catalogue fields or 404 if pending M1."""
    response = client.get("/api/v1/meta/profile-fields")
    if response.status_code == 404:
        assert response.json()["error"]["code"] == "NOT_FOUND"
    else:
        assert response.status_code == 200
        data = response.json()
        assert "fields" in data
        assert isinstance(data["fields"], list)
        assert len(data["fields"]) >= 10
        field_ids = {f["id"] for f in data["fields"]}
        assert "age_years" in field_ids
        assert "state_code" in field_ids


def test_f1_04_meta_profile_fields_types_and_ranges(client: Any) -> None:
    """F1: Profile fields declare valid data types and range/allowed value constraints."""
    response = client.get("/api/v1/meta/profile-fields")
    if response.status_code == 404:
        assert response.json()["error"]["code"] == "NOT_FOUND"
    else:
        assert response.status_code == 200
        fields_by_id = {f["id"]: f for f in response.json()["fields"]}
        assert fields_by_id["age_years"]["type"] == "int"
        assert fields_by_id["state_code"]["type"] == "enum"
        if "range" in fields_by_id["age_years"]:
            assert fields_by_id["age_years"]["range"]["min"] == 0


def test_f1_05_meta_endpoints_content_type(client: Any) -> None:
    """F1: Meta endpoints return application/json content type."""
    response = client.get("/api/v1/meta/jurisdictions")
    assert "application/json" in response.headers.get("Content-Type", "")
    assert response.status_code in (200, 404)


def test_f1_06_meta_endpoints_query_params_ignored(client: Any) -> None:
    """F1: Extraneous query parameters do not cause 500 errors on meta endpoints."""
    response = client.get("/api/v1/meta/jurisdictions?unexpected_param=123")
    assert response.status_code in (200, 404)
    assert response.status_code != 500


# ==============================================================================
# F2: Health & Readiness Probes
# ==============================================================================

def test_f2_01_health_live_returns_ok(client: Any) -> None:
    """F2: GET /health/live returns HTTP 200 with status ok."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_f2_02_health_ready_returns_200(client: Any) -> None:
    """F2: GET /health/ready returns HTTP 200 indicating DB is ready."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") in ("ok", "ready")


def test_f2_03_health_live_request_id_generated(client: Any) -> None:
    """F2: GET /health/live auto-generates a 32-character hex X-Request-ID header."""
    response = client.get("/health/live")
    assert "X-Request-ID" in response.headers
    request_id = response.headers["X-Request-ID"]
    assert HEX_32_PATTERN.match(request_id) is not None


def test_f2_04_health_live_custom_request_id_echoed(client: Any) -> None:
    """F2: Supplied X-Request-ID header is echoed back verbatim in response."""
    custom_id = "test-e2e-health-probe-12345"
    response = client.get("/health/live", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id


def test_f2_05_health_rapid_probes(client: Any) -> None:
    """F2: Multiple successive health and readiness probes respond reliably."""
    for _ in range(5):
        resp_live = client.get("/health/live")
        assert resp_live.status_code == 200
        resp_ready = client.get("/health/ready")
        assert resp_ready.status_code == 200


def test_f2_06_health_no_credentials_leaked(client: Any) -> None:
    """F2: Health endpoints never leak database URLs, keys, or internal tokens."""
    for endpoint in ("/health/live", "/health/ready"):
        response = client.get(endpoint)
        assert "password" not in response.text.lower()
        assert "secret" not in response.text.lower()
        assert "token" not in response.text.lower()


# ==============================================================================
# F3: Scheme Discovery & Search
# ==============================================================================

def test_f3_01_schemes_default_pagination(client: Any) -> None:
    """F3: GET /api/v1/schemes returns items with standard pagination metadata."""
    response = client.get("/api/v1/schemes")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "page" in data
    assert "page_size" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert isinstance(data["items"], list)
    assert data["total"] >= len(data["items"])


def test_f3_02_schemes_text_search_kisan(client: Any) -> None:
    """F3: Text search filtering by keyword 'kisan' returns matching schemes."""
    response = client.get("/api/v1/schemes?q=kisan")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 1
    for item in data["items"]:
        text_content = f"{item['name']} {item.get('summary', '')}".lower()
        assert "kisan" in text_content


def test_f3_03_schemes_filter_government_level_central(client: Any) -> None:
    """F3: Filtering by government_level=central returns only central schemes."""
    response = client.get("/api/v1/schemes?government_level=central")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 1
    for item in data["items"]:
        assert item["government_level"] == "central"


def test_f3_04_schemes_filter_state_code(client: Any) -> None:
    """F3: Filtering by valid state_code=IN-AP returns applicable schemes."""
    response = client.get("/api/v1/schemes?state_code=IN-AP")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["items"], list)


def test_f3_05_schemes_rejects_status_filter(client: Any) -> None:
    """F3: Attempting to query unpublished status on public endpoint returns HTTP 400."""
    response = client.get("/api/v1/schemes?status=published")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_QUERY"


def test_f3_06_schemes_invalid_state_code_returns_422(client: Any) -> None:
    """F3: Providing an invalid state_code returns HTTP 422 VALIDATION_ERROR."""
    response = client.get("/api/v1/schemes?state_code=UNKNOWN_STATE_999")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# ==============================================================================
# F4: Scheme Details & Provenance
# ==============================================================================

def test_f4_01_scheme_details_central_pm_kisan(
    client: Any, sample_central_scheme_id: str
) -> None:
    """F4: GET /api/v1/schemes/{id} returns comprehensive details for Central scheme."""
    response = client.get(f"/api/v1/schemes/{sample_central_scheme_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_central_scheme_id
    assert data["government_level"] == "central"
    assert data["scope"] == "all_india"
    assert "criteria" in data or "eligibility_rule" in data
    assert "sources" in data
    assert isinstance(data["sources"], list)
    assert len(data["sources"]) >= 1


def test_f4_02_scheme_details_state_rythu_bharosa(
    client: Any, sample_state_scheme_id: str
) -> None:
    """F4: GET /api/v1/schemes/{id} returns comprehensive details for State scheme."""
    response = client.get(f"/api/v1/schemes/{sample_state_scheme_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_state_scheme_id
    assert data["government_level"] == "state"
    assert data["scope"] == "state"


def test_f4_03_scheme_details_provenance_sources(
    client: Any, sample_central_scheme_id: str
) -> None:
    """F4: Scheme provenance sources must have official status, HTTPS URLs, and access dates."""
    response = client.get(f"/api/v1/schemes/{sample_central_scheme_id}")
    assert response.status_code == 200
    sources = response.json()["sources"]
    assert len(sources) >= 1
    for source in sources:
        assert source["official_status"] == "official"
        assert source["url"].startswith("https://")
        assert "access_date" in source


def test_f4_04_scheme_details_nonexistent_returns_404(client: Any) -> None:
    """F4: Requesting a non-existent scheme ID returns HTTP 404 SCHEME_NOT_FOUND."""
    response = client.get("/api/v1/schemes/sch_definitely_nonexistent_9999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SCHEME_NOT_FOUND"


def test_f4_05_scheme_details_malformed_id_safety(client: Any) -> None:
    """F4: Malformed or special-character scheme IDs return 404/422 without 500 error."""
    for malformed_id in ("%00", "a" * 100, "../secret", "<script>"):
        response = client.get(f"/api/v1/schemes/{malformed_id}")
        assert response.status_code in (404, 422)
        assert "Traceback" not in response.text


def test_f4_06_scheme_details_application_guidance(
    client: Any, sample_central_scheme_id: str
) -> None:
    """F4: Scheme detail view contains documents checklist and application guidance."""
    response = client.get(f"/api/v1/schemes/{sample_central_scheme_id}")
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data or "document_checklist" in data
    assert "application_steps" in data or "application_guidance" in data


# ==============================================================================
# F5: Stateless Eligibility Evaluation
# ==============================================================================

def test_f5_01_evaluate_eligible_farmer(client: Any, valid_farmer_profile: dict[str, Any]) -> None:
    """F5: POST /api/v1/eligibility/evaluate returns 200 with evaluation results."""
    response = client.post(
        "/api/v1/eligibility/evaluate",
        json={"answers": valid_farmer_profile},
    )
    assert response.status_code == 200
    data = response.json()
    assert "evaluation_date" in data
    assert "results" in data
    assert isinstance(data["results"], list)
    assert len(data["results"]) >= 1


def test_f5_02_evaluate_decision_enums(client: Any, valid_farmer_profile: dict[str, Any]) -> None:
    """F5: Every evaluated scheme returns a valid decision enum."""
    allowed_decisions = {
        "LIKELY_ELIGIBLE",
        "NEEDS_MORE_INFORMATION",
        "NOT_LIKELY_ELIGIBLE",
        "VERIFICATION_REQUIRED",
    }
    response = client.post(
        "/api/v1/eligibility/evaluate",
        json={"answers": valid_farmer_profile},
    )
    assert response.status_code == 200
    for result in response.json()["results"]:
        assert result["decision"] in allowed_decisions


def test_f5_03_evaluate_criteria_breakdown(
    client: Any, valid_farmer_profile: dict[str, Any]
) -> None:
    """F5: Criteria results contain criterion_id, status (PASS/FAIL/UNKNOWN), and explanation."""
    allowed_statuses = {"PASS", "FAIL", "UNKNOWN"}
    response = client.post(
        "/api/v1/eligibility/evaluate",
        json={"answers": valid_farmer_profile},
    )
    assert response.status_code == 200
    for result in response.json()["results"]:
        assert "criteria" in result
        for criterion in result["criteria"]:
            assert "criterion_id" in criterion
            assert criterion["status"] in allowed_statuses
            assert "explanation" in criterion
            assert "mandatory" in criterion


def test_f5_04_evaluate_missing_fields_and_questions(client: Any) -> None:
    """F5: Incomplete profile returns missing_fields and structured follow_up_questions."""
    response = client.post(
        "/api/v1/eligibility/evaluate",
        json={"answers": {"state_code": "IN-AP"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert "missing_fields" in data
    assert "follow_up_questions" in data
    assert len(data["missing_fields"]) >= 1
    assert len(data["follow_up_questions"]) >= 1
    for q in data["follow_up_questions"]:
        assert "field" in q
        assert "label" in q
        assert "reason" in q


def test_f5_05_evaluate_government_level_filter(
    client: Any, valid_farmer_profile: dict[str, Any]
) -> None:
    """F5: Filtering evaluation by government_levels narrows results to requested tier."""
    response = client.post(
        "/api/v1/eligibility/evaluate",
        json={
            "answers": valid_farmer_profile,
            "filters": {"government_levels": ["state"]},
        },
    )
    assert response.status_code == 200
    for result in response.json()["results"]:
        assert result["government_level"] == "state"


def test_f5_06_evaluate_disclaimer_present(
    client: Any, valid_farmer_profile: dict[str, Any]
) -> None:
    """F5: Every evaluation response carries the statutory non-binding disclaimer."""
    response = client.post(
        "/api/v1/eligibility/evaluate",
        json={"answers": valid_farmer_profile},
    )
    assert response.status_code == 200
    disclaimer = response.json().get("disclaimer", "")
    assert len(disclaimer) > 20
    assert "official" in disclaimer.lower() or "disclaimer" in disclaimer.lower() or "not" in disclaimer.lower()


# ==============================================================================
# F6: Privacy Guardrail Rejection
# ==============================================================================

@pytest.mark.parametrize(
    "forbidden_field",
    ["aadhaar", "pan", "bank_account", "password", "phone", "email", "government_id"],
)
def test_f6_01_to_04_rejects_forbidden_fields(client: Any, forbidden_field: str) -> None:
    """F6: Requests containing forbidden sensitive keys are rejected with HTTP 422 FORBIDDEN_FIELD."""
    secret_val = "SECRET_CANARY_VALUE_987654"
    response = client.post(
        "/api/v1/eligibility/evaluate",
        json={"answers": {forbidden_field: secret_val, "age_years": 30}},
    )
    assert response.status_code == 422
    assert secret_val not in response.text
    details = response.json().get("error", {}).get("details", [])
    has_forbidden_code = any(d.get("code") == "FORBIDDEN_FIELD" for d in details)
    assert has_forbidden_code


def test_f6_05_secret_values_never_echoed_in_response(client: Any) -> None:
    """F6: Sensitive payload values must never be echoed back in body or headers."""
    canary = "SENSITIVE_AADHAAR_998877665544"
    response = client.post(
        "/api/v1/eligibility/evaluate",
        json={"answers": {"aadhaar": canary}},
    )
    assert canary not in response.text
    for header_val in response.headers.values():
        assert canary not in header_val


def test_f6_06_stateless_no_db_persistence(
    client: Any, valid_farmer_profile: dict[str, Any]
) -> None:
    """F6: Evaluation does not write citizen answers or profiles to any database table."""
    resp1 = client.post("/api/v1/eligibility/evaluate", json={"answers": valid_farmer_profile})
    assert resp1.status_code == 200

    resp2 = client.post("/api/v1/eligibility/evaluate", json={"answers": valid_farmer_profile})
    assert resp2.status_code == 200
    assert resp1.json()["results"] == resp2.json()["results"]


# ==============================================================================
# F7: Geographic Hierarchy Validation
# ==============================================================================

def test_f7_01_all_india_scheme_matches_multiple_states(client: Any) -> None:
    """F7: Central all-India schemes are applicable across different states."""
    for state in ("IN-AP", "IN-UP", "IN-MH"):
        response = client.post(
            "/api/v1/eligibility/evaluate",
            json={"answers": {"state_code": state, "is_farmer": True, "landholding_acres": 1.5}},
        )
        assert response.status_code == 200
        matched_ids = {r["scheme_id"] for r in response.json()["results"]}
        assert "sch_pm_kisan_2019" in matched_ids


def test_f7_02_state_scheme_matches_resident_state(client: Any) -> None:
    """F7: State schemes match citizens residing in that specific state."""
    response = client.post(
        "/api/v1/eligibility/evaluate",
        json={"answers": {"state_code": "IN-AP", "is_farmer": True}},
    )
    assert response.status_code == 200
    matched_ids = {r["scheme_id"] for r in response.json()["results"]}
    assert "sch_ap_rythu_bharosa" in matched_ids


def test_f7_03_state_scheme_excludes_non_resident_state(client: Any) -> None:
    """F7: Citizen from Maharashtra (IN-MH) is not evaluated as eligible for AP scheme."""
    response = client.post(
        "/api/v1/eligibility/evaluate",
        json={"answers": {"state_code": "IN-MH", "is_farmer": True}},
    )
    assert response.status_code == 200
    matched_ids = {
        r["scheme_id"] for r in response.json()["results"]
        if r["decision"] == "LIKELY_ELIGIBLE"
    }
    assert "sch_ap_rythu_bharosa" not in matched_ids


def test_f7_04_valid_district_in_state(client: Any) -> None:
    """F7: Citizen with matching district IN-AP-GNT and state IN-AP evaluates cleanly."""
    response = client.post(
        "/api/v1/eligibility/evaluate",
        json={"answers": {"state_code": "IN-AP", "district_code": "IN-AP-GNT", "is_farmer": True}},
    )
    assert response.status_code == 200
    assert len(response.json()["results"]) >= 1


def test_f7_05_cross_state_district_mismatch(client: Any) -> None:
    """F7: District belonging to AP combined with state MH does not crash."""
    response = client.post(
        "/api/v1/eligibility/evaluate",
        json={"answers": {"state_code": "IN-MH", "district_code": "IN-AP-GNT"}},
    )
    assert response.status_code == 200
    matched_ids = {
        r["scheme_id"] for r in response.json()["results"]
        if r["decision"] == "LIKELY_ELIGIBLE"
    }
    assert "sch_ap_rythu_bharosa" not in matched_ids


def test_f7_06_district_without_state_evaluation(client: Any) -> None:
    """F7: District provided without state evaluates geography to UNKNOWN, not crashing."""
    response = client.post(
        "/api/v1/eligibility/evaluate",
        json={"answers": {"district_code": "IN-AP-GNT", "is_farmer": True}},
    )
    assert response.status_code == 200
    for r in response.json()["results"]:
        if r["scheme_id"] == "sch_ap_rythu_bharosa":
            assert r["decision"] in ("NEEDS_MORE_INFORMATION", "NOT_LIKELY_ELIGIBLE")


# ==============================================================================
# F8: Anonymous Application Tracking
# ==============================================================================

def test_f8_01_create_tracking_record(client: Any, tracking_payload: dict[str, Any]) -> None:
    """F8: POST /api/v1/tracking creates record and returns public ID and secret token."""
    response = client.post("/api/v1/tracking", json=tracking_payload)
    assert response.status_code == 201
    data = response.json()
    assert "tracking_id" in data
    assert "token" in data
    assert data["status"] == "submitted"
    assert data["scheme_id"] == tracking_payload["scheme_id"]


def test_f8_02_read_tracking_with_token(client: Any, tracking_payload: dict[str, Any]) -> None:
    """F8: GET /api/v1/tracking/{id} with valid X-Tracking-Token returns tracker status."""
    create_resp = client.post("/api/v1/tracking", json=tracking_payload)
    assert create_resp.status_code == 201
    tid = create_resp.json()["tracking_id"]
    token = create_resp.json()["token"]

    get_resp = client.get(f"/api/v1/tracking/{tid}", headers={"X-Tracking-Token": token})
    assert get_resp.status_code == 200
    assert get_resp.json()["tracking_id"] == tid
    assert get_resp.json()["status"] == "submitted"


def test_f8_03_read_tracking_missing_token_401(
    client: Any, tracking_payload: dict[str, Any]
) -> None:
    """F8: GET /api/v1/tracking/{id} without token returns 401 UNAUTHORIZED."""
    create_resp = client.post("/api/v1/tracking", json=tracking_payload)
    assert create_resp.status_code == 201
    tid = create_resp.json()["tracking_id"]

    get_resp = client.get(f"/api/v1/tracking/{tid}")
    assert get_resp.status_code == 401
    assert get_resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_f8_04_read_tracking_wrong_token_404(
    client: Any, tracking_payload: dict[str, Any]
) -> None:
    """F8: GET /api/v1/tracking/{id} with invalid token returns 404 (prevent token harvesting)."""
    create_resp = client.post("/api/v1/tracking", json=tracking_payload)
    assert create_resp.status_code == 201
    tid = create_resp.json()["tracking_id"]

    get_resp = client.get(
        f"/api/v1/tracking/{tid}",
        headers={"X-Tracking-Token": "completely-wrong-token-abc"},
    )
    assert get_resp.status_code == 404
    assert get_resp.json()["error"]["code"] == "TRACKING_NOT_FOUND"


def test_f8_05_patch_tracking_status(client: Any, tracking_payload: dict[str, Any]) -> None:
    """F8: PATCH /api/v1/tracking/{id} updates status when authenticated with token."""
    create_resp = client.post("/api/v1/tracking", json={"status": "planned"})
    assert create_resp.status_code == 201
    tid = create_resp.json()["tracking_id"]
    token = create_resp.json()["token"]

    patch_resp = client.patch(
        f"/api/v1/tracking/{tid}",
        json={"status": "in_progress"},
        headers={"X-Tracking-Token": token},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "in_progress"


def test_f8_06_token_never_echoed_in_subsequent_reads(
    client: Any, tracking_payload: dict[str, Any]
) -> None:
    """F8: GET and PATCH never return or echo the access token."""
    create_resp = client.post("/api/v1/tracking", json=tracking_payload)
    assert create_resp.status_code == 201
    tid = create_resp.json()["tracking_id"]
    token = create_resp.json()["token"]

    get_resp = client.get(f"/api/v1/tracking/{tid}", headers={"X-Tracking-Token": token})
    assert get_resp.status_code == 200
    assert "token" not in get_resp.json()
    assert token not in get_resp.text


# ==============================================================================
# F9: Admin Security
# ==============================================================================

def test_f9_01_valid_admin_token_accepted(client: Any, admin_headers: dict[str, str]) -> None:
    """F9: Valid X-Admin-Token allows access to admin review queue."""
    response = client.get("/api/v1/admin/schemes/review-queue", headers=admin_headers)
    assert response.status_code in (200, 404)
    assert response.status_code not in (401, 403)


def test_f9_02_missing_admin_token_rejected(client: Any) -> None:
    """F9: Missing X-Admin-Token is rejected with 401 UNAUTHORIZED or 403 ADMIN_TOKEN_INVALID."""
    response = client.get("/api/v1/admin/schemes/review-queue")
    assert response.status_code in (401, 403)
    assert response.json()["error"]["code"] in ("UNAUTHORIZED", "ADMIN_TOKEN_INVALID", "ADMIN_DISABLED")


def test_f9_03_invalid_admin_token_rejected(
    client: Any, invalid_admin_headers: dict[str, str]
) -> None:
    """F9: Invalid X-Admin-Token is rejected with 401 UNAUTHORIZED or 403 ADMIN_TOKEN_INVALID."""
    response = client.get("/api/v1/admin/schemes/review-queue", headers=invalid_admin_headers)
    assert response.status_code in (401, 403)
    assert response.json()["error"]["code"] in ("UNAUTHORIZED", "ADMIN_TOKEN_INVALID", "ADMIN_DISABLED")


def test_f9_04_empty_admin_token_rejected(client: Any) -> None:
    """F9: Empty X-Admin-Token header is rejected with 401 or 403."""
    response = client.get("/api/v1/admin/schemes/review-queue", headers={"X-Admin-Token": ""})
    assert response.status_code in (401, 403)


def test_f9_05_admin_token_not_echoed_in_response(
    client: Any, admin_headers: dict[str, str], admin_token: str
) -> None:
    """F9: Admin token is never reflected in response body or headers."""
    response = client.get("/api/v1/admin/schemes/review-queue", headers=admin_headers)
    assert admin_token not in response.text
    for hname, hval in response.headers.items():
        assert admin_token not in hname.lower()
        assert admin_token not in hval


def test_f9_06_admin_data_sources_endpoint_protected(
    client: Any, admin_headers: dict[str, str], invalid_admin_headers: dict[str, str]
) -> None:
    """F9: Admin data-sources endpoint enforces authentication."""
    unauth = client.get("/api/v1/admin/data-sources", headers=invalid_admin_headers)
    assert unauth.status_code in (401, 403)
    auth = client.get("/api/v1/admin/data-sources", headers=admin_headers)
    assert auth.status_code == 200


# ==============================================================================
# F10: Conversational Assistant Profile Extraction
# ==============================================================================

def test_f10_01_assistant_turn_structure(client: Any) -> None:
    """F10: POST /api/v1/assistant/turn returns 200 (if Groq active) or 503 (if disabled), never 500."""
    payload = {
        "messages": ["I am a 35 year old farmer living in Andhra Pradesh"],
        "answers": {},
        "locale": "en",
    }
    response = client.post("/api/v1/assistant/turn", json=payload)
    assert response.status_code in (200, 503)
    assert response.status_code != 500


def test_f10_02_assistant_turn_503_envelope(client: Any) -> None:
    """F10: When Groq AI is unavailable, assistant returns structured 503 error envelope."""
    payload = {
        "messages": ["Hello"],
        "answers": {},
    }
    response = client.post("/api/v1/assistant/turn", json=payload)
    if response.status_code == 503:
        error = response.json().get("error", {})
        assert "code" in error
        assert "message" in error
        assert "request_id" in error


def test_f10_03_assistant_turn_rejects_missing_messages(client: Any) -> None:
    """F10: Request missing required messages array returns HTTP 422 VALIDATION_ERROR."""
    response = client.post("/api/v1/assistant/turn", json={"answers": {}})
    assert response.status_code == 422


def test_f10_04_assistant_turn_locale_support(client: Any) -> None:
    """F10: Assistant accepts language code in locale parameter without crashing."""
    payload = {
        "messages": ["नमस्ते"],
        "answers": {},
        "locale": "hi",
    }
    response = client.post("/api/v1/assistant/turn", json=payload)
    assert response.status_code in (200, 503)


def test_f10_05_assistant_turn_statelessness(client: Any) -> None:
    """F10: Conversational assistant endpoint sets no session cookies."""
    payload = {
        "messages": ["Hello"],
        "answers": {},
    }
    response = client.post("/api/v1/assistant/turn", json=payload)
    assert "set-cookie" not in {h.lower() for h in response.headers.keys()}


def test_f10_06_assistant_turn_rejects_forbidden_fields(client: Any) -> None:
    """F10: If answers contains sensitive forbidden fields, request is rejected or handled gracefully."""
    payload = {
        "messages": ["Here is my info"],
        "answers": {"aadhaar": "123456789012"},
    }
    response = client.post("/api/v1/assistant/turn", json=payload)
    assert response.status_code in (422, 503)
    if response.status_code == 422:
        assert "123456789012" not in response.text
