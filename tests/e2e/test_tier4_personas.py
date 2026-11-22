"""Tier 4: Real-World Citizen Workload Scenarios (The 10 Citizen Personas).

End-to-end evaluation journeys for the 10 diverse citizen personas synthesized
during Step 0 Domain Research & Specification Mining:
- Persona 1: Ramesh Kumar (Marginal Farmer, AP, Guntur)
- Persona 2: Sunita Devi (Urban Street Vendor, UP, Lucknow)
- Persona 3: Priya Sharma (Low-Income Student, MH, Pune)
- Persona 4: Ramappa K (Destitute Elderly Farmer, KA, Raichur)
- Persona 5: Ananya Das (Divorced Handloom Artisan, WB, Nadia)
- Persona 6: Gurpreet Singh (Commercial Landowner & Taxpayer, PB, Ludhiana)
- Persona 7: Lakshmi Bai (Tenant Cultivator with CCRC, AP, Prakasam)
- Persona 8: Mohammed Farhan (Disabled Unemployed Youth, TG, Hyderabad)
- Persona 9: Baby Meera / Parent (Girl Child, RJ, Jaipur)
- Persona 10: Incomplete Boundary Citizen (Partial Answers & Progressive Follow-up)

Plus end-to-end multi-step journeys (evaluation -> details -> tracking -> updates)
and cross-persona HTTP response contract and coverage validation.

Opaque-box design: Tests interact exclusively with public HTTP endpoints.
"""

from __future__ import annotations

from typing import Any

import pytest

VALID_DECISIONS = {
    "LIKELY_ELIGIBLE",
    "NEEDS_MORE_INFORMATION",
    "NOT_LIKELY_ELIGIBLE",
    "VERIFICATION_REQUIRED",
}


# ==============================================================================
# 10 Citizen Persona Evaluation Tests
# ==============================================================================


@pytest.mark.e2e
def test_persona_1_ramesh_kumar_marginal_farmer_ap(client: Any) -> None:
    """Persona 1: Ramesh Kumar — Marginal Farmer, AP, Guntur.

    Expected:
    - PM-KISAN: LIKELY_ELIGIBLE (is_farmer=True, landholding_acres > 0)
    - AP Rythu Bharosa: LIKELY_ELIGIBLE (resident in AP, is_farmer=True)
    - PM SVANidhi: NOT_LIKELY_ELIGIBLE (is_unorganised_worker=False)
    - missing_fields: empty list
    - Document checklist returned for both eligible schemes
    """
    profile = {
        "state_code": "IN-AP",
        "district_code": "IN-AP-GNT",
        "residence": "rural",
        "age_years": 42,
        "gender": "male",
        "social_category": "obc",
        "occupation": "farmer",
        "is_farmer": True,
        "landholding_acres": 2.2,
        "annual_household_income_inr": 110000,
        "family_size": 4,
        "marital_status": "married",
        "is_unorganised_worker": False,
    }
    resp = client.post("/api/v1/eligibility/evaluate", json={"answers": profile})
    assert resp.status_code == 200, f"Evaluation failed: {resp.text}"
    data = resp.json()

    # Structural conformance
    assert "evaluation_date" in data
    assert "results" in data
    assert "missing_fields" in data
    assert "follow_up_questions" in data
    assert "disclaimer" in data
    assert len(data["disclaimer"]) > 0

    results_by_id = {r["scheme_id"]: r for r in data["results"]}

    # PM-KISAN
    assert "sch_pm_kisan_2019" in results_by_id
    assert results_by_id["sch_pm_kisan_2019"]["decision"] == "LIKELY_ELIGIBLE"
    assert results_by_id["sch_pm_kisan_2019"]["government_level"] == "central"
    assert "document_checklist" in results_by_id["sch_pm_kisan_2019"]

    # AP Rythu Bharosa
    assert "sch_ap_rythu_bharosa" in results_by_id
    assert results_by_id["sch_ap_rythu_bharosa"]["decision"] == "LIKELY_ELIGIBLE"
    assert results_by_id["sch_ap_rythu_bharosa"]["government_level"] == "state"

    # PM SVANidhi
    assert "sch_pm_svanidhi" in results_by_id
    assert results_by_id["sch_pm_svanidhi"]["decision"] == "NOT_LIKELY_ELIGIBLE"

    # Fully answered profile
    assert data["missing_fields"] == []
    assert data["follow_up_questions"] == []


