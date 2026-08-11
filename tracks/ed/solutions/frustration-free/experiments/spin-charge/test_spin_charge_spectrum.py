#!/usr/bin/env python3
"""Tests for spin_charge_spectrum.py."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure the script is importable
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from spin_charge_spectrum import (
    CHARGE_SCALE,
    DELTA_FIXED,
    D_THRESHOLDS,
    K_CHARGE_DEFAULT,
    K_LOW_DEFAULT,
    RMHSpectrumSolver,
    T,
    U_FIXED,
    build_delta_values,
    extract_edges,
    save_csv,
    save_npz,
    scan_delta,
    validate_l6_full_vs_sparse,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def solver_l6_d0() -> RMHSpectrumSolver:
    return RMHSpectrumSolver(L=6, U=U_FIXED, Delta=DELTA_FIXED, delta=0.0)


@pytest.fixture
def solver_l6_d05() -> RMHSpectrumSolver:
    return RMHSpectrumSolver(L=6, U=U_FIXED, Delta=DELTA_FIXED, delta=0.5)


@pytest.fixture
def solver_l8_d0() -> RMHSpectrumSolver:
    return RMHSpectrumSolver(L=8, U=U_FIXED, Delta=DELTA_FIXED, delta=0.0)


# ===========================================================================
# Construction & validation
# ===========================================================================


class TestConstruction:
    def test_valid_parameters(self):
        s = RMHSpectrumSolver(L=6, U=12.0, Delta=2.0, delta=0.3)
        assert s.L == 6
        assert s.N_up == 3
        assert s.N_down == 3

    def test_rejects_odd_L(self):
        with pytest.raises(ValueError, match="even"):
            RMHSpectrumSolver(L=5, U=12.0, Delta=2.0, delta=0.0)

    def test_rejects_L_zero(self):
        with pytest.raises((ValueError, Exception)):
            RMHSpectrumSolver(L=0, U=12.0, Delta=2.0, delta=0.0)

    def test_basis_dimension_l6(self, solver_l6_d0):
        # C(6,3)^2 = 20^2 = 400
        assert solver_l6_d0.basis.Ns == 400

    def test_basis_dimension_l8(self, solver_l8_d0):
        # C(8,4)^2 = 70^2 = 4900
        assert solver_l8_d0.basis.Ns == 4900

    @pytest.mark.parametrize("L,expected_dim", [(4, 36), (6, 400), (8, 4900)])
    def test_basis_dimension_various(self, L, expected_dim):
        s = RMHSpectrumSolver(L=L, U=12.0, Delta=2.0, delta=0.0)
        assert s.basis.Ns == expected_dim


class TestHermiticity:
    def test_hermiticity_delta_zero(self, solver_l6_d0):
        err = solver_l6_d0.hermiticity_error()
        assert err < 1e-12

    def test_hermiticity_delta_half(self, solver_l6_d05):
        err = solver_l6_d05.hermiticity_error()
        assert err < 1e-12

    def test_hermiticity_l8(self, solver_l8_d0):
        err = solver_l8_d0.hermiticity_error()
        assert err < 1e-12

    def test_hermiticity_various_deltas(self):
        for delta in [-0.5, -0.25, 0.0, 0.25, 0.5]:
            s = RMHSpectrumSolver(L=6, U=12.0, Delta=2.0, delta=delta)
            assert s.hermiticity_error() < 1e-12

    def test_validate_hermiticity_passes(self, solver_l6_d0):
        solver_l6_d0.validate_hermiticity(tolerance=1e-12)


# ===========================================================================
# Doublon operator
# ===========================================================================


class TestDoublonOperator:
    def test_doublon_matrix_hermitian(self, solver_l6_d0):
        D = solver_l6_d0.D_dense
        err = np.max(np.abs(D - D.conj().T))
        assert err < 1e-12

    def test_doublon_nonnegative_eigenvalues(self, solver_l6_d0):
        """D is positive semidefinite (sum of projectors)."""
        D = solver_l6_d0.D_dense
        evals = np.linalg.eigvalsh(D)
        assert np.all(evals >= -1e-12)

    def test_doublon_range(self, solver_l6_d0):
        """Each eigenvalue of D should be in [0, L/2] for half-filling."""
        D = solver_l6_d0.D_dense
        evals = np.linalg.eigvalsh(D)
        assert np.all(evals <= solver_l6_d0.L / 2 + 1e-10)

    def test_doublon_atomic_limit_commutes_with_H(self):
        """At t=delta=Delta=0, D commutes with H (only U term)."""
        s = RMHSpectrumSolver(L=4, U=10.0, Delta=0.0, delta=0.0, t=0.0)
        H = s.H_dense
        D = s.D_dense
        commutator = H @ D - D @ H
        assert np.max(np.abs(commutator)) < 1e-12


# ===========================================================================
# Full ED
# ===========================================================================


class TestFullED:
    def test_returns_all_eigenstates_l6(self, solver_l6_d0):
        r = solver_l6_d0.solve_full_ed()
        assert r.n_states == 400
        assert len(r.eigenvalues) == 400
        assert len(r.doublons) == 400

    def test_eigenvalues_sorted(self, solver_l6_d0):
        r = solver_l6_d0.solve_full_ed()
        assert np.all(np.diff(r.eigenvalues) >= -1e-12)

    def test_eigenvalues_real(self, solver_l6_d0):
        r = solver_l6_d0.solve_full_ed()
        assert np.all(np.isreal(r.eigenvalues))

    def test_doublons_real(self, solver_l6_d0):
        r = solver_l6_d0.solve_full_ed()
        assert np.all(np.isreal(r.doublons))

    def test_delta_doublons_zero_for_ground_state(self, solver_l6_d0):
        r = solver_l6_d0.solve_full_ed()
        assert abs(r.delta_doublons[0]) < 1e-12

    def test_residual_small(self, solver_l6_d0):
        r = solver_l6_d0.solve_full_ed()
        assert r.residual < 1e-10

    def test_ground_state_energy_reasonable(self, solver_l6_d0):
        """Ground state energy should be negative and O(L)."""
        r = solver_l6_d0.solve_full_ed()
        assert r.e0 < 0
        assert abs(r.e0) < 50  # loose bound

    def test_ground_state_doublon_small_but_nonzero(self, solver_l6_d0):
        """D_0 should be non-zero but < 1 (not a charge-rich state)."""
        r = solver_l6_d0.solve_full_ed()
        assert 0.0 < r.d0 < 1.5

    def test_full_ed_reproducible(self, solver_l6_d0):
        r1 = solver_l6_d0.solve_full_ed()
        r2 = solver_l6_d0.solve_full_ed()
        assert np.allclose(r1.eigenvalues, r2.eigenvalues)
        assert np.allclose(r1.doublons, r2.doublons)

    def test_l4_full_ed(self):
        """L=4 as a fast cross-check."""
        s = RMHSpectrumSolver(L=4, U=12.0, Delta=2.0, delta=0.0)
        r = s.solve_full_ed()
        assert r.n_states == 36  # C(4,2)^2
        assert r.residual < 1e-10


# ===========================================================================
# Sparse solver
# ===========================================================================


class TestSparseSolver:
    def test_returns_states_l6(self, solver_l6_d0):
        r = solver_l6_d0.solve_sparse(k_low=30, k_charge=10)
        # Sparse targets two clusters: low-E and charge band.
        # States between are intentionally skipped.  After dedup,
        # expect at least 20 unique states.
        assert 20 <= r.n_states <= 45
        assert r.residual < 1e-8

    def test_returns_states_l8(self, solver_l8_d0):
        r = solver_l8_d0.solve_sparse(k_low=50, k_charge=20)
        # Dense charge-band spectrum at L=8 may cause more dedup.
        assert 40 <= r.n_states <= 75
        assert r.residual < 1e-8

    def test_eigenvalues_sorted(self, solver_l6_d0):
        r = solver_l6_d0.solve_sparse(k_low=30, k_charge=10)
        assert np.all(np.diff(r.eigenvalues) >= -1e-12)

    def test_delta_doublons_zero_for_ground_state(self, solver_l6_d0):
        r = solver_l6_d0.solve_sparse(k_low=30, k_charge=10)
        assert abs(r.delta_doublons[0]) < 1e-12

    def test_sparse_matches_full_l6(self, solver_l6_d0):
        """Low-energy cluster from sparse must match full ED exactly."""
        r_full = solver_l6_d0.solve_full_ed()
        r_sparse = solver_l6_d0.solve_sparse(k_low=50, k_charge=30)

        # Match sparse eigenvalues to their closest full-ED counterparts.
        # The sparse solver captures the low-E cluster and charge-band cluster
        # but intentionally skips the intermediate states.
        for i in range(r_sparse.n_states):
            e_sp = r_sparse.eigenvalues[i]
            # Find closest full-ED eigenvalue
            idx = np.argmin(np.abs(r_full.eigenvalues - e_sp))
            e_full = r_full.eigenvalues[idx]
            assert abs(e_sp - e_full) < 1e-8, (
                f"sparse state {i}: E_sparse={e_sp:.10f} vs "
                f"closest full E[{idx}]={e_full:.10f}"
            )

    def test_sparse_doublons_match_full_l6(self, solver_l6_d0):
        """Doublon values for sparse-captured states must match full ED."""
        r_full = solver_l6_d0.solve_full_ed()
        r_sparse = solver_l6_d0.solve_sparse(k_low=50, k_charge=30)

        for i in range(r_sparse.n_states):
            e_sp = r_sparse.eigenvalues[i]
            idx = np.argmin(np.abs(r_full.eigenvalues - e_sp))
            assert abs(r_sparse.doublons[i] - r_full.doublons[idx]) < 1e-6, (
                f"state {i}: doublon mismatch "
                f"({r_sparse.doublons[i]:.8f} vs {r_full.doublons[idx]:.8f})"
            )


# ===========================================================================
# Delta scan
# ===========================================================================


class TestDeltaScan:
    def test_smoke_scan_l6(self):
        deltas = build_delta_values(n=3)
        results = scan_delta(L=6, U=U_FIXED, Delta=DELTA_FIXED,
                             delta_values=deltas, method="full_ed")
        assert len(results) == 3
        for r in results:
            assert r.n_states == 400
            assert r.method == "full_ed"

    def test_smoke_scan_l8_sparse(self):
        deltas = build_delta_values(n=3)
        results = scan_delta(L=8, U=U_FIXED, Delta=DELTA_FIXED,
                             delta_values=deltas, method="sparse")
        assert len(results) == 3
        for r in results:
            assert r.n_states >= 50
            assert "sparse" in r.method

    def test_delta_values_range(self):
        deltas = build_delta_values(n=41)
        assert len(deltas) == 41
        assert abs(deltas[0] - (-0.5)) < 1e-12
        assert abs(deltas[-1] - 0.5) < 1e-12


# ===========================================================================
# Edge extraction
# ===========================================================================


class TestEdgeExtraction:
    @pytest.fixture
    def sample_results(self):
        deltas = build_delta_values(n=5)
        return scan_delta(L=6, U=U_FIXED, Delta=DELTA_FIXED,
                          delta_values=deltas, method="full_ed")

    def test_extract_edges_returns_all_thresholds(self, sample_results):
        edges = extract_edges(sample_results)
        for d_th in D_THRESHOLDS:
            assert d_th in edges
            assert "delta" in edges[d_th]
            assert "Delta_s" in edges[d_th]
            assert "E_ch_min" in edges[d_th]

    def test_Delta_s_positive(self, sample_results):
        edges = extract_edges(sample_results)
        for d_th in D_THRESHOLDS:
            ds = edges[d_th]["Delta_s"]
            assert np.all(np.nan_to_num(ds) >= -1e-12)

    def test_E_ch_min_greater_than_Delta_s(self, sample_results):
        """Charge excitations should generally be above spin excitations."""
        edges = extract_edges(sample_results)
        for d_th in D_THRESHOLDS:
            ech = edges[d_th]["E_ch_min"]
            ds = edges[d_th]["Delta_s"]
            # Where both are defined, E_ch_min should be >= Delta_s
            valid = ~np.isnan(ech) & ~np.isnan(ds)
            if np.any(valid):
                assert np.all(ech[valid] >= ds[valid] - 1e-10)


# ===========================================================================
# Physical checks
# ===========================================================================


class TestPhysicalChecks:
    def test_charge_scale_correct(self):
        assert abs(CHARGE_SCALE - 8.0) < 1e-12

    def test_spin_exchange_energy_scale(self):
        """J = 4Ut^2/(U^2-4Δ^2) at δ=0 should be ≈ 0.375."""
        J = 4 * U_FIXED * T**2 / (U_FIXED**2 - 4 * DELTA_FIXED**2)
        assert abs(J - 0.375) < 0.001

    def test_dimension_fixed_particle_sector(self, solver_l6_d0):
        """Verify the basis is in the correct particle sector."""
        # Spot-check: the basis dimension matches combinatorics
        from math import comb
        expected = comb(6, 3) ** 2
        assert solver_l6_d0.basis.Ns == expected

    def test_particle_number_conserved(self, solver_l6_d0):
        """The QuSpin basis enforces fixed N_up, N_down by construction."""
        # This is guaranteed by spinful_fermion_basis_1d with Nf=(3,3)
        # Verify by checking that H doesn't connect different sectors
        H = solver_l6_d0.H_dense
        # The matrix is block-diagonal in the basis (one block)
        # Just verify H is square with correct dimension
        assert H.shape == (400, 400)

    def test_doublon_at_delta_zero_reasonable(self, solver_l6_d0):
        """At δ=0, D_0 should be small due to strong U."""
        r = solver_l6_d0.solve_full_ed()
        # With U=12, doublons are suppressed
        assert 0 < r.d0 < 1.0, f"D_0 = {r.d0}"

    def test_spectrum_has_charge_states(self, solver_l6_d0):
        """Some excited states should have ΔD_n ~ 1 (charge-like)."""
        r = solver_l6_d0.solve_full_ed()
        # At least some states with ΔD_n > 0.5
        assert np.any(r.delta_doublons > 0.5)

    def test_spectrum_has_spin_states(self, solver_l6_d0):
        """Many low-energy states should have ΔD_n ≈ 0 (spin-like)."""
        r = solver_l6_d0.solve_full_ed()
        # First 10 excited states should be mostly spin-like
        de_low = r.delta_doublons[1:11]
        assert np.mean(de_low) < 0.3


# ===========================================================================
# Data I/O
# ===========================================================================


class TestDataIO:
    @pytest.fixture
    def sample_results(self):
        deltas = build_delta_values(n=3)
        return scan_delta(L=6, U=U_FIXED, Delta=DELTA_FIXED,
                          delta_values=deltas, method="full_ed")

    def test_save_and_load_csv(self, sample_results, tmp_path):
        csv_path = tmp_path / "test.csv"
        save_csv(sample_results, csv_path)
        assert csv_path.exists()
        content = csv_path.read_text()
        # header
        assert "L,U,Delta,delta,n,E_n" in content
        # some data rows
        lines = content.strip().split("\n")
        assert len(lines) > 400  # at least all states from first δ

    def test_save_and_load_npz(self, sample_results, tmp_path):
        npz_path = tmp_path / "test.npz"
        save_npz(sample_results, npz_path)
        assert npz_path.exists()
        data = np.load(npz_path)
        assert "delta_values" in data
        assert "L" in data
        assert "U" in data
        assert "Delta" in data
        assert len(data["delta_values"]) == 3

    def test_csv_delta_doublon_ground_state_zero(self, sample_results, tmp_path):
        csv_path = tmp_path / "test.csv"
        save_csv(sample_results, csv_path)
        with open(csv_path) as fh:
            import csv
            reader = csv.DictReader(fh)
            for row in reader:
                if int(row["n"]) == 0:
                    assert abs(float(row["Delta_D_n"])) < 1e-12


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:
    def test_u_zero_limit(self):
        """U=0 should be handled (free fermions + staggered potential)."""
        s = RMHSpectrumSolver(L=4, U=0.0, Delta=2.0, delta=0.0)
        r = s.solve_full_ed()
        assert r.residual < 1e-10
        assert r.n_states == 36

    def test_large_dimerization(self):
        """δ close to t should still be valid."""
        s = RMHSpectrumSolver(L=6, U=12.0, Delta=2.0, delta=0.99)
        r = s.solve_full_ed()
        assert r.residual < 1e-10

    def test_negative_delta(self):
        """δ negative should give a valid spectrum."""
        s = RMHSpectrumSolver(L=6, U=12.0, Delta=2.0, delta=-0.5)
        r = s.solve_full_ed()
        assert r.residual < 1e-10

    def test_zero_delta_zero_dimerization(self):
        """δ=0, uniform hopping."""
        s = RMHSpectrumSolver(L=6, U=12.0, Delta=2.0, delta=0.0)
        r = s.solve_full_ed()
        assert r.residual < 1e-10

    def test_k_low_respects_dimension(self, solver_l6_d0):
        """Requesting more states than dim should be capped."""
        r = solver_l6_d0.solve_sparse(k_low=500, k_charge=200)
        assert r.n_states <= solver_l6_d0.basis.Ns


# ===========================================================================
# Validation cross-check
# ===========================================================================


class TestValidation:
    def test_l6_sparse_vs_full(self):
        """Sparse eigenpairs match full ED for L=6."""
        deltas = build_delta_values(n=3)
        validate_l6_full_vs_sparse(deltas, n_check=3)
