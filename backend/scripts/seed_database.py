"""Seed the local database with reviewed sample scheme records across major sectors.

The records are imported as drafts then follow the normal human-review lifecycle:
import -> validate -> verify -> publish. They remain sample records for local
product demonstration; the original official links are kept as provenance.
"""

from __future__ import annotations

import copy
import json
import os
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
    # ---------------------------------------------------------------- Agriculture
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
                {
                    "criterion_id": "crit_kisan_taxpayer_exclusion",
                    "field": "is_income_tax_payer",
                    "operator": "ne",
                    "value": True,
                    "mandatory": False,
                    "explanation": "Excludes institutional landholders and income tax paying families.",
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
                "section": "Section 3 - Eligibility Criteria and Exclusions",
            }
        ],
    },
    {
        "id": "sch_ap_rythu_bharosa",
        "slug": "ap-rythu-bharosa",
        "name": "YSR Rythu Bharosa / Annadata Sukhibhava",
        "summary": (
            "Andhra Pradesh farmer welfare scheme offering annual financial "
            "assistance of Rs. 13,500 to eligible farmer families and tenant cultivators."
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
                    "criterion_id": "crit_ap_farmer",
                    "field": "is_farmer",
                    "operator": "eq",
                    "value": True,
                    "mandatory": True,
                    "explanation": (
                        "Applicant must be a farmer or cultivating tenant (including CCRC holders with 0 owned acres) in Andhra Pradesh."
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
                "section": "Eligibility and Guidelines for Landowners and Tenant Cultivators",
            }
        ],
    },
    {
        "id": "sch_pmfby",
        "slug": "pradhan-mantri-fasal-bima-yojana",
        "name": "Pradhan Mantri Fasal Bima Yojana (PMFBY)",
        "summary": (
            "Comprehensive crop insurance cover against non-preventable natural risks "
            "from pre-sowing to post-harvest for farmers."
        ),
        "government_level": "central",
        "categories": ["agriculture", "insurance"],
        "beneficiary_groups": ["farmer"],
        "jurisdictions": {"scope": "all_india", "state_codes": [], "district_codes": []},
        "effective_from": "2016-04-01",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_pmfby_farmer",
                    "field": "is_farmer",
                    "operator": "eq",
                    "value": True,
                    "mandatory": True,
                    "explanation": "Must be a farmer cultivating notified crops in notified areas.",
                    "source_refs": ["src_pmfby_guidelines"],
                },
                {
                    "criterion_id": "crit_pmfby_landholding",
                    "field": "landholding_acres",
                    "operator": "gt",
                    "value": 0.0,
                    "mandatory": True,
                    "explanation": "Must cultivate agricultural land with insurable interest.",
                    "source_refs": ["src_pmfby_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "Sowing Certificate / Land Revenue Record",
                "mandatory": True,
                "description": "Proof of cultivating notified crop on specified land.",
                "purpose": "crop verification",
            }
        ],
        "application_steps": [
            {"instruction": "Visit the PMFBY portal or consult your local bank branch/CSC."},
            {"instruction": "Submit land details, crop sown, and bank account for premium debit."},
        ],
        "application_url": "https://pmfby.gov.in/",
        "sources": [
            {
                "id": "src_pmfby_guidelines",
                "title": "PMFBY Revised Operational Guidelines",
                "publisher": "Ministry of Agriculture and Farmers Welfare, Government of India",
                "url": "https://pmfby.gov.in/pdf/Revised_Operational_Guidelines.pdf",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2016-02-15",
                "section": "Coverage of Farmers and Crops",
            }
        ],
    },
    {
        "id": "sch_kcc",
        "slug": "kisan-credit-card",
        "name": "Kisan Credit Card (KCC) Scheme",
        "summary": (
            "Adequate and timely institutional credit to farmers for agricultural "
            "inputs, post-harvest expenses, and allied activities at subsidized interest rates."
        ),
        "government_level": "central",
        "categories": ["agriculture", "financial_inclusion"],
        "beneficiary_groups": ["farmer"],
        "jurisdictions": {"scope": "all_india", "state_codes": [], "district_codes": []},
        "effective_from": "1998-08-01",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_kcc_farmer",
                    "field": "is_farmer",
                    "operator": "eq",
                    "value": True,
                    "mandatory": True,
                    "explanation": "Applicant must be an owner cultivator, tenant farmer, or oral lessee.",
                    "source_refs": ["src_kcc_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "Land record / Lease agreement",
                "mandatory": True,
                "description": "Proof of agricultural landholding or tenancy.",
                "purpose": "credit limit assessment",
            }
        ],
        "application_steps": [
            {"instruction": "Apply online via Jansamarth portal or visit your local cooperative/commercial bank."},
            {"instruction": "Submit identity proof and land cultivation documents to obtain KCC credit limit."},
        ],
        "application_url": "https://agricoop.gov.in/",
        "sources": [
            {
                "id": "src_kcc_guidelines",
                "title": "Kisan Credit Card Scheme Guidelines",
                "publisher": "Reserve Bank of India & Department of Agriculture",
                "url": "https://agricoop.gov.in/Documents/kcc_guidelines.pdf",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2019-02-04",
                "section": "Eligibility Criteria",
            }
        ],
    },

    # ---------------------------------------------------------------- Health & Insurance
    {
        "id": "sch_ayushman_pmjay",
        "slug": "ayushman-bharat-pmjay",
        "name": "Ayushman Bharat PM-JAY",
        "summary": (
            "National health protection scheme providing ₹5 lakh cashless secondary "
            "and tertiary hospitalization cover per family per year to eligible households and seniors 70+."
        ),
        "government_level": "central",
        "categories": ["health", "social_security"],
        "beneficiary_groups": ["senior_citizen", "low_income"],
        "jurisdictions": {"scope": "all_india", "state_codes": [], "district_codes": []},
        "effective_from": "2018-09-23",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_pmjay_senior",
                    "field": "age_years",
                    "operator": "gte",
                    "value": 70,
                    "mandatory": True,
                    "explanation": "Senior citizens aged 70 years and above are eligible for dedicated PM-JAY health cover regardless of income.",
                    "source_refs": ["src_pmjay_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "Age Proof / Voter ID / Ration Card",
                "mandatory": True,
                "description": "Document establishing age 70 or above for senior citizen health cover.",
                "purpose": "beneficiary identification",
            }
        ],
        "application_steps": [
            {"instruction": "Visit beneficiary.nha.gov.in or any empaneled hospital / CSC."},
            {"instruction": "Generate Ayushman Vay Vandana card for senior citizens aged 70+."},
        ],
        "application_url": "https://pmjay.gov.in/",
        "sources": [
            {
                "id": "src_pmjay_guidelines",
                "title": "Ayushman Bharat PM-JAY Guidelines, National Health Authority",
                "publisher": "National Health Authority, Ministry of Health and Family Welfare",
                "url": "https://pmjay.gov.in/about/pmjay",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2024-10-29",
                "section": "Universal Health Coverage for Senior Citizens Aged 70+",
            }
        ],
    },
    {
        "id": "sch_pmjjby",
        "slug": "pradhan-mantri-jeevan-jyoti-bima-yojana",
        "name": "Pradhan Mantri Jeevan Jyoti Bima Yojana (PMJJBY)",
        "summary": (
            "Renewable one-year life insurance cover of ₹2 lakh for death due to any "
            "cause to individuals aged 18 to 50 with a bank account."
        ),
        "government_level": "central",
        "categories": ["insurance", "social_security"],
        "beneficiary_groups": ["general"],
        "jurisdictions": {"scope": "all_india", "state_codes": [], "district_codes": []},
        "effective_from": "2015-05-09",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_pmjjby_age_min",
                    "field": "age_years",
                    "operator": "gte",
                    "value": 18,
                    "mandatory": True,
                    "explanation": "Applicant must be at least 18 years of age.",
                    "source_refs": ["src_pmjjby_guidelines"],
                },
                {
                    "criterion_id": "crit_pmjjby_age_max",
                    "field": "age_years",
                    "operator": "lte",
                    "value": 50,
                    "mandatory": True,
                    "explanation": "Applicant must be aged 50 years or younger at entry.",
                    "source_refs": ["src_pmjjby_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "Savings Bank Account / Auto-Debit Consent",
                "mandatory": True,
                "description": "Active bank account for annual premium deduction.",
                "purpose": "premium payment",
            }
        ],
        "application_steps": [
            {"instruction": "Visit your bank branch or use netbanking to give auto-debit consent."},
        ],
        "application_url": "https://financialservices.gov.in/",
        "sources": [
            {
                "id": "src_pmjjby_guidelines",
                "title": "PMJJBY Rules and Guidelines, Department of Financial Services",
                "publisher": "Ministry of Finance, Government of India",
                "url": "https://financialservices.gov.in/insurance-divisions/Government-Sponsored-Socially-Oriented-Insurance-Schemes/Pradhan-Mantri-Jeevan-Jyoti-Bima-Yojana(PMJJBY)",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2015-05-01",
                "section": "Eligibility Criteria",
            }
        ],
    },
    {
        "id": "sch_pmsby",
        "slug": "pradhan-mantri-suraksha-bima-yojana",
        "name": "Pradhan Mantri Suraksha Bima Yojana (PMSBY)",
        "summary": (
            "Affordable accident insurance cover of ₹2 lakh for accidental death and permanent "
            "disability for individuals aged 18 to 70 years."
        ),
        "government_level": "central",
        "categories": ["insurance", "social_security"],
        "beneficiary_groups": ["general"],
        "jurisdictions": {"scope": "all_india", "state_codes": [], "district_codes": []},
        "effective_from": "2015-05-09",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_pmsby_age_min",
                    "field": "age_years",
                    "operator": "gte",
                    "value": 18,
                    "mandatory": True,
                    "explanation": "Applicant must be at least 18 years old.",
                    "source_refs": ["src_pmsby_guidelines"],
                },
                {
                    "criterion_id": "crit_pmsby_age_max",
                    "field": "age_years",
                    "operator": "lte",
                    "value": 70,
                    "mandatory": True,
                    "explanation": "Applicant must be aged 70 years or younger.",
                    "source_refs": ["src_pmsby_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "Bank account passbook",
                "mandatory": True,
                "description": "Active savings account for annual premium deduction.",
                "purpose": "auto-debit enrollment",
            }
        ],
        "application_steps": [
            {"instruction": "Submit enrollment form at your bank branch or via mobile banking app."},
        ],
        "application_url": "https://financialservices.gov.in/",
        "sources": [
            {
                "id": "src_pmsby_guidelines",
                "title": "PMSBY Rules and Guidelines, Department of Financial Services",
                "publisher": "Ministry of Finance, Government of India",
                "url": "https://financialservices.gov.in/insurance-divisions/Government-Sponsored-Socially-Oriented-Insurance-Schemes/Pradhan-Mantri-Suraksha-Bima-Yojana(PMSBY)",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2015-05-01",
                "section": "Eligibility and Terms",
            }
        ],
    },

    # ---------------------------------------------------------------- Pensions & Social Security
    {
        "id": "sch_nsap_ignoaps",
        "slug": "nsap-ignoaps-old-age-pension",
        "name": "NSAP - Indira Gandhi National Old Age Pension Scheme",
        "summary": (
            "Monthly social assistance pension provided to destitute elderly citizens "
            "aged 60 years and above from economically vulnerable households."
        ),
        "government_level": "central",
        "categories": ["pension", "social_security"],
        "beneficiary_groups": ["senior_citizen"],
        "jurisdictions": {"scope": "all_india", "state_codes": [], "district_codes": []},
        "effective_from": "2007-11-19",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_ignoaps_age",
                    "field": "age_years",
                    "operator": "gte",
                    "value": 60,
                    "mandatory": True,
                    "explanation": "Applicant must be 60 years of age or older.",
                    "source_refs": ["src_nsap_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "Age Proof & BPL Certificate / Ration Card",
                "mandatory": True,
                "description": "Proof of age 60+ and BPL household status.",
                "purpose": "pension qualification",
            }
        ],
        "application_steps": [
            {"instruction": "Apply through your local Block Development Office, Municipal Corporation, or CSC."},
        ],
        "application_url": "https://nsap.nic.in/",
        "sources": [
            {
                "id": "src_nsap_guidelines",
                "title": "National Social Assistance Programme (NSAP) Guidelines",
                "publisher": "Ministry of Rural Development, Government of India",
                "url": "https://nsap.nic.in/guidelines.html",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2014-06-01",
                "section": "IGNOAPS Eligibility",
            }
        ],
    },
    {
        "id": "sch_atal_pension",
        "slug": "atal-pension-yojana",
        "name": "Atal Pension Yojana (APY)",
        "summary": (
            "Guaranteed monthly pension (₹1,000 to ₹5,000) from age 60 for unorganised "
            "sector workers joining between 18 and 40 years of age."
        ),
        "government_level": "central",
        "categories": ["pension", "financial_inclusion"],
        "beneficiary_groups": ["unorganised_worker"],
        "jurisdictions": {"scope": "all_india", "state_codes": [], "district_codes": []},
        "effective_from": "2015-05-09",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_apy_age_min",
                    "field": "age_years",
                    "operator": "gte",
                    "value": 18,
                    "mandatory": True,
                    "explanation": "Must be at least 18 years old.",
                    "source_refs": ["src_apy_guidelines"],
                },
                {
                    "criterion_id": "crit_apy_age_max",
                    "field": "age_years",
                    "operator": "lte",
                    "value": 40,
                    "mandatory": True,
                    "explanation": "Must be aged 40 years or younger.",
                    "source_refs": ["src_apy_guidelines"],
                },
                {
                    "criterion_id": "crit_apy_tax_exclusion",
                    "field": "is_income_tax_payer",
                    "operator": "ne",
                    "value": True,
                    "mandatory": False,
                    "explanation": "Income tax payers are not eligible to join APY.",
                    "source_refs": ["src_apy_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "Bank account details",
                "mandatory": True,
                "description": "Savings bank account for monthly auto-debit contribution.",
                "purpose": "pension contribution",
            }
        ],
        "application_steps": [
            {"instruction": "Approach your bank branch to register for Atal Pension Yojana auto-debit."},
        ],
        "application_url": "https://pfrda.org.in/",
        "sources": [
            {
                "id": "src_apy_guidelines",
                "title": "Atal Pension Yojana Operational Guidelines",
                "publisher": "Pension Fund Regulatory and Development Authority (PFRDA)",
                "url": "https://www.pfrda.org.in/index1.cshtml?lsid=103",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2022-08-10",
                "section": "Section 2 - Subscriber Eligibility",
            }
        ],
    },
    {
        "id": "sch_sukanya_samriddhi",
        "slug": "sukanya-samriddhi-yojana",
        "name": "Sukanya Samriddhi Yojana (SSY)",
        "summary": (
            "Small savings scheme for girl children with high interest rates, "
            "tax exemption under 80C, and maturity on attaining age 21 or marriage."
        ),
        "government_level": "central",
        "categories": ["financial_inclusion", "women_and_child"],
        "beneficiary_groups": ["child", "women"],
        "jurisdictions": {"scope": "all_india", "state_codes": [], "district_codes": []},
        "effective_from": "2015-01-22",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_ssy_age",
                    "field": "age_years",
                    "operator": "lte",
                    "value": 10,
                    "mandatory": True,
                    "explanation": "Account can be opened in the name of a girl child aged 10 years or younger.",
                    "source_refs": ["src_ssy_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "Birth Certificate of Girl Child",
                "mandatory": True,
                "description": "Proof of age and identity of the girl child.",
                "purpose": "account opening",
            }
        ],
        "application_steps": [
            {"instruction": "Visit any Post Office or authorized commercial bank branch with parent KYC and child birth certificate."},
        ],
        "application_url": "https://www.indiapost.gov.in/",
        "sources": [
            {
                "id": "src_ssy_guidelines",
                "title": "Sukanya Samriddhi Account Rules",
                "publisher": "Department of Posts & Ministry of Finance, Government of India",
                "url": "https://www.indiapost.gov.in/Financial/Pages/Content/Sukanya-Samriddhi-Account.aspx",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2019-12-12",
                "section": "Eligibility and Opening of Account",
            }
        ],
    },

    # ---------------------------------------------------------------- Housing & Sanitation
    {
        "id": "sch_pmay_gramin",
        "slug": "pmay-gramin",
        "name": "Pradhan Mantri Awaas Yojana - Gramin (PMAY-G)",
        "summary": (
            "Financial assistance of ₹1.20 lakh to ₹1.30 lakh to rural houseless families "
            "and those living in kutcha/dilapidated houses for constructing pucca houses."
        ),
        "government_level": "central",
        "categories": ["housing"],
        "beneficiary_groups": ["low_income", "rural"],
        "jurisdictions": {"scope": "state", "state_codes": ["IN-UP", "IN-WB", "IN-RJ", "IN-PB", "IN-KA", "IN-MH", "IN-TG"], "district_codes": []},
        "effective_from": "2016-11-20",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_pmayg_residence",
                    "field": "residence",
                    "operator": "eq",
                    "value": "rural",
                    "mandatory": True,
                    "explanation": "Applicant must reside in a rural area.",
                    "source_refs": ["src_pmayg_guidelines"],
                },
                {
                    "criterion_id": "crit_pmayg_pucca",
                    "field": "owns_pucca_house",
                    "operator": "eq",
                    "value": False,
                    "mandatory": True,
                    "explanation": "Beneficiary household must not own a pucca house anywhere in India.",
                    "source_refs": ["src_pmayg_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "BPL Card / SECC Data Verification / Land Ownership Proof",
                "mandatory": True,
                "description": "Proof of rural housing deprivation and house site availability.",
                "purpose": "housing assistance",
            }
        ],
        "application_steps": [
            {"instruction": "Contact your Gram Panchayat or Block Development Officer to check inclusion in the PMAY-G Awaas+ list."},
        ],
        "application_url": "https://pmayg.nic.in/",
        "sources": [
            {
                "id": "src_pmayg_guidelines",
                "title": "Pradhan Mantri Awaas Yojana - Gramin Framework for Implementation",
                "publisher": "Ministry of Rural Development, Government of India",
                "url": "https://pmayg.nic.in/netiay/home.aspx",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2016-04-01",
                "section": "Selection of Beneficiaries",
            }
        ],
    },
    {
        "id": "sch_pmay_urban",
        "slug": "pmay-urban",
        "name": "Pradhan Mantri Awaas Yojana - Urban (PMAY-U)",
        "summary": (
            "Credit-linked subsidy and affordable housing assistance for urban Economically "
            "Weaker Sections (EWS) and Low-Income Groups (LIG) who do not own a pucca house."
        ),
        "government_level": "central",
        "categories": ["housing"],
        "beneficiary_groups": ["low_income", "urban"],
        "jurisdictions": {"scope": "state", "state_codes": ["IN-MH", "IN-TG", "IN-UP"], "district_codes": []},
        "effective_from": "2015-06-25",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_pmayu_residence",
                    "field": "residence",
                    "operator": "eq",
                    "value": "urban",
                    "mandatory": True,
                    "explanation": "Must reside in a statutory town or notified urban planning area.",
                    "source_refs": ["src_pmayu_guidelines"],
                },
                {
                    "criterion_id": "crit_pmayu_pucca",
                    "field": "owns_pucca_house",
                    "operator": "eq",
                    "value": False,
                    "mandatory": True,
                    "explanation": "Family must not own a pucca house in any part of India.",
                    "source_refs": ["src_pmayu_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "Income Certificate & Urban Domicile Proof",
                "mandatory": True,
                "description": "Proof of urban residence and income eligibility.",
                "purpose": "housing subsidy",
            }
        ],
        "application_steps": [
            {"instruction": "Apply online at pmay-urban.gov.in or visit the nearest ULB office."},
        ],
        "application_url": "https://pmay-urban.gov.in/",
        "sources": [
            {
                "id": "src_pmayu_guidelines",
                "title": "PMAY-U Scheme Guidelines",
                "publisher": "Ministry of Housing and Urban Affairs, Government of India",
                "url": "https://pmay-urban.gov.in/about",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2015-06-25",
                "section": "Eligibility of Beneficiaries",
            }
        ],
    },
    {
        "id": "sch_sbm_gramin",
        "slug": "swachh-bharat-mission-gramin",
        "name": "Swachh Bharat Mission - Gramin (SBM-G)",
        "summary": (
            "Financial incentive of ₹12,000 for constructing individual household latrines "
            "(IHHL) to achieve open-defecation-free status in rural India."
        ),
        "government_level": "central",
        "categories": ["housing", "health"],
        "beneficiary_groups": ["rural", "low_income"],
        "jurisdictions": {"scope": "state", "state_codes": ["IN-UP", "IN-WB", "IN-RJ", "IN-PB"], "district_codes": []},
        "effective_from": "2014-10-02",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_sbmg_rural",
                    "field": "residence",
                    "operator": "eq",
                    "value": "rural",
                    "mandatory": True,
                    "explanation": "Applicant must reside in a rural village.",
                    "source_refs": ["src_sbmg_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "Bank account passbook & Ration card",
                "mandatory": True,
                "description": "Bank account for IHHL incentive DBT transfer.",
                "purpose": "incentive transfer",
            }
        ],
        "application_steps": [
            {"instruction": "Apply online at sbm.gov.in or submit an application to the Gram Panchayat."},
        ],
        "application_url": "https://swachhbharatmission.ddws.gov.in/",
        "sources": [
            {
                "id": "src_sbmg_guidelines",
                "title": "Swachh Bharat Mission (Gramin) Phase II Guidelines",
                "publisher": "Department of Drinking Water and Sanitation, Ministry of Jal Shakti",
                "url": "https://swachhbharatmission.ddws.gov.in/about-us",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2020-02-19",
                "section": "Individual Household Latrines (IHHL)",
            }
        ],
    },

    # ---------------------------------------------------------------- Employment & Livelihood
    {
        "id": "sch_pm_svanidhi",
        "slug": "pm-svanidhi",
        "name": "PM SVANidhi (Street Vendor's AtmaNirbhar Nidhi)",
        "summary": (
            "Working capital micro-credit loan scheme for urban street vendors "
            "to restart and expand their micro-businesses."
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
                {
                    "criterion_id": "crit_svanidhi_residence",
                    "field": "residence",
                    "operator": "eq",
                    "value": "urban",
                    "mandatory": False,
                    "explanation": "Street vending operations must be situated in an urban local body area.",
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
    {
        "id": "sch_mgnrega",
        "slug": "mgnrega",
        "name": "Mahatma Gandhi National Rural Employment Guarantee Scheme (MGNREGA)",
        "summary": (
            "Guarantees 100 days of wage employment in a financial year to every rural "
            "household whose adult members volunteer to do unskilled manual work."
        ),
        "government_level": "central",
        "categories": ["employment", "social_security"],
        "beneficiary_groups": ["rural", "daily_wage"],
        "jurisdictions": {"scope": "state", "state_codes": ["IN-WB", "IN-UP", "IN-KA", "IN-RJ", "IN-PB"], "district_codes": []},
        "effective_from": "2006-02-02",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_mgnrega_rural",
                    "field": "residence",
                    "operator": "eq",
                    "value": "rural",
                    "mandatory": True,
                    "explanation": "Applicant household must reside in a rural area.",
                    "source_refs": ["src_mgnrega_guidelines"],
                },
                {
                    "criterion_id": "crit_mgnrega_age",
                    "field": "age_years",
                    "operator": "gte",
                    "value": 18,
                    "mandatory": True,
                    "explanation": "Applicant must be an adult aged 18 years or older.",
                    "source_refs": ["src_mgnrega_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "Job Card / Gram Panchayat Registration",
                "mandatory": True,
                "description": "MGNREGA Job Card issued by local Gram Panchayat.",
                "purpose": "work demand and muster roll",
            }
        ],
        "application_steps": [
            {"instruction": "Submit an oral or written application for a Job Card at the local Gram Panchayat."},
        ],
        "application_url": "https://nrega.nic.in/",
        "sources": [
            {
                "id": "src_mgnrega_guidelines",
                "title": "MGNREGA Operational Guidelines",
                "publisher": "Ministry of Rural Development, Government of India",
                "url": "https://nrega.nic.in/Nregahome/MGNREGA_new/Guidelines.html",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2013-02-01",
                "section": "Chapter 2 - Job Cards and Employment Allocation",
            }
        ],
    },
    {
        "id": "sch_pmegp",
        "slug": "prime-ministers-employment-generation-programme",
        "name": "Prime Minister's Employment Generation Programme (PMEGP)",
        "summary": (
            "Credit-linked subsidy scheme offering 15% to 35% margin money subsidy "
            "for establishing micro-enterprises in non-farm manufacturing and service sectors."
        ),
        "government_level": "central",
        "categories": ["employment", "financial_inclusion"],
        "beneficiary_groups": ["self_employed"],
        "jurisdictions": {"scope": "all_india", "state_codes": [], "district_codes": []},
        "effective_from": "2008-08-15",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_pmegp_age",
                    "field": "age_years",
                    "operator": "gte",
                    "value": 18,
                    "mandatory": True,
                    "explanation": "Applicant must be at least 18 years old.",
                    "source_refs": ["src_pmegp_guidelines"],
                },
                {
                    "criterion_id": "crit_pmegp_nonfarm",
                    "field": "is_farmer",
                    "operator": "eq",
                    "value": False,
                    "mandatory": True,
                    "explanation": "PMEGP supports new micro-enterprises in the non-farm sector.",
                    "source_refs": ["src_pmegp_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "Detailed Project Report (DPR) & Educational Certificate",
                "mandatory": True,
                "description": "Project proposal and proof of passing 8th standard for projects above threshold.",
                "purpose": "project sanction",
            }
        ],
        "application_steps": [
            {"instruction": "Submit application online on the KVIC PMEGP e-Portal (kviconline.gov.in)."},
        ],
        "application_url": "https://www.kviconline.gov.in/",
        "sources": [
            {
                "id": "src_pmegp_guidelines",
                "title": "PMEGP Scheme Guidelines",
                "publisher": "Khadi and Village Industries Commission, Ministry of MSME",
                "url": "https://www.kviconline.gov.in/pmegpeportal/pmegphome/index.jsp",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2022-05-30",
                "section": "Eligibility Criteria for Beneficiaries",
            }
        ],
    },
    {
        "id": "sch_pm_mudra",
        "slug": "pradhan-mantri-mudra-yojana",
        "name": "Pradhan Mantri Mudra Yojana (PMMY)",
        "summary": (
            "Collateral-free loans up to ₹20 lakh for non-corporate, non-farm small "
            "and micro enterprises under Shishu, Kishore, and Tarun categories."
        ),
        "government_level": "central",
        "categories": ["employment", "financial_inclusion"],
        "beneficiary_groups": ["self_employed"],
        "jurisdictions": {"scope": "all_india", "state_codes": [], "district_codes": []},
        "effective_from": "2015-04-08",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_mudra_age",
                    "field": "age_years",
                    "operator": "gte",
                    "value": 18,
                    "mandatory": True,
                    "explanation": "Applicant must be an Indian citizen of at least 18 years of age.",
                    "source_refs": ["src_mudra_guidelines"],
                },
                {
                    "criterion_id": "crit_mudra_nonfarm",
                    "field": "is_farmer",
                    "operator": "eq",
                    "value": False,
                    "mandatory": True,
                    "explanation": "Mudra loans cater to non-farm revenue-generating micro-enterprises.",
                    "source_refs": ["src_mudra_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "Business Plan & Proof of Identity",
                "mandatory": True,
                "description": "Proof of identity and proposed business activity description.",
                "purpose": "micro-loan appraisal",
            }
        ],
        "application_steps": [
            {"instruction": "Apply through any commercial bank, RRB, MFI, or via the Udyamimitra portal."},
        ],
        "application_url": "https://www.mudra.org.in/",
        "sources": [
            {
                "id": "src_mudra_guidelines",
                "title": "PMMY Guidelines and Loan Categories",
                "publisher": "Micro Units Development and Refinance Agency, Department of Financial Services",
                "url": "https://www.mudra.org.in/Offerings",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2015-04-08",
                "section": "Eligibility of Micro Enterprises",
            }
        ],
    },

    # ---------------------------------------------------------------- Education & Scholarships
    {
        "id": "sch_post_matric_scholarship",
        "slug": "post-matric-scholarship-sc-st-obc",
        "name": "Post-Matric Scholarship Scheme",
        "summary": (
            "Financial support covering tuition fees and maintenance allowance for "
            "students from disadvantaged social categories enrolled in post-secondary education."
        ),
        "government_level": "central",
        "categories": ["education"],
        "beneficiary_groups": ["student"],
        "jurisdictions": {"scope": "state", "state_codes": ["IN-MH", "IN-TG", "IN-UP"], "district_codes": []},
        "effective_from": "2018-04-01",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_pms_student",
                    "field": "is_student",
                    "operator": "eq",
                    "value": True,
                    "mandatory": True,
                    "explanation": "Applicant must currently be a student enrolled in a recognized institution.",
                    "source_refs": ["src_pms_guidelines"],
                },
                {
                    "criterion_id": "crit_pms_enrollment",
                    "field": "current_enrollment",
                    "operator": "eq",
                    "value": True,
                    "mandatory": True,
                    "explanation": "Must be actively enrolled in post-matric studies.",
                    "source_refs": ["src_pms_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "College Bonafide Certificate & Marksheet",
                "mandatory": True,
                "description": "Proof of current post-matric institutional enrollment.",
                "purpose": "scholarship disbursement",
            }
        ],
        "application_steps": [
            {"instruction": "Apply online through the National Scholarship Portal (scholarships.gov.in)."},
        ],
        "application_url": "https://scholarships.gov.in/",
        "sources": [
            {
                "id": "src_pms_guidelines",
                "title": "Centrally Sponsored Post Matric Scholarship Guidelines",
                "publisher": "Ministry of Social Justice and Empowerment, Government of India",
                "url": "https://scholarships.gov.in/public/schemeGuidelines/Post_Matric_Scholarship_Guidelines.pdf",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2021-03-31",
                "section": "Eligibility Criteria",
            }
        ],
    },
    {
        "id": "sch_nmms_scholarship",
        "slug": "national-means-cum-merit-scholarship",
        "name": "National Means-cum-Merit Scholarship Scheme (NMMSS)",
        "summary": (
            "Annual scholarship of ₹12,000 for meritorious students from economically "
            "weaker sections to prevent dropout at class 8 and encourage secondary schooling."
        ),
        "government_level": "central",
        "categories": ["education"],
        "beneficiary_groups": ["student", "child"],
        "jurisdictions": {"scope": "all_india", "state_codes": [], "district_codes": []},
        "effective_from": "2008-05-01",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_nmms_age",
                    "field": "age_years",
                    "operator": "lte",
                    "value": 15,
                    "mandatory": True,
                    "explanation": "Applicant must be a school student aged 15 years or younger.",
                    "source_refs": ["src_nmms_guidelines"],
                },
                {
                    "criterion_id": "crit_nmms_student",
                    "field": "is_student",
                    "operator": "eq",
                    "value": True,
                    "mandatory": True,
                    "explanation": "Must be currently studying in government or government-aided school.",
                    "source_refs": ["src_nmms_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "Class 8 marksheet & School Verification Certificate",
                "mandatory": True,
                "description": "Proof of passing class 7/8 with qualifying marks.",
                "purpose": "scholarship selection",
            }
        ],
        "application_steps": [
            {"instruction": "Register and apply via the National Scholarship Portal (scholarships.gov.in)."},
        ],
        "application_url": "https://scholarships.gov.in/",
        "sources": [
            {
                "id": "src_nmms_guidelines",
                "title": "National Means-cum-Merit Scholarship Scheme Guidelines",
                "publisher": "Department of School Education and Literacy, Ministry of Education",
                "url": "https://scholarships.gov.in/public/schemeGuidelines/NMMSS_Guidelines.pdf",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2022-04-01",
                "section": "Eligibility and Quota Allocation",
            }
        ],
    },

    # ---------------------------------------------------------------- Women & Child Welfare
    {
        "id": "sch_pm_ujjwala",
        "slug": "pradhan-mantri-ujjwala-yojana",
        "name": "Pradhan Mantri Ujjwala Yojana (PMUY)",
        "summary": (
            "Deposit-free LPG cylinder connection with financial support of ₹1,600 "
            "provided to adult women from poor and vulnerable households."
        ),
        "government_level": "central",
        "categories": ["women_and_child", "social_security"],
        "beneficiary_groups": ["women", "low_income"],
        "jurisdictions": {"scope": "state", "state_codes": ["IN-UP", "IN-WB", "IN-KA", "IN-RJ"], "district_codes": []},
        "effective_from": "2016-05-01",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_pmuy_gender",
                    "field": "gender",
                    "operator": "eq",
                    "value": "female",
                    "mandatory": True,
                    "explanation": "LPG connection is issued only in the name of an adult female member.",
                    "source_refs": ["src_pmuy_guidelines"],
                },
                {
                    "criterion_id": "crit_pmuy_age",
                    "field": "age_years",
                    "operator": "gte",
                    "value": 18,
                    "mandatory": True,
                    "explanation": "Applicant must have attained 18 years of age.",
                    "source_refs": ["src_pmuy_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "BPL Ration Card & Bank Account Details",
                "mandatory": True,
                "description": "Proof of household deprivation and active bank account.",
                "purpose": "connection release",
            }
        ],
        "application_steps": [
            {"instruction": "Apply online at pmuy.gov.in or visit any local LPG distributorship."},
        ],
        "application_url": "https://www.pmuy.gov.in/",
        "sources": [
            {
                "id": "src_pmuy_guidelines",
                "title": "Pradhan Mantri Ujjwala Yojana 2.0 Guidelines",
                "publisher": "Ministry of Petroleum and Natural Gas, Government of India",
                "url": "https://www.pmuy.gov.in/about.html",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2021-08-10",
                "section": "Eligibility Criteria for Ujjwala Beneficiaries",
            }
        ],
    },
    {
        "id": "sch_pmmvy",
        "slug": "pradhan-mantri-matru-vandana-yojana",
        "name": "Pradhan Mantri Matru Vandana Yojana (PMMVY)",
        "summary": (
            "Direct cash benefit of ₹5,000 in installments to pregnant women and lactating "
            "mothers for first living child towards nutrition and wage compensation."
        ),
        "government_level": "central",
        "categories": ["women_and_child", "health"],
        "beneficiary_groups": ["women"],
        "jurisdictions": {"scope": "state", "state_codes": ["IN-UP", "IN-WB", "IN-MH", "IN-TG", "IN-RJ"], "district_codes": []},
        "effective_from": "2017-01-01",
        "effective_to": None,
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "crit_pmmvy_gender",
                    "field": "gender",
                    "operator": "eq",
                    "value": "female",
                    "mandatory": True,
                    "explanation": "Beneficiary must be a pregnant woman or lactating mother.",
                    "source_refs": ["src_pmmvy_guidelines"],
                },
                {
                    "criterion_id": "crit_pmmvy_age",
                    "field": "age_years",
                    "operator": "gte",
                    "value": 19,
                    "mandatory": True,
                    "explanation": "Applicant must be at least 19 years old at the time of pregnancy.",
                    "source_refs": ["src_pmmvy_guidelines"],
                },
            ]
        },
        "documents": [
            {
                "name": "Mother and Child Protection (MCP) Card",
                "mandatory": True,
                "description": "Proof of ante-natal check-up and institutional registration.",
                "purpose": "maternity incentive",
            }
        ],
        "application_steps": [
            {"instruction": "Register at the nearest Anganwadi Centre (AWC) or approved health facility / pmmvy.wcd.gov.in."},
        ],
        "application_url": "https://pmmvy.wcd.gov.in/",
        "sources": [
            {
                "id": "src_pmmvy_guidelines",
                "title": "PMMVY Scheme Implementation Guidelines",
                "publisher": "Ministry of Women and Child Development, Government of India",
                "url": "https://pmmvy.wcd.gov.in/about-us",
                "source_type": "official_guideline",
                "official_status": "official",
                "access_date": "2025-01-15",
                "publication_date": "2022-07-14",
                "section": "Beneficiary Eligibility and Verification",
            }
        ],
    },
]


def seed_database() -> int:
    """Insert jurisdiction data and publish sample scheme records if absent."""
    backend_dir = Path(__file__).resolve().parents[1]
    db_file = backend_dir / "claim_whats_yours.db"
    settings = get_settings()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        db_url = f"sqlite:///{db_file}"

    factory = get_session_factory(db_url)
    now = datetime.now(UTC)

    data_path = backend_dir / "data" / "jurisdictions.json"
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
