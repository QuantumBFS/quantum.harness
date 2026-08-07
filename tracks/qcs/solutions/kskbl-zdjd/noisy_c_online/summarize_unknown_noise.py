"""Summarize quadratic discovery when the learner is not told the noise rate."""

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
    parser.add_argument("--known", action="append", type=Path, required=True)
    parser.add_argument("--estimated", action="append", type=Path, required=True)
    parser.add_argument("--stress", action="append", type=Path, required=True)
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
        "first_record": first_record,
        "final": run["final"],
        "integer_coefficients": tuple(
            int(row["coefficient"]) for row in run["integer_coefficients"]
        ),
        "metrics": metrics,
    }


def key(run: dict[str, Any]) -> tuple[float, int]:
    config = run["config"]
    return float(config["noise_rate"]), int(config["base_seed"])


def validate(
    known: list[dict[str, Any]],
    estimated: list[dict[str, Any]],
    stress: list[dict[str, Any]],
) -> None:
    if len(known) != 12 or len(estimated) != 12 or len(stress) != 2:
        raise ValueError("expected twelve paired runs and two stress runs")
    if {key(run) for run in known} != {key(run) for run in estimated}:
        raise ValueError("known and estimated runs are not paired")
    for run in known + estimated + stress:
        config = run["config"]
        verification = run["verification"]
        if config["input_sampling"] != "d-optimal-cycle":
            raise ValueError("input design mismatch")
        if config["design_size"] != 79 or config["design_rank"] != 79:
            raise ValueError("design is not minimal full rank")
        if run["first_full_recovery_step"] is None:
            raise ValueError("a run did not reach exact recovery")
        if run["final"]["word_accuracy"] != 1.0:
            raise ValueError("a run did not end exact")
        if not verification["fresh_noise_each_sample"]:
            raise ValueError("noise was not regenerated")
        if verification["clean_labels_used_for_updates"]:
            raise ValueError("clean labels leaked into updates")
        if verification["target_formula_seeded"]:
            raise ValueError("target formula was seeded")
    for run in known:
        if run["config"].get("learner_noise_mode", "known") != "known":
            raise ValueError("known-noise run marker mismatch")
        if not run["verification"].get(
            "learner_receives_oracle_noise_rate",
            True,
        ):
            raise ValueError("known-noise verification marker mismatch")
    for run in estimated + stress:
        if run["config"]["learner_noise_mode"] != "pairwise-estimated":
            raise ValueError("estimated-noise run marker mismatch")
        if run["verification"]["learner_receives_oracle_noise_rate"]:
            raise ValueError("oracle noise rate leaked to learner")
    if len(
        {run["integer_coefficients"] for run in known + estimated + stress}
    ) != 1:
        raise ValueError("runs recovered different integer rules")


def compact(run: dict[str, Any]) -> dict[str, Any]:
    config = run["config"]
    true_rate = float(config["noise_rate"])
    first_estimate = float(
        run["first_record"].get("estimated_noise_rate", true_rate)
    )
    return {
        "path": run["path"],
        "run_sha256": run["run_sha256"],
        "metrics_sha256": run["metrics_sha256"],
        "true_noise_rate": true_rate,
        "base_seed": int(config["base_seed"]),
        "initial_noise_rate": config.get("initial_noise_rate"),
        "first_full_recovery_step": run["first_full_recovery_step"],
        "first_full_recovery_examples": run["first_record"]["examples_seen"],
        "estimated_noise_rate_at_first_recovery": first_estimate,
        "absolute_noise_error_at_first_recovery": abs(
            first_estimate - true_rate
        ),
        "final_estimated_noise_rate": run["final"].get(
            "estimated_noise_rate",
            true_rate,
        ),
        "final_word_accuracy": run["final"]["word_accuracy"],
    }


