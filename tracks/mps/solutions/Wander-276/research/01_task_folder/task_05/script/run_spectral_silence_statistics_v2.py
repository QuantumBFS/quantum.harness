#!/usr/bin/env python3
"""Simultaneous-band inference for spectral silence and geometric chaos."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from lgeth.statistics import (
    CurveBand,
    matrix_bootstrap_band,
    number_variance_matrix_curves,
    unfold_spectra,
)


VERSION = "v2"
REGISTERED_BOOTSTRAP_REPLICATES = 10_000
REGISTERED_SEED = 20260728220
RATIO_EDGES = np.linspace(0.0, 1.0, 61)
LENGTHS = np.linspace(0.25, 8.0, 32)
TAU_MIN = 0.25
TAU_MAX = 1.50


def _default_output(name: str) -> Path:
    return Path(__file__).resolve().parent / "output" / name


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def registered_compatibility_onset(
    grid: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    minimum: float,
    maximum: float,
) -> float | None:
    """Return the first point after which all registered bands contain zero."""

    values = np.asarray(grid, dtype=float)
    low = np.asarray(lower, dtype=float)
    high = np.asarray(upper, dtype=float)
    if values.ndim != 1 or low.shape != values.shape or high.shape != values.shape:
        raise ValueError("grid and confidence bounds must be matching vectors")
    if np.any(low > high):
        raise ValueError("lower confidence bound exceeds upper bound")
    indices = np.flatnonzero(
        (values >= float(minimum)) & (values <= float(maximum))
    )
    if indices.size == 0:
        raise ValueError("registered interval contains no grid points")
    compatible = (low[indices] <= 0.0) & (high[indices] >= 0.0)
    for offset, index in enumerate(indices):
        if bool(np.all(compatible[offset:])):
            return float(values[index])
    return None


def registered_compatibility_extent(
    grid: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    minimum: float,
    maximum: float,
) -> float | None:
    """Return the largest initial scale with uninterrupted compatibility."""

    values = np.asarray(grid, dtype=float)
    low = np.asarray(lower, dtype=float)
    high = np.asarray(upper, dtype=float)
    if values.ndim != 1 or low.shape != values.shape or high.shape != values.shape:
        raise ValueError("grid and confidence bounds must be matching vectors")
    indices = np.flatnonzero(
        (values >= float(minimum)) & (values <= float(maximum))
    )
    if indices.size == 0:
        raise ValueError("registered interval contains no grid points")
    compatible = (low[indices] <= 0.0) & (high[indices] >= 0.0)
    if not bool(compatible[0]):
        return None
    stop = 0
    while stop + 1 < compatible.size and bool(compatible[stop + 1]):
        stop += 1
    return float(values[indices[stop]])


def _partition_matrix_curves(
    spectra: np.ndarray,
    times: np.ndarray,
) -> np.ndarray:
    values = np.asarray(spectra, dtype=float)
    grid = np.asarray(times, dtype=float)
    if values.ndim != 2 or values.shape[1] < 2:
        raise ValueError("spectra must be a matrix with at least two levels")
    partition = np.empty(
        (values.shape[0], grid.size),
        dtype=np.complex128,
    )
    for start in range(0, values.shape[0], 512):
        stop = min(start + 512, values.shape[0])
        phases = np.exp(
            -2j
            * np.pi
            * values[start:stop, :, None]
            * grid[None, None, :]
        )
        partition[start:stop] = np.sum(phases, axis=1)
    mean_partition = np.mean(partition, axis=0)
    return (
        np.abs(partition) ** 2
        - np.abs(mean_partition)[None, :] ** 2
    ) / values.shape[1]


def _ratio_values(spectrum: np.ndarray) -> np.ndarray:
    ordered = np.sort(np.asarray(spectrum, dtype=float))
    trim = int(np.floor(0.15 * ordered.size))
    bulk = ordered[trim : ordered.size - trim if trim else ordered.size]
    gaps = np.diff(bulk)
    left = gaps[:-1]
    right = gaps[1:]
    denominator = np.maximum(left, right)
    scale = max(float(np.ptp(bulk)), 1.0)
    tolerance = 1e-11 * scale
    ratios = np.zeros_like(denominator)
    keep = denominator > tolerance
    ratios[keep] = (
        np.minimum(left[keep], right[keep]) / denominator[keep]
    )
    return ratios


def _ratio_matrix_curves(
    spectra: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(spectra, dtype=float)
    width = np.diff(RATIO_EDGES)
    curves = np.empty(
        (values.shape[0], RATIO_EDGES.size - 1),
        dtype=np.float32,
    )
    means = np.empty(values.shape[0], dtype=float)
    for matrix, spectrum in enumerate(values):
        ratios = _ratio_values(spectrum)
        counts, _ = np.histogram(ratios, bins=RATIO_EDGES)
        curves[matrix] = counts / (np.sum(counts) * width)
        means[matrix] = float(np.mean(ratios))
    return curves, means


def _curve_sets(
    spectra: np.ndarray,
    times: np.ndarray,
    include_number: bool,
) -> dict[str, np.ndarray]:
    unfolded = unfold_spectra(spectra, "ensemble_cdf")
    ratio, ratio_mean = _ratio_matrix_curves(spectra)
    result = {
        "form": _partition_matrix_curves(unfolded, times),
        "ratio": ratio,
        "ratio_mean": ratio_mean[:, None],
    }
    if include_number:
        result["number"] = number_variance_matrix_curves(
            unfolded,
            LENGTHS,
        )
    return result


def _reduced_units(
    curves: np.ndarray,
    groups: np.ndarray | None,
) -> np.ndarray:
    values = np.asarray(curves, dtype=float)
    if groups is None:
        return values
    labels = np.asarray(groups)
    if labels.shape != (values.shape[0],):
        raise ValueError("groups must provide one label per curve")
    return np.asarray(
        [
            np.mean(values[labels == label], axis=0)
            for label in np.unique(labels)
        ]
    )


def _independent_difference_band(
    first_curves: np.ndarray,
    second_curves: np.ndarray,
    replicates: int,
    seed: int,
    first_groups: np.ndarray | None = None,
    second_groups: np.ndarray | None = None,
) -> CurveBand:
    first = _reduced_units(first_curves, first_groups)
    second = _reduced_units(second_curves, second_groups)
    if first.shape[1] != second.shape[1]:
        raise ValueError("difference curves must share one grid")
    if first.shape[0] < 2 or second.shape[0] < 2:
        raise ValueError("each difference ensemble needs two units")
    first_mean = np.mean(first, axis=0)
    second_mean = np.mean(second, axis=0)
    mean = first_mean - second_mean
    first_centered = first - first_mean
    second_centered = second - second_mean
    covariance = (
        first_centered.T @ first_centered
        / (first.shape[0] * (first.shape[0] - 1))
        + second_centered.T @ second_centered
        / (second.shape[0] * (second.shape[0] - 1))
    )
    covariance = 0.5 * (covariance + covariance.T)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    cutoff = max(float(eigenvalues[-1]) * 1e-13, 0.0)
    keep = eigenvalues > cutoff
    factor = (
        eigenvectors[:, keep] * np.sqrt(eigenvalues[keep])[None, :]
    )
    rng = np.random.default_rng(int(seed))
    draws = mean + rng.normal(
        size=(int(replicates), int(np.count_nonzero(keep)))
    ) @ factor.T
    pointwise_lower, pointwise_upper = np.quantile(
        draws,
        (0.025, 0.975),
        axis=0,
    )
    standard_error = np.std(draws, axis=0, ddof=1)
    safe = np.maximum(standard_error, 1e-15)
    maximum = np.max(np.abs((draws - mean) / safe), axis=1)
    critical = float(np.quantile(maximum, 0.95))
    return CurveBand(
        mean=mean,
        lower=mean - critical * standard_error,
        upper=mean + critical * standard_error,
        pointwise_lower=pointwise_lower,
        pointwise_upper=pointwise_upper,
        standard_error=standard_error,
        critical_value=critical,
        replicates=int(replicates),
        units=int(first.shape[0] + second.shape[0]),
        method="independent_unit_gaussian_multiplier",
    )


def _store_band(
    prefix: str,
    band: CurveBand,
    output: dict[str, np.ndarray],
) -> None:
    output[f"{prefix}_mean"] = band.mean.astype(np.float32)
    output[f"{prefix}_lower"] = band.lower.astype(np.float32)
    output[f"{prefix}_upper"] = band.upper.astype(np.float32)
    output[f"{prefix}_pointwise_lower"] = (
        band.pointwise_lower.astype(np.float32)
    )
    output[f"{prefix}_pointwise_upper"] = (
        band.pointwise_upper.astype(np.float32)
    )
    output[f"{prefix}_standard_error"] = (
        band.standard_error.astype(np.float32)
    )


def run(
    output_json: Path,
    output_npz: Path,
    bootstrap_replicates: int = REGISTERED_BOOTSTRAP_REPLICATES,
) -> dict[str, Any]:
    """Run simultaneous-band inference for every v2 control."""

    started = time.perf_counter()
    draws = int(bootstrap_replicates)
    if draws < 500:
        raise ValueError("bootstrap_replicates must be at least 500")
    script_dir = Path(__file__).resolve().parent
    source_json_path = script_dir / "output" / "spectral_silence_v2.json"
    source_npz_path = script_dir / "output" / "spectral_silence_v2.npz"
    source_json = json.loads(
        source_json_path.read_text(encoding="utf-8")
    )
    source = np.load(source_npz_path, allow_pickle=False)
    if not source_json["all_checks_pass"]:
        raise RuntimeError("spectral-silence source audit failed")
    times = np.asarray(source["times"], dtype=float)
    analytic = np.asarray(source["jacobi_connected_D50"], dtype=float)
    structured_sets = _curve_sets(
        source["structured_spectra"],
        times,
        include_number=True,
    )
    physical_sets = _curve_sets(
        source["physical_test_spectra"],
        times,
        include_number=True,
    )
    haar_sets = _curve_sets(
        source["haar_spectra"],
        times,
        include_number=True,
    )
    output: dict[str, np.ndarray] = {
        "times": times.astype(np.float32),
        "ratio_centers": (
            0.5 * (RATIO_EDGES[:-1] + RATIO_EDGES[1:])
        ).astype(np.float32),
        "lengths": LENGTHS.astype(np.float32),
        "jacobi_connected_D50": analytic.astype(np.float32),
    }
    base_specs = (
        (
            "structured",
            structured_sets,
            source["structured_orbit_id"],
            0,
        ),
        (
            "physical",
            physical_sets,
            source["physical_seed_block"],
            20,
        ),
        ("haar", haar_sets, None, 40),
    )
    band_metadata: dict[str, Any] = {}
    base_bands: dict[str, dict[str, CurveBand]] = {}
    for label, sets, groups, offset in base_specs:
        base_bands[label] = {}
        band_metadata[label] = {}
        for curve_index, curve_name in enumerate(
            ("form", "ratio", "ratio_mean", "number")
        ):
            band = matrix_bootstrap_band(
                sets[curve_name],
                replicates=draws,
                seed=REGISTERED_SEED + offset + curve_index,
                groups=groups,
            )
            base_bands[label][curve_name] = band
            _store_band(f"{label}_{curve_name}", band, output)
            band_metadata[label][curve_name] = {
                "units": band.units,
                "method": band.method,
                "critical_value": band.critical_value,
            }
    physical_residual = CurveBand(
        mean=base_bands["physical"]["form"].mean - analytic,
        lower=base_bands["physical"]["form"].lower - analytic,
        upper=base_bands["physical"]["form"].upper - analytic,
        pointwise_lower=(
            base_bands["physical"]["form"].pointwise_lower - analytic
        ),
        pointwise_upper=(
            base_bands["physical"]["form"].pointwise_upper - analytic
        ),
        standard_error=base_bands["physical"]["form"].standard_error,
        critical_value=base_bands["physical"]["form"].critical_value,
        replicates=draws,
        units=base_bands["physical"]["form"].units,
        method="physical_minus_exact_finite_jacobi",
    )
    structured_residual = CurveBand(
        mean=base_bands["structured"]["form"].mean - analytic,
        lower=base_bands["structured"]["form"].lower - analytic,
        upper=base_bands["structured"]["form"].upper - analytic,
        pointwise_lower=(
            base_bands["structured"]["form"].pointwise_lower - analytic
        ),
        pointwise_upper=(
            base_bands["structured"]["form"].pointwise_upper - analytic
        ),
        standard_error=base_bands["structured"]["form"].standard_error,
        critical_value=base_bands["structured"]["form"].critical_value,
        replicates=draws,
        units=base_bands["structured"]["form"].units,
        method="structured_minus_exact_finite_jacobi",
    )
    _store_band("physical_form_residual", physical_residual, output)
    _store_band("structured_form_residual", structured_residual, output)
    number_residual = _independent_difference_band(
        physical_sets["number"],
        haar_sets["number"],
        replicates=draws,
        seed=REGISTERED_SEED + 60,
        first_groups=source["physical_seed_block"],
    )
    _store_band("physical_haar_number_residual", number_residual, output)
    tau_onset = registered_compatibility_onset(
        times,
        physical_residual.lower,
        physical_residual.upper,
        minimum=TAU_MIN,
        maximum=TAU_MAX,
    )
    length_extent = registered_compatibility_extent(
        LENGTHS,
        number_residual.lower,
        number_residual.upper,
        minimum=float(LENGTHS[0]),
        maximum=float(LENGTHS[-1]),
    )
    g_values = np.asarray(source["g_values"], dtype=float)
    g_count = g_values.size
    g_form_arrays = {
        name: np.empty((g_count, times.size), dtype=np.float32)
        for name in ("mean", "lower", "upper", "standard_error")
    }
    g_ratio_arrays = {
        name: np.empty(
            (g_count, RATIO_EDGES.size - 1),
            dtype=np.float32,
        )
        for name in ("mean", "lower", "upper", "standard_error")
    }
    g_ratio_scalar = {
        name: np.empty(g_count, dtype=np.float32)
        for name in ("mean", "lower", "upper")
    }
    g_tau_onset: list[float | None] = []
    for index, g in enumerate(g_values):
        sets = _curve_sets(
            source["g_spectra"][index],
            times,
            include_number=False,
        )
        groups = source["g_seed_block"][index]
        form_band = matrix_bootstrap_band(
            sets["form"],
            replicates=draws,
            seed=REGISTERED_SEED + 100 + 4 * index,
            groups=groups,
        )
        ratio_band = matrix_bootstrap_band(
            sets["ratio"],
            replicates=draws,
            seed=REGISTERED_SEED + 101 + 4 * index,
            groups=groups,
        )
        scalar_band = matrix_bootstrap_band(
            sets["ratio_mean"],
            replicates=draws,
            seed=REGISTERED_SEED + 102 + 4 * index,
            groups=groups,
        )
        for name in ("mean", "lower", "upper", "standard_error"):
            g_form_arrays[name][index] = getattr(form_band, name)
            g_ratio_arrays[name][index] = getattr(ratio_band, name)
        for name in ("mean", "lower", "upper"):
            g_ratio_scalar[name][index] = float(
                getattr(scalar_band, name)[0]
            )
        g_tau_onset.append(
            registered_compatibility_onset(
                times,
                form_band.lower - analytic,
                form_band.upper - analytic,
                minimum=TAU_MIN,
                maximum=TAU_MAX,
            )
        )
    for name, values in g_form_arrays.items():
        output[f"g_form_{name}"] = values
    for name, values in g_ratio_arrays.items():
        output[f"g_ratio_{name}"] = values
    for name, values in g_ratio_scalar.items():
        output[f"g_ratio_scalar_{name}"] = values
    output["g_values"] = g_values.astype(np.float32)
    alpha_values = np.asarray(source["alpha_values"], dtype=float)
    alpha_count = alpha_values.size
    energy_gap = {
        name: np.empty(alpha_count, dtype=np.float32)
        for name in ("mean", "lower", "upper")
    }
    energy_form = {
        name: np.empty((alpha_count, times.size), dtype=np.float32)
        for name in ("mean", "lower", "upper", "standard_error")
    }
    for index, alpha in enumerate(alpha_values):
        sets = _curve_sets(
            source["energy_spectra_alpha"][index],
            times,
            include_number=False,
        )
        gap_band = matrix_bootstrap_band(
            sets["ratio_mean"],
            replicates=draws,
            seed=REGISTERED_SEED + 200 + 3 * index,
        )
        form_band = matrix_bootstrap_band(
            sets["form"],
            replicates=draws,
            seed=REGISTERED_SEED + 201 + 3 * index,
        )
        for name in ("mean", "lower", "upper"):
            energy_gap[name][index] = float(getattr(gap_band, name)[0])
        for name in ("mean", "lower", "upper", "standard_error"):
            energy_form[name][index] = getattr(form_band, name)
    for name, values in energy_gap.items():
        output[f"energy_gap_ratio_{name}"] = values
    for name, values in energy_form.items():
        output[f"energy_form_{name}"] = values
    output["alpha_values"] = alpha_values.astype(np.float32)
    output["projector_distance_alpha"] = source[
        "projector_distance_alpha"
    ]
    output["curvature_error_alpha"] = source["curvature_error_alpha"]
    output["rank_D"] = source["rank_D"]
    output["rank_interior"] = source["rank_interior"]
    output["rank_atom_each"] = source["rank_atom_each"]
    output["rank_physical_connected_full"] = source[
        "rank_physical_connected_full"
    ]
    output["rank_reference_connected_full"] = source[
        "rank_reference_connected_full"
    ]
    compatible_g_indices = [
        index
        for index, onset in enumerate(g_tau_onset)
        if onset is not None
        and np.count_nonzero(
            (times >= onset) & (times <= TAU_MAX)
        )
        >= 8
    ]
    first_compatible_g = (
        float(g_values[compatible_g_indices[0]])
        if compatible_g_indices
        else None
    )
    haar_ratio_lower = float(
        base_bands["haar"]["ratio_mean"].lower[0]
    )
    haar_ratio_upper = float(
        base_bands["haar"]["ratio_mean"].upper[0]
    )
    local_compatible_indices = [
        index
        for index in range(g_count)
        if float(g_ratio_scalar["upper"][index]) >= haar_ratio_lower
        and float(g_ratio_scalar["lower"][index]) <= haar_ratio_upper
    ]
    first_local_g = (
        float(g_values[local_compatible_indices[0]])
        if local_compatible_indices
        else None
    )
    tau_index = int(np.argmin(np.abs(times - 0.5)))
    length_index = -1
    structured_rejects = bool(
        structured_residual.lower[tau_index] > 0.0
        or structured_residual.upper[tau_index] < 0.0
    )
    physical_window = bool(
        tau_onset is not None
        and np.count_nonzero(
            (times >= tau_onset) & (times <= TAU_MAX)
        )
        >= 8
    )
    long_range_resolved = bool(
        number_residual.lower[length_index] > 0.0
        or number_residual.upper[length_index] < 0.0
    )
    spectral_separated = bool(
        energy_gap["upper"][0] < energy_gap["lower"][-1]
    )
    checks = {
        "source_artifact_passes": bool(source_json["all_checks_pass"]),
        "structured_control_rejects_jacobi": structured_rejects,
        "physical_has_registered_jacobi_window": physical_window,
        "geometry_axis_crossover_resolved": (
            first_compatible_g is not None
        ),
        "local_to_ramp_hierarchy_resolved": bool(
            first_local_g is not None
            and first_compatible_g is not None
            and first_local_g < first_compatible_g
        ),
        "spectral_axis_confidence_separated": spectral_separated,
        "fixed_projector_invariance_retained": bool(
            np.max(source["projector_distance_alpha"]) < 1e-12
            and np.max(source["curvature_error_alpha"]) < 1e-12
        ),
        "long_range_memory_resolved": long_range_resolved,
        "atom_plateau_data_retained": bool(
            int(source["rank_atom_each"][-1]) == 120
            and abs(
                float(
                    source["rank_interior"][-1]
                    / source["rank_D"][-1]
                )
                - 0.7
            )
            < 1e-12
        ),
    }
    result = {
        "schema_version": 2,
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": {
            "json": _sha256(source_json_path),
            "npz": _sha256(source_npz_path),
        },
        "bootstrap_replicates": draws,
        "registered_windows": {
            "tau_minimum": TAU_MIN,
            "tau_maximum": TAU_MAX,
            "number_minimum": float(LENGTHS[0]),
            "number_maximum": float(LENGTHS[-1]),
        },
        "outcomes": {
            "physical_tau_compatibility_onset": tau_onset,
            "number_variance_compatibility_extent": length_extent,
            "g_tau_compatibility_onsets": g_tau_onset,
            "first_g_with_registered_jacobi_window": first_compatible_g,
            "first_g_with_haar_gap_ratio_interval": first_local_g,
            "haar_gap_ratio_interval": {
                "mean": float(
                    base_bands["haar"]["ratio_mean"].mean[0]
                ),
                "lower": haar_ratio_lower,
                "upper": haar_ratio_upper,
            },
            "tau_0p5": {
                "structured": float(
                    base_bands["structured"]["form"].mean[tau_index]
                ),
                "physical": float(
                    base_bands["physical"]["form"].mean[tau_index]
                ),
                "haar": float(
                    base_bands["haar"]["form"].mean[tau_index]
                ),
                "analytic_jacobi": float(analytic[tau_index]),
            },
            "number_variance_L8_residual": {
                "mean": float(number_residual.mean[length_index]),
                "lower": float(number_residual.lower[length_index]),
                "upper": float(number_residual.upper[length_index]),
            },
            "energy_gap_ratio_endpoints": {
                "poisson": float(energy_gap["mean"][0]),
                "poisson_lower": float(energy_gap["lower"][0]),
                "poisson_upper": float(energy_gap["upper"][0]),
                "gue": float(energy_gap["mean"][-1]),
                "gue_lower": float(energy_gap["lower"][-1]),
                "gue_upper": float(energy_gap["upper"][-1]),
            },
        },
        "band_metadata": band_metadata,
        "checks": checks,
        "all_checks_pass": bool(all(checks.values())),
        "runtime_seconds": time.perf_counter() - started,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_npz.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    np.savez_compressed(output_npz, **output)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-json",
        type=Path,
        default=_default_output(
            "spectral_silence_statistics_v2.json"
        ),
    )
    parser.add_argument(
        "--output-npz",
        type=Path,
        default=_default_output(
            "spectral_silence_statistics_v2.npz"
        ),
    )
    parser.add_argument(
        "--bootstrap-replicates",
        type=int,
        default=REGISTERED_BOOTSTRAP_REPLICATES,
    )
    args = parser.parse_args()
    result = run(
        args.output_json,
        args.output_npz,
        bootstrap_replicates=args.bootstrap_replicates,
    )
    print(json.dumps(result, indent=2))
    if not result["all_checks_pass"]:
        raise SystemExit("spectral-silence statistical audit failed")


if __name__ == "__main__":
    main()
