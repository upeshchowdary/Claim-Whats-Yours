"""Import scheme JSON files from a directory as draft records. Never publishes or verifies."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy.orm import sessionmaker  # noqa: E402

from claim_whats_yours.core.config import get_settings  # noqa: E402
from claim_whats_yours.db.session import get_session_factory  # noqa: E402
from claim_whats_yours.services.admin_service import import_draft  # noqa: E402

EXIT_OK = 0
EXIT_UNREADABLE = 2


def load_records(directory: Path) -> tuple[list[Any], list[str]]:
    """Read every *.json file. Returns (records, unreadable-file messages)."""
    records: list[Any] = []
    unreadable: list[str] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            unreadable.append(f"{path.name}: {exc}")
            continue
        records.extend(data if isinstance(data, list) else [data])
    return records, unreadable


def import_record(factory: sessionmaker, record: Any, now: datetime) -> str | None:
    """Import one record in its own session and commit. Returns None, or a skip code."""
    if not isinstance(record, dict):
        return "INVALID_RECORD"
    with factory() as session:
        try:
            import_draft(session, record, now)
            session.commit()
        except ValueError as exc:
            session.rollback()
            return str(exc)
        except (KeyError, TypeError):
            session.rollback()
            return "INVALID_RECORD"
    return None


def _label(record: Any) -> str:
    if isinstance(record, dict) and isinstance(record.get("id"), str) and record["id"]:
        return record["id"]
    return "<unknown>"


def main(argv: list[str]) -> int:
    """Import every record in the given directory as a draft and print a summary."""
    if len(argv) != 2:
        print("usage: python scripts/import_schemes.py <directory>", file=sys.stderr)
        return EXIT_UNREADABLE
    directory = Path(argv[1])
    if not directory.is_dir():
        print(f"error: not a directory: {directory}", file=sys.stderr)
        return EXIT_UNREADABLE
    records, unreadable = load_records(directory)
    if unreadable:
        for message in unreadable:
            print(f"error: unreadable input: {message}", file=sys.stderr)
        return EXIT_UNREADABLE
    factory = get_session_factory(get_settings().database_url)
    now = datetime.now(UTC)
    imported = 0
    skipped = 0
    for record in records:
        code = import_record(factory, record, now)
        if code is None:
            imported += 1
        else:
            skipped += 1
            print(f"{_label(record)}: SKIPPED {code}")
    print(f"Imported {imported} draft(s); skipped {skipped}.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
