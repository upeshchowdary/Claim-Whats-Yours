"""Team-aware API key manager for Groq credentials.

Design rules:
- Rate limits at Groq are per-API-key (requests/min, tokens/min per model).
  Keys from different accounts are genuinely independent. Keys from the same
  account still share account-level limits, so we track team_label to model this.
- A 429 triggers a per-team cooldown (not per-key rotation to bypass limits).
- Key cycling within the same team is NOT a legitimate way to bypass rate limits.
- Failover to a different key is only meaningful when keys belong to independently
  provisioned accounts with separate capacity.

Thread-safety: all mutable state is protected by a threading.Lock so the manager
is safe for use in a multi-threaded FastAPI/uvicorn setup.

Nothing in this module makes network calls.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from claim_whats_yours.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class CredentialState(StrEnum):
    HEALTHY = "healthy"
    COOLDOWN = "cooldown"  # 429 — quota exhausted, back off
    INVALID = "invalid"  # 401/403 — key is wrong or disabled
    DISABLED = "disabled"  # slot was empty at startup


@dataclass
class _KeySlot:
    """Internal state for one credential slot. Never exposed via API."""

    slot_index: int  # 1-based
    team_label: str  # operator-defined label, e.g. "slot-1"
    _key: str = field(repr=False)  # kept private; never logged or returned

    state: CredentialState = CredentialState.HEALTHY
    cooldown_until: float = 0.0
    consecutive_failures: int = 0
    last_success_at: float = 0.0
    total_requests: int = 0
    total_failures: int = 0
    last_error_category: str = ""

    def is_usable(self, now: float) -> bool:
        if self.state == CredentialState.DISABLED:
            return False
        if self.state == CredentialState.INVALID:
            return False
        if self.state == CredentialState.COOLDOWN and now < self.cooldown_until:
            return False
        # Cooldown window elapsed — reset to healthy automatically
        if self.state == CredentialState.COOLDOWN and now >= self.cooldown_until:
            self.state = CredentialState.HEALTHY
        return True

    def public_info(self, now: float) -> dict[str, Any]:
        """Non-sensitive health snapshot suitable for admin endpoints."""
        # Reflect the effective state: if cooldown has elapsed, report HEALTHY.
        effective_state = self.state
        if effective_state == CredentialState.COOLDOWN and now >= self.cooldown_until:
            effective_state = CredentialState.HEALTHY
        remaining = (
            max(0.0, self.cooldown_until - now)
            if effective_state == CredentialState.COOLDOWN
            else 0.0
        )
        return {
            "slot": self.slot_index,
            "team_label": self.team_label,
            "state": effective_state.value,
            "cooldown_remaining_seconds": round(remaining, 1),
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "last_success_at": self.last_success_at or None,
            "last_error_category": self.last_error_category or None,
        }


class NoUsableCredentialError(RuntimeError):
    """Raised when no key slot is currently available."""


class GroqKeyManager:
    """Manages up to three Groq credential slots with team-aware rate limiting.

    Usage:
        manager = GroqKeyManager.from_settings()
        slot = manager.acquire()          # raises NoUsableCredentialError if none available
        try:
            ...make request using manager.get_key(slot)...
            manager.record_success(slot)
        except SomeError as exc:
            manager.record_failure(slot, http_status=429, retry_after=60)
    """

    def __init__(self, slots: list[_KeySlot]) -> None:
        self._slots = slots
        self._lock = threading.Lock()
        logger.info(
            "GroqKeyManager initialised: %d slot(s) configured, %d active",
            len(slots),
            sum(1 for s in slots if s.state != CredentialState.DISABLED),
        )

    # ---------------------------------------------------------------- factory

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> GroqKeyManager:
        """Build from application settings. Empty key strings → DISABLED slot."""
        cfg = settings or get_settings()
        raw_slots = [
            (1, cfg.groq_api_key_1, cfg.groq_team_label_1),
            (2, cfg.groq_api_key_2, cfg.groq_team_label_2),
            (3, cfg.groq_api_key_3, cfg.groq_team_label_3),
        ]
        slots: list[_KeySlot] = []
        for idx, key, label in raw_slots:
            if not key.strip():
                slots.append(
                    _KeySlot(
                        slot_index=idx,
                        team_label=label,
                        _key="",
                        state=CredentialState.DISABLED,
                    )
                )
                logger.debug("Groq key slot %d is empty — disabled", idx)
            else:
                slots.append(_KeySlot(slot_index=idx, team_label=label, _key=key))
                logger.info("Groq key slot %d (%s) loaded", idx, label)
        return cls(slots)

    # ---------------------------------------------------------------- public interface

    def acquire(self) -> _KeySlot:
        """Return the first usable slot in priority order (slot 1 → 2 → 3).

        Raises NoUsableCredentialError when no slot is available.
        Caller must call record_success() or record_failure() after every attempt.
        """
        now = time.monotonic()
        with self._lock:
            for slot in self._slots:
                if slot.is_usable(now):
                    slot.total_requests += 1
                    return slot
        raise NoUsableCredentialError(
            "No Groq credential is currently available. "
            "All slots are disabled, invalid, or in cooldown."
        )

    def get_key(self, slot: _KeySlot) -> str:
        """Return the raw key for a slot. Only called by the HTTP layer, never logged."""
        return slot._key  # noqa: SLF001

    def record_success(self, slot: _KeySlot) -> None:
        """Mark a request as successful."""
        now = time.monotonic()
        with self._lock:
            slot.last_success_at = now
            slot.consecutive_failures = 0
            if slot.state == CredentialState.COOLDOWN:
                slot.state = CredentialState.HEALTHY

    def record_failure(
        self,
        slot: _KeySlot,
        *,
        http_status: int | None = None,
        retry_after: float | None = None,
        error_category: str = "unknown",
    ) -> None:
        """Update slot state based on failure type.

        Args:
            slot: the slot that failed.
            http_status: HTTP status code returned by the provider, or None for network errors.
            retry_after: seconds from the Retry-After header (429 responses).
            error_category: short string for observability (e.g. "rate_limited", "auth_error").
        """
        now = time.monotonic()
        with self._lock:
            slot.total_failures += 1
            slot.consecutive_failures += 1
            slot.last_error_category = error_category

            if http_status in (401, 403):
                # Key is wrong or revoked — do not retry with this slot.
                slot.state = CredentialState.INVALID
                logger.warning(
                    "Groq slot %d (%s): marked INVALID after HTTP %s",
                    slot.slot_index,
                    slot.team_label,
                    http_status,
                )

            elif http_status == 429:
                # Team-level quota exhausted. Put the entire team label into cooldown.
                # retry_after comes from the Retry-After header; default to 60 s.
                backoff = retry_after if retry_after and retry_after > 0 else 60.0
                self._apply_team_cooldown(slot.team_label, now + backoff)
                logger.warning(
                    "Groq team '%s': 429 received — cooldown %.0f s",
                    slot.team_label,
                    backoff,
                )

    def apply_team_cooldown(self, team_label: str, cooldown_seconds: float) -> None:
        """Externally trigger a team-level cooldown (e.g. from circuit-breaker logic)."""
        now = time.monotonic()
        with self._lock:
            self._apply_team_cooldown(team_label, now + cooldown_seconds)

    def _apply_team_cooldown(self, team_label: str, until: float) -> None:
        """Must be called with self._lock held."""
        for slot in self._slots:
            if slot.team_label == team_label and slot.state not in (
                CredentialState.DISABLED,
                CredentialState.INVALID,
            ):
                slot.state = CredentialState.COOLDOWN
                slot.cooldown_until = max(slot.cooldown_until, until)

    def health_snapshot(self) -> dict[str, Any]:
        """Non-sensitive health info for the admin endpoint."""
        now = time.monotonic()
        with self._lock:
            slot_infos = [s.public_info(now) for s in self._slots]
            active = sum(1 for s in self._slots if s.is_usable(now))
        return {
            "configured_slots": len(self._slots),
            "active_slots": active,
            "slots": slot_infos,
        }
