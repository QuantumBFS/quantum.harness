#!/usr/bin/env python3
"""Matrix-level inference for the large-scale Geometric-ETH ensembles."""

from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy.ndimage import gaussian_filter1d

from lgeth.statistics import (
    bulk_gap_ratio_per_spectrum,
    fit_size_models,
    matrix_bootstrap_band,
    number_variance_matrix_curves,
    unfold_spectra,
)


VERSION = "v1"
BOOTSTRAP_REPLICATES = 10_000
DENSITY_GRID = np.linspace(-1.05, 1.05, 301)
KDE_BANDWIDTH = 0.025
RATIO_EDGES = np.linspace(0.0, 1.0, 61)
LENGTHS = np.linspace(0.25, 8.0, 32)
FORM_FACTOR_TIMES = np.linspace(0.0, 3.0, 61)


def _kde_matrix_curves(
    spectra: np.ndarray,
    grid: np.ndarray,
    bandwidth: float,
) -> np.ndarray:
    values = np.asarray(spectra, dtype=float)
    result = np.empty((values.shape[0], grid.size), dtype=np.float32)
    normalization = bandwidth * np.sqrt(2.0 * np.pi)
    for start in range(0, values.shape[0], 256):
        stop = min(start + 256, values.shape[0])
        difference = (
            grid[None, :, None] - values[start:stop, None, :]
        ) / bandwidth
        curves = np.mean(
            np.exp(-0.5 * difference * difference),
            axis=2,
        ) / normalization
        integral = np.trapezoid(curves, grid, axis=1)
        result[start:stop] = curves / integral[:, None]
    return result


def _ratio_matrix_curves(spectra: np.ndarray) -> np.ndarray:
    values = np.sort(np.asarray(spectra, dtype=float), axis=1)
    curves = np.empty(
        (values.shape[0], RATIO_EDGES.size - 1),
        dtype=np.float32,
    )
    width = np.diff(RATIO_EDGES)
    for matrix, levels in enumerate(values):
        trim = int(np.floor(0.15 * levels.size))
        bulk = levels[trim : levels.size - trim]
        gaps = np.diff(bulk)
        ratios = np.minimum(gaps[:-1], gaps[1:]) / np.maximum(
            gaps[:-1],
            gaps[1:],
        )
        counts, _ = np.histogram(ratios, bins=RATIO_EDGES)
        curves[matrix] = counts / (np.sum(counts) * width)
    return curves


def _rigidity_from_number(
    number_curves: np.ndarray,
    lengths: np.ndarray,
) -> np.ndarray:
    result = np.empty_like(number_curves)
    extended_x = np.concatenate([[0.0], lengths])
    for column, length in enumerate(lengths):
        x = extended_x[: column + 2]
        values = np.concatenate(
            [
                np.zeros((number_curves.shape[0], 1)),
                number_curves[:, : column + 1],
            ],
            axis=1,
        )
        kernel = length**3 - 2.0 * length * length * x + x**3
        result[:, column] = (
            2.0
            / length**4
            * np.trapezoid(values * kernel[None, :], x, axis=1)
        )
    return result


def _form_factor_matrix_curves(
    unfolded: np.ndarray,
    times: np.ndarray,
) -> np.ndarray:
    levels = unfolded.shape[1]
    partition = np.empty(
        (unfolded.shape[0], times.size),
        dtype=np.complex128,
    )
    for start in range(0, unfolded.shape[0], 512):
        stop = min(start + 512, unfolded.shape[0])
        phases = np.exp(
            -2j
            * np.pi
            * unfolded[start:stop, :, None]
            * times[None, None, :]
        )
        partition[start:stop] = np.sum(phases, axis=1)
    mean_partition = np.mean(partition, axis=0)
    return (
        np.abs(partition) ** 2
        - np.abs(mean_partition)[None, :] ** 2
    ) / levels


def _band_arrays(prefix: str, band, output: dict[str, np.ndarray]) -> None:
    output[f"{prefix}_mean"] = band.mean.astype(np.float32)
    output[f"{prefix}_lower"] = band.lower.astype(np.float32)
    output[f"{prefix}_upper"] = band.upper.astype(np.float32)
    output[f"{prefix}_pointwise_lower"] = band.pointwise_lower.astype(
        np.float32
    )
    output[f"{prefix}_pointwise_upper"] = band.pointwise_upper.astype(
        np.float32
    )
    output[f"{prefix}_standard_error"] = band.standard_error.astype(
        np.float32
    )


