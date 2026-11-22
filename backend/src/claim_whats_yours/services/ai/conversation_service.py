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

from claim_whats_yours.core.config import Settings, get_settings
from claim_whats_yours.domain.fields import load_registry, validate_answers
from claim_whats_yours.schemas.conversation import (
    ConversationRequest,
    ConversationTurnResponse,
    ExtractedProfile,
)
from claim_whats_yours.services.ai.groq_client import GroqClient

logger = logging.getLogger(__name__)


class ConversationService:
    """Handles conversational profile collection and eligibility evaluation."""

    # Fields that require additional clarifying questions
    CLARIFYING_FIELDS: set[str] = {
        "landholding_acres",  # Need to know if owned or leased
        "occupation",  # Need specifics
        "is_farmer",  # Need confirmation
    }

    def __init__(self, groq: GroqClient, settings: Settings) -> None:
        self._groq = groq
        self._cfg = settings

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> ConversationService:
        cfg = settings or get_settings()
        groq = GroqClient.from_settings(cfg)
        return cls(groq, cfg)

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

    def _identify_missing(self, answers: dict[str, Any]) -> list[str]:
        """Identify profile fields needed for eligibility evaluation.

        Returns a list of field IDs that are missing or have no answer.
        """
        missing: list[str] = []
        registry = load_registry()

        for field_id in registry:
            value = answers.get(field_id)
            if value is None or value == "prefer_not_to_say":
                missing.append(field_id)

        return missing

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