@pytest.mark.e2e
def test_persona_2_sunita_devi_urban_street_vendor_up(client: Any) -> None:
    """Persona 2: Sunita Devi — Urban Street Vendor, UP, Lucknow.

    Expected:
    - PM SVANidhi: LIKELY_ELIGIBLE (is_unorganised_worker=True, age 38 >= 18)
    - PM-KISAN: NOT_LIKELY_ELIGIBLE (is_farmer=False, landholding_acres=0.0)
    - AP Rythu Bharosa: Excluded by geography (state is IN-UP, not IN-AP)
    """
    profile = {
        "state_code": "IN-UP",
        "residence": "urban",
        "age_years": 38,
        "gender": "female",
        "social_category": "sc",
        "occupation": "self_employed",
        "is_unorganised_worker": True,
        "is_farmer": False,
        "landholding_acres": 0.0,
        "annual_household_income_inr": 85000,
        "family_size": 5,
        "marital_status": "married",
    }
    resp = client.post("/api/v1/eligibility/evaluate", json={"answers": profile})
    assert resp.status_code == 200
    data = resp.json()

    results_by_id = {r["scheme_id"]: r for r in data["results"]}

    # PM SVANidhi matches
    assert "sch_pm_svanidhi" in results_by_id
    assert results_by_id["sch_pm_svanidhi"]["decision"] == "LIKELY_ELIGIBLE"

    # PM-KISAN does not match
    assert "sch_pm_kisan_2019" in results_by_id
    assert results_by_id["sch_pm_kisan_2019"]["decision"] == "NOT_LIKELY_ELIGIBLE"

    # AP State scheme must be completely excluded
    assert "sch_ap_rythu_bharosa" not in results_by_id


@pytest.mark.e2e
def test_persona_3_priya_sharma_low_income_student_mh(client: Any) -> None:
    """Persona 3: Priya Sharma — Low-Income College Student, MH, Pune.

    Expected:
    - PM-KISAN: NOT_LIKELY_ELIGIBLE (not a farmer)
    - PM SVANidhi: NOT_LIKELY_ELIGIBLE (not an unorganised worker)
    - AP Rythu Bharosa: Excluded by geography (MH != AP)
    """
    profile = {
        "state_code": "IN-MH",
        "residence": "urban",
        "age_years": 19,
        "gender": "female",
        "social_category": "ews",
        "occupation": "student",
        "is_student": True,
        "education_level": "higher_secondary",
        "annual_household_income_inr": 140000,
        "family_size": 4,
        "marital_status": "single",
        "is_farmer": False,
        "is_unorganised_worker": False,
    }
    resp = client.post("/api/v1/eligibility/evaluate", json={"answers": profile})
    assert resp.status_code == 200
    data = resp.json()

    results_by_id = {r["scheme_id"]: r for r in data["results"]}
    assert "sch_pm_kisan_2019" in results_by_id
    assert results_by_id["sch_pm_kisan_2019"]["decision"] == "NOT_LIKELY_ELIGIBLE"

    assert "sch_pm_svanidhi" in results_by_id
    assert results_by_id["sch_pm_svanidhi"]["decision"] == "NOT_LIKELY_ELIGIBLE"

    assert "sch_ap_rythu_bharosa" not in results_by_id


@pytest.mark.e2e
def test_persona_4_ramappa_k_destitute_elderly_farmer_ka(client: Any) -> None:
    """Persona 4: Ramappa K — Destitute Elderly Farmer, KA, Raichur.

    Expected:
    - PM-KISAN: LIKELY_ELIGIBLE (farmer with 0.75 acres dryland)
    - AP Rythu Bharosa: Excluded by geography (KA != AP)
    - PM SVANidhi: NOT_LIKELY_ELIGIBLE
    """
    profile = {
        "state_code": "IN-KA",
        "residence": "rural",
        "age_years": 68,
        "gender": "male",
        "social_category": "st",
        "occupation": "farmer",
        "is_farmer": True,
        "landholding_acres": 0.75,
        "annual_household_income_inr": 32000,
        "family_size": 1,
        "marital_status": "widowed",
        "is_unorganised_worker": False,
    }
    resp = client.post("/api/v1/eligibility/evaluate", json={"answers": profile})
    assert resp.status_code == 200
    data = resp.json()

    results_by_id = {r["scheme_id"]: r for r in data["results"]}
    assert "sch_pm_kisan_2019" in results_by_id
    assert results_by_id["sch_pm_kisan_2019"]["decision"] == "LIKELY_ELIGIBLE"

    assert "sch_ap_rythu_bharosa" not in results_by_id
    assert "sch_pm_svanidhi" in results_by_id
    assert results_by_id["sch_pm_svanidhi"]["decision"] == "NOT_LIKELY_ELIGIBLE"


