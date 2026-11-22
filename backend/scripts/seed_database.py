"""Seed the local database with reviewed sample scheme records.

The records are imported as drafts then follow the normal human-review lifecycle:
import -> validate -> verify -> publish. They remain sample records for local
product demonstration; the original official links are kept as provenance.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claim_whats_yours.core.config import get_settings  # noqa: E402
from claim_whats_yours.db.models import Jurisdiction, Scheme  # noqa: E402
from claim_whats_yours.db.session import get_session_factory  # noqa: E402
from claim_whats_yours.services.admin_service import (  # noqa: E402
    import_draft,
    publish_scheme,
    validate_scheme,
    verify_scheme,
)

SCHEMES = [
    {
        "id": "sch_pm_kisan_2019",
        "slug": "pm-kisan-samman-nidhi",
        "name": "PM Kisan Samman Nidhi (PM-KISAN)",
        "summary": (
            "Income support of Rs. 6,000 per year in three equal installments "
            "to landholding farmer families across India."
        ),
        "government_level": "central",
        "categories": ["agriculture", "financial_inclusion"],
        "beneficiary_groups": ["farmer"],
        "jurisdictions": {"scope": "all_india", "state_codes": [], "district_codes": []},
        "effective_from": "2019-02-24",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_is_farmer",
                    "field": "is_farmer",
                    "operator": "eq",
                    "value": True,
                    "mandatory": True,
                    "explanation": "Applicant family must cultivate or own agricultural land.",
                    "source_refs": ["src_pm_kisan_guidelines"],
                },
                {
                    "criterion_id": "crit_landholding",
                    "field": "landholding_acres",
                    "operator": "gt",
                    "value": 0.0,
                    "mandatory": True,
                    "explanation": "Must hold cultivable land in revenue records.",
                    "source_refs": ["src_pm_kisan_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "Land ownership record (RoR / Pattadar Passbook)",
                "mandatory": True,
                "description": "Proof of ownership of cultivable agricultural land.",
                "purpose": "land verification",
            },
            {
                "name": "Bank account details",
                "mandatory": True,
                "description": "Active bank account for Direct Benefit Transfer (DBT).",
                "purpose": "payment transfer",
            },
        ],
        "application_steps": [
            {
                "instruction": (
                    "Visit the official PM-KISAN portal or your nearest Common "
                    "Service Centre (CSC)."
                ),
                "department": "Department of Agriculture and Farmers Welfare",
            },
            {"instruction": "In Farmers Corner, select New Farmer Registration."},
            {
                "instruction": (
                    "Enter your state, district, and landholding revenue survey number details."
                )
            },
            {"instruction": "Submit the application and note its reference number."},
        ],
        "application_url": "https://pmkisan.gov.in/",
        "sources": [
            {
                "id": "src_pm_kisan_guidelines",
                "title": (
                    "PM-KISAN Operational Guidelines, Ministry of Agriculture and Farmers Welfare"
                ),
                "publisher": "Ministry of Agriculture and Farmers Welfare, Government of India",
                "url": "https://pmkisan.gov.in/Documents/OperationalGuidelines.pdf",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2019-02-01",
                "section": "Section 3 - Eligibility Criteria",
            }
        ],
    },
    {
        "id": "sch_ap_rythu_bharosa",
        "slug": "ap-rythu-bharosa",
        "name": "YSR Rythu Bharosa / Annadata Sukhibhava",
        "summary": (
            "Andhra Pradesh farmer welfare scheme offering annual financial "
            "assistance of Rs. 13,500 to eligible farmer families and tenants."
        ),
        "government_level": "state",
        "categories": ["agriculture", "financial_inclusion"],
        "beneficiary_groups": ["farmer"],
        "jurisdictions": {"scope": "state", "state_codes": ["IN-AP"], "district_codes": []},
        "effective_from": "2019-10-15",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_ap_resident",
                    "field": "state_code",
                    "operator": "eq",
                    "value": "IN-AP",
                    "mandatory": True,
                    "explanation": "Applicant must reside in Andhra Pradesh.",
                    "source_refs": ["src_ap_rythu_go"],
                },
                {
                    "criterion_id": "crit_ap_farmer",
                    "field": "is_farmer",
                    "operator": "eq",
                    "value": True,
                    "mandatory": True,
                    "explanation": (
                        "Applicant must be a farmer or cultivating tenant in Andhra Pradesh."
                    ),
                    "source_refs": ["src_ap_rythu_go"],
                },
            ]
        },
        "documents": [
            {
                "name": "Pattadar passbook or CCRC (Crop Cultivator Rights Card)",
                "mandatory": True,
                "description": (
                    "Proof of agricultural land ownership or authorized tenant rights card."
                ),
                "purpose": "cultivation rights",
            },
            {
                "name": "Bank account passbook",
                "mandatory": True,
                "description": "Bank account linked with a local branch.",
                "purpose": "DBT transfer",
            },
        ],
        "application_steps": [
            {
                "instruction": (
                    "Approach your Grama or Ward Sachivalayam or the Agriculture "
                    "Assistant in your area."
                ),
                "department": "Department of Agriculture, Government of Andhra Pradesh",
            },
            {
                "instruction": (
                    "Verify your name in the social-audit list at a Rythu Bharosa Kendra (RBK)."
                )
            },
            {"instruction": "Submit land or tenant cultivation records for verification."},
        ],
        "application_url": "https://ysrrythubharosa.ap.gov.in/",
        "sources": [
            {
                "id": "src_ap_rythu_go",
                "title": (
                    "Government Order G.O.Ms.No.96, Agriculture and Cooperation "
                    "Department, Andhra Pradesh"
                ),
                "publisher": "Government of Andhra Pradesh",
                "url": "https://ysrrythubharosa.ap.gov.in/RBK/Home/About",
                "source_type": "government_order",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2019-10-01",
                "section": "Eligibility and Guidelines",
            }
        ],
    },
    {
        "id": "sch_pm_svanidhi",
        "slug": "pm-svanidhi",
        "name": "PM SVANidhi (Street Vendor's AtmaNirbhar Nidhi)",
        "summary": (
            "Central scheme providing affordable working-capital loans to street "
            "vendors so they can resume or grow their livelihoods."
        ),
        "government_level": "central",
        "categories": ["employment", "financial_inclusion"],
        "beneficiary_groups": ["unorganised_worker"],
        "jurisdictions": {"scope": "all_india", "state_codes": [], "district_codes": []},
        "effective_from": "2020-06-01",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_svanidhi_worker",
                    "field": "is_unorganised_worker",
                    "operator": "eq",
                    "value": True,
                    "mandatory": True,
                    "explanation": "Must be engaged in vending or unorganised micro-enterprise.",
                    "source_refs": ["src_svanidhi_guidelines"],
                },
                {
                    "criterion_id": "crit_svanidhi_age",
                    "field": "age_years",
                    "operator": "gte",
                    "value": 18,
                    "mandatory": True,
                    "explanation": "Applicant must be at least 18 years of age.",
                    "source_refs": ["src_svanidhi_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "Certificate of Vending or ULB identity card",
                "mandatory": True,
                "description": "Vending ID or Letter of Recommendation from the Urban Local Body.",
                "purpose": "vendor verification",
            }
        ],
        "application_steps": [
            {
                "instruction": (
                    "Visit the PM SVANidhi portal or consult a local Urban Local "
                    "Body (ULB) officer."
                ),
                "department": "Ministry of Housing and Urban Affairs",
            },
            {"instruction": "Apply for a working-capital loan using the vending certificate."},
        ],
        "application_url": "https://pmsvanidhi.mohua.gov.in/",
        "sources": [
            {
                "id": "src_svanidhi_guidelines",
                "title": "PM SVANidhi Scheme Guidelines, Ministry of Housing and Urban Affairs",
                "publisher": "Ministry of Housing and Urban Affairs, Government of India",
                "url": "https://pmsvanidhi.mohua.gov.in/Schemes/Guideline",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2020-06-01",
                "section": "Section 4 - Eligibility of Beneficiaries",
            }
        ],
    },
]


def seed_database() -> int:
    """Insert jurisdiction data and publish sample scheme records if absent."""
    settings = get_settings()
    factory = get_session_factory(settings.database_url)
    now = datetime.now(UTC)

    data_path = Path(__file__).resolve().parents[1] / "data" / "jurisdictions.json"
    with data_path.open(encoding="utf-8") as file:
        jurisdictions_data = json.load(file)

    with factory() as session:
        for jurisdiction in jurisdictions_data:
            if session.get(Jurisdiction, jurisdiction["code"]) is None:
                session.add(
                    Jurisdiction(
                        code=jurisdiction["code"],
                        name=jurisdiction["name"],
                        level=jurisdiction["level"],
                        parent_code=jurisdiction.get("parent_code"),
                    )
                )
        session.commit()
    print(f"Ensured {len(jurisdictions_data)} jurisdictions.")

    published_count = 0
    for record in SCHEMES:
        with factory() as session:
            if session.get(Scheme, record["id"]) is not None:
                print(f"Scheme {record['id']} already exists, skipping.")
                continue
            scheme = import_draft(session, record, now)
            session.commit()
            ok, errors = validate_scheme(session, scheme.id, now)
            if not ok:
                session.rollback()
                raise RuntimeError(f"Validation failed for {scheme.id}: {errors}")
            session.commit()
            verify_scheme(
                session,
                scheme.id,
                reviewer="Government Program Reviewer",
                verified_at=date.today(),
                now=now,
            )
            session.commit()
            publish_scheme(session, scheme.id, actor="System Administrator", now=now)
            session.commit()
            published_count += 1
            print(f"Published sample scheme: {scheme.id}")

    print(f"Published {published_count} new scheme(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(seed_database())
