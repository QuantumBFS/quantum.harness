"""Test dense vs sparse solver agreement."""

import sys
from pathlib import Path

import numpy as np
import pytest

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
sys.path.insert(0, str(_PROJECT))
from src.eigensolver import CONVERGENCE_TOL, SectorResult, solve_dense, solve_sparse
from src.model import RiceMeleHubbardModel


class TestDenseSolver:
    def test_residual_below_tolerance_L4(self):
        m = RiceMeleHubbardModel(L=4, t=1.0, delta=0.0, Delta=2.0, U=12.0,
                                 N_up=2, N_down=2)
        r = solve_dense(m)
        assert r.residual < 1e-12
        assert r.converged
        assert r.method == "dense_eigh"

    def test_returns_all_eigenvalues(self):
        m = RiceMeleHubbardModel(L=4, t=1.0, delta=0.0, Delta=0.0, U=12.0,
                                 N_up=2, N_down=2)
        r = solve_dense(m)
        assert len(r.eigenvalues) == 36  # C(4,2)^2

    def test_eigenvalues_sorted(self):
        m = RiceMeleHubbardModel(L=4, t=1.0, delta=0.3, Delta=1.0, U=12.0,
                                 N_up=2, N_down=2)
        r = solve_dense(m)
        assert np.all(np.diff(r.eigenvalues) >= -1e-12)

    def test_eigenvalues_real(self):
        m = RiceMeleHubbardModel(L=4, t=1.0, delta=0.0, Delta=2.0, U=12.0,
                                 N_up=2, N_down=2)
        r = solve_dense(m)
        assert np.all(np.isreal(r.eigenvalues))


class TestSparseSolver:
    def test_residual_below_tolerance(self):
        m = RiceMeleHubbardModel(L=4, t=1.0, delta=0.0, Delta=2.0, U=12.0,
                                 N_up=2, N_down=2)
        r = solve_sparse(m, k=2)
        assert r.residual < 1e-8
        assert r.converged
        assert "sparse" in r.method or "dense" in r.method

    def test_returns_requested_eigenvalues(self):
        m = RiceMeleHubbardModel(L=4, t=1.0, delta=0.3, Delta=1.0, U=12.0,
                                 N_up=2, N_down=2)
        for k in [1, 2, 3]:
            r = solve_sparse(m, k=k)
            assert len(r.eigenvalues) == k

    def test_sparse_matches_dense_L6(self):
        for delta in [0.0, 0.3, -0.5]:
            for Dv in [0.0, 2.0, 6.0]:
                m = RiceMeleHubbardModel(L=6, t=1.0, delta=delta, Delta=Dv, U=12.0,
                                         N_up=3, N_down=3)
                r_dense = solve_dense(m)
                r_sparse = solve_sparse(m, k=2)
                n_cmp = r_sparse.eigenvalues.shape[0]
                de = np.max(np.abs(r_sparse.eigenvalues[:n_cmp] - r_dense.eigenvalues[:n_cmp]))
                assert de < 1e-8, f"δ={delta} Δ={Dv}: max|ΔE|={de:.2e}"

    def test_sparse_matches_dense_all_sectors(self):
        sectors = [(2, 2), (3, 1), (3, 2), (1, 2)]
        for n_up, n_down in sectors:
            m = RiceMeleHubbardModel(L=4, t=1.0, delta=0.3, Delta=2.0, U=12.0,
                                     N_up=n_up, N_down=n_down)
            r_dense = solve_dense(m)
            r_sparse = solve_sparse(m, k=1)
            de = abs(r_sparse.eigenvalues[0] - r_dense.eigenvalues[0])
            assert de < 1e-8


class TestLargeL10:
    def test_L10_hamiltonian_builds(self):
        m = RiceMeleHubbardModel(L=10, t=1.0, delta=0.0, Delta=0.0, U=12.0,
                                 N_up=5, N_down=5)
        assert m.dim == 63504
        assert m.hermiticity_error() < 1e-12
