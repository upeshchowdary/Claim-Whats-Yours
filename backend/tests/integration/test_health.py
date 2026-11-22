"""Integration tests for health endpoints, request IDs and the error envelope."""

from __future__ import annotations

import re
from typing import Any
from unittest.mock import MagicMock

from claim_whats_yours.app import app
from claim_whats_yours.db.session import get_db

HEX_32 = re.compile(r"[0-9a-f]{32}")


def test_live_returns_ok(client: Any) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_200(client: Any) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_ready_returns_500_on_db_failure(client: Any) -> None:
    failing_db = MagicMock()
    failing_db.execute.side_effect = RuntimeError("DB connection lost")

    def override_get_db() -> Any:
        yield failing_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/health/ready")
        assert response.status_code == 500
        assert response.json() == {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Database unreachable",
            }
        }
    finally:
        app.dependency_overrides.pop(get_db, None)


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
