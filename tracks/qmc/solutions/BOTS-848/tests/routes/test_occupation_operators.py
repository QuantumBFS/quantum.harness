from __future__ import annotations

import math
from collections import Counter

import numpy as np
import pytest

from benchmark_v0.fock_ed import (
    apply_annihilation,
    apply_creation,
    apply_two_body as oracle_apply_two_body,
    fixed_m_basis,
    full_basis,
    hamiltonian_matrix,
    l_plus_matrix,
    l_squared_matrix,
)
from benchmark_v0.lll_coulomb import (
    antisymmetrized_pair_matrix,
    coulomb_integrals,
)
from scalable_v1.routes.occupation_autoregressive.operators import (
    apply_one_body,
    apply_two_body,
    compose_ladders,
    ladder_neighbors,
    local_energy,
    local_from_neighbors,
    local_l2,
    two_body_neighbors,
)


def _oracle_apply_one_body(
    state: int,
    *,
    a: int,
    c: int,
) -> tuple[int, int] | None:
    annihilated = apply_annihilation(state, c)
    if annihilated is None:
        return None
    intermediate, sign_1 = annihilated
    created = apply_creation(intermediate, a)
    if created is None:
        return None
    target, sign_2 = created
    return target, sign_1 * sign_2


def _amplitude_from_basis(
    basis: tuple[int, ...],
    values: np.ndarray,
):
    amplitudes = dict(zip(basis, values, strict=True))
    return amplitudes.__getitem__


def test_route_local_fermion_actions_match_fock_ed_term_by_term() -> None:
    two_q = 3
    for state in range(1 << (two_q + 1)):
        for a in range(two_q + 1):
            for c in range(two_q + 1):
                assert apply_one_body(state, a=a, c=c, two_q=two_q) == (
                    _oracle_apply_one_body(state, a=a, c=c)
                )
                for b in range(two_q + 1):
                    for d in range(two_q + 1):
                        # Convention: c_a^dagger c_b^dagger c_d c_c.
                        assert apply_two_body(
                            state,
                            a=a,
                            b=b,
                            c=c,
                            d=d,
                            two_q=two_q,
                        ) == oracle_apply_two_body(
                            state,
                            a=a,
                            b=b,
                            c=c,
                            d=d,
                        )


def test_fermion_actions_include_pauli_zero_and_repeated_indices() -> None:
    source = (1 << 0) | (1 << 2)

    assert apply_one_body(source, a=1, c=1, two_q=3) is None
    assert apply_one_body(source, a=2, c=0, two_q=3) is None
    assert apply_two_body(source, a=1, b=1, c=0, d=2, two_q=3) is None
    assert apply_two_body(source, a=1, b=3, c=0, d=0, two_q=3) is None


@pytest.mark.parametrize(
    ("function", "kwargs", "error", "message"),
    [
        (apply_one_body, {"state": True, "a": 0, "c": 0, "two_q": 1}, TypeError, "state must be an integer"),
        (apply_one_body, {"state": -1, "a": 0, "c": 0, "two_q": 1}, ValueError, "non-negative"),
        (apply_one_body, {"state": 4, "a": 0, "c": 0, "two_q": 1}, ValueError, "outside the orbital range"),
        (apply_one_body, {"state": 1, "a": True, "c": 0, "two_q": 1}, TypeError, "a must be an integer"),
        (apply_one_body, {"state": 1, "a": 2, "c": 0, "two_q": 1}, ValueError, "a must be in"),
        (apply_two_body, {"state": 3, "a": 0, "b": 1, "c": 0, "d": -1, "two_q": 1}, ValueError, "d must be in"),
        (apply_two_body, {"state": 3, "a": 0, "b": 1, "c": 0, "d": 1, "two_q": 1.0}, TypeError, "two_q must be an integer"),
    ],
)
def test_fermion_actions_reject_bad_types_and_ranges(
    function,
    kwargs: dict[str, object],
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=message):
        function(**kwargs)


