"""Shared fixtures for Claim What's Yours E2E test suite."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

DEFAULT_ADMIN_TOKEN = "test-admin-token-123"


@pytest.fixture(scope="session")
def client() -> Iterator[Any]:
    """Shared HTTP client fixture.

    If E2E_BASE_URL is set in environment, tests execute against the live HTTP server.
    Otherwise, tests execute against an in-process FastAPI application instance using TestClient.
    """
    base_url = os.environ.get("E2E_BASE_URL")
    if base_url:
        with httpx.Client(base_url=base_url, timeout=30.0) as http_client:
            yield http_client
    else:
        # Resolve backend database path if not explicitly configured
        repo_root = Path(__file__).resolve().parents[2]
        db_path = repo_root / "backend" / "claim_whats_yours.db"
        if "DATABASE_URL" not in os.environ and db_path.exists():
            os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

        os.environ.setdefault("ADMIN_API_TOKEN", DEFAULT_ADMIN_TOKEN)

        from claim_whats_yours.core.config import get_settings
        get_settings.cache_clear()

        from claim_whats_yours.main import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as test_client:
            yield test_client


@pytest.fixture
def admin_token() -> str:
    """Configured admin API token."""
    return os.environ.get("ADMIN_API_TOKEN", DEFAULT_ADMIN_TOKEN)


@pytest.fixture
def admin_headers(admin_token: str) -> dict[str, str]:
    """Valid admin authentication headers."""
    return {"X-Admin-Token": admin_token}


@pytest.fixture
def invalid_admin_headers() -> dict[str, str]:
    """Invalid admin authentication headers."""
    return {"X-Admin-Token": "completely-invalid-admin-token-xyz"}


@pytest.fixture
def sample_central_scheme_id() -> str:
    """ID of a known published Central scheme."""
    return "sch_pm_kisan_2019"


@pytest.fixture
def sample_state_scheme_id() -> str:
    """ID of a known published State scheme."""
    return "sch_ap_rythu_bharosa"


@pytest.fixture
def sample_svanidhi_scheme_id() -> str:
    """ID of PM SVANidhi scheme."""
    return "sch_pm_svanidhi"


@pytest.fixture
def valid_farmer_profile() -> dict[str, Any]:
    """Persona 1 (Ramesh Kumar): Marginal Farmer, AP, Guntur."""
    return {
        "state_code": "IN-AP",
        "district_code": "IN-AP-GNT",
        "age_years": 42,
        "gender": "male",
        "social_category": "obc",
        "occupation": "farmer",
        "is_farmer": True,
        "landholding_acres": 2.2,
        "annual_household_income_inr": 110000,
    }


@pytest.fixture
def valid_vendor_profile() -> dict[str, Any]:
    """Persona 2 (Sunita Devi): Urban Street Vendor, UP, Lucknow."""
    return {
        "state_code": "IN-UP",
        "residence": "urban",
        "age_years": 38,
        "gender": "female",
        "social_category": "sc",
        "occupation": "self_employed",
        "is_unorganised_worker": True,
        "is_farmer": False,
        "landholding_acres": 0.0,
        "annual_household_income_inr": 85000,
    }


@pytest.fixture
def valid_student_profile() -> dict[str, Any]:
    """Persona 3 (Priya Sharma): Low-Income Student, MH, Pune."""
    return {
        "state_code": "IN-MH",
        "residence": "urban",
        "age_years": 19,
        "gender": "female",
        "social_category": "ews",
        "occupation": "student",
        "is_student": True,
        "education_level": "higher_secondary",
        "annual_household_income_inr": 140000,
        "is_farmer": False,
    }


@pytest.fixture
def tracking_payload(sample_central_scheme_id: str) -> dict[str, Any]:
    """Valid payload for creating an anonymous application tracking record."""
    return {
        "scheme_id": sample_central_scheme_id,
        "status": "submitted",
    }
