"""Integration tests for health endpoints, request IDs and the error envelope."""

from __future__ import annotations

import re
from typing import Any

HEX_32 = re.compile(r"[0-9a-f]{32}")


def test_live_returns_ok(client: Any) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_200(client: Any) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200


def test_supplied_request_id_is_echoed(client: Any) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "caller-req-42"})

    assert response.headers["X-Request-ID"] == "caller-req-42"


def test_generated_request_id_is_32_hex(client: Any) -> None:
    response = client.get("/health/live")

    assert HEX_32.fullmatch(response.headers["X-Request-ID"])


def test_unknown_route_returns_not_found_envelope(client: Any) -> None:
    response = client.get("/api/v1/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert "Traceback" not in response.text
