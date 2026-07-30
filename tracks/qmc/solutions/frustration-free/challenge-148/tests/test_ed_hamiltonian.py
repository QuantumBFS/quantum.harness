from __future__ import annotations

import numpy as np
import pytest

import challenge148.ed as ed_module
from challenge148.ed import (
    build_dense_hamiltonian_oracle,
    build_sparse_hamiltonian,
    estimate_ed_resources,
)
from challenge148.lattice import PeriodicGraph, honeycomb_graph, triangular_graph


def manual_pauli_diagonal(graph: PeriodicGraph, state: int, coupling: float) -> float:
    sigma_z = [1 if ((state >> site) & 1) == 0 else -1 for site in range(graph.site_count)]
    return -coupling * sum(sigma_z[left] * sigma_z[right] for left, right in graph.bonds)


def test_sparse_hamiltonian_matches_independent_kronecker_oracle():
    graph = honeycomb_graph(2)
    sparse = build_sparse_hamiltonian(graph, coupling=1.0, field=2.1325)
    dense = build_dense_hamiltonian_oracle(graph, coupling=1.0, field=2.1325)
    np.testing.assert_allclose(sparse.toarray(), dense, atol=0, rtol=0)


def test_hamiltonian_uses_pauli_not_spin_half_normalization():
    graph = honeycomb_graph(2)
    h0 = build_sparse_hamiltonian(graph, coupling=1.0, field=0.0)
    all_up = 0
    assert h0[all_up, all_up] == -len(graph.bonds)


def test_basis_state_bits_use_zero_for_sigma_z_plus_one():
    graph = honeycomb_graph(2)
    h0 = build_sparse_hamiltonian(graph, coupling=1.0, field=0.0)

    for state in (0, 1, 3, 17):
        assert h0[state, state] == manual_pauli_diagonal(graph, state, coupling=1.0)


def test_dense_resource_guard_rejects_unsafe_thermal_dimension():
    estimate = estimate_ed_resources(16)
    assert estimate.dimension == 2**16
    assert estimate.dense_eigenvector_bytes == (2**16) ** 2 * 8
    assert estimate.dense_full_thermal_peak_bytes >= estimate.dense_builder_peak_bytes
    assert estimate.dense_builder_peak_bytes >= estimate.dense_matrix_bytes

    with pytest.raises(MemoryError, match="full thermal ED"):
        build_dense_hamiltonian_oracle(triangular_graph(4), field=4.76811)


def test_sparse_hamiltonian_is_hermitian_with_one_flip_per_site():
    graph = honeycomb_graph(2)
    field = 1.75
    sparse = build_sparse_hamiltonian(graph, coupling=1.0, field=field)
    dense = sparse.toarray()
    np.testing.assert_allclose(dense, dense.conj().T, atol=0, rtol=0)

    coo = sparse.tocoo()
    off_diagonal = coo.row != coo.col
    assert int(np.count_nonzero(off_diagonal)) == graph.site_count * (2**graph.site_count)
    np.testing.assert_allclose(coo.data[off_diagonal], -field, atol=0, rtol=0)


@pytest.mark.parametrize(
    "builder",
    [build_sparse_hamiltonian, build_dense_hamiltonian_oracle],
)
def test_hamiltonian_builders_reject_bool_or_non_finite_numeric_parameters(builder):
    graph = honeycomb_graph(2)

    with pytest.raises(TypeError, match="coupling must be a real number"):
        builder(graph, coupling=True, field=1.0)

    with pytest.raises(TypeError, match="field must be a real number"):
        builder(graph, coupling=1.0, field=False)

    with pytest.raises(ValueError, match="coupling must be finite"):
        builder(graph, coupling=np.inf, field=1.0)

    with pytest.raises(ValueError, match="field must be finite"):
        builder(graph, coupling=1.0, field=np.nan)


@pytest.mark.parametrize("site_count", [0, -1, True])
def test_estimate_ed_resources_rejects_non_positive_or_bool_site_count(site_count):
    expected_error = TypeError if isinstance(site_count, bool) else ValueError
    expected_message = (
        "site_count must be an int" if isinstance(site_count, bool) else "positive"
    )

    with pytest.raises(expected_error, match=expected_message):
        estimate_ed_resources(site_count)


def test_sparse_resource_guard_rejects_valid_huge_graph_before_allocation():
    graph = honeycomb_graph(8)
    estimate = estimate_ed_resources(graph.site_count)
    assert estimate.sparse_diagonal_peak_bytes < estimate.sparse_nonzero_field_peak_bytes
    assert estimate.sparse_peak_bytes == estimate.sparse_nonzero_field_peak_bytes
    assert estimate.sparse_nonzero_field_peak_bytes > 16 * 1024**3

    with pytest.raises(MemoryError, match="sparse Hamiltonian"):
        build_sparse_hamiltonian(graph, coupling=1.0, field=1.0)


def test_sparse_guard_uses_diagonal_only_limit_for_zero_field(monkeypatch):
    graph = honeycomb_graph(2)
    estimate = estimate_ed_resources(graph.site_count)
    limit = estimate.sparse_diagonal_peak_bytes + (
        estimate.sparse_nonzero_field_peak_bytes - estimate.sparse_diagonal_peak_bytes
    ) // 2
    assert estimate.sparse_diagonal_peak_bytes < limit
    assert limit < estimate.sparse_nonzero_field_peak_bytes

    monkeypatch.setattr(ed_module, "_LOCAL_SPARSE_GUARD_BYTES", limit)
    diagonal = build_sparse_hamiltonian(graph, coupling=1.0, field=0.0)
    assert diagonal.shape == (2**graph.site_count, 2**graph.site_count)

    def fail_empty(*args, **kwargs):
        raise AssertionError("sparse arrays allocated before guard")

    monkeypatch.setattr(ed_module.np, "empty", fail_empty)
    with pytest.raises(MemoryError, match="sparse Hamiltonian"):
        build_sparse_hamiltonian(graph, coupling=1.0, field=1.0)


def test_dense_peak_estimate_includes_kronecker_workspace():
    estimate = estimate_ed_resources(honeycomb_graph(2).site_count)
    assert estimate.dense_builder_peak_bytes > estimate.dense_matrix_bytes
    assert estimate.dense_full_thermal_peak_bytes > estimate.dense_eigenvector_bytes


def test_dense_resource_guard_checks_peak_not_only_final_matrix():
    graph = triangular_graph(4)
    estimate = estimate_ed_resources(graph.site_count)
    assert estimate.dense_matrix_bytes > 0
    assert estimate.dense_full_thermal_peak_bytes > 2 * 1024**3

    with pytest.raises(MemoryError, match="full thermal ED"):
        build_dense_hamiltonian_oracle(graph, coupling=1.0, field=4.76811)


@pytest.mark.parametrize(
    "builder",
    [build_sparse_hamiltonian, build_dense_hamiltonian_oracle],
)
def test_hamiltonian_builders_validate_graph_contract(builder):
    bad_graph = PeriodicGraph(
        lattice="honeycomb",
        length=2,
        site_count=8,
        bonds=((0, 0),),
    )

    with pytest.raises(ValueError, match="self-loop"):
        builder(bad_graph, coupling=1.0, field=1.0)
