"""Locked Phase 9 challenge-validation specifications and analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import numpy as np

from .crossing_analysis import linear_crossing
from .phase8_scaling import (
    adjacent_effective_exponents,
    direct_gap_power_law,
    sensitivity_regression,
)


NN_SIZES = (16, 32, 64)
GAMMA_NN = (0.98, 1.00, 1.02)
MEAN_FIELD_SIZES = (16, 32, 64, 96)
SIGMA_MEAN_FIELD = 2.0 / 3.0
GAMMA_MEAN_FIELD = 3.673
MEAN_FIELD_BENCHMARKS = (
    {
        "sigma": SIGMA_MEAN_FIELD,
        "Gamma": GAMMA_MEAN_FIELD,
        "expected_z": 1.0 / 3.0,
    },
    {
        "sigma": 0.4,
        "Gamma": 5.85,
        "expected_z": 0.2,
    },
)
K = 24
CHI = 64
ALPHA = 0.5
R_FIT = 2048
RELATIVE_VARIANCE_LIMIT = 1.0e-10
DISCARDED_WEIGHT_LIMIT = 1.0e-7
SIGMA_18 = 1.8
GAMMA_SIGMA_18 = 1.5288
SIGMA_18_SIZES = (16, 32, 64, 96, 128)
SIGMA_18_CHI = 128


def build_nn_spec(output_dir: str | Path) -> dict:
    """Return the fixed eighteen-cell nearest-neighbor validation."""
    run_dir = Path(output_dir)
    cells = []
    for length in NN_SIZES:
        for gamma in GAMMA_NN:
            for sector in ("even", "odd"):
                cells.append(
                    {
                        "cell_id": (
                            f"nn_L{length}_Gamma{gamma:.2f}_"
                            f"{sector}_chi{CHI}"
                        ),
                        "status": "pending",
                        "model": "nearest-neighbor-tfim",
                        "L": length,
                        "Gamma": gamma,
                        "sector": sector,
                        "chi": CHI,
                    }
                )
    return {
        "run_id": "phase9-nn-limit",
        "run_dir": str(run_dir),
        "settings": {
            "hamiltonian": "-sum_i Z_i Z_(i+1) - Gamma sum_i X_i",
            "boundary": "periodic-ring-Hamiltonian_finite-OBC-MPS",
            "operator_convention": "rotated-xz-parity-v1",
            "sizes": list(NN_SIZES),
            "Gamma_grid": list(GAMMA_NN),
            "gap_field": 1.0,
            "chi": CHI,
            "adaptive_gamma": False,
            "automatic_chi128": False,
            "precision_z_claim": False,
        },
        "cells": cells,
    }


def build_mean_field_spec(
    output_dir: str | Path,
    fit_summaries: Mapping[float, str | Path],
) -> dict:
    """Return only mean-field branches that passed MPO qualification."""
    run_dir = Path(output_dir)
    expected_sigmas = {SIGMA_MEAN_FIELD}
    if set(fit_summaries) != expected_sigmas:
        raise ValueError(
            "fit_summaries must contain exactly the qualified sigma=2/3 fit"
        )
    cells = []
    for benchmark in MEAN_FIELD_BENCHMARKS:
        sigma = benchmark["sigma"]
        if sigma not in fit_summaries:
            continue
        gamma = benchmark["Gamma"]
        sigma_label = "2over3" if sigma == SIGMA_MEAN_FIELD else "0p4"
        for length in MEAN_FIELD_SIZES:
            for sector in ("even", "odd"):
                cells.append(
                    {
                        "cell_id": (
                            f"sigma{sigma_label}_L{length}_Gamma{gamma:g}_"
                            f"{sector}_K{K}_chi{CHI}"
                        ),
                        "status": "pending",
                        "model": "periodic-long-range-tfim",
                        "sigma": sigma,
                        "L": length,
                        "Gamma": gamma,
                        "sector": sector,
                        "K": K,
                        "chi": CHI,
                    }
                )
    return {
        "run_id": "phase9-mean-field-qualified-published-fields",
        "run_dir": str(run_dir),
        "settings": {
            "benchmarks": [
                dict(item)
                for item in MEAN_FIELD_BENCHMARKS
                if item["sigma"] in fit_summaries
            ],
            "excluded_benchmarks": [
                {
                    "sigma": 0.4,
                    "Gamma": 5.85,
                    "reason": "K32_finite_ring_error_above_1_percent",
                }
            ],
            "field_role": "external_published_benchmark",
            "sizes": list(MEAN_FIELD_SIZES),
            "K": K,
            "chi": CHI,
            "alpha": ALPHA,
            "r_fit": R_FIT,
            "fit_summaries": {
                str(sigma): str(path)
                for sigma, path in fit_summaries.items()
            },
            "exact_zero_pruning": True,
            "approximate_mpo_compression": False,
            "automatic_chi128": False,
            "reported_exponents": ["z"],
        },
        "cells": cells,
    }


def build_sigma18_z_spec(output_dir: str | Path) -> dict:
    """Return the fixed ten-state sigma=1.8 published-field validation."""
    run_dir = Path(output_dir)
    cells = []
    for length in SIGMA_18_SIZES:
        for sector in ("even", "odd"):
            cells.append(
                {
                    "cell_id": (
                        f"sigma1.8_L{length}_Gamma{GAMMA_SIGMA_18:g}_"
                        f"{sector}_K{K}_chi{SIGMA_18_CHI}"
                    ),
                    "status": "pending",
                    "model": "periodic-long-range-tfim",
                    "sigma": SIGMA_18,
                    "L": length,
                    "Gamma": GAMMA_SIGMA_18,
                    "sector": sector,
                    "K": K,
                    "chi": SIGMA_18_CHI,
                }
            )
    return {
        "run_id": "phase9-sigma1.8-published-field-z",
        "run_dir": str(run_dir),
        "settings": {
            "sigma": SIGMA_18,
            "Gamma": GAMMA_SIGMA_18,
            "field_role": "external_published_benchmark",
            "sizes": list(SIGMA_18_SIZES),
            "K": K,
            "chi": SIGMA_18_CHI,
            "alpha": ALPHA,
            "r_fit": R_FIT,
            "exact_zero_pruning": True,
            "approximate_mpo_compression": False,
            "automatic_chi_increase": False,
            "Gamma_search": False,
        },
        "cells": cells,
    }


def _state(summary: Mapping, sector: str) -> Mapping:
    if summary.get("status") != "success":
        raise ValueError(f"{sector} summary is not successful")
    try:
        return summary["direct"][sector]
    except KeyError as error:
        raise ValueError(f"summary is missing direct {sector} state") from error


def state_diagnostics(summary: Mapping, sector: str) -> dict:
    """Apply baseline gates without scheduling a refinement."""
    state = _state(summary, sector)
    energy = float(state["energy"])
    variance = float(state["variance"])
    discarded = float(state["discarded_weight"])
    sweeps = int(state["sweeps"])
    max_sweeps = int(summary.get("settings", {}).get("max_sweeps", 30))
    relative_variance = variance / max(energy * energy, 1.0)
    flags = []
    if relative_variance > RELATIVE_VARIANCE_LIMIT:
        flags.append("relative_variance")
    if discarded > DISCARDED_WEIGHT_LIMIT:
        flags.append("discarded_weight")
    if sweeps >= max_sweeps:
        flags.append("sweep_cap")
    return {
        "accepted": not flags,
        "flags": flags,
        "energy": energy,
        "relative_variance": relative_variance,
        "discarded_weight": discarded,
        "reached_chi": int(state["reached_chi"]),
        "sweeps": sweeps,
        "wall_seconds": float(state.get("wall_seconds", np.nan)),
        "max_sweeps": max_sweeps,
        "refinement_requested": False,
    }


def _gap_records(
    summaries: Mapping[tuple[int, float, str], Mapping],
    lengths: tuple[int, ...],
    gamma: float,
) -> tuple[list[dict], list[float]]:
    records = []
    gaps = []
    for length in lengths:
        even_summary = summaries[(length, gamma, "even")]
        odd_summary = summaries[(length, gamma, "odd")]
        even = state_diagnostics(even_summary, "even")
        odd = state_diagnostics(odd_summary, "odd")
        gap = odd["energy"] - even["energy"]
        if gap <= 0.0:
            raise ValueError(f"L={length} gap must be positive")
        gaps.append(gap)
        records.append(
            {
                "L": length,
                "Gamma": gamma,
                "E_even": even["energy"],
                "E_odd": odd["energy"],
                "gap": gap,
                "even_diagnostics": even,
                "odd_diagnostics": odd,
                "accepted": even["accepted"] and odd["accepted"],
            }
        )
    return records, gaps


def analyze_nn(
    summaries: Mapping[tuple[int, float, str], Mapping],
) -> dict:
    """Analyze fixed NN crossings and exact-field gap scaling."""
    cell_diagnostics = []
    for length in NN_SIZES:
        for gamma in GAMMA_NN:
            for sector in ("even", "odd"):
                diagnostic = state_diagnostics(
                    summaries[(length, gamma, sector)],
                    sector,
                )
                cell_diagnostics.append(
                    {
                        "L": length,
                        "Gamma": gamma,
                        "sector": sector,
                        **diagnostic,
                    }
                )
    crossings = []
    for small, large in zip(NN_SIZES[:-1], NN_SIZES[1:], strict=True):
        r_small = [
            float(summaries[(small, gamma, "even")]["raw_observables"]["r_xi"])
            for gamma in GAMMA_NN
        ]
        r_large = [
            float(summaries[(large, gamma, "even")]["raw_observables"]["r_xi"])
            for gamma in GAMMA_NN
        ]
        crossing = linear_crossing(GAMMA_NN, r_small, r_large)
        crossings.append(
            {
                "size_pair": f"{small}_{large}",
                "Gamma_x": crossing.gamma,
                "interpolation_indices": [
                    crossing.left_index,
                    crossing.right_index,
                ],
                "interpolation_points": [
                    GAMMA_NN[crossing.left_index],
                    GAMMA_NN[crossing.right_index],
                ],
            }
        )

    records, gaps = _gap_records(summaries, NN_SIZES, 1.0)
    adjacent = adjacent_effective_exponents(NN_SIZES, gaps)
    direct = direct_gap_power_law(NN_SIZES, gaps)
    return {
        "model": "nearest-neighbor-tfim",
        "cell_diagnostics": cell_diagnostics,
        "crossings": crossings,
        "crossing_resolution": 0.01,
        "gap_records": records,
        "gap_scaling": {
            "z_eff": adjacent,
            "direct": direct,
            "L_times_gap": [
                length * gap for length, gap in zip(NN_SIZES, gaps, strict=True)
            ],
        },
        "interpretation": "scaling_pipeline_validation_only",
        "precision_z_claim": False,
        "target": {"Gamma_c": 1.0, "z": 1.0},
    }


def analyze_mean_field(
    summaries: Mapping[tuple[int, float, str], Mapping],
    *,
    sigma: float,
    gamma: float,
) -> dict:
    """Analyze one fixed published-field mean-field gap benchmark."""
    matches = [
        item
        for item in MEAN_FIELD_BENCHMARKS
        if np.isclose(item["sigma"], sigma)
        and np.isclose(item["Gamma"], gamma)
    ]
    if len(matches) != 1:
        raise ValueError("unknown Phase 9 mean-field benchmark")
    benchmark = matches[0]
    records, gaps = _gap_records(
        summaries,
        MEAN_FIELD_SIZES,
        gamma,
    )
    return {
        "model": "periodic-long-range-tfim",
        "sigma": sigma,
        "Gamma": gamma,
        "field_role": "external_published_benchmark",
        "gap_records": records,
        "gap_scaling": {
            "z_eff": adjacent_effective_exponents(MEAN_FIELD_SIZES, gaps),
            "direct": direct_gap_power_law(MEAN_FIELD_SIZES, gaps),
            "L_to_expected_z_times_gap": [
                length ** benchmark["expected_z"] * gap
                for length, gap in zip(MEAN_FIELD_SIZES, gaps, strict=True)
            ],
        },
        "target": {
            "analytic_z": benchmark["expected_z"],
        },
        "reported_exponents": ["z"],
    }


def analyze_sigma18_z(
    summaries: Mapping[tuple[int, float, str], Mapping],
) -> dict:
    """Analyze the fixed published-field sigma=1.8 gap sequence."""
    records, gaps = _gap_records(
        summaries,
        SIGMA_18_SIZES,
        GAMMA_SIGMA_18,
    )
    adjacent = adjacent_effective_exponents(SIGMA_18_SIZES, gaps)
    power = sensitivity_regression(
        adjacent["values"],
        adjacent["effective_lengths"],
        "power",
    )
    log = sensitivity_regression(
        adjacent["values"],
        adjacent["effective_lengths"],
        "log",
    )
    return {
        "model": "periodic-long-range-tfim",
        "sigma": SIGMA_18,
        "Gamma": GAMMA_SIGMA_18,
        "field_role": "external_published_benchmark",
        "gap_records": records,
        "gap_scaling": {
            "z_eff": adjacent,
            "direct": direct_gap_power_law(SIGMA_18_SIZES, gaps),
            "correction_sensitivity": {
                "power": power,
                "log": log,
                "interpretation": (
                    "finite_size_sensitivity_not_statistical_model_selection"
                ),
            },
            "length_convention": "L_eff=sqrt(L1*L2)",
        },
        "published_comparison": {
            "source": "Shiratani-Todo arXiv:2305.14121",
            "z_power_approx": 0.93,
            "z_log_approx": 1.00,
            "role": "validation_comparison_only",
        },
        "precision_reproduction_claim": False,
    }


def published_gamma_comparison() -> dict:
    """Return the reused sigma=2 finite-size Table II comparison."""
    crossing = 1.4284112034302971
    published = 1.4208
    return {
        "sigma": 2.0,
        "Gamma_x_32_64": crossing,
        "broad_bracket": [1.40, 1.45],
        "crossing_resolution": 0.025,
        "published_Gamma_c": published,
        "published_uncertainty": 0.0002,
        "difference": crossing - published,
        "relative_difference": (crossing - published) / published,
        "chi_validation": {
            "maximum_R_xi_shift": 4.0e-6,
            "bracket_unchanged": True,
            "sign_structure_unchanged": True,
        },
        "classification": "finite_size_crossing_comparison",
        "exact_reproduction_claim": False,
    }
