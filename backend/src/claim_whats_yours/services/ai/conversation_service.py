"""Conversational eligibility assistant service.

This service handles natural-language input from citizens, extracts structured
profile fields, identifies missing information, and generates follow-up questions.

The key constraint from the master engineering prompt:
- No persistent storage of citizen profiles or conversation history
- The client sends previously-accepted answers on subsequent turns
- The backend merges these with new extractions and evaluates eligibility

Usage:
    service = ConversationService.from_settings()
    result = service.turn(
        messages=["I'm a farmer from Andhra Pradesh..."],
        answers={"state_code": "IN-AP"},  # previous answers
        locale="te"
    )
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from claim_whats_yours.core.config import Settings, get_settings
from claim_whats_yours.db.models import Scheme
from claim_whats_yours.db.session import get_session_factory
from claim_whats_yours.domain.fields import load_registry, validate_answers
from claim_whats_yours.domain.geography import known_state_codes
from claim_whats_yours.domain.rules import Tri, prune_advisory
from claim_whats_yours.schemas.conversation import (
    ConversationRequest,
    ConversationTurnResponse,
    ExtractedProfile,
)
from claim_whats_yours.services.ai.groq_client import GroqClient
from claim_whats_yours.services.eligibility_service import _extract_leaves, _raw_leaf_fields

logger = logging.getLogger(__name__)


_DEFAULT_SCHEME_RULES: list[dict[str, Any]] = [
    {
        "id": "sch_pm_kisan_2019",
        "scope": "all_india",
        "state_codes": [],
        "rule": {
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
    },
    {
        "id": "sch_ap_rythu_bharosa",
        "scope": "state",
        "state_codes": ["IN-AP"],
        "rule": {
            "all": [
                {
                    "criterion_id": "crit_ap_resident",
                    "field": "state_code",
                    "operator": "eq",
                    "value": "IN-AP",
                    "mandatory": True,
                    "explanation": "Must reside in Andhra Pradesh.",
                    "source_refs": ["src_ap_rythu_go"],
                },
                {
                    "criterion_id": "crit_ap_farmer",
                    "field": "is_farmer",
                    "operator": "eq",
                    "value": True,
                    "mandatory": True,
                    "explanation": "Must be a landowner farmer or registered tenant farmer.",
                    "source_refs": ["src_ap_rythu_go"],
                },
            ]
        },
    },
    {
        "id": "sch_pm_svanidhi",
        "scope": "all_india",
        "state_codes": [],
        "rule": {
            "all": [
                {
                    "criterion_id": "crit_svanidhi_worker",
                    "field": "is_unorganised_worker",
                    "operator": "eq",
                    "value": True,
                    "mandatory": True,
                    "explanation": "Must be engaged in vending or unorganised micro-enterprise.",
                    "source_refs": ["src_pm_svanidhi_scheme"],
                },
                {
                    "criterion_id": "crit_svanidhi_age",
                    "field": "age_years",
                    "operator": "gte",
                    "value": 18,
                    "mandatory": True,
                    "explanation": "Street vendor must be at least 18 years of age.",
                    "source_refs": ["src_pm_svanidhi_scheme"],
                },
            ]
        },
    },
]


class ConversationService:
    """Handles conversational profile collection and eligibility evaluation."""

    # Fields that require additional clarifying questions
    CLARIFYING_FIELDS: set[str] = {
        "landholding_acres",  # Need to know if owned or leased
        "occupation",  # Need specifics
        "is_farmer",  # Need confirmation
    }

    def __init__(
        self,
        groq: GroqClient,
        settings: Settings,
        session: Session | None = None,
        schemes: list[Any] | None = None,
    ) -> None:
        self._groq = groq
        self._cfg = settings
        self._session = session
        self._schemes = schemes

    @classmethod
    def from_settings(
        cls, settings: Settings | None = None, session: Session | None = None
    ) -> ConversationService:
        cfg = settings or get_settings()
        groq = GroqClient.from_settings(cfg)
        return cls(groq, cfg, session=session)

    def turn(self, req: ConversationRequest) -> ConversationTurnResponse:
        """Process one turn of the conversation.

        Args:
            req: The conversation request containing messages and previous answers.

        Returns:
            A response with follow-up questions or eligibility readiness.

        Raises:
            GroqError: If Groq API call fails after all retries.
        """
        # Validate locale format
        if not re.match(r"^[a-z]{2}(-[A-Z]{2})?$", req.locale):
            raise ValueError(f"Invalid locale format: {req.locale}")

        # Merge previous answers with new extraction
        merged = dict(req.answers)

        # Extract structured data from messages
        extracted = self._extract_profile(req.messages, req.locale)

        # Merge extracted answers into profile
        merged.update(extracted.extracted_answers)

        # Validate merged answers against registry
        validation_errors = validate_answers(merged)

        if validation_errors:
            logger.warning(
                "Profile validation errors: %s",
                [e.get("code") for e in validation_errors],
            )

        # Identify missing mandatory fields for eligibility evaluation
        missing = self._identify_missing(merged)

        # Determine if we can evaluate eligibility
        eligibility_ready = len(missing) == 0

        # Generate follow-up question if needed
        follow_up = None
        if not eligibility_ready:
            if extracted.clarification_required and extracted.next_question:
                follow_up = extracted.next_question
            else:
                # Generate a targeted follow-up question for the first missing field
                follow_up = self._generate_follow_up(missing, merged, req.locale)

        return ConversationTurnResponse(
            follow_up_question=follow_up,
            extracted_profile=merged,
            missing_fields=missing,
            eligibility_ready=eligibility_ready,
            evaluation_suggestion=self._build_suggestion(extracted, missing)
            if eligibility_ready
            else None,
        )

    def _extract_profile(self, messages: list[str], locale: str) -> ExtractedProfile:
        """Extract structured profile data from conversational messages using Groq."""

        system_prompt = (
            "You are an Indian government benefits assistant. Extract profile "
            "information from citizen messages to determine which welfare schemes "
            "they may be eligible for."
        )

        # Profile fields schema for structured output
        registry = load_registry()
        field_types = {}
        for fid, fdef in registry.items():
            ftype = fdef.get("type", "string")
            if ftype == "bool":
                field_types[fid] = {"type": "boolean"}
            elif ftype in ("int", "number"):
                field_types[fid] = {"type": "integer"}
            else:
                field_types[fid] = {"type": "string"}

        response_schema = {
            "type": "object",
            "properties": {
                "language": {
                    "type": "string",
                    "description": "Detected language (2-letter ISO code)",
                    "enum": ["en", "te", "hi", "ta", "mr", "bn", "gu", "kn", "ml", "or", "pa"],
                },
                "extracted_answers": {
                    "type": "object",
                    "description": "Extracted profile field values",
                    "properties": field_types,
                    "additionalProperties": False,
                },
                "missing_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Profile fields mentioned or needed but not found",
                },
                "clarification_required": {
                    "type": "boolean",
                    "description": "True if input is ambiguous and needs follow-up",
                },
                "next_question": {
                    "type": "string",
                    "description": "Specific follow-up question to ask, or null if none needed",
                },
                "intent_summary": {
                    "type": "string",
                    "description": "Brief summary of user's situation and intent",
                    "maxLength": 200,
                },
            },
            "required": [
                "language",
                "extracted_answers",
                "missing_fields",
                "clarification_required",
                "intent_summary",
            ],
        }

        # Combine all messages into a single context
        full_context = "\n\n".join(messages)

        result = self._groq.structured_request(
            system_prompt=system_prompt,
            user_message=(
                f" citizen is speaking in {locale}. "
                f"Extract their profile information from these messages:\n\n"
                f"{full_context}\n\n"
                f"Respond ONLY with the extracted profile JSON."
            ),
            response_schema=response_schema,
            schema_name="extracted_profile",
        )

        return ExtractedProfile(
            language=result["language"],
            extracted_answers=result["extracted_answers"],
            missing_fields=result.get("missing_fields", []),
            clarification_required=result.get("clarification_required", False),
            next_question=result.get("next_question"),
            intent_summary=result.get("intent_summary", ""),
        )

    def _get_schemes(self) -> list[Any]:
        if self._schemes is not None:
            return self._schemes
        if self._session is not None:
            try:
                stmt = select(Scheme).where(Scheme.record_status == "published")
                schemes = list(self._session.scalars(stmt).all())
                if schemes:
                    return schemes
            except Exception:
                pass
        try:
            url = self._cfg.database_url
            with get_session_factory(url)() as s:
                stmt = select(Scheme).where(Scheme.record_status == "published")
                schemes = list(s.scalars(stmt).all())
                if schemes:
                    return schemes
        except Exception:
            pass
        return _DEFAULT_SCHEME_RULES

    def _identify_missing(self, answers: dict[str, Any]) -> list[str]:
        """Identify profile fields needed for eligibility evaluation.

        Returns only the missing fields needed by matching or applicable schemes,
        rather than requiring all 16 profile fields from the catalogue.
        """
        schemes = self._get_schemes()
        applicable_schemes: list[Any] = []
        for scheme in schemes:
            scope = (
                getattr(scheme, "scope", None)
                or (scheme.get("scope") if isinstance(scheme, dict) else "all_india")
            )
            if hasattr(scheme, "jurisdictions") and scheme.jurisdictions:
                state_codes = [
                    j.jurisdiction_code
                    for j in scheme.jurisdictions
                    if j.jurisdiction_code in known_state_codes()
                ]
            elif isinstance(scheme, dict):
                state_codes = scheme.get("state_codes", [])
            else:
                state_codes = []

            state_ans = answers.get("state_code")
            if state_ans is not None and scope == "state" and state_ans not in state_codes:
                continue
            applicable_schemes.append(scheme)

        if not applicable_schemes:
            return []

        ready_schemes: list[Any] = []
        partial_matches: list[tuple[Any, list[str]]] = []
        candidate_schemes: list[tuple[Any, list[str]]] = []

        for scheme in applicable_schemes:
            rule = (
                getattr(scheme, "eligibility_rule", None)
                or (scheme.get("rule") if isinstance(scheme, dict) else None)
            )
            if not rule:
                continue

            pruned = prune_advisory(rule) or rule
            leaf_fields = _raw_leaf_fields(pruned)
            leaves = _extract_leaves(pruned, answers)

            has_fail = any(
                leaf_item.status is Tri.FAIL and leaf_item.mandatory for leaf_item in leaves
            )
            if has_fail:
                continue

            missing_for_scheme = [
                field
                for leaf, field in zip(leaves, leaf_fields, strict=True)
                if leaf.status is Tri.UNKNOWN
                and (answers.get(field) is None or answers.get(field) == "prefer_not_to_say")
            ]

            if not missing_for_scheme:
                ready_schemes.append(scheme)
            else:
                has_pass = any(leaf_item.status is Tri.PASS for leaf_item in leaves)
                if has_pass:
                    partial_matches.append((scheme, missing_for_scheme))
                else:
                    candidate_schemes.append((scheme, missing_for_scheme))

        if partial_matches:
            missing_set: set[str] = set()
            for _, fields in partial_matches:
                missing_set.update(fields)
            return sorted(missing_set)

        if ready_schemes:
            return []

        missing_set = set()
        for _, fields in candidate_schemes:
            missing_set.update(fields)
        return sorted(missing_set)

    def _generate_follow_up(self, missing: list[str], answers: dict[str, Any], locale: str) -> str:
        """Generate a targeted follow-up question for the first missing field."""

        if not missing:
            return ""

        field_id = missing[0]
        registry = load_registry()

        field_def = registry.get(field_id)
        if not field_def:
            return ""

        field_name = field_def.get("label", field_id)

        # Generate context-aware follow-up
        if field_id == "landholding_acres":
            return "Do you own the agricultural land, or are you cultivating leased land?"
        if field_id == "is_farmer":
            return "Are you engaged in farming as your primary occupation?"
        if field_id == "occupation":
            return "What is your current occupation? (e.g., farmer, salaried, self-employed)"
        if field_id == "annual_household_income_inr":
            return "What is your approximate annual household income in INR?"
        if field_id == "social_category":
            return "Which social category do you belong to?"
        if field_id == "disability_status":
            return "Do you have any certified disability?"
        if field_id == "is_unorganised_worker":
            return "Do you work in the unorganised sector or informal economy?"
        if field_id == "state_code":
            return "Which state or union territory do you live in?"
        if field_id == "age_years":
            return "What is your age in completed years?"

        # Generic follow-up
        return f"What is your {field_name.lower()}?"

    def _build_suggestion(self, extracted: ExtractedProfile, missing: list[str]) -> str:
        """Build a brief eligibility suggestion when data is sufficient."""

        if not missing:
            return (
                f"Based on your profile as {extracted.intent_summary.lower()}, "
                f"you may be eligible for government welfare schemes. "
                f"Please review the recommendations below."
            )
        return ""

    def check_consent_required(self, messages: list[str]) -> bool:
        """Check if Grok processing consent is needed based on message content.

        This is a simple heuristic check. In production, this would query a
        user preference store.
        """
        text = " ".join(messages).lower()
        sensitive_patterns = [
            "aadhaar",
            "pan",
            "bank",
            "account",
            "password",
            "government id",
        ]
        for pattern in sensitive_patterns:
            if pattern in text:
                logger.warning("Sensitive identifier detected in message")
                return True
        return False

    def redact_sensitive(self, text: str) -> str:
        """Redact obvious sensitive identifiers from user input.

        Returns a sanitized version of the text.
        """
        # Simple regex patterns for common identifiers
        patterns = [
            # Aadhaar: 12 digits in groups of 4
            (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "[AADHAAR_REDACTED]"),
            # PAN: 5 letters + 4 digits + 1 letter
            (r"\b[A-Z]{5}\d{4}[A-Z]\b", "[PAN_REDACTED]"),
        ]

        redacted = text
        for pattern, replacement in patterns:
            redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)

        return redacted
