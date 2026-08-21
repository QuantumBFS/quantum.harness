"""Pure gap-convergence and effective-exponent analysis for Phase 6."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class GapConvergenceStatus:
    converged: bool
    next_chi: int | None
    relative_threshold: float
    discarded_threshold: float
    relative_shift: float
    reason: str


def effective_z(delta_l: float, delta_2l: float) -> float:
    """Return the gap-based pairwise z_eff for a doubling of L."""
    if delta_l <= 0 or delta_2l <= 0:
        raise ValueError("gaps must be positive")
    return float(np.log(delta_l / delta_2l) / np.log(2.0))


def z_effective_series(lengths, gaps):
    sizes = np.asarray(lengths, dtype=int)
    values = np.asarray(gaps, dtype=float)
    if len(sizes) != len(values) or np.any(sizes[1:] != 2 * sizes[:-1]):
        raise ValueError("lengths must be consecutive doubling pairs")
    return np.array([effective_z(values[i], values[i + 1]) for i in range(len(values) - 1)])


def gap_chi_status(
    gaps_by_chi,
    discarded_by_state,
    relative_threshold: float = 1e-3,
    discarded_threshold: float = 1e-9,
) -> GapConvergenceStatus:
    """Require stable gaps and acceptable discarded weights in both sectors."""
    gaps = {int(k): float(v) for k, v in gaps_by_chi.items()}
    if 256 not in gaps or 384 not in gaps:
        missing = 256 if 256 not in gaps else 384
        return GapConvergenceStatus(False, missing, relative_threshold, discarded_threshold, np.nan, "missing_chi")
    relative = abs(gaps[384] - gaps[256]) / abs(gaps[384])
    weights_ok = all(
        float(discarded_by_state[chi][sector]) <= discarded_threshold
        for chi in (256, 384)
        for sector in ("even", "odd")
    )
    converged = relative <= relative_threshold and weights_ok
    return GapConvergenceStatus(
        converged,
        None if converged else 512,
        relative_threshold,
        discarded_threshold,
        float(relative),
        "converged" if converged else "gap_or_discarded_weight_failed",
    )
