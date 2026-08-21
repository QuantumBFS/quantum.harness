from __future__ import annotations

import numpy as np
from tenpy.algorithms.exact_diag import get_numpy_Hamiltonian

from lrtfim.dmrg_workflow import (
    build_mpo_model,
    default_dmrg_options,
    run_ground_and_first_excited,
)
from lrtfim.mpo import build_nearest_neighbor_tfim_mpo


def _pauli_tfim_dense(length: int, gamma: float) -> np.ndarray:
    identity = np.eye(2)
    x = np.array([[0.0, 1.0], [1.0, 0.0]])
    z = np.diag([1.0, -1.0])
    hamiltonian = np.zeros((2**length, 2**length))

    def product(operators: list[np.ndarray]) -> np.ndarray:
        result = operators[0]
        for operator in operators[1:]:
            result = np.kron(result, operator)
        return result

    for i in range(length):
        field_ops = [identity] * length
        field_ops[i] = x
        hamiltonian -= gamma * product(field_ops)

        interaction_ops = [identity] * length
        interaction_ops[i] = z
        interaction_ops[(i + 1) % length] = z
        hamiltonian -= product(interaction_ops)
    return hamiltonian


def test_periodic_nearest_neighbor_mpo_matches_dense_hamiltonian() -> None:
    length = 4
    gamma = 0.73
    mpo = build_nearest_neighbor_tfim_mpo(length, gamma)
    actual = get_numpy_Hamiltonian(build_mpo_model(mpo), from_mpo=True)
    expected = _pauli_tfim_dense(length, gamma)
    np.testing.assert_allclose(actual, expected, atol=1.0e-13)


def test_excited_state_targeting_matches_ed_on_small_chain() -> None:
    length = 4
    gamma = 1.0
    mpo = build_nearest_neighbor_tfim_mpo(length, gamma)
    model = build_mpo_model(mpo)
    options = default_dmrg_options(chi_max=16)
    options.update({"min_sweeps": 4, "max_sweeps": 12})

    result = run_ground_and_first_excited(model, options)
    exact = np.linalg.eigvalsh(_pauli_tfim_dense(length, gamma))[:2]

    np.testing.assert_allclose(
        [result.ground.energy, result.excited.energy],
        exact,
        atol=1.0e-9,
    )
    assert result.overlap < 1.0e-10
    assert result.ground.variance < 1.0e-10
    assert result.excited.variance < 1.0e-10
    assert result.ground.variance >= 0.0
    assert result.excited.variance >= 0.0
    assert result.gap > 0.0
