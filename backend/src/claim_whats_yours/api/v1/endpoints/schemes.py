"""Public read-only scheme endpoints."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.orm import Session

from claim_whats_yours.core.errors import AppError
from claim_whats_yours.db.session import get_db
from claim_whats_yours.domain.geography import is_valid_jurisdiction_code
from claim_whats_yours.services.scheme_service import (
    get_published_scheme,
    list_published_schemes,
    scheme_detail,
    scheme_summary,
)

router = APIRouter(prefix="/schemes", tags=["schemes"])


@router.get("")
def list_schemes(
    request: Request,
    q: str | None = Query(default=None, max_length=200),
    government_level: (
        list[Literal["central", "state", "ut", "district"]] | None
    ) = Query(default=None),
    state_code: str | None = Query(default=None, max_length=16),
    district_code: str | None = Query(default=None, max_length=16),
    category: list[str] | None = Query(default=None),
    beneficiary_group: list[str] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return one page of published schemes matching the filters."""
    if "status" in request.query_params:
        raise AppError(400, "INVALID_QUERY", "The status filter is not available on this endpoint.")
    if state_code is not None and not is_valid_jurisdiction_code(state_code):
        raise AppError(422, "VALIDATION_ERROR", "Unknown state_code.")

    items, total = list_published_schemes(
        session,
        q,
        government_level,
        state_code,
        district_code,
        category,
        beneficiary_group,
        page,
        page_size,
    )
    return {
        "items": [scheme_summary(s) for s in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/{scheme_id}")
def get_scheme(
    scheme_id: str = Path(max_length=64),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return the detail view of one published scheme."""
    scheme = get_published_scheme(session, scheme_id)
    if scheme is None:
        raise AppError(404, "SCHEME_NOT_FOUND", "Scheme not found.")
    return scheme_detail(scheme)
