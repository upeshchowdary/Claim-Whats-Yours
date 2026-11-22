"""Integration and capability tests for Milestone M2:
Domain Schemes, Catalogues & Geographic Evaluation.

Verifies:
1. District search scope inclusivity:
   Querying by district_code returns national schemes, resident state schemes,
   and district-specific schemes via parent state resolution.
2. Multi-state district catalogues:
   All 7 key citizen persona districts are catalogued with valid parent codes and names.
3. Profile fields catalogue:
   8 new high-impact domain fields (ration_card_type, is_income_tax_payer,
   disability_percentage, minority_status, owns_pucca_house, employer_sector,
   has_epf_esi, current_enrollment) are present and properly constrained.
   All 7 forbidden sensitive fields remain strictly forbidden.
4. Rich sector-representative scheme corpus:
   Schemes across all 7 priority sectors (Agriculture, Health/Insurance, Pensions/Security,
   Housing/Sanitation, Employment/Livelihood, Education, Women/Child) are seeded,
   published, have authentic HTTPS official sources, and pass rule AST validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from claim_whats_yours.core.config import get_settings
from claim_whats_yours.db import models
from claim_whats_yours.db.session import get_session_factory
from claim_whats_yours.domain.fields import (
    forbidden_field_ids,
    load_registry,
    validate_answers,
)
from claim_whats_yours.domain.geography import (
    district_parent_state,
    known_district_codes,
    known_state_codes,
)
from claim_whats_yours.domain.rules import check_rule

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
LIST_URL = "/api/v1/schemes"


# ==============================================================================
# 1. District Search Scope Inclusivity (scheme_service.py)
# ==============================================================================


def test_district_search_includes_national_state_and_district_schemes(
    client: Any, db: Session, scheme_factory: Any
) -> None:
    """When querying schemes by district_code, the response must include:
    - central (all_india) schemes
    - resident parent state schemes
    - district-specific schemes for that district
    And exclude schemes belonging to other states or other districts.
    """
    # Central scheme
    scheme_factory(db, "sch-central-nat", scope="all_india", government_level="central")

    # State scheme for UP (parent of IN-UP-LKO)
    scheme_factory(
        db,
        "sch-up-state",
        scope="state",
        state_codes=("IN-UP",),
        government_level="state",
    )

    # District scheme for Lucknow
    scheme_factory(
        db,
        "sch-lko-district",
        scope="district",
        state_codes=("IN-UP-LKO",),
        government_level="district",
    )

    # State scheme for Maharashtra (should be excluded when querying Lucknow)
    scheme_factory(
        db,
        "sch-mh-state",
        scope="state",
        state_codes=("IN-MH",),
        government_level="state",
    )

    # District scheme for Pune (should be excluded when querying Lucknow)
    scheme_factory(
        db,
        "sch-pun-district",
        scope="district",
        state_codes=("IN-MH-PUN",),
        government_level="district",
    )

    # Query by Lucknow district
    response = client.get(LIST_URL, params={"district_code": "IN-UP-LKO"})
    assert response.status_code == 200, f"Query failed: {response.text}"

    items = response.json()["items"]
    ids = {item["id"] for item in items}

    # Must include central, UP state, and Lucknow district schemes
    assert "sch-central-nat" in ids
    assert "sch-up-state" in ids
    assert "sch-lko-district" in ids

    # Must NOT include Maharashtra or Pune schemes
    assert "sch-mh-state" not in ids
    assert "sch-pun-district" not in ids


def test_district_search_invalid_district_code_returns_empty_or_national(
    client: Any, db: Session, scheme_factory: Any
) -> None:
    """An unknown district code returns national schemes only (no matching state/district)."""
    scheme_factory(db, "sch-nat-only", scope="all_india", government_level="central")
    scheme_factory(
        db,
        "sch-up-only",
        scope="state",
        state_codes=("IN-UP",),
        government_level="state",
    )

    response = client.get(LIST_URL, params={"district_code": "IN-XX-UNKNOWN"})
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert "sch-nat-only" in ids
    assert "sch-up-only" not in ids


# ==============================================================================
# 2. Multi-State District Catalogues (jurisdictions.json & geography.py)
# ==============================================================================


@pytest.mark.parametrize(
    ("district_code", "expected_name", "expected_parent"),
    [
        ("IN-UP-LKO", "Lucknow", "IN-UP"),
        ("IN-MH-PUN", "Pune", "IN-MH"),
        ("IN-KA-RAI", "Raichur", "IN-KA"),
        ("IN-WB-NAD", "Nadia", "IN-WB"),
        ("IN-PB-LDH", "Ludhiana", "IN-PB"),
        ("IN-TG-HYD", "Hyderabad", "IN-TG"),
        ("IN-RJ-JAI", "Jaipur", "IN-RJ"),
    ],
)
def test_persona_districts_catalogued(
    district_code: str, expected_name: str, expected_parent: str
) -> None:
    """Verify all 7 persona districts exist in catalogue and resolve to correct parent state."""
    with open(DATA_DIR / "jurisdictions.json", encoding="utf-8") as f:
        catalogue = json.load(f)

    districts = {j["code"]: j for j in catalogue if j.get("level") == "district"}
    assert district_code in districts, f"District {district_code} missing from jurisdictions.json"

    entry = districts[district_code]
    assert entry["name"] == expected_name
    assert entry["level"] == "district"
    assert entry["parent_code"] == expected_parent

    # Check geography module resolvers
    assert district_code in known_district_codes()
    assert district_parent_state(district_code) == expected_parent
    assert expected_parent in known_state_codes()


# ==============================================================================
# 3. Profile Fields Catalogue Enrichment (profile_fields.json & fields.py)
# ==============================================================================


def test_new_domain_fields_registered() -> None:
    """Verify all 8 newly added domain profile fields are present and correctly typed."""
    registry = load_registry()

    expected_fields = {
        "ration_card_type": {"category": "economic", "type": "enum"},
        "is_income_tax_payer": {"category": "economic", "type": "bool"},
        "disability_percentage": {"category": "health", "type": "int"},
        "minority_status": {"category": "demographic", "type": "bool"},
        "owns_pucca_house": {"category": "housing", "type": "bool"},
        "employer_sector": {"category": "employment", "type": "enum"},
        "has_epf_esi": {"category": "employment", "type": "bool"},
        "current_enrollment": {"category": "education", "type": "bool"},
    }

    for field_name, expected in expected_fields.items():
        assert field_name in registry, f"Field '{field_name}' not in registry"
        field_def = registry[field_name]
        assert field_def["category"] == expected["category"]
        assert field_def["type"] == expected["type"]


def test_ration_card_type_enum_options() -> None:
    """ration_card_type must allow aay, bpl_phh, apl_nphh, none, and prefer_not_to_say."""
    registry = load_registry()
    allowed = registry["ration_card_type"]["allowed"]
    expected_allowed = ["aay", "bpl_phh", "apl_nphh", "none", "prefer_not_to_say"]
    for opt in expected_allowed:
        assert opt in allowed, f"Option '{opt}' missing from ration_card_type"


def test_employer_sector_enum_options() -> None:
    """employer_sector must allow government, private_organized, unorganized, none, etc."""
    registry = load_registry()
    allowed = registry["employer_sector"]["allowed"]
    expected = ["government", "private_organized", "unorganized", "none", "prefer_not_to_say"]
    for opt in expected:
        assert opt in allowed, f"Option '{opt}' missing from employer_sector"


def test_disability_percentage_range_validation() -> None:
    """disability_percentage must enforce range 0 to 100."""
    registry = load_registry()
    val_range = registry["disability_percentage"].get("range", {})
    assert val_range.get("min") == 0
    assert val_range.get("max") == 100

    # Valid values
    assert validate_answers({"disability_percentage": 0}) == []
    assert validate_answers({"disability_percentage": 40}) == []
    assert validate_answers({"disability_percentage": 100}) == []

    # Out of range values
    errs_low = validate_answers({"disability_percentage": -5})
    assert len(errs_low) > 0

    errs_high = validate_answers({"disability_percentage": 105})
    assert len(errs_high) > 0


def test_forbidden_sensitive_fields_remain_strictly_blocked() -> None:
    """Critical privacy invariant: all 7 sensitive fields must be rejected."""
    registry = load_registry()
    for sensitive in forbidden_field_ids():
        assert sensitive not in registry, f"Forbidden field '{sensitive}' leaked into registry!"
        # Submitting them in answers must result in validation errors
        errors = validate_answers({sensitive: "sensitive_value_123"})
        assert len(errors) > 0, f"Sensitive field '{sensitive}' was not rejected!"


# ==============================================================================
# 4. Sector Representation & Official HTTPS Sources
# ==============================================================================


def test_database_contains_representative_schemes_across_all_sectors() -> None:
    """Verify the database has published schemes representing all priority sectors."""
    db_path = Path(__file__).resolve().parents[2] / "claim_whats_yours.db"
    url = f"sqlite:///{db_path}" if db_path.exists() else get_settings().database_url
    session_factory = get_session_factory(url)

    with session_factory() as session:
        schemes = (
            session.query(models.Scheme)
            .filter(models.Scheme.record_status == "published")
            .all()
        )
        schemes_by_id = {s.id: s for s in schemes}

        # Check required schemes by sector
        expected_schemes = [
            # Agriculture
            "sch_pm_kisan_2019",
            "sch_pmfby",
            "sch_kcc",
            "sch_ap_rythu_bharosa",
            # Health & Insurance
            "sch_ayushman_pmjay",
            "sch_pmjjby",
            "sch_pmsby",
            # Pensions & Social Security
            "sch_nsap_ignoaps",
            "sch_atal_pension",
            "sch_sukanya_samriddhi",
            # Housing & Sanitation
            "sch_pmay_gramin",
            "sch_pmay_urban",
            "sch_sbm_gramin",
            # Employment & Livelihood
            "sch_pm_svanidhi",
            "sch_mgnrega",
            "sch_pmegp",
            "sch_pm_mudra",
            # Education
            "sch_post_matric_scholarship",
            "sch_nmms_scholarship",
            # Women & Child
            "sch_pm_ujjwala",
            "sch_pmmvy",
        ]

        for sid in expected_schemes:
            assert sid in schemes_by_id, (
                f"Mandatory representative scheme '{sid}' is not published in database!"
            )
            scheme = schemes_by_id[sid]

            # Verify rule AST validity
            rule_errors = check_rule(scheme.eligibility_rule)
            assert rule_errors == [], f"Scheme '{sid}' has invalid rule AST: {rule_errors}"

            # Verify HTTPS official sources
            payload = scheme.payload if isinstance(scheme.payload, dict) else {}
            sources = payload.get("sources", [])
            assert len(sources) > 0, f"Scheme '{sid}' must have at least one official source"
            for src in sources:
                assert src.get("url", "").startswith("https://"), (
                    f"Scheme '{sid}' source URL '{src.get('url')}' is not secure HTTPS"
                )
