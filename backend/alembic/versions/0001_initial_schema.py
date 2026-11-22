"""Initial schema: jurisdictions, schemes, scheme links, sources, versions, tracking.

Revision ID: 0001_initial
Revises:
Create Date: 2025-01-01

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jurisdictions",
        sa.Column("code", sa.String(length=16), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("parent_code", sa.String(length=16), nullable=True),
    )

    op.create_table(
        "schemes",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("slug", sa.String(length=120), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("government_level", sa.String(length=16), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("record_status", sa.String(length=16), nullable=False),
        sa.Column("verification_status", sa.String(length=16), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("eligibility_rule", sa.JSON(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("current_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_schemes_record_status", "schemes", ["record_status"])
    op.create_index("ix_schemes_government_level", "schemes", ["government_level"])
    op.create_index("ix_schemes_scope", "schemes", ["scope"])

    op.create_table(
        "scheme_jurisdictions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "scheme_id",
            sa.String(length=64),
            sa.ForeignKey("schemes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "jurisdiction_code",
            sa.String(length=16),
            sa.ForeignKey("jurisdictions.code"),
            nullable=False,
        ),
        sa.UniqueConstraint("scheme_id", "jurisdiction_code"),
    )

    op.create_table(
        "scheme_sources",
        sa.Column(
            "scheme_id",
            sa.String(length=64),
            sa.ForeignKey("schemes.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("publisher", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("official_status", sa.String(length=32), nullable=False),
        sa.Column("access_date", sa.Date(), nullable=False),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
    )

    op.create_table(
        "scheme_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "scheme_id",
            sa.String(length=64),
            sa.ForeignKey("schemes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=True),
        sa.Column("change_note", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scheme_id", "version"),
    )

    op.create_table(
        "tracking_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tracking_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("access_token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "scheme_id",
            sa.String(length=64),
            sa.ForeignKey("schemes.id"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("progress_date", sa.Date(), nullable=True),
        sa.Column("reminder_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_tracking_records_access_token_hash",
        "tracking_records",
        ["access_token_hash"],
    )


def downgrade() -> None:
    op.drop_table("tracking_records")
    op.drop_table("scheme_versions")
    op.drop_table("scheme_sources")
    op.drop_table("scheme_jurisdictions")
    op.drop_table("schemes")
    op.drop_table("jurisdictions")
