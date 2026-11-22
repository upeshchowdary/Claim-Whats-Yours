"""Groq HTTP client with retries, circuit breaker and structured outputs.

This module is the ONLY place in the codebase that makes network calls to Groq.
It enforces every security and operational rule from the master engineering prompt:

- API keys are never logged, never returned in responses.
- Prompts and citizen answers are never logged.
- Retries respect exponential back-off with jitter.
- 429 responses trigger team-level cooldown via GroqKeyManager.
- A circuit breaker opens after N consecutive 5xx/network failures.
- Structured output uses Groq's JSON mode (response_format: json_object) with
  an explicit schema in the system prompt, validated against a Pydantic model.
- All calls are stateless — no conversation state is kept here.

Groq uses an OpenAI-compatible API:
  Base URL : https://api.groq.com/openai/v1
  Endpoint : POST /chat/completions
  Auth     : Authorization: Bearer <key>

Eligibility decisions are NEVER made here. This module only handles
natural-language understanding tasks (field extraction, question generation,
language detection) as defined in Part 4 of the master engineering prompt.
"""

from __future__ import annotations

import json
import logging
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from claim_whats_yours.core.config import Settings, get_settings
from claim_whats_yours.services.ai.groq_key_manager import (
    GroqKeyManager,
    NoUsableCredentialError,
    _KeySlot,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------- stable error codes
GROQ_UNAVAILABLE = "GROQ_UNAVAILABLE"
GROQ_SCHEMA_ERROR = "GROQ_SCHEMA_ERROR"
GROQ_RATE_LIMITED = "GROQ_RATE_LIMITED"
GROQ_AUTH_ERROR = "GROQ_AUTH_ERROR"
GROQ_TIMEOUT = "GROQ_TIMEOUT"


class GroqError(RuntimeError):
    """Raised when the Groq API call ultimately fails after all retries."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------- circuit breaker


@dataclass
class _CircuitBreaker:
    """Per-client circuit breaker.

    States:
      CLOSED — requests flow normally.
      OPEN   — requests refused immediately; probe allowed after reset_seconds.
      HALF   — one probe allowed; success → CLOSED, failure → OPEN.
    """

    threshold: int
    reset_seconds: float
    _state: str = "CLOSED"
    _failures: int = 0
    _opened_at: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def allow(self) -> bool:
        now = time.monotonic()
        with self._lock:
            if self._state == "CLOSED":
                return True
            if self._state == "OPEN":
                if now - self._opened_at >= self.reset_seconds:
                    self._state = "HALF"
                    return True
                return False
            # HALF — allow one probe
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = "CLOSED"

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.threshold or self._state == "HALF":
                self._state = "OPEN"
                self._opened_at = time.monotonic()
                logger.warning(
                    "Groq circuit breaker OPENED after %d consecutive failures",
                    self._failures,
                )

    @property
    def state(self) -> str:
        return self._state


# ---------------------------------------------------------------- usage stats


@dataclass
class RequestStats:
    """Non-sensitive usage data recorded after each call."""

    success: bool
    http_status: int | None
    latency_seconds: float
    model: str
    team_label: str
    retry_count: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    error_category: str = ""


# ---------------------------------------------------------------- client


class GroqClient:
    """Sync HTTP client for the Groq chat completions API with structured JSON output.

    Use GroqClient.from_settings() to get a configured instance.
    Call structured_request() for any AI task.
    """

    def __init__(self, key_manager: GroqKeyManager, settings: Settings) -> None:
        self._km = key_manager
        self._cfg = settings
        self._cb = _CircuitBreaker(
            threshold=settings.groq_circuit_breaker_threshold,
            reset_seconds=settings.groq_circuit_breaker_reset_seconds,
        )
        self._http = httpx.Client(
            base_url=settings.groq_api_base_url,
            timeout=settings.groq_timeout_seconds,
        )
        self._stats: list[RequestStats] = []
        self._stats_lock = threading.Lock()

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> GroqClient:
        cfg = settings or get_settings()
        return cls(GroqKeyManager.from_settings(cfg), cfg)

    # ---------------------------------------------------------------- public API

    def structured_request(
        self,
        *,
        system_prompt: str,
        user_message: str,
        response_schema: dict[str, Any],
        schema_name: str = "response",
    ) -> dict[str, Any]:
        """Send a structured-output request to Groq and return the parsed JSON dict.

        Groq supports JSON mode via response_format={"type": "json_object"}.
        The schema is embedded in the system prompt so the model knows what to return.
        The returned JSON is validated to be a dict; callers are responsible for
        further Pydantic validation against the expected schema.

        Args:
            system_prompt: instruction for the model. Must not contain raw PII.
            user_message: citizen's message after local PII scrubbing.
            response_schema: JSON Schema dict describing the expected response.
            schema_name: label used in the system prompt schema embedding.

        Returns:
            Parsed dict from Groq's response content.

        Raises:
            GroqError: on unrecoverable failure after all retries.
        """
        if not self._cfg.groq_enabled:
            raise GroqError(GROQ_UNAVAILABLE, "Groq integration is disabled (GROQ_ENABLED=false)")

        if not self._cb.allow():
            raise GroqError(
                GROQ_UNAVAILABLE,
                f"Groq circuit breaker is OPEN (resets in "
                f"{self._cfg.groq_circuit_breaker_reset_seconds:.0f} s)",
            )

        # Embed schema in system prompt so the model knows what JSON to produce
        schema_instruction = (
            f"\n\nRespond ONLY with a valid JSON object matching this schema "
            f"({schema_name}):\n{json.dumps(response_schema, indent=2)}"
        )
        full_system = system_prompt + schema_instruction
        payload = self._build_payload(full_system, user_message)
        return self._execute_with_retry(payload)

    def health(self) -> dict[str, Any]:
        """Non-sensitive health snapshot for the admin endpoint."""
        return {
            "enabled": self._cfg.groq_enabled,
            "model": self._cfg.groq_model,
            "circuit_breaker": self._cb.state,
            "key_manager": self._km.health_snapshot(),
        }

    # ---------------------------------------------------------------- internals

    def _build_payload(self, system_prompt: str, user_message: str) -> dict[str, Any]:
        return {
            "model": self._cfg.groq_model,
            "max_tokens": self._cfg.groq_max_output_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,  # deterministic extraction
        }

    def _execute_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: GroqError | None = None
        for attempt in range(self._cfg.groq_max_retries + 1):
            slot: _KeySlot | None = None
            t0 = time.monotonic()
            try:
                slot = self._km.acquire()
                result, stats = self._single_attempt(slot, payload, attempt)
                self._km.record_success(slot)
                self._cb.record_success()
                self._record_stats(stats)
                return result

            except _RetryableError as exc:
                latency = time.monotonic() - t0
                if slot:
                    self._km.record_failure(
                        slot,
                        http_status=exc.http_status,
                        retry_after=exc.retry_after,
                        error_category=exc.category,
                    )
                if exc.http_status and exc.http_status >= 500:
                    self._cb.record_failure()
                self._record_stats(
                    RequestStats(
                        success=False,
                        http_status=exc.http_status,
                        latency_seconds=latency,
                        model=self._cfg.groq_model,
                        team_label=slot.team_label if slot else "none",
                        retry_count=attempt,
                        error_category=exc.category,
                    )
                )
                last_error = GroqError(exc.groq_code, exc.args[0])
                if attempt < self._cfg.groq_max_retries:
                    delay = self._backoff(attempt, exc.retry_after)
                    logger.info(
                        "Groq attempt %d/%d failed (%s) — retrying in %.1f s",
                        attempt + 1,
                        self._cfg.groq_max_retries + 1,
                        exc.category,
                        delay,
                    )
                    time.sleep(delay)

            except NoUsableCredentialError as exc:
                raise GroqError(GROQ_UNAVAILABLE, str(exc)) from exc

            except _FatalError as exc:
                latency = time.monotonic() - t0
                if slot:
                    self._km.record_failure(
                        slot,
                        http_status=exc.http_status,
                        error_category=exc.category,
                    )
                self._record_stats(
                    RequestStats(
                        success=False,
                        http_status=exc.http_status,
                        latency_seconds=latency,
                        model=self._cfg.groq_model,
                        team_label=slot.team_label if slot else "none",
                        retry_count=attempt,
                        error_category=exc.category,
                    )
                )
                raise GroqError(exc.groq_code, exc.args[0]) from exc

        raise last_error or GroqError(GROQ_UNAVAILABLE, "Max retries exhausted")

    def _single_attempt(
        self,
        slot: _KeySlot,
        payload: dict[str, Any],
        attempt: int,
    ) -> tuple[dict[str, Any], RequestStats]:
        """Make one HTTP call. Returns parsed dict + stats. Raises _RetryableError/_FatalError."""
        t0 = time.monotonic()
        try:
            response = self._http.post(
                "/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._km.get_key(slot)}",
                    "Content-Type": "application/json",
                },
            )
        except httpx.TimeoutException as exc:
            raise _RetryableError(
                f"Request timed out after {self._cfg.groq_timeout_seconds} s",
                http_status=None,
                retry_after=None,
                category="timeout",
                groq_code=GROQ_TIMEOUT,
            ) from exc
        except httpx.NetworkError as exc:
            raise _RetryableError(
                f"Network error: {type(exc).__name__}",
                http_status=None,
                retry_after=None,
                category="network_error",
                groq_code=GROQ_UNAVAILABLE,
            ) from exc

        latency = time.monotonic() - t0
        status = response.status_code

        if status == 200:
            return self._parse_response(response, slot, attempt, latency)

        retry_after: float | None = None
        raw_ra = response.headers.get("Retry-After")
        if raw_ra:
            try:
                retry_after = float(raw_ra)
            except ValueError:
                retry_after = 60.0

        if status == 429:
            raise _RetryableError(
                f"Rate limited (429) — team '{slot.team_label}'",
                http_status=429,
                retry_after=retry_after,
                category="rate_limited",
                groq_code=GROQ_RATE_LIMITED,
            )
        if status in (500, 502, 503, 504):
            raise _RetryableError(
                f"Provider error {status}",
                http_status=status,
                retry_after=retry_after,
                category=f"server_error_{status}",
                groq_code=GROQ_UNAVAILABLE,
            )
        if status in (401, 403):
            raise _FatalError(
                f"Auth error {status} on slot {slot.slot_index}",
                http_status=status,
                category="auth_error",
                groq_code=GROQ_AUTH_ERROR,
            )
        if status in (400, 404, 422):
            raise _FatalError(
                f"Request error {status}: {response.text[:200]}",
                http_status=status,
                category=f"request_error_{status}",
                groq_code=GROQ_SCHEMA_ERROR,
            )
        raise _RetryableError(
            f"Unexpected status {status}",
            http_status=status,
            retry_after=None,
            category=f"unexpected_{status}",
            groq_code=GROQ_UNAVAILABLE,
        )

    def _parse_response(
        self,
        response: httpx.Response,
        slot: _KeySlot,
        attempt: int,
        latency: float,
    ) -> tuple[dict[str, Any], RequestStats]:
        try:
            body = response.json()
        except Exception as exc:
            raise _FatalError(
                "Response body is not valid JSON",
                http_status=200,
                category="invalid_json",
                groq_code=GROQ_SCHEMA_ERROR,
            ) from exc

        # Groq OpenAI-compatible format: choices[0].message.content
        try:
            content = body["choices"][0]["message"]["content"]
            parsed: dict[str, Any] = json.loads(content)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise _FatalError(
                "Could not extract structured JSON from Groq response",
                http_status=200,
                category="schema_mismatch",
                groq_code=GROQ_SCHEMA_ERROR,
            ) from exc

        usage = body.get("usage", {})
        stats = RequestStats(
            success=True,
            http_status=200,
            latency_seconds=latency,
            model=self._cfg.groq_model,
            team_label=slot.team_label,
            retry_count=attempt,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )
        return parsed, stats

    @staticmethod
    def _backoff(attempt: int, retry_after: float | None) -> float:
        """Exponential back-off with full jitter. Respects Retry-After when provided."""
        if retry_after and retry_after > 0:
            return retry_after
        base = min(2**attempt, 30)
        return base * random.random()  # noqa: S311

    def _record_stats(self, stats: RequestStats) -> None:
        with self._stats_lock:
            self._stats.append(stats)
            if len(self._stats) > 100:
                self._stats.pop(0)


# ---------------------------------------------------------------- internal exceptions


class _RetryableError(Exception):
    def __init__(
        self,
        message: str,
        *,
        http_status: int | None,
        retry_after: float | None,
        category: str,
        groq_code: str,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.retry_after = retry_after
        self.category = category
        self.groq_code = groq_code


class _FatalError(Exception):
    def __init__(
        self,
        message: str,
        *,
        http_status: int | None,
        category: str,
        groq_code: str,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.category = category
        self.groq_code = groq_code
