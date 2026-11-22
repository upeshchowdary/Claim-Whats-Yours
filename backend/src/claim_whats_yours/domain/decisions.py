"""Maps tri-state criterion results to a user-facing eligibility decision. Pure."""

from enum import StrEnum

from claim_whats_yours.domain.rules import Tri

DISCLAIMER = (
    "This is an information aid based on the rules we hold. It is not a decision by the "
    "government and does not guarantee eligibility or benefit approval."
)


class Decision(StrEnum):
    LIKELY_ELIGIBLE = "LIKELY_ELIGIBLE"
    NEEDS_MORE_INFORMATION = "NEEDS_MORE_INFORMATION"
    NOT_LIKELY_ELIGIBLE = "NOT_LIKELY_ELIGIBLE"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"


def decide(
    geo: Tri,
    mandatory_results: list[Tri],
    verification_ok: bool,
    has_unresolved_mandatory_self_check: bool,
) -> Decision:
    """Return the decision for a scheme. Raises ValueError if geo is FAIL (excluded scheme).

    Checked in order: verification, geo FAIL (raises), geo UNKNOWN, mandatory FAIL,
    mandatory UNKNOWN or unresolved self-check, then LIKELY_ELIGIBLE.
    """
    if not verification_ok:
        return Decision.VERIFICATION_REQUIRED
    if geo == Tri.FAIL:
        raise ValueError("excluded schemes (geo FAIL) must not reach decide()")
    if geo == Tri.UNKNOWN:
        return Decision.NEEDS_MORE_INFORMATION
    if Tri.FAIL in mandatory_results:
        return Decision.NOT_LIKELY_ELIGIBLE
    if Tri.UNKNOWN in mandatory_results:
        return Decision.NEEDS_MORE_INFORMATION
    if has_unresolved_mandatory_self_check:
        return Decision.NEEDS_MORE_INFORMATION
    return Decision.LIKELY_ELIGIBLE
