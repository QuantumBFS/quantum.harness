from src.production_b_policy import (
    PRODUCTION_B_ELIGIBLE_SELECTIONS,
    PRODUCTION_B_INELIGIBLE_SELECTIONS,
    is_production_b_eligible,
)


def test_v12_policy_matrix() -> None:
    assert PRODUCTION_B_ELIGIBLE_SELECTIONS == frozenset(
        {
            "scalar_surrogate_not_rejected",
            "independent_two_burgers_supported",
            "coupled_two_mode_supported",
        }
    )
    assert PRODUCTION_B_INELIGIBLE_SELECTIONS == frozenset(
        {"memory_or_more_modes_required"}
    )
    assert is_production_b_eligible("scalar_surrogate_not_rejected")
    assert is_production_b_eligible("independent_two_burgers_supported")
    assert is_production_b_eligible("coupled_two_mode_supported")
    assert not is_production_b_eligible("memory_or_more_modes_required")
    assert not is_production_b_eligible("unresolved")


def test_policy_sets_do_not_overlap() -> None:
    assert not (
        PRODUCTION_B_ELIGIBLE_SELECTIONS
        & PRODUCTION_B_INELIGIBLE_SELECTIONS
    )
