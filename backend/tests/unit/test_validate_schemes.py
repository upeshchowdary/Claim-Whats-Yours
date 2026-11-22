"""CLI tests for scripts/validate_schemes.py. Records are synthetic fixtures."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRIPT = BACKEND_DIR / "scripts" / "validate_schemes.py"


def _synthetic_record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": "synthetic-x",
        "slug": "synthetic-x",
        "name": "Synthetic",
        "summary": "Synthetic test fixture",
        "government_level": "central",
        "jurisdictions": {"scope": "all_india", "state_codes": [], "district_codes": []},
        "eligibility_rule": {
            "all": [
                {
                    "criterion_id": "c1",
                    "field": "age_years",
                    "operator": "gte",
                    "value": 18,
                    "mandatory": True,
                    "explanation": "x",
                    "source_refs": ["s1"],
                }
            ]
        },
        "sources": [
            {
                "id": "s1",
                "title": "t",
                "publisher": "p",
                "url": "https://example.gov.in/x",
                "source_type": "guideline",
                "official_status": "official",
                "access_date": "2025-01-01",
            }
        ],
        "application_steps": ["step"],
        "record_status": "draft",
    }
    record.update(overrides)
    return record


def _run(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(directory)],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_bad_record_reports_non_https_and_unresolved_evidence(tmp_path: Path) -> None:
    bad = _synthetic_record(
        application_url="http://example.gov.in/apply",
        sources=[
            {
                "id": "s1",
                "title": "t",
                "publisher": "p",
                "url": "http://example.gov.in/x",
                "source_type": "guideline",
                "official_status": "unofficial",
                "access_date": "2025-01-01",
            }
        ],
        eligibility_rule={
            "all": [
                {
                    "criterion_id": "c1",
                    "field": "age_years",
                    "operator": "gte",
                    "value": 18,
                    "mandatory": True,
                    "explanation": "x",
                    "source_refs": ["missing-source"],
                }
            ]
        },
        jurisdictions={"scope": "all_india", "state_codes": ["IN-AP"], "district_codes": []},
    )
    (tmp_path / "bad.json").write_text(json.dumps(bad), encoding="utf-8")

    result = _run(tmp_path)

    assert result.returncode == 1
    assert "NON_HTTPS_URL" in result.stdout
    assert "UNRESOLVED_EVIDENCE" in result.stdout


def test_utf8_bom_file_is_not_reported_as_unreadable(tmp_path: Path) -> None:
    payload = json.dumps(_synthetic_record()).encode("utf-8")
    (tmp_path / "bom.json").write_bytes(b"\xef\xbb\xbf" + payload)

    result = _run(tmp_path)

    assert result.returncode in (0, 1)
    assert "BOM" not in result.stdout


def test_missing_directory_exits_with_unreadable_code(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"

    result = _run(missing)

    assert result.returncode == 2


def test_duplicate_ids_across_files_are_reported(tmp_path: Path) -> None:
    record = json.dumps(_synthetic_record())
    (tmp_path / "first.json").write_text(record, encoding="utf-8")
    (tmp_path / "second.json").write_text(record, encoding="utf-8")

    result = _run(tmp_path)

    assert "DUPLICATE_ID" in result.stdout
