"""Shared pytest fixtures. All scheme and jurisdiction data here is synthetic."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from claim_whats_yours.core.config import get_settings
from claim_whats_yours.db import models
from claim_whats_yours.db.base import Base

ADMIN_TOKEN = "test-admin-token-123"


@pytest.fixture
def engine() -> Iterator[Engine]:
    """In-memory SQLite engine shared across connections, with all tables created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """Session seeded with the synthetic jurisdiction rows."""
    session = Session(bind=engine)
    session.add_all(
        [
            models.Jurisdiction(code="IN", name="India", level="all_india", parent_code=None),
            models.Jurisdiction(
                code="IN-AP", name="Andhra Pradesh", level="state", parent_code=None
            ),
            models.Jurisdiction(code="IN-KA", name="Karnataka", level="state", parent_code=None),
        ]
    )
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """FastAPI TestClient whose get_db dependency is bound to the test engine."""
    from fastapi.testclient import TestClient

    from claim_whats_yours.app import app
    from claim_whats_yours.db.session import get_db

    monkeypatch.setenv("ADMIN_API_TOKEN", ADMIN_TOKEN)
    get_settings.cache_clear()

    def override() -> Iterator[Session]:
        session = Session(bind=engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
def admin_headers() -> dict[str, str]:
    """Headers carrying the synthetic admin token."""
    return {"X-Admin-Token": ADMIN_TOKEN}


@pytest.fixture
def scheme_factory() -> Callable[..., models.Scheme]:
    """Return a function that inserts a synthetic Scheme with one source."""

    def make_scheme(
        session: Session,
        scheme_id: str,
        scope: str = "all_india",
        state_codes: tuple[str, ...] = (),
        government_level: str = "central",
        record_status: str = "published",
        verification_status: str = "verified",
        review_due_at: datetime | None = None,
        categories: tuple[str, ...] = ("education",),
        rule_age_min: int = 18,
    ) -> models.Scheme:
        now = datetime.now(UTC)
        scheme = models.Scheme(
            id=scheme_id,
            slug=scheme_id,
            name="Synthetic scheme " + scheme_id,
            summary="Synthetic test fixture",
            government_level=government_level,
            scope=scope,
            record_status=record_status,
            verification_status=verification_status,
            last_verified_at=now,
            review_due_at=review_due_at or now + timedelta(days=365),
            eligibility_rule={
                "all": [
                    {
                        "criterion_id": "min_age",
                        "field": "age_years",
                        "operator": "gte",
                        "value": rule_age_min,
                        "mandatory": True,
                        "explanation": "Age at least " + str(rule_age_min),
                        "source_refs": ["s1"],
                    }
                ]
            },
            payload={
                "categories": list(categories),
                "beneficiary_groups": ["students"],
                "documents": [],
                "application_steps": [],
                "application_url": None,
            },
            current_version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(scheme)
        session.add(
            models.SchemeSource(
                scheme_id=scheme_id,
                id="s1",
                title="Synthetic source",
                publisher="Synthetic",
                url="https://example.gov.in/synthetic",
                source_type="guideline",
                official_status="official",
                access_date=date.today(),
            )
        )
        if scope != "all_india":
            for code in state_codes:
                session.add(models.SchemeJurisdiction(scheme_id=scheme_id, jurisdiction_code=code))
        session.flush()
        session.commit()
        return scheme

    return make_scheme
