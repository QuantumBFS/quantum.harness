"""Audit word-correlated noise and compare naive versus cluster-safe intervals."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--naive", action="append", type=Path, required=True)
    parser.add_argument("--robust", action="append", type=Path, required=True)
    parser.add_argument("--learned-network", type=Path, required=True)
    parser.add_argument("--independent-summary", type=Path, required=True)
    parser.add_argument("--monte-carlo-trials", type=int, default=5000)
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
    naive: list[dict[str, Any]],
    robust: list[dict[str, Any]],
    network: dict[str, Any],
) -> None:
    if len(naive) != 12 or len(robust) != 12:
        raise ValueError("expected twelve paired runs per method")
    naive_seeds = {run["config"]["base_seed"] for run in naive}
    robust_seeds = {run["config"]["base_seed"] for run in robust}
    if naive_seeds != robust_seeds:
        raise ValueError("naive and robust runs are not seed-paired")
    expected_signature = tuple(
        sorted(
            (int(row["mask"]), int(row["coefficient"]))
            for row in network["active_features"]
        )
    )
    for method, runs in (("bit", naive), ("word", robust)):
        for run in runs:
            config = run["config"]
            verification = run["verification"]
            if config["noise_mode"] != "common-xor":
                raise ValueError("run does not use common-XOR noise")
            if config["noise_confidence_unit"] != method:
                raise ValueError("confidence unit mismatch")
            if config["oracle_noise_rate"] != 0.25:
                raise ValueError("marginal noise rate mismatch")
            if config["independent_noise_rate"] != 0.05:
                raise ValueError("residual noise rate mismatch")
            if run["accepted_degree"] != 2:
                raise ValueError("a run did not accept degree two")
            if [stage["decision"] for stage in run["stages"]] != [
                "reject-and-expand",
                "accept",
            ]:
                raise ValueError("unexpected degree decisions")
            if run["final_clean_metrics"]["word_accuracy"] != 1.0:
                raise ValueError("a final model is not exact")
            if signature(run["stages"][-1]) != expected_signature:
                raise ValueError("a run recovered a different integer rule")
            if verification["clean_labels_used_for_degree_selection"]:
                raise ValueError("clean labels leaked into selection")
            if verification["clean_labels_used_for_updates"]:
                raise ValueError("clean labels leaked into training")
            if verification["target_formula_seeded"]:
                raise ValueError("target formula was seeded")
            if not verification[
                "validation_uses_independent_fresh_noisy_labels"
            ]:
                raise ValueError("holdout is not fresh and independent")


def compact(run: dict[str, Any]) -> dict[str, Any]:
    accepted = run["stages"][-1]["checks"][-1]
    true_rate = float(run["config"]["oracle_noise_rate"])
    p_lower = float(accepted["selection_noise_rate_lower"])
    p_upper = float(accepted["selection_noise_rate_upper"])
    return {
        "path": run["_path"],
        "run_sha256": run["_sha256"],
        "base_seed": int(run["config"]["base_seed"]),
        "quadratic_accept_step": int(accepted["stage_step"]),
        "estimated_noise_rate_at_acceptance": float(
            accepted["selection_estimated_noise_rate"]
        ),
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


def common_xor_diagnostics(
    marginal: float,
    residual: float,
) -> dict[str, float]:
    common = (marginal - residual) / (1.0 - 2.0 * residual)
    joint_flip = (
        common * (1.0 - residual) ** 2
        + (1.0 - common) * residual**2
    )
    flip_correlation = (
        (joint_flip - marginal**2)
        / (marginal * (1.0 - marginal))
    )
    common_pair = 2.0 * common * (1.0 - common)
    residual_pair = 2.0 * residual * (1.0 - residual)
    pair_marginal = (
        common_pair
        + residual_pair
        - 2.0 * common_pair * residual_pair
    )
    joint_pair = (
        common_pair * (1.0 - residual_pair) ** 2
        + (1.0 - common_pair) * residual_pair**2
    )
    pair_correlation = (
        (joint_pair - pair_marginal**2)
        / (pair_marginal * (1.0 - pair_marginal))
    )
    return {
        "common_flip_rate": common,
        "within_word_flip_indicator_correlation": flip_correlation,
        "repeated_pair_disagreement_rate": pair_marginal,
        "within_pair_disagreement_indicator_correlation": pair_correlation,
        "bitwise_design_effect_for_12_bits": (
            1.0 + 11.0 * pair_correlation
        ),
    }


def transform_disagreement(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, 0.0, 0.5)
    return 0.5 * (1.0 - np.sqrt(np.maximum(1.0 - 2.0 * clipped, 0.0)))


def interval_arrays(
    count: int,
    total: np.ndarray,
    total_square: np.ndarray,
    delta: float,
) -> tuple[np.ndarray, np.ndarray]:
    mean = total / count
    variance = np.maximum(
        (total_square - total * total / count) / (count - 1),
        0.0,
    )
    log_term = math.log(3.0 / delta)
    radius = (
        np.sqrt(2.0 * variance * log_term / count)
        + 3.0 * log_term / count
    )
    return (
        transform_disagreement(np.maximum(mean - radius, 0.0)),
        transform_disagreement(np.minimum(mean + radius, 0.5)),
    )


def monte_carlo_coverage(
    trials: int,
    word_pair_counts: list[int],
    common: float,
    residual: float,
    true_marginal: float,
    delta: float,
) -> list[dict[str, float | int]]:
    rng = np.random.default_rng(913_577)
    common_pair_rate = 2.0 * common * (1.0 - common)
    residual_pair_rate = 2.0 * residual * (1.0 - residual)
    rows: list[dict[str, float | int]] = []
    for word_pairs in word_pair_counts:
        naive_covered = 0
        robust_covered = 0
        naive_widths: list[float] = []
        robust_widths: list[float] = []
        completed = 0
        while completed < trials:
            chunk = min(250, trials - completed)
            shared = rng.random((chunk, word_pairs)) < common_pair_rate
            residual_counts = rng.binomial(
                12,
                residual_pair_rate,
                size=(chunk, word_pairs),
            )
            disagreements = np.where(
                shared,
                12 - residual_counts,
                residual_counts,
            ).astype(np.float64)
            total_bits = disagreements.sum(axis=1)
            naive_lower, naive_upper = interval_arrays(
                word_pairs * 12,
                total_bits,
                total_bits,
                delta,
            )
            word_fractions = disagreements / 12.0
            robust_total = word_fractions.sum(axis=1)
            robust_square = np.square(word_fractions).sum(axis=1)
            robust_lower, robust_upper = interval_arrays(
                word_pairs,
                robust_total,
                robust_square,
                delta,
            )
            naive_covered += int(
                np.count_nonzero(
                    (naive_lower <= true_marginal)
                    & (true_marginal <= naive_upper)
                )
            )
            robust_covered += int(
                np.count_nonzero(
                    (robust_lower <= true_marginal)
                    & (true_marginal <= robust_upper)
                )
            )
            naive_widths.extend((naive_upper - naive_lower).tolist())
            robust_widths.extend((robust_upper - robust_lower).tolist())
            completed += chunk
        rows.append(
            {
                "independent_word_pairs": word_pairs,
                "trials": trials,
                "nominal_single_interval_coverage": 1.0 - delta,
                "naive_bit_unit_empirical_coverage": (
                    naive_covered / trials
                ),
                "word_cluster_empirical_coverage": (
                    robust_covered / trials
                ),
                "naive_median_interval_width": float(
                    np.median(naive_widths)
                ),
                "word_cluster_median_interval_width": float(
                    np.median(robust_widths)
                ),
            }
        )
    return rows


def plot(
    naive_rows: list[dict[str, Any]],
    robust_rows: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
    independent_mean_total: float,
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
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 3.8))
    counts = [row["independent_word_pairs"] for row in coverage]
    axes[0].plot(
        counts,
        [100 * row["naive_bit_unit_empirical_coverage"] for row in coverage],
        "o-",
        color="#c2415d",
        label="treat 12 bits as independent",
    )
    axes[0].plot(
        counts,
        [100 * row["word_cluster_empirical_coverage"] for row in coverage],
        "o-",
        color="#08745a",
        label="word-cluster interval",
    )
    nominal = 100 * coverage[0]["nominal_single_interval_coverage"]
    axes[0].axhline(
        nominal,
        color="#666666",
        linestyle="--",
        linewidth=1,
        label=f"nominal {nominal:.4f}%",
    )
    axes[0].set_xscale("log")
    axes[0].set_ylim(80, 100.5)
    axes[0].set_xlabel("independent repeated-word pairs")
    axes[0].set_ylabel("empirical interval coverage (%)")
    axes[0].set_title("Bitwise intervals become overconfident")
    axes[0].grid(True, which="both", alpha=0.2)
    axes[0].legend(frameon=False, fontsize=7.5)

    axes[1].plot(
        counts,
        [
            100 * row["naive_median_interval_width"]
            for row in coverage
        ],
        "o-",
        color="#c2415d",
        label="naive bit unit",
    )
    axes[1].plot(
        counts,
        [
            100 * row["word_cluster_median_interval_width"]
            for row in coverage
        ],
        "o-",
        color="#08745a",
        label="word-cluster robust",
    )
    axes[1].set_xscale("log")
    axes[1].set_yscale("log")
    axes[1].set_xlabel("independent repeated-word pairs")
    axes[1].set_ylabel("median p-interval width (percentage points)")
    axes[1].set_title("Honest uncertainty is wider")
    axes[1].grid(True, which="both", alpha=0.2)
    axes[1].legend(frameon=False, fontsize=8)

    methods = ["independent\nword-robust", "correlated\nbit-naive", "correlated\nword-robust"]
    training = [
        9_500,
        np.mean([row["training_examples"] for row in naive_rows]),
        np.mean([row["training_examples"] for row in robust_rows]),
    ]
    holdout = [
        independent_mean_total - 9_500,
        np.mean([row["holdout_words"] for row in naive_rows]),
        np.mean([row["holdout_words"] for row in robust_rows]),
    ]
    x = np.arange(3)
    axes[2].bar(x, training, color="#075985", label="noisy training")
    axes[2].bar(
        x,
        holdout,
        bottom=training,
        color="#f1b24a",
        label="holdout / calibration",
    )
    axes[2].set_xticks(x, methods)
    axes[2].set_ylabel("mean noisy oracle words")
    axes[2].set_title("Correlation has a measurable sample cost")
    axes[2].grid(True, axis="y", alpha=0.2)
    axes[2].legend(frameon=False, fontsize=8)

    fig.suptitle(
        "Word-cluster uncertainty stays valid under strongly correlated flips",
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    naive = [load_run(path) for path in args.naive]
    robust = [load_run(path) for path in args.robust]
    network = json.loads(args.learned_network.read_text(encoding="utf-8"))
    independent = json.loads(
        args.independent_summary.read_text(encoding="utf-8")
    )
    validate(naive, robust, network)
    naive_rows = [compact(run) for run in naive]
    robust_rows = [compact(run) for run in robust]
    diagnostics = common_xor_diagnostics(0.25, 0.05)
    interval_delta = min(
        float(run["config"]["per_interval_failure_probability"])
        for run in robust
    )
    coverage = monte_carlo_coverage(
        args.monte_carlo_trials,
        [250, 500, 1000, 2500, 5000],
        diagnostics["common_flip_rate"],
        0.05,
        0.25,
        interval_delta,
    )
    independent_mean_total = float(
        independent["claims"][
            "mean_sequential_total_noisy_words_all_eight"
        ]
    )
    naive_mean_total = float(
        np.mean([row["total_noisy_oracle_words"] for row in naive_rows])
    )
    robust_mean_total = float(
        np.mean([row["total_noisy_oracle_words"] for row in robust_rows])
    )
    summary = {
        "kind": "word-correlated-noise-cluster-robust-uncertainty",
        "protocol": {
            "marginal_per_bit_flip_rate": 0.25,
            "independent_residual_flip_rate": 0.05,
            **diagnostics,
            "paired_seeds": sorted(
                row["base_seed"] for row in naive_rows
            ),
            "naive_confidence_unit": "individual bit disagreement",
            "robust_confidence_unit": (
                "mean disagreement within one repeated-word pair"
            ),
            "monte_carlo_trials_per_pair_count": args.monte_carlo_trials,
            "monte_carlo_interval_failure_probability": interval_delta,
            "clean_labels_used_for_updates_or_selection": False,
        },
        "claims": {
            "all_24_correlated_runs_select_quadratic": True,
            "all_24_correlated_runs_final_exact": True,
            "all_24_recover_verified_36_term_156_gate_rule": True,
            "naive_true_noise_interval_coverage_at_acceptance": (
                sum(
                    row["noise_interval_contains_true_rate"]
                    for row in naive_rows
                )
                / len(naive_rows)
            ),
            "robust_true_noise_interval_coverage_at_acceptance": (
                sum(
                    row["noise_interval_contains_true_rate"]
                    for row in robust_rows
                )
                / len(robust_rows)
            ),
            "independent_mean_total_noisy_words": independent_mean_total,
            "correlated_naive_mean_total_noisy_words": naive_mean_total,
            "correlated_robust_mean_total_noisy_words": robust_mean_total,
            "robust_correlation_cost_factor_over_independent": (
                robust_mean_total / independent_mean_total
            ),
            "robust_cost_factor_over_naive": (
                robust_mean_total / naive_mean_total
            ),
            "monte_carlo_naive_coverage_at_5000_pairs": coverage[-1][
                "naive_bit_unit_empirical_coverage"
            ],
            "monte_carlo_robust_coverage_at_5000_pairs": coverage[-1][
                "word_cluster_empirical_coverage"
            ],
        },
        "monte_carlo_coverage": coverage,
        "naive_bit_unit_runs": naive_rows,
        "word_cluster_robust_runs": robust_rows,
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    plot(
        naive_rows,
        robust_rows,
        coverage,
        independent_mean_total,
        args.output_figure,
    )
    print(json.dumps(summary["claims"], indent=2))
    print(json.dumps(coverage, indent=2))


if __name__ == "__main__":
    main()
