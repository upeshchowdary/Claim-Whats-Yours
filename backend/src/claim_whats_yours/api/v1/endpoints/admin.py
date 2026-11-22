"""Admin endpoints for the scheme lifecycle. Every route requires the X-Admin-Token header."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from claim_whats_yours.api.deps import require_admin
from claim_whats_yours.core.config import get_settings
from claim_whats_yours.core.errors import AppError
from claim_whats_yours.db.session import get_db
from claim_whats_yours.schemas.admin import ActorBody, ReviewerBody
from claim_whats_yours.services.admin_service import (
    archive_scheme,
    import_draft,
    list_versions,
    publish_scheme,
    review_queue,
    validate_scheme,
    verify_scheme,
)
from claim_whats_yours.services.notification_service import (
    NotificationOutboxService,
    NotificationRegistry,
)
from claim_whats_yours.services.sources.source_registry import SourceRegistry

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

_ERROR_MAP: dict[str, tuple[int, str, str]] = {
    "DUPLICATE_SCHEME": (
        409,
        "DUPLICATE_SCHEME",
        "A scheme with this id or slug already exists.",
    ),
    "INVALID_JURISDICTION": (422, "INVALID_JURISDICTION", "Invalid jurisdiction code in record."),
    "SCHEME_NOT_FOUND": (404, "SCHEME_NOT_FOUND", "Scheme not found."),
    "INVALID_TRANSITION": (
        409,
        "INVALID_TRANSITION",
        "The scheme is not in a state that allows this action.",
    ),
    "PUBLICATION_GATE_FAILED": (
        409,
        "PUBLICATION_GATE_FAILED",
        "Scheme failed the publication checks.",
    ),
    "VERIFICATION_STALE": (409, "VERIFICATION_STALE", "Scheme verification is stale."),
    "INVALID_REVIEWER": (422, "VALIDATION_ERROR", "Reviewer name is invalid."),
}


def _map(exc: ValueError) -> AppError:
    status, code, message = _ERROR_MAP.get(
        str(exc), (422, "VALIDATION_ERROR", "Request could not be processed.")
    )
    return AppError(status, code, message)


@router.post("/schemes/import", status_code=201)
def import_scheme(body: dict[str, Any], session: Session = Depends(get_db)) -> dict[str, Any]:
    """Import a source record as a draft. Status is forced to draft regardless of input."""
    try:
        scheme = import_draft(session, body, datetime.now(UTC))
    except ValueError as exc:
        raise _map(exc) from exc
    session.commit()
    return {
        "scheme_id": scheme.id,
        "record_status": scheme.record_status,
        "verification_status": scheme.verification_status,
    }


@router.get("/schemes/review-queue")
def get_review_queue(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return one page of schemes awaiting review."""
    schemes, total = review_queue(session, {"draft", "needs_review"}, page, page_size)
    return {
        "items": [
            {
                "id": scheme.id,
                "name": scheme.name,
                "record_status": scheme.record_status,
                "verification_status": scheme.verification_status,
            }
            for scheme in schemes
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.post("/schemes/{scheme_id}/validate")
def validate(scheme_id: str, session: Session = Depends(get_db)) -> dict[str, Any]:
    """Run the review checks on a scheme and report any errors."""
    try:
        ok, errors = validate_scheme(session, scheme_id, datetime.now(UTC))
    except ValueError as exc:
        if str(exc) == "INVALID_TRANSITION":
            raise AppError(
                409,
                "INVALID_TRANSITION",
                "Scheme is not in a state that can be validated.",
            ) from exc
        raise _map(exc) from exc
    session.commit()
    return {"scheme_id": scheme_id, "valid": ok, "errors": errors}


@router.post("/schemes/{scheme_id}/verify")
def verify(
    scheme_id: str, body: ReviewerBody, session: Session = Depends(get_db)
) -> dict[str, Any]:
    """Record a human verification of a scheme."""
    try:
        scheme = verify_scheme(
            session, scheme_id, body.reviewer, body.verified_at, datetime.now(UTC)
        )
    except ValueError as exc:
        raise _map(exc) from exc
    session.commit()
    return {
        "scheme_id": scheme.id,
        "record_status": scheme.record_status,
        "verification_status": scheme.verification_status,
    }


@router.post("/schemes/{scheme_id}/publish")
def publish(scheme_id: str, body: ActorBody, session: Session = Depends(get_db)) -> dict[str, Any]:
    """Publish a verified scheme after the publication gate and freshness checks."""
    try:
        scheme = publish_scheme(session, scheme_id, body.actor, datetime.now(UTC))
    except ValueError as exc:
        raise _map(exc) from exc
    session.commit()
    return {"scheme_id": scheme.id, "record_status": scheme.record_status}


@router.post("/schemes/{scheme_id}/archive")
def archive(scheme_id: str, body: ActorBody, session: Session = Depends(get_db)) -> dict[str, Any]:
    """Archive a published scheme."""
    try:
        scheme = archive_scheme(session, scheme_id, body.actor, datetime.now(UTC))
    except ValueError as exc:
        raise _map(exc) from exc
    session.commit()
    return {"scheme_id": scheme.id, "record_status": scheme.record_status}


@router.get("/schemes/{scheme_id}/versions")
def get_versions(scheme_id: str, session: Session = Depends(get_db)) -> dict[str, Any]:
    """Return the version history of a scheme without snapshot bodies."""
    versions = list_versions(session, scheme_id)
    if versions is None:
        raise AppError(404, "SCHEME_NOT_FOUND", "Scheme not found.")
    return {
        "items": [
            {
                "version": version.version,
                "change_note": version.change_note,
                "created_at": version.created_at.isoformat(),
            }
            for version in versions
        ]
    }


# ---------------------------------------------------------------- notification endpoints


@router.get("/notifications/health")
def notification_health(session: Session = Depends(get_db)) -> dict[str, Any]:
    """Return notification service health and configuration."""
    settings = get_settings()
    registry = NotificationRegistry(settings)

    return {
        "enabled": settings.notifications_enabled,
        "email_provider": settings.email_provider or None,
        "sms_provider": settings.sms_provider or None,
        "email_adapter_health": registry.get_email_adapter().check_health()
        if hasattr(registry.get_email_adapter(), "check_health")
        else None,
        "sms_adapter_health": registry.get_sms_adapter().check_health()
        if hasattr(registry.get_sms_adapter(), "check_health")
        else None,
    }


@router.post("/notifications/send-reminders")
def send_reminders(session: Session = Depends(get_db)) -> dict[str, Any]:
    """Manually trigger sending of pending notification reminders."""
    service = NotificationOutboxService(get_settings(), session)
    sent = service.send_notifications()

    return {"sent": sent, "status": "ok"}


@router.get("/notifications/outbox/{tracking_id}")
def get_outbox(tracking_id: str, session: Session = Depends(get_db)) -> dict[str, Any]:
    """Return notification history for a tracking record."""
    service = NotificationOutboxService(get_settings(), session)
    outbox = service.get_outbox(tracking_id)

    return {
        "tracking_id": tracking_id,
        "items": [
            {
                "id": item.id,
                "channel": item.channel,
                "subject": item.subject,
                "body": item.body,
                "status": item.status.value,
                "scheduled_at": item.scheduled_at.isoformat(),
                "sent_at": item.sent_at.isoformat() if item.sent_at else None,
                "error": item.error,
            }
            for item in outbox
        ],
    }


# ---------------------------------------------------------------- data source endpoints


@router.get("/data-sources")
def list_data_sources(session: Session = Depends(get_db)) -> dict[str, Any]:
    """Return health status for all configured data sources."""
    settings = get_settings()
    registry = SourceRegistry.from_settings(settings)

    return {
        "sources": registry.health(),
        "enabled_count": len(registry.enabled_adapters()),
    }


@router.post("/data-sources/discover")
def discover_schemes(
    keywords: list[str] = Query(default_factory=list),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Discover schemes from all enabled data sources."""
    settings = get_settings()
    registry = SourceRegistry.from_settings(settings)

    schemes = registry.discover_schemes(keywords)

    return {
        "keywords": keywords,
        "count": len(schemes),
        "items": schemes,
    }


@router.post("/data-sources/{source_name}/health")
def source_health(source_name: str, session: Session = Depends(get_db)) -> dict[str, Any]:
    """Return health status for a specific data source."""
    settings = get_settings()
    registry = SourceRegistry.from_settings(settings)

    adapter = registry.get_adapter(source_name)
    if adapter is None:
        raise AppError(404, "SOURCE_NOT_FOUND", f"Unknown source: {source_name}")

    return {"source": source_name, **adapter.check_health()}
