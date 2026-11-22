"""Metadata endpoints: jurisdictions and profile field catalogue."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from claim_whats_yours.domain.fields import forbidden_field_ids

_DATA_DIR = Path(__file__).resolve().parents[5] / "data"
_JURISDICTIONS_PATH = _DATA_DIR / "jurisdictions.json"
_PROFILE_FIELDS_PATH = _DATA_DIR / "profile_fields.json"

router = APIRouter(prefix="/meta", tags=["meta"])


@lru_cache(maxsize=1)
def _load_jurisdictions() -> list[dict[str, Any]]:
    with _JURISDICTIONS_PATH.open(encoding="utf-8") as fh:
        data: list[dict[str, Any]] = json.load(fh)
    return data


@lru_cache(maxsize=1)
def _load_profile_fields() -> list[dict[str, Any]]:
    with _PROFILE_FIELDS_PATH.open(encoding="utf-8") as fh:
        raw: dict[str, Any] = json.load(fh)
    forbidden = forbidden_field_ids()
    fields: list[dict[str, Any]] = []
    for f in raw.get("fields", []):
        fid = str(f.get("id", ""))
        if fid.lower() in forbidden:
            continue
        item = dict(f)
        item["key"] = fid
        item["id"] = fid
        fields.append(item)
    return fields


@router.get("/jurisdictions")
def get_jurisdictions(
    level: str | None = Query(default=None),
    parent_code: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
) -> dict[str, Any]:
    """Return the geography catalogue with optional filtering and pagination."""
    all_items = _load_jurisdictions()
    filtered: list[dict[str, Any]] = []
    normalized_level = level.lower() if level is not None else None

    for item in all_items:
        item_level = str(item.get("level", "")).lower()
        if normalized_level is not None:
            if normalized_level in ("central", "all_india"):
                if item_level not in ("central", "all_india"):
                    continue
            elif item_level != normalized_level:
                continue
        if parent_code is not None and item.get("parent_code") != parent_code:
            continue
        filtered.append(item)

    total = len(filtered)
    offset = (page - 1) * page_size
    paged = filtered[offset : offset + page_size]

    return {
        "items": paged,
        "jurisdictions": paged,
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/profile-fields")
def get_profile_fields(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
) -> dict[str, Any]:
    """Return the allowed profile field catalogue used by eligibility evaluation."""
    all_fields = _load_profile_fields()
    total = len(all_fields)
    offset = (page - 1) * page_size
    paged = all_fields[offset : offset + page_size]

    return {
        "items": paged,
        "fields": paged,
        "page": page,
        "page_size": page_size,
        "total": total,
    }