def test_local_energy_matches_tiny_public_coulomb_hamiltonian() -> None:
    two_q = 6
    basis = fixed_m_basis(3, two_q, 0.0)
    integrals = coulomb_integrals(two_q, n_theta=20, n_phi=28)
    pairs, pair_matrix = antisymmetrized_pair_matrix(integrals)
    hamiltonian = hamiltonian_matrix(basis, pairs, pair_matrix)
    values = np.array(
        [1.0 + 0.17j * (index + 1) for index in range(len(basis))],
        dtype=np.complex128,
    )
    amplitude = _amplitude_from_basis(basis, values)
    expected = hamiltonian @ values

    for index, state in enumerate(basis):
        assert local_energy(
            state,
            pairs=pairs,
            pair_matrix=pair_matrix,
            amplitude=amplitude,
            two_q=two_q,
        ) == pytest.approx(expected[index] / values[index], abs=1.0e-12)


def test_local_energy_uses_h_current_target_for_complex_hermitian_input() -> None:
    two_q = 3
    pairs = ((0, 1), (2, 3))
    pair_matrix = np.array(
        [[0.0, 1.0 + 2.0j], [1.0 - 2.0j, 0.0]],
        dtype=np.complex128,
    )
    basis = full_basis(2, two_q)
    hamiltonian = hamiltonian_matrix(basis, pairs, pair_matrix)
    values = np.array(
        [1.0 + (0.1 + 0.2j) * index for index in range(len(basis))],
        dtype=np.complex128,
    )
    amplitude = _amplitude_from_basis(basis, values)

    assert pair_matrix[0, 1] != pair_matrix[1, 0]
    for index, state in enumerate(basis):
        expected = (hamiltonian @ values)[index] / values[index]
        assert local_energy(
            state,
            pairs=pairs,
            pair_matrix=pair_matrix,
            amplitude=amplitude,
            two_q=two_q,
        ) == pytest.approx(expected, abs=1.0e-12)


def test_two_body_neighbors_merge_repeated_targets_before_amplitude_calls() -> None:
    two_q = 4
    pairs = tuple((a, b) for a in range(5) for b in range(a + 1, 5))
    pair_index = {pair: index for index, pair in enumerate(pairs)}
    pair_matrix = np.zeros((len(pairs), len(pairs)), dtype=np.complex128)
    pair_matrix[pair_index[(0, 3)], pair_index[(0, 2)]] = 2.0
    pair_matrix[pair_index[(1, 3)], pair_index[(1, 2)]] = -0.5
    pair_matrix += pair_matrix.conj().T
    source = (1 << 0) | (1 << 1) | (1 << 2)
    target = (1 << 0) | (1 << 1) | (1 << 3)

    neighbors = two_body_neighbors(
        source,
        pairs=pairs,
        pair_matrix=pair_matrix,
        two_q=two_q,
    )
    assert set(neighbors) == {target}

    calls: Counter[int] = Counter()

    def amplitude(state: int) -> complex:
        calls[state] += 1
        return 1.0 + 0.25j * state

    local_energy(
        source,
        pairs=pairs,
        pair_matrix=pair_matrix,
        amplitude=amplitude,
        two_q=two_q,
    )

    assert calls[target] == 1
    assert calls[source] == 1


def test_ladder_neighbors_matches_tiny_l_plus_matrix() -> None:
    two_q = 6
    source_basis = fixed_m_basis(3, two_q, 0.0)
    target_basis = fixed_m_basis(3, two_q, 1.0)
    expected = l_plus_matrix(source_basis, target_basis, two_q=two_q)
    target_index = {state: index for index, state in enumerate(target_basis)}

    for column, state in enumerate(source_basis):
        observed = ladder_neighbors(state, two_q, direction=1)
        observed_column = np.zeros(len(target_basis), dtype=np.complex128)
        for target, coefficient in observed.items():
            observed_column[target_index[target]] += coefficient
        np.testing.assert_allclose(observed_column, expected[:, column], atol=1.0e-14)


