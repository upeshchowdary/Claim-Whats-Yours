"""Stateless eligibility evaluation endpoint. Nothing from the request is stored or logged."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from claim_whats_yours.db.session import get_db
from claim_whats_yours.schemas.eligibility import EvaluateRequest
from claim_whats_yours.services.eligibility_service import evaluate_profile

router = APIRouter(prefix="/eligibility", tags=["eligibility"])


@router.post("/evaluate", response_model=None)
def evaluate(
    body: EvaluateRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> JSONResponse | dict[str, Any]:
    """Evaluate published schemes against the supplied answers without persisting them."""
    request_id = getattr(request.state, "request_id", "unknown")
    categories = set(body.filters.categories) or None
    government_levels = set(body.filters.government_levels) or None
    result = evaluate_profile(
        session,
        body.answers,
        datetime.now(UTC),
        government_levels,
        categories=categories,
    )
    if "errors" in result:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "The profile answers are invalid.",
                    "request_id": request_id,
                    "details": result["errors"],
                }
            },
        )
    return {"request_id": request_id, **result}
