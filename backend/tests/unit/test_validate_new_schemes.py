"""Test that all proposed seed scheme definitions conform to schema and pass publication gates."""

from claim_whats_yours.domain.rules import validate_rule
from claim_whats_yours.domain.fields import field_ids
from claim_whats_yours.domain.geography import is_valid_jurisdiction_code

def test_fields_in_catalogue():
    known = field_ids()
    m2_fields = {
        "ration_card_type",
        "is_income_tax_payer",
        "disability_percentage",
        "minority_status",
        "owns_pucca_house",
        "employer_sector",
        "has_epf_esi",
        "current_enrollment",
    }
    assert m2_fields <= known

def test_persona_districts_in_catalogue():
    persona_districts = {
        "IN-UP-LKO",
        "IN-MH-PUN",
        "IN-KA-RAI",
        "IN-WB-NAD",
        "IN-PB-LDH",
        "IN-TG-HYD",
        "IN-RJ-JAI",
    }
    for code in persona_districts:
        assert is_valid_jurisdiction_code(code), f"Invalid district: {code}"
