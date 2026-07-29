"""Pure planning and analysis rules for the Phase 7 crossover scan."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np


SIGMAS = (1.50, 1.60, 1.70, 1.75, 1.80, 1.90, 2.00)
SIZES = (32, 64)
EXPLORATION_K = 24
EXPLORATION_CHI = 64
ALPHA = 0.5
R_FIT = 2048


def broad_gamma_grid() -> np.ndarray:
    """Return the immutable common first-pass Gamma grid."""
    return np.arange(120, 191, 5, dtype=float) / 100.0


def grid_hash(values: Sequence[float]) -> str:
    """Hash an ordered numeric grid using canonical compact JSON."""
    payload = json.dumps(
        [float(value) for value in values],
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _fit_for_sigma(fit_records: Mapping[str, Mapping], sigma: float) -> dict:
    key = f"{sigma:.2f}"
    if key not in fit_records:
        raise ValueError(f"fit records missing sigma={key}")
    fit = dict(fit_records[key])
    expected = {
        "sigma": sigma,
        "K": EXPLORATION_K,
        "alpha": ALPHA,
        "r_fit": R_FIT,
    }
    for field, value in expected.items():
        if fit.get(field) != value:
            raise ValueError(
                f"fit records {key} {field} mismatch: "
                f"{fit.get(field)!r} != {value!r}"
            )
    for field in ("path", "fit_hash", "coefficient_hash"):
        if not fit.get(field):
            raise ValueError(f"fit records {key} missing {field}")
    return fit


def build_broad_spec(
    fit_records: Mapping[str, Mapping],
    output_dir: str | Path,
) -> dict:
    """Build the immutable, even-sector broad-scan specification."""
    gammas = broad_gamma_grid()
    gamma_hash = grid_hash(gammas)
    fits = {
        f"{sigma:.2f}": _fit_for_sigma(fit_records, sigma)
        for sigma in SIGMAS
    }
    cells = []
    for sigma in SIGMAS:
        fit = fits[f"{sigma:.2f}"]
        for length in SIZES:
            for gamma in gammas:
                cell_id = (
                    f"sigma{sigma:.2f}_L{length}_Gamma{gamma:.2f}"
                    f"_even_K{EXPLORATION_K}_chi{EXPLORATION_CHI}"
                )
                cells.append(
                    {
                        "cell_id": cell_id,
                        "params": {
                            "sigma": sigma,
                            "L": length,
                            "Gamma": float(gamma),
                            "sector": "even",
                        },
                        "sigma": sigma,
                        "L": length,
                        "Gamma": float(gamma),
                        "sector": "even",
                        "K": EXPLORATION_K,
                        "chi": EXPLORATION_CHI,
                        "fit_hash": fit["fit_hash"],
                        "coefficient_hash": fit["coefficient_hash"],
                        "grid_hash": gamma_hash,
                        "status": "pending",
                    }
                )
    return {
        "run_id": "phase7-crossover-broad",
        "run_dir": str(Path(output_dir)),
        "axes": {
            "sigma": list(SIGMAS),
            "L": list(SIZES),
            "Gamma": gammas.tolist(),
        },
        "settings": {
            "K": EXPLORATION_K,
            "chi": EXPLORATION_CHI,
            "alpha": ALPHA,
            "r_fit": R_FIT,
            "sector": "even",
            "gamma_grid_hash": gamma_hash,
            "exact_zero_pruning": True,
            "approximate_mpo_compression": False,
            "adaptive_gamma": False,
        },
        "provenance": {"fits": fits},
        "cells": cells,
    }


def quality_flags(summary: Mapping) -> list[dict]:
    """Return deterministic requests for selective chi=128 validation."""
    flags: list[dict] = []
    if summary.get("status") != "success" or summary.get("converged") is False:
        flags.append({"code": "dmrg_nonconverged"})
    direct = summary.get("direct", {})
    for sector, state in direct.items():
        energy = float(state.get("energy", np.nan))
        variance = float(state.get("variance", np.nan))
        relative = variance / max(energy * energy, 1.0)
        if not np.isfinite(relative) or relative > 1.0e-10:
            flags.append(
                {
                    "code": "relative_variance",
                    "sector": sector,
                    "value": relative,
                    "threshold": 1.0e-10,
                }
            )
        discarded = float(state.get("discarded_weight", np.nan))
        if not np.isfinite(discarded) or discarded > 1.0e-8:
            flags.append(
                {
                    "code": "discarded_weight",
                    "sector": sector,
                    "value": discarded,
                    "threshold": 1.0e-8,
                }
            )
        sweeps = state.get("sweeps")
        max_sweeps = summary.get("settings", {}).get("max_sweeps")
        if max_sweeps is not None and sweeps is not None and sweeps >= max_sweeps:
            flags.append(
                {
                    "code": "sweep_cap_reached",
                    "sector": sector,
                    "value": sweeps,
                    "threshold": max_sweeps,
                }
            )
    raw = summary.get("raw_observables", {})
    ratio_values = [
        float(raw.get(field, np.nan))
        for field in ("r_xi", "xi", "s_zero", "s_k_min")
    ]
    if (
        not all(np.isfinite(value) for value in ratio_values)
        or ratio_values[2] < ratio_values[3]
    ):
        flags.append(
            {
                "code": "invalid_second_moment",
                "values": {
                    field: raw.get(field)
                    for field in ("r_xi", "xi", "s_zero", "s_k_min")
                },
            }
        )
    if "even" in direct and "odd" in direct:
        gap = float(direct["odd"]["energy"]) - float(direct["even"]["energy"])
        reported = float(raw.get("gap", gap))
        if not np.isfinite(gap) or gap <= 0.0 or reported <= 0.0:
            flags.append({"code": "nonpositive_gap", "value": reported})
    return flags


def _manifest_lookup(
    manifests: Mapping[str, Mapping],
    *,
    sigma: float,
) -> dict[tuple[int, float], dict]:
    lookup = {}
    for manifest in manifests.values():
        settings = manifest.get("settings", {})
        manifest_sigma = settings.get("sigma")
        if manifest_sigma is None or not np.isclose(float(manifest_sigma), sigma):
            continue
        length = settings.get("length", settings.get("L"))
        gamma = settings.get("gamma", settings.get("Gamma"))
        if length is not None and gamma is not None:
            lookup[(int(length), float(gamma))] = dict(manifest)
    return lookup


def _brackets(gammas: Sequence[float], differences: Sequence[float]) -> list:
    found = []
    values = np.asarray(differences, dtype=float)
    for index in np.flatnonzero(values == 0.0):
        index = int(index)
        left = max(0, index - 1)
        right = min(len(values) - 1, index + 1)
        if left != right:
            found.append((left, index) if index > 0 else (index, right))
    for index in range(len(values) - 1):
        if values[index] * values[index + 1] < 0.0:
            found.append((index, index + 1))
    return sorted(set(found))


def decide_refinement(
    sigma: float,
    broad_spec: Mapping,
    manifests: Mapping[str, Mapping],
) -> dict:
    """Select a unique observed broad bracket without extending the grid."""
    gammas = [float(value) for value in broad_spec["axes"]["Gamma"]]
    lookup = _manifest_lookup(manifests, sigma=float(sigma))
    differences = []
    missing = []
    for gamma in gammas:
        small = lookup.get((32, gamma))
        large = lookup.get((64, gamma))
        if (
            small is None
            or large is None
            or small.get("status") != "success"
            or large.get("status") != "success"
        ):
            missing.append(gamma)
            continue
        differences.append(
            float(small["raw_observables"]["r_xi"])
            - float(large["raw_observables"]["r_xi"])
        )
    base = {
        "sigma": float(sigma),
        "broad_grid": gammas,
        "grid_hash": broad_spec["settings"]["gamma_grid_hash"],
    }
    if missing:
        return {**base, "status": "incomplete", "missing_gamma": missing}
    base["differences"] = differences
    candidates = _brackets(gammas, differences)
    if not candidates:
        return {**base, "status": "unresolved_no_bracket"}
    if len(candidates) != 1:
        return {
            **base,
            "status": "unresolved_multiple_brackets",
            "candidate_brackets": [
                [gammas[left], gammas[right]] for left, right in candidates
            ],
        }
    left, right = candidates[0]
    bracket = [gammas[left], gammas[right]]
    ticks = np.arange(
        int(round(100 * bracket[0])),
        int(round(100 * bracket[1])) + 1,
        1,
    )
    return {
        **base,
        "status": "ready",
        "broad_bracket": bracket,
        "refinement_grid": (ticks / 100.0).tolist(),
    }


def finalize_crossing(
    decision: Mapping,
    manifests: Mapping[str, Mapping],
) -> dict:
    """Resolve the unique refined crossing and record grid resolution."""
    if decision.get("status") != "ready":
        return dict(decision)
    gammas = [float(value) for value in decision["refinement_grid"]]
    lookup = _manifest_lookup(manifests, sigma=float(decision["sigma"]))
    differences = []
    for gamma in gammas:
        small = lookup.get((32, gamma))
        large = lookup.get((64, gamma))
        if (
            small is None
            or large is None
            or small.get("status") != "success"
            or large.get("status") != "success"
        ):
            return {
                **decision,
                "status": "incomplete",
                "missing_refined_gamma": gamma,
            }
        differences.append(
            float(small["raw_observables"]["r_xi"])
            - float(large["raw_observables"]["r_xi"])
        )
    candidates = _brackets(gammas, differences)
    if len(candidates) != 1:
        status = (
            "unresolved_no_bracket"
            if not candidates
            else "unresolved_multiple_brackets"
        )
        return {**decision, "status": status, "refined_differences": differences}
    left, right = candidates[0]
    gamma_left, gamma_right = gammas[left], gammas[right]
    d_left, d_right = differences[left], differences[right]
    if d_right == d_left:
        return {**decision, "status": "unresolved_no_bracket"}
    fraction = -d_left / (d_right - d_left)
    crossing = gamma_left + fraction * (gamma_right - gamma_left)
    return {
        **decision,
        "status": "crossing_resolved",
        "refined_differences": differences,
        "interpolation_points": [gamma_left, gamma_right],
        "interpolation_differences": [d_left, d_right],
        "interpolation_fraction": float(fraction),
        "Gamma_x": float(crossing),
        "delta_gamma_grid": 0.5 * (gamma_right - gamma_left),
    }


def build_gap_spec(
    decisions: Sequence[Mapping],
    output_dir: str | Path,
) -> dict:
    """Schedule odd sectors only at resolved interpolation endpoints."""
    cells = []
    for decision in decisions:
        if decision.get("status") != "crossing_resolved":
            continue
        sigma = float(decision["sigma"])
        for length in SIZES:
            for gamma in decision["interpolation_points"]:
                cells.append(
                    {
                        "cell_id": (
                            f"sigma{sigma:.2f}_L{length}_Gamma{gamma:.2f}"
                            f"_odd_K{EXPLORATION_K}_chi{EXPLORATION_CHI}"
                        ),
                        "sigma": sigma,
                        "L": length,
                        "Gamma": float(gamma),
                        "sector": "odd",
                        "K": EXPLORATION_K,
                        "chi": EXPLORATION_CHI,
                        "status": "pending",
                    }
                )
    return {
        "run_id": "phase7-crossover-gaps",
        "run_dir": str(Path(output_dir)),
        "settings": {
            "K": EXPLORATION_K,
            "chi": EXPLORATION_CHI,
            "exact_zero_pruning": True,
            "approximate_mpo_compression": False,
        },
        "cells": cells,
    }


def estimate_scan_cost(
    timing_records: Sequence[Mapping],
    broad_spec: Mapping,
) -> dict:
    """Estimate serial local cost from measured chi=128 records."""
    grouped: dict[tuple[int, str], list[Mapping]] = {}
    for record in timing_records:
        key = (int(record["L"]), str(record["sector"]))
        grouped.setdefault(key, []).append(record)
    required = {(length, sector) for length in SIZES for sector in ("even", "odd")}
    if not required.issubset(grouped):
        missing = sorted(required.difference(grouped))
        raise ValueError(f"calibration records missing {missing}")
    for records in grouped.values():
        for record in records:
            if (
                int(record.get("chi", 0)) != 128
                or float(record.get("wall_seconds", 0.0)) <= 0.0
                or float(record.get("peak_memory_gib", 0.0)) <= 0.0
            ):
                raise ValueError(
                    "calibration chi must be 128 and timing/memory must be positive"
                )
    time_factor = (EXPLORATION_CHI / 128.0) ** 3
    memory_factor = (EXPLORATION_CHI / 128.0) ** 2
    calibrated = {}
    for key, records in sorted(grouped.items()):
        length, sector = key
        calibrated[f"L{length}_{sector}"] = {
            "samples": len(records),
            "median_wall_seconds_chi128": float(
                np.median([float(record["wall_seconds"]) for record in records])
            ),
            "estimated_wall_seconds_chi64": float(
                np.median([float(record["wall_seconds"]) for record in records])
                * time_factor
            ),
            "median_peak_memory_gib_chi128": float(
                np.median(
                    [float(record["peak_memory_gib"]) for record in records]
                )
            ),
            "estimated_peak_memory_gib_chi64": float(
                np.median(
                    [float(record["peak_memory_gib"]) for record in records]
                )
                * memory_factor
            ),
            "paths": [str(record["path"]) for record in records],
            "code_hashes": sorted(
                {str(record["code_hash"]) for record in records}
            ),
            "hardware": [record["hardware"] for record in records],
        }
    even_per_gamma = sum(
        calibrated[f"L{length}_even"]["estimated_wall_seconds_chi64"]
        for length in SIZES
    )
    odd_per_gamma = sum(
        calibrated[f"L{length}_odd"]["estimated_wall_seconds_chi64"]
        for length in SIZES
    )
    broad_cells = len(broad_spec["cells"])
    broad_seconds = len(SIGMAS) * len(broad_gamma_grid()) * even_per_gamma
    refinement_new_cells = len(SIGMAS) * len(SIZES) * 4
    refinement_seconds = len(SIGMAS) * 4 * even_per_gamma
    gap_cells = len(SIGMAS) * len(SIZES) * 2
    gap_seconds = len(SIGMAS) * 2 * odd_per_gamma
    central = broad_seconds + refinement_seconds + gap_seconds
    safety_factor = 2.0
    peak_memory = max(
        item["estimated_peak_memory_gib_chi64"]
        for item in calibrated.values()
    )
    return {
        "basis": "measured local chi=128 medians scaled to chi=64",
        "scaling": {
            "time_formula": "(64/128)^3",
            "memory_formula": "(64/128)^2",
            "time_chi_factor": time_factor,
            "memory_chi_factor": memory_factor,
        },
        "calibration": calibrated,
        "stages": {
            "broad": {
                "cells": broad_cells,
                "central_wall_seconds": broad_seconds,
            },
            "refinement": {
                "maximum_new_even_cells": refinement_new_cells,
                "central_wall_seconds": refinement_seconds,
            },
            "gaps": {
                "maximum_odd_cells": gap_cells,
                "central_wall_seconds": gap_seconds,
            },
        },
        "combined": {
            "maximum_cells": broad_cells + refinement_new_cells + gap_cells,
            "central_wall_seconds": central,
            "safety_wall_seconds": safety_factor * central,
            "estimated_peak_memory_gib": peak_memory,
        },
        "safety_factor": safety_factor,
    }
