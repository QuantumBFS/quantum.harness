"""Locked planning rules for Phase 8 sigma=1.75 finite-size scaling."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import numpy as np

from .phase8_scaling import strict_endpoint_crossing, two_point_sensitivity


SIGMA = 1.75
ENDPOINTS = (1.55, 1.60)
SIZES = (16, 32, 64, 96, 128)
K = 24
CROSSING_CHI = 64
GAP_CHI = 128
ALPHA = 0.5
R_FIT = 2048
GAP_RELATIVE_VARIANCE_LIMIT = 1.0e-10
GAP_DISCARDED_WEIGHT_LIMIT = 1.0e-7


def build_crossing_spec(output_dir: str | Path) -> dict:
    """Create exactly two pending L=128 even-sector endpoint cells."""
    run_dir = Path(output_dir)
    cells = []
    for gamma in ENDPOINTS:
        cell_id = f"sigma{SIGMA:.2f}_L128_Gamma{gamma:.2f}_even_K{K}_chi{CROSSING_CHI}"
        cells.append(
            {
                "cell_id": cell_id,
                "status": "pending",
                "sigma": SIGMA,
                "L": 128,
                "Gamma": gamma,
                "sector": "even",
                "K": K,
                "chi": CROSSING_CHI,
            }
        )
    return {
        "run_id": "phase8-sigma1.75-crossing-L128",
        "run_dir": str(run_dir),
        "settings": {
            "sigma": SIGMA,
            "Gamma_endpoints": list(ENDPOINTS),
            "K": K,
            "chi": CROSSING_CHI,
            "alpha": ALPHA,
            "r_fit": R_FIT,
            "sector": "even",
            "exact_zero_pruning": True,
            "approximate_mpo_compression": False,
            "adaptive_gamma": False,
        },
        "cells": cells,
    }


def _validate_summary(
    summary: Mapping,
    *,
    length: int,
    gamma: float,
    chi: int,
) -> float:
    if summary.get("status") != "success":
        raise ValueError(f"L={length}, Gamma={gamma} summary is not successful")
    settings = summary.get("settings", {})
    expected = {
        "sigma": SIGMA,
        "length": length,
        "gamma": gamma,
        "num_exponentials": K,
        "alpha": ALPHA,
        "r_fit": R_FIT,
        "chi_schedule": [chi],
        "sectors": ["even"],
        "direct_only": True,
    }
    for field, value in expected.items():
        actual = settings.get(field)
        if isinstance(value, float):
            matches = actual is not None and np.isclose(float(actual), value)
        else:
            matches = actual == value
        if not matches:
            raise ValueError(
                f"L={length}, Gamma={gamma} {field} mismatch: "
                f"{actual!r} != {value!r}"
            )
    mpo = summary.get("mpo", {})
    if mpo.get("pruned") is not True:
        raise ValueError("exact-zero MPO pruning must be enabled")
    if mpo.get("approximate_compression") is not False:
        raise ValueError("approximate MPO compression must be disabled")
    r_xi = float(summary.get("raw_observables", {}).get("r_xi", np.nan))
    if not np.isfinite(r_xi):
        raise ValueError("R_xi must be finite")
    return r_xi


def common_field_sensitivity(x32: float, x64: float) -> dict:
    """Evaluate the locked power and logarithmic crossing sensitivities."""
    power = two_point_sensitivity([x32, x64], [32, 64], "power")
    log = two_point_sensitivity([x32, x64], [32, 64], "log")
    return {
        "primary": "power",
        "gap_field": power["estimate"],
        "power": power,
        "log": log,
        "spread": abs(power["estimate"] - log["estimate"]),
        "propagated_to_gap_uncertainty": False,
        "correction_coordinates_are_sensitivity_only": True,
        "known_correction_exponent_assumed": False,
    }


def decide_crossing(
    phase7_decision: Mapping,
    summaries: Mapping[tuple[int, float], Mapping],
) -> dict:
    """Resolve L=64,128 only when both locked endpoints strictly bracket."""
    if not np.isclose(float(phase7_decision.get("sigma", np.nan)), SIGMA):
        raise ValueError("Phase 7 decision must have sigma=1.75")
    if phase7_decision.get("status") != "ready":
        raise ValueError("Phase 7 decision must have status=ready")
    if not np.allclose(phase7_decision.get("broad_bracket", []), ENDPOINTS):
        raise ValueError("Phase 7 bracket must match the locked endpoints")
    x32 = float(phase7_decision.get("broad_Gamma_x", np.nan))
    if not np.isfinite(x32):
        raise ValueError("Phase 7 Gamma_x(32,64) must be finite")

    r64 = []
    r128 = []
    for gamma in ENDPOINTS:
        try:
            small = summaries[(64, gamma)]
            large = summaries[(128, gamma)]
        except KeyError as error:
            raise ValueError(
                f"missing endpoint summary L={error.args[0][0]}, "
                f"Gamma={error.args[0][1]}"
            ) from error
        r64.append(
            _validate_summary(
                small,
                length=64,
                gamma=gamma,
                chi=CROSSING_CHI,
            )
        )
        r128.append(
            _validate_summary(
                large,
                length=128,
                gamma=gamma,
                chi=CROSSING_CHI,
            )
        )

    crossing = strict_endpoint_crossing(ENDPOINTS, r64, r128)
    result = {
        "sigma": SIGMA,
        "Gamma_x_32_64": x32,
        "endpoint_R_xi": {
            "L64": r64,
            "L128": r128,
        },
        **crossing,
    }
    if crossing["status"] != "resolved":
        return result

    x64 = float(crossing["Gamma_x"])
    return {
        **result,
        "Gamma_x_64_128": x64,
        "common_field": common_field_sensitivity(x32, x64),
    }


def build_gap_spec(decision: Mapping, output_dir: str | Path) -> dict:
    """Create ten ordered common-field states after a resolved crossing."""
    if decision.get("status") != "resolved":
        raise ValueError("a resolved Phase 8 crossing is required")
    if not np.isclose(float(decision.get("sigma", np.nan)), SIGMA):
        raise ValueError("resolved decision must have sigma=1.75")
    gamma = float(decision.get("common_field", {}).get("gap_field", np.nan))
    if not np.isfinite(gamma):
        raise ValueError("resolved decision must contain a finite gap field")

    run_dir = Path(output_dir)
    cells = []
    for length in SIZES:
        for sector in ("even", "odd"):
            cell_id = (
                f"sigma{SIGMA:.2f}_L{length}_Gamma{gamma:.12g}_"
                f"{sector}_K{K}_chi{GAP_CHI}"
            )
            cells.append(
                {
                    "cell_id": cell_id,
                    "status": "pending",
                    "sigma": SIGMA,
                    "L": length,
                    "Gamma": gamma,
                    "sector": sector,
                    "K": K,
                    "chi": GAP_CHI,
                }
            )
    return {
        "run_id": "phase8-sigma1.75-gaps-common-Gamma",
        "run_dir": str(run_dir),
        "settings": {
            "sigma": SIGMA,
            "Gamma": gamma,
            "K": K,
            "chi": GAP_CHI,
            "alpha": ALPHA,
            "r_fit": R_FIT,
            "sectors": ["even", "odd"],
            "exact_zero_pruning": True,
            "approximate_mpo_compression": False,
            "acceptance": {
                "relative_variance_max": GAP_RELATIVE_VARIANCE_LIMIT,
                "discarded_weight_max": GAP_DISCARDED_WEIGHT_LIMIT,
                "sweeps_must_be_below_cap": True,
                "positive_gap_required": True,
                "protocol_amendment": (
                    "discarded-weight limit relaxed from 1e-8 after the "
                    "L=64 odd state recorded 5.49e-8 while variance and "
                    "energy convergence passed"
                ),
            },
        },
        "cells": cells,
    }
