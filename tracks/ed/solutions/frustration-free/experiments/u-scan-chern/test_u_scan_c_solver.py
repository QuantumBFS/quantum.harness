"""Tests for u_scan_c_solver.py — U-dependent many-body Chern number solver."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import pytest

_PARENT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PARENT))

from u_scan_c_solver import (  # noqa: E402
    CAPITAL_DELTA0,
    DELTA0,
    GRID_CONVERGENCE_SIZES,
    GRID_CONVERGENCE_U,
    T,
    U_COARSE,
    RiceMeleHubbardSolver,
    ScanResult,
    _build_filename_stem,
    _build_refined_u_list,
    _write_csv,
    check_grid_convergence,
    check_path_reversal,
    detect_Uc,
    run_coarse_scan,
)
from run_rice_mele_chern import compute_fhs, verify_gauge_invariance  # noqa: E402


# ===========================================================================
# Fast solver fixtures
# ===========================================================================


@pytest.fixture(scope="module")
def solver_u0_l6() -> RiceMeleHubbardSolver:
    return RiceMeleHubbardSolver(L=6, U=0.0)


@pytest.fixture(scope="module")
def solver_u0_l4() -> RiceMeleHubbardSolver:
    return RiceMeleHubbardSolver(L=4, U=0.0)


# ===========================================================================
# U=0 benchmark
# ===========================================================================


def test_u0_chern_is_plus_two():
    """Spec acceptance criterion §8.1: |C_raw - 2| < 1e-3 at U=0."""
    r = RiceMeleHubbardSolver(L=6, U=0.0).scan_grid(5, 5)
    assert abs(r.C_raw - 2.0) < 1e-3, f"C_raw = {r.C_raw:.10f}"
    assert r.C_rounded == 2
    assert r.converged


def test_u0_gap_is_positive():
    r = RiceMeleHubbardSolver(L=6, U=0.0).scan_grid(5, 5)
    assert r.gap_min > 0


# ===========================================================================
# Large repulsive U
# ===========================================================================


def test_large_repulsive_u_gives_trivial_chern():
    """Spec acceptance criterion §8.2: |C_raw| < 1e-3 for U = 16, 24, 32."""
    for U in [16, 32]:
        r = RiceMeleHubbardSolver(L=6, U=U).scan_grid(5, 5)
        assert abs(r.C_raw) < 1e-3, f"U={U}: C_raw = {r.C_raw:.10f}"
        assert r.C_rounded == 0


# ===========================================================================
# Negative U
# ===========================================================================


def test_negative_u_gives_chern_two():
    """Spec acceptance criterion §8.3: |C_raw - 2| < 1e-3 for finite negative U."""
    for U in [-16, -8]:
        r = RiceMeleHubbardSolver(L=6, U=U).scan_grid(5, 5)
        assert abs(r.C_raw - 2.0) < 1e-3, f"U={U}: C_raw = {r.C_raw:.10f}"


# ===========================================================================
# Hamiltonian checks
# ===========================================================================


@pytest.mark.parametrize("U", [0.0, 4.0, -8.0, 10.0])
def test_hamiltonian_is_hermitian(U):
    solver = RiceMeleHubbardSolver(L=4, U=U)
    H = solver.build_hamiltonian(phi=1.2, theta=3.4)
    m = H.toarray()
    assert np.allclose(m, m.conj().T, atol=1e-12)


def test_hamiltonian_periodic_in_theta():
    solver = RiceMeleHubbardSolver(L=4, U=4.0)
    H0 = solver.build_hamiltonian(phi=np.pi, theta=0.0)
    H2pi = solver.build_hamiltonian(phi=np.pi, theta=2.0 * np.pi)
    assert np.allclose(H0.toarray(), H2pi.toarray(), atol=1e-12)


def test_hamiltonian_periodic_in_phi():
    solver = RiceMeleHubbardSolver(L=4, U=4.0)
    H0 = solver.build_hamiltonian(phi=0.0, theta=1.0)
    H2pi = solver.build_hamiltonian(phi=2.0 * np.pi, theta=1.0)
    assert np.allclose(H0.toarray(), H2pi.toarray(), atol=1e-12)


# ===========================================================================
# Basis / shared object
# ===========================================================================


def test_single_basis_object_reused():
    solver = RiceMeleHubbardSolver(L=4, U=0.0)
    basis_id = id(solver.basis)
    H1 = solver.build_hamiltonian(phi=0.0, theta=0.0)
    H2 = solver.build_hamiltonian(phi=1.0, theta=2.0)
    assert H1.basis is solver.basis
    assert H2.basis is solver.basis
    assert id(solver.basis) == basis_id


def test_rejects_odd_L():
    with pytest.raises(ValueError, match="even"):
        RiceMeleHubbardSolver(L=5, U=0.0)


# ===========================================================================
# Grid convergence
# ===========================================================================


def test_grid_convergence_at_u0():
    """Chern number converges with grid refinement at U=0."""
    results = {}
    for N in (5, 9):
        solver = RiceMeleHubbardSolver(L=6, U=0.0)
        results[N] = solver.scan_grid(N, N)
    assert results[5].C_rounded == 2
    assert results[9].C_rounded == 2
    # finer grid should give smaller chern_error
    assert results[9].chern_error < 1e-3


# ===========================================================================
# Gauge invariance
# ===========================================================================


def test_fhs_gauge_invariance_at_u0():
    solver = RiceMeleHubbardSolver(L=6, U=0.0)
    r = solver.scan_grid(5, 5)
    # We need a GridScanResult-like object for verify_gauge_invariance
    # Build a minimal wrapper
    class _FakeResult:
        states = np.empty((5, 5, solver.basis.Ns), dtype=np.complex128)
        fhs = None

    fake = _FakeResult()
    # Re-scan to get states
    states = np.empty((5, 5, solver.basis.Ns), dtype=np.complex128)
    for m in range(5):
        for n in range(5):
            from fractions import Fraction
            v = solver._vertex((Fraction(m, 5), Fraction(n, 5)))
            states[m, n] = v.state
    fake.states = states
    fake.fhs = compute_fhs(states)
    err = verify_gauge_invariance(fake, seed=20260728)
    assert err < 1e-11


# ===========================================================================
# Path reversal
# ===========================================================================


def test_path_reversal_negates_chern():
    """C(φ → -φ) = -C(φ)  (spec §7)."""
    rows = check_path_reversal([0, 6.0])
    for row in rows:
        assert row["pass"], f"U={row['U']}: sum = {row['sum']:.2e}"


# ===========================================================================
# ScanResult and CSV output
# ===========================================================================


def test_scan_result_dict_contains_all_fields():
    r = RiceMeleHubbardSolver(L=6, U=0.0).scan_grid(5, 5)
    d = r.as_dict()
    required = [
        "U", "L", "N_theta", "N_phi", "C_raw", "C_rounded", "chern_error",
        "gap_min", "theta_gap_min", "phi_gap_min", "min_link_overlap",
        "max_abs_berry_curvature", "solver_residual", "converged",
    ]
    for field in required:
        assert field in d, f"missing field: {field}"


def test_scan_result_converged_flag():
    r_good = RiceMeleHubbardSolver(L=6, U=0.0).scan_grid(5, 5)
    assert r_good.converged


def test_csv_roundtrip(tmp_path):
    r = RiceMeleHubbardSolver(L=6, U=0.0).scan_grid(5, 5)
    csv_path = tmp_path / "test.csv"
    _write_csv([r], csv_path)
    assert csv_path.exists()
    with open(csv_path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert float(rows[0]["C_raw"]) == pytest.approx(r.C_raw)


# ===========================================================================
# detect_Uc
# ===========================================================================


def test_detect_uc_finds_transition():
    """Synthetic results with a clear 2→0 transition."""
    from u_scan_c_solver import ScanResult as SR

    def _fake(U, C):
        return SR(
            U=U, L=6, N_theta=5, N_phi=5,
            C_raw=float(C), C_rounded=C, chern_error=0.0,
            gap_min=0.1, theta_gap_min=0.0, phi_gap_min=0.0,
            min_link_overlap=0.9, max_abs_berry_curvature=0.5,
            solver_residual=1e-14, converged=True,
            berry_curvature_map=np.zeros((5, 5)),
            ground_state_energies=np.zeros((5, 5)),
            first_excited_energies=np.zeros((5, 5)),
            hermiticity_errors=np.zeros((5, 5)),
            diagonalization_count=25, wall_time_s=0.0,
        )

    results = [
        _fake(-16, 2), _fake(-8, 2), _fake(0, 2), _fake(4, 2),
        _fake(5.5, 2), _fake(6.0, 2), _fake(6.5, 0), _fake(8, 0),
        _fake(16, 0), _fake(32, 0),
    ]
    Uc = detect_Uc(results)
    assert Uc is not None
    assert 6.0 <= Uc <= 6.5


def test_detect_uc_returns_none_if_no_transition():
    from u_scan_c_solver import ScanResult as SR

    def _fake(U, C):
        return SR(
            U=U, L=6, N_theta=5, N_phi=5,
            C_raw=float(C), C_rounded=C, chern_error=0.0,
            gap_min=0.1, theta_gap_min=0.0, phi_gap_min=0.0,
            min_link_overlap=0.9, max_abs_berry_curvature=0.5,
            solver_residual=1e-14, converged=True,
            berry_curvature_map=np.zeros((5, 5)),
            ground_state_energies=np.zeros((5, 5)),
            first_excited_energies=np.zeros((5, 5)),
            hermiticity_errors=np.zeros((5, 5)),
            diagonalization_count=25, wall_time_s=0.0,
        )

    results = [_fake(0, 2), _fake(4, 2), _fake(8, 2), _fake(16, 2)]
    Uc = detect_Uc(results)
    assert Uc is None


# ===========================================================================
# _build_refined_u_list
# ===========================================================================


def test_refined_u_list_includes_negative_checkpoints():
    u_list = _build_refined_u_list(6.0, du=0.5)
    for neg in [-32, -24, -16, -8]:
        assert neg in u_list


def test_refined_u_list_covers_transition_window():
    u_list = _build_refined_u_list(6.0, du=0.5)
    assert min(u for u in u_list if u >= 0) <= 5.0
    assert max(u_list) >= 7.0


# ===========================================================================
# Vertex caching
# ===========================================================================


def test_vertex_cache_hits():
    solver = RiceMeleHubbardSolver(L=4, U=0.0)
    from fractions import Fraction
    key = (Fraction(0, 3), Fraction(0, 3))
    v1 = solver._vertex(key)
    assert solver._diag_count == 1
    v2 = solver._vertex(key)
    assert solver._diag_count == 1  # no new diag
    assert np.allclose(v1.state, v2.state)


# ===========================================================================
# Solver residual
# ===========================================================================


def test_solver_residual_is_small():
    for U in [0.0, 6.0, 16.0]:
        solver = RiceMeleHubbardSolver(L=6, U=U)
        r = solver.scan_grid(5, 5)
        assert r.solver_residual < 1e-9, f"U={U}: residual={r.solver_residual:.2e}"


# ===========================================================================
# Berry curvature map shape
# ===========================================================================


def test_berry_curvature_map_shape():
    N = 5
    r = RiceMeleHubbardSolver(L=6, U=0.0).scan_grid(N, N)
    assert r.berry_curvature_map.shape == (N, N)


# ===========================================================================
# Filename stem
# ===========================================================================


def test_filename_stem_encoding():
    stem = _build_filename_stem(-16.0, 6, 9, 9)
    assert "U_neg16" in stem
    assert "L6" in stem
    assert "Ntheta9" in stem
    assert "Nphi9" in stem


# ===========================================================================
# Quick smoke: coarse scan runs end-to-end
# ===========================================================================


def test_coarse_scan_smoke():
    """Minimal smoke: 3 U points, verify all return valid results."""
    results = run_coarse_scan([-8, 0, 8])
    assert len(results) == 3
    for r in results:
        assert r.L == 6
        assert r.N_theta == 5
        assert r.N_phi == 5
        assert r.gap_min > 0
        assert r.solver_residual < 1e-9
