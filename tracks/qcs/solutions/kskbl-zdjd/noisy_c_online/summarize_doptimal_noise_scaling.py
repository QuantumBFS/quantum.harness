"""Compare D-optimal and uniform recovery across fresh-noise rates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


NOISE_RATES = (0.05, 0.15, 0.25, 0.35, 0.40, 0.45)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uniform", action="append", type=Path, required=True)
    parser.add_argument("--d-optimal", action="append", type=Path, required=True)
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
    return {
        "path": directory.as_posix(),
        "run_sha256": sha256(path),
        "config": run["config"],
        "verification": run["verification"],
        "first_full_recovery_step": run["first_full_recovery_step"],
        "final_word_accuracy": run["final"]["word_accuracy"],
        "integer_coefficients": tuple(
            int(row["coefficient"]) for row in run["integer_coefficients"]
        ),
    }


def key(run: dict[str, Any]) -> tuple[float, int]:
    config = run["config"]
    return float(config["noise_rate"]), int(config["base_seed"])


def validate(
    uniform: list[dict[str, Any]],
    d_optimal: list[dict[str, Any]],
) -> None:
    if len(uniform) != 12 or len(d_optimal) != 12:
        raise ValueError("expected twelve runs for each sampling method")
    if {key(run) for run in uniform} != {key(run) for run in d_optimal}:
        raise ValueError("uniform and D-optimal runs are not paired")
    if {key(run)[0] for run in uniform} != set(NOISE_RATES):
        raise ValueError("noise-rate grid does not match")
    all_runs = uniform + d_optimal
    for run in all_runs:
        config = run["config"]
        verification = run["verification"]
        if config["batch_size"] != 100 or config["weight_mode"] != "observation":
            raise ValueError("protocol mismatch")
        if run["first_full_recovery_step"] is None:
            raise ValueError("a paired run never reached exact recovery")
        if run["final_word_accuracy"] != 1.0:
            raise ValueError("a paired run did not end exact")
        if not verification["fresh_noise_each_sample"]:
            raise ValueError("noise was not regenerated")
        if verification["clean_labels_used_for_updates"]:
            raise ValueError("clean labels leaked into updates")
        if verification["target_formula_seeded"]:
            raise ValueError("target formula was seeded")
    for run in d_optimal:
        config = run["config"]
        verification = run["verification"]
        if config["input_sampling"] != "d-optimal-cycle":
            raise ValueError("wrong D-optimal marker")
        if config["design_size"] != 79 or config["design_rank"] != 79:
            raise ValueError("D-optimal design is not minimal full-rank")
        if verification["input_design_uses_target_labels"]:
            raise ValueError("D-optimal input design used labels")
    if len({run["integer_coefficients"] for run in all_runs}) != 1:
        raise ValueError("runs recovered different integer rules")


def aggregate(
    uniform: list[dict[str, Any]],
    d_optimal: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    indexed_u = {key(run): run for run in uniform}
    indexed_d = {key(run): run for run in d_optimal}
    rows: list[dict[str, Any]] = []
    for noise_rate in NOISE_RATES:
        seeds = sorted(
            seed for rate, seed in indexed_u if rate == noise_rate
        )
        uniform_steps = [
            indexed_u[(noise_rate, seed)]["first_full_recovery_step"]
            for seed in seeds
        ]
        d_optimal_steps = [
            indexed_d[(noise_rate, seed)]["first_full_recovery_step"]
            for seed in seeds
        ]
        mean_u = float(np.mean(uniform_steps))
        mean_d = float(np.mean(d_optimal_steps))
        rows.append(
            {
                "noise_rate": noise_rate,
                "seeds": seeds,
                "uniform_first_exact_steps": uniform_steps,
                "d_optimal_first_exact_steps": d_optimal_steps,
                "uniform_mean_first_exact_steps": mean_u,
                "d_optimal_mean_first_exact_steps": mean_d,
                "uniform_mean_first_exact_examples": mean_u * 100,
                "d_optimal_mean_first_exact_examples": mean_d * 100,
                "example_reduction_factor": mean_u / mean_d,
            }
        )
    return rows


def fit_signal_scaling(rows: list[dict[str, Any]]) -> dict[str, float | str]:
    noise = np.array([row["noise_rate"] for row in rows])
    signal_inverse_squared = 1.0 / np.square(1.0 - 2.0 * noise)
    steps = np.array(
        [row["d_optimal_mean_first_exact_steps"] for row in rows]
    )
    slope, intercept = np.polyfit(signal_inverse_squared, steps, 1)
    prediction = intercept + slope * signal_inverse_squared
    r_squared = 1.0 - np.sum(np.square(steps - prediction)) / np.sum(
        np.square(steps - steps.mean())
    )
    return {
        "model": "mean_first_exact_step = intercept + slope / (1 - 2p)^2",
        "intercept": float(intercept),
        "slope": float(slope),
        "r_squared": float(r_squared),
    }


def plot(
    rows: list[dict[str, Any]],
    scaling_fit: dict[str, float | str],
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
    noise_percent = 100.0 * np.array(
        [row["noise_rate"] for row in rows]
    )
    uniform_mean = np.array(
        [row["uniform_mean_first_exact_steps"] for row in rows]
    )
    d_optimal_mean = np.array(
        [row["d_optimal_mean_first_exact_steps"] for row in rows]
    )
    axes[0].plot(
        noise_percent,
        uniform_mean * 100,
        color="#4c78a8",
        marker="o",
        linewidth=2,
        label="uniform",
    )
    axes[0].plot(
        noise_percent,
        d_optimal_mean * 100,
        color="#e45756",
        marker="o",
        linewidth=2,
        label="D-optimal",
    )
    axes[0].set_yscale("log")
    axes[0].set_xlabel("per-bit flip rate (%)")
    axes[0].set_ylabel("mean examples at first exact recovery")
    axes[0].set_title("Acceleration persists through 45% noise")
    axes[0].grid(True, which="both", alpha=0.2)
    axes[0].legend(frameon=False)

    reductions = np.array(
        [row["example_reduction_factor"] for row in rows]
    )
    axes[1].plot(
        noise_percent,
        reductions,
        color="#f58518",
        marker="o",
        linewidth=2,
    )
    axes[1].axhline(
        reductions.mean(),
        color="#777777",
        linestyle="--",
        linewidth=1,
        label=f"mean {reductions.mean():.1f}x",
    )
    axes[1].set_ylim(0, max(reductions) * 1.18)
    axes[1].set_xlabel("per-bit flip rate (%)")
    axes[1].set_ylabel("uniform examples / D-optimal examples")
    axes[1].set_title("55x–72x fewer examples at every rate")
    axes[1].grid(True, alpha=0.2)
    axes[1].legend(frameon=False)

    noise = np.array([row["noise_rate"] for row in rows])
    inverse_signal_squared = 1.0 / np.square(1.0 - 2.0 * noise)
    intercept = float(scaling_fit["intercept"])
    slope = float(scaling_fit["slope"])
    x_line = np.linspace(
        inverse_signal_squared.min(),
        inverse_signal_squared.max(),
        200,
    )
    axes[2].scatter(
        inverse_signal_squared,
        d_optimal_mean,
        color="#e45756",
        s=45,
        zorder=3,
    )
    axes[2].plot(
        x_line,
        intercept + slope * x_line,
        color="#555555",
        linewidth=1.5,
        label=f"linear fit, R²={float(scaling_fit['r_squared']):.5f}",
    )
    axes[2].set_xlabel("inverse squared clean-bit signal")
    axes[2].set_ylabel("D-optimal mean first-exact batch")
    axes[2].set_title("Predictable noise scaling")
    axes[2].grid(True, alpha=0.2)
    axes[2].legend(frameon=False)

    fig.suptitle(
        "Minimal 79-point design across six fresh-noise levels",
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    uniform = [load_run(path) for path in args.uniform]
    d_optimal = [load_run(path) for path in args.d_optimal]
    validate(uniform, d_optimal)
    rows = aggregate(uniform, d_optimal)
    scaling_fit = fit_signal_scaling(rows)
    reductions = [row["example_reduction_factor"] for row in rows]
    summary = {
        "kind": "d-optimal-versus-uniform-noise-scaling",
        "protocol": {
            "noise_rates": list(NOISE_RATES),
            "seeds": sorted({key(run)[1] for run in uniform}),
            "batch_size": 100,
            "fresh_noise_each_sample": True,
            "clean_labels_used_for_updates": False,
            "target_formula_seeded": False,
            "d_optimal_design_points": 79,
            "d_optimal_design_uses_output_labels": False,
        },
        "claims": {
            "all_24_runs_final_exact": True,
            "all_24_runs_recover_same_integer_rule": True,
            "minimum_example_reduction_factor": float(np.min(reductions)),
            "maximum_example_reduction_factor": float(np.max(reductions)),
            "mean_example_reduction_factor": float(np.mean(reductions)),
            "d_optimal_45_percent_mean_examples": rows[-1][
                "d_optimal_mean_first_exact_examples"
            ],
            "uniform_45_percent_mean_examples": rows[-1][
                "uniform_mean_first_exact_examples"
            ],
        },
        "signal_scaling_fit": scaling_fit,
        "by_noise_rate": rows,
        "runs": {
            "uniform": [
                {
                    "path": run["path"],
                    "run_sha256": run["run_sha256"],
                    "noise_rate": key(run)[0],
                    "base_seed": key(run)[1],
                    "first_full_recovery_step": run[
                        "first_full_recovery_step"
                    ],
                }
                for run in uniform
            ],
            "d_optimal": [
                {
                    "path": run["path"],
                    "run_sha256": run["run_sha256"],
                    "noise_rate": key(run)[0],
                    "base_seed": key(run)[1],
                    "first_full_recovery_step": run[
                        "first_full_recovery_step"
                    ],
                }
                for run in d_optimal
            ],
        },
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    plot(rows, scaling_fit, args.output_figure)
    print(json.dumps({**summary["claims"], **scaling_fit}, indent=2))


if __name__ == "__main__":
    main()