@pytest.mark.e2e
def test_persona_5_ananya_das_divorced_artisan_wb(client: Any) -> None:
    """Persona 5: Ananya Das — Divorced Handloom Artisan, WB, Nadia.

    Expected:
    - PM-KISAN: NOT_LIKELY_ELIGIBLE (is_farmer=False)
    - AP Rythu Bharosa: Excluded by geography (WB != AP)
    - PM SVANidhi: Evaluates cleanly without error (satisfies unorganised worker)
    """
    profile = {
        "state_code": "IN-WB",
        "residence": "rural",
        "age_years": 34,
        "gender": "female",
        "social_category": "sc",
        "occupation": "daily_wage",
        "is_unorganised_worker": True,
        "annual_household_income_inr": 54000,
        "family_size": 2,
        "marital_status": "divorced",
        "is_farmer": False,
        "landholding_acres": 0.0,
    }
    resp = client.post("/api/v1/eligibility/evaluate", json={"answers": profile})
    assert resp.status_code == 200
    data = resp.json()

    results_by_id = {r["scheme_id"]: r for r in data["results"]}
    assert "sch_pm_kisan_2019" in results_by_id
    assert results_by_id["sch_pm_kisan_2019"]["decision"] == "NOT_LIKELY_ELIGIBLE"

    assert "sch_ap_rythu_bharosa" not in results_by_id
    assert "sch_pm_svanidhi" in results_by_id
    assert results_by_id["sch_pm_svanidhi"]["decision"] == "LIKELY_ELIGIBLE"


@pytest.mark.e2e
def test_persona_6_gurpreet_singh_commercial_landowner_pb(client: Any) -> None:
    """Persona 6: Gurpreet Singh — Commercial Landowner & Taxpayer, PB, Ludhiana.

    Expected:
    - Evaluates cleanly without 500 error
    - PM-KISAN: evaluated against rule criteria (landowner farmer)
    - AP Rythu Bharosa: Excluded by geography (PB != AP)
    - PM SVANidhi: NOT_LIKELY_ELIGIBLE (not an unorganised worker)
    """
    profile = {
        "state_code": "IN-PB",
        "age_years": 52,
        "gender": "male",
        "social_category": "general",
        "occupation": "farmer",
        "is_farmer": True,
        "landholding_acres": 22.0,
        "annual_household_income_inr": 1600000,
        "family_size": 4,
        "marital_status": "married",
        "is_unorganised_worker": False,
    }
    resp = client.post("/api/v1/eligibility/evaluate", json={"answers": profile})
    assert resp.status_code == 200
    data = resp.json()

    results_by_id = {r["scheme_id"]: r for r in data["results"]}
    assert "sch_pm_kisan_2019" in results_by_id
    # Under current rule, farmer with land > 0 is likely eligible
    assert results_by_id["sch_pm_kisan_2019"]["decision"] in ("LIKELY_ELIGIBLE", "NOT_LIKELY_ELIGIBLE")

    assert "sch_ap_rythu_bharosa" not in results_by_id
    assert "sch_pm_svanidhi" in results_by_id
    assert results_by_id["sch_pm_svanidhi"]["decision"] == "NOT_LIKELY_ELIGIBLE"


@pytest.mark.e2e
def test_persona_7_lakshmi_bai_tenant_cultivator_ap(client: Any) -> None:
    """Persona 7: Lakshmi Bai — Tenant Cultivator with CCRC, AP, Prakasam.

    Expected:
    - PM-KISAN: NOT_LIKELY_ELIGIBLE (fails landholding_acres > 0.0 because she owns 0.0 land)
    - AP Rythu Bharosa: LIKELY_ELIGIBLE (AP resident farmer)
    - PM SVANidhi: NOT_LIKELY_ELIGIBLE
    - Demonstrates real-world State vs Central policy divergence.
    """
    profile = {
        "state_code": "IN-AP",
        "district_code": "IN-AP-PRA",
        "residence": "rural",
        "age_years": 44,
        "gender": "female",
        "social_category": "sc",
        "occupation": "farmer",
        "is_farmer": True,
        "landholding_acres": 0.0,
        "annual_household_income_inr": 75000,
        "family_size": 4,
        "marital_status": "married",
        "is_unorganised_worker": False,
    }
    resp = client.post("/api/v1/eligibility/evaluate", json={"answers": profile})
    assert resp.status_code == 200
    data = resp.json()

    results_by_id = {r["scheme_id"]: r for r in data["results"]}

    # PM-KISAN strictly requires owning cultivable land (> 0)
    assert "sch_pm_kisan_2019" in results_by_id
    assert results_by_id["sch_pm_kisan_2019"]["decision"] == "NOT_LIKELY_ELIGIBLE"

    # AP Rythu Bharosa covers AP tenant farmers
    assert "sch_ap_rythu_bharosa" in results_by_id
    assert results_by_id["sch_ap_rythu_bharosa"]["decision"] == "LIKELY_ELIGIBLE"

    assert "sch_pm_svanidhi" in results_by_id
    assert results_by_id["sch_pm_svanidhi"]["decision"] == "NOT_LIKELY_ELIGIBLE"


