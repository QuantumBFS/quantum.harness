"""Finite-domain numerical metrics used by the progress atlas."""

from __future__ import annotations

import numpy as np


def _finite(values: np.ndarray, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} contains non-finite values")
    return array


def profile_error(
    reference: np.ndarray,
    candidate: np.ndarray,
    background: float,
    mask: np.ndarray,
) -> dict[str, list[float]]:
    reference = _finite(reference, "reference")
    candidate = _finite(candidate, "candidate")
    mask = np.asarray(mask, dtype=bool)
    if reference.shape != candidate.shape or reference.ndim != 2:
        raise ValueError("profiles must have equal (time, space) shape")
    if mask.shape != (reference.shape[1],) or not mask.any():
        raise ValueError("mask must select at least one spatial coordinate")
    delta = candidate[:, mask] - reference[:, mask]
    signal = candidate[:, mask] - float(background)
    denom = np.linalg.norm(signal, axis=1)
    numer = np.linalg.norm(delta, axis=1)
    relative = np.divide(numer, denom, out=np.zeros_like(numer), where=denom > 0)
    return {
        "relative_l2": relative.tolist(),
        "max_abs": np.max(np.abs(delta), axis=1).tolist(),
    }


def normalized_even_odd_residual(
    up: np.ndarray, down: np.ndarray
) -> list[float]:
    up = _finite(up, "up")
    down = _finite(down, "down")
    if up.shape != down.shape or up.ndim != 2:
        raise ValueError("spin-flip arrays must have equal (time, space) shape")
    even = np.linalg.norm(up + down, axis=1)
    odd = np.linalg.norm(up - down, axis=1)
    return np.divide(even, odd, out=np.zeros_like(even), where=odd > 0).tolist()


def common_coordinate_indices(
    reference_x: np.ndarray, candidate_x: np.ndarray, limit: float
) -> tuple[np.ndarray, np.ndarray]:
    reference_x = _finite(reference_x, "reference_x")
    candidate_x = _finite(candidate_x, "candidate_x")
    wanted = reference_x[np.abs(reference_x) <= limit]
    ref = np.flatnonzero(np.isin(reference_x, wanted))
    cand = np.flatnonzero(np.isin(candidate_x, wanted))
    if ref.size == 0 or cand.size != ref.size:
        raise ValueError("coordinate grids have no exact common window")
    if not np.allclose(reference_x[ref], candidate_x[cand], atol=0, rtol=0):
        raise ValueError("coordinate alignment is not exact")
    return ref, cand

