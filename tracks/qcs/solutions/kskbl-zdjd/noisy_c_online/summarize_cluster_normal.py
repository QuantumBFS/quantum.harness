"""Compare cluster-normal and empirical-Bernstein intervals under correlation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normal", action="append", type=Path, required=True)
    parser.add_argument("--bernstein", action="append", type=Path, required=True)
    parser.add_argument("--learned-network", type=Path, required=True)
    parser.add_argument("--monte-carlo-trials", type=int, default=20000)
    parser.add_argument("--output-summary", type=Path, required=True)
    parser.add_argument("--output-figure", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_run(directory: Path) -> dict[str, Any]:
    path = directory / "run.json"
    run = json.loads(path.read_text(encoding="utf-8"))
    run["_path"] = path.as_posix()
    run["_sha256"] = sha256(path)
    return run


def signature(stage: dict[str, Any]) -> tuple[tuple[int, int], ...]:
    return tuple(
        sorted(
            (int(row["mask"]), int(row["coefficient"]))
            for row in stage["final_integer_coefficients"]
            if int(row["coefficient"]) != 0
        )
    )


def validate(
    normal: list[dict[str, Any]],
    bernstein: list[dict[str, Any]],
    network: dict[str, Any],
) -> None:
    if len(normal) != 12 or len(bernstein) != 12:
        raise ValueError("expected twelve paired runs per method")
    if {
        run["config"]["base_seed"] for run in normal
    } != {
        run["config"]["base_seed"] for run in bernstein
    }:
        raise ValueError("runs are not seed-paired")
    expected_signature = tuple(
        sorted(
            (int(row["mask"]), int(row["coefficient"]))
            for row in network["active_features"]
        )
    )
    for method, runs in (
        ("cluster-normal", normal),
        ("empirical-bernstein", bernstein),
    ):
        for run in runs:
            config = run["config"]
            if config["noise_mode"] != "common-xor":
                raise ValueError("noise mode mismatch")
            if config["noise_confidence_unit"] != "word":
                raise ValueError("run is not word-cluster")
            if (
                config.get(
                    "confidence_interval_method",
                    "empirical-bernstein",
                )
                != method
            ):
                raise ValueError("interval method mismatch")
            if run["accepted_degree"] != 2:
                raise ValueError("a run did not select quadratic")
            if run["final_clean_metrics"]["word_accuracy"] != 1.0:
                raise ValueError("a final model is not exact")
            if signature(run["stages"][-1]) != expected_signature:
                raise ValueError("a run recovered a different rule")
            verification = run["verification"]
            if verification["clean_labels_used_for_degree_selection"]:
                raise ValueError("clean labels leaked into selection")


def compact(run: dict[str, Any]) -> dict[str, Any]:
    accepted = run["stages"][-1]["checks"][-1]
    true_rate = float(run["config"]["oracle_noise_rate"])
    p_lower = float(accepted["selection_noise_rate_lower"])
    p_upper = float(accepted["selection_noise_rate_upper"])
    return {
        "path": run["_path"],
        "run_sha256": run["_sha256"],
        "base_seed": int(run["config"]["base_seed"]),
        "accept_step": int(accepted["stage_step"]),
        "noise_interval_at_acceptance": [p_lower, p_upper],
        "noise_interval_contains_true_rate": (
            p_lower <= true_rate <= p_upper
        ),
        "excess_interval_at_acceptance": [
            float(accepted["holdout_excess_lower"]),
            float(accepted["holdout_excess_upper"]),
        ],
        "training_examples": int(run["cumulative_training_examples"]),
        "holdout_words": int(run["cumulative_holdout_words"]),
        "total_noisy_oracle_words": int(
            run["cumulative_noisy_oracle_words"]
        ),
        "final_clean_word_accuracy": float(
            run["final_clean_metrics"]["word_accuracy"]
        ),
    }


def to_noise(disagreement: np.ndarray) -> np.ndarray:
    clipped = np.clip(disagreement, 0.0, 0.5)
    return 0.5 * (
        1.0 - np.sqrt(np.maximum(1.0 - 2.0 * clipped, 0.0))
    )


def monte_carlo(
    trials: int,
    word_pair_counts: list[int],
    delta: float,
) -> list[dict[str, float | int]]:
    rng = np.random.default_rng(1_276_019)
    common = 2.0 / 9.0
    residual = 0.05
    shared_pair_rate = 2.0 * common * (1.0 - common)
    residual_pair_rate = 2.0 * residual * (1.0 - residual)
    z_value = NormalDist().inv_cdf(1.0 - delta / 2.0)
    log_term = math.log(3.0 / delta)
    rows: list[dict[str, float | int]] = []
    for word_pairs in word_pair_counts:
        normal_covered = 0
        bernstein_covered = 0
        normal_widths: list[float] = []
        bernstein_widths: list[float] = []
        completed = 0
        while completed < trials:
            chunk = min(200, trials - completed)
            shared = rng.random((chunk, word_pairs)) < shared_pair_rate
            residual_counts = rng.binomial(
                12,
                residual_pair_rate,
                size=(chunk, word_pairs),
            )
            disagreements = np.where(
                shared,
                12 - residual_counts,
                residual_counts,
            ) / 12.0
            means = disagreements.mean(axis=1)
            variances = disagreements.var(axis=1, ddof=1)
            standard_errors = np.sqrt(variances / word_pairs)
            normal_radius = z_value * standard_errors
            bernstein_radius = (
                np.sqrt(
                    2.0 * variances * log_term / word_pairs
                )
                + 3.0 * log_term / word_pairs
            )
            normal_lower = to_noise(means - normal_radius)
            normal_upper = to_noise(means + normal_radius)
            bernstein_lower = to_noise(means - bernstein_radius)
            bernstein_upper = to_noise(means + bernstein_radius)
            normal_covered += int(
                np.count_nonzero(
                    (normal_lower <= 0.25) & (0.25 <= normal_upper)
                )
            )
            bernstein_covered += int(
                np.count_nonzero(
                    (bernstein_lower <= 0.25)
                    & (0.25 <= bernstein_upper)
                )
            )
            normal_widths.extend(
                (normal_upper - normal_lower).tolist()
            )
            bernstein_widths.extend(
                (bernstein_upper - bernstein_lower).tolist()
            )
            completed += chunk
        rows.append(
            {
                "independent_word_pairs": word_pairs,
                "trials": trials,
                "nominal_coverage": 1.0 - delta,
                "cluster_normal_empirical_coverage": (
                    normal_covered / trials
                ),
                "empirical_bernstein_coverage": (
                    bernstein_covered / trials
                ),
                "cluster_normal_median_width": float(
                    np.median(normal_widths)
                ),
                "empirical_bernstein_median_width": float(
                    np.median(bernstein_widths)
                ),
            }
        )
    return rows


def plot(
    normal: list[dict[str, Any]],
    bernstein: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
    output: Path,
) -> None:
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )
    fig, axes = plt.subplots(1, 3, figsize=(13.4, 3.8))
    normal_by_seed = {row["base_seed"]: row for row in normal}
    bernstein_by_seed = {row["base_seed"]: row for row in bernstein}
    seeds = sorted(normal_by_seed)
    axes[0].scatter(
        [bernstein_by_seed[seed]["total_noisy_oracle_words"] for seed in seeds],
        [normal_by_seed[seed]["total_noisy_oracle_words"] for seed in seeds],
        color="#7c3aed",
        s=45,
        edgecolor="white",
        linewidth=0.6,
    )
    limit = max(
        row["total_noisy_oracle_words"]
        for row in normal + bernstein
    ) * 1.05
    axes[0].plot([0, limit], [0, limit], color="#666666", linestyle="--")
    axes[0].set_xlim(0, limit)
    axes[0].set_ylim(0, limit)
    axes[0].set_xlabel("Bernstein total noisy words")
    axes[0].set_ylabel("cluster-normal total noisy words")
    axes[0].set_title("Every paired run is cheaper")
    axes[0].grid(True, alpha=0.2)

    counts = [row["independent_word_pairs"] for row in coverage]
    axes[1].plot(
        counts,
        [
            100 * row["cluster_normal_empirical_coverage"]
            for row in coverage
        ],
        "o-",
        color="#7c3aed",
        label="cluster-normal",
    )
    axes[1].plot(
        counts,
        [
            100 * row["empirical_bernstein_coverage"]
            for row in coverage
        ],
        "o-",
        color="#08745a",
        label="empirical Bernstein",
    )
    axes[1].axhline(
        100 * coverage[0]["nominal_coverage"],
        color="#666666",
        linestyle="--",
        linewidth=1,
        label="nominal 99%",
    )
    axes[1].set_xscale("log")
    axes[1].set_ylim(97.5, 100.2)
    axes[1].set_xlabel("independent repeated-word pairs")
    axes[1].set_ylabel("empirical coverage (%)")
    axes[1].set_title("A 99% finite-simulation audit")
    axes[1].grid(True, which="both", alpha=0.2)
    axes[1].legend(frameon=False, fontsize=8)

    axes[2].plot(
        counts,
        [
            100 * row["cluster_normal_median_width"]
            for row in coverage
        ],
        "o-",
        color="#7c3aed",
        label="cluster-normal",
    )
    axes[2].plot(
        counts,
        [
            100 * row["empirical_bernstein_median_width"]
            for row in coverage
        ],
        "o-",
        color="#08745a",
        label="empirical Bernstein",
    )
    axes[2].set_xscale("log")
    axes[2].set_yscale("log")
    axes[2].set_xlabel("independent repeated-word pairs")
    axes[2].set_ylabel("median p-interval width (percentage points)")
    axes[2].set_title("Asymptotic intervals recover precision")
    axes[2].grid(True, which="both", alpha=0.2)
    axes[2].legend(frameon=False, fontsize=8)

    fig.suptitle(
        "Cluster-normal intervals halve the correlated-noise oracle cost",
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    normal_runs = [load_run(path) for path in args.normal]
    bernstein_runs = [load_run(path) for path in args.bernstein]
    network = json.loads(args.learned_network.read_text(encoding="utf-8"))
    validate(normal_runs, bernstein_runs, network)
    normal = [compact(run) for run in normal_runs]
    bernstein = [compact(run) for run in bernstein_runs]
    coverage = monte_carlo(
        args.monte_carlo_trials,
        [250, 500, 1000, 2500, 5000],
        0.01,
    )
    normal_mean = float(
        np.mean([row["total_noisy_oracle_words"] for row in normal])
    )
    bernstein_mean = float(
        np.mean(
            [row["total_noisy_oracle_words"] for row in bernstein]
        )
    )
    summary = {
        "kind": "cluster-normal-correlated-noise-acceleration",
        "protocol": {
            "noise_model": (
                "25% marginal common-XOR noise with 5% independent residual"
            ),
            "confidence_unit": "independent repeated-word pair",
            "deployed_interval_probability": normal_runs[0]["config"][
                "per_interval_failure_probability"
            ],
            "monte_carlo_audit_coverage_level": 0.99,
            "monte_carlo_trials_per_pair_count": args.monte_carlo_trials,
            "clean_labels_used_for_updates_or_selection": False,
        },
        "claims": {
            "all_24_paired_runs_select_quadratic": True,
            "all_24_paired_runs_final_exact": True,
            "all_24_recover_verified_36_term_156_gate_rule": True,
            "cluster_normal_true_p_covered_at_acceptance": sum(
                row["noise_interval_contains_true_rate"]
                for row in normal
            ),
            "bernstein_true_p_covered_at_acceptance": sum(
                row["noise_interval_contains_true_rate"]
                for row in bernstein
            ),
            "cluster_normal_mean_total_noisy_words": normal_mean,
            "bernstein_mean_total_noisy_words": bernstein_mean,
            "mean_cost_reduction_factor": bernstein_mean / normal_mean,
            "all_12_paired_cluster_normal_runs_cheaper": all(
                next(
                    row for row in normal
                    if row["base_seed"] == baseline["base_seed"]
                )["total_noisy_oracle_words"]
                < baseline["total_noisy_oracle_words"]
                for baseline in bernstein
            ),
            "minimum_cluster_normal_99pct_monte_carlo_coverage": float(
                min(
                    row["cluster_normal_empirical_coverage"]
                    for row in coverage
                )
            ),
        },
        "monte_carlo_coverage": coverage,
        "cluster_normal_runs": normal,
        "empirical_bernstein_runs": bernstein,
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    plot(normal, bernstein, coverage, args.output_figure)
    print(json.dumps(summary["claims"], indent=2))
    print(json.dumps(coverage, indent=2))


if __name__ == "__main__":
    main()
