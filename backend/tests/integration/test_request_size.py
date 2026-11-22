"""Request-size limit: oversized bodies are rejected with 413 whether or not Content-Length is set.

All payloads are synthetic. The oversized field name is not a profile key on purpose.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

EVALUATE_PATH = "/api/v1/eligibility/evaluate"
JSON_HEADERS = {"Content-Type": "application/json"}
OVERSIZED_NOTE = "a" * 70000


def _oversized_body() -> bytes:
    return json.dumps({"answers": {"note": OVERSIZED_NOTE}}).encode()


def _chunks(payload: bytes, size: int = 8192) -> list[bytes]:
    return [payload[i : i + size] for i in range(0, len(payload), size)]


def _error_code(response: Any) -> Any:
    return response.json().get("error", {}).get("code")


def test_oversized_body_with_content_length_is_rejected(client: TestClient) -> None:
    body = _oversized_body()
    headers = {**JSON_HEADERS, "Content-Length": str(len(body))}

    response = client.post(EVALUATE_PATH, content=body, headers=headers)

    assert response.status_code == 413
    assert _error_code(response) == "PAYLOAD_TOO_LARGE"


def test_oversized_chunked_body_without_content_length_is_rejected(client: TestClient) -> None:
    body = _oversized_body()

    response = client.post(EVALUATE_PATH, content=iter(_chunks(body)), headers=JSON_HEADERS)

    assert response.status_code == 413
    assert _error_code(response) == "PAYLOAD_TOO_LARGE"


def test_small_chunked_body_without_content_length_is_accepted(client: TestClient) -> None:
    body = json.dumps({"answers": {"age_years": 25}}).encode()

    response = client.post(EVALUATE_PATH, content=iter(_chunks(body)), headers=JSON_HEADERS)

    assert response.status_code == 200
    assert "results" in response.json()


def test_small_body_with_content_length_is_accepted(client: TestClient) -> None:
    body = json.dumps({"answers": {"age_years": 25}}).encode()
    headers = {**JSON_HEADERS, "Content-Length": str(len(body))}

    response = client.post(EVALUATE_PATH, content=body, headers=headers)

    assert response.status_code == 200


def test_rejected_response_does_not_echo_payload(client: TestClient) -> None:
    body = _oversized_body()
    headers = {**JSON_HEADERS, "Content-Length": str(len(body))}

    response = client.post(EVALUATE_PATH, content=body, headers=headers)

    assert response.status_code == 413
    assert "a" * 100 not in response.text
