"""Audit and summarize noisy holdout-based polynomial-degree discovery."""

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


def coefficient_signature(stage: dict[str, Any]) -> tuple[tuple[int, int], ...]:
    return tuple(
        sorted(
            (
                int(row["mask"]),
                int(row["coefficient"]),
            )
            for row in stage["final_integer_coefficients"]
            if int(row["coefficient"]) != 0
        )
    )


def validate(
    runs: list[dict[str, Any]],
    learned_network: dict[str, Any],
) -> None:
    if len(runs) != 4:
        raise ValueError("expected four independent runs")
    expected_signature = tuple(
        sorted(
            (int(row["mask"]), int(row["coefficient"]))
            for row in learned_network["active_features"]
        )
    )
    for run in runs:
        verification = run["verification"]
        if run["accepted_degree"] != 2:
            raise ValueError("a run did not select degree two")
        if [stage["degree"] for stage in run["stages"]] != [1, 2]:
            raise ValueError("unexpected sequence of tested degrees")
        if [stage["decision"] for stage in run["stages"]] != [
            "reject-and-expand",
            "accept",
        ]:
            raise ValueError("unexpected degree decisions")
        if run["final_clean_metrics"]["word_accuracy"] != 1.0:
            raise ValueError("accepted model is not exact")
        if coefficient_signature(run["stages"][-1]) != expected_signature:
            raise ValueError("accepted rule differs from the verified network")
        required_true = (
            "training_uses_only_fresh_noisy_labels",
            "validation_uses_independent_fresh_noisy_labels",
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
            raise ValueError("a required verification marker is false")
        if any(verification[key] for key in required_false):
            raise ValueError("a forbidden information path is present")
        if any(stage["decision_uses_clean_labels"] for stage in run["stages"]):
            raise ValueError("clean labels leaked into a stage decision")
        if run["stages"][0]["design"]["size"] != 13:
            raise ValueError("linear design is not minimally full rank")
        if run["stages"][1]["design"]["size"] != 79:
            raise ValueError("quadratic design is not minimally full rank")


def compact(run: dict[str, Any]) -> dict[str, Any]:
    linear, quadratic = run["stages"]
    linear_last = linear["checks"][-1]
    quadratic_last = quadratic["checks"][-1]
    validation_words = int(
        run["config"]["validation_words_per_check"]
        * sum(len(stage["checks"]) for stage in run["stages"])
    )
    training_examples = int(run["cumulative_training_examples"])
    return {
        "path": run["_path"],
        "run_sha256": run["_sha256"],
        "base_seed": int(run["config"]["base_seed"]),
        "linear_decision": linear["decision"],
        "linear_decision_step": int(linear_last["stage_step"]),
        "linear_holdout_gap_at_decision": float(
            linear_last["holdout_disagreement_gap"]
        ),
        "quadratic_decision": quadratic["decision"],
        "quadratic_decision_step": int(quadratic_last["stage_step"]),
        "quadratic_holdout_gap_at_decision": float(
            quadratic_last["holdout_disagreement_gap"]
        ),
        "quadratic_rounding_residual_at_decision": float(
            quadratic_last["maximum_rounding_residual"]
        ),
        "estimated_noise_rate_at_acceptance": float(
            quadratic_last["estimated_noise_rate"]
        ),
        "training_examples": training_examples,
        "independent_noisy_holdout_words": validation_words,
        "total_noisy_oracle_words": training_examples + validation_words,
        "final_clean_word_accuracy": float(
            run["final_clean_metrics"]["word_accuracy"]
        ),
        "active_integer_coefficients": int(
            quadratic_last["active_integer_coefficients"]
        ),
    }


def plot(runs: list[dict[str, Any]], output: Path) -> None:
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )
    fig, axes = plt.subplots(1, 3, figsize=(13.4, 3.75))
    degree_colors = {1: "#c2415d", 2: "#08745a"}

    for run_index, run in enumerate(runs):
        for stage in run["stages"]:
            checks = stage["checks"]
            degree = int(stage["degree"])
            axes[0].plot(
                [row["cumulative_training_examples"] for row in checks],
                [row["holdout_disagreement_gap"] * 100 for row in checks],
                color=degree_colors[degree],
                alpha=0.48,
                linewidth=1.5,
                label=(
                    f"degree {degree}"
                    if run_index == 0
                    else None
                ),
            )
    axes[0].axhspan(-1, 1, color="#d1fae5", alpha=0.8)
    axes[0].axhline(15, color="#9f1239", linestyle="--", linewidth=1)
    axes[0].set_xlabel("cumulative noisy training examples")
    axes[0].set_ylabel("holdout excess over estimated noise (pp)")
    axes[0].set_title("Fresh-noise holdout separates fit from noise")
    axes[0].grid(True, alpha=0.2)
    axes[0].legend(frameon=False)

    for degree, marker in ((1, "X"), (2, "o")):
        endpoints = [
            next(
                stage for stage in run["stages"]
                if stage["degree"] == degree
            )["checks"][-1]
            for run in runs
        ]
        axes[1].scatter(
            [row["maximum_rounding_residual"] for row in endpoints],
            [row["holdout_disagreement_gap"] * 100 for row in endpoints],
            s=62,
            marker=marker,
            color=degree_colors[degree],
            edgecolor="white",
            linewidth=0.7,
            label=(
                "linear: reject"
                if degree == 1
                else "quadratic: accept"
            ),
            zorder=3,
        )
    axes[1].axvspan(0, 0.10, color="#d1fae5", alpha=0.55)
    axes[1].axhspan(-1, 1, color="#d1fae5", alpha=0.55)
    axes[1].axhline(15, color="#9f1239", linestyle="--", linewidth=1)
    axes[1].set_xlabel("maximum coefficient-rounding residual")
    axes[1].set_ylabel("holdout excess at decision (pp)")
    axes[1].set_title("Decision uses two independent safeguards")
    axes[1].grid(True, alpha=0.2)
    axes[1].legend(frameon=False, loc="center left")

    training = np.mean(
        [run["cumulative_training_examples"] for run in runs]
    )
    holdout = np.mean(
        [
            run["config"]["validation_words_per_check"]
            * sum(len(stage["checks"]) for stage in run["stages"])
            for run in runs
        ]
    )
    names = [
        "D-optimal\nknown degree",
        "adaptive\ntraining only",
        "adaptive\nall noisy words",
        "uniform\nknown degree",
    ]
    costs = [4_125, training, training + holdout, 243_875]
    colors = ["#075985", "#08745a", "#b7791f", "#8b5cf6"]
    bars = axes[2].bar(names, costs, color=colors, width=0.68)
    axes[2].set_yscale("log")
    axes[2].set_ylim(2_500, 400_000)
    axes[2].set_ylabel("mean noisy oracle words (log scale)")
    axes[2].set_title("Removing the degree prior has a visible cost")
    axes[2].grid(True, axis="y", which="both", alpha=0.2)
    for bar, cost in zip(bars, costs, strict=True):
        axes[2].text(
            bar.get_x() + bar.get_width() / 2,
            cost * 1.10,
            f"{cost:,.0f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    fig.suptitle(
        "The learner discovers that a linear model is insufficient",
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
    learned_network = json.loads(
        args.learned_network.read_text(encoding="utf-8")
    )
    validate(runs, learned_network)
    rows = [compact(run) for run in runs]
    true_noise_rate = float(runs[0]["config"]["oracle_noise_rate"])
    noise_errors = [
        abs(row["estimated_noise_rate_at_acceptance"] - true_noise_rate)
        for row in rows
    ]
    summary = {
        "kind": "fresh-noise-holdout-adaptive-degree-discovery",
        "protocol": {
            "candidate_degrees": [1, 2, 3],
            "learner_initial_noise_rate": 0.10,
            "oracle_noise_rate": true_noise_rate,
            "batch_size": 100,
            "fresh_noisy_holdout_words_per_check": 4096,
            "acceptance_rule": (
                "three checks with absolute holdout excess below 0.01 "
                "and maximum coefficient-rounding residual below 0.10"
            ),
            "early_rejection_rule": (
                "three checks with holdout excess above 0.15"
            ),
            "clean_labels_used_for_updates_or_selection": False,
            "target_degree_seeded": False,
            "target_formula_seeded": False,
        },
        "claims": {
            "all_four_runs_reject_linear_at_step_40": all(
                row["linear_decision_step"] == 40 for row in rows
            ),
            "all_four_runs_accept_quadratic": True,
            "quadratic_acceptance_steps": [
                row["quadratic_decision_step"] for row in rows
            ],
            "all_four_final_models_exact": True,
            "all_four_recover_verified_36_term_rule": True,
            "verified_rule_compiles_to_gates": 156,
            "mean_training_examples": float(
                np.mean([row["training_examples"] for row in rows])
            ),
            "mean_independent_noisy_holdout_words": float(
                np.mean(
                    [
                        row["independent_noisy_holdout_words"]
                        for row in rows
                    ]
                )
            ),
            "mean_total_noisy_oracle_words": float(
                np.mean(
                    [row["total_noisy_oracle_words"] for row in rows]
                )
            ),
            "mean_absolute_noise_rate_error_at_acceptance": float(
                np.mean(noise_errors)
            ),
            "maximum_absolute_noise_rate_error_at_acceptance": float(
                np.max(noise_errors)
            ),
        },
        "runs": rows,
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    plot(runs, args.output_figure)
    print(json.dumps(summary["claims"], indent=2))


if __name__ == "__main__":
    main()
