"""Scheme source adapters base interface and registry.

This module provides a base class for data source adapters and a registry
for managing multiple adapters. Adapters are responsible for fetching
scheme data from official sources.

Source hierarchy (from DATA_GOVERNANCE.md):
1. Original Central Government ministry and department sources
2. Andhra Pradesh state government and department portals
3. Official scheme guidelines, government orders, notifications
4. Official application portals, circulars and FAQs
5. myScheme for scheme discovery and cross-reference
6. data.gov.in as a supplementary dataset source
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from claim_whats_yours.core.config import Settings

logger = logging.getLogger(__name__)


class SourceAdapter(ABC):
    """Base class for scheme data source adapters."""

    name: str
    base_url: str

    def __init__(self, settings: Settings) -> None:
        self._cfg = settings
        self.enabled = False

    def is_enabled(self) -> bool:
        """Check if this adapter is enabled."""
        return self.enabled

    @abstractmethod
    def list_schemes(self, **kwargs) -> list[dict[str, Any]]:
        """Return a list of schemes from this source.

        Each scheme dict should contain:
        - id: unique scheme identifier
        - name: official scheme name
        - slug: URL-friendly identifier
        - summary: brief description
        - government_level: central / state / ut / local
        - scope: all_india / state / ut / district
        - eligibility_rule: rule tree per domain/rules.py grammar
        - payload: additional data (benefits, documents, steps)
        - jurisdictions: list of jurisdiction codes
        - sources: list of source records

        May raise SourceError for network/HTTP errors.
        """
        raise NotImplementedError

    @abstractmethod
    def get_scheme(self, scheme_id: str) -> dict[str, Any]:
        """Return a single scheme by ID.

        Raises SourceError if not found.
        """
        raise NotImplementedError

    @abstractmethod
    def check_health(self) -> dict[str, Any]:
        """Return adapter health status."""
        raise NotImplementedError


class SourceError(Exception):
    """Base exception for source adapter errors."""

    def __init__(self, message: str, source_name: str | None = None) -> None:
        if source_name:
            message = f"[{source_name}] {message}"
        super().__init__(message)
        self.source_name = source_name


class SourceUnavailableError(SourceError):
    """Raised when the source is temporarily unavailable."""


class SourceAuthError(SourceError):
    """Raised when authentication fails (401/403)."""


class SourceNotFoundError(SourceError):
    """Raised when a scheme is not found (404)."""
