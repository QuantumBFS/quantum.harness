"""Summarize symbolic recovery across fresh bit-flip probabilities."""

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
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--output-summary", type=Path, required=True)
    parser.add_argument("--output-figure", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_run(path: Path) -> dict[str, Any]:
    run_path = path / "run.json"
    metrics_path = path / "metrics.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    verification = run["verification"]
    if run["final"]["word_accuracy"] != 1.0:
        raise ValueError(f"{path}: final symbolic rule is not exact")
    if run["final"]["active_integer_coefficients"] != 36:
        raise ValueError(f"{path}: final rule is not the 36-term solution")
    if verification.get("clean_labels_used_for_updates") is not False:
        raise ValueError(f"{path}: clean-label isolation is not verified")
    if verification.get("fresh_noise_each_sample") is not True:
        raise ValueError(f"{path}: fresh-noise invariant is not verified")
    active_coefficients = [
        row for row in run["integer_coefficients"] if row["coefficient"]
    ]
    return {
        "path": path.as_posix(),
        "run_sha256": sha256(run_path),
        "metrics_sha256": sha256(metrics_path),
        "config": run["config"],
        "first_full_recovery_step": run["first_full_recovery_step"],
        "final": run["final"],
        "active_integer_coefficients": active_coefficients,
    }


def plot_summary(summary: dict[str, Any], output: Path) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "text.color": "#0f172a",
            "axes.labelcolor": "#334155",
            "axes.edgecolor": "#94a3b8",
            "xtick.color": "#475569",
            "ytick.color": "#475569",
        }
    )
    figure, axes = plt.subplots(
        1,
        3,
        figsize=(14.2, 4.6),
        constrained_layout=True,
    )
    figure.patch.set_facecolor("#ffffff")
    for axis in axes:
        axis.set_facecolor("#f8fafc")
        axis.grid(color="#d8e0e8", alpha=0.75)

    colors = {127100: "#075985", 137100: "#0f9f78"}
    for seed, runs in summary["by_seed"].items():
        numeric_seed = int(seed)
        axes[0].plot(
            [run["config"]["noise_rate"] for run in runs],
            [run["first_full_recovery_step"] for run in runs],
            marker="o",
            linewidth=2.2,
            color=colors[numeric_seed],
            label=f"seed {numeric_seed:,}",
        )
    axes[0].set_yscale("log")
    axes[0].set_xlabel("Independent flip probability per bit")
    axes[0].set_ylabel("First exact step (log scale)")
    axes[0].set_title("Recovery remains exact through 45% noise")
    axes[0].legend(fontsize=8.5)

    points = summary["points"]
    signal_inverse_square = np.asarray(
        [point["inverse_signal_squared"] for point in points]
    )
    first_steps = np.asarray(
        [point["first_full_recovery_step"] for point in points]
    )
    axes[1].scatter(
        signal_inverse_square,
        first_steps,
        c=[
            colors[point["base_seed"]]
            for point in points
        ],
        s=48,
        alpha=0.9,
    )
    fit = summary["scaling_fit"]
    fit_x = np.linspace(
        signal_inverse_square.min(),
        signal_inverse_square.max(),
        200,
    )
    axes[1].plot(
        fit_x,
        fit["intercept"] + fit["slope"] * fit_x,
        color="#7c3aed",
        linestyle="--",
        linewidth=2.0,
        label=f"linear fit · R²={fit['r_squared']:.4f}",
    )
    axes[1].set_xlabel("Inverse squared signal: 1 / (1 − 2p)²")
    axes[1].set_ylabel("First exact step")
    axes[1].set_title("Sample cost follows denoising signal strength")
    axes[1].legend(fontsize=8.5)

    noise_rates = summary["noise_rates"]
    mean_steps = [
        summary["by_noise_rate"][f"{noise_rate:.2f}"][
            "mean_first_full_recovery_step"
        ]
        for noise_rate in noise_rates
    ]
    mean_seconds = [
        summary["by_noise_rate"][f"{noise_rate:.2f}"][
            "mean_final_elapsed_seconds"
        ]
        for noise_rate in noise_rates
    ]
    axes[2].plot(
        noise_rates,
        mean_seconds,
        marker="o",
        color="#ea580c",
        linewidth=2.2,
        label="measured CPU training time",
    )
    for noise_rate, seconds, steps in zip(
        noise_rates,
        mean_seconds,
        mean_steps,
        strict=True,
    ):
        axes[2].annotate(
            f"{steps:,.0f} steps",
            (noise_rate, seconds),
            xytext=(0, 7),
            textcoords="offset points",
            ha="center",
            fontsize=7.5,
        )
    axes[2].set_yscale("log")
    axes[2].set_xlabel("Independent flip probability per bit")
    axes[2].set_ylabel("Training time in seconds (log scale)")
    axes[2].set_title("All scans remain laptop-scale")

    figure.suptitle(
        "The same 36-term rule is recovered from 5% to 45% fresh bit noise",
        fontsize=16,
        fontweight="bold",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180, facecolor=figure.get_facecolor())
    plt.close(figure)