def _curve_suite(
    spectra: np.ndarray,
    seed: int,
    output: dict[str, np.ndarray],
    prefix: str,
    groups: np.ndarray | None,
    replicates: int,
) -> dict[str, Any]:
    density_curves = _kde_matrix_curves(
        spectra,
        DENSITY_GRID,
        KDE_BANDWIDTH,
    )
    ratio_curves = _ratio_matrix_curves(spectra)
    unfolded = unfold_spectra(spectra, "ensemble_cdf")
    number_curves = number_variance_matrix_curves(unfolded, LENGTHS)
    rigidity_curves = _rigidity_from_number(number_curves, LENGTHS)
    form_curves = _form_factor_matrix_curves(
        unfolded,
        FORM_FACTOR_TIMES,
    )
    moments = np.column_stack(
        [np.mean(spectra.astype(float) ** order, axis=1) for order in (2,4,6,8)]
    )
    curve_sets = {
        "density": density_curves,
        "ratio": ratio_curves,
        "number": number_curves,
        "rigidity": rigidity_curves,
        "form_factor": form_curves,
        "moments": moments,
    }
    metadata: dict[str, Any] = {}
    for offset, (name, curves) in enumerate(curve_sets.items()):
        band = matrix_bootstrap_band(
            curves,
            replicates=replicates,
            seed=seed + offset,
            groups=groups,
        )
        _band_arrays(f"{prefix}_{name}", band, output)
        metadata[name] = {
            "method": band.method,
            "units": band.units,
            "replicates": band.replicates,
            "critical_value": band.critical_value,
        }
    return metadata


def _smoothed_density(
    spectra: np.ndarray,
    bandwidth: float,
) -> np.ndarray:
    fine_edges = np.linspace(-1.1, 1.1, 2202)
    density, _ = np.histogram(
        spectra.ravel(),
        bins=fine_edges,
        density=True,
    )
    centers = 0.5 * (fine_edges[:-1] + fine_edges[1:])
    spacing = centers[1] - centers[0]
    smoothed = gaussian_filter1d(
        density,
        bandwidth / spacing,
        mode="constant",
    )
    interpolated = np.interp(DENSITY_GRID, centers, smoothed)
    return interpolated / np.trapezoid(interpolated, DENSITY_GRID)


def _sensitivity(
    physical: np.ndarray,
    haar: np.ndarray,
    deformed: np.ndarray,
) -> dict[str, Any]:
    bandwidth_results = {}
    for bandwidth in (0.015, 0.02, 0.025, 0.035, 0.05):
        first = _smoothed_density(physical, bandwidth)
        second = _smoothed_density(haar, bandwidth)
        third = _smoothed_density(deformed, bandwidth)
        bandwidth_results[str(bandwidth)] = {
            "physical_haar_l1": float(
                np.trapezoid(np.abs(first - second), DENSITY_GRID)
            ),
            "physical_deformed_l1": float(
                np.trapezoid(np.abs(first - third), DENSITY_GRID)
            ),
        }
    bulk_results = {}
    for fraction in (0.5, 0.6, 0.7, 0.8, 0.9):
        bulk_results[str(fraction)] = {
            "physical": float(
                np.mean(
                    bulk_gap_ratio_per_spectrum(
                        physical,
                        bulk_fraction=fraction,
                    )
                )
            ),
            "haar": float(
                np.mean(
                    bulk_gap_ratio_per_spectrum(
                        haar,
                        bulk_fraction=fraction,
                    )
                )
            ),
            "deformed": float(
                np.mean(
                    bulk_gap_ratio_per_spectrum(
                        deformed,
                        bulk_fraction=fraction,
                    )
                )
            ),
        }
    unfolding_results = {}
    for method in ("ensemble_cdf", "polynomial"):
        unfolding_results[method] = {}
        for name, spectra in (
            ("physical", physical),
            ("haar", haar),
            ("deformed", deformed),
        ):
            unfolded = unfold_spectra(spectra, method)
            unfolding_results[method][name] = float(
                np.mean(bulk_gap_ratio_per_spectrum(unfolded))
            )
    binning_results = {}
    for bins in (30, 50, 70):
        edges = np.linspace(0.0, 1.0, bins + 1)
        distributions = {}
        for name, spectra in (
            ("physical", physical),
            ("haar", haar),
            ("deformed", deformed),
        ):
            ordered = np.sort(spectra, axis=1)
            gaps = np.diff(ordered, axis=1)
            ratios = np.minimum(gaps[:, :-1], gaps[:, 1:]) / np.maximum(
                gaps[:, :-1], gaps[:, 1:]
            )
            distributions[name], _ = np.histogram(
                ratios,
                bins=edges,
                density=True,
            )
        binning_results[str(bins)] = {
            "physical_haar_l1": float(
                np.sum(
                    np.abs(
                        distributions["physical"] - distributions["haar"]
                    )
                    * np.diff(edges)
                )
            ),
            "physical_deformed_l1": float(
                np.sum(
                    np.abs(
                        distributions["physical"]
                        - distributions["deformed"]
                    )
                    * np.diff(edges)
                )
            ),
        }
    return {
        "bandwidth": bandwidth_results,
        "bulk_fraction": bulk_results,
        "unfolding": unfolding_results,
        "ratio_binning": binning_results,
    }


