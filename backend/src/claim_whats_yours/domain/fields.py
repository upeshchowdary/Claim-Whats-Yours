"""Profile field catalogue and answer validation. Pure: returns errors, never raises."""

import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

# parents[0]=domain, [1]=claim_whats_yours, [2]=src, [3]=backend
_DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "profile_fields.json"


@lru_cache(maxsize=1)
def _raw() -> dict[str, Any]:
    with _DATA_PATH.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


@lru_cache(maxsize=1)
def load_registry() -> Mapping[str, Mapping[str, Any]]:
    """Return field id -> field definition, loaded once from profile_fields.json."""
    return MappingProxyType({f["id"]: MappingProxyType(f) for f in _raw()["fields"]})


def field_ids() -> frozenset[str]:
    """Return the set of known profile field ids."""
    return frozenset(load_registry())


def forbidden_field_ids() -> frozenset[str]:
    """Return the set of field names that must never be collected."""
    return frozenset(str(name).lower() for name in _raw()["forbidden_fields"])


def validate_answers(answers: dict[str, Any]) -> list[dict[str, str]]:
    """Return every validation error for the answers. Never raises."""
    errors: list[dict[str, str]] = []
    for key, value in answers.items():
        errors.extend(_validate_one(key, value))
    return errors


def _validate_one(key: str, value: Any) -> list[dict[str, str]]:
    if key.lower() in forbidden_field_ids():
        return [_error(key, "FORBIDDEN_FIELD", "This field must not be collected.")]
    field = load_registry().get(key)
    if field is None:
        return [_error(key, "UNKNOWN_FIELD", "This field is not in the catalogue.")]
    if value is None:
        return []
    if not _matches_type(field["type"], value):
        return [_error(key, "INVALID_TYPE", f"Expected a value of type {field['type']}.")]
    return _check_constraints(key, field, value)


def _check_constraints(key: str, field: Mapping[str, Any], value: Any) -> list[dict[str, str]]:
    if field["type"] in ("int", "number") and _is_out_of_range(field, value):
        return [_error(key, "OUT_OF_RANGE", "Value is outside the allowed range.")]
    allowed = field.get("allowed_values")
    if allowed is not None and value not in allowed:
        return [_error(key, "NOT_ALLOWED_VALUE", "Value is not one of the allowed options.")]
    return []


def _matches_type(field_type: str, value: Any) -> bool:
    if field_type == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if field_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if field_type == "bool":
        return isinstance(value, bool)
    if field_type in ("enum", "string"):
        return isinstance(value, str)
    return False


def _is_out_of_range(field: Mapping[str, Any], value: Any) -> bool:
    bounds: Mapping[str, Any] = field.get("range") or {}
    low = bounds.get("min")
    high = bounds.get("max")
    if low is not None and value < low:
        return True
    return high is not None and value > high


def _error(key: str, code: str, message: str) -> dict[str, str]:
    return {"field": key, "code": code, "message": message}
