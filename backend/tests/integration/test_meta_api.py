"""Integration tests for the metadata endpoints: jurisdictions and profile fields."""

from __future__ import annotations

from typing import Any

JURISDICTIONS_URL = "/api/v1/meta/jurisdictions"
PROFILE_FIELDS_URL = "/api/v1/meta/profile-fields"

FORBIDDEN_FIELDS = {
    "aadhaar",
    "pan",
    "bank_account",
    "password",
    "phone",
    "email",
    "government_id",
}


def test_jurisdictions_returns_envelope_and_items(client: Any) -> None:
    response = client.get(JURISDICTIONS_URL)

    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "jurisdictions" in body
    assert body["page"] == 1
    assert body["page_size"] == 100
    assert body["total"] > 0
    assert len(body["items"]) == body["total"]


def test_jurisdictions_filter_by_level_central(client: Any) -> None:
    response = client.get(JURISDICTIONS_URL, params={"level": "central"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    for item in body["items"]:
        assert item["level"] in ("central", "all_india")


def test_jurisdictions_filter_by_level_state(client: Any) -> None:
    response = client.get(JURISDICTIONS_URL, params={"level": "state"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 28
    for item in body["items"]:
        assert item["level"] == "state"


def test_jurisdictions_filter_by_parent_code(client: Any) -> None:
    response = client.get(JURISDICTIONS_URL, params={"parent_code": "IN-AP"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] > 0
    for item in body["items"]:
        assert item["parent_code"] == "IN-AP"
        assert item["level"] == "district"


def test_jurisdictions_pagination(client: Any) -> None:
    response = client.get(JURISDICTIONS_URL, params={"page": 2, "page_size": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 2
    assert body["page_size"] == 5
    assert len(body["items"]) == 5


def test_profile_fields_returns_envelope_and_items(client: Any) -> None:
    response = client.get(PROFILE_FIELDS_URL)

    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "fields" in body
    assert body["page"] == 1
    assert body["page_size"] == 100
    assert body["total"] > 0
    assert len(body["items"]) == body["total"]


def test_profile_fields_never_contain_forbidden_identifiers(client: Any) -> None:
    response = client.get(PROFILE_FIELDS_URL)

    assert response.status_code == 200
    body = response.json()
    for item in body["items"]:
        field_id = item.get("id", "").lower()
        field_key = item.get("key", "").lower()
        assert field_id not in FORBIDDEN_FIELDS
        assert field_key not in FORBIDDEN_FIELDS


def test_profile_fields_pagination(client: Any) -> None:
    response = client.get(PROFILE_FIELDS_URL, params={"page": 1, "page_size": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert len(body["items"]) == 5
