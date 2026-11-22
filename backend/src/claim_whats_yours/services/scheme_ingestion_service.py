"""Scheme ingestion service.

This service manages the scheme lifecycle:
1. Import schemes from official sources
2. Validate rules and data quality
3. Create version snapshots
4. Track source updates for change detection

The service enforces the controlled scheme lifecycle:
    draft -> needs_review -> verified -> published -> archived
"""

from __future__ import annotations

import logging
import secrets
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from claim_whats_yours.core.config import Settings
from claim_whats_yours.db.models import Scheme, SchemeJurisdiction, SchemeSource, SchemeVersion
from claim_whats_yours.db.session import get_session
from claim_whats_yours.domain.rules import check_rule
from claim_whats_yours.services.sources.base_adapter import SourceAdapter

logger = logging.getLogger(__name__)


class SchemeIngestionError(Exception):
    """Base exception for scheme ingestion errors."""


class SchemeValidationError(SchemeIngestionError):
    """Raised when scheme validation fails."""


class SchemeIngestionService:
    """Service for importing, validating, and managing scheme data."""

    def __init__(self, settings: Settings, session: Session | None = None) -> None:
        self._cfg = settings
        self._session = session

    def _get_session(self) -> Session:
        if self._session:
            return self._session
        return next(get_session())

    def import_scheme(
        self, payload: dict[str, Any], source_records: list[dict[str, Any]]
    ) -> Scheme:
        """Import a new scheme as a draft.

        Args:
            payload: The scheme data including eligibility_rule, name, summary, etc.
            source_records: List of official source references.

        Returns:
            The created Scheme ORM model.

        Raises:
            SchemeValidationError: If validation fails.
        """
        scheme_id = payload.get("id")
        if not scheme_id:
            raise SchemeValidationError("Scheme must have an 'id' field")

        # Validate eligibility rule structure
        if "eligibility_rule" in payload:
            errors = check_rule(payload["eligibility_rule"])
            if errors:
                error_messages = [e.as_dict() for e in errors]
                raise SchemeValidationError(f"Invalid eligibility rule: {error_messages}")

        # Create the scheme as a draft
        scheme = Scheme(
            id=scheme_id,
            slug=payload.get("slug", scheme_id),
            name=payload.get("name", scheme_id),
            summary=payload.get("summary", ""),
            government_level=payload.get("government_level", "central"),
            scope=payload.get("scope", "all_india"),
            record_status="draft",
            verification_status="needs_review",
            eligibility_rule=payload.get("eligibility_rule"),
            payload=payload,
            current_version=1,
        )

        # Add jurisdictions
        jurisdiction_codes = payload.get("jurisdictions", [])
        for code in jurisdiction_codes:
            scheme.jurisdictions.append(SchemeJurisdiction(jurisdiction_code=code))

        # Add sources
        for src in source_records:
            scheme.sources.append(
                SchemeSource(
                    id=src.get("id", secrets.token_hex(8)),
                    title=src.get("title", ""),
                    publisher=src.get("publisher", ""),
                    url=src.get("url", ""),
                    source_type=src.get("source_type", "official"),
                    official_status=src.get("official_status", "official"),
                    access_date=date.today(),
                )
            )

        session = self._get_session()
        session.add(scheme)
        session.commit()
        session.refresh(scheme)

        logger.info("Scheme imported as draft: %s", scheme_id)
        return scheme

    def validate_scheme(self, scheme_id: str) -> Scheme:
        """Run validation checks on a draft scheme.

        Transitions: draft -> needs_review (on clean pass)

        Raises:
            SchemeValidationError: If validation fails.
        """
        session = self._get_session()
        scheme = session.get(Scheme, scheme_id)
        if not scheme:
            raise SchemeValidationError(f"Scheme not found: {scheme_id}")

        if scheme.record_status != "draft":
            raise SchemeValidationError(
                f"Scheme must be draft to validate (current: {scheme.record_status})"
            )

        # Check required fields
        errors = []

        if not scheme.name:
            errors.append("Missing scheme name")
        if not scheme.summary:
            errors.append("Missing scheme summary")

        # Validate eligibility rule if present
        if scheme.eligibility_rule:
            rule_errors = check_rule(scheme.eligibility_rule)
            if rule_errors:
                errors.extend(f"Rule error: {e.path} - {e.message}" for e in rule_errors)

        # Check for at least one official source
        official_sources = [
            s for s in scheme.sources if s.official_status in ("official", "official_portal")
        ]
        if not official_sources:
            errors.append("At least one official source is required")

        if errors:
            raise SchemeValidationError("; ".join(errors))

        # Validation passed
        scheme.verification_status = "needs_review"
        session.commit()

        logger.info("Scheme validated and moved to needs_review: %s", scheme_id)
        return scheme

    def verify_scheme(self, scheme_id: str, reviewer_name: str, verified_at: datetime) -> Scheme:
        """Verify a scheme as ready for publication.

        Transitions: needs_review -> verified

        Args:
            scheme_id: The scheme ID.
            reviewer_name: Name of the reviewing authority.
            verified_at: Timestamp of verification.
        """
        session = self._get_session()
        scheme = session.get(Scheme, scheme_id)
        if not scheme:
            raise SchemeValidationError(f"Scheme not found: {scheme_id}")

        if scheme.verification_status != "needs_review":
            raise SchemeValidationError(
                f"Scheme must be needs_review to verify (current: {scheme.verification_status})"
            )

        scheme.verification_status = "verified"
        scheme.last_verified_at = verified_at
        # review_due_at = last_verified + 180 days
        scheme.review_due_at = verified_at.date() + datetime.timedelta(days=180)

        session.commit()
        logger.info("Scheme verified by %s: %s", reviewer_name, scheme_id)
        return scheme

    def publish_scheme(self, scheme_id: str, actor: str) -> Scheme:
        """Publish a verified scheme.

        Transitions: verified -> published

        Gates:
        - Scheme must be verified
        - verification_status must be verified
        - review_due_at must be in the future (or None)
        """
        session = self._get_session()
        scheme = session.get(Scheme, scheme_id)
        if not scheme:
            raise SchemeValidationError(f"Scheme not found: {scheme_id}")

        if scheme.verification_status != "verified":
            raise SchemeValidationError(
                f"Scheme must be verified to publish (current: {scheme.verification_status})"
            )

        today = date.today()
        if scheme.review_due_at is not None and scheme.review_due_at < today:
            raise SchemeValidationError(
                f"Scheme verification is stale (review_due_at: {scheme.review_due_at})"
            )

        # Record version snapshot
        scheme.current_version += 1
        version = SchemeVersion(
            scheme=scheme,
            version=scheme.current_version,
            snapshot={
                "eligibility_rule": scheme.eligibility_rule,
                "payload": scheme.payload,
            },
            change_note=f"Published by {actor} on {today.isoformat()}",
        )
        session.add(version)

        scheme.record_status = "published"
        session.commit()

        logger.info("Scheme published by %s: %s", actor, scheme_id)
        return scheme

    def archive_scheme(self, scheme_id: str, actor: str) -> Scheme:
        """Archive a published scheme.

        Transitions: published -> archived

        Archive removes the scheme from public listing and eligibility evaluation.
        """
        session = self._get_session()
        scheme = session.get(Scheme, scheme_id)
        if not scheme:
            raise SchemeValidationError(f"Scheme not found: {scheme_id}")

        if scheme.record_status != "published":
            raise SchemeValidationError(
                f"Scheme must be published to archive (current: {scheme.record_status})"
            )

        scheme.record_status = "archived"

        version = SchemeVersion(
            scheme=scheme,
            version=scheme.current_version + 1,
            snapshot={"archived_by": actor, "archived_at": datetime.now().isoformat()},
            change_note=f"Archived by {actor} on {date.today().isoformat()}",
        )
        session.add(version)

        session.commit()
        logger.info("Scheme archived by %s: %s", actor, scheme_id)
        return scheme

    def get_review_queue(self) -> list[Scheme]:
        """Get all schemes needing review (draft + needs_review)."""
        session = self._get_session()
        stmt = select(Scheme).where(Scheme.record_status.in_(["draft", "needs_review"]))
        return list(session.scalars(stmt))

    def list_versions(self, scheme_id: str) -> list[dict[str, Any]]:
        """Get version history for a scheme (without snapshot bodies)."""
        session = self._get_session()
        scheme = session.get(Scheme, scheme_id)
        if not scheme:
            return []

        versions = []
        for v in scheme.versions:
            versions.append(
                {
                    "version": v.version,
                    "change_note": v.change_note,
                    "created_at": v.created_at.isoformat(),
                }
            )
        return versions

    def check_source_updates(self, adapter: SourceAdapter) -> list[dict[str, Any]]:
        """Check registered sources for updates.

        Returns a list of schemes that may need review.
        """
        updates = []
        session = self._get_session()

        stmt = select(Scheme).where(Scheme.record_status == "published")
        for scheme in session.scalars(stmt):
            for source in scheme.sources:
                if source.source_type == adapter.name:
                    updates.append(
                        {
                            "scheme_id": scheme.id,
                            "source_id": source.id,
                            "source_url": source.url,
                            "needs_check": True,
                        }
                    )
        return updates
