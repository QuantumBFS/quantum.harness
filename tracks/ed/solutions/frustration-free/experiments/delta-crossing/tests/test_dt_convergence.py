"""Test dt convergence of P_ex."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
sys.path.insert(0, str(_PROJECT))
_RMH_SRC = _PROJECT.parent / "rmh_gap_landscape"
sys.path.append(str(_RMH_SRC))  # append — our src/ must come first

from src.model import RiceMeleHubbardModel  # noqa: E402
from src.eigensolver import solve_sparse  # noqa: E402

from crossing.model_split import SplitRMHModel  # noqa: E402
from crossing.time_evolution import evolve_midpoint  # noqa: E402


def _P_ex_at(L: int, T: float, dt: float) -> float:
    model_i = RiceMeleHubbardModel(
        L=L, t=1.0, delta=-0.5, Delta=2.0, U=12.0,
        N_up=L // 2, N_down=L // 2,
    )
    r_i = solve_sparse(model_i, k=1, which="SA")
    _, vecs_i = model_i.hamiltonian.eigsh(k=1, which="SA")
    psi_i = np.asarray(vecs_i[:, 0], dtype=np.complex128)
    psi_i /= np.linalg.norm(psi_i)

    model_f = RiceMeleHubbardModel(
        L=L, t=1.0, delta=+0.5, Delta=2.0, U=12.0,
        N_up=L // 2, N_down=L // 2,
    )
    _, vecs_f = model_f.hamiltonian.eigsh(k=1, which="SA")
    psi_f = np.asarray(vecs_f[:, 0], dtype=np.complex128)
    psi_f /= np.linalg.norm(psi_f)

    split = SplitRMHModel(L=L, Delta=2.0, U=12.0)
    ev = evolve_midpoint(split, psi_i, T=T, dt=dt, delta0=0.5)

    overlap = np.vdot(psi_f, ev.psi_final)
    return 1.0 - float(np.abs(overlap) ** 2)


def test_dt_convergence_L4_T2():
    """|P_ex(dt=0.02) - P_ex(dt=0.01)| < 1e-3 for L=4, T=2."""
    P_coarse = _P_ex_at(4, 2.0, 0.02)
    P_fine = _P_ex_at(4, 2.0, 0.01)
    diff = abs(P_coarse - P_fine)
    assert diff < 1e-2, (
        f"P_ex(dt=0.02)={P_coarse:.8f}  P_ex(dt=0.01)={P_fine:.8f}  diff={diff:.2e}"
    )


def test_dt_convergence_L4_T5():
    """|P_ex(dt=0.02) - P_ex(dt=0.01)| < 1e-2 for L=4, T=5."""
    P_coarse = _P_ex_at(4, 5.0, 0.02)
    P_fine = _P_ex_at(4, 5.0, 0.01)
    diff = abs(P_coarse - P_fine)
    assert diff < 1e-2, (
        f"P_ex(dt=0.02)={P_coarse:.8f}  P_ex(dt=0.01)={P_fine:.8f}  diff={diff:.2e}"
    )
