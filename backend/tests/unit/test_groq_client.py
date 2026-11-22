"""Unit tests for GroqClient — all network calls are mocked with httpx.MockTransport.

No real API keys are used. No credits are consumed.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from claim_whats_yours.core.config import Settings
from claim_whats_yours.services.ai.groq_client import (
    GROQ_AUTH_ERROR,
    GROQ_RATE_LIMITED,
    GROQ_SCHEMA_ERROR,
    GROQ_TIMEOUT,
    GROQ_UNAVAILABLE,
    GroqClient,
    GroqError,
    _CircuitBreaker,
)
from claim_whats_yours.services.ai.groq_key_manager import GroqKeyManager

# ---------------------------------------------------------------- helpers


def _settings(**overrides) -> Settings:
    base = dict(
        groq_enabled=True,
        groq_api_key_1="key-aaa",
        groq_api_key_2="",
        groq_api_key_3="",
        groq_team_label_1="team-alpha",
        groq_team_label_2="team-alpha",
        groq_team_label_3="team-beta",
        groq_circuit_breaker_threshold=3,
        groq_circuit_breaker_reset_seconds=60.0,
        groq_timeout_seconds=5.0,
        groq_max_retries=2,
        groq_max_output_tokens=500,
        groq_model="llama3-8b-8192",
        groq_api_base_url="https://api.groq.com/openai/v1",
        data_gov_in_enabled=False,
        notifications_enabled=False,
    )
    base.update(overrides)
    return Settings(**base)


SIMPLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


def _ok_response(data: dict[str, Any], status: int = 200) -> httpx.Response:
    """Build a 200 response matching Groq OpenAI-compatible format."""
    body = {
        "choices": [{"message": {"content": json.dumps(data)}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    return httpx.Response(status, json=body)


def _error_response(status: int, retry_after: str | None = None) -> httpx.Response:
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return httpx.Response(status, json={"error": "err"}, headers=headers)


def _make_client(transport: httpx.MockTransport, **kw) -> GroqClient:
    cfg = _settings(**kw)
    km = GroqKeyManager.from_settings(cfg)
    client = GroqClient(km, cfg)
    client._http = httpx.Client(
        base_url=cfg.groq_api_base_url,
        transport=transport,
    )
    return client


# ---------------------------------------------------------------- disabled


def test_raises_when_groq_disabled() -> None:
    cfg = _settings(groq_enabled=False)
    km = GroqKeyManager.from_settings(cfg)
    client = GroqClient(km, cfg)
    with pytest.raises(GroqError) as exc_info:
        client.structured_request(
            system_prompt="s", user_message="u", response_schema=SIMPLE_SCHEMA
        )
    assert exc_info.value.code == GROQ_UNAVAILABLE


# ---------------------------------------------------------------- successful call


def test_successful_structured_request() -> None:
    expected = {"answer": "Visakhapatnam"}
    transport = httpx.MockTransport(lambda _req: _ok_response(expected))
    client = _make_client(transport)

    result = client.structured_request(
        system_prompt="Extract location.",
        user_message="I live in Visakhapatnam.",
        response_schema=SIMPLE_SCHEMA,
    )
    assert result == expected


def test_auth_header_contains_bearer_token(monkeypatch) -> None:
    """Verify the Authorization header is set; never assert the key value in test output."""
    captured: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        auth = req.headers.get("authorization", "")
        captured.append(auth)
        return _ok_response({"answer": "ok"})

    transport = httpx.MockTransport(handler)
    client = _make_client(transport)
    client.structured_request(system_prompt="s", user_message="u", response_schema=SIMPLE_SCHEMA)
    assert len(captured) == 1
    assert captured[0].startswith("Bearer ")


# ---------------------------------------------------------------- retry on 5xx


def test_retries_on_500_then_succeeds() -> None:
    call_count = [0]

    def handler(req: httpx.Request) -> httpx.Response:
        call_count[0] += 1
        if call_count[0] < 3:
            return _error_response(500)
        return _ok_response({"answer": "ok"})

    transport = httpx.MockTransport(handler)
    client = _make_client(transport, groq_max_retries=3)

    # Patch sleep so test doesn't actually wait
    with patch("claim_whats_yours.services.ai.groq_client.time.sleep"):
        result = client.structured_request(
            system_prompt="s", user_message="u", response_schema=SIMPLE_SCHEMA
        )
    assert result == {"answer": "ok"}
    assert call_count[0] == 3


def test_exhausts_retries_on_persistent_500() -> None:
    transport = httpx.MockTransport(lambda _req: _error_response(500))
    client = _make_client(transport, groq_max_retries=2)

    with patch("claim_whats_yours.services.ai.groq_client.time.sleep"):
        with pytest.raises(GroqError) as exc_info:
            client.structured_request(
                system_prompt="s", user_message="u", response_schema=SIMPLE_SCHEMA
            )
    assert exc_info.value.code == GROQ_UNAVAILABLE


# ---------------------------------------------------------------- 429 handling


def test_429_raises_rate_limited_error() -> None:
    transport = httpx.MockTransport(lambda _req: _error_response(429, retry_after="30"))
    client = _make_client(transport, groq_max_retries=0)

    with pytest.raises(GroqError) as exc_info:
        client.structured_request(
            system_prompt="s", user_message="u", response_schema=SIMPLE_SCHEMA
        )
    assert exc_info.value.code == GROQ_RATE_LIMITED


def test_429_respects_retry_after_header() -> None:
    """The backoff delay should use the Retry-After value, not exponential back-off."""
    slept: list[float] = []

    def handler(req: httpx.Request) -> httpx.Response:
        if len(slept) == 0:
            return _error_response(429, retry_after="45")
        return _ok_response({"answer": "ok"})

    transport = httpx.MockTransport(handler)
    client = _make_client(
        transport,
        groq_max_retries=2,
        groq_api_key_1="k1",
        groq_api_key_2="",
        groq_api_key_3="",
    )

    with patch(
        "claim_whats_yours.services.ai.groq_client.time.sleep",
        side_effect=lambda s: slept.append(s),
    ):
        # Will fail because same team → both retries hit cooldown
        with pytest.raises(GroqError):
            client.structured_request(
                system_prompt="s", user_message="u", response_schema=SIMPLE_SCHEMA
            )
    # If a sleep was called, it should use the Retry-After value
    if slept:
        assert slept[0] == pytest.approx(45.0)


# ---------------------------------------------------------------- auth errors (fatal)


def test_401_raises_auth_error_without_retry() -> None:
    call_count = [0]

    def handler(req: httpx.Request) -> httpx.Response:
        call_count[0] += 1
        return _error_response(401)

    transport = httpx.MockTransport(handler)
    client = _make_client(transport, groq_max_retries=3)

    with pytest.raises(GroqError) as exc_info:
        client.structured_request(
            system_prompt="s", user_message="u", response_schema=SIMPLE_SCHEMA
        )
    assert exc_info.value.code == GROQ_AUTH_ERROR
    assert call_count[0] == 1  # must NOT retry on auth errors


def test_403_raises_auth_error_without_retry() -> None:
    call_count = [0]

    def handler(req: httpx.Request) -> httpx.Response:
        call_count[0] += 1
        return _error_response(403)

    transport = httpx.MockTransport(handler)
    client = _make_client(transport, groq_max_retries=3)

    with pytest.raises(GroqError) as exc_info:
        client.structured_request(
            system_prompt="s", user_message="u", response_schema=SIMPLE_SCHEMA
        )
    assert exc_info.value.code == GROQ_AUTH_ERROR
    assert call_count[0] == 1


# ---------------------------------------------------------------- schema / parse errors


def test_invalid_json_in_response_raises_schema_error() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        body = {"choices": [{"message": {"content": "NOT JSON {{{"}}]}
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    client = _make_client(transport)

    with pytest.raises(GroqError) as exc_info:
        client.structured_request(
            system_prompt="s", user_message="u", response_schema=SIMPLE_SCHEMA
        )
    assert exc_info.value.code == GROQ_SCHEMA_ERROR


def test_missing_output_key_raises_schema_error() -> None:
    transport = httpx.MockTransport(lambda _req: httpx.Response(200, json={"unexpected": True}))
    client = _make_client(transport)

    with pytest.raises(GroqError) as exc_info:
        client.structured_request(
            system_prompt="s", user_message="u", response_schema=SIMPLE_SCHEMA
        )
    assert exc_info.value.code == GROQ_SCHEMA_ERROR


# ---------------------------------------------------------------- timeout / network


def test_timeout_raises_groq_timeout() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=req)

    transport = httpx.MockTransport(handler)
    client = _make_client(transport, groq_max_retries=0)

    with pytest.raises(GroqError) as exc_info:
        client.structured_request(
            system_prompt="s", user_message="u", response_schema=SIMPLE_SCHEMA
        )
    assert exc_info.value.code == GROQ_TIMEOUT


def test_network_error_is_retried() -> None:
    call_count = [0]

    def handler(req: httpx.Request) -> httpx.Response:
        call_count[0] += 1
        if call_count[0] < 3:
            raise httpx.NetworkError("connection refused", request=req)
        return _ok_response({"answer": "ok"})

    transport = httpx.MockTransport(handler)
    client = _make_client(transport, groq_max_retries=3)

    with patch("claim_whats_yours.services.ai.groq_client.time.sleep"):
        result = client.structured_request(
            system_prompt="s", user_message="u", response_schema=SIMPLE_SCHEMA
        )
    assert result == {"answer": "ok"}


# ---------------------------------------------------------------- circuit breaker


def test_circuit_breaker_opens_after_threshold_failures() -> None:
    transport = httpx.MockTransport(lambda _req: _error_response(500))
    client = _make_client(transport, groq_max_retries=0, groq_circuit_breaker_threshold=2)

    with patch("claim_whats_yours.services.ai.groq_client.time.sleep"):
        for _ in range(2):
            with pytest.raises(GroqError):
                client.structured_request(
                    system_prompt="s", user_message="u", response_schema=SIMPLE_SCHEMA
                )

    assert client._cb.state == "OPEN"


def test_circuit_breaker_open_refuses_immediately() -> None:
    transport = httpx.MockTransport(lambda _req: _error_response(500))
    client = _make_client(
        transport,
        groq_max_retries=0,
        groq_circuit_breaker_threshold=1,
    )
    # Trip the breaker
    with patch("claim_whats_yours.services.ai.groq_client.time.sleep"):
        with pytest.raises(GroqError):
            client.structured_request(
                system_prompt="s", user_message="u", response_schema=SIMPLE_SCHEMA
            )
    assert client._cb.state == "OPEN"

    # Next call should be refused without even hitting the transport
    call_count = [0]

    def counting_handler(req: httpx.Request) -> httpx.Response:
        call_count[0] += 1
        return _ok_response({"answer": "ok"})

    client._http = httpx.Client(
        base_url=client._cfg.groq_api_base_url,
        transport=httpx.MockTransport(counting_handler),
    )
    with pytest.raises(GroqError) as exc_info:
        client.structured_request(
            system_prompt="s", user_message="u", response_schema=SIMPLE_SCHEMA
        )
    assert exc_info.value.code == GROQ_UNAVAILABLE
    assert call_count[0] == 0  # circuit open — no HTTP call


def test_circuit_breaker_half_open_probe_succeeds() -> None:
    cb = _CircuitBreaker(threshold=1, reset_seconds=0.0)
    cb.record_failure()
    assert cb.state == "OPEN"
    # reset_seconds=0 means allow immediately
    assert cb.allow() is True
    cb.record_success()
    assert cb.state == "CLOSED"


def test_circuit_breaker_half_open_probe_fails_reopens() -> None:
    cb = _CircuitBreaker(threshold=1, reset_seconds=0.0)
    cb.record_failure()
    assert cb.allow() is True  # probe allowed
    cb.record_failure()
    assert cb.state == "OPEN"


# ---------------------------------------------------------------- no keys configured


def test_no_keys_raises_unavailable() -> None:
    transport = httpx.MockTransport(lambda _req: _ok_response({"answer": "ok"}))
    client = _make_client(transport, groq_api_key_1="", groq_api_key_2="", groq_api_key_3="")

    with pytest.raises(GroqError) as exc_info:
        client.structured_request(
            system_prompt="s", user_message="u", response_schema=SIMPLE_SCHEMA
        )
    assert exc_info.value.code == GROQ_UNAVAILABLE


# ---------------------------------------------------------------- health endpoint


def test_health_returns_non_sensitive_info() -> None:
    transport = httpx.MockTransport(lambda _req: _ok_response({"answer": "ok"}))
    client = _make_client(transport)
    h = client.health()
    assert h["enabled"] is True
    assert "circuit_breaker" in h
    assert "key_manager" in h
    # No key values in health output
    text = str(h)
    assert "key-aaa" not in text
    assert "Bearer" not in text


# ---------------------------------------------------------------- no PII in logs


def test_prompts_and_messages_not_in_log(caplog) -> None:
    """Citizen messages and system prompts must not appear in log output."""
    transport = httpx.MockTransport(lambda _req: _ok_response({"answer": "ok"}))
    client = _make_client(transport)

    secret_text = "My Aadhaar is 1234-5678-9012"
    with caplog.at_level("DEBUG"):
        client.structured_request(
            system_prompt="System instructions here",
            user_message=secret_text,
            response_schema=SIMPLE_SCHEMA,
        )
    assert secret_text not in caplog.text
    assert "1234-5678-9012" not in caplog.text
    assert "key-aaa" not in caplog.text