def plot(
    known: list[dict[str, Any]],
    estimated: list[dict[str, Any]],
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
    rates = sorted({key(run)[0] for run in estimated})
    colors = plt.cm.viridis(np.linspace(0.05, 0.95, len(rates)))

    for color, rate in zip(colors, rates, strict=True):
        selected = sorted(
            (run for run in estimated if key(run)[0] == rate),
            key=lambda run: key(run)[1],
        )
        for index, run in enumerate(selected):
            examples = [record["examples_seen"] for record in run["metrics"]]
            estimates = [
                record["estimated_noise_rate"] for record in run["metrics"]
            ]
            axes[0].plot(
                examples,
                estimates,
                color=color,
                linewidth=1.4,
                alpha=0.7,
                label=f"{100 * rate:.0f}%" if index == 0 else None,
            )
    axes[0].set_xscale("log")
    axes[0].set_xlabel("fresh noisy examples")
    axes[0].set_ylabel("learner's estimated flip rate")
    axes[0].set_title("One 10% initial guess tracks six rates")
    axes[0].grid(True, which="both", alpha=0.2)
    axes[0].legend(frameon=False, ncol=2, fontsize=8)

    indexed_known = {key(run): run for run in known}
    indexed_estimated = {key(run): run for run in estimated}
    known_examples = []
    estimated_examples = []
    for pair_key in sorted(indexed_known):
        known_examples.append(
            indexed_known[pair_key]["first_record"]["examples_seen"]
        )
        estimated_examples.append(
            indexed_estimated[pair_key]["first_record"]["examples_seen"]
        )
    axes[1].scatter(
        known_examples,
        estimated_examples,
        c=np.repeat(colors, 2, axis=0),
        s=44,
        edgecolor="white",
        linewidth=0.5,
        zorder=3,
    )
    limits = [
        min(known_examples + estimated_examples) * 0.75,
        max(known_examples + estimated_examples) * 1.3,
    ]
    axes[1].plot(limits, limits, color="#666666", linestyle="--", linewidth=1)
    axes[1].set_xscale("log")
    axes[1].set_yscale("log")
    axes[1].set_xlim(limits)
    axes[1].set_ylim(limits)
    axes[1].set_xlabel("examples when true noise rate is supplied")
    axes[1].set_ylabel("examples when noise rate is estimated")
    axes[1].set_title("No sample-efficiency penalty")
    axes[1].grid(True, which="both", alpha=0.2)

    true_rates = []
    first_estimates = []
    for run in estimated:
        true_rates.append(key(run)[0])
        first_estimates.append(
            run["first_record"]["estimated_noise_rate"]
        )
    axes[2].scatter(
        np.array(true_rates) * 100,
        np.array(first_estimates) * 100,
        c=np.repeat(colors, 2, axis=0),
        s=44,
        edgecolor="white",
        linewidth=0.5,
        zorder=3,
    )
    axes[2].plot([0, 50], [0, 50], color="#666666", linestyle="--", linewidth=1)
    axes[2].set_xlim(0, 50)
    axes[2].set_ylim(0, 50)
    axes[2].set_xlabel("true flip rate (%)")
    axes[2].set_ylabel("estimate at first exact recovery (%)")
    axes[2].set_title("Noise estimate is already calibrated")
    axes[2].grid(True, alpha=0.2)

    fig.suptitle(
        "Repeated-label disagreement removes the known-noise assumption",
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    known = [load_run(path) for path in args.known]
    estimated = [load_run(path) for path in args.estimated]
    stress = [load_run(path) for path in args.stress]
    validate(known, estimated, stress)

    indexed_known = {key(run): run for run in known}
    indexed_estimated = {key(run): run for run in estimated}
    step_differences = [
        indexed_estimated[pair_key]["first_full_recovery_step"]
        - indexed_known[pair_key]["first_full_recovery_step"]
        for pair_key in sorted(indexed_known)
    ]
    estimated_rows = [compact(run) for run in estimated]
    first_errors = [
        row["absolute_noise_error_at_first_recovery"]
        for row in estimated_rows
    ]
    summary = {
        "kind": "unknown-noise-pairwise-disagreement-discovery",
        "protocol": {
            "true_noise_rates": sorted({key(run)[0] for run in estimated}),
            "paired_seeds": sorted({key(run)[1] for run in estimated}),
            "learner_initial_noise_rate": 0.10,
            "batch_size": 100,
            "d_optimal_design_points": 79,
            "fresh_noise_each_sample": True,
            "clean_labels_used_for_updates": False,
            "oracle_noise_rate_given_to_estimated_learner": False,
            "estimator": (
                "pairwise repeated-label disagreement: "
                "d = 2p(1-p), solve for p below 0.5"
            ),
        },
        "claims": {
            "all_12_estimated_noise_runs_exact": True,
            "all_26_runs_recover_same_integer_rule": True,
            "paired_first_exact_steps_identical_count": sum(
                difference == 0 for difference in step_differences
            ),
            "maximum_paired_first_exact_step_difference": int(
                max(abs(difference) for difference in step_differences)
            ),
            "mean_absolute_noise_error_at_first_recovery": float(
                np.mean(first_errors)
            ),
            "maximum_absolute_noise_error_at_first_recovery": float(
                np.max(first_errors)
            ),
            "stress_initial_guesses": sorted(
                run["config"]["initial_noise_rate"] for run in stress
            ),
            "stress_runs_both_exact": True,
        },
        "step_differences_estimated_minus_known": step_differences,
        "estimated_noise_runs": estimated_rows,
        "known_noise_runs": [compact(run) for run in known],
        "initial_guess_stress_runs": [compact(run) for run in stress],
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    plot(known, estimated, args.output_figure)
    print(json.dumps(summary["claims"], indent=2))


if __name__ == "__main__":
    main()
