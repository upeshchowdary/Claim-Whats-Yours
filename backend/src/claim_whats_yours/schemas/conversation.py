"""Pydantic schemas for the conversational eligibility assistant."""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------- request/response models


class ConversationRequest(BaseModel):
    """Body for the assistant turn endpoint.

    The client should send all previously-accepted answers from the conversation
    history, plus the latest user message. The backend merges these and evaluates
    against the scheme rules.

    Nothing from this request is persisted. Profile data lives only in the
    request memory during evaluation.
    """

    model_config = ConfigDict(extra="forbid")

    messages: Annotated[
        list[str],
        Field(description="Conversational history, including the current turn", max_length=100),
    ]
    answers: Annotated[
        dict[str, Any],
        Field(description="Previously-accepted structured answers", default_factory=dict),
    ]
    locale: Annotated[str, Field(default="en", max_length=10)] = "en"
    scheme_ids: Annotated[
        list[str] | None,
        Field(description="Specific schemes to evaluate (optional)", max_length=100),
    ] = None


class ExtractedProfile(BaseModel):
    """Structured profile data extracted from natural language input.

    This is the output from Groq's structured request for field extraction.
    """

    model_config = ConfigDict(extra="forbid")

    language: Annotated[str, Field(description="Detected language code", max_length=10)]
    extracted_answers: Annotated[
        dict[str, Any], Field(description="Extracted profile field values")
    ]
    missing_fields: Annotated[
        list[str], Field(description="Fields needed but not found in input", default_factory=list)
    ]
    clarification_required: Annotated[
        bool, Field(description="True if input was ambiguous and needs follow-up")
    ]
    next_question: Annotated[
        str | None, Field(description="Follow-up question to ask, or None if sufficient data")
    ]
    intent_summary: Annotated[
        str, Field(description="Brief summary of user's intent", max_length=200)
    ]


class ConversationTurnResponse(BaseModel):
    """Response for one turn of the conversation."""

    model_config = ConfigDict(extra="forbid")

    follow_up_question: Annotated[
        str | None, Field(description="Question to ask next, or None if evaluation is ready")
    ]
    extracted_profile: Annotated[
        dict[str, Any], Field(description="Merged profile with new extracted values")
    ]
    missing_fields: Annotated[
        list[str],
        Field(description="Fields still missing for eligibility evaluation", default_factory=list),
    ]
    eligibility_ready: Annotated[
        bool, Field(description="True when sufficient data for eligibility evaluation")
    ]
    evaluation_suggestion: Annotated[
        str | None,
        Field(description="Brief summary of what schemes match", max_length=500, default=None),
    ]


# ---------------------------------------------------------------- error responses

CONVERSATION_INVALID_INPUT = "CONVERSATION_INVALID_INPUT"
CONVERSATION_GROQ_ERROR = "CONVERSATION_GROQ_ERROR"


class ConversationErrorResponse(BaseModel):
    """Standard error response for conversation errors."""

    code: str
    message: str
    request_id: str
