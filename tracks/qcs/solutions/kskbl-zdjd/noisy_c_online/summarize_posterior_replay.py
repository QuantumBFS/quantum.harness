"""Validate, summarize and plot posterior-replay experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


CURVE_KEYS = (
    "step",
    "examples_seen",
    "elapsed_seconds",
    "clean_bce",
    "bit_accuracy",
    "word_accuracy",
    "normalized_mae",
    "bit_uncertainty",
    "value_uncertainty",
    "teacher_word_accuracy",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-run", type=Path, required=True)
    parser.add_argument("--main-run", type=Path, required=True)
    parser.add_argument("--replicate-run", type=Path, required=True)
    parser.add_argument("--dense-run", type=Path, required=True)
    parser.add_argument("--bayes-run", type=Path, required=True)
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
    clean_isolated = (
        verification.get("clean_labels_used_for_updates") is False
        or verification.get("clean_domain_used_for_gradients") is False
    )
    if not clean_isolated:
        raise ValueError(f"{path}: clean-label isolation was not verified")
    fresh_noise = (
        verification.get("fresh_noise_each_sample") is True
        or verification.get("noise_mask_regenerated_every_batch") is True
    )
    if not fresh_noise:
        raise ValueError(f"{path}: fresh-noise invariant was not verified")

    first_full = next(
        (record for record in metrics if record["word_accuracy"] == 1.0),
        None,
    )
    return {
        "path": path.as_posix(),
        "run_sha256": sha256(path / "run.json"),
        "metrics_sha256": sha256(path / "metrics.json"),
        "model_sha256": {
            model_path.name: sha256(model_path)
            for model_path in sorted(path.glob("model-*.pt"))
        },
        "config": config,
        "verification": verification,
        "first_full_recovery": first_full,
        "final": metrics[-1],
        "full_recovery_checkpoints": sum(
            record["word_accuracy"] == 1.0 for record in metrics
        ),
        "checkpoint_count": len(metrics),
        "curve": compact_curve(metrics),
    }


def summarize_scan(path: Path) -> dict[str, Any]:
    run_spec = load_json(path / "run_spec.json")
    rows = []
    for cell in run_spec["cells"]:
        manifest_path = path / "cells" / cell["cell_id"] / "manifest.json"
        manifest = load_json(manifest_path)
        if manifest["status"] != "success":
            raise ValueError(f"{cell['cell_id']}: scan cell did not succeed")
        rows.append(
            {
                "cell_id": cell["cell_id"],
                **cell["params"],
                "word_accuracy": manifest["result"]["word_accuracy"],
                "bit_accuracy": manifest["result"]["bit_accuracy"],
                "clean_bce": manifest["result"]["clean_bce"],
                "elapsed_seconds": manifest["result"]["elapsed_seconds"],
            }
        )
    return {
        "settings": run_spec["settings"],
        "provenance": run_spec["provenance"],
        "cells": rows,
    }


def plot_summary(
    summary: dict[str, Any],
    output: Path,
) -> None:
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
        figsize=(13.8, 8.7),
        constrained_layout=True,
    )
    figure.patch.set_facecolor("#ffffff")
    colors = {
        "Posterior replay · main": "#075985",
        "Posterior replay · replicate": "#0f9f78",
        "Direct shared MLP": "#ea580c",
        "Bayesian table": "#7c3aed",
    }
    series = (
        ("Posterior replay · main", summary["main"]["curve"]),
        ("Posterior replay · replicate", summary["replicate"]["curve"]),
        ("Direct shared MLP", summary["dense_baseline"]["curve"]),
        ("Bayesian table", summary["bayes_baseline"]["curve"]),
    )
    for label, records in series:
        steps = [record["step"] for record in records]
        axes[0, 0].plot(
            steps,
            [record["word_accuracy"] for record in records],
            label=label,
            color=colors[label],
            linewidth=2.25,
        )
        axes[0, 1].plot(
            steps,
            np.maximum(
                [record["clean_bce"] for record in records],
                1e-6,
            ),
            label=label,
            color=colors[label],
            linewidth=2.15,
        )

    for label, records in series[:3]:
        axes[1, 0].plot(
            [record["step"] for record in records],
            np.maximum(
                [record["bit_uncertainty"] for record in records],
                1e-4,
            ),
            label=label,
            color=colors[label],
            linewidth=2.15,
        )

    for axis in axes.flat[:3]:
        axis.set_xscale("symlog", linthresh=100)
        axis.set_xlabel("Optimization steps (100 fresh examples per member)")
        axis.grid(color="#d8e0e8", alpha=0.75)
        axis.set_facecolor("#f8fafc")
    axes[0, 0].set_title("Exact 12-bit word recovery")
    axes[0, 0].set_ylabel("Clean exact-word accuracy")
    axes[0, 0].set_ylim(-0.02, 1.02)
    axes[0, 0].legend(loc="lower right", fontsize=8.5)
    axes[0, 1].set_title("Clean full-domain loss")
    axes[0, 1].set_ylabel("Binary cross-entropy")
    axes[0, 1].set_yscale("log")
    axes[1, 0].set_title("Hard-prediction disagreement")
    axes[1, 0].set_ylabel("Summed bit uncertainty")
    axes[1, 0].set_yscale("log")

    architectures = ("shared", "parity3")
    strategies = ("uniform", "active")
    lookup = {
        (cell["architecture"], cell["replay_strategy"]): cell["word_accuracy"]
        for cell in summary["scan"]["cells"]
    }
    matrix = np.asarray(
        [
            [lookup[(architecture, strategy)] for strategy in strategies]
            for architecture in architectures
        ]
    )
    image = axes[1, 1].imshow(
        matrix,
        vmin=0,
        vmax=1,
        cmap="Blues",
        aspect="auto",
    )
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            value = matrix[row, column]
            axes[1, 1].text(
                column,
                row,
                f"{100 * value:.2f}%",
                ha="center",
                va="center",
                color="#ffffff" if value > 0.55 else "#0f172a",
                fontweight="bold",
            )
    axes[1, 1].set_xticks(range(len(strategies)), strategies)
    axes[1, 1].set_yticks(range(len(architectures)), architectures)
    axes[1, 1].set_xlabel("Replay selection")
    axes[1, 1].set_ylabel("Representation")
    axes[1, 1].set_title("Single-model accuracy after 2,000 steps")
    figure.colorbar(image, ax=axes[1, 1], fraction=0.046, pad=0.04)

    figure.suptitle(
        "Posterior replay recovers the hidden six-bit map under 25% fresh noise",
        fontsize=17,
        fontweight="bold",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180, facecolor=figure.get_facecolor())
    plt.close(figure)


def main() -> None:
    args = parse_args()
    summary = {
        "kind": "posterior-replay-fresh-noise-summary",
        "protocol": {
            "input_bits": 12,
            "output_bits": 12,
            "clean_domain_size": 4096,
            "fresh_examples_per_step_per_member": 100,
            "independent_output_bit_flip_probability": 0.25,
            "clean_domain_role": "checkpoint evaluation only",
            "formula_or_exact_circuit_seeded": False,
        },
        "scan": summarize_scan(args.scan_run),
        "main": summarize_run(args.main_run),
        "replicate": summarize_run(args.replicate_run),
        "dense_baseline": summarize_run(args.dense_run),
        "bayes_baseline": summarize_run(args.bayes_run),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    plot_summary(summary, args.output_figure)
    print(args.output_json)
    print(args.output_figure)


if __name__ == "__main__":
    main()
