from __future__ import annotations

import numpy as np
import pytest

from tensor_square.algebra import kron_sum
from tensor_square.fock import (
    basis_states,
    d_gamma,
    many_body_hamiltonian,
    max_abs,
    normal_ordered_q_square,
    particle_number_operator,
)


def edge(m: int, i: int, j: int) -> np.ndarray:
    matrix = np.zeros((m, m))
    matrix[i, j] = matrix[j, i] = 1.0
    return matrix


def test_m3_seed_hamiltonian_is_hermitian_and_number_conserving() -> None:
    m = 3
    a12, a23 = edge(m, 0, 1), edge(m, 1, 2)
    k = -0.6 * (a12 + a23)
    hamiltonian, basis, _ = many_body_hamiltonian(
        m, k, [a12, a23], [1.0, 0.75]
    )
    number = particle_number_operator(basis)
    assert max_abs(hamiltonian - hamiltonian.getH()) < 2e-14
    assert max_abs(hamiltonian @ number - number @ hamiltonian) < 2e-14


@pytest.mark.parametrize("m", [2, 3])
def test_normal_ordering_keeps_the_contraction_correction(m: int) -> None:
    rng = np.random.default_rng(4410 + m)
    raw = rng.normal(size=(m, m))
    channel = (raw + raw.T) / 2.0
    one_body = kron_sum(channel)
    basis = basis_states(m * m)
    q = d_gamma(one_body, basis)
    rewritten = normal_ordered_q_square(one_body, basis)
    assert max_abs(q @ q - rewritten) < 2e-12
