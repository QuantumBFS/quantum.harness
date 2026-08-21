"""Binary-symplectic and transported-geometry tests for X-cube v11."""

from __future__ import annotations

import numpy as np

from lgeth.xcube_stabilizer import (
    coefficient_reweighting_control,
    gf2_rank,
    structured_transport_control,
    symplectic_commutator,
    verify_dense_transport_toy,
    xcube_stabilizer_table,
)


def test_periodic_xcube_rank_and_degeneracy_formula() -> None:
    for length in (2, 3, 4, 5):
        table = xcube_stabilizer_table(length)
        expected_log2 = 6 * length - 3
        expected_rank = table.n_qubits - expected_log2
        assert table.rows.shape == (4 * length**3, 2 * table.n_qubits)
        assert gf2_rank(table.rows) == expected_rank
        assert table.stabilizer_rank == expected_rank
        assert table.logical_qubits == expected_log2
        assert table.ground_dimension == 2**expected_log2


def test_all_xcube_stabilizers_commute() -> None:
    for length in (2, 3, 4):
        table = xcube_stabilizer_table(length)
        commutator = symplectic_commutator(table.rows, table.rows)
        assert commutator.shape == (4 * length**3, 4 * length**3)
        assert np.count_nonzero(commutator) == 0


def test_positive_coefficient_reweighting_has_exactly_zero_geometry() -> None:
    result = coefficient_reweighting_control(4)
    assert result["projector_derivative_norm"] == 0.0
    assert result["quantum_metric"] == 0.0
    assert result["berry_curvature"] == 0.0
    assert result["ground_dimension"] == 2 ** (6 * 4 - 3)
    assert all(result["checks"].values())


def test_local_transport_is_isospectral_and_scalar_not_random() -> None:
    for length in (2, 3, 4, 5):
        result = structured_transport_control(length)
        assert result.generator_supports == (1, 4)
        assert result.generators_anticommute is True
        assert result.product_is_stabilizer is True
        assert result.exactly_isospectral is True
        assert result.curvature_eigenvalue == -0.5
        assert result.curvature_multiplicity == 2 ** (6 * length - 3)
        assert result.curvature_distinct_eigenvalues == 1
        assert result.connected_curvature_variance == 0.0
        assert all(result.checks.values())


def test_dense_toy_reproduces_projector_curvature_identity() -> None:
    audit = verify_dense_transport_toy()
    assert audit["projector_rank"] == 2
    assert audit["curvature_error"] < 2e-14
    assert audit["spectrum_error"] < 2e-14
    assert all(audit["checks"].values())