@pytest.mark.e2e
def test_persona_8_mohammed_farhan_disabled_unemployed_tg(client: Any) -> None:
    """Persona 8: Mohammed Farhan — Disabled Unemployed Youth, TG, Hyderabad.

    Expected:
    - Evaluates cleanly without 500 error
    - PM-KISAN: NOT_LIKELY_ELIGIBLE (not a farmer)
    - AP Rythu Bharosa: Excluded by geography (TG != AP)
    - PM SVANidhi: NOT_LIKELY_ELIGIBLE (not an unorganised worker)
    """
    profile = {
        "state_code": "IN-TG",
        "residence": "urban",
        "age_years": 24,
        "gender": "male",
        "social_category": "other",
        "occupation": "unemployed",
        "disability_status": True,
        "annual_household_income_inr": 60000,
        "family_size": 3,
        "marital_status": "single",
        "is_farmer": False,
        "is_unorganised_worker": False,
    }
    resp = client.post("/api/v1/eligibility/evaluate", json={"answers": profile})
    assert resp.status_code == 200
    data = resp.json()

    results_by_id = {r["scheme_id"]: r for r in data["results"]}
    assert "sch_pm_kisan_2019" in results_by_id
    assert results_by_id["sch_pm_kisan_2019"]["decision"] == "NOT_LIKELY_ELIGIBLE"

    assert "sch_ap_rythu_bharosa" not in results_by_id
    assert "sch_pm_svanidhi" in results_by_id
    assert results_by_id["sch_pm_svanidhi"]["decision"] == "NOT_LIKELY_ELIGIBLE"


@pytest.mark.e2e
def test_persona_9_baby_meera_girl_child_rj(client: Any) -> None:
    """Persona 9: Baby Meera / Parent — Girl Child Profile, RJ, Jaipur.

    Expected:
    - Evaluates cleanly without 500 error
    - PM SVANidhi: NOT_LIKELY_ELIGIBLE (age 6 < 18)
    - AP Rythu Bharosa: Excluded by geography (RJ != AP)
    - PM-KISAN: NOT_LIKELY_ELIGIBLE (not a farmer)
    """
    profile = {
        "state_code": "IN-RJ",
        "age_years": 6,
        "gender": "female",
        "social_category": "general",
        "education_level": "primary",
        "annual_household_income_inr": 220000,
        "family_size": 4,
        "is_farmer": False,
        "is_unorganised_worker": False,
    }
    resp = client.post("/api/v1/eligibility/evaluate", json={"answers": profile})
    assert resp.status_code == 200
    data = resp.json()

    results_by_id = {r["scheme_id"]: r for r in data["results"]}
    assert "sch_pm_svanidhi" in results_by_id
    assert results_by_id["sch_pm_svanidhi"]["decision"] == "NOT_LIKELY_ELIGIBLE"

    assert "sch_ap_rythu_bharosa" not in results_by_id
    assert "sch_pm_kisan_2019" in results_by_id
    assert results_by_id["sch_pm_kisan_2019"]["decision"] == "NOT_LIKELY_ELIGIBLE"


