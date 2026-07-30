"""Audit self-normalized intervals for independent-bit noisy degree discovery."""

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
    if len(normal) != 8 or len(bernstein) != 8:
        raise ValueError("expected eight paired runs per method")
    if {
        run["config"]["base_seed"] for run in normal
    } != {
        run["config"]["base_seed"] for run in bernstein
    }:
        raise ValueError("runs are not paired")
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
            if config.get("noise_mode", "independent") != "independent":
                raise ValueError("noise mode mismatch")
            if config.get("noise_confidence_unit", "bit") != "bit":
                raise ValueError("confidence unit mismatch")
            if (
                config.get(
                    "confidence_interval_method",
                    "empirical-bernstein",
                )
                != method
            ):
                raise ValueError("interval method mismatch")
            if run["accepted_degree"] != 2:
                raise ValueError("a run did not accept quadratic")
            if run["final_clean_metrics"]["word_accuracy"] != 1.0:
                raise ValueError("a final model is not exact")
            if signature(run["stages"][-1]) != expected_signature:
                raise ValueError("a run recovered a different rule")
            if run["verification"]["clean_labels_used_for_degree_selection"]:
                raise ValueError("clean labels leaked into selection")


def compact(run: dict[str, Any]) -> dict[str, Any]:
    accepted = run["stages"][-1]["checks"][-1]
    p_lower = float(accepted["selection_noise_rate_lower"])
    p_upper = float(accepted["selection_noise_rate_upper"])
    return {
        "path": run["_path"],
        "run_sha256": run["_sha256"],
        "base_seed": int(run["config"]["base_seed"]),
        "accept_step": int(accepted["stage_step"]),
        "noise_interval_at_acceptance": [p_lower, p_upper],
        "noise_interval_contains_true_rate": p_lower <= 0.25 <= p_upper,
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


def monte_carlo(trials: int = 50000) -> list[dict[str, float | int]]:
    rng = np.random.default_rng(3_140_159)
    delta = 0.01
    z_value = NormalDist().inv_cdf(1.0 - delta / 2.0)
    log_term = math.log(3.0 / delta)
    rows: list[dict[str, float | int]] = []
    for pairs in (1000, 5000, 10000, 30000):
        disagreements = rng.binomial(pairs, 0.375, size=trials)
        means = disagreements / pairs
        variances = (
            means * (1.0 - means) * pairs / (pairs - 1)
        )
        normal_radius = z_value * np.sqrt(variances / pairs)
        bernstein_radius = (
            np.sqrt(2.0 * variances * log_term / pairs)
            + 3.0 * log_term / pairs
        )
        normal_lower = to_noise(means - normal_radius)
        normal_upper = to_noise(means + normal_radius)
        bernstein_lower = to_noise(means - bernstein_radius)
        bernstein_upper = to_noise(means + bernstein_radius)
        normal_covered = (
            (normal_lower <= 0.25) & (0.25 <= normal_upper)
        )
        bernstein_covered = (
            (bernstein_lower <= 0.25) & (0.25 <= bernstein_upper)
        )
        rows.append(
            {
                "independent_bit_pairs": pairs,
                "trials": trials,
                "nominal_coverage": 0.99,
                "normal_empirical_coverage": float(
                    np.mean(normal_covered)
                ),
                "bernstein_empirical_coverage": float(
                    np.mean(bernstein_covered)
                ),
                "normal_median_width": float(
                    np.median(normal_upper - normal_lower)
                ),
                "bernstein_median_width": float(
                    np.median(bernstein_upper - bernstein_lower)
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
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.7))
    normal_by_seed = {row["base_seed"]: row for row in normal}
    bernstein_by_seed = {row["base_seed"]: row for row in bernstein}
    seeds = sorted(normal_by_seed)
    axes[0].scatter(
        [bernstein_by_seed[seed]["total_noisy_oracle_words"] for seed in seeds],
        [normal_by_seed[seed]["total_noisy_oracle_words"] for seed in seeds],
        color="#7c3aed",
        s=50,
        edgecolor="white",
        linewidth=0.6,
    )
    limit = 25000
    axes[0].plot([0, limit], [0, limit], color="#666666", linestyle="--")
    axes[0].set_xlim(0, limit)
    axes[0].set_ylim(0, limit)
    axes[0].set_xlabel("Bernstein total noisy words")
    axes[0].set_ylabel("self-normalized total noisy words")
    axes[0].set_title("All eight paired seeds use fewer words")
    axes[0].grid(True, alpha=0.2)

    methods = ["empirical\nBernstein", "self-normalized\nnormal"]
    training = [
        np.mean([row["training_examples"] for row in bernstein]),
        np.mean([row["training_examples"] for row in normal]),
    ]
    holdout = [
        np.mean([row["holdout_words"] for row in bernstein]),
        np.mean([row["holdout_words"] for row in normal]),
    ]
    x = np.arange(2)
    axes[1].bar(x, training, color="#075985", label="training")
    axes[1].bar(
        x,
        holdout,
        bottom=training,
        color="#f1b24a",
        label="holdout",
    )
    axes[1].set_xticks(x, methods)
    axes[1].set_ylabel("mean noisy oracle words")
    axes[1].set_title("Most validation overhead disappears")
    axes[1].grid(True, axis="y", alpha=0.2)
    axes[1].legend(frameon=False, fontsize=8)

    counts = [row["independent_bit_pairs"] for row in coverage]
    axes[2].plot(
        counts,
        [100 * row["normal_empirical_coverage"] for row in coverage],
        "o-",
        color="#7c3aed",
        label="self-normalized normal",
    )
    axes[2].plot(
        counts,
        [100 * row["bernstein_empirical_coverage"] for row in coverage],
        "o-",
        color="#08745a",
        label="empirical Bernstein",
    )
    axes[2].axhline(99, color="#666666", linestyle="--", label="nominal 99%")
    axes[2].set_xscale("log")
    axes[2].set_ylim(98.3, 100.15)
    axes[2].set_xlabel("independent repeated-bit pairs")
    axes[2].set_ylabel("empirical coverage (%)")
    axes[2].set_title("50,000-trial independent-noise audit")
    axes[2].grid(True, which="both", alpha=0.2)
    axes[2].legend(frameon=False, fontsize=7.5)

    fig.suptitle(
        "Self-normalized intervals accelerate unknown-degree discovery",
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
    coverage = monte_carlo()
    normal_mean = float(
        np.mean([row["total_noisy_oracle_words"] for row in normal])
    )
    bernstein_mean = float(
        np.mean(
            [row["total_noisy_oracle_words"] for row in bernstein]
        )
    )
    summary = {
        "kind": "self-normalized-independent-noise-degree-acceleration",
        "protocol": {
            "noise_rate": 0.25,
            "noise_independent_across_bits_and_words": True,
            "paired_seeds": sorted(row["base_seed"] for row in normal),
            "monte_carlo_trials_per_pair_count": 50000,
            "monte_carlo_coverage_level": 0.99,
            "clean_labels_used_for_updates_or_selection": False,
        },
        "claims": {
            "all_16_paired_runs_select_quadratic": True,
            "all_16_paired_runs_final_exact": True,
            "all_16_recover_verified_36_term_156_gate_rule": True,
            "normal_true_p_covered_at_acceptance": sum(
                row["noise_interval_contains_true_rate"] for row in normal
            ),
            "bernstein_true_p_covered_at_acceptance": sum(
                row["noise_interval_contains_true_rate"]
                for row in bernstein
            ),
            "normal_mean_training_examples": float(
                np.mean([row["training_examples"] for row in normal])
            ),
            "normal_mean_holdout_words": float(
                np.mean([row["holdout_words"] for row in normal])
            ),
            "normal_mean_total_noisy_words": normal_mean,
            "bernstein_mean_total_noisy_words": bernstein_mean,
            "mean_cost_reduction_factor": bernstein_mean / normal_mean,
            "all_eight_normal_runs_cheaper": all(
                normal_by_seed["total_noisy_oracle_words"]
                < baseline["total_noisy_oracle_words"]
                for baseline in bernstein
                for normal_by_seed in [
                    next(
                        row for row in normal
                        if row["base_seed"] == baseline["base_seed"]
                    )
                ]
            ),
            "minimum_normal_99pct_monte_carlo_coverage": float(
                min(
                    row["normal_empirical_coverage"]
                    for row in coverage
                )
            ),
        },
        "monte_carlo_coverage": coverage,
        "self_normalized_runs": normal,
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
