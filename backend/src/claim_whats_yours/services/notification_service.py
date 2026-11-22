"""Notification service with adapter pattern for email/SMS/push.

This module provides a durable notification outbox and idempotent delivery.
Reminders are sent by a separate worker process to avoid blocking requests.

Configuration (environment variables):
    NOTIFICATIONS_ENABLED=false
    EMAIL_PROVIDER=  # e.g., "sendgrid", "smtp", "postmark"
    EMAIL_API_KEY=
    SMS_PROVIDER=    # e.g., "twilio", "vonage"
    SMS_API_KEY=

Adapter types:
    - "sendgrid": SendGrid SMTP API
    - "smtp": Generic SMTP (requires SMTP_* env vars)
    - "twilio": Twilio SMS API
    - "null": No-op adapter for testing
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from claim_whats_yours.core.config import Settings

logger = logging.getLogger(__name__)


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    EXPIRED = "expired"
    SUPPRESSED = "suppressed"


@dataclass
class NotificationOutbox:
    """A notification record waiting to be sent."""

    id: str
    tracking_id: str | None
    scheme_id: str | None
    recipient: str
    channel: str  # "email" or "sms"
    subject: str | None  # email only
    body: str
    status: NotificationStatus
    scheduled_at: datetime
    sent_at: datetime | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)


class NotificationAdapter(ABC):
    """Base class for notification adapters."""

    name: str

    @abstractmethod
    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email. Returns True on success."""

    @abstractmethod
    def send_sms(self, to: str, body: str) -> bool:
        """Send an SMS. Returns True on success."""


class NullAdapter(NotificationAdapter):
    """No-op adapter for testing and disabled state."""

    name = "null"

    def send_email(self, to: str, subject: str, body: str) -> bool:
        logger.info("[null] Would send email to %s: %s", to, subject)
        return True

    def send_sms(self, to: str, body: str) -> bool:
        logger.info("[null] Would send SMS to %s", to)
        return True


class SmtpAdapter(NotificationAdapter):
    """SMTP email adapter. Configured via SMTP_* environment variables."""

    name = "smtp"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._from_address = settings.smtp_from_address or "noreply@claimwhatssyours.gov.in"
        self._enabled = bool(settings.smtp_host)

    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send email via SMTP. Returns True on success."""
        if not self._enabled:
            logger.warning("SMTP adapter disabled")
            return False

        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["From"] = self._from_address
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        try:
            with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port) as server:
                if self._settings.smtp_use_tls:
                    server.starttls()
                if self._settings.smtp_user:
                    server.login(self._settings.smtp_user, self._settings.smtp_password)
                server.send_message(msg)
            return True
        except Exception as exc:
            logger.error("SMTP send failed: %s", exc)
            return False

    def send_sms(self, to: str, body: str) -> bool:
        logger.warning("SMTP adapter does not support SMS")
        return False


class SendGridAdapter(NotificationAdapter):
    """SendGrid email adapter using HTTP API."""

    name = "sendgrid"

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.sendgrid_api_key.strip() if settings.sendgrid_api_key else ""
        self._from_address = settings.smtp_from_address or "noreply@claimwhatssyours.gov.in"
        self._enabled = bool(self._api_key)

    def send_email(self, to: str, subject: str, body: str) -> bool:
        if not self._enabled:
            logger.warning("SendGrid adapter disabled")
            return False

        import httpx

        url = "https://api.sendgrid.com/v3/mail/send"
        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": self._from_address},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client() as client:
                response = client.post(url, json=payload, headers=headers)
                if response.status_code in (200, 202):
                    return True
                logger.error("SendGrid error: %s %s", response.status_code, response.text)
                return False
        except Exception as exc:
            logger.error("SendGrid send failed: %s", exc)
            return False

    def send_sms(self, to: str, body: str) -> bool:
        logger.warning("SendGrid adapter does not support SMS")
        return False


class TwilioAdapter(NotificationAdapter):
    """Twilio SMS adapter."""

    name = "twilio"

    def __init__(self, settings: Settings) -> None:
        self._account_sid = (
            settings.twilio_account_sid.strip() if settings.twilio_account_sid else ""
        )
        self._auth_token = settings.twilio_auth_token.strip() if settings.twilio_auth_token else ""
        self._from_number = (
            settings.twilio_from_number.strip() if settings.twilio_from_number else ""
        )
        self._enabled = bool(self._account_sid and self._auth_token and self._from_number)

    def send_sms(self, to: str, body: str) -> bool:
        if not self._enabled:
            logger.warning("Twilio adapter disabled")
            return False

        import httpx

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self._account_sid}/Messages.json"
        payload = {
            "From": self._from_number,
            "To": to,
            "Body": body,
        }

        try:
            with httpx.Client() as client:
                response = client.post(
                    url,
                    data=payload,
                    auth=(self._account_sid, self._auth_token),
                )
                if response.status_code in (200, 201):
                    return True
                logger.error("Twilio error: %s %s", response.status_code, response.text)
                return False
        except Exception as exc:
            logger.error("Twilio send failed: %s", exc)
            return False

    def send_email(self, to: str, subject: str, body: str) -> bool:
        logger.warning("Twilio adapter does not support email")
        return False


# ---------------------------------------------------------------- registry


class NotificationRegistry:
    """Registry and factory for notification adapters."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_email_adapter(self) -> NotificationAdapter:
        """Return the configured email adapter, or NullAdapter if disabled."""
        if not self._settings.notifications_enabled:
            return NullAdapter()

        provider = self._settings.email_provider.strip().lower()
        if provider == "sendgrid":
            return SendGridAdapter(self._settings)
        if provider == "smtp":
            return SmtpAdapter(self._settings)
        if provider == "twilio":
            return TwilioAdapter(self._settings)
        logger.warning("Unknown email provider: %s", self._settings.email_provider)
        return NullAdapter()

    def get_sms_adapter(self) -> NotificationAdapter:
        """Return the configured SMS adapter, or NullAdapter if disabled."""
        if not self._settings.notifications_enabled:
            return NullAdapter()

        provider = self._settings.sms_provider.strip().lower()
        if provider == "twilio":
            return TwilioAdapter(self._settings)
        if provider == "smtp":
            return NullAdapter()  # SMTP is email-only
        logger.warning("Unknown SMS provider: %s", self._settings.sms_provider)
        return NullAdapter()


