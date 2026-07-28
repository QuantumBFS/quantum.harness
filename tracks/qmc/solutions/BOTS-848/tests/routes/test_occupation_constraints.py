from __future__ import annotations

import pytest

from benchmark_v0.fock_ed import fixed_m_basis
from scalable_v1.routes.occupation_autoregressive.constraints import (
    FeasibilityTable,
    occupation_m2,
)


def test_dp_support_equals_tiny_exact_fixed_m_basis() -> None:
    table = FeasibilityTable.build(n_electrons=3, two_q=6, target_m2=0)

    assert set(table.enumerate_support()) == set(fixed_m_basis(3, 6, 0.0))


def test_masked_sampler_never_leaves_n_m_sector() -> None:
    table = FeasibilityTable.build(n_electrons=6, two_q=15, target_m2=0)

    draws = table.sample_uniform(256, seed=848)

    assert draws.tolist() == table.sample_uniform(256, seed=848).tolist()
    assert all(state.bit_count() == 6 for state in draws)
    assert all(occupation_m2(state, 15) == 0 for state in draws)


def test_uniform_sampler_weights_branches_by_completion_counts() -> None:
    table = FeasibilityTable.build(n_electrons=2, two_q=5, target_m2=0)
    draws = table.sample_uniform(6000, seed=848)

    occupied_first_orbital = sum(bool(state & 1) for state in draws)
    observed_probability = occupied_first_orbital / len(draws)

    # The support is {(0, 5), (1, 4), (2, 3)}.  At orbital zero the
    # occupied branch has one completion and the empty branch has two.
    assert observed_probability == pytest.approx(1.0 / 3.0, abs=0.03)
    assert abs(observed_probability - 0.5) > 0.10


def test_allowed_matches_each_nonzero_completion_count() -> None:
    table = FeasibilityTable.build(n_electrons=2, two_q=5, target_m2=0)

    for (orbital, remaining, target_m2), total in table.counts.items():
        if orbital > table.two_q:
            continue
        m2 = -table.two_q + 2 * orbital
        zero_count = table.counts.get((orbital + 1, remaining, target_m2), 0)
        one_count = table.counts.get(
            (orbital + 1, remaining - 1, target_m2 - m2),
            0,
        )

        assert table.allowed(orbital, remaining, target_m2) == (
            zero_count > 0,
            one_count > 0,
        )
        assert total == zero_count + one_count

    assert table.counts[(0, 2, 0)] == len(fixed_m_basis(2, 5, 0.0)) == 3


def test_enumerate_support_rejects_physical_particle_count() -> None:
    table = FeasibilityTable.build(n_electrons=5, two_q=12, target_m2=0)

    with pytest.raises(ValueError, match="at most 4 electrons"):
        table.enumerate_support()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n_electrons": True, "two_q": 6, "target_m2": 0},
        {"n_electrons": 3, "two_q": False, "target_m2": 0},
        {"n_electrons": 3, "two_q": 6, "target_m2": True},
        {"n_electrons": 3.0, "two_q": 6, "target_m2": 0},
    ],
)
def test_build_rejects_non_integer_and_bool_parameters(kwargs: dict[str, object]) -> None:
    with pytest.raises(TypeError, match="must be an integer"):
        FeasibilityTable.build(**kwargs)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"n_electrons": -1, "two_q": 6, "target_m2": 0}, "non-negative"),
        ({"n_electrons": 1, "two_q": -1, "target_m2": 0}, "non-negative"),
        ({"n_electrons": 4, "two_q": 2, "target_m2": 0}, "orbital count"),
        ({"n_electrons": 2, "two_q": 5, "target_m2": 11}, "outside"),
    ],
)
def test_build_rejects_negative_and_out_of_range_parameters(
    kwargs: dict[str, int],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        FeasibilityTable.build(**kwargs)


def test_build_rejects_empty_fixed_n_fixed_m_sector() -> None:
    with pytest.raises(ValueError, match="empty fixed-N fixed-M sector"):
        FeasibilityTable.build(n_electrons=1, two_q=2, target_m2=1)


def test_public_helpers_reject_bad_ranges_and_bool_parameters() -> None:
    table = FeasibilityTable.build(n_electrons=2, two_q=5, target_m2=0)

    with pytest.raises(TypeError, match="must be an integer"):
        occupation_m2(True, 5)
    with pytest.raises(ValueError, match="outside the orbital range"):
        occupation_m2(1 << 6, 5)
    with pytest.raises(ValueError, match="non-negative"):
        table.sample_uniform(-1, seed=848)
    with pytest.raises(TypeError, match="must be an integer"):
        table.sample_uniform(1, seed=True)
    with pytest.raises(ValueError, match="orbital must be in"):
        table.allowed(-1, remaining=2, target_m2=0)
