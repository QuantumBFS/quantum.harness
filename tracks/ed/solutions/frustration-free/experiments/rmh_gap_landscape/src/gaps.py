"""Gap computation: 4-sector orchestration at a single (δ, Δ) point."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .eigensolver import SectorResult, solve_dense, solve_sparse
from .model import RiceMeleHubbardModel


@dataclass
class GapPointResult:
    L: int
    delta: float
    Delta: float
    U: float

    # ground-state energies per sector
    E0_half: float
    E1_half: float
    E0_triplet: float
    E0_charge_up: float
    E0_charge_down: float

    # three gaps
    Delta_MB: float   # E1_half - E0_half
    Delta_s: float    # E0_triplet - E0_half
    Delta_c: float    # E0_charge_up + E0_charge_down - 2*E0_half

    # diagnostic dicts
    residuals: dict[str, float] = field(default_factory=dict)
    converged: dict[str, bool] = field(default_factory=dict)
    dimensions: dict[str, int] = field(default_factory=dict)
    wall_time_s: float = 0.0
    method: str = ""


def solve_point(
    L: int,
    delta: float,
    Delta: float,
    U: float,
    t: float = 1.0,
    method: str = "auto",
) -> GapPointResult:
    """Solve all 4 sectors and compute three gaps at one (δ, Δ) point.

    Parameters
    ----------
    method : str
        "dense"  — np.linalg.eigh for all sectors
        "sparse" — eigsh(k, which="SA") for all sectors
        "auto"   — dense for L ≤ 6, sparse for L ≥ 8
    """
    t0 = time.perf_counter()

    if method == "auto":
        method = "dense" if L <= 6 else "sparse"

    half = L // 2

    # define sectors
    sectors: dict[str, tuple[int, int, int]] = {
        "half": (half, half, 2),           # (3,3) for L=6, needs k=2
        "triplet": (half + 1, half - 1, 1), # (4,2) for L=6
        "charge_up": (half + 1, half, 1),   # (4,3) for L=6
        "charge_down": (half - 1, half, 1), # (2,3) for L=6
    }

    residuals: dict[str, float] = {}
    converged: dict[str, bool] = {}
    dimensions: dict[str, int] = {}
    energies: dict[str, np.ndarray] = {}

    for name, (n_up, n_down, k) in sectors.items():
        model = RiceMeleHubbardModel(
            L=L, t=t, delta=delta, Delta=Delta, U=U,
            N_up=n_up, N_down=n_down,
        )
        dimensions[name] = model.dim

        if method == "dense":
            r: SectorResult = solve_dense(model)
        else:
            r = solve_sparse(model, k=k, which="SR")

        residuals[name] = r.residual
        converged[name] = r.converged
        energies[name] = r.eigenvalues

    E0_half = float(energies["half"][0])
    E1_half = float(energies["half"][1]) if len(energies["half"]) >= 2 else float("nan")
    E0_triplet = float(energies["triplet"][0])
    E0_charge_up = float(energies["charge_up"][0])
    E0_charge_down = float(energies["charge_down"][0])

    elapsed = time.perf_counter() - t0

    return GapPointResult(
        L=L, delta=delta, Delta=Delta, U=U,
        E0_half=E0_half, E1_half=E1_half,
        E0_triplet=E0_triplet,
        E0_charge_up=E0_charge_up,
        E0_charge_down=E0_charge_down,
        Delta_MB=E1_half - E0_half,
        Delta_s=E0_triplet - E0_half,
        Delta_c=E0_charge_up + E0_charge_down - 2 * E0_half,
        residuals=residuals,
        converged=converged,
        dimensions=dimensions,
        wall_time_s=elapsed,
        method=method,
    )
