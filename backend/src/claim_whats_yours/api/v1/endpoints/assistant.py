"""Conversational eligibility assistant endpoint.

POST /api/v1/assistant/turn is stateless: the client sends its accepted profile
answers with the current message. The server neither persists profile answers nor
conversation history.
"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from claim_whats_yours.core.config import Settings, get_settings
from claim_whats_yours.core.errors import AppError
from claim_whats_yours.schemas.conversation import ConversationRequest, ConversationTurnResponse
from claim_whats_yours.services.ai.conversation_service import ConversationService
from claim_whats_yours.services.ai.groq_client import GroqError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/turn", response_model=ConversationTurnResponse)
def assistant_turn(
    body: ConversationRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> ConversationTurnResponse | JSONResponse:
    """Process one stateless conversational profile-collection turn."""
    request_id = str(getattr(request.state, "request_id", "unknown"))
    try:
        return ConversationService.from_settings(settings).turn(body)
    except ValueError as exc:
        raise AppError(422, "VALIDATION_ERROR", str(exc)) from exc
    except GroqError as exc:
        logger.warning("assistant_unavailable request_id=%s code=%s", request_id, exc.code)
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": exc.code,
                    "message": "The conversational assistant is currently unavailable.",
                    "request_id": request_id,
                }
            },
        )
