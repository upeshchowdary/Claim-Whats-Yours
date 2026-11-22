#!/usr/bin/env python3
"""Claim What's Yours - E2E Test Suite Runner.

Executes end-to-end tests across all tiers, aggregates outcomes, formats
a comprehensive per-tier report, and returns exit code 0 on pass, 1 on fail.

Usage:
    python tests/e2e/run_e2e.py
    python tests/e2e/run_e2e.py -v
    python tests/e2e/run_e2e.py --tier 1
    python tests/e2e/run_e2e.py --tier 2
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest


class TierCollectorPlugin:
    """Pytest plugin that intercepts test execution reports and groups by Tier."""

    def __init__(self) -> None:
        self.reports: list[Any] = []
        self.failures: list[Any] = []

    def pytest_runtest_logreport(self, report: Any) -> None:
        if report.when == "call" or (report.when == "setup" and report.failed):
            self.reports.append(report)
            if report.failed:
                self.failures.append(report)


def _classify_tier(nodeid: str) -> str:
    """Map test nodeid to its respective test tier."""
    if "test_tier1_features" in nodeid:
        return "Tier 1: Feature Coverage (F1-F10)"
    if "test_tier2_boundaries" in nodeid:
        return "Tier 2: Boundary Value Analysis (B1-B8 / E1-E24)"
    if "test_tier3_combinations" in nodeid:
        return "Tier 3: Cross-Feature Interactions"
    if "test_tier4_personas" in nodeid:
        return "Tier 4: Real-World Workload Personas"
    return "E2E Other Tests"


def run_e2e(pytest_args: list[str]) -> int:
    """Execute pytest with TierCollectorPlugin and format results."""
    collector = TierCollectorPlugin()
    start_time = time.perf_counter()

    exit_code = pytest.main(pytest_args, plugins=[collector])
    duration = time.perf_counter() - start_time

    # Aggregate by tier
    tier_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"passed": 0, "failed": 0, "skipped": 0})
    for rep in collector.reports:
        tier_name = _classify_tier(rep.nodeid)
        outcome = rep.outcome  # 'passed', 'failed', 'skipped'
        if outcome in tier_stats[tier_name]:
            tier_stats[tier_name][outcome] += 1

    total_passed = sum(s["passed"] for s in tier_stats.values())
    total_failed = sum(s["failed"] for s in tier_stats.values())
    total_skipped = sum(s["skipped"] for s in tier_stats.values())
    total_tests = total_passed + total_failed + total_skipped

    # Output formatted report
    print("\n" + "=" * 80)
    print("CLAIM WHAT'S YOURS — END-TO-END TEST SUITE SUMMARY")
    print("=" * 80)
    print(f"{'Tier / Category':<52} {'Total':>7} {'Pass':>6} {'Fail':>6} {'Skip':>6}")
    print("-" * 80)

    for tier_name in sorted(tier_stats.keys()):
        stats = tier_stats[tier_name]
        tier_total = stats["passed"] + stats["failed"] + stats["skipped"]
        status_flag = "PASS" if stats["failed"] == 0 else "FAIL"
        print(
            f"{tier_name:<52} {tier_total:>7} {stats['passed']:>6} {stats['failed']:>6} {stats['skipped']:>6}  [{status_flag}]"
        )

    print("-" * 80)
    overall_status = "ALL TESTS PASSED" if total_failed == 0 and total_tests > 0 else "TEST SUITE FAILED"
    print(f"{'TOTAL SUMMARY':<52} {total_tests:>7} {total_passed:>6} {total_failed:>6} {total_skipped:>6}  [{overall_status}]")
    print(f"Elapsed Time: {duration:.2f} seconds")
    print("=" * 80)

    if collector.failures:
        print("\nFAILURE DETAILS:")
        for idx, fail in enumerate(collector.failures, 1):
            print(f"  {idx}. {fail.nodeid}")
            if hasattr(fail, "longreprtext") and fail.longreprtext:
                for line in fail.longreprtext.splitlines()[-5:]:
                    print(f"     {line}")
        print()

    return 0 if (exit_code == 0 and total_failed == 0) else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Claim What's Yours E2E Test Runner")
    parser.add_argument("--tier", choices=["1", "2", "3", "4"], help="Execute only a specific tier")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose pytest output")
    parser.add_argument("-k", "--expression", help="Only run tests matching given keyword expression")

    args, unknown = parser.parse_known_args()

    tests_dir = Path(__file__).resolve().parent
    pytest_args = ["-q"]

    if args.verbose:
        pytest_args.append("-v")
    if args.expression:
        pytest_args.extend(["-k", args.expression])

    if args.tier == "1":
        pytest_args.append(str(tests_dir / "test_tier1_features.py"))
    elif args.tier == "2":
        pytest_args.append(str(tests_dir / "test_tier2_boundaries.py"))
    elif args.tier == "3":
        pytest_args.append(str(tests_dir / "test_tier3_combinations.py"))
    elif args.tier == "4":
        pytest_args.append(str(tests_dir / "test_tier4_personas.py"))
    else:
        pytest_args.append(str(tests_dir))

    pytest_args.extend(unknown)
    sys.exit(run_e2e(pytest_args))


if __name__ == "__main__":
    main()
