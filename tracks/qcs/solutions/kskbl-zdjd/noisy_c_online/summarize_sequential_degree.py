"""Summarize confidence-sequential noisy holdout degree discovery."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="append", type=Path, required=True)
    parser.add_argument("--fixed-summary", type=Path, required=True)
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
    runs: list[dict[str, Any]],
    fixed: dict[str, Any],
    network: dict[str, Any],
) -> None:
    if len(runs) != 8:
        raise ValueError("expected eight sequential runs")
    network_signature = tuple(
        sorted(
            (int(row["mask"]), int(row["coefficient"]))
            for row in network["active_features"]
        )
    )
    fixed_seeds = {int(row["base_seed"]) for row in fixed["runs"]}
    sequential_seeds = {int(run["config"]["base_seed"]) for run in runs}
    if not fixed_seeds.issubset(sequential_seeds):
        raise ValueError("the four fixed runs are not paired")
    for run in runs:
        if run["kind"] != (
            "confidence-sequential-noisy-holdout-degree-discovery"
        ):
            raise ValueError("run kind mismatch")
        if run["accepted_degree"] != 2:
            raise ValueError("a run did not select degree two")
        if [stage["decision"] for stage in run["stages"]] != [
            "reject-and-expand",
            "accept",
        ]:
            raise ValueError("unexpected decision sequence")
        if run["final_clean_metrics"]["word_accuracy"] != 1.0:
            raise ValueError("an accepted model is not exact")
        if signature(run["stages"][-1]) != network_signature:
            raise ValueError("an accepted rule differs from the 156-gate rule")
        verification = run["verification"]
        required_true = (
            "training_uses_only_fresh_noisy_labels",
            "validation_uses_independent_fresh_noisy_labels",
            "noise_interval_uses_disjoint_noisy_label_pairs",
            "global_interval_failure_budget_precommitted",
            "clean_full_domain_evaluated_after_selection_locked",
        )
        required_false = (
            "validation_labels_used_for_updates",
            "clean_labels_used_for_updates",
            "clean_labels_used_for_degree_selection",
            "target_formula_seeded",
            "existing_circuit_seeded",
            "target_degree_seeded",
            "input_design_uses_output_labels",
        )
        if not all(verification[key] for key in required_true):
            raise ValueError("required verification marker is false")
        if any(verification[key] for key in required_false):
            raise ValueError("forbidden information path is present")


def compact(run: dict[str, Any]) -> dict[str, Any]:
    linear, quadratic = run["stages"]
    linear_last = linear["checks"][-1]
    quadratic_last = quadratic["checks"][-1]
    return {
        "path": run["_path"],
        "run_sha256": run["_sha256"],
        "base_seed": int(run["config"]["base_seed"]),
        "linear_reject_step": int(linear_last["stage_step"]),
        "linear_holdout_words_for_final_signature": int(
            linear_last["holdout_words"]
        ),
        "linear_excess_interval_at_rejection": [
            float(linear_last["holdout_excess_lower"]),
            float(linear_last["holdout_excess_upper"]),
        ],
        "quadratic_accept_step": int(quadratic_last["stage_step"]),
        "quadratic_holdout_words_for_final_signature": int(
            quadratic_last["holdout_words"]
        ),
        "quadratic_excess_interval_at_acceptance": [
            float(quadratic_last["holdout_excess_lower"]),
            float(quadratic_last["holdout_excess_upper"]),
        ],
        "training_examples": int(run["cumulative_training_examples"]),
        "holdout_words_across_all_signatures": int(
            run["cumulative_holdout_words"]
        ),
        "total_noisy_oracle_words": int(
            run["cumulative_noisy_oracle_words"]
        ),
        "final_clean_word_accuracy": float(
            run["final_clean_metrics"]["word_accuracy"]
        ),
        "active_integer_coefficients": int(
            quadratic_last["active_integer_coefficients"]
        ),
    }


def plot(
    rows: list[dict[str, Any]],
    fixed_rows: list[dict[str, Any]],
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
    indexed = {row["base_seed"]: row for row in rows}
    paired_fixed = sorted(fixed_rows, key=lambda row: row["base_seed"])
    seeds = [row["base_seed"] for row in paired_fixed]
    x = np.arange(len(seeds))
    width = 0.36
    fixed_totals = [
        row["total_noisy_oracle_words"] for row in paired_fixed
    ]
    sequential_totals = [
        indexed[seed]["total_noisy_oracle_words"] for seed in seeds
    ]
    axes[0].bar(
        x - width / 2,
        fixed_totals,
        width,
        color="#b7791f",
        label="fixed 4,096-word checks",
    )
    axes[0].bar(
        x + width / 2,
        sequential_totals,
        width,
        color="#08745a",
        label="confidence-sequential",
    )
    axes[0].set_xticks(x, [str(seed) for seed in seeds], rotation=20)
    axes[0].set_ylabel("total noisy oracle words")
    axes[0].set_title("Matched seeds use far fewer labels")
    axes[0].grid(True, axis="y", alpha=0.2)
    axes[0].legend(frameon=False, fontsize=8)

    all_seeds = [row["base_seed"] for row in rows]
    training = np.array([row["training_examples"] for row in rows])
    holdout = np.array(
        [row["holdout_words_across_all_signatures"] for row in rows]
    )
    all_x = np.arange(len(rows))
    axes[1].bar(
        all_x,
        training,
        color="#075985",
        label="noisy training",
    )
    axes[1].bar(
        all_x,
        holdout,
        bottom=training,
        color="#f1b24a",
        label="adaptive holdout",
    )
    axes[1].axhline(
        np.mean(
            [row["total_noisy_oracle_words"] for row in fixed_rows]
        ),
        color="#9a4d08",
        linestyle="--",
        linewidth=1.2,
        label="fixed-check mean",
    )
    axes[1].set_xticks(
        all_x,
        [str(seed)[:3] for seed in all_seeds],
    )
    axes[1].set_xlabel("seed prefix")
    axes[1].set_ylabel("noisy oracle words")
    axes[1].set_title("Eight-run cost accounting")
    axes[1].grid(True, axis="y", alpha=0.2)
    axes[1].legend(frameon=False, fontsize=8)

    for index, row in enumerate(rows):
        for interval_key, color, marker, offset in (
            (
                "linear_excess_interval_at_rejection",
                "#c2415d",
                "X",
                0.11,
            ),
            (
                "quadratic_excess_interval_at_acceptance",
                "#08745a",
                "o",
                -0.11,
            ),
        ):
            lower, upper = row[interval_key]
            midpoint = 0.5 * (lower + upper)
            axes[2].errorbar(
                midpoint * 100,
                index + offset,
                xerr=np.array(
                    [[(midpoint - lower) * 100], [(upper - midpoint) * 100]]
                ),
                fmt=marker,
                color=color,
                markersize=5.5,
                capsize=2,
                linewidth=1,
            )
    axes[2].axvspan(-3.5, 3.5, color="#d1fae5", alpha=0.7)
    axes[2].axvline(15, color="#9f1239", linestyle="--", linewidth=1)
    axes[2].set_yticks(
        np.arange(len(rows)),
        [str(seed)[:3] for seed in all_seeds],
    )
    axes[2].set_xlabel("confidence interval for excess disagreement (pp)")
    axes[2].set_ylabel("seed prefix")
    axes[2].set_title("Every noisy decision is confidence-separated")
    axes[2].grid(True, axis="x", alpha=0.2)
    axes[2].invert_yaxis()

    fig.suptitle(
        "Confidence-sequential holdout removes most validation cost",
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    runs = [load_run(path) for path in args.run]
    fixed = json.loads(args.fixed_summary.read_text(encoding="utf-8"))
    network = json.loads(args.learned_network.read_text(encoding="utf-8"))
    validate(runs, fixed, network)
    rows = [compact(run) for run in runs]
    indexed = {row["base_seed"]: row for row in rows}
    fixed_rows = fixed["runs"]
    paired_sequential = [
        indexed[int(row["base_seed"])] for row in fixed_rows
    ]
    fixed_mean_holdout = float(
        np.mean(
            [row["independent_noisy_holdout_words"] for row in fixed_rows]
        )
    )
    sequential_paired_mean_holdout = float(
        np.mean(
            [
                row["holdout_words_across_all_signatures"]
                for row in paired_sequential
            ]
        )
    )
    fixed_mean_total = float(
        np.mean([row["total_noisy_oracle_words"] for row in fixed_rows])
    )
    sequential_paired_mean_total = float(
        np.mean(
            [row["total_noisy_oracle_words"] for row in paired_sequential]
        )
    )
    summary = {
        "kind": "confidence-sequential-noisy-holdout-ablation",
        "protocol": {
            "paired_fixed_seeds": sorted(
                int(row["base_seed"]) for row in fixed_rows
            ),
            "additional_sequential_seeds": sorted(
                set(row["base_seed"] for row in rows)
                - set(int(row["base_seed"]) for row in fixed_rows)
            ),
            "holdout_look_sizes": runs[0]["config"]["holdout_look_sizes"],
            "precommitted_global_interval_failure_probability": (
                runs[0]["config"]["global_failure_probability"]
            ),
            "empirical_bernstein_per_interval_probability": (
                runs[0]["config"]["per_interval_failure_probability"]
            ),
            "acceptance_excess_band": runs[0]["config"]["accept_gap"],
            "rejection_excess_threshold": runs[0]["config"]["reject_gap"],
            "coefficient_signature_checks_for_acceptance": (
                runs[0]["config"]["stable_signature_checks"]
            ),
            "persistent_training_checks_for_degree_rejection": (
                runs[0]["config"]["stable_signature_checks"]
            ),
            "clean_labels_used_for_updates_or_selection": False,
        },
        "claims": {
            "all_eight_runs_reject_linear_and_accept_quadratic": True,
            "all_eight_final_models_exact": True,
            "all_eight_recover_verified_36_term_156_gate_rule": True,
            "linear_rejection_steps": [
                row["linear_reject_step"] for row in rows
            ],
            "quadratic_acceptance_steps": [
                row["quadratic_accept_step"] for row in rows
            ],
            "quadratic_final_signature_4096_word_runs": sum(
                row["quadratic_holdout_words_for_final_signature"] == 4096
                for row in rows
            ),
            "quadratic_final_signature_8192_word_runs": sum(
                row["quadratic_holdout_words_for_final_signature"] == 8192
                for row in rows
            ),
            "mean_sequential_training_examples_all_eight": float(
                np.mean([row["training_examples"] for row in rows])
            ),
            "mean_sequential_holdout_words_all_eight": float(
                np.mean(
                    [
                        row["holdout_words_across_all_signatures"]
                        for row in rows
                    ]
                )
            ),
            "mean_sequential_total_noisy_words_all_eight": float(
                np.mean(
                    [row["total_noisy_oracle_words"] for row in rows]
                )
            ),
            "paired_fixed_mean_holdout_words": fixed_mean_holdout,
            "paired_sequential_mean_holdout_words": (
                sequential_paired_mean_holdout
            ),
            "paired_holdout_reduction_factor": (
                fixed_mean_holdout / sequential_paired_mean_holdout
            ),
            "paired_fixed_mean_total_noisy_words": fixed_mean_total,
            "paired_sequential_mean_total_noisy_words": (
                sequential_paired_mean_total
            ),
            "paired_total_noisy_word_reduction_factor": (
                fixed_mean_total / sequential_paired_mean_total
            ),
        },
        "sequential_runs": rows,
        "paired_fixed_runs": fixed_rows,
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    plot(rows, fixed_rows, args.output_figure)
    print(json.dumps(summary["claims"], indent=2))


if __name__ == "__main__":
    main()
