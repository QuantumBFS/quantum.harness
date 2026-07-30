"""Frozen v1.2 eligibility policy for confirmatory Production B."""

from __future__ import annotations

PRODUCTION_B_ELIGIBLE_SELECTIONS = frozenset(
    {
        "scalar_surrogate_not_rejected",
        "independent_two_burgers_supported",
        "coupled_two_mode_supported",
    }
)

PRODUCTION_B_INELIGIBLE_SELECTIONS = frozenset(
    {
        "memory_or_more_modes_required",
    }
)

KNOWN_VALIDATION_SELECTIONS = (
    PRODUCTION_B_ELIGIBLE_SELECTIONS
    | PRODUCTION_B_INELIGIBLE_SELECTIONS
)


def is_production_b_eligible(status: str) -> bool:
    """Return whether a frozen validation status survives to Production B."""

    return str(status) in PRODUCTION_B_ELIGIBLE_SELECTIONS