def _scaling_inference(
    scaling_json: dict[str, Any],
    scaling_arrays: Any,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    cases = scaling_json["cases"]
    D = np.asarray([case["D"] for case in cases], dtype=float)
    M = np.asarray([case["M"] for case in cases], dtype=float)
    density = np.asarray(
        [case["interior_density_l1"] for case in cases],
        dtype=float,
    )
    gap = np.asarray(
        [case["gap_ratio_difference"] for case in cases],
        dtype=float,
    )
    participation = np.asarray(
        [case["mean_participation"] for case in cases],
        dtype=float,
    )
    density_se = np.empty(D.size)
    gap_se = np.empty(D.size)
    participation_se = np.empty(D.size)
    for index, case in enumerate(cases):
        n = case["n"]
        labels = scaling_arrays[f"n{n}_seed_block"]
        root = scaling_arrays[f"n{n}_interior_spectra"]
        reference = scaling_arrays[f"n{n}_reference_interior_spectra"]
        root_ratio = scaling_arrays[f"n{n}_gap_ratios"]
        reference_ratio = scaling_arrays[f"n{n}_reference_gap_ratios"]
        root_participation = scaling_arrays[f"n{n}_participation"]
        block_density = []
        block_gap = []
        block_participation = []
        edges = np.linspace(-1.0, 1.0, 161)
        reference_density, _ = np.histogram(
            reference.ravel(),
            bins=edges,
            density=True,
        )
        for block in np.unique(labels):
            keep = labels == block
            block_hist, _ = np.histogram(
                root[keep].ravel(),
                bins=edges,
                density=True,
            )
            block_density.append(
                np.sum(np.abs(block_hist - reference_density) * np.diff(edges))
            )
            block_gap.append(
                abs(
                    float(np.mean(root_ratio[keep]))
                    - float(np.mean(reference_ratio))
                )
            )
            block_participation.append(
                float(np.mean(root_participation[keep]))
            )
        density_se[index] = np.std(block_density, ddof=1) / np.sqrt(
            len(block_density)
        )
        gap_se[index] = np.std(block_gap, ddof=1) / np.sqrt(len(block_gap))
        participation_se[index] = np.std(
            block_participation,
            ddof=1,
        ) / np.sqrt(len(block_participation))
    density_se = np.maximum(density_se, 1e-4)
    gap_se = np.maximum(gap_se, 1e-4)
    participation_se = np.maximum(participation_se, 1e-5)
    fits = {
        "density_l1": fit_size_models(D, density, density_se),
        "gap_ratio_difference": fit_size_models(D, gap, gap_se),
        "participation_deficit": fit_size_models(
            D,
            1.0 - participation,
            participation_se,
        ),
    }
    arrays = {
        "scaling_D": D.astype(np.float32),
        "scaling_M": M.astype(np.float32),
        "scaling_density_l1": density.astype(np.float32),
        "scaling_density_se": density_se.astype(np.float32),
        "scaling_gap_difference": gap.astype(np.float32),
        "scaling_gap_se": gap_se.astype(np.float32),
        "scaling_participation": participation.astype(np.float32),
        "scaling_participation_se": participation_se.astype(np.float32),
        "scaling_atom_weight": np.asarray(
            [
                2.0 * case["plus_atoms_per_matrix"] / case["D"]
                for case in cases
            ],
            dtype=np.float32,
        ),
    }
    return fits, arrays


def run(
    physical_npz: Path,
    covariance_npz: Path,
    scaling_json_path: Path,
    scaling_npz: Path,
    output_json: Path,
    output_npz: Path,
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES,
) -> dict[str, Any]:
    """Generate confidence bands, long-range diagnostics, and size fits."""

    started = time.perf_counter()
    replicates = int(bootstrap_replicates)
    if replicates < 100:
        raise ValueError("at least 100 bootstrap replicates are required")
    with np.load(physical_npz) as physical_arrays:
        test_indices = physical_arrays["test_indices"]
        physical = physical_arrays["normalized_spectra"][
            test_indices
        ].astype(float)
        physical_groups = physical_arrays["seed_block"][test_indices]
    with np.load(covariance_npz) as covariance_arrays:
        haar = covariance_arrays["haar_spectra"].astype(float)
        deformed = covariance_arrays["deformed_spectra"].astype(float)
    scaling_json = json.loads(
        scaling_json_path.read_text(encoding="utf-8")
    )
    output_arrays: dict[str, np.ndarray] = {
        "density_grid": DENSITY_GRID.astype(np.float32),
        "ratio_centers": (
            0.5 * (RATIO_EDGES[:-1] + RATIO_EDGES[1:])
        ).astype(np.float32),
        "lengths": LENGTHS.astype(np.float32),
        "form_factor_times": FORM_FACTOR_TIMES.astype(np.float32),
        "moment_orders": np.asarray([2, 4, 6, 8], dtype=np.int16),
    }
    ensemble_metadata = {}
    for offset, (name, spectra, groups) in enumerate(
        (
            ("physical", physical, physical_groups),
            ("haar", haar, None),
            ("deformed", deformed, None),
        )
    ):
        print(f"statistical curves: {name}", flush=True)
        ensemble_metadata[name] = _curve_suite(
            spectra,
            seed=20260728600 + 20 * offset,
            output=output_arrays,
            prefix=name,
            groups=groups,
            replicates=replicates,
        )
    sensitivity = _sensitivity(physical, haar, deformed)
    with np.load(scaling_npz) as scaling_arrays:
        fits, scaling_output = _scaling_inference(
            scaling_json,
            scaling_arrays,
        )
    output_arrays.update(scaling_output)
    density_band_ordering = all(
        values["physical_deformed_l1"]
        < values["physical_haar_l1"]
        for values in sensitivity["bandwidth"].values()
    )
    checks = {
        "registered_bootstrap_count": (
            replicates == BOOTSTRAP_REPLICATES
        ),
        "physical_uses_seed_block_hierarchy": (
            ensemble_metadata["physical"]["density"]["method"]
            == "hierarchical_seed_block_bootstrap"
        ),
        "reference_uses_matrix_level_inference": (
            ensemble_metadata["haar"]["density"]["method"].startswith(
                "matrix_"
            )
            and ensemble_metadata["deformed"]["density"][
                "method"
            ].startswith("matrix_")
        ),
        "covariance_improvement_bandwidth_stable": density_band_ordering,
        "all_size_fits_registered": all(
            fit["best_by_loo"] in {"D^-1/2", "D^-1", "free"}
            for fit in fits.values()
        ),
        "all_curves_finite": all(
            bool(np.all(np.isfinite(value)))
            for value in output_arrays.values()
        ),
    }
    result = {
        "schema_version": 1,
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "physical": str(physical_npz),
            "covariance": str(covariance_npz),
            "scaling_json": str(scaling_json_path),
            "scaling_npz": str(scaling_npz),
        },
        "bootstrap_replicates": replicates,
        "kde_bandwidth": KDE_BANDWIDTH,
        "bulk_fraction": 0.7,
        "unfolding": "ensemble_cdf",
        "physical_test_matrices": int(physical.shape[0]),
        "haar_matrices": int(haar.shape[0]),
        "deformed_matrices": int(deformed.shape[0]),
        "ensemble_inference": ensemble_metadata,
        "sensitivity": sensitivity,
        "finite_size_fits": fits,
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
    np.savez_compressed(output_npz, **output_arrays)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--physical-npz",
        type=Path,
        default=Path("output/physical_ensemble_v1.npz"),
    )
    parser.add_argument(
        "--covariance-npz",
        type=Path,
        default=Path("output/covariance_model_v1.npz"),
    )
    parser.add_argument(
        "--scaling-json",
        type=Path,
        default=Path("output/rank_scaling_v1.json"),
    )
    parser.add_argument(
        "--scaling-npz",
        type=Path,
        default=Path("output/rank_scaling_v1.npz"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("output/statistical_analysis_v1.json"),
    )
    parser.add_argument(
        "--output-npz",
        type=Path,
        default=Path("output/statistical_analysis_v1.npz"),
    )
    parser.add_argument(
        "--bootstrap-replicates",
        type=int,
        default=BOOTSTRAP_REPLICATES,
    )
    args = parser.parse_args()
    result = run(
        args.physical_npz,
        args.covariance_npz,
        args.scaling_json,
        args.scaling_npz,
        args.output_json,
        args.output_npz,
        bootstrap_replicates=args.bootstrap_replicates,
    )
    print(json.dumps(result, indent=2))
    if not result["all_checks_pass"]:
        raise SystemExit("statistical-analysis audit failed")


if __name__ == "__main__":
    main()
