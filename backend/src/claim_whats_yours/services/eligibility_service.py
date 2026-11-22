"""Stateless eligibility evaluation over published schemes. Never persists anything."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from claim_whats_yours.db.models import Scheme
from claim_whats_yours.domain.decisions import DISCLAIMER, Decision, decide
from claim_whats_yours.domain.fields import validate_answers
from claim_whats_yours.domain.geography import (
    applicable,
    geographic_status,
    is_valid_district_code,
    known_state_codes,
)
from claim_whats_yours.domain.rules import (
    CriterionResult,
    Tri,
    check_rule,
    evaluate_rule,
    prune_advisory,
)
from claim_whats_yours.services.document_service import DocumentService

# parents[0]=services, [1]=claim_whats_yours, [2]=src, [3]=backend
_FIELDS_PATH = Path(__file__).resolve().parents[3] / "data" / "profile_fields.json"
_DECISION_ORDER: dict[str, int] = {
    decision.value: index
    for index, decision in enumerate(
        (
            Decision.LIKELY_ELIGIBLE,
            Decision.NEEDS_MORE_INFORMATION,
            Decision.VERIFICATION_REQUIRED,
            Decision.NOT_LIKELY_ELIGIBLE,
        )
    )
}


def evaluate_profile(
    session: Session,
    answers: dict[str, Any],
    now: datetime,
    government_levels: set[str] | None,
    today: date | None = None,
    doc_service: DocumentService | None = None,
) -> dict[str, Any]:
    """Evaluate published schemes against stateless answers. Nothing is stored.

    "today" is the UTC date used for the effective-period and verification-freshness checks.
    When omitted it is taken from "now" (UTC). Tests pass a fixed date.

    Schemes whose effective period does not include "today" are excluded from the results.
    Each returned scheme reports verification_current and last_verified_at; a scheme whose
    verification is not current is returned as VERIFICATION_REQUIRED.

    A published scheme whose stored rule fails validation is not evaluated and is not returned
    in results. It is listed in "excluded_schemes" with reason "rule_invalid" and its errors.
    """
    errors = validate_answers(answers)
    if errors:
        return {"errors": errors}
    today = today if today is not None else _utc_date(now)
    # The public evaluation response always includes personalised document and
    # application guidance; it remains stateless because this instance holds no
    # citizen data beyond the current call.
    doc_service = doc_service or DocumentService()
    schemes = session.scalars(select(Scheme).where(Scheme.record_status == "published")).all()
    results: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for scheme in schemes:
        if government_levels is not None and scheme.government_level not in government_levels:
            continue
        if not _in_scope(scheme, answers, today):
            continue
        rule_errors = [error.as_dict() for error in check_rule(scheme.eligibility_rule)]
        if rule_errors:
            excluded.append(_rule_invalid_entry(scheme, rule_errors))
            continue
        results.append(_evaluate_scheme(scheme, answers, today, doc_service))
    results.sort(key=lambda r: (_DECISION_ORDER[r["decision"]], r["scheme_id"]))
    excluded.sort(key=lambda e: e["scheme_id"])
    missing = sorted({field for r in results for field in r["missing_fields"]})
    return {
        "evaluation_date": today.isoformat(),
        "results": results,
        "excluded_schemes": excluded,
        "missing_fields": missing,
        "follow_up_questions": build_questions(missing, results),
        "disclaimer": DISCLAIMER,
    }


def _in_scope(scheme: Scheme, answers: dict[str, Any], today: date) -> bool:
    """True when today is in the effective period and the scheme's geography applies."""
    return _in_effective_period(scheme, today) and applicable(_scheme_geo(scheme, answers))


def _rule_invalid_entry(scheme: Scheme, errors: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "scheme_id": scheme.id,
        "name": scheme.name,
        "reason": "rule_invalid",
        "errors": errors,
    }


# DocumentService is instantiated lazily in evaluate_profile