def main() -> None:
    args = parse_args()
    runs = [load_run(path) for path in args.run]
    seeds = sorted({run["config"]["base_seed"] for run in runs})
    noise_rates = sorted({run["config"]["noise_rate"] for run in runs})
    expected_count = len(seeds) * len(noise_rates)
    if len(runs) != expected_count:
        raise ValueError("noise-rate scan is not a complete seed grid")
    reference_coefficients = runs[0]["active_integer_coefficients"]
    if any(
        run["active_integer_coefficients"] != reference_coefficients
        for run in runs[1:]
    ):
        raise ValueError("noise rates recovered different integer rules")

    by_seed = {
        str(seed): sorted(
            [
                run
                for run in runs
                if run["config"]["base_seed"] == seed
            ],
            key=lambda run: run["config"]["noise_rate"],
        )
        for seed in seeds
    }
    by_noise_rate = {}
    points = []
    for noise_rate in noise_rates:
        cells = [
            run
            for run in runs
            if run["config"]["noise_rate"] == noise_rate
        ]
        first_steps = [
            run["first_full_recovery_step"] for run in cells
        ]
        elapsed = [run["final"]["elapsed_seconds"] for run in cells]
        by_noise_rate[f"{noise_rate:.2f}"] = {
            "run_count": len(cells),
            "first_full_recovery_steps": first_steps,
            "mean_first_full_recovery_step": float(np.mean(first_steps)),
            "mean_final_elapsed_seconds": float(np.mean(elapsed)),
        }
        inverse_signal_squared = 1.0 / (1.0 - 2.0 * noise_rate) ** 2
        for run in cells:
            points.append(
                {
                    "noise_rate": noise_rate,
                    "base_seed": run["config"]["base_seed"],
                    "inverse_signal_squared": inverse_signal_squared,
                    "first_full_recovery_step": (
                        run["first_full_recovery_step"]
                    ),
                }
            )

    x = np.asarray([point["inverse_signal_squared"] for point in points])
    y = np.asarray([point["first_full_recovery_step"] for point in points])
    design = np.stack([np.ones_like(x), x], axis=1)
    intercept, slope = np.linalg.lstsq(design, y, rcond=None)[0]
    prediction = intercept + slope * x
    residual_sum = float(np.square(y - prediction).sum())
    total_sum = float(np.square(y - y.mean()).sum())
    r_squared = 1.0 - residual_sum / total_sum

    summary = {
        "kind": "quadratic-discovery-noise-rate-scan",
        "protocol": {
            "noise_rates": noise_rates,
            "seeds": seeds,
            "batch_size": 100,
            "input_sampling": "uniform",
            "fresh_noise_each_sample": True,
            "clean_domain_used_for_updates": False,
            "formula_or_existing_circuit_seeded": False,
        },
        "claims": {
            "all_runs_final_exact": True,
            "all_runs_recover_same_36_term_rule": True,
            "maximum_verified_noise_rate": max(noise_rates),
            "maximum_noise_mean_first_recovery_step": (
                by_noise_rate[f"{max(noise_rates):.2f}"][
                    "mean_first_full_recovery_step"
                ]
            ),
        },
        "scaling_fit": {
            "model": "first_exact_step = intercept + slope / (1 - 2p)^2",
            "intercept": float(intercept),
            "slope": float(slope),
            "r_squared": r_squared,
        },
        "noise_rates": noise_rates,
        "by_noise_rate": by_noise_rate,
        "by_seed": by_seed,
        "points": points,
        "active_integer_coefficients": reference_coefficients,
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    plot_summary(summary, args.output_figure)
    print(
        json.dumps(
            {
                **summary["claims"],
                **summary["scaling_fit"],
                "output_summary": args.output_summary.as_posix(),
                "output_figure": args.output_figure.as_posix(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
