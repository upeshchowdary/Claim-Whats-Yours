"""Jurisdiction lookup and geographic applicability for schemes. Pure and deterministic."""

import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from claim_whats_yours.domain.rules import Tri

# parents[0]=domain, [1]=claim_whats_yours, [2]=src, [3]=backend
_DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "jurisdictions.json"
_VALID_LEVELS: frozenset[str] = frozenset({"all_india", "state", "ut"})
_STATE_LEVELS: frozenset[str] = frozenset({"state", "ut"})
_STATE_SCOPES: frozenset[str] = frozenset({"state", "ut"})


@lru_cache(maxsize=1)
def _jurisdiction_records() -> tuple[dict, ...]:
    """Load and cache all jurisdiction records from the data file."""
    with _DATA_PATH.open(encoding="utf-8") as fh:
        records: list[dict[str, str]] = json.load(fh)
    return tuple(records)


@lru_cache(maxsize=1)
def _levels_by_code() -> Mapping[str, str]:
    return MappingProxyType({r["code"]: r["level"] for r in _jurisdiction_records()})


@lru_cache(maxsize=1)
def _parent_by_code() -> Mapping[str, str | None]:
    """Map each jurisdiction code to its parent_code (or None for all-India)."""
    return MappingProxyType({r["code"]: r.get("parent_code") for r in _jurisdiction_records()})


@lru_cache(maxsize=1)
def _district_parent_map() -> Mapping[str, str]:
    """Map each district code to its parent state/UT code."""
    return MappingProxyType(
        {
            r["code"]: r["parent_code"]
            for r in _jurisdiction_records()
            if r["level"] == "district" and r.get("parent_code")
        }
    )


@lru_cache(maxsize=1)
def known_state_codes() -> frozenset[str]:
    """Return codes for states and union territories (excludes the all-India code)."""
    return frozenset(code for code, level in _levels_by_code().items() if level in _STATE_LEVELS)


@lru_cache(maxsize=1)
def known_district_codes() -> frozenset[str]:
    """Return all known district codes."""
    return frozenset(code for code, level in _levels_by_code().items() if level == "district")


def is_valid_jurisdiction_code(code: str) -> bool:
    """Return True for the all-India code or any known state, UT, or district code."""
    return _levels_by_code().get(code) in (_VALID_LEVELS | frozenset({"district"}))


def is_valid_district_code(code: str) -> bool:
    """Return True only for known district codes."""
    return _levels_by_code().get(code) == "district"


def district_parent_state(district_code: str) -> str | None:
    """Return the parent state/UT code for a district, or None if not found."""
    return _district_parent_map().get(district_code)


def validate_state_district_pair(state_code: str, district_code: str) -> bool:
    """Return True only when the district belongs to the given state/UT.

    Both codes must be known; an unknown code returns False.
    """
    return _district_parent_map().get(district_code) == state_code


def geographic_status(
    scheme_scope: str,
    scheme_state_codes: list[str],
    scheme_district_codes: list[str],
    profile_state_code: str | None,
    profile_district_code: str | None,
) -> Tri:
    """Return PASS, FAIL or UNKNOWN for a scheme's geographic scope.

    For district-scope schemes the provided district codes must be registered
    district codes in the jurisdiction catalogue. A district code from a different
    parent state than the profile's state_code returns FAIL.

    Raises ValueError on an unsupported scope.
    """
    if scheme_scope == "all_india":
        return Tri.PASS
    if scheme_scope in _STATE_SCOPES:
        return _state_status(scheme_state_codes, profile_state_code)
    if scheme_scope == "district":
        return _district_status(
            scheme_district_codes,
            profile_state_code,
            profile_district_code,
        )
    raise ValueError(f"unsupported scheme scope: {scheme_scope!r}")


def _state_status(scheme_state_codes: list[str], profile_state_code: str | None) -> Tri:
    if profile_state_code is None:
        return Tri.UNKNOWN
    return Tri.PASS if profile_state_code in scheme_state_codes else Tri.FAIL


def _district_status(
    scheme_district_codes: list[str],
    profile_state_code: str | None,
    profile_district_code: str | None,
) -> Tri:
    """Evaluate geographic match for district-scoped schemes.

    Rules:
    - No district provided → UNKNOWN (we don't know yet).
    - District provided but not in the catalogue → FAIL (invalid code).
    - District provided and state provided but they disagree → FAIL.
    - District provided, no state provided, district is in catalogue → UNKNOWN
      (we know the district but can't confirm state without profile_state_code).
    - District in scheme's list, state consistent → PASS.
    - District not in scheme's list → FAIL.
    """
    if profile_district_code is None:
        return Tri.UNKNOWN

    # Reject district codes not in the registered catalogue (positive lookup)
    if not is_valid_district_code(profile_district_code):
        return Tri.FAIL

    # Cross-validate state+district consistency when state is available
    parent_state = district_parent_state(profile_district_code)
    if profile_state_code is not None and parent_state != profile_state_code:
        return Tri.FAIL

    # If state is missing but district is known, we can't fully confirm geography
    if profile_state_code is None:
        return Tri.UNKNOWN

    return Tri.PASS if profile_district_code in scheme_district_codes else Tri.FAIL


def applicable(status: Tri) -> bool:
    """Return True when the scheme should be shown (PASS or UNKNOWN). FAIL means excluded."""
    return status in (Tri.PASS, Tri.UNKNOWN)
