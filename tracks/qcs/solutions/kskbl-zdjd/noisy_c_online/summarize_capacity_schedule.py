"""Validate and summarize the posterior-replay capacity/schedule study."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


CURVE_KEYS = (
    "step",
    "examples_seen",
    "elapsed_seconds",
    "learning_rate",
    "anneal_start_step",
    "train_loss_ema",
    "clean_bce",
    "bit_accuracy",
    "word_accuracy",
    "normalized_mae",
    "bit_uncertainty",
    "teacher_word_accuracy",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h128-fast-run", type=Path, required=True)
    parser.add_argument("--h64-cosine-run", type=Path, required=True)
    parser.add_argument("--h48-constant-run", type=Path, required=True)
    parser.add_argument("--h48-cosine-run", type=Path, required=True)
    parser.add_argument("--h48-triggered-run", type=Path, required=True)
    parser.add_argument("--h40-triggered-run", type=Path, required=True)
    parser.add_argument("--h36-triggered-run", type=Path, required=True)
    parser.add_argument("--h36-replicate-run", type=Path, required=True)
    parser.add_argument("--h32-triggered-run", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-figure", type=Path, required=True)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parameter_count(config: dict[str, Any]) -> int:
    if config["architecture"] == "parity3":
        input_width = sum(math.comb(12, degree) for degree in range(1, 4))
    elif config["architecture"] == "shared":
        input_width = 12
    else:
        raise ValueError(f"unsupported architecture: {config['architecture']}")
    hidden = int(config["hidden"])
    depth = int(config["depth"])
    return (
        input_width * hidden
        + hidden
        + (depth - 1) * (hidden * hidden + hidden)
        + hidden * 12
        + 12
    )


def compact_curve(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: record[key] for key in CURVE_KEYS if key in record}
        for record in metrics
    ]


def summarize_run(path: Path) -> dict[str, Any]:
    run = load_json(path / "run.json")
    metrics = load_json(path / "metrics.json")
    config = run["config"]
    verification = run["verification"]
    if config["batch_size"] != 100 or config["noise_rate"] != 0.25:
        raise ValueError(f"{path}: protocol mismatch")
    if verification.get("clean_labels_used_for_updates") is not False:
        raise ValueError(f"{path}: clean-label isolation is not verified")
    if verification.get("fresh_noise_each_sample") is not True:
        raise ValueError(f"{path}: fresh noise is not verified")

    first_exact_index = next(
        (
            index
            for index, record in enumerate(metrics)
            if record["word_accuracy"] == 1.0
        ),
        None,
    )
    first_exact = (
        metrics[first_exact_index] if first_exact_index is not None else None
    )
    after_first = (
        metrics[first_exact_index:] if first_exact_index is not None else []
    )
    per_member_parameters = parameter_count(config)
    return {
        "path": path.as_posix(),
        "run_sha256": sha256(path / "run.json"),
        "metrics_sha256": sha256(path / "metrics.json"),
        "model_sha256": {
            model_path.name: sha256(model_path)
            for model_path in sorted(path.glob("model-*.pt"))
        },
        "config": config,
        "learning_rate_schedule": config.get(
            "learning_rate_schedule",
            "cosine",
        ),
        "anneal_start_step": run.get("anneal_start_step"),
        "parameters_per_member": per_member_parameters,
        "total_student_parameters": (
            per_member_parameters * int(config["ensemble_size"])
        ),
        "first_full_recovery": first_exact,
        "final": metrics[-1],
        "full_recovery_checkpoints": sum(
            record["word_accuracy"] == 1.0 for record in metrics
        ),
        "checkpoints_after_first_recovery": len(after_first),
        "all_checkpoints_exact_after_first": bool(after_first)
        and all(record["word_accuracy"] == 1.0 for record in after_first),
        "curve": compact_curve(metrics),
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
        2,
        2,
        figsize=(14.0, 8.8),
        constrained_layout=True,
    )
    figure.patch.set_facecolor("#ffffff")
    for axis in axes.flat:
        axis.set_facecolor("#f8fafc")
        axis.grid(color="#d8e0e8", alpha=0.75)

    colors = {
        "h128_fast": "#7c3aed",
        "h64_cosine": "#2563eb",
        "h48_triggered": "#0891b2",
        "h40_triggered": "#0f9f78",
        "h36_triggered": "#15803d",
        "h36_replicate": "#84cc16",
        "h32_triggered": "#ea580c",
    }
    labels = {
        "h128_fast": "h128 × 4, fast ensemble",
        "h64_cosine": "h64, fixed-horizon cosine",
        "h48_triggered": "h48, loss-triggered",
        "h40_triggered": "h40, loss-triggered",
        "h36_triggered": "h36, loss-triggered",
        "h36_replicate": "h36, independent seed",
        "h32_triggered": "h32, current budget",
    }
    convergence_keys = (
        "h128_fast",
        "h64_cosine",
        "h48_triggered",
        "h40_triggered",
        "h36_triggered",
        "h36_replicate",
        "h32_triggered",
    )
    for key in convergence_keys:
        curve = summary["runs"][key]["curve"]
        axes[0, 0].plot(
            [record["step"] for record in curve],
            [record["word_accuracy"] for record in curve],
            label=labels[key],
            color=colors[key],
            linewidth=2.0,
        )
    axes[0, 0].set_title("Capacity frontier under the same noisy protocol")
    axes[0, 0].set_xlabel("Training step")
    axes[0, 0].set_ylabel("Clean exact-word accuracy")
    axes[0, 0].set_ylim(-0.02, 1.02)
    axes[0, 0].legend(loc="lower right", fontsize=7.7, ncol=2)

    exact_keys = (
        "h128_fast",
        "h64_cosine",
        "h48_triggered",
        "h40_triggered",
        "h36_triggered",
        "h36_replicate",
    )
    for key in exact_keys:
        run = summary["runs"][key]
        axes[0, 1].scatter(
            run["parameters_per_member"],
            run["first_full_recovery"]["step"],
            s=65,
            color=colors[key],
            label=labels[key],
            zorder=3,
        )
    h32 = summary["runs"]["h32_triggered"]
    axes[0, 1].scatter(
        h32["parameters_per_member"],
        h32["config"]["steps"],
        marker="x",
        s=80,
        linewidth=2.5,
        color=colors["h32_triggered"],
        label="h32: not exact by 12k",
        zorder=3,
    )
    axes[0, 1].set_title("Compression costs optimization steps")
    axes[0, 1].set_xlabel("Continuous parameters per member")
    axes[0, 1].set_ylabel("First exact checkpoint")
    axes[0, 1].legend(loc="upper right", fontsize=7.6)

    schedule_keys = (
        "h48_constant",
        "h48_cosine",
        "h48_triggered",
    )
    schedule_labels = {
        "h48_constant": "constant LR",
        "h48_cosine": "fixed-horizon cosine",
        "h48_triggered": "loss-triggered cooldown",
    }
    schedule_colors = {
        "h48_constant": "#dc2626",
        "h48_cosine": "#9333ea",
        "h48_triggered": "#0891b2",
    }
    for key in schedule_keys:
        curve = summary["runs"][key]["curve"]
        axes[1, 0].plot(
            [record["step"] for record in curve],
            [record["word_accuracy"] for record in curve],
            label=schedule_labels[key],
            color=schedule_colors[key],
            linewidth=2.2,
        )
    trigger = summary["runs"]["h48_triggered"]["anneal_start_step"]
    axes[1, 0].axvline(
        trigger,
        color="#64748b",
        linestyle="--",
        linewidth=1.2,
        label=f"loss trigger at step {trigger:,}",
    )
    axes[1, 0].set_title("h48 schedule ablation")
    axes[1, 0].set_xlabel("Training step")
    axes[1, 0].set_ylabel("Clean exact-word accuracy")
    axes[1, 0].set_ylim(-0.02, 1.02)
    axes[1, 0].legend(loc="lower right", fontsize=8.0)

    capacity_keys = (
        "h128_fast",
        "h64_cosine",
        "h48_triggered",
        "h40_triggered",
        "h36_triggered",
        "h32_triggered",
    )
    parameter_values = [
        summary["runs"][key]["parameters_per_member"]
        for key in capacity_keys
    ]
    capacity_labels = [
        "h128",
        "h64",
        "h48",
        "h40",
        "h36",
        "h32",
    ]
    bar_colors = [
        colors[key]
        if summary["runs"][key]["first_full_recovery"] is not None
        else "#f97316"
        for key in capacity_keys
    ]
    y_positions = np.arange(len(capacity_keys))
    axes[1, 1].barh(
        y_positions,
        parameter_values,
        color=bar_colors,
        alpha=0.9,
    )
    for y_position, value, key in zip(
        y_positions,
        parameter_values,
        capacity_keys,
    ):
        status = (
            "exact"
            if summary["runs"][key]["first_full_recovery"] is not None
            else "74.44% at 12k"
        )
        axes[1, 1].text(
            value + 1000,
            y_position,
            f"{value:,} · {status}",
            va="center",
            fontsize=8.5,
        )
    axes[1, 1].set_yticks(y_positions, capacity_labels)
    axes[1, 1].invert_yaxis()
    axes[1, 1].set_xlim(0, max(parameter_values) * 1.35)
    axes[1, 1].set_xlabel("Continuous parameters per member")
    axes[1, 1].set_title("Smallest replicated exact student: h36")

    figure.suptitle(
        "Loss-triggered annealing moves the exact-recovery frontier to 13,872 parameters",
        fontsize=16.5,
        fontweight="bold",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180, facecolor=figure.get_facecolor())
    plt.close(figure)


def main() -> None:
    args = parse_args()
    paths = {
        "h128_fast": args.h128_fast_run,
        "h64_cosine": args.h64_cosine_run,
        "h48_constant": args.h48_constant_run,
        "h48_cosine": args.h48_cosine_run,
        "h48_triggered": args.h48_triggered_run,
        "h40_triggered": args.h40_triggered_run,
        "h36_triggered": args.h36_triggered_run,
        "h36_replicate": args.h36_replicate_run,
        "h32_triggered": args.h32_triggered_run,
    }
    runs = {key: summarize_run(path) for key, path in paths.items()}
    winner = runs["h36_triggered"]
    replicate = runs["h36_replicate"]
    if winner["final"]["word_accuracy"] != 1.0:
        raise ValueError("primary h36 run is not exact")
    if replicate["final"]["word_accuracy"] != 1.0:
        raise ValueError("replicate h36 run is not exact")
    if not winner["all_checkpoints_exact_after_first"]:
        raise ValueError("primary h36 run is unstable after first recovery")
    if not replicate["all_checkpoints_exact_after_first"]:
        raise ValueError("replicate h36 run is unstable after first recovery")

    summary = {
        "kind": "posterior-replay-capacity-schedule-summary",
        "protocol": {
            "input_bits": 12,
            "output_bits": 12,
            "clean_domain_size": 4096,
            "fresh_examples_per_step_per_member": 100,
            "independent_output_bit_flip_probability": 0.25,
            "clean_domain_used_for_updates": False,
            "formula_or_circuit_seeded": False,
        },
        "claims": {
            "smallest_replicated_exact_width": 36,
            "smallest_replicated_exact_parameters": (
                winner["parameters_per_member"]
            ),
            "parameter_reduction_vs_h128_per_member": (
                1.0
                - winner["parameters_per_member"]
                / runs["h128_fast"]["parameters_per_member"]
            ),
            "parameter_reduction_vs_h40": (
                1.0
                - winner["parameters_per_member"]
                / runs["h40_triggered"]["parameters_per_member"]
            ),
            "primary_first_exact_step": (
                winner["first_full_recovery"]["step"]
            ),
            "replicate_first_exact_step": (
                replicate["first_full_recovery"]["step"]
            ),
            "primary_exact_checkpoints_after_first": (
                winner["checkpoints_after_first_recovery"]
            ),
            "replicate_exact_checkpoints_after_first": (
                replicate["checkpoints_after_first_recovery"]
            ),
            "h32_word_accuracy_at_12000": (
                runs["h32_triggered"]["final"]["word_accuracy"]
            ),
            "h32_is_not_claimed_as_a_hard_capacity_lower_bound": True,
        },
        "runs": runs,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    plot_summary(summary, args.output_figure)
    print(
        json.dumps(
            {
                "output_json": args.output_json.as_posix(),
                "output_figure": args.output_figure.as_posix(),
                "winner_parameters": winner["parameters_per_member"],
                "primary_first_exact_step": (
                    winner["first_full_recovery"]["step"]
                ),
                "replicate_first_exact_step": (
                    replicate["first_full_recovery"]["step"]
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
