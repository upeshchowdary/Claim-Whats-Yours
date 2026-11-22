"""Unit tests for GroqKeyManager — all tests are offline (no network calls)."""

from __future__ import annotations

import time

import pytest

from claim_whats_yours.core.config import Settings
from claim_whats_yours.services.ai.groq_key_manager import (
    CredentialState,
    GroqKeyManager,
    NoUsableCredentialError,
)

# ---------------------------------------------------------------- helpers


def _settings(**overrides) -> Settings:
    """Return a Settings instance with Groq enabled and test keys."""
    base = dict(
        groq_enabled=True,
        groq_api_key_1="key-aaa",
        groq_api_key_2="key-bbb",
        groq_api_key_3="key-ccc",
        groq_team_label_1="team-alpha",
        groq_team_label_2="team-alpha",  # same team → shared quota
        groq_team_label_3="team-beta",  # different team → independent quota
        groq_circuit_breaker_threshold=5,
        groq_circuit_breaker_reset_seconds=60.0,
        groq_timeout_seconds=45.0,
        groq_max_retries=4,
        groq_max_output_tokens=2000,
        groq_model="llama3-8b-8192",
        groq_api_base_url="https://api.groq.com/openai/v1",
        data_gov_in_enabled=False,
        notifications_enabled=False,
    )
    base.update(overrides)
    return Settings(**base)


def _manager(**kw) -> GroqKeyManager:
    return GroqKeyManager.from_settings(_settings(**kw))


# ---------------------------------------------------------------- configuration


def test_empty_key_slot_is_disabled() -> None:
    mgr = _manager(groq_api_key_1="", groq_api_key_2="", groq_api_key_3="key-ccc")
    snap = mgr.health_snapshot()
    assert snap["configured_slots"] == 3
    assert snap["slots"][0]["state"] == CredentialState.DISABLED
    assert snap["slots"][1]["state"] == CredentialState.DISABLED
    assert snap["slots"][2]["state"] == CredentialState.HEALTHY


def test_all_empty_keys_means_no_active_slots() -> None:
    mgr = _manager(groq_api_key_1="", groq_api_key_2="", groq_api_key_3="")
    assert mgr.health_snapshot()["active_slots"] == 0


def test_three_keys_means_three_active_slots() -> None:
    mgr = _manager()
    assert mgr.health_snapshot()["active_slots"] == 3


def test_key_is_never_exposed_in_health_snapshot() -> None:
    mgr = _manager()
    snap = mgr.health_snapshot()
    # Stringify the entire snapshot and make sure no key prefix appears
    text = str(snap)
    assert "key-aaa" not in text
    assert "key-bbb" not in text
    assert "key-ccc" not in text


# ---------------------------------------------------------------- acquire / success


def test_acquire_returns_first_healthy_slot() -> None:
    mgr = _manager()
    slot = mgr.acquire()
    assert slot.slot_index == 1


def test_acquire_skips_disabled_slot() -> None:
    mgr = _manager(groq_api_key_1="")
    slot = mgr.acquire()
    assert slot.slot_index == 2


def test_acquire_raises_when_no_slots_available() -> None:
    mgr = _manager(groq_api_key_1="", groq_api_key_2="", groq_api_key_3="")
    with pytest.raises(NoUsableCredentialError):
        mgr.acquire()


def test_record_success_clears_consecutive_failures() -> None:
    mgr = _manager()
    slot = mgr.acquire()
    slot.consecutive_failures = 3
    mgr.record_success(slot)
    assert slot.consecutive_failures == 0


def test_record_success_records_timestamp() -> None:
    mgr = _manager()
    slot = mgr.acquire()
    mgr.record_success(slot)
    assert slot.last_success_at > 0


# ---------------------------------------------------------------- 401 / 403 → invalid


def test_401_marks_slot_invalid() -> None:
    mgr = _manager()
    slot = mgr.acquire()
    mgr.record_failure(slot, http_status=401, error_category="auth_error")
    assert slot.state == CredentialState.INVALID


def test_403_marks_slot_invalid() -> None:
    mgr = _manager()
    slot = mgr.acquire()
    mgr.record_failure(slot, http_status=403, error_category="auth_error")
    assert slot.state == CredentialState.INVALID


