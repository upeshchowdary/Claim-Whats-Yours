"""Data.gov.in adapter for scheme data.

Uses the official data.gov.in API to fetch scheme information.

Configuration (via environment variables):
    DATA_GOV_IN_ENABLED=false
    DATA_GOV_IN_API_KEY=

Reference: https://data.gov.in/resources
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from claim_whats_yours.core.config import Settings
from claim_whats_yours.services.sources.base_adapter import (
    SourceAdapter,
    SourceAuthError,
    SourceError,
    SourceNotFoundError,
    SourceUnavailableError,
)

logger = logging.getLogger(__name__)


class DataGovAdapter(SourceAdapter):
    """Adapter for data.gov.in scheme data.

    Note: As of 2024, data.gov.in does not provide a direct scheme eligibility
    rules API. This adapter is configured for discovery information and cross-reference.
    Actual eligibility rules should come from official government portals.
    """

    name = "data_gov_in"
    base_url = "https://api.data.gov.in"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._api_key = settings.data_gov_in_api_key.strip()
        self.enabled = settings.data_gov_in_enabled and bool(self._api_key)

        if self.enabled:
            logger.info("DataGovAdapter enabled with API key configured")
        else:
            logger.info("DataGovAdapter disabled (DATA_GOV_IN_ENABLED=false or no API key)")

    def _build_client(self) -> httpx.Client:
        headers: dict[str, str] = {}
        if self._api_key:
            headers["api-key"] = self._api_key
        headers["Accept"] = "application/json"

        return httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=60.0,
        )

    def list_schemes(self, **kwargs) -> list[dict[str, Any]]:
        """Fetch schemes from data.gov.in.

        data.gov.in uses a dataset-based API. We query for datasets with
        scheme-related keywords and extract scheme-like information.
        """
        if not self.enabled:
            raise SourceError("Adapter not enabled", self.name)

        client = self._build_client()
        params: dict[str, str] = {
            "api-key": self._api_key,
            "format": "json",
            **kwargs,
        }

        try:
            response = client.get("/resource/identify", params=params)
        except httpx.RequestError as exc:
            raise SourceUnavailableError(f"Network error: {type(exc).__name__}", self.name) from exc

        if response.status_code == 401:
            raise SourceAuthError("Invalid API key", self.name)
        if response.status_code == 403:
            raise SourceAuthError("Access denied", self.name)
        if response.status_code == 404:
            raise SourceNotFoundError("Dataset not found", self.name)

        if response.status_code != 200:
            raise SourceError(f"HTTP {response.status_code}: {response.text[:200]}", self.name)

        body = response.json()
        # data.gov.in response structure
        if "response" in body:
            return body["response"].get("records", [])
        return []

    def get_scheme(self, scheme_id: str) -> dict[str, Any]:
        """Get a specific scheme from data.gov.in.

        Note: This adapter does not provide eligibility rules. It returns
        discovery information that must be validated against official sources.
        """
        if not self.enabled:
            raise SourceError("Adapter not enabled", self.name)

        # data.gov.in doesn't have a direct scheme-by-id endpoint
        # In production, use this adapter for discovery and cross-reference
        # with official sources, then fetch detailed eligibility data elsewhere.
        raise SourceError(
            "This adapter does not provide scheme-by-id lookup. Use for discovery only.",
            self.name,
        )

    def check_health(self) -> dict[str, Any]:
        """Check data.gov.in API health."""
        if not self.enabled:
            return {
                "status": "disabled",
                "source": self.name,
                "message": "Adapter is disabled",
            }

        try:
            client = self._build_client()
            response = client.get("/resource/identify", params={"api-key": self._api_key})
            if response.status_code == 401:
                return {
                    "status": "error",
                    "source": self.name,
                    "http_status": 401,
                    "message": "Invalid API key",
                }
            if response.status_code == 200:
                return {
                    "status": "ok",
                    "source": self.name,
                    "http_status": 200,
                    "message": "API accessible",
                }
            return {
                "status": "error",
                "source": self.name,
                "http_status": response.status_code,
                "message": "Unexpected status",
            }
        except Exception as exc:
            return {
                "status": "error",
                "source": self.name,
                "message": str(exc),
            }

    def discover_schemes(self, keywords: list[str] | None = None, **kwargs) -> list[dict[str, Any]]:
        """Search for schemes matching keywords.

        Returns discovery records that should be manually verified against
        official sources before use.
        """
        if keywords is None:
            keywords = ["scheme", "benefit", "welfare"]

        results = []
        for keyword in keywords:
            try:
                records = self.list_schemes(q=keyword, **kwargs)
                for record in records:
                    if isinstance(record, dict):
                        results.append(self._normalize_record(record))
            except SourceError as exc:
                logger.warning("Discovery error for '%s': %s", keyword, exc)
        return results

    def _normalize_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Normalize a data.gov.in record to our scheme schema.

        This is a best-effort normalization since data.gov.in data varies
        by dataset. Fields not found are set to None or empty.
        """
        # Try to extract scheme-like data from record
        scheme_id = record.get("id") or record.get("scheme_id") or record.get("oid")
        name = record.get("title") or record.get("scheme_name") or record.get("name")

        return {
            "id": str(scheme_id) if scheme_id else "",
            "name": str(name) if name else "",
            "slug": str(name).lower().replace(" ", "-") if name else "",
            "summary": record.get("description", ""),
            "government_level": record.get("organization_type", "central"),
            "scope": "all_india",  # data.gov.in typically lists national schemes
            "jurisdictions": [],
            "sources": [],
        }
