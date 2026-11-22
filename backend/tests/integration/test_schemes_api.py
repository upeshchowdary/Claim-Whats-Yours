"""Integration tests for the public scheme list and detail endpoints. Synthetic data only."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy.orm import Session

from claim_whats_yours.db import models

LIST_URL = "/api/v1/schemes"


def _ids(response: Any) -> set[str]:
    return {item["id"] for item in response.json()["items"]}


def test_list_returns_only_published_schemes(
    client: Any, db: Session, scheme_factory: Callable[..., models.Scheme]
) -> None:
    scheme_factory(db, "pub-one")
    scheme_factory(db, "draft-one", record_status="draft")

    response = client.get(LIST_URL)

    assert response.status_code == 200
    ids = _ids(response)
    assert "pub-one" in ids
    assert "draft-one" not in ids


def test_pagination_second_page_has_one_item_and_total(
    client: Any, db: Session, scheme_factory: Callable[..., models.Scheme]
) -> None:
    scheme_factory(db, "page-a")
    scheme_factory(db, "page-b")

    response = client.get(LIST_URL, params={"page_size": 1, "page": 2})

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["total"] == 2


@pytest.mark.parametrize(
    "params",
    [{"page_size": 0}, {"page_size": 101}, {"page": 0}],
)
def test_invalid_pagination_returns_422(client: Any, params: dict[str, int]) -> None:
    response = client.get(LIST_URL, params=params)

    assert response.status_code == 422


def test_status_draft_filter_is_rejected(client: Any) -> None:
    response = client.get(LIST_URL, params={"status": "draft"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_QUERY"


def test_state_filter_includes_state_and_all_india_schemes(
    client: Any, db: Session, scheme_factory: Callable[..., models.Scheme]
) -> None:
    scheme_factory(db, "all-india-one")
    scheme_factory(
        db,
        "ap-state-one",
        scope="state",
        state_codes=("IN-AP",),
        government_level="state",
    )

    response = client.get(LIST_URL, params={"state_code": "IN-AP"})

    assert response.status_code == 200
    ids = _ids(response)
    assert "ap-state-one" in ids
    assert "all-india-one" in ids


def test_state_filter_excludes_other_state_scheme(
    client: Any, db: Session, scheme_factory: Callable[..., models.Scheme]
) -> None:
    scheme_factory(
        db,
        "ap-state-only",
        scope="state",
        state_codes=("IN-AP",),
        government_level="state",
    )

    response = client.get(LIST_URL, params={"state_code": "IN-KA"})

    assert response.status_code == 200
    assert "ap-state-only" not in _ids(response)


def test_unknown_state_code_returns_422(client: Any) -> None:
    response = client.get(LIST_URL, params={"state_code": "IN-XX"})

    assert response.status_code == 422


def test_query_matches_name_token(
    client: Any, db: Session, scheme_factory: Callable[..., models.Scheme]
) -> None:
    scheme_factory(db, "alpha-scheme")
    scheme_factory(db, "beta-scheme")

    response = client.get(LIST_URL, params={"q": "alpha"})

    assert response.status_code == 200
    ids = _ids(response)
    assert "alpha-scheme" in ids
    assert "beta-scheme" not in ids


def test_category_filter_selects_matching_schemes(
    client: Any, db: Session, scheme_factory: Callable[..., models.Scheme]
) -> None:
    scheme_factory(db, "health-one", categories=("health",))
    scheme_factory(db, "edu-one", categories=("education",))

    response = client.get(LIST_URL, params={"category": "health"})

    assert response.status_code == 200
    ids = _ids(response)
    assert "health-one" in ids
    assert "edu-one" not in ids


def test_detail_returns_published_scheme_with_sources(
    client: Any, db: Session, scheme_factory: Callable[..., models.Scheme]
) -> None:
    scheme_factory(db, "detail-ok")

    response = client.get(f"{LIST_URL}/detail-ok")

    assert response.status_code == 200
    assert "sources" in response.json()
    assert "Traceback" not in response.text


@pytest.mark.parametrize("target", ["draft-only", "no-such-scheme"])
def test_detail_missing_or_draft_returns_404(
    client: Any,
    db: Session,
    scheme_factory: Callable[..., models.Scheme],
    target: str,
) -> None:
    scheme_factory(db, "draft-only", record_status="draft")

    response = client.get(f"{LIST_URL}/{target}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SCHEME_NOT_FOUND"
    assert "Traceback" not in response.text
