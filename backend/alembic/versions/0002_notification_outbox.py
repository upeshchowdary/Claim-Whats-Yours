"""Add durable notification outbox.

Revision ID: 0002_notification_outbox
Revises: 0001_initial
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_notification_outbox"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "tracking_id",
            sa.String(length=64),
            sa.ForeignKey("tracking_records.tracking_id"),
            nullable=True,
        ),
        sa.Column("scheme_id", sa.String(length=64), sa.ForeignKey("schemes.id"), nullable=True),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_notification_outbox_status_scheduled_at",
        "notification_outbox",
        ["status", "scheduled_at"],
    )
    op.create_index(
        "ix_notification_outbox_tracking_id",
        "notification_outbox",
        ["tracking_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_outbox_tracking_id", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_status_scheduled_at", table_name="notification_outbox")
    op.drop_table("notification_outbox")
