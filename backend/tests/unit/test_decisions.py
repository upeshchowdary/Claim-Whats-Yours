"""Unit tests for the pure decision mapping in claim_whats_yours.domain.decisions."""

import pytest

from claim_whats_yours.domain.decisions import DISCLAIMER, Decision, decide
from claim_whats_yours.domain.rules import Tri


@pytest.mark.parametrize(
    ("geo", "mandatory", "verification_ok", "self_check", "expected"),
    [
        # LIKELY_ELIGIBLE
        (Tri.PASS, [Tri.PASS, Tri.PASS], True, False, Decision.LIKELY_ELIGIBLE),
        # NOT_LIKELY_ELIGIBLE
        (Tri.PASS, [Tri.PASS, Tri.FAIL], True, False, Decision.NOT_LIKELY_ELIGIBLE),
        # NEEDS_MORE_INFORMATION
        (Tri.PASS, [Tri.PASS, Tri.UNKNOWN], True, False, Decision.NEEDS_MORE_INFORMATION),
        (Tri.UNKNOWN, [Tri.PASS, Tri.PASS], True, False, Decision.NEEDS_MORE_INFORMATION),
        (Tri.PASS, [Tri.PASS, Tri.PASS], True, True, Decision.NEEDS_MORE_INFORMATION),
        # VERIFICATION_REQUIRED
        (Tri.PASS, [Tri.PASS, Tri.PASS], False, False, Decision.VERIFICATION_REQUIRED),
        (Tri.PASS, [Tri.PASS, Tri.FAIL], False, False, Decision.VERIFICATION_REQUIRED),
    ],
)
def test_decide_returns_expected_decision(
    geo: Tri,
    mandatory: list[Tri],
    verification_ok: bool,
    self_check: bool,
    expected: Decision,
) -> None:
    assert decide(geo, mandatory, verification_ok, self_check) == expected


def test_geo_fail_with_verification_ok_raises() -> None:
    # Excluded (geo FAIL) schemes must never reach decide(); the caller filters them.
    with pytest.raises(ValueError):
        decide(Tri.FAIL, [Tri.PASS, Tri.PASS], True, False)


def test_failed_non_mandatory_criterion_does_not_affect_decision() -> None:
    # The caller passes only mandatory results, so a failed optional criterion
    # never appears in mandatory_results and the decision stays LIKELY_ELIGIBLE.
    mandatory_only = [Tri.PASS, Tri.PASS]
    assert decide(Tri.PASS, mandatory_only, True, False) == Decision.LIKELY_ELIGIBLE


def test_disclaimer_says_it_does_not_guarantee_eligibility() -> None:
    assert "does not guarantee" in DISCLAIMER
