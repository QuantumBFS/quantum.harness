"""Locked and resumable Phase 6 scan specification."""

from __future__ import annotations

from pathlib import Path

import numpy as np


PRODUCTION_SIZES = [32, 64, 128, 256]
FULL_SCAN_CHI = 128


def _grid(start: float, stop: float, step: float) -> np.ndarray:
    count = int(round((stop - start) / step))
    return np.round(start + step * np.arange(count + 1), 12)


def locked_gamma_grid() -> np.ndarray:
    """Return the immutable union of coarse and fine Gamma grids."""
    coarse = _grid(1.540, 1.580, 0.005)
    fine = _grid(1.552, 1.570, 0.001)
    return np.unique(np.concatenate([coarse, fine]))


def symmetric_extended_gamma_grid(
    extension: float | tuple[float, float],
) -> dict[str, np.ndarray]:
    """Extend both sides equally while retaining the locked spacings."""
    if isinstance(extension, tuple):
        if len(extension) != 2 or extension[0] != extension[1]:
            raise ValueError("Gamma extension must be symmetric")
        amount = float(extension[0])
    else:
        amount = float(extension)
    if amount <= 0.0 or not np.isclose(amount / 0.010, round(amount / 0.010)):
        raise ValueError("symmetric extension must be a positive multiple of 0.010")
    return {
        "coarse": _grid(1.540 - amount, 1.580 + amount, 0.005),
        "fine": _grid(1.552 - amount, 1.570 + amount, 0.001),
    }


def build_run_spec(
    *,
    sigma: float,
    fit_id: str,
    output_dir: str | Path,
) -> dict:
    """Build the production run specification without executing any cell."""
    gammas = locked_gamma_grid()
    cells = [
        {
            "cell_id": f"L{length}_Gamma{gamma:.3f}_K24_chi{FULL_SCAN_CHI}",
            "length": length,
            "gamma": float(gamma),
            "num_exponentials": 24,
            "chi": FULL_SCAN_CHI,
            "status": "pending",
        }
        for length in PRODUCTION_SIZES
        for gamma in gammas
    ]
    return {
        "run_id": "phase6_sigma1.75",
        "run_dir": str(output_dir),
        "sigma": float(sigma),
        "sizes": list(PRODUCTION_SIZES),
        "gammas": gammas.tolist(),
        "settings": {
            "full_scan_chi": FULL_SCAN_CHI,
            "coarse_step": 0.005,
            "fine_step": 0.001,
            "adaptive_refinement": False,
        },
        "provenance": {"fit_id": fit_id},
        "cells": cells,
    }
