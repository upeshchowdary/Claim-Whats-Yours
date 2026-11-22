"""Registry and factory for scheme source adapters.

This module manages all available adapters and provides a unified interface
for data ingestion. It handles adapter configuration, health monitoring,
and coordinated multi-source queries.

Example usage:
    from claim_whats_yours.core.config import get_settings
    from claim_whats_yours.services.sources.source_registry import SourceRegistry

    registry = SourceRegistry.from_settings(get_settings())

    # List all enabled adapters
    for adapter in registry.enabled_adapters():
        print(f"{adapter.name}: {adapter.is_enabled()}")

    # Discover schemes from all sources
    schemes = registry.discover_schemes(keywords=["farmer", "welfare"])

    # Get health status
    health = registry.health()
"""

from __future__ import annotations

import logging
from typing import Any

from claim_whats_yours.core.config import Settings, get_settings
from claim_whats_yours.services.sources.base_adapter import SourceAdapter, SourceError
from claim_whats_yours.services.sources.data_gov_adapter import DataGovAdapter

logger = logging.getLogger(__name__)


class SourceRegistry:
    """Registry and factory for scheme source adapters.

    Manages multiple adapters with the same interface. Each adapter can be
    enabled/disabled independently via configuration.
    """

    _ADAPTER_CLASSES: dict[str, type[SourceAdapter]] = {
        "data_gov_in": DataGovAdapter,
    }

    def __init__(self, adapters: list[SourceAdapter]) -> None:
        self._adapters = adapters
        self._adapter_map = {a.name: a for a in adapters}

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> SourceRegistry:
        """Build registry from application settings."""
        cfg = settings or get_settings()

        adapters: list[SourceAdapter] = []

        # Initialize data.gov.in adapter
        data_gov = DataGovAdapter(cfg)
        if data_gov.enabled:
            adapters.append(data_gov)
            logger.info("SourceRegistry: DataGovAdapter enabled")

        logger.info("SourceRegistry: %d adapter(s) enabled", len(adapters))
        return cls(adapters)

    def get_adapter(self, name: str) -> SourceAdapter | None:
        """Get an adapter by name."""
        return self._adapter_map.get(name)

    def enabled_adapters(self) -> list[SourceAdapter]:
        """Return list of currently enabled adapters."""
        return [a for a in self._adapters if a.is_enabled()]

    def discover_schemes(self, keywords: list[str] | None = None, **kwargs) -> list[dict[str, Any]]:
        """Discover schemes from all enabled sources.

        Returns a flattened list of schemes from all adapters.
        Duplicates should be resolved by the caller using scheme IDs.
        """
        results: list[dict[str, Any]] = []
        for adapter in self.enabled_adapters():
            try:
                schemes = adapter.discover_schemes(keywords, **kwargs)
                results.extend(schemes)
                logger.info(
                    "SourceRegistry: Discovered %d schemes from %s",
                    len(schemes),
                    adapter.name,
                )
            except SourceError as exc:
                logger.warning("SourceRegistry: Discovery failed for %s: %s", adapter.name, exc)
        return results

    def health(self) -> dict[str, Any]:
        """Get health status for all adapters."""
        health_info = {}
        for adapter in self._adapters:
            try:
                health_info[adapter.name] = adapter.check_health()
            except Exception as exc:
                health_info[adapter.name] = {
                    "status": "error",
                    "source": adapter.name,
                    "message": str(exc),
                }
        return health_info

    def list_schemes(self, **kwargs) -> list[dict[str, Any]]:
        """List schemes from all enabled adapters."""
        results: list[dict[str, Any]] = []
        for adapter in self.enabled_adapters():
            try:
                schemes = adapter.list_schemes(**kwargs)
                results.extend(schemes)
                logger.info("SourceRegistry: Loaded %d schemes from %s", len(schemes), adapter.name)
            except SourceError as exc:
                logger.warning("SourceRegistry: list_schemes failed for %s: %s", adapter.name, exc)
        return results

    def get_scheme(self, scheme_id: str) -> dict[str, Any] | None:
        """Try to get a scheme from any adapter."""
        for adapter in self.enabled_adapters():
            try:
                scheme = adapter.get_scheme(scheme_id)
                return scheme
            except SourceError as exc:
                logger.debug("SourceRegistry: %s not found in %s: %s", scheme_id, adapter.name, exc)
        return None
