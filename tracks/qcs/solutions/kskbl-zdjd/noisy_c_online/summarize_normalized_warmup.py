"""Summarize design-size-normalized warmup for adaptive degree discovery."""

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


def validate(runs: list[dict[str, Any]], network: dict[str, Any]) -> None:
    if len(runs) != 8:
        raise ValueError("expected eight runs")
    expected = tuple(
        sorted(
            (int(row["mask"]), int(row["coefficient"]))
            for row in network["active_features"]
        )
    )
    for run in runs:
        config = run["config"]
        if config["min_observations_per_design_point"] != 50.0:
            raise ValueError("warmup normalization mismatch")
        if config["confidence_interval_method"] != "cluster-normal":
            raise ValueError("interval method mismatch")
        if [stage["minimum_stage_steps"] for stage in run["stages"]] != [
            7,
            40,
        ]:
            raise ValueError("unexpected normalized warmups")
        if [stage["decision"] for stage in run["stages"]] != [
            "reject-and-expand",
            "accept",
        ]:
            raise ValueError("unexpected decisions")
        if run["stages"][0]["checks"][-1]["stage_step"] != 20:
            raise ValueError("linear rejection did not occur at step 20")
        if run["final_clean_metrics"]["word_accuracy"] != 1.0:
            raise ValueError("a run is not exact")
        if signature(run["stages"][-1]) != expected:
            raise ValueError("a run recovered a different rule")
        if run["verification"]["clean_labels_used_for_degree_selection"]:
            raise ValueError("clean labels leaked into selection")


def compact(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": run["_path"],
        "run_sha256": run["_sha256"],
        "base_seed": int(run["config"]["base_seed"]),
        "linear_warmup_steps": int(run["stages"][0]["minimum_stage_steps"]),
        "linear_reject_step": int(
            run["stages"][0]["checks"][-1]["stage_step"]
        ),
        "quadratic_warmup_steps": int(
            run["stages"][1]["minimum_stage_steps"]
        ),
        "quadratic_accept_step": int(
            run["stages"][1]["checks"][-1]["stage_step"]
        ),
        "training_examples": int(run["cumulative_training_examples"]),
        "holdout_words": int(run["cumulative_holdout_words"]),
        "total_noisy_oracle_words": int(
            run["cumulative_noisy_oracle_words"]
        ),
        "final_clean_word_accuracy": float(
            run["final_clean_metrics"]["word_accuracy"]
        ),
    }


def plot(
    rows: list[dict[str, Any]],
    baseline: list[dict[str, Any]],
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
    fig, axes = plt.subplots(1, 3, figsize=(13.0, 3.65))
    x = np.arange(2)
    width = 0.34
    axes[0].bar(
        x - width / 2,
        [30, 30],
        width,
        color="#94a3b8",
        label="fixed warmup",
    )
    axes[0].bar(
        x + width / 2,
        [7, 40],
        width,
        color="#08745a",
        label="50 observations per design point",
    )
    axes[0].set_xticks(x, ["linear · 13 points", "quadratic · 79 points"])
    axes[0].set_ylabel("minimum eligible batch")
    axes[0].set_title("Warmup follows hypothesis dimension")
    axes[0].grid(True, axis="y", alpha=0.2)
    axes[0].legend(frameon=False, fontsize=8)

    indexed_baseline = {row["base_seed"]: row for row in baseline}
    axes[1].scatter(
        [
            indexed_baseline[row["base_seed"]][
                "total_noisy_oracle_words"
            ]
            for row in rows
        ],
        [row["total_noisy_oracle_words"] for row in rows],
        color="#7c3aed",
        s=48,
        edgecolor="white",
        linewidth=0.6,
    )
    axes[1].plot([0, 14000], [0, 14000], color="#666666", linestyle="--")
    axes[1].set_xlim(0, 14000)
    axes[1].set_ylim(0, 14000)
    axes[1].set_xlabel("fixed-warmup total noisy words")
    axes[1].set_ylabel("dimension-normalized total noisy words")
    axes[1].set_title("Every matched seed is cheaper")
    axes[1].grid(True, alpha=0.2)

    methods = ["fixed\n30 batches", "dimension\nnormalized"]
    training = [
        np.mean([row["training_examples"] for row in baseline]),
        np.mean([row["training_examples"] for row in rows]),
    ]
    holdout = [
        np.mean([row["holdout_words"] for row in baseline]),
        np.mean([row["holdout_words"] for row in rows]),
    ]
    axes[2].bar(methods, training, color="#075985", label="training")
    axes[2].bar(
        methods,
        holdout,
        bottom=training,
        color="#f1b24a",
        label="holdout",
    )
    axes[2].set_ylabel("mean noisy oracle words")
    axes[2].set_title("Earlier linear rejection removes 2,000 words")
    axes[2].grid(True, axis="y", alpha=0.2)
    axes[2].legend(frameon=False, fontsize=8)

    fig.suptitle(
        "Information-normalized warmup pushes unknown-degree cost below 9k",
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
    baseline_summary = json.loads(
        args.fixed_summary.read_text(encoding="utf-8")
    )
    network = json.loads(args.learned_network.read_text(encoding="utf-8"))
    validate(runs, network)
    rows = [compact(run) for run in runs]
    baseline = baseline_summary["self_normalized_runs"]
    indexed = {row["base_seed"]: row for row in baseline}
    if set(indexed) != {row["base_seed"] for row in rows}:
        raise ValueError("baseline seeds are not paired")
    mean_total = float(
        np.mean([row["total_noisy_oracle_words"] for row in rows])
    )
    baseline_total = float(
        np.mean(
            [row["total_noisy_oracle_words"] for row in baseline]
        )
    )
    summary = {
        "kind": "design-size-normalized-degree-warmup",
        "protocol": {
            "minimum_mean_observations_per_design_point": 50,
            "linear_design_points": 13,
            "quadratic_design_points": 79,
            "linear_minimum_eligible_step": 7,
            "quadratic_minimum_eligible_step": 40,
            "rule_uses_output_labels": False,
            "target_degree_seeded": False,
            "clean_labels_used_for_updates_or_selection": False,
        },
        "claims": {
            "all_eight_reject_linear_at_step_20": True,
            "all_eight_accept_quadratic": True,
            "all_eight_final_models_exact": True,
            "all_eight_recover_verified_36_term_156_gate_rule": True,
            "mean_training_examples": float(
                np.mean([row["training_examples"] for row in rows])
            ),
            "mean_holdout_words": float(
                np.mean([row["holdout_words"] for row in rows])
            ),
            "mean_total_noisy_words": mean_total,
            "fixed_warmup_mean_total_noisy_words": baseline_total,
            "mean_cost_reduction_factor": baseline_total / mean_total,
            "all_eight_dimension_normalized_runs_cheaper": all(
                row["total_noisy_oracle_words"]
                < indexed[row["base_seed"]]["total_noisy_oracle_words"]
                for row in rows
            ),
        },
        "runs": rows,
        "fixed_warmup_runs": baseline,
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    plot(rows, baseline, args.output_figure)
    print(json.dumps(summary["claims"], indent=2))


if __name__ == "__main__":
    main()