# ---------------------------------------------------------------- outbox service


class NotificationOutboxService:
    """Durable notification outbox service.

    Stores notifications in the database for idempotent retry and
    prevents duplicate sends (e.g., same tracking reminder).
    """

    def __init__(self, settings: Settings, session: Session | None = None) -> None:
        self._settings = settings
        self._session = session
        self._registry = NotificationRegistry(settings)

    def _get_session(self) -> Session:
        if self._session:
            return self._session
        from claim_whats_yours.db.session import get_session

        return next(get_session())

    def enqueue_reminder(
        self,
        tracking_id: str,
        scheme_id: str | None,
        recipient: str,
        subject: str,
        body: str,
        scheduled_at: datetime,
    ) -> NotificationOutbox:
        """Enqueue a notification for later delivery.

        Returns the created outbox record.
        """
        # Check for existing pending notification for this tracking
        session = self._get_session()
        existing = session.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.tracking_id == tracking_id,
                NotificationOutbox.status == NotificationStatus.PENDING,
            )
        )
        if existing:
            logger.debug("Notification already pending for tracking %s", tracking_id)
            return existing

        outbox = NotificationOutbox(
            id=str(uuid.uuid4()),
            tracking_id=tracking_id,
            scheme_id=scheme_id,
            recipient=recipient,
            channel="email",
            subject=subject,
            body=body,
            status=NotificationStatus.PENDING,
            scheduled_at=scheduled_at,
        )
        session.add(outbox)
        session.flush()
        return outbox

    def send_notifications(self) -> int:
        """Send all pending notifications. Returns count sent."""
        session = self._get_session()
        now = datetime.now()

        pending = session.scalars(
            select(NotificationOutbox).where(
                NotificationOutbox.status == NotificationStatus.PENDING,
                NotificationOutbox.scheduled_at <= now,
            )
        ).all()

        sent = 0
        for outbox in pending:
            adapter = self._registry.get_email_adapter()
            success = adapter.send_email(
                to=outbox.recipient,
                subject=outbox.subject or "",
                body=outbox.body,
            )

            if success:
                outbox.status = NotificationStatus.SENT
                outbox.sent_at = now
            else:
                outbox.status = NotificationStatus.FAILED
                outbox.error = "send_failed"
            session.flush()
            sent += 1

        return sent

    def get_outbox(self, tracking_id: str) -> list[NotificationOutbox]:
        """Get notification history for a tracking record."""
        session = self._get_session()
        return list(
            session.scalars(
                select(NotificationOutbox)
                .where(NotificationOutbox.tracking_id == tracking_id)
                .order_by(NotificationOutbox.created_at.desc())
            ).all()
        )
