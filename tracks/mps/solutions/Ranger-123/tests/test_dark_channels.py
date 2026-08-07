import numpy as np
from numpy.testing import assert_allclose

from floquet_if_manybody.dark_channels import (
    dark_candidates,
    floquet_matrix_elements,
    harmonic_sum_rule,
    period_variance,
)
from floquet_if_manybody.floquet import solve_floquet


def test_static_system_has_only_zero_harmonic_matrix_elements():
    hamiltonian = np.diag([-0.2, 0.3]).astype(complex)
    operator = np.array([[0, 1], [1, 0]], dtype=complex)
    solution = solve_floquet(lambda _time: hamiltonian, period=1.0, steps=64)
    records = floquet_matrix_elements(solution, operator, harmonic_cutoff=2, threshold=1e-14)
    bright = [record for record in records if record.weight > 1e-12]
    assert {record.harmonic for record in bright} == {0}
    assert_allclose(sorted(record.weight for record in bright), [1, 1], atol=1e-12)
    assert harmonic_sum_rule(solution, operator, 2) < 1e-12


def test_dark_candidates_and_variance():
    hamiltonian = np.diag([-0.2, 0.3]).astype(complex)
    operator = np.diag([1, -1]).astype(complex)
    solution = solve_floquet(lambda _time: hamiltonian, period=1.0, steps=32)
    records = floquet_matrix_elements(solution, operator, 1)
    assert len(dark_candidates(records, 1e-8)) > 0
    densities = np.repeat(np.eye(2, dtype=complex)[None, :, :] / 2, 8, axis=0)
    assert_allclose(period_variance(densities, operator), 1)