def _evaluate_scheme(
    scheme: Scheme,
    answers: dict[str, Any],
    today: date,
    doc_service: DocumentService | None,
) -> dict[str, Any]:
    """Return the per-scheme result. The caller has already checked scope and rule validity."""
    geo = _scheme_geo(scheme, answers)
    rule = scheme.eligibility_rule
    leaves = _leaf_results(evaluate_rule(rule, answers))
    fields = _raw_leaf_fields(rule)
    decision_status = _decision_status(rule, answers)
    verification_current = _verification_current(scheme, today)
    # Self-check handling is not implemented yet; the flag is always False for now.
    decision = decide(geo, [decision_status], verification_current, False)
    last_verified = scheme.last_verified_at.isoformat() if scheme.last_verified_at else None
    payload = scheme.payload if isinstance(scheme.payload, dict) else {}

    # Build enhanced document checklist using DocumentService
    document_checklist = payload.get("documents", [])
    application_guidance = {
        "steps": payload.get("application_steps", []),
        "application_url": payload.get("application_url"),
    }
    personalized_checklist = None
    if doc_service and payload:
        try:
            personalized_checklist = doc_service.get_document_checklist(payload, answers)
            application_guidance = doc_service.get_application_guide(payload, answers)
            document_checklist = (
                personalized_checklist["required"] + personalized_checklist["conditional"]
            )
        except (KeyError, TypeError, ValueError):
            # Preserve the verified source record if a malformed optional
            # presentation field cannot be personalized.
            personalized_checklist = None

    return {
        "scheme_id": scheme.id,
        "name": scheme.name,
        "government_level": scheme.government_level,
        "categories": [str(category) for category in payload.get("categories", [])],
        "decision": decision.value,
        "verification_status": scheme.verification_status,
        "verification_current": verification_current,
        "last_verified_at": last_verified,
        "criteria": [_criterion(leaf) for leaf in leaves],
        "missing_fields": sorted(
            {
                field
                for leaf, field in zip(leaves, fields, strict=True)
                if leaf.status is Tri.UNKNOWN
            }
        ),
        "source_refs": list(dict.fromkeys(ref for leaf in leaves for ref in leaf.source_refs)),
        "document_checklist": document_checklist,
        "personalized_checklist": personalized_checklist,
        "application_guidance": application_guidance,
    }


def _decision_status(rule: dict[str, Any], answers: dict[str, Any]) -> Tri:
    """Return the single status the scheme decision uses, from the real rule tree.

    Semantics:
    - A leaf with mandatory=false is advisory. It never affects the decision. It is still
      reported per criterion by _criterion for explanation.
    - Mandatory leaves form the decision expression. It is evaluated as a tree with the
      all/any/not rules, so OR and NOT are preserved.
    - If no mandatory leaf exists, the decision status is PASS.
    """
    pruned = prune_advisory(rule)
    if pruned is None:
        return Tri.PASS
    return evaluate_rule(pruned, answers).status


def _scheme_geo(scheme: Scheme, answers: dict[str, Any]) -> Tri:
    codes = [link.jurisdiction_code for link in scheme.jurisdictions]
    state_codes = [code for code in codes if code in known_state_codes()]
    district_codes = [code for code in codes if is_valid_district_code(code)]
    return geographic_status(
        scheme.scope,
        state_codes,
        district_codes,
        answers.get("state_code"),
        answers.get("district_code"),
    )


def _utc_date(value: datetime) -> date:
    """Return the UTC calendar date of a datetime. Naive values are treated as UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).date()


def _in_effective_period(scheme: Scheme, today: date) -> bool:
    """True when today is on or after effective_from (if set) and on or before effective_to.

    An unset bound is open-ended.
    """
    if scheme.effective_from is not None and today < scheme.effective_from:
        return False
    return not (scheme.effective_to is not None and today > scheme.effective_to)


def _verification_current(scheme: Scheme, today: date) -> bool:
    """True only when the scheme is verified, last_verified_at and review_due_at are both set,
    and review_due_at falls after today (UTC date). Otherwise verification is not current.
    """
    if scheme.verification_status != "verified":
        return False
    if scheme.last_verified_at is None or scheme.review_due_at is None:
        return False
    return _utc_date(scheme.review_due_at) > today


def _leaf_results(result: CriterionResult) -> list[CriterionResult]:
    """Return leaf criteria in rule order (leaves are the nodes without children)."""
    if not result.children:
        return [result]
    return [leaf for child in result.children for leaf in _leaf_results(child)]


def _raw_leaf_fields(node: dict[str, Any]) -> list[str]:
    """Return leaf field names in the same depth-first order as _leaf_results."""
    for key in ("all", "any"):
        if key in node:
            return [field for child in node[key] for field in _raw_leaf_fields(child)]
    if "not" in node:
        return _raw_leaf_fields(node["not"])
    return [node["field"]]


def _criterion(leaf: CriterionResult) -> dict[str, Any]:
    return {
        "criterion_id": leaf.criterion_id,
        "status": leaf.status.value,
        "explanation": leaf.explanation,
        "source_refs": list(leaf.source_refs),
        "mandatory": leaf.mandatory,
    }


def build_questions(
    missing_fields: list[str], results: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return follow-up questions for missing fields, most-blocking fields first."""
    registry = _field_definitions()
    counted = [
        (sum(1 for r in results if field in r["missing_fields"]), field)
        for field in sorted(set(missing_fields))
        if field in registry
    ]
    counted.sort(key=lambda item: (-item[0], item[1]))
    return [_question(field, count, registry[field]) for count, field in counted]


def _question(field: str, count: int, definition: dict[str, Any]) -> dict[str, Any]:
    return {
        "field": field,
        "label": definition.get("label", field),
        "description": definition.get("description"),
        "allowed_values": definition.get("allowed_values"),
        "reason": f"Needed to evaluate {count} matching scheme(s)",
    }


@lru_cache(maxsize=1)
def _field_definitions() -> dict[str, dict[str, Any]]:
    with _FIELDS_PATH.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return {field["id"]: field for field in data["fields"]}
