from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ThermoPoint:
    beta: float
    log_z: float
    f: float
    u: float
    c: float


def thermal_from_spectrum(
    evals: np.ndarray,
    *,
    beta: float,
    nsites: int,
) -> ThermoPoint:
    if beta <= 0 or nsites < 1:
        raise ValueError("beta and nsites must be positive")
    evals = np.asarray(evals, dtype=np.float64)
    e0 = float(evals.min())
    weights = np.exp(-beta * (evals - e0))
    norm = float(weights.sum())
    probs = weights / norm
    mean_e = float(probs @ evals)
    mean_e2 = float(probs @ (evals * evals))
    log_z = float(np.log(norm) - beta * e0)
    return ThermoPoint(
        beta=beta,
        log_z=log_z,
        f=-log_z / (beta * nsites),
        u=mean_e / nsites,
        c=beta * beta * (mean_e2 - mean_e * mean_e) / nsites,
    )
