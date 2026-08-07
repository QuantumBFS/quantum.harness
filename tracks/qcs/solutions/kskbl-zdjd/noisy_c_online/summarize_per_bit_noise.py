"""Summarize heterogeneous per-bit noise and dual-track uncertainty."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


ENTROPY_STOP = 1e-3
ROUNDING_STOP = 0.05


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dual-track", action="append", type=Path, required=True)
    parser.add_argument("--per-bit-fit", action="append", type=Path, required=True)
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
    blind_stop = next(
        (
            record
            for record in metrics
            if record["mean_word_posterior_entropy"] < ENTROPY_STOP
            and record["maximum_rounding_residual"] < ROUNDING_STOP
        ),
        None,
    )
    return {
        "path": directory.as_posix(),
        "run_sha256": sha256(run_path),
        "metrics_sha256": sha256(metrics_path),
        "config": run["config"],
        "verification": run["verification"],
        "first_full_recovery_step": run["first_full_recovery_step"],
        "final": run["final"],
        "integer_coefficients": tuple(
            int(row["coefficient"]) for row in run["integer_coefficients"]
        ),
        "blind_stop": blind_stop,
        "metrics": metrics,
    }


def validate(
    dual_track: list[dict[str, Any]],
    per_bit_fit: list[dict[str, Any]],
) -> list[float]:
    if len(dual_track) != 2 or len(per_bit_fit) != 2:
        raise ValueError("expected two seeds per strategy")
    all_runs = dual_track + per_bit_fit
    seeds = [
        {run["config"]["base_seed"] for run in runs}
        for runs in (dual_track, per_bit_fit)
    ]
    if seeds[0] != seeds[1]:
        raise ValueError("strategy seeds do not match")
    profiles = {
        tuple(run["config"]["oracle_per_bit_noise_rates"])
        for run in all_runs
    }
    if len(profiles) != 1:
        raise ValueError("heterogeneous noise profiles do not match")
    profile = list(next(iter(profiles)))
    if len(profile) != 12 or min(profile) != 0.05 or max(profile) != 0.45:
        raise ValueError("unexpected heterogeneous noise profile")
    for run in all_runs:
        config = run["config"]
        verification = run["verification"]
        if config["input_sampling"] != "d-optimal-cycle":
            raise ValueError("input design mismatch")
        if config["design_size"] != 79 or config["design_rank"] != 79:
            raise ValueError("design is not minimal full rank")
        if run["first_full_recovery_step"] is None:
            raise ValueError("a run did not become exact")
        if run["final"]["word_accuracy"] != 1.0:
            raise ValueError("a run did not end exact")
        if run["blind_stop"] is None:
            raise ValueError("blind uncertainty stop was never reached")
        if run["blind_stop"]["word_accuracy"] != 1.0:
            raise ValueError("blind uncertainty stop was not clean-domain exact")
        if not verification["fresh_noise_each_sample"]:
            raise ValueError("noise was not regenerated")
        if verification["clean_labels_used_for_updates"]:
            raise ValueError("clean labels leaked into updates")
        if verification["learner_receives_oracle_noise_rate"]:
            raise ValueError("oracle noise profile leaked to learner")
    if any(
        run["config"]["learner_noise_mode"] != "pairwise-estimated"
        for run in dual_track
    ):
        raise ValueError("dual-track marker mismatch")
    if any(
        run["config"]["learner_noise_mode"]
        != "per-bit-pairwise-estimated"
        for run in per_bit_fit
    ):
        raise ValueError("per-bit-fit marker mismatch")
    if len({run["integer_coefficients"] for run in all_runs}) != 1:
        raise ValueError("strategies recovered different integer rules")
    return profile


def compact(run: dict[str, Any], profile: list[float]) -> dict[str, Any]:
    stop = run["blind_stop"]
    estimates = np.array(stop["estimated_noise_rates"])
    truth = np.array(profile)
    return {
        "path": run["path"],
        "run_sha256": run["run_sha256"],
        "metrics_sha256": run["metrics_sha256"],
        "base_seed": run["config"]["base_seed"],
        "learner_noise_mode": run["config"]["learner_noise_mode"],
        "first_full_recovery_step": run["first_full_recovery_step"],
        "blind_stop_step": stop["step"],
        "blind_stop_examples": stop["examples_seen"],
        "blind_stop_clean_word_accuracy_report_only": stop["word_accuracy"],
        "blind_stop_word_entropy_bits": stop[
            "mean_word_posterior_entropy"
        ],
        "blind_stop_maximum_rounding_residual": stop[
            "maximum_rounding_residual"
        ],
        "estimated_noise_rates_at_blind_stop": estimates.tolist(),
        "per_bit_noise_mae_at_blind_stop": float(
            np.mean(np.abs(estimates - truth))
        ),
        "per_bit_noise_max_error_at_blind_stop": float(
            np.max(np.abs(estimates - truth))
        ),
    }


def plot(
    dual_track: list[dict[str, Any]],
    per_bit_fit: list[dict[str, Any]],
    profile: list[float],
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
    bits = np.arange(12)
    axes[0].plot(
        bits,
        100 * np.array(profile),
        color="#222222",
        marker="o",
        linewidth=2,
        label="true profile",
    )
    for index, run in enumerate(dual_track):
        axes[0].plot(
            bits,
            100 * np.array(run["blind_stop"]["estimated_noise_rates"]),
            color="#e45756",
            marker=".",
            linewidth=1.2,
            alpha=0.7,
            label="dual-track estimate" if index == 0 else None,
        )
    axes[0].set_xticks(bits)
    axes[0].set_xlabel("output bit")
    axes[0].set_ylabel("flip rate (%)")
    axes[0].set_title("Twelve rates calibrated without clean labels")
    axes[0].grid(True, alpha=0.2)
    axes[0].legend(frameon=False, fontsize=8)

    for method, runs, color in (
        ("dual-track", dual_track, "#e45756"),
        ("per-bit posterior", per_bit_fit, "#4c78a8"),
    ):
        for index, run in enumerate(runs):
            axes[1].plot(
                [record["examples_seen"] for record in run["metrics"]],
                [record["word_accuracy"] for record in run["metrics"]],
                color=color,
                linewidth=1.3,
                alpha=0.65,
                label=method if index == 0 else None,
            )
    axes[1].set_xscale("log")
    axes[1].set_ylim(-0.03, 1.04)
    axes[1].set_xlabel("fresh noisy examples")
    axes[1].set_ylabel("clean-domain word accuracy")
    axes[1].set_title("Global fit is faster; both end exact")
    axes[1].grid(True, which="both", alpha=0.2)
    axes[1].legend(frameon=False, fontsize=8)

    for method, runs, color, marker in (
        ("dual-track", dual_track, "#e45756", "o"),
        ("per-bit posterior", per_bit_fit, "#4c78a8", "s"),
    ):
        for index, run in enumerate(runs):
            entropy = [
                record["mean_word_posterior_entropy"]
                for record in run["metrics"]
            ]
            residual = [
                record["maximum_rounding_residual"]
                for record in run["metrics"]
            ]
            axes[2].plot(
                entropy,
                residual,
                color=color,
                linewidth=1.0,
                alpha=0.55,
                label=method if index == 0 else None,
            )
            stop = run["blind_stop"]
            axes[2].scatter(
                [stop["mean_word_posterior_entropy"]],
                [stop["maximum_rounding_residual"]],
                color=color,
                marker=marker,
                s=48,
                zorder=4,
            )
    axes[2].axvline(
        ENTROPY_STOP,
        color="#777777",
        linestyle="--",
        linewidth=1,
    )
    axes[2].axhline(
        ROUNDING_STOP,
        color="#777777",
        linestyle="--",
        linewidth=1,
    )
    axes[2].set_xscale("log")
    axes[2].set_yscale("log")
    axes[2].set_xlabel("sum of 12 calibrated posterior entropies (bits)")
    axes[2].set_ylabel("maximum coefficient rounding residual")
    axes[2].set_title("Blind stop requires both uncertainties low")
    axes[2].grid(True, which="both", alpha=0.2)
    axes[2].legend(frameon=False, fontsize=8)

    fig.suptitle(
        "Heterogeneous 5%–45% bit noise: fast fit plus calibrated uncertainty",
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    dual_track = [load_run(path) for path in args.dual_track]
    per_bit_fit = [load_run(path) for path in args.per_bit_fit]
    profile = validate(dual_track, per_bit_fit)
    dual_rows = [compact(run, profile) for run in dual_track]
    per_bit_rows = [compact(run, profile) for run in per_bit_fit]
    all_rows = dual_rows + per_bit_rows
    summary = {
        "kind": "heterogeneous-per-bit-noise-dual-track-discovery",
        "protocol": {
            "oracle_per_bit_noise_rates": profile,
            "seeds": sorted(row["base_seed"] for row in dual_rows),
            "batch_size": 100,
            "d_optimal_design_points": 79,
            "initial_noise_rate_for_every_bit": 0.10,
            "fresh_noise_each_sample": True,
            "clean_labels_used_for_updates": False,
            "oracle_noise_profile_given_to_learner": False,
            "blind_stop": {
                "sum_of_per_bit_posterior_entropies_below_bits": ENTROPY_STOP,
                "maximum_coefficient_rounding_residual_below": ROUNDING_STOP,
                "clean_accuracy_not_used_by_stop": True,
            },
        },
        "claims": {
            "all_four_runs_final_exact": True,
            "all_four_runs_recover_same_integer_rule": True,
            "all_four_blind_stops_clean_exact_report_only": True,
            "dual_track_mean_first_exact_step": float(
                np.mean(
                    [row["first_full_recovery_step"] for row in dual_rows]
                )
            ),
            "per_bit_fit_mean_first_exact_step": float(
                np.mean(
                    [
                        row["first_full_recovery_step"]
                        for row in per_bit_rows
                    ]
                )
            ),
            "dual_track_mean_blind_stop_step": float(
                np.mean([row["blind_stop_step"] for row in dual_rows])
            ),
            "per_bit_fit_mean_blind_stop_step": float(
                np.mean([row["blind_stop_step"] for row in per_bit_rows])
            ),
            "mean_per_bit_noise_mae_at_blind_stop": float(
                np.mean(
                    [
                        row["per_bit_noise_mae_at_blind_stop"]
                        for row in all_rows
                    ]
                )
            ),
            "maximum_per_bit_noise_error_at_blind_stop": float(
                np.max(
                    [
                        row["per_bit_noise_max_error_at_blind_stop"]
                        for row in all_rows
                    ]
                )
            ),
        },
        "dual_track": dual_rows,
        "per_bit_fit": per_bit_rows,
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    plot(dual_track, per_bit_fit, profile, args.output_figure)
    print(json.dumps(summary["claims"], indent=2))


if __name__ == "__main__":
    main()
