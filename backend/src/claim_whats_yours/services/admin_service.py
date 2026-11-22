"""Admin lifecycle for schemes: import drafts, validate, verify, publish, archive, history.

Every function takes the session and only adds or flushes; the caller commits.
A refused change raises ValueError whose message is a stable code string.
"""

import copy
from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from claim_whats_yours.core.config import get_settings
from claim_whats_yours.db.models import Scheme, SchemeJurisdiction, SchemeSource, SchemeVersion
from claim_whats_yours.domain.geography import is_valid_jurisdiction_code
from claim_whats_yours.domain.rules import GROUP_KEYS, validate_rule

RECORD_STATUSES: frozenset[str] = frozenset(
    {"draft", "needs_review", "verified", "published", "archived"}
)
_VALIDATABLE: frozenset[str] = frozenset({"draft", "needs_review"})


def _error(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _as_date(value: Any) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _get_scheme(session: Session, scheme_id: str) -> Scheme:
    scheme = session.get(Scheme, scheme_id)
    if scheme is None:
        raise ValueError("SCHEME_NOT_FOUND")
    return scheme


def _iter_leaves(node: Any) -> Iterator[dict[str, Any]]:
    if not isinstance(node, dict):
        return
    group_keys = [k for k in node if k in GROUP_KEYS]
    if not group_keys:
        yield node
        return
    value = node[group_keys[0]]
    children = value if isinstance(value, list) else [value]
    for child in children:
        yield from _iter_leaves(child)


def _append_version(session: Session, scheme: Scheme, note: str, now: datetime) -> None:
    scheme.current_version += 1
    session.add(
        SchemeVersion(
            scheme_id=scheme.id,
            version=scheme.current_version,
            snapshot=copy.deepcopy(scheme.payload),
            change_note=note,
            created_at=now,
        )
    )


def _gate_errors(scheme: Scheme) -> list[dict[str, str]]:
    errors = [
        _error("UNSUPPORTED_RULE", "eligibility_rule", message)
        for message in validate_rule(scheme.eligibility_rule)
    ]
    sources = sorted(scheme.sources, key=lambda s: s.id)
    if not any(s.official_status == "official" for s in sources):
        errors.append(_error("NO_OFFICIAL_SOURCE", "sources", "an official source is required"))
    source_ids = {s.id for s in sources}
    for leaf in _iter_leaves(scheme.eligibility_rule):
        refs = leaf.get("source_refs", [])
        if not isinstance(refs, list):
            continue
        for ref in refs:
            if not isinstance(ref, str) or ref not in source_ids:
                errors.append(
                    _error(
                        "UNRESOLVED_EVIDENCE",
                        "eligibility_rule",
                        f"criterion {leaf.get('criterion_id')!r} cites unknown source {ref!r}",
                    )
                )
    for index, source in enumerate(sources):
        if not source.url.startswith("https://"):
            errors.append(
                _error("INVALID_URL", f"sources[{index}].url", "source url must be https")
            )
    payload = scheme.payload
    application_url = payload.get("application_url") if isinstance(payload, dict) else None
    if application_url and not str(application_url).startswith("https://"):
        errors.append(_error("INVALID_URL", "application_url", "application_url must be https"))
    has_rows = bool(scheme.jurisdictions)
    if scheme.scope == "all_india" and has_rows:
        errors.append(
            _error("INVALID_JURISDICTION", "jurisdictions", "all_india scheme must have no codes")
        )
    if scheme.scope != "all_india" and not has_rows:
        errors.append(
            _error("INVALID_JURISDICTION", "jurisdictions", "scheme needs at least one code")
        )
    return errors


def import_draft(session: Session, record: dict[str, Any], now: datetime) -> Scheme:
    """Create a draft scheme from an imported source record. Status is always forced to draft."""
    scheme_id = record["id"]
    slug = record["slug"]
    if (
        session.get(Scheme, scheme_id) is not None
        or session.scalar(select(Scheme.id).where(Scheme.slug == slug)) is not None
    ):
        raise ValueError("DUPLICATE_SCHEME")
    jurisdictions = record["jurisdictions"]
    codes = list(
        dict.fromkeys(
            [*jurisdictions.get("state_codes", []), *jurisdictions.get("district_codes", [])]
        )
    )
    if not all(is_valid_jurisdiction_code(code) for code in codes):
        raise ValueError("INVALID_JURISDICTION")
    payload = copy.deepcopy(record)
    payload["record_status"] = "draft"
    payload["verification_status"] = "needs_review"
    scheme = Scheme(
        id=scheme_id,
        slug=slug,
        name=record["name"],
        summary=record["summary"],
        government_level=record["government_level"],
        scope=jurisdictions["scope"],
        record_status="draft",
        verification_status="needs_review",
        eligibility_rule=copy.deepcopy(record["eligibility_rule"]),
        payload=payload,
        current_version=1,
        created_at=now,
        updated_at=now,
    )
    scheme.jurisdictions = [SchemeJurisdiction(jurisdiction_code=code) for code in codes]
    scheme.sources = [
        SchemeSource(
            id=source["id"],
            title=source["title"],
            publisher=source["publisher"],
            url=source["url"],
            source_type=source["source_type"],
            official_status=source["official_status"],
            access_date=_as_date(source["access_date"]),
            publication_date=_as_date(source.get("publication_date")),
            section=source.get("section"),
        )
        for source in record.get("sources", [])
    ]
    scheme.versions = [
        SchemeVersion(
            version=1,
            snapshot=copy.deepcopy(payload),
            change_note="imported as draft",
            created_at=now,
        )
    ]
    session.add(scheme)
    session.flush()
    return scheme


def validate_scheme(
    session: Session, scheme_id: str, now: datetime
) -> tuple[bool, list[dict[str, str]]]:
    """Run the review checks. A clean draft moves to needs_review. Returns (ok, errors)."""
    scheme = _get_scheme(session, scheme_id)
    if scheme.record_status not in _VALIDATABLE:
        raise ValueError("INVALID_TRANSITION")
    errors = _gate_errors(scheme)
    if not errors and scheme.record_status == "draft":
        scheme.record_status = "needs_review"
        scheme.updated_at = now
        session.add(scheme)
        session.flush()
    return (not errors, errors)


def verify_scheme(
    session: Session, scheme_id: str, reviewer: str, verified_at: date, now: datetime
) -> Scheme:
    """Record a human verification. record_status moves needs_review -> verified."""
    scheme = _get_scheme(session, scheme_id)
    if scheme.record_status != "needs_review":
        raise ValueError("INVALID_TRANSITION")
    reviewer_name = reviewer.strip()
    if not 1 <= len(reviewer_name) <= 120:
        raise ValueError("INVALID_REVIEWER")
    last_verified = datetime.combine(verified_at, time(0), tzinfo=UTC)
    scheme.verification_status = "verified"
    scheme.record_status = "verified"
    scheme.last_verified_at = last_verified
    scheme.review_due_at = last_verified + timedelta(days=get_settings().scheme_review_max_age_days)
    payload = copy.deepcopy(scheme.payload) if isinstance(scheme.payload, dict) else {}
    verification = payload.get("verification")
    if not isinstance(verification, dict):
        verification = {}
        payload["verification"] = verification
    verification["reviewed_by"] = reviewer_name
    verification["reviewed_at"] = verified_at.isoformat()
    scheme.payload = payload
    scheme.updated_at = now
    _append_version(session, scheme, "verified by " + reviewer_name, now)
    session.flush()
    return scheme


def publish_scheme(session: Session, scheme_id: str, actor: str, now: datetime) -> Scheme:
    """Publish a verified scheme after the publication gate and freshness checks pass."""
    scheme = _get_scheme(session, scheme_id)
    if scheme.record_status != "verified":
        raise ValueError("INVALID_TRANSITION")
    if _gate_errors(scheme):
        raise ValueError("PUBLICATION_GATE_FAILED")
    due = scheme.review_due_at
    if scheme.verification_status != "verified" or due is None or _aware(due) < _aware(now):
        raise ValueError("VERIFICATION_STALE")
    scheme.record_status = "published"
    scheme.updated_at = now
    _append_version(session, scheme, "published by " + actor, now)
    session.flush()
    return scheme


def archive_scheme(session: Session, scheme_id: str, actor: str, now: datetime) -> Scheme:
    """Archive a published scheme."""
    scheme = _get_scheme(session, scheme_id)
    if scheme.record_status != "published":
        raise ValueError("INVALID_TRANSITION")
    scheme.record_status = "archived"
    scheme.updated_at = now
    _append_version(session, scheme, "archived by " + actor, now)
    session.flush()
    return scheme


def review_queue(
    session: Session, statuses: set[str], page: int, page_size: int
) -> tuple[list[Scheme], int]:
    """Return one page of schemes in the given statuses, ordered by id, plus the total."""
    if not statuses <= RECORD_STATUSES:
        raise ValueError("INVALID_STATUS")
    if page < 1 or page_size < 1:
        raise ValueError("INVALID_PAGINATION")
    condition = Scheme.record_status.in_(sorted(statuses))
    total = session.scalar(select(func.count()).select_from(Scheme).where(condition))
    schemes = session.scalars(
        select(Scheme)
        .where(condition)
        .order_by(Scheme.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(schemes), int(total or 0)


def list_versions(session: Session, scheme_id: str) -> list[SchemeVersion] | None:
    """Return the version history, newest first, or None when the scheme does not exist."""
    if session.get(Scheme, scheme_id) is None:
        return None
    versions = session.scalars(
        select(SchemeVersion)
        .where(SchemeVersion.scheme_id == scheme_id)
        .order_by(SchemeVersion.version.desc())
    ).all()
    return list(versions)
