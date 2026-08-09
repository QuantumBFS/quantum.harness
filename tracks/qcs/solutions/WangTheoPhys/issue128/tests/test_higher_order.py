import mpmath as mp
import pytest

from trottercert.algebra import PauliString, PauliSum
from trottercert.higher_order import (
    fourth_order_suzuki_stages,
    higher_order_triangle_weights,
    weak_compositions,
    fourth_order_local_pauli_l1_density,
    fourth_order_triple_jump_stages,
    higher_order_combined_local_l1_density,
    higher_order_combined_local_l1_density_symplectic,
    _pairwise_anticommuting_float_bound,
)


def test_weak_compositions() -> None:
    values = tuple(weak_compositions(3, 2))
    assert values == ((0, 3), (1, 2), (2, 1), (3, 0))


def test_fourth_order_stage_consistency_and_palindrome() -> None:
    stages = fourth_order_suzuki_stages(4)
    assert len(stages) == 31
    assert [stage.fragment_index for stage in stages] == [
        stage.fragment_index for stage in reversed(stages)
    ]
    coefficients = [mp.mpf("0") for _ in range(4)]
    for stage in stages:
        coefficients[stage.fragment_index] += stage.coefficient
    assert all(mp.almosteq(value, 1) for value in coefficients)
    triple = fourth_order_triple_jump_stages(4)
    assert len(triple) == 19
    assert [stage.fragment_index for stage in triple] == [
        stage.fragment_index for stage in reversed(triple)
    ]


def test_higher_order_weights_are_positive_and_depth_five() -> None:
    weights = higher_order_triangle_weights(fourth_order_suzuki_stages(2), 4)
    assert weights
    assert all(len(key) == 5 for key in weights)
    assert all(value > 0 for value in weights.values())


@pytest.mark.slow
def test_local_fourth_order_density_is_finite_and_positive() -> None:
    density, _ = fourth_order_local_pauli_l1_density()
    assert density > 0
    assert mp.isfinite(density)


@pytest.mark.slow
def test_combined_bj_bound_is_no_worse_than_expanded_bound() -> None:
    stages = fourth_order_suzuki_stages(4)
    combined = higher_order_combined_local_l1_density(stages, center=20)
    assert combined > 0


@pytest.mark.slow
def test_symplectic_combined_bound_matches_fraction_discovery() -> None:
    stages = fourth_order_suzuki_stages(4)
    fraction_value = higher_order_combined_local_l1_density(stages, center=2)
    symplectic_value = higher_order_combined_local_l1_density_symplectic(
        stages,
        center=2,
    )
    assert float(fraction_value) == pytest.approx(symplectic_value, rel=1e-12)


def test_pairwise_anticommuting_float_bound() -> None:
    # X and Z anticommute, while I is left as a singleton.
    paulis = ((1, 0), (0, 1), (0, 0))
    coefficients = mp.matrix([3.0, 4.0, 2.0])
    import numpy as np

    value = _pairwise_anticommuting_float_bound(
        paulis,
        np.asarray(coefficients, dtype=float).reshape(-1),
    )
    assert value == pytest.approx(7.0)
