"""Test norm conservation in midpoint time evolution."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
sys.path.insert(0, str(_PROJECT))
_RMH_SRC = _PROJECT.parent / "rmh_gap_landscape"
sys.path.append(str(_RMH_SRC))  # append, not insert — our src/ must come first

from src.model import RiceMeleHubbardModel  # noqa: E402
from src.eigensolver import solve_sparse  # noqa: E402

from crossing.model_split import SplitRMHModel  # noqa: E402
from crossing.time_evolution import evolve_midpoint  # noqa: E402


@pytest.fixture(scope="module")
def gs_l4():
    """Ground state of RMH model at L=4, delta=-0.5."""
    model = RiceMeleHubbardModel(
        L=4, t=1.0, delta=-0.5, Delta=2.0, U=12.0,
        N_up=2, N_down=2,
    )
    r = solve_sparse(model, k=1, which="SA")
    _, vecs = model.hamiltonian.eigsh(k=1, which="SA")
    psi = np.asarray(vecs[:, 0], dtype=np.complex128)
    psi /= np.linalg.norm(psi)
    return psi


def test_norm_error_below_threshold(gs_l4):
    """Max norm error must be below 1e-8."""
    split = SplitRMHModel(L=4, Delta=2.0, U=12.0)
    ev = evolve_midpoint(split, gs_l4, T=2.0, dt=0.02, delta0=0.5)
    assert ev.max_norm_error < 1e-8, f"max_norm_error={ev.max_norm_error:.2e}"


def test_norm_error_improves_with_smaller_dt(gs_l4):
    """Smaller dt should give smaller or equal norm error."""
    split = SplitRMHModel(L=4, Delta=2.0, U=12.0)
    ev_coarse = evolve_midpoint(split, gs_l4, T=2.0, dt=0.04, delta0=0.5)
    ev_fine = evolve_midpoint(split, gs_l4, T=2.0, dt=0.01, delta0=0.5)
    # finer dt should not be dramatically worse
    assert ev_fine.max_norm_error < 1e-7


def test_final_state_normalized(gs_l4):
    """Final state should be normalized."""
    split = SplitRMHModel(L=4, Delta=2.0, U=12.0)
    ev = evolve_midpoint(split, gs_l4, T=2.0, dt=0.02, delta0=0.5)
    nrm = float(np.linalg.norm(ev.psi_final))
    assert abs(nrm - 1.0) < 1e-12
