from __future__ import annotations

import json

import numpy as np
import pytest

from run_rice_mele_chern import (
    RiceMeleChernScanner,
    compute_fhs,
    run_nested_scan,
    verify_gauge_invariance,
)


def test_fhs_rejects_zero_neighbor_overlap():
    states = np.eye(4, dtype=np.complex128).reshape(2, 2, 4)

    with pytest.raises(ValueError, match="overlap"):
        compute_fhs(states, overlap_threshold=1e-12)


def test_fhs_rejects_overlap_equal_to_threshold():
    first = np.array([1.0, 0.0], dtype=np.complex128)
    second = np.array([1e-12, np.sqrt(1.0 - 1e-24)], dtype=np.complex128)
    states = np.array([[first, first], [second, second]])
    threshold = abs(np.vdot(first, second))

    with pytest.raises(ValueError, match="overlap"):
        compute_fhs(states, overlap_threshold=threshold)


def test_fhs_is_invariant_under_independent_grid_point_phases():
    base = np.array([1.0, 0.25j, -0.1], dtype=np.complex128)
    base /= np.linalg.norm(base)
    states = np.broadcast_to(base, (3, 3, base.size)).copy()
    baseline = compute_fhs(states)

    rng = np.random.default_rng(20260728)
    phases = rng.uniform(0.0, 2.0 * np.pi, size=(3, 3))
    phased_states = states * np.exp(1j * phases)[:, :, None]
    transformed = compute_fhs(phased_states)

    assert np.allclose(transformed.flux, baseline.flux, atol=1e-12)
    assert transformed.chern_raw == pytest.approx(baseline.chern_raw, abs=1e-12)


def test_fhs_orientation_on_qi_wu_zhang_lower_band():
    size = 9
    sigma_x = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128)
    sigma_y = np.array([[0.0, -1j], [1j, 0.0]], dtype=np.complex128)
    sigma_z = np.diag([1.0, -1.0]).astype(np.complex128)
    states = np.empty((size, size, 2), dtype=np.complex128)
    for m in range(size):
        k_x = 2.0 * np.pi * m / size
        for n in range(size):
            k_y = 2.0 * np.pi * n / size
            H = (
                np.sin(k_x) * sigma_x
                + np.sin(k_y) * sigma_y
                + (-1.0 + np.cos(k_x) + np.cos(k_y)) * sigma_z
            )
            _, vectors = np.linalg.eigh(H)
            states[m, n] = vectors[:, 0]

    result = compute_fhs(states)

    assert result.chern_raw == pytest.approx(-1.0, abs=1e-12)


def test_model_is_hermitian_and_periodic_with_one_shared_basis():
    scanner = RiceMeleChernScanner(L=4)
    basis_id = id(scanner.basis)
    h0 = scanner.build_hamiltonian(phi=0.0, theta=0.0)
    h_phi = scanner.build_hamiltonian(phi=2.0 * np.pi, theta=0.0)
    h_theta = scanner.build_hamiltonian(phi=0.0, theta=2.0 * np.pi)

    matrix = h0.toarray()
    assert id(scanner.basis) == basis_id
    assert h0.basis is scanner.basis
    assert h_phi.basis is scanner.basis
    assert h_theta.basis is scanner.basis
    assert np.allclose(matrix, matrix.conj().T, atol=1e-12)
    assert np.allclose(matrix, h_phi.toarray(), atol=1e-12)
    assert np.allclose(matrix, h_theta.toarray(), atol=1e-12)


def test_refining_five_to_ten_reuses_twenty_five_vertices():
    scanner = RiceMeleChernScanner(L=4)

    coarse = scanner.scan_grid(5)
    refined = scanner.scan_grid(10)

    assert coarse.new_diagonalizations == 25
    assert refined.new_diagonalizations == 75
    assert scanner.diagonalization_count == 100
    assert np.allclose(coarse.states, refined.states[::2, ::2])
    assert {vertex.basis_fingerprint for vertex in scanner.cache.values()} == {
        scanner.basis_fingerprint
    }


def test_five_by_five_many_body_benchmark_has_chern_minus_two():
    result = RiceMeleChernScanner().scan_grid(5)

    assert result.fhs.chern_raw == pytest.approx(-2.0, abs=1e-10)
    assert result.minimum_gap > 0.0
    assert result.fhs.maximum_absolute_flux < np.pi - 1e-8
    assert verify_gauge_invariance(result, seed=20260728) < 1e-11


def test_nested_refinement_is_stable_and_reuses_all_vertices():
    scanner = RiceMeleChernScanner()
    results = [scanner.scan_grid(size) for size in (5, 10, 20)]

    assert [result.fhs.chern_integer for result in results] == [-2, -2, -2]
    assert results[-1].minimum_gap <= results[0].minimum_gap
    assert scanner.diagonalization_count == 400


def test_write_summary_records_parameters_and_refinement(tmp_path):
    output_path = tmp_path / "summary.json"

    run_nested_scan((5,), output_path=output_path)
    payload = json.loads(output_path.read_text())

    assert payload["parameters"]["U"] == 0.0
    assert payload["grid_results"][0]["chern_integer"] == -2
    assert payload["cache"]["unique_diagonalizations"] == 25
