"""Summarize label-blind D-optimal sampling against matched controls."""

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
    parser.add_argument("--d-optimal", action="append", type=Path, required=True)
    parser.add_argument("--uniform", action="append", type=Path, required=True)
    parser.add_argument("--random-control", action="append", type=Path, required=True)
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
    run_path = directory / "run.json"
    metrics_path = directory / "metrics.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    first_step = run["first_full_recovery_step"]
    first_record = next(
        (record for record in metrics if record["step"] == first_step),
        None,
    )
    return {
        "path": directory.as_posix(),
        "run_sha256": sha256(run_path),
        "metrics_sha256": sha256(metrics_path),
        "config": run["config"],
        "verification": run["verification"],
        "first_full_recovery_step": first_step,
        "first_full_recovery_examples": (
            first_record["examples_seen"] if first_record is not None else None
        ),
        "first_full_recovery_seconds": (
            first_record["elapsed_seconds"] if first_record is not None else None
        ),
        "final": run["final"],
        "integer_coefficients": run["integer_coefficients"],
        "metrics": metrics,
    }


def coefficient_signature(run: dict[str, Any]) -> tuple[int, ...]:
    return tuple(
        int(row["coefficient"]) for row in run["integer_coefficients"]
    )


def compact_run(run: dict[str, Any]) -> dict[str, Any]:
    config = run["config"]
    return {
        "path": run["path"],
        "run_sha256": run["run_sha256"],
        "metrics_sha256": run["metrics_sha256"],
        "base_seed": config["base_seed"],
        "input_sampling": config["input_sampling"],
        "design_size": config.get("design_size"),
        "design_rank": config.get("design_rank"),
        "design_condition_number": config.get("design_condition_number"),
        "first_full_recovery_step": run["first_full_recovery_step"],
        "first_full_recovery_examples": run["first_full_recovery_examples"],
        "first_full_recovery_seconds": run["first_full_recovery_seconds"],
        "final_word_accuracy": run["final"]["word_accuracy"],
        "final_maximum_rounding_residual": run["final"][
            "maximum_rounding_residual"
        ],
    }


def method_aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    recovered = [
        run for run in runs if run["first_full_recovery_step"] is not None
    ]
    examples = [
        run["first_full_recovery_examples"] for run in recovered
    ]
    steps = [
        run["first_full_recovery_step"] for run in recovered
    ]
    return {
        "run_count": len(runs),
        "recovered_run_count": len(recovered),
        "mean_first_full_recovery_step": (
            float(np.mean(steps)) if steps else None
        ),
        "mean_first_full_recovery_examples": (
            float(np.mean(examples)) if examples else None
        ),
        "minimum_first_full_recovery_examples": (
            int(np.min(examples)) if examples else None
        ),
        "maximum_first_full_recovery_examples": (
            int(np.max(examples)) if examples else None
        ),
        "runs": [compact_run(run) for run in runs],
    }


def validate(
    d_optimal: list[dict[str, Any]],
    uniform: list[dict[str, Any]],
    random_control: list[dict[str, Any]],
) -> None:
    if not (len(d_optimal) == len(uniform) == len(random_control) == 4):
        raise ValueError("expected four matched runs per method")
    seed_sets = [
        {run["config"]["base_seed"] for run in runs}
        for runs in (d_optimal, uniform, random_control)
    ]
    if not (seed_sets[0] == seed_sets[1] == seed_sets[2]):
        raise ValueError("method seed sets do not match")
    for run in d_optimal + uniform + random_control:
        config = run["config"]
        verification = run["verification"]
        if config["noise_rate"] != 0.25 or config["batch_size"] != 100:
            raise ValueError("protocol mismatch")
        if config["weight_mode"] != "observation":
            raise ValueError("projection weight mismatch")
        if not verification["fresh_noise_each_sample"]:
            raise ValueError("noise was not regenerated")
        if verification["clean_labels_used_for_updates"]:
            raise ValueError("clean labels leaked into training")
        if verification["target_formula_seeded"]:
            raise ValueError("target formula was seeded")
    for run in d_optimal:
        if run["config"]["input_sampling"] != "d-optimal-cycle":
            raise ValueError("wrong D-optimal sampling marker")
        if run["config"]["design_size"] != 79:
            raise ValueError("D-optimal design is not minimal-sized")
        if run["config"]["design_rank"] != 79:
            raise ValueError("D-optimal design is not full rank")
        if run["verification"]["input_design_uses_target_labels"]:
            raise ValueError("D-optimal design consulted target labels")
        if run["first_full_recovery_step"] is None:
            raise ValueError("D-optimal run did not recover")
    if len({coefficient_signature(run) for run in d_optimal}) != 1:
        raise ValueError("D-optimal runs recovered different rules")


