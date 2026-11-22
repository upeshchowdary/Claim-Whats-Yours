"""ORM models. Layering: db only; no FastAPI imports, no citizen-profile table."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from claim_whats_yours.db.base import Base, utc_now


class Jurisdiction(Base):
    __tablename__ = "jurisdictions"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    level: Mapped[str] = mapped_column(String(16))
    parent_code: Mapped[str | None] = mapped_column(String(16), nullable=True)


class Scheme(Base):
    __tablename__ = "schemes"
    __table_args__ = (
        Index("ix_schemes_record_status", "record_status"),
        Index("ix_schemes_government_level", "government_level"),
        Index("ix_schemes_scope", "scope"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    government_level: Mapped[str] = mapped_column(String(16))
    scope: Mapped[str] = mapped_column(String(16))
    record_status: Mapped[str] = mapped_column(String(16))
    verification_status: Mapped[str] = mapped_column(String(16))
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    eligibility_rule: Mapped[dict | list | None] = mapped_column(JSON)
    payload: Mapped[dict | list | None] = mapped_column(JSON)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    jurisdictions: Mapped[list[SchemeJurisdiction]] = relationship(
        back_populates="scheme", cascade="all, delete-orphan"
    )
    sources: Mapped[list[SchemeSource]] = relationship(
        back_populates="scheme", cascade="all, delete-orphan"
    )
    versions: Mapped[list[SchemeVersion]] = relationship(
        back_populates="scheme", cascade="all, delete-orphan"
    )
    notifications: Mapped[list[NotificationOutbox]] = relationship(
        back_populates="scheme", cascade="all, delete-orphan"
    )


class SchemeJurisdiction(Base):
    __tablename__ = "scheme_jurisdictions"
    __table_args__ = (UniqueConstraint("scheme_id", "jurisdiction_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_id: Mapped[str] = mapped_column(String(64), ForeignKey("schemes.id", ondelete="CASCADE"))
    jurisdiction_code: Mapped[str] = mapped_column(String(16), ForeignKey("jurisdictions.code"))

    scheme: Mapped[Scheme] = relationship(back_populates="jurisdictions")


class SchemeSource(Base):
    __tablename__ = "scheme_sources"

    scheme_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("schemes.id", ondelete="CASCADE"), primary_key=True
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    publisher: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(2048))
    source_type: Mapped[str] = mapped_column(String(64))
    official_status: Mapped[str] = mapped_column(String(32))
    access_date: Mapped[date] = mapped_column(Date)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)

    scheme: Mapped[Scheme] = relationship(back_populates="sources")


class SchemeVersion(Base):
    __tablename__ = "scheme_versions"
    __table_args__ = (UniqueConstraint("scheme_id", "version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_id: Mapped[str] = mapped_column(String(64), ForeignKey("schemes.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict | list | None] = mapped_column(JSON)
    change_note: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    scheme: Mapped[Scheme] = relationship(back_populates="versions")


class TrackingRecord(Base):
    __tablename__ = "tracking_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tracking_id: Mapped[str] = mapped_column(String(64), unique=True)
    access_token_hash: Mapped[str] = mapped_column(String(64), index=True)
    scheme_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("schemes.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16))
    progress_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reminder_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    notifications: Mapped[list[NotificationOutbox]] = relationship(
        back_populates="tracking", cascade="all, delete-orphan"
    )


class NotificationOutbox(Base):
    """Durable notification outbox for email/SMS reminders.

    Notifications are stored here for idempotent retry. Once sent, the record
    is updated with status SENT and sent_at timestamp.
    """

    __tablename__ = "notification_outbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tracking_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tracking_records.tracking_id"), nullable=True
    )
    scheme_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("schemes.id"), nullable=True
    )
    recipient: Mapped[str] = mapped_column(String(255))
    channel: Mapped[str] = mapped_column(String(16))  # "email" or "sms"
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))  # pending/sent/failed
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    tracking: Mapped[TrackingRecord | None] = relationship(
        back_populates="notifications", foreign_keys=[tracking_id]
    )
    scheme: Mapped[Scheme | None] = relationship(
        back_populates="notifications", foreign_keys=[scheme_id]
    )
