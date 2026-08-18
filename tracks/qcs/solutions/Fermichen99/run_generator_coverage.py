#!/usr/bin/env python3
"""Measure how many model-Hessian directions cover all true gate generators."""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import sys
import tempfile
import time
from pathlib import Path

import jax

jax.config.update("jax_enable_x64", True)

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "fermichen99-sim-to-real-matplotlib"),
)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy

from landscapes import coverage_spectrum, endpoint_jacobian
from sim_to_real import (
    make_demo_problem,
    make_drift_perturbation,
    with_drift_mismatch,
)


DEFAULT_EPSILONS = [
    0.0,
    0.01,
    0.02,
    0.03,
    0.05,
    0.075,
    0.1,
    0.125,
    0.15,
    0.175,
    0.2,
    0.25,
    0.3,
    0.35,
    0.4,
    0.5,
    0.6,
    0.75,
    1.0,
    1.5,
    2.0,
]
DEFAULT_PERTURBATION_SEEDS = [113, 211, 307, 401, 503]
DEFAULT_THRESHOLDS = [0.9, 0.95, 0.99]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--calibration",
        type=Path,
        default=Path(
            "tracks/qcs/results/sim-to-real-calibration-v1/calibration_data.npz"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tracks/qcs/results/sim-to-real-generator-coverage-v1"),
    )
    parser.add_argument(
        "--epsilons",
        type=float,
        nargs="+",
        default=DEFAULT_EPSILONS,
    )
    parser.add_argument(
        "--perturbation-seeds",
        type=int,
        nargs="+",
        default=DEFAULT_PERTURBATION_SEEDS,
    )
    parser.add_argument(
        "--thresholds",
        type=float,
        nargs="+",
        default=DEFAULT_THRESHOLDS,
    )
    parser.add_argument("--minimum-k", type=int, default=15)
    parser.add_argument("--maximum-k", type=int, default=40)
    parser.add_argument("--n-steps", type=int, default=256)
    parser.add_argument("--small-gap-fit-maximum", type=float, default=0.1)
    return parser.parse_args()


def progress(message: str) -> None:
    print(message, flush=True)


def quantile_summary(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "minimum": float(np.min(array)),
        "q25": float(np.quantile(array, 0.25)),
        "median": float(np.median(array)),
        "q75": float(np.quantile(array, 0.75)),
        "maximum": float(np.max(array)),
    }


def threshold_label(threshold: float) -> str:
    return f"covered_{round(100 * threshold):d}"


def fit_power_law(
    rows: list[dict[str, object]],
    *,
    maximum_epsilon: float,
) -> dict[str, float | int]:
    selected = [
        row
        for row in rows
        if 0.0 < float(row["epsilon"]) <= maximum_epsilon
        and int(row["k"]) == 15
    ]
    epsilon = np.asarray(
        [float(row["epsilon"]) for row in selected], dtype=np.float64
    )
    lost_coverage = np.asarray(
        [1.0 - float(row["minimum_coverage"]) for row in selected],
        dtype=np.float64,
    )
    positive = lost_coverage > np.finfo(np.float64).eps
    log_epsilon = np.log(epsilon[positive])
    log_loss = np.log(lost_coverage[positive])
    slope, intercept = np.polyfit(log_epsilon, log_loss, 1)
    predicted = slope * log_epsilon + intercept
    residual = float(np.sum((log_loss - predicted) ** 2))
    total = float(np.sum((log_loss - np.mean(log_loss)) ** 2))
    return {
        "samples": int(log_loss.size),
        "maximum_epsilon": maximum_epsilon,
        "exponent": float(slope),
        "coefficient": float(np.exp(intercept)),
        "r_squared_log_space": 1.0 - residual / total,
    }


