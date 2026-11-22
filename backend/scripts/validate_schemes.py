"""Validate scheme JSON files against the quality checks in DATA_GOVERNANCE.md section 8."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claim_whats_yours.domain.rules import GROUP_KEYS, validate_rule  # noqa: E402

EXIT_OK = 0
EXIT_ERRORS = 1
EXIT_UNREADABLE = 2
SCOPES_NEEDING_STATE_CODES: frozenset[str] = frozenset({"state", "ut"})


def load_directory(directory: Path) -> tuple[list[tuple[str, Any]], list[str]]:
    """Read every *.json file. Returns ((file name, record) pairs, unreadable messages)."""
    loaded: list[tuple[str, Any]] = []
    unreadable: list[str] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            unreadable.append(f"{path.name}: {exc}")
            continue
        items = data if isinstance(data, list) else [data]
        loaded.extend((path.name, item) for item in items)
    return loaded, unreadable


def check_record(record: Any, today: date) -> list[tuple[str, str]]:
    """Return (code, message) pairs for every quality problem in one record. Never raises."""
    if not isinstance(record, dict):
        return [("INVALID_RECORD", "record must be a JSON object")]
    problems: list[tuple[str, str]] = []
    if not _is_non_empty_str(record.get("id")):
        problems.append(("MISSING_ID", "record id must be a non-empty string"))
    if not _is_non_empty_str(record.get("slug")):
        problems.append(("MISSING_SLUG", "record slug must be a non-empty string"))
    problems.extend(_check_sources(record))
    problems.extend(_check_rule(record))
    problems.extend(_check_scope(record))
    problems.extend(_check_expiry(record, today))
    if record.get("record_status") == "published" and not record.get("application_steps"):
        problems.append(("EMPTY_APPLICATION_STEPS", "published scheme has no application_steps"))
    return problems


def _check_sources(record: dict[str, Any]) -> list[tuple[str, str]]:
    sources = record.get("sources")
    problems: list[tuple[str, str]] = []
    if not isinstance(sources, list) or not sources:
        problems.append(("MISSING_SOURCES", "sources must be a non-empty list"))
    else:
        problems.extend(_check_source_entries(sources))
    application_url = record.get("application_url")
    if application_url and not _is_https(application_url):
        problems.append(("NON_HTTPS_URL", "application_url must be https"))
    return problems


def _check_source_entries(sources: list[Any]) -> list[tuple[str, str]]:
    problems: list[tuple[str, str]] = []
    official = [
        s for s in sources if isinstance(s, dict) and s.get("official_status") == "official"
    ]
    if not official:
        problems.append(("NO_OFFICIAL_SOURCE", "no source has official_status 'official'"))
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            problems.append(("INVALID_SOURCE", f"sources[{index}] must be an object"))
        elif not _is_https(source.get("url")):
            problems.append(("NON_HTTPS_URL", f"sources[{index}].url must be https"))
    return problems


def _check_rule(record: dict[str, Any]) -> list[tuple[str, str]]:
    rule = record.get("eligibility_rule")
    problems = [("UNSUPPORTED_RULE", message) for message in validate_rule(rule)]
    source_ids = _source_ids(record)
    for leaf in _iter_leaves(rule):
        label = leaf.get("criterion_id")
        refs = leaf.get("source_refs")
        ref_list = [r for r in refs if isinstance(r, str)] if isinstance(refs, list) else []
        if not any(ref in source_ids for ref in ref_list):
            problems.append(
                (
                    "MISSING_EVIDENCE",
                    f"criterion {label!r} has no source_refs resolving to a source",
                )
            )
        for ref in ref_list:
            if ref not in source_ids:
                problems.append(
                    ("UNRESOLVED_EVIDENCE", f"criterion {label!r} cites unknown source {ref!r}")
                )
    return problems


def _check_scope(record: dict[str, Any]) -> list[tuple[str, str]]:
    jurisdictions = record.get("jurisdictions")
    if not isinstance(jurisdictions, dict):
        return [("INVALID_SCOPE", "jurisdictions must be an object")]
    scope = jurisdictions.get("scope")
    state_codes = _as_list(jurisdictions.get("state_codes"))
    district_codes = _as_list(jurisdictions.get("district_codes"))
    if scope == "all_india":
        if state_codes or district_codes:
            return [("SCOPE_MISMATCH", "all_india scheme must not list state or district codes")]
        return []
    if scope in SCOPES_NEEDING_STATE_CODES:
        if not state_codes:
            return [("SCOPE_MISSING_CODES", f"{scope} scheme needs at least one state_code")]
        return []
    return [("INVALID_SCOPE", f"unknown scope {scope!r}")]


def _check_expiry(record: dict[str, Any], today: date) -> list[tuple[str, str]]:
    effective_to = record.get("effective_to")
    if effective_to is None:
        return []
    try:
        expiry = date.fromisoformat(str(effective_to))
    except ValueError:
        return [("INVALID_DATE", f"effective_to {effective_to!r} is not YYYY-MM-DD")]
    if expiry < today:
        return [("EXPIRED", f"effective_to {expiry.isoformat()} is before {today.isoformat()}")]
    return []


def _check_duplicates(
    record: dict[str, Any], file_name: str, seen: dict[str, dict[str, str]]
) -> list[tuple[str, str]]:
    problems: list[tuple[str, str]] = []
    for field in ("id", "slug"):
        value = record.get(field)
        if not _is_non_empty_str(value):
            continue
        earlier = seen[field]
        if value in earlier:
            code = f"DUPLICATE_{field.upper()}"
            problems.append((code, f"{field} {value!r} already used in {earlier[value]}"))
        else:
            earlier[value] = file_name
    return problems


def _iter_leaves(node: Any) -> Iterator[dict[str, Any]]:
    if not isinstance(node, dict):
        return
    group_keys = [key for key in node if key in GROUP_KEYS]
    if not group_keys:
        yield node
        return
    value = node[group_keys[0]]
    for child in value if isinstance(value, list) else [value]:
        yield from _iter_leaves(child)


def _source_ids(record: dict[str, Any]) -> set[str]:
    sources = record.get("sources")
    if not isinstance(sources, list):
        return set()
    return {s["id"] for s in sources if isinstance(s, dict) and _is_non_empty_str(s.get("id"))}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _is_https(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("https://")


def _is_non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _record_label(record: Any) -> str:
    if isinstance(record, dict) and _is_non_empty_str(record.get("id")):
        return str(record["id"])
    return "<unknown>"


def main(argv: list[str]) -> int:
    """Validate every record in the given directory and print one line per error."""
    if len(argv) != 2:
        print("usage: python scripts/validate_schemes.py <directory>", file=sys.stderr)
        return EXIT_UNREADABLE
    directory = Path(argv[1])
    if not directory.is_dir():
        print(f"error: not a directory: {directory}", file=sys.stderr)
        return EXIT_UNREADABLE
    loaded, unreadable = load_directory(directory)
    for message in unreadable:
        print(f"error: unreadable input: {message}", file=sys.stderr)
    today = datetime.now(UTC).date()
    seen: dict[str, dict[str, str]] = {"id": {}, "slug": {}}
    error_count = 0
    for file_name, record in loaded:
        problems = check_record(record, today)
        if isinstance(record, dict):
            problems.extend(_check_duplicates(record, file_name, seen))
        for code, message in problems:
            print(f"{file_name}: {_record_label(record)}: {code}: {message}")
            error_count += 1
    file_count = len(list(directory.glob("*.json")))
    print(f"Checked {len(loaded)} record(s) from {file_count} file(s): {error_count} error(s).")
    if unreadable:
        return EXIT_UNREADABLE
    return EXIT_ERRORS if error_count else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
