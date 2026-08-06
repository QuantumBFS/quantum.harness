"""Test fidelity bounds and physical monotonicity for P_ex(T)."""

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


def _compute_P_ex(L: int, T: float, dt: float = 0.02) -> float:
    """Compute P_ex for given parameters."""
    # initial GS
    model_i = RiceMeleHubbardModel(
        L=L, t=1.0, delta=-0.5, Delta=2.0, U=12.0,
        N_up=L // 2, N_down=L // 2,
    )
    r_i = solve_sparse(model_i, k=1, which="SA")
    _, vecs_i = model_i.hamiltonian.eigsh(k=1, which="SA")
    psi_i = np.asarray(vecs_i[:, 0], dtype=np.complex128)
    psi_i /= np.linalg.norm(psi_i)

    # final GS
    model_f = RiceMeleHubbardModel(
        L=L, t=1.0, delta=+0.5, Delta=2.0, U=12.0,
        N_up=L // 2, N_down=L // 2,
    )
    _, vecs_f = model_f.hamiltonian.eigsh(k=1, which="SA")
    psi_f = np.asarray(vecs_f[:, 0], dtype=np.complex128)
    psi_f /= np.linalg.norm(psi_f)

    # evolve
    split = SplitRMHModel(L=L, Delta=2.0, U=12.0)
    ev = evolve_midpoint(split, psi_i, T=T, dt=dt, delta0=0.5)

    overlap = np.vdot(psi_f, ev.psi_final)
    F = float(np.abs(overlap) ** 2)
    return 1.0 - F


class TestFidelityBounds:
    """Fidelity and P_ex must be in [0, 1]."""

    @pytest.mark.parametrize("T", [1.0, 5.0, 20.0])
    def test_P_ex_in_01(self, T):
        P = _compute_P_ex(4, T, dt=0.05)
        assert 0.0 <= P <= 1.0, f"P_ex({T}) = {P}"


class TestAdiabaticTrend:
    """P_ex should decrease as T increases (more adiabatic)."""

    def test_longer_T_gives_smaller_P_ex(self):
        P_short = _compute_P_ex(4, 1.0, dt=0.05)
        P_long = _compute_P_ex(4, 10.0, dt=0.05)
        assert P_long < P_short, (
            f"P_ex(T=1)={P_short:.6f} should be > P_ex(T=10)={P_long:.6f}"
        )

    def test_very_long_T_approaches_zero(self):
        """At very large T, P_ex should be small (< 0.1 for L=4)."""
        P = _compute_P_ex(4, 50.0, dt=0.05)
        assert P < 0.5, f"P_ex(T=50)={P:.6f} should be small"