def main() -> None:
    args = parse_args()
    if not args.calibration.exists():
        raise FileNotFoundError(f"missing calibration: {args.calibration}")
    if any(epsilon < 0.0 for epsilon in args.epsilons):
        raise ValueError("epsilons must be non-negative")
    if not args.perturbation_seeds:
        raise ValueError("at least one perturbation seed is required")
    if any(not 0.0 < threshold <= 1.0 for threshold in args.thresholds):
        raise ValueError("coverage thresholds must lie in (0, 1]")
    if args.minimum_k <= 0 or args.maximum_k < args.minimum_k:
        raise ValueError("invalid k range")

    calibration = np.load(args.calibration)
    theta_star = np.asarray(calibration["theta_star"], dtype=np.float64)
    model_eigenvectors = np.asarray(
        calibration["hessian_eigenvectors"], dtype=np.float64
    )
    if args.maximum_k > theta_star.size:
        raise ValueError("maximum k exceeds the pulse parameter count")
    if model_eigenvectors.shape != (theta_star.size, theta_star.size):
        raise ValueError("unexpected model Hessian eigenvector shape")

    problem = make_demo_problem()
    generator_dimension = problem.dim**2 - 1
    if args.minimum_k < generator_dimension:
        raise ValueError(
            f"minimum k must be at least d^2-1={generator_dimension}"
        )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    dimensions = list(range(args.minimum_k, args.maximum_k + 1))
    display_threshold = min(
        args.thresholds, key=lambda threshold: abs(threshold - 0.95)
    )
    total_cases = len(args.epsilons) * len(args.perturbation_seeds)
    progress(
        f"[1/5] generator coverage: {total_cases} Jacobians, "
        f"k={args.minimum_k}..{args.maximum_k}, "
        f"thresholds={args.thresholds}"
    )

    rows: list[dict[str, object]] = []
    required_rows: list[dict[str, object]] = []
    start = time.perf_counter()
    completed = 0
    for perturbation_seed in args.perturbation_seeds:
        perturbation = make_drift_perturbation(
            problem, seed=perturbation_seed
        )
        for epsilon in args.epsilons:
            true_problem = with_drift_mismatch(
                problem, perturbation, epsilon
            )
            jacobian = np.asarray(
                endpoint_jacobian(
                    true_problem,
                    theta_star,
                    n_steps=args.n_steps,
                ),
                dtype=np.float64,
            )
            _, singular_values, right_vectors_h = np.linalg.svd(
                jacobian, full_matrices=False
            )
            tolerance = (
                np.max(jacobian.shape)
                * np.finfo(np.float64).eps
                * singular_values[0]
            )
            observed_rank = int(np.sum(singular_values > tolerance))
            if observed_rank != generator_dimension:
                raise RuntimeError(
                    f"endpoint Jacobian rank {observed_rank}, "
                    f"expected {generator_dimension}"
                )
            true_generator_basis = right_vectors_h.T[:, :generator_dimension]

            case_rows: list[dict[str, object]] = []
            for k in dimensions:
                spectrum = coverage_spectrum(
                    true_generator_basis,
                    model_eigenvectors[:, :k],
                )
                row: dict[str, object] = {
                    "epsilon": epsilon,
                    "perturbation_seed": perturbation_seed,
                    "k": k,
                    "generator_dimension": generator_dimension,
                    "minimum_coverage": float(np.min(spectrum)),
                    "mean_coverage": float(np.mean(spectrum)),
                    "uncovered_weight": float(np.sum(1.0 - spectrum)),
                    "largest_angle_degrees": float(
                        np.degrees(np.arccos(np.sqrt(np.min(spectrum))))
                    ),
                }
                for threshold in args.thresholds:
                    row[threshold_label(threshold)] = int(
                        np.sum(spectrum >= threshold)
                    )
                rows.append(row)
                case_rows.append(row)

            for threshold in args.thresholds:
                required_k = next(
                    int(row["k"])
                    for row in case_rows
                    if float(row["minimum_coverage"]) + 1e-12 >= threshold
                )
                required_rows.append(
                    {
                        "epsilon": epsilon,
                        "perturbation_seed": perturbation_seed,
                        "threshold": threshold,
                        "required_k": required_k,
                    }
                )

            completed += 1
            display_k = next(
                int(row["required_k"])
                for row in required_rows
                if row["epsilon"] == epsilon
                and row["perturbation_seed"] == perturbation_seed
                and np.isclose(
                    float(row["threshold"]), display_threshold
                )
            )
            progress(
                f"      {completed:>3}/{total_cases}: "
                f"seed={perturbation_seed}, ε={epsilon:g}, "
                f"k{100 * display_threshold:.0f}={display_k}"
            )

    progress("[2/5] aggregate threshold dimensions and fixed-k coverage")
    with (args.output_dir / "coverage_by_k.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    with (args.output_dir / "required_k.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(required_rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(required_rows)

    required_summaries: list[dict[str, object]] = []
    for epsilon in args.epsilons:
        for threshold in args.thresholds:
            selected = [
                int(row["required_k"])
                for row in required_rows
                if row["epsilon"] == epsilon
                and np.isclose(float(row["threshold"]), threshold)
            ]
            required_summaries.append(
                {
                    "epsilon": epsilon,
                    "threshold": threshold,
                    **quantile_summary(selected),
                }
            )
    with (args.output_dir / "required_k_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(required_summaries[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(required_summaries)

    fixed15_summaries: list[dict[str, object]] = []
    for epsilon in args.epsilons:
        selected = [
            row
            for row in rows
            if row["epsilon"] == epsilon and int(row["k"]) == 15
        ]
        minimum_summary = quantile_summary(
            [float(row["minimum_coverage"]) for row in selected]
        )
        mean_summary = quantile_summary(
            [float(row["mean_coverage"]) for row in selected]
        )
        fixed15_summaries.append(
            {
                "epsilon": epsilon,
                **{
                    f"minimum_coverage_{key}": value
                    for key, value in minimum_summary.items()
                },
                **{
                    f"mean_coverage_{key}": value
                    for key, value in mean_summary.items()
                },
            }
        )
    with (args.output_dir / "fixed15_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fixed15_summaries[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(fixed15_summaries)

    power_law = fit_power_law(
        rows, maximum_epsilon=args.small_gap_fit_maximum
    )
    (args.output_dir / "small_gap_fit.json").write_text(
        json.dumps(power_law, indent=2), encoding="utf-8"
    )

    progress("[3/5] render coverage and required-dimension figures")
    epsilons = np.asarray(args.epsilons, dtype=np.float64)
    figure, axis = plt.subplots(figsize=(8.2, 4.8))
    fixed_median = np.asarray(
        [row["minimum_coverage_median"] for row in fixed15_summaries]
    )
    fixed_q25 = np.asarray(
        [row["minimum_coverage_q25"] for row in fixed15_summaries]
    )
    fixed_q75 = np.asarray(
        [row["minimum_coverage_q75"] for row in fixed15_summaries]
    )
    axis.plot(epsilons, fixed_median, "o-", label="median over drift seeds")
    axis.fill_between(
        epsilons,
        fixed_q25,
        fixed_q75,
        alpha=0.2,
        label="seed IQR",
    )
    for threshold in args.thresholds:
        axis.axhline(
            threshold,
            linestyle=":",
            linewidth=1.0,
            label=f"{100 * threshold:.0f}% threshold",
        )
    axis.set_xscale("symlog", linthresh=0.03)
    axis.set_xlim(0.0, float(np.max(epsilons)) * 1.05)
    axis.set(
        xlabel="structural mismatch ε",
        ylabel="worst-generator coverage by model top-15",
        ylim=(0.0, 1.02),
        title="Fixed 15 Hessian directions gradually lose generator coverage",
    )
    axis.grid(alpha=0.2)
    axis.legend(fontsize=8, ncol=2)
    figure.tight_layout()
    figure.savefig(
        args.output_dir / "fixed15_coverage_vs_epsilon.png", dpi=180
    )
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8.2, 4.8))
    colors = plt.cm.plasma(
        np.linspace(0.15, 0.85, len(args.thresholds))
    )
    for threshold, color in zip(args.thresholds, colors, strict=True):
        selected = [
            row
            for row in required_summaries
            if np.isclose(float(row["threshold"]), threshold)
        ]
        median = np.asarray([row["median"] for row in selected])
        q25 = np.asarray([row["q25"] for row in selected])
        q75 = np.asarray([row["q75"] for row in selected])
        axis.plot(
            epsilons,
            median,
            "o-",
            color=color,
            label=f"all 15 ≥ {100 * threshold:.0f}%",
        )
        axis.fill_between(epsilons, q25, q75, color=color, alpha=0.15)
    axis.axhline(
        generator_dimension,
        color="gray",
        linestyle="--",
        linewidth=1.0,
        label="ideal d²−1 = 15",
    )
    axis.set_xscale("symlog", linthresh=0.03)
    axis.set_xlim(0.0, float(np.max(epsilons)) * 1.05)
    axis.set(
        xlabel="structural mismatch ε",
        ylabel="minimum number of model Hessian directions k",
        ylim=(14.0, args.maximum_k + 1.0),
        title="How many Hessian directions cover all 15 generators?",
    )
    axis.grid(alpha=0.2)
    axis.legend(fontsize=8, ncol=2)
    figure.tight_layout()
    figure.savefig(
        args.output_dir / "required_k_vs_epsilon.png", dpi=180
    )
    plt.close(figure)

    median_grid = np.empty(
        (len(dimensions), len(args.epsilons)), dtype=np.float64
    )
    for epsilon_index, epsilon in enumerate(args.epsilons):
        for dimension_index, k in enumerate(dimensions):
            selected = [
                float(row["minimum_coverage"])
                for row in rows
                if row["epsilon"] == epsilon and int(row["k"]) == k
            ]
            median_grid[dimension_index, epsilon_index] = np.median(selected)
    figure, axis = plt.subplots(figsize=(10.5, 6.0))
    image = axis.imshow(
        median_grid,
        origin="lower",
        aspect="auto",
        vmin=0.0,
        vmax=1.0,
        cmap="viridis",
    )
    axis.set_xticks(
        np.arange(len(args.epsilons)),
        [f"{epsilon:g}" for epsilon in args.epsilons],
        rotation=55,
        ha="right",
    )
    axis.set_yticks(
        np.arange(0, len(dimensions), 5),
        [dimensions[index] for index in range(0, len(dimensions), 5)],
    )
    axis.set(
        xlabel="structural mismatch ε",
        ylabel="number of model Hessian directions k",
        title="Median worst-generator coverage across five drift directions",
    )
    colorbar = figure.colorbar(image, ax=axis)
    colorbar.set_label("minimum squared principal cosine")
    figure.tight_layout()
    figure.savefig(args.output_dir / "coverage_heatmap.png", dpi=180)
    plt.close(figure)

    small_rows = [
        row
        for row in fixed15_summaries
        if 0.0 < float(row["epsilon"]) <= args.small_gap_fit_maximum
    ]
    small_epsilon = np.asarray([row["epsilon"] for row in small_rows])
    lost_median = 1.0 - np.asarray(
        [row["minimum_coverage_median"] for row in small_rows]
    )
    fitted = (
        float(power_law["coefficient"])
        * small_epsilon ** float(power_law["exponent"])
    )
    figure, axis = plt.subplots(figsize=(6.8, 4.6))
    axis.loglog(
        small_epsilon,
        lost_median,
        "o-",
        label="median observed loss",
    )
    axis.loglog(
        small_epsilon,
        fitted,
        "--",
        label=(
            f"fit ∝ ε^{float(power_law['exponent']):.2f}, "
            f"R²={float(power_law['r_squared_log_space']):.3f}"
        ),
    )
    axis.set(
        xlabel="small structural mismatch ε",
        ylabel="lost worst-direction coverage, 1−cmin",
        title="Small-mismatch coverage loss is approximately quadratic",
    )
    axis.grid(alpha=0.2, which="both")
    axis.legend()
    figure.tight_layout()
    figure.savefig(args.output_dir / "small_gap_scaling.png", dpi=180)
    plt.close(figure)

    progress("[4/5] save run metadata")
    report = {
        "schema_version": 1,
        "run": "sim-to-real-generator-coverage-v1",
        "question": (
            "How many model-Hessian parameter directions are required to "
            "cover all d^2-1 true endpoint-generator directions?"
        ),
        "definition": {
            "reference": (
                "15-dimensional right-singular subspace of the true endpoint "
                "Jacobian at the model-optimal pulse"
            ),
            "candidate": "leading k model-Hessian eigenvectors",
            "coverage_spectrum": (
                "squared principal cosines between reference and candidate"
            ),
            "certificate": (
                "minimum coverage is the worst covered linear combination "
                "of true generator directions"
            ),
            "required_k": (
                "smallest k whose minimum coverage reaches the threshold"
            ),
        },
        "setup": {
            "dim": problem.dim,
            "generator_dimension": generator_dimension,
            "pulse_parameters": problem.n_params,
            "epsilons": args.epsilons,
            "perturbation_seeds": args.perturbation_seeds,
            "thresholds": args.thresholds,
            "minimum_k": args.minimum_k,
            "maximum_k": args.maximum_k,
            "n_steps": args.n_steps,
            "measurement_noise": (
                "none; epsilon is structural model-device mismatch, not "
                "finite-shot noise"
            ),
        },
        "small_gap_power_law": power_law,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "jax": jax.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "devices": [str(device) for device in jax.devices()],
        },
        "wall_seconds": time.perf_counter() - start,
        "artifacts": [
            "coverage_by_k.csv",
            "required_k.csv",
            "required_k_summary.csv",
            "fixed15_summary.csv",
            "small_gap_fit.json",
            "fixed15_coverage_vs_epsilon.png",
            "required_k_vs_epsilon.png",
            "coverage_heatmap.png",
            "small_gap_scaling.png",
        ],
        "rerun": (
            "python3 tracks/qcs/solutions/Fermichen99/"
            "run_generator_coverage.py"
        ),
    }
    (args.output_dir / "run.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    progress(
        f"[5/5] complete in {report['wall_seconds']:.1f}s: "
        f"{args.output_dir}/run.json"
    )


if __name__ == "__main__":
    main()