def test_ladder_coefficient_and_fermion_sign_are_explicit() -> None:
    two_q = 4
    source = (1 << 0) | (1 << 2)

    assert ladder_neighbors(source, two_q, direction=1) == {
        (1 << 1) | (1 << 2): math.sqrt(4.0),
        (1 << 0) | (1 << 3): math.sqrt(6.0),
    }
    assert ladder_neighbors((1 << 0) | (1 << 1), two_q, direction=1) == {
        (1 << 0) | (1 << 2): math.sqrt(6.0),
    }


def test_compose_ladders_merges_paths_and_keeps_diagonal_return() -> None:
    two_q = 6
    basis = fixed_m_basis(3, two_q, 0.0)
    raised_basis = fixed_m_basis(3, two_q, 1.0)
    l_plus = l_plus_matrix(basis, raised_basis, two_q=two_q)
    expected = l_plus.T @ l_plus
    basis_index = {state: index for index, state in enumerate(basis)}

    saw_merged_target = False
    for column, state in enumerate(basis):
        observed = compose_ladders(state, two_q)
        assert state in observed
        observed_column = np.zeros(len(basis), dtype=np.complex128)
        for target, coefficient in observed.items():
            observed_column[basis_index[target]] += coefficient
        np.testing.assert_allclose(observed_column, expected[:, column], atol=1.0e-14)

        path_targets = []
        for raised in ladder_neighbors(state, two_q, direction=1):
            path_targets.extend(ladder_neighbors(raised, two_q, direction=-1))
        saw_merged_target |= len(path_targets) > len(set(path_targets))

    assert saw_merged_target


@pytest.mark.parametrize("target_m", [0.0, 1.0])
def test_local_l2_matches_tiny_exact_matrix_for_complex_amplitudes(
    target_m: float,
) -> None:
    two_q = 6
    basis = fixed_m_basis(3, two_q, target_m)
    matrix = l_squared_matrix(basis, two_q=two_q, target_m=target_m)
    rng = np.random.default_rng(848 + int(target_m))
    values = rng.normal(size=len(basis)) + 1j * rng.normal(size=len(basis))
    values += 0.7 + 0.3j
    amplitude = _amplitude_from_basis(basis, values)
    expected = matrix @ values

    for index, state in enumerate(basis):
        assert local_l2(
            state,
            two_q=two_q,
            target_m=target_m,
            amplitude=amplitude,
        ) == pytest.approx(expected[index] / values[index], abs=1.0e-12)


@pytest.mark.parametrize("value", [0.0, 1.0e-301, np.nan, np.inf, complex(1, np.inf)])
def test_local_estimator_rejects_bad_sampled_amplitude(value: complex) -> None:
    with pytest.raises(ValueError, match="sampled amplitude"):
        local_from_neighbors(1, {1: 2.0}, lambda _state: value)


def test_operator_estimators_reject_bad_shapes_and_configuration_inputs() -> None:
    pairs = ((0, 1),)
    amplitude = lambda _state: 1.0

    with pytest.raises(ValueError, match="pair_matrix must have shape"):
        two_body_neighbors(3, pairs=pairs, pair_matrix=np.zeros((1, 2)), two_q=1)
    with pytest.raises(ValueError, match="outside the orbital range"):
        ladder_neighbors(1 << 3, 1, direction=1)
    with pytest.raises(ValueError, match="direction must be -1 or 1"):
        ladder_neighbors(1, 1, direction=0)
    with pytest.raises(TypeError, match="target_m must be a finite integer or half-integer"):
        local_l2(1, two_q=1, target_m=True, amplitude=amplitude)
    with pytest.raises(ValueError, match="target_m must be a finite integer or half-integer"):
        local_l2(1, two_q=1, target_m=0.25, amplitude=amplitude)
    with pytest.raises(ValueError, match="target_m must be a finite integer or half-integer"):
        local_l2(1, two_q=1, target_m=np.inf, amplitude=amplitude)