def test_invalid_slot_is_skipped_on_next_acquire() -> None:
    mgr = _manager()
    slot = mgr.acquire()
    mgr.record_failure(slot, http_status=401, error_category="auth_error")
    next_slot = mgr.acquire()
    assert next_slot.slot_index == 2


def test_all_slots_invalid_raises() -> None:
    mgr = _manager()
    for _ in range(3):
        s = mgr.acquire()
        mgr.record_failure(s, http_status=401, error_category="auth_error")
    with pytest.raises(NoUsableCredentialError):
        mgr.acquire()


# ---------------------------------------------------------------- 429 → team cooldown


def test_429_puts_same_team_slots_in_cooldown() -> None:
    """Slots 1 and 2 share team-alpha; a 429 on slot 1 must also cool down slot 2."""
    mgr = _manager()
    slot1 = mgr.acquire()
    assert slot1.slot_index == 1
    mgr.record_failure(slot1, http_status=429, retry_after=120.0, error_category="rate_limited")

    # Both team-alpha slots should be in cooldown
    snap = mgr.health_snapshot()
    assert snap["slots"][0]["state"] == CredentialState.COOLDOWN
    assert snap["slots"][1]["state"] == CredentialState.COOLDOWN
    # team-beta slot 3 should still be healthy
    assert snap["slots"][2]["state"] == CredentialState.HEALTHY


def test_429_failover_to_independent_team() -> None:
    """After a 429 on team-alpha, team-beta (slot 3) should be acquirable."""
    mgr = _manager()
    slot1 = mgr.acquire()
    mgr.record_failure(slot1, http_status=429, retry_after=120.0, error_category="rate_limited")
    next_slot = mgr.acquire()
    assert next_slot.slot_index == 3  # team-beta
    assert next_slot.team_label == "team-beta"


def test_cooldown_expires_and_slot_becomes_usable(monkeypatch) -> None:
    """After the cooldown window elapses, the slot should become HEALTHY again."""
    mgr = _manager()
    slot = mgr.acquire()
    mgr.record_failure(slot, http_status=429, retry_after=1.0, error_category="rate_limited")
    assert slot.state == CredentialState.COOLDOWN

    # Advance monotonic time past the cooldown
    original = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: original() + 5.0)

    snap = mgr.health_snapshot()
    assert snap["slots"][0]["state"] == CredentialState.HEALTHY


def test_429_default_cooldown_is_60s_when_no_retry_after() -> None:
    mgr = _manager()
    t_before = time.monotonic()
    slot = mgr.acquire()
    mgr.record_failure(slot, http_status=429, retry_after=None, error_category="rate_limited")
    assert slot.state == CredentialState.COOLDOWN
    assert slot.cooldown_until >= t_before + 59.0  # at least 59 s (allow minor float delta)


# ---------------------------------------------------------------- health snapshot


def test_health_snapshot_shape() -> None:
    mgr = _manager()
    snap = mgr.health_snapshot()
    assert "configured_slots" in snap
    assert "active_slots" in snap
    assert "slots" in snap
    assert len(snap["slots"]) == 3


def test_health_snapshot_contains_team_labels() -> None:
    mgr = _manager()
    snap = mgr.health_snapshot()
    labels = {s["team_label"] for s in snap["slots"]}
    assert "team-alpha" in labels
    assert "team-beta" in labels


def test_total_requests_increments_on_acquire() -> None:
    mgr = _manager()
    slot = mgr.acquire()
    mgr.record_success(slot)
    slot2 = mgr.acquire()
    mgr.record_success(slot2)
    assert slot.total_requests == 2


def test_total_failures_increments_on_failure() -> None:
    mgr = _manager()
    # Use slot 3 (team-beta) to avoid cascading cooldown on slot 1+2
    mgr._slots[0].state = CredentialState.DISABLED
    mgr._slots[1].state = CredentialState.DISABLED
    slot = mgr.acquire()
    mgr.record_failure(slot, http_status=500, error_category="server_error")
    assert slot.total_failures == 1
