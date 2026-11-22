"""Read-only scheme queries for published schemes.

Layering: services call db and domain; no FastAPI imports. Functions never commit
or add rows.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from claim_whats_yours.db.models import Scheme, SchemeJurisdiction
from claim_whats_yours.domain.geography import district_parent_state

PUBLISHED = "published"


def _payload_dict(scheme: Scheme) -> dict[str, Any]:
    """Return the payload as a dict, or an empty dict when it is not a JSON object."""
    payload = scheme.payload
    return payload if isinstance(payload, dict) else {}


def _payload_list(scheme: Scheme, key: str) -> list[str]:
    """Return a list-valued payload key, defaulting to an empty list."""
    value = _payload_dict(scheme).get(key)
    return list(value) if isinstance(value, list) else []


def _tokens(q: str | None) -> list[str]:
    """Lowercase the query and split it on whitespace."""
    return q.lower().split() if q else []


def _name_hits(scheme: Scheme, tokens: list[str]) -> int:
    """Count how many query tokens occur in the scheme name."""
    name = scheme.name.lower()
    return sum(1 for token in tokens if token in name)


def _apply_text_filter(stmt: Select[tuple[Scheme]], tokens: list[str]) -> Select[tuple[Scheme]]:
    """Require every token to occur in name or summary (case-insensitive, LIKE-escaped)."""
    for token in tokens:
        stmt = stmt.where(
            or_(
                func.lower(Scheme.name).contains(token, autoescape=True),
                func.lower(Scheme.summary).contains(token, autoescape=True),
            )
        )
    return stmt


def list_published_schemes(
    session: Session,
    q: str | None,
    government_level: str | list[str] | None,
    state_code: str | None,
    district_code: str | None,
    category: str | list[str] | None,
    beneficiary_group: str | list[str] | None,
    page: int,
    page_size: int,
) -> tuple[list[Scheme], int]:
    """Return one page of published schemes matching the filters, plus the total count."""
    tokens = _tokens(q)
    stmt = select(Scheme).where(Scheme.record_status == PUBLISHED)
    stmt = _apply_text_filter(stmt, tokens)

    if isinstance(government_level, str):
        levels = [government_level]
    elif government_level is not None:
        levels = list(government_level)
    else:
        levels = []

    if levels:
        stmt = stmt.where(Scheme.government_level.in_(levels))

    if district_code is not None:
        parent_state = state_code or district_parent_state(district_code)
        state_ids = select(SchemeJurisdiction.scheme_id).where(
            SchemeJurisdiction.jurisdiction_code == parent_state
        )
        district_ids = select(SchemeJurisdiction.scheme_id).where(
            SchemeJurisdiction.jurisdiction_code == district_code
        )
        stmt = stmt.where(
            or_(
                Scheme.scope == "all_india",
                Scheme.id.in_(state_ids),
                Scheme.id.in_(district_ids),
            )
        )
    elif state_code is not None:
        state_ids = select(SchemeJurisdiction.scheme_id).where(
            SchemeJurisdiction.jurisdiction_code == state_code
        )
        stmt = stmt.where(or_(Scheme.scope == "all_india", Scheme.id.in_(state_ids)))

    rows = list(session.scalars(stmt).all())

    # Category and beneficiary group live inside the JSON payload, so they are
    # matched Python-side on the loaded rows.
    if isinstance(category, str):
        categories = [category]
    elif category is not None:
        categories = list(category)
    else:
        categories = []

    if categories:
        rows = [s for s in rows if any(c in _payload_list(s, "categories") for c in categories)]

    if isinstance(beneficiary_group, str):
        groups = [beneficiary_group]
    elif beneficiary_group is not None:
        groups = list(beneficiary_group)
    else:
        groups = []

    if groups:
        rows = [s for s in rows if any(g in _payload_list(s, "beneficiary_groups") for g in groups)]

    rows.sort(key=lambda s: (-_name_hits(s, tokens), s.name, s.id))

    total = len(rows)
    page = max(page, 1)
    page_size = max(page_size, 1)
    offset = (page - 1) * page_size
    return rows[offset : offset + page_size], total


def get_published_scheme(session: Session, scheme_id: str) -> Scheme | None:
    """Return the scheme with the given id only if it is published."""
    stmt = select(Scheme).where(Scheme.id == scheme_id, Scheme.record_status == PUBLISHED)
    return session.scalars(stmt).first()


def scheme_summary(scheme: Scheme) -> dict[str, Any]:
    """Return the list-view representation of a scheme."""
    return {
        "id": scheme.id,
        "scheme_id": scheme.id,
        "slug": scheme.slug,
        "name": scheme.name,
        "summary": scheme.summary,
        "government_level": scheme.government_level,
        "scope": scheme.scope,
        "record_status": scheme.record_status,
        "verification_status": scheme.verification_status,
        "last_verified_at": (
            scheme.last_verified_at.isoformat() if scheme.last_verified_at else None
        ),
        "review_due_at": scheme.review_due_at.isoformat() if scheme.review_due_at else None,
        "current_version": scheme.current_version,
        "categories": _payload_list(scheme, "categories"),
        "beneficiary_groups": _payload_list(scheme, "beneficiary_groups"),
    }


def _criteria(node: Any) -> list[dict[str, Any]]:
    """Flatten rule leaves for display without altering decision-tree semantics."""
    if not isinstance(node, dict):
        return []
    for group in ("all", "any"):
        children = node.get(group)
        if isinstance(children, list):
            return [criterion for child in children for criterion in _criteria(child)]
    if isinstance(node.get("not"), dict):
        return _criteria(node["not"])
    if "field" not in node or "operator" not in node:
        return []
    return [
        {
            "criterion_id": node.get("criterion_id"),
            "field": node["field"],
            "op": node["operator"],
            "value": node.get("value"),
            "mandatory": bool(node.get("mandatory", False)),
            "explanation": node.get("explanation", ""),
            "source_refs": list(node.get("source_refs", [])),
        }
    ]


def scheme_detail(scheme: Scheme) -> dict[str, Any]:
    """Return the public detail representation, including UI-ready guidance fields."""
    payload = _payload_dict(scheme)
    detail = scheme_summary(scheme)
    sources = [
        {
            "id": src.id,
            "source_id": src.id,
            "title": src.title,
            "publisher": src.publisher,
            "url": src.url,
            "source_type": src.source_type,
            "official_status": src.official_status,
            "access_date": src.access_date.isoformat(),
            "retrieved_on": src.access_date.isoformat(),
            "publication_date": (
                src.publication_date.isoformat() if src.publication_date else None
            ),
            "section": src.section,
        }
        for src in scheme.sources
    ]
    documents = payload.get("documents", [])
    application_steps = payload.get("application_steps", [])
    application_url = payload.get("application_url")
    detail.update(
        {
            "benefits": payload.get("benefits", []),
            "documents": documents,
            "document_checklist": documents,
            "application_steps": application_steps,
            "application_url": application_url,
            "application_guidance": {
                "steps": application_steps,
                "application_url": application_url,
            },
            "deadline": payload.get("deadline"),
            "criteria": _criteria(scheme.eligibility_rule),
            "sources": sources,
            "source_refs": sources,
            "jurisdictions": sorted(j.jurisdiction_code for j in scheme.jurisdictions),
        }
    )
    return detail