@pytest.mark.e2e
def test_persona_10_incomplete_boundary_citizen_ap(client: Any) -> None:
    """Persona 10: Incomplete / Boundary Query Citizen (Partial Answers).

    Expected:
    - PM-KISAN: NEEDS_MORE_INFORMATION (is_farmer and landholding_acres missing)
    - AP Rythu Bharosa: NEEDS_MORE_INFORMATION (is_farmer missing)
    - PM SVANidhi: NEEDS_MORE_INFORMATION (age 18 passes >= 18; is_unorganised_worker missing)
    - missing_fields: contains 'is_farmer', 'landholding_acres', 'is_unorganised_worker'
    - follow_up_questions: non-empty list of targeted questions
    """
    profile = {
        "state_code": "IN-AP",
        "age_years": 18,
    }
    resp = client.post("/api/v1/eligibility/evaluate", json={"answers": profile})
    assert resp.status_code == 200
    data = resp.json()

    results_by_id = {r["scheme_id"]: r for r in data["results"]}
    assert results_by_id["sch_pm_kisan_2019"]["decision"] == "NEEDS_MORE_INFORMATION"
    assert results_by_id["sch_ap_rythu_bharosa"]["decision"] == "NEEDS_MORE_INFORMATION"
    assert results_by_id["sch_pm_svanidhi"]["decision"] == "NEEDS_MORE_INFORMATION"

    missing = data.get("missing_fields", [])
    assert "is_farmer" in missing
    assert "landholding_acres" in missing
    assert "is_unorganised_worker" in missing

    questions = data.get("follow_up_questions", [])
    assert len(questions) >= 1
    question_fields = {q["field"] for q in questions}
    assert "is_farmer" in question_fields or "is_unorganised_worker" in question_fields


# ==============================================================================
# Cross-Persona Contract, Journey, and Progressive Resolution Tests
# ==============================================================================


@pytest.mark.e2e
def test_personas_cross_comparison_response_contract_conformance(client: Any) -> None:
    """Verify that all 10 citizen personas produce responses adhering to the API contract."""
    personas = [
        # P1: Marginal farmer AP
        {"state_code": "IN-AP", "age_years": 42, "is_farmer": True, "landholding_acres": 2.2},
        # P2: Street vendor UP
        {"state_code": "IN-UP", "age_years": 38, "is_unorganised_worker": True, "is_farmer": False},
        # P3: Student MH
        {"state_code": "IN-MH", "age_years": 19, "is_student": True, "is_farmer": False},
        # P4: Elderly farmer KA
        {"state_code": "IN-KA", "age_years": 68, "is_farmer": True, "landholding_acres": 0.75},
        # P5: Artisan WB
        {"state_code": "IN-WB", "age_years": 34, "is_unorganised_worker": True, "is_farmer": False},
        # P6: Commercial landowner PB
        {"state_code": "IN-PB", "age_years": 52, "is_farmer": True, "landholding_acres": 22.0},
        # P7: Tenant farmer AP
        {"state_code": "IN-AP", "age_years": 44, "is_farmer": True, "landholding_acres": 0.0},
        # P8: Disabled youth TG
        {"state_code": "IN-TG", "age_years": 24, "disability_status": True, "is_farmer": False},
        # P9: Girl child RJ
        {"state_code": "IN-RJ", "age_years": 6, "gender": "female", "is_farmer": False},
        # P10: Incomplete boundary
        {"state_code": "IN-AP", "age_years": 18},
    ]

    for index, p in enumerate(personas, 1):
        resp = client.post("/api/v1/eligibility/evaluate", json={"answers": p})
        assert resp.status_code == 200, f"Persona {index} failed with status {resp.status_code}"
        data = resp.json()

        # Contract assertions
        assert "evaluation_date" in data, f"Persona {index} missing evaluation_date"
        assert "results" in data, f"Persona {index} missing results"
        assert isinstance(data["results"], list)
        assert "excluded_schemes" in data, f"Persona {index} missing excluded_schemes"
        assert "missing_fields" in data, f"Persona {index} missing missing_fields"
        assert "follow_up_questions" in data, f"Persona {index} missing follow_up_questions"
        assert "disclaimer" in data, f"Persona {index} missing disclaimer"
        assert len(data["disclaimer"]) > 0

        # Decisions enum check
        for res in data["results"]:
            assert res["decision"] in VALID_DECISIONS, f"Persona {index} invalid decision: {res['decision']}"
            assert "criteria" in res
            assert "verification_status" in res

        # If coverage metadata is present (M1 contract), assert its fields
        if "coverage" in data:
            cov = data["coverage"]
            assert "schemes_considered" in cov
            assert "excluded_by_geography" in cov
            assert "excluded_by_filters" in cov


