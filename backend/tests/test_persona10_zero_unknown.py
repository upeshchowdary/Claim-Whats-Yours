"""Verify that every scheme in the proposed seed corpus evaluates to PASS or FAIL for Persona 10 without UNKNOWN leaves."""
from claim_whats_yours.domain.rules import evaluate_rule, Tri
from claim_whats_yours.services.eligibility_service import _extract_leaves, _raw_leaf_fields

p = {
    "state_code": "IN-AP",
    "age_years": 18,
    "is_farmer": True,
    "landholding_acres": 2.5,
    "is_unorganised_worker": False,
}

def test_scheme_rules():
    # 1. PM-KISAN
    r_kisan = {
        "all": [
            {"criterion_id": "c1", "field": "is_farmer", "operator": "eq", "value": True, "mandatory": True, "explanation": "", "source_refs": ["s1"]},
            {"criterion_id": "c2", "field": "landholding_acres", "operator": "gt", "value": 0.0, "mandatory": True, "explanation": "", "source_refs": ["s1"]},
        ]
    }
    assert evaluate_rule(r_kisan, p).status == Tri.PASS

    # 2. PM SVANidhi
    r_svanidhi = {
        "all": [
            {"criterion_id": "c1", "field": "is_unorganised_worker", "operator": "eq", "value": True, "mandatory": True, "explanation": "", "source_refs": ["s1"]},
            {"criterion_id": "c2", "field": "age_years", "operator": "gte", "value": 18, "mandatory": True, "explanation": "", "source_refs": ["s1"]},
        ]
    }
    assert evaluate_rule(r_svanidhi, p).status == Tri.FAIL

    # 3. Ayushman PM-JAY (70+ senior expansion)
    r_pmjay = {
        "all": [
            {"criterion_id": "c1", "field": "age_years", "operator": "gte", "value": 70, "mandatory": True, "explanation": "", "source_refs": ["s1"]},
        ]
    }
    assert evaluate_rule(r_pmjay, p).status == Tri.FAIL
    leaves = _extract_leaves(r_pmjay, p)
    assert not any(l.status == Tri.UNKNOWN for l in leaves)

    # 4. NSAP IGNOAPS (60+ old age)
    r_nsap = {
        "all": [
            {"criterion_id": "c1", "field": "age_years", "operator": "gte", "value": 60, "mandatory": True, "explanation": "", "source_refs": ["s1"]},
        ]
    }
    assert evaluate_rule(r_nsap, p).status == Tri.FAIL
    leaves = _extract_leaves(r_nsap, p)
    assert not any(l.status == Tri.UNKNOWN for l in leaves)

    # 5. Sukanya Samriddhi (<= 10 girl child)
    r_ssy = {
        "all": [
            {"criterion_id": "c1", "field": "age_years", "operator": "lte", "value": 10, "mandatory": True, "explanation": "", "source_refs": ["s1"]},
        ]
    }
    assert evaluate_rule(r_ssy, p).status == Tri.FAIL
    leaves = _extract_leaves(r_ssy, p)
    assert not any(l.status == Tri.UNKNOWN for l in leaves)

    # 6. PMEGP / Mudra (non-farm self-employment)
    r_pmegp = {
        "all": [
            {"criterion_id": "c1", "field": "is_farmer", "operator": "eq", "value": False, "mandatory": True, "explanation": "", "source_refs": ["s1"]},
            {"criterion_id": "c2", "field": "age_years", "operator": "gte", "value": 18, "mandatory": True, "explanation": "", "source_refs": ["s1"]},
        ]
    }
    assert evaluate_rule(r_pmegp, p).status == Tri.FAIL
    leaves = _extract_leaves(r_pmegp, p)
    assert not any(l.status == Tri.UNKNOWN for l in leaves)

    # 7. MGNREGA (unorganised rural manual work)
    r_mgnrega = {
        "all": [
            {"criterion_id": "c1", "field": "is_unorganised_worker", "operator": "eq", "value": True, "mandatory": True, "explanation": "", "source_refs": ["s1"]},
            {"criterion_id": "c2", "field": "age_years", "operator": "gte", "value": 18, "mandatory": True, "explanation": "", "source_refs": ["s1"]},
        ]
    }
    assert evaluate_rule(r_mgnrega, p).status == Tri.FAIL
    leaves = _extract_leaves(r_mgnrega, p)
    assert not any(l.status == Tri.UNKNOWN for l in leaves)

    # 8. PMFBY (crop insurance for farmers with land > 0)
    r_pmfby = {
        "all": [
            {"criterion_id": "c1", "field": "is_farmer", "operator": "eq", "value": True, "mandatory": True, "explanation": "", "source_refs": ["s1"]},
            {"criterion_id": "c2", "field": "landholding_acres", "operator": "gt", "value": 0.0, "mandatory": True, "explanation": "", "source_refs": ["s1"]},
        ]
    }
    assert evaluate_rule(r_pmfby, p).status == Tri.PASS
    leaves = _extract_leaves(r_pmfby, p)
    assert not any(l.status == Tri.UNKNOWN for l in leaves)
