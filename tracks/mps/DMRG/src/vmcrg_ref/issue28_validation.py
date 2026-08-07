"""Shared scientific-gate semantics for the Issue 28 workflow."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np


def excess_patch_tv_components(
    observed_probabilities: np.ndarray,
    target_probabilities: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return observed, target-noise, and excess TV from the uniform target."""

    observed = np.asarray(observed_probabilities, dtype=np.float64)
    target = np.asarray(target_probabilities, dtype=np.float64)
    if observed.shape != target.shape or observed.ndim < 1:
        raise ValueError("patch probability arrays must have matching shapes")
    if observed.shape[-1] <= 1:
        raise ValueError("patch probability arrays require at least two bins")
    if not np.all(np.isfinite(observed)) or not np.all(np.isfinite(target)):
        raise ValueError("patch probabilities must be finite")
    if np.any(observed < 0.0) or np.any(target < 0.0):
        raise ValueError("patch probabilities must be nonnegative")
    if not np.allclose(observed.sum(axis=-1), 1.0, atol=1e-12, rtol=0.0):
        raise ValueError("observed patch probabilities must sum to one")
    if not np.allclose(target.sum(axis=-1), 1.0, atol=1e-12, rtol=0.0):
        raise ValueError("target patch probabilities must sum to one")

    uniform = 1.0 / observed.shape[-1]
    observed_tv = 0.5 * np.sum(np.abs(observed - uniform), axis=-1)
    target_tv = 0.5 * np.sum(np.abs(target - uniform), axis=-1)
    return observed_tv, target_tv, observed_tv - target_tv


def scientific_round_gates_pass(gates: Mapping[str, Any]) -> bool:
    """Return whether one N2/N3 round passed every frozen scientific gate."""

    validation = gates.get("validation", gates.get("frozen_validation"))
    if (
        gates.get("training") != "CONVERGED"
        or validation != "PASS"
        or gates.get("objective") != "IDENTIFIABLE"
    ):
        return False
    improvement = gates.get("objective_improvement")
    return improvement is None or improvement == "PASS"
