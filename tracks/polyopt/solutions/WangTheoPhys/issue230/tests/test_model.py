import numpy as np
import pytest

from xxzcert.model import (
    finite_xxz,
    finite_xxz_sparse,
    local_xxz,
    partial_trace_edge,
    reduced_density,
)


def test_local_xxz_spectrum_at_delta_one():
    assert np.allclose(
        np.linalg.eigvalsh(local_xxz(1.0)), [-0.75, 0.25, 0.25, 0.25]
    )


def test_two_site_periodic_hamiltonian_counts_bond_once():
    assert np.allclose(finite_xxz(1.0, 2, True), local_xxz(1.0))


def test_three_site_open_contains_two_bonds():
    assert np.isclose(np.trace(finite_xxz(0.7, 3, False)), 0.0)
    assert finite_xxz(0.7, 3, False).shape == (8, 8)
    assert np.allclose(
        finite_xxz_sparse(0.7, 3, False).toarray(),
        finite_xxz(0.7, 3, False),
    )


def test_partial_trace_bell_state():
    bell = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)
    rho = np.outer(bell, bell.conj())
    assert np.allclose(partial_trace_edge(rho, "left"), np.eye(2) / 2)
    assert np.allclose(partial_trace_edge(rho, "right"), np.eye(2) / 2)


def test_reduced_density_preserves_requested_order():
    state = np.zeros(8, complex)
    state[4] = 1  # |100>
    assert np.allclose(reduced_density(state, (2, 0)), np.diag([0, 1, 0, 0]))


def test_invalid_site_count_rejected():
    with pytest.raises(ValueError):
        finite_xxz(1.0, 1)