@pytest.mark.e2e
def test_persona_1_discovery_to_tracking_application_journey(
    client: Any, valid_farmer_profile: dict[str, Any]
) -> None:
    """Full end-to-end journey for Ramesh Kumar: Evaluate -> Detail Provenance -> Track -> Update."""
    # Step 1: Evaluate eligibility
    eval_resp = client.post("/api/v1/eligibility/evaluate", json={"answers": valid_farmer_profile})
    assert eval_resp.status_code == 200
    kisan_res = next(
        r for r in eval_resp.json()["results"] if r["scheme_id"] == "sch_pm_kisan_2019"
    )
    assert kisan_res["decision"] == "LIKELY_ELIGIBLE"

    # Step 2: Fetch detailed provenance and application steps for PM-KISAN
    detail_resp = client.get("/api/v1/schemes/sch_pm_kisan_2019")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == "sch_pm_kisan_2019"
    assert "sources" in detail
    assert len(detail["sources"]) >= 1

    # Step 3: Create anonymous tracking application
    track_resp = client.post(
        "/api/v1/tracking",
        json={
            "scheme_id": "sch_pm_kisan_2019",
            "status": "planned",
            "progress_date": "2026-11-22",
        },
    )
    assert track_resp.status_code == 201
    track_data = track_resp.json()
    tracking_id = track_data["tracking_id"]
    token = track_data["token"]

    # Step 4: Query application status anonymously
    get_resp = client.get(
        f"/api/v1/tracking/{tracking_id}",
        headers={"X-Tracking-Token": token},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "planned"

    # Step 5: Citizen submits application at official portal and updates tracking record
    patch_resp = client.patch(
        f"/api/v1/tracking/{tracking_id}",
        headers={"X-Tracking-Token": token},
        json={"status": "submitted"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "submitted"

    # Step 6: Verify updated status is persistent
    final_get = client.get(
        f"/api/v1/tracking/{tracking_id}",
        headers={"X-Tracking-Token": token},
    )
    assert final_get.status_code == 200
    assert final_get.json()["status"] == "submitted"


@pytest.mark.e2e
def test_persona_10_progressive_resolution_journey(client: Any) -> None:
    """Step-by-step resolution journey for Persona 10 (Incomplete Boundary Citizen).

    Citizen progressively answers follow-up questions until unknown decisions flip to definitive outcomes.
    """
    # Step 1: Starting state — only knows resident state AP and boundary age 18
    p = {"state_code": "IN-AP", "age_years": 18}
    r1 = client.post("/api/v1/eligibility/evaluate", json={"answers": p}).json()
    results1 = {res["scheme_id"]: res["decision"] for res in r1["results"]}
    assert results1["sch_pm_kisan_2019"] == "NEEDS_MORE_INFORMATION"
    assert results1["sch_ap_rythu_bharosa"] == "NEEDS_MORE_INFORMATION"
    assert results1["sch_pm_svanidhi"] == "NEEDS_MORE_INFORMATION"
    assert "is_farmer" in r1["missing_fields"]

    # Step 2: Citizen answers first follow-up question: 'is_farmer: True'
    p["is_farmer"] = True
    r2 = client.post("/api/v1/eligibility/evaluate", json={"answers": p}).json()
    results2 = {res["scheme_id"]: res["decision"] for res in r2["results"]}
    # AP Rythu Bharosa now has all mandatory requirements satisfied (state AP + farmer) -> flips to LIKELY_ELIGIBLE!
    assert results2["sch_ap_rythu_bharosa"] == "LIKELY_ELIGIBLE"
    # PM-KISAN still needs landholding_acres
    assert results2["sch_pm_kisan_2019"] == "NEEDS_MORE_INFORMATION"

    # Step 3: Citizen answers second question: 'landholding_acres: 2.5'
    p["landholding_acres"] = 2.5
    r3 = client.post("/api/v1/eligibility/evaluate", json={"answers": p}).json()
    results3 = {res["scheme_id"]: res["decision"] for res in r3["results"]}
    # PM-KISAN now flips to LIKELY_ELIGIBLE!
    assert results3["sch_pm_kisan_2019"] == "LIKELY_ELIGIBLE"

    # Step 4: Citizen answers remaining question: 'is_unorganised_worker: False'
    p["is_unorganised_worker"] = False
    r4 = client.post("/api/v1/eligibility/evaluate", json={"answers": p}).json()
    results4 = {res["scheme_id"]: res["decision"] for res in r4["results"]}
    # PM SVANidhi flips to NOT_LIKELY_ELIGIBLE
    assert results4["sch_pm_svanidhi"] == "NOT_LIKELY_ELIGIBLE"

    # Final state: completely resolved
    assert r4["missing_fields"] == []
    assert r4["follow_up_questions"] == []