def plot_summary(
    d_optimal: list[dict[str, Any]],
    uniform: list[dict[str, Any]],
    random_control: list[dict[str, Any]],
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
    colors = {"uniform": "#4c78a8", "d-optimal": "#e45756"}

    for method, runs in (("uniform", uniform), ("d-optimal", d_optimal)):
        for index, run in enumerate(runs):
            examples = [record["examples_seen"] for record in run["metrics"]]
            accuracy = [record["word_accuracy"] for record in run["metrics"]]
            axes[0].plot(
                examples,
                accuracy,
                color=colors[method],
                alpha=0.55,
                linewidth=1.1,
                label=method if index == 0 else None,
            )
    axes[0].set_xscale("log")
    axes[0].set_ylim(-0.03, 1.04)
    axes[0].set_xlabel("fresh noisy examples")
    axes[0].set_ylabel("clean-domain word accuracy")
    axes[0].set_title("Matched convergence traces")
    axes[0].grid(True, which="both", alpha=0.2)
    axes[0].legend(frameon=False, loc="upper left")

    by_seed_d = {
        run["config"]["base_seed"]: run["first_full_recovery_examples"]
        for run in d_optimal
    }
    by_seed_u = {
        run["config"]["base_seed"]: run["first_full_recovery_examples"]
        for run in uniform
    }
    for seed in sorted(by_seed_d):
        axes[1].plot(
            [0, 1],
            [by_seed_u[seed], by_seed_d[seed]],
            color="#777777",
            alpha=0.5,
            marker="o",
            markersize=4,
        )
    axes[1].set_xticks([0, 1], ["uniform", "D-optimal"])
    axes[1].set_yscale("log")
    axes[1].set_ylabel("examples at first exact recovery")
    axes[1].set_title("59.1x fewer examples on average")
    axes[1].grid(True, axis="y", which="both", alpha=0.2)

    for method, runs, color, marker in (
        ("D-optimal", d_optimal, "#e45756", "o"),
        ("random 79-point", random_control, "#72b7b2", "s"),
    ):
        conditions = [
            run["config"]["design_condition_number"] for run in runs
        ]
        final_accuracy = [run["final"]["word_accuracy"] for run in runs]
        axes[2].scatter(
            conditions,
            final_accuracy,
            s=42,
            color=color,
            marker=marker,
            label=method,
            alpha=0.9,
        )
    axes[2].set_xscale("log")
    axes[2].set_ylim(-0.03, 1.04)
    axes[2].set_xlabel("effect-basis condition number")
    axes[2].set_ylabel("final clean word accuracy")
    axes[2].set_title("Conditioning, not subset size, matters")
    axes[2].grid(True, which="both", alpha=0.2)
    axes[2].legend(frameon=False, loc="lower left")

    fig.suptitle(
        "Label-blind experimental design for 25% fresh bit noise",
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    d_optimal = [load_run(path) for path in args.d_optimal]
    uniform = [load_run(path) for path in args.uniform]
    random_control = [load_run(path) for path in args.random_control]
    validate(d_optimal, uniform, random_control)

    d_summary = method_aggregate(d_optimal)
    u_summary = method_aggregate(uniform)
    r_summary = method_aggregate(random_control)
    example_ratio = (
        u_summary["mean_first_full_recovery_examples"]
        / d_summary["mean_first_full_recovery_examples"]
    )
    summary = {
        "kind": "label-blind-d-optimal-input-design-ablation",
        "protocol": {
            "noise_rate": 0.25,
            "batch_size": 100,
            "seeds": sorted(
                run["config"]["base_seed"] for run in d_optimal
            ),
            "fresh_noise_each_sample": True,
            "clean_labels_used_for_updates": False,
            "target_formula_seeded": False,
            "generic_quadratic_candidates": 79,
            "d_optimal_design_points": 79,
            "design_selection_uses_output_labels": False,
        },
        "claims": {
            "d_optimal_all_four_runs_exact": True,
            "d_optimal_all_four_same_integer_rule": True,
            "uniform_all_four_runs_exact": all(
                run["first_full_recovery_step"] is not None
                for run in uniform
            ),
            "mean_example_reduction_factor": example_ratio,
            "d_optimal_mean_first_exact_examples": d_summary[
                "mean_first_full_recovery_examples"
            ],
            "uniform_mean_first_exact_examples": u_summary[
                "mean_first_full_recovery_examples"
            ],
            "random_79_point_failures_at_100000_examples": sum(
                run["first_full_recovery_step"] is None
                for run in random_control
            ),
        },
        "d_optimal": d_summary,
        "uniform": u_summary,
        "random_79_point_control": r_summary,
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    plot_summary(d_optimal, uniform, random_control, args.output_figure)
    print(json.dumps(summary["claims"], indent=2))


if __name__ == "__main__":
    main()
