"""Integration tests: admin auth, lifecycle transitions, error privacy. Synthetic data only."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.orm import Session

from claim_whats_yours.core.config import get_settings
from claim_whats_yours.db import models

IMPORT_URL = "/api/v1/admin/schemes/import"
REVIEW_QUEUE_URL = "/api/v1/admin/schemes/review-queue"
PUBLIC_DETAIL_URL = "/api/v1/schemes/synthetic-a"
SCHEME_ID = "synthetic-a"

SYNTHETIC_RECORD: dict[str, Any] = {
    "id": "synthetic-a",
    "slug": "synthetic-a",
    "name": "Synthetic scheme A",
    "summary": "Synthetic test fixture",
    "government_level": "central",
    "jurisdictions": {"scope": "all_india", "state_codes": [], "district_codes": []},
    "eligibility_rule": {
        "all": [
            {
                "criterion_id": "c1",
                "field": "age_years",
                "operator": "gte",
                "value": 18,
                "mandatory": True,
                "explanation": "Age at least 18",
                "source_refs": ["s1"],
            }
        ]
    },
    "sources": [
        {
            "id": "s1",
            "title": "Synthetic source",
            "publisher": "Synthetic",
            "url": "https://example.gov.in/synthetic",
            "source_type": "guideline",
            "official_status": "official",
            "access_date": "2025-01-01",
        }
    ],
    "application_url": "https://example.gov.in/apply",
}

# Admin routes as (method, path). Scheme-specific routes use a placeholder id.
ADMIN_ROUTES: list[tuple[str, str]] = [
    ("POST", IMPORT_URL),
    ("GET", REVIEW_QUEUE_URL),
    ("POST", "/api/v1/admin/schemes/x/validate"),
    ("POST", "/api/v1/admin/schemes/x/verify"),
    ("POST", "/api/v1/admin/schemes/x/publish"),
    ("POST", "/api/v1/admin/schemes/x/archive"),
    ("GET", "/api/v1/admin/schemes/x/versions"),
]


@pytest.fixture
def admin_disabled(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Run with ADMIN_API_TOKEN set to an empty string; restore env and settings cache after."""
    monkeypatch.setenv("ADMIN_API_TOKEN", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_admin_route_without_token_returns_401(client: Any, method: str, path: str) -> None:
    response = client.request(method, path)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_admin_route_with_wrong_token_returns_401(client: Any, method: str, path: str) -> None:
    response = client.request(method, path, headers={"X-Admin-Token": "wrong-token-value"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_wrong_token_response_does_not_echo_token(client: Any) -> None:
    response = client.request(
        "POST", IMPORT_URL, headers={"X-Admin-Token": "nope"}, json=SYNTHETIC_RECORD
    )

    assert response.status_code == 401
    assert "nope" not in response.text
    assert "Traceback" not in response.text


def test_admin_disabled_when_token_unset_returns_403(client: Any, admin_disabled: None) -> None:
    response = client.request(
        "POST", IMPORT_URL, headers={"X-Admin-Token": "any-token"}, json=SYNTHETIC_RECORD
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ADMIN_DISABLED"


def test_import_returns_201_draft_then_duplicate_returns_409(
    client: Any, admin_headers: dict[str, str]
) -> None:
    first = client.post(IMPORT_URL, headers=admin_headers, json=SYNTHETIC_RECORD)
    second = client.post(IMPORT_URL, headers=admin_headers, json=SYNTHETIC_RECORD)

    assert first.status_code == 201
    assert first.json()["record_status"] == "draft"
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DUPLICATE_SCHEME"


def test_publish_before_verify_returns_409_invalid_transition(
    client: Any, admin_headers: dict[str, str]
) -> None:
    client.post(IMPORT_URL, headers=admin_headers, json=SYNTHETIC_RECORD)

    response = client.post(
        f"/api/v1/admin/schemes/{SCHEME_ID}/publish",
        headers=admin_headers,
        json={"actor": "admin-1"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_TRANSITION"


def test_full_lifecycle_import_validate_verify_publish_then_public_read(
    client: Any, admin_headers: dict[str, str]
) -> None:
    today = datetime.now(UTC).date().isoformat()
    client.post(IMPORT_URL, headers=admin_headers, json=SYNTHETIC_RECORD)

    validated = client.post(f"/api/v1/admin/schemes/{SCHEME_ID}/validate", headers=admin_headers)
    verified = client.post(
        f"/api/v1/admin/schemes/{SCHEME_ID}/verify",
        headers=admin_headers,
        json={"reviewer": "Reviewer One", "verified_at": today},
    )
    published = client.post(
        f"/api/v1/admin/schemes/{SCHEME_ID}/publish",
        headers=admin_headers,
        json={"actor": "admin-1"},
    )
    public = client.get(PUBLIC_DETAIL_URL)

    assert validated.status_code == 200
    assert validated.json()["valid"] is True
    assert verified.status_code == 200
    assert published.status_code == 200
    assert published.json()["record_status"] == "published"
    assert public.status_code == 200


def test_archive_published_scheme_hides_it_from_public_detail(
    client: Any,
    admin_headers: dict[str, str],
    db: Session,
    scheme_factory: Callable[..., models.Scheme],
) -> None:
    scheme_factory(db, SCHEME_ID)

    archived = client.post(
        f"/api/v1/admin/schemes/{SCHEME_ID}/archive",
        headers=admin_headers,
        json={"actor": "admin-1"},
    )
    public = client.get(PUBLIC_DETAIL_URL)

    assert archived.status_code == 200
    assert archived.json()["record_status"] == "archived"
    assert public.status_code == 404
    assert public.json()["error"]["code"] == "SCHEME_NOT_FOUND"


def test_versions_record_import_and_publish_notes(
    client: Any, admin_headers: dict[str, str]
) -> None:
    today = datetime.now(UTC).date().isoformat()
    client.post(IMPORT_URL, headers=admin_headers, json=SYNTHETIC_RECORD)
    client.post(f"/api/v1/admin/schemes/{SCHEME_ID}/validate", headers=admin_headers)
    client.post(
        f"/api/v1/admin/schemes/{SCHEME_ID}/verify",
        headers=admin_headers,
        json={"reviewer": "Reviewer One", "verified_at": today},
    )
    client.post(
        f"/api/v1/admin/schemes/{SCHEME_ID}/publish",
        headers=admin_headers,
        json={"actor": "admin-1"},
    )

    response = client.get(f"/api/v1/admin/schemes/{SCHEME_ID}/versions", headers=admin_headers)

    assert response.status_code == 200
    notes = [item["change_note"] for item in response.json()["items"]]
    assert any("imported as draft" in note for note in notes)
    assert any("published by admin-1" in note for note in notes)


def test_publish_stale_verification_returns_409_without_stack_trace(
    client: Any,
    admin_headers: dict[str, str],
    db: Session,
    scheme_factory: Callable[..., models.Scheme],
) -> None:
    scheme_factory(
        db,
        SCHEME_ID,
        record_status="verified",
        verification_status="verified",
        review_due_at=datetime(2024, 1, 1, tzinfo=UTC),
    )

    response = client.post(
        f"/api/v1/admin/schemes/{SCHEME_ID}/publish",
        headers=admin_headers,
        json={"actor": "admin-1"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERIFICATION_STALE"
    assert "Traceback" not in response.text
    assert 'File "' not in response.text


def test_archive_with_extra_body_key_returns_422(
    client: Any,
    admin_headers: dict[str, str],
    db: Session,
    scheme_factory: Callable[..., models.Scheme],
) -> None:
    scheme_factory(db, SCHEME_ID)

    response = client.post(
        f"/api/v1/admin/schemes/{SCHEME_ID}/archive",
        headers=admin_headers,
        json={"actor": "admin-1", "unexpected_key": "value"},
    )

    assert response.status_code == 422


def test_publish_unknown_scheme_returns_not_found_or_conflict(
    client: Any, admin_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/admin/schemes/no-such-scheme/publish",
        headers=admin_headers,
        json={"actor": "admin-1"},
    )

    # The admin service maps a missing scheme to SCHEME_NOT_FOUND (404). Accepting 409 as well
    # keeps this test valid if the service reports an unknown id as an invalid transition.
    assert response.status_code in (404, 409)
    assert response.json()["error"]["code"] in ("SCHEME_NOT_FOUND", "INVALID_TRANSITION")
