"""Cross-model synthesis figures derived from frozen report values."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

from analysis.sources import ModelResult


COLORS = ("#2878B5", "#D95F02", "#2A9D6F")
SHORT_NAMES = ("Clean Ising", "Nishimori", "Weak self-dual")


def build_comparison_plots(
    models: Sequence[ModelResult], output_dir: Path
) -> Dict[str, Path]:
    if len(models) != 3:
        raise ValueError("comparison plots require exactly three models")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    _apply_style()
    paths = {
        "central-charge-intervals": destination / "central-charge-intervals.png",
        "target-deviation": destination / "target-deviation.png",
        "precision-runtime": destination / "precision-runtime.png",
        "validation-gates": destination / "validation-gates.png",
    }
    _central_charge_intervals(models, paths["central-charge-intervals"])
    _target_deviation(models, paths["target-deviation"])
    _precision_runtime(models, paths["precision-runtime"])
    _validation_gates(models, paths["validation-gates"])
    return paths


def _apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlesize": 16,
            "axes.labelsize": 12,
            "axes.edgecolor": "#203040",
            "axes.linewidth": 0.9,
            "axes.grid": True,
            "grid.color": "#DDE5EC",
            "grid.linewidth": 0.8,
            "grid.alpha": 0.9,
            "figure.facecolor": "white",
            "axes.facecolor": "#F8FAFC",
            "savefig.facecolor": "white",
        }
    )


def _central_charge_intervals(models: Sequence[ModelResult], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    y = np.arange(len(models))
    for index, (model, color) in enumerate(zip(models, COLORS)):
        left = model.estimate - model.ci95[0]
        right = model.ci95[1] - model.estimate
        ax.errorbar(
            model.estimate,
            index,
            xerr=np.asarray([[left], [right]]),
            fmt="o",
            markersize=9,
            capsize=5,
            color=color,
            ecolor=color,
            linewidth=2.2,
            label="Estimate with 95% CI" if index == 0 else None,
        )
        ax.scatter(
            model.target,
            index,
            marker="D",
            s=72,
            facecolor="white",
            edgecolor="#172B3A",
            linewidth=1.8,
            zorder=4,
            label="Benchmark target" if index == 0 else None,
        )
        ax.text(
            model.ci95[1] + 0.0018,
            index,
            f"{model.estimate:.4f}",
            va="center",
            fontsize=10,
            color="#203040",
        )
    ax.set_yticks(y, SHORT_NAMES)
    ax.invert_yaxis()
    ax.set_xlabel("Central charge or effective central charge")
    ax.set_title("Three central-charge verifications")
    ax.set_xlim(0.425, 0.515)
    ax.legend(loc="lower right", frameon=True, framealpha=1.0)
    ax.grid(axis="y", visible=False)
    _save(fig, path)


def _target_deviation(models: Sequence[ModelResult], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    z_values = np.asarray(
        [(model.estimate - model.target) / model.standard_error for model in models]
    )
    y = np.arange(len(models))
    ax.axvspan(-1.96, 1.96, color="#DDEFE8", alpha=0.85, label="Nominal 95% band")
    ax.axvline(0.0, color="#203040", linewidth=1.2)
    ax.axvline(-1.96, color="#4B6F61", linewidth=1.0, linestyle="--")
    ax.axvline(1.96, color="#4B6F61", linewidth=1.0, linestyle="--")
    for index, (z_value, color) in enumerate(zip(z_values, COLORS)):
        ax.scatter(z_value, index, s=115, color=color, edgecolor="white", linewidth=1.2)
        ax.text(
            z_value + (0.10 if z_value >= 0 else -0.10),
            index - 0.17,
            f"{z_value:+.2f} SE",
            ha="left" if z_value >= 0 else "right",
            fontsize=10,
        )
    ax.set_yticks(y, SHORT_NAMES)
    ax.invert_yaxis()
    ax.set_xlim(-2.5, 2.5)
    ax.set_xlabel("(estimate - target) / standard error")
    ax.set_title("Deviation from each model's benchmark")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", frameon=True)
    _save(fig, path)


def _precision_runtime(models: Sequence[ModelResult], path: Path) -> None:
    fig, (precision_ax, runtime_ax) = plt.subplots(1, 2, figsize=(10.2, 5.2))
    x = np.arange(len(models))
    half_widths = [(model.ci95[1] - model.ci95[0]) / 2.0 for model in models]
    runtimes = [model.runtime_s for model in models]
    precision_ax.bar(x, half_widths, color=COLORS, width=0.64)
    precision_ax.set_xticks(x, SHORT_NAMES, rotation=18, ha="right")
    precision_ax.set_ylabel("95% interval half-width")
    precision_ax.set_title("Reported precision")
    precision_ax.grid(axis="x", visible=False)
    for index, value in enumerate(half_widths):
        precision_ax.text(index, value + 0.00035, f"{value:.4f}", ha="center", fontsize=10)

    runtime_ax.bar(x, runtimes, color=COLORS, width=0.64)
    runtime_ax.set_xticks(x, SHORT_NAMES, rotation=18, ha="right")
    runtime_ax.set_ylabel("Recorded end-to-end runtime (s)")
    runtime_ax.set_title("Frozen workflow runtime")
    runtime_ax.grid(axis="x", visible=False)
    for index, value in enumerate(runtimes):
        runtime_ax.text(index, value + 11, f"{value:.0f} s", ha="center", fontsize=10)
    fig.suptitle("Precision and runtime are related but not equivalent", fontsize=17)
    fig.subplots_adjust(top=0.82, bottom=0.22, wspace=0.34)
    _save(fig, path, tight=False)


def _validation_gates(models: Sequence[ModelResult], path: Path) -> None:
    categories = (
        ("Target agreement", ("target", "accuracy", "interval")),
        ("Precision", ("standard_error", "precision")),
        ("Fit stability", ("fit", "window", "systematic", "residual")),
        ("Sampling stability", ("thermal", "replica", "half", "effective_sample")),
        ("Physical oracle", ("oracle", "identity", "duality", "bond")),
        ("Numerical invariants", ("invariant", "integration")),
        ("Convergence", ("convergence", "trend")),
        ("Runtime", ("runtime",)),
    )
    matrix = np.zeros((len(categories), len(models)), dtype=int)
    for column, model in enumerate(models):
        for row, (_, tokens) in enumerate(categories):
            matches = [
                gate
                for gate in model.gates
                if gate.required
                and any(token in gate.name.lower() for token in tokens)
            ]
            if matches:
                matrix[row, column] = 1 if all(gate.passed for gate in matches) else -1

    fig, ax = plt.subplots(figsize=(8.6, 6.2))
    cmap = ListedColormap(("#C94C4C", "#E9EEF2", "#3A9D72"))
    ax.imshow(matrix, cmap=cmap, vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(np.arange(len(models)), SHORT_NAMES)
    ax.set_yticks(np.arange(len(categories)), [item[0] for item in categories])
    ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)
    ax.grid(False)
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            label = {1: "PASS", 0: "N/A", -1: "FAIL"}[int(matrix[row, column])]
            color = "white" if matrix[row, column] != 0 else "#52616B"
            ax.text(column, row, label, ha="center", va="center", color=color, weight="bold")
    ax.set_xticks(np.arange(-0.5, len(models), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(categories), 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=2)
    ax.tick_params(which="minor", bottom=False, left=False)
    ax.set_title("Required scientific-gate coverage", pad=38)
    ax.legend(
        handles=(
            Patch(facecolor="#3A9D72", label="Passed required gate"),
            Patch(facecolor="#E9EEF2", label="Different model-specific check"),
        ),
        loc="lower center",
        bbox_to_anchor=(0.5, -0.18),
        ncol=2,
        frameon=False,
    )
    fig.subplots_adjust(left=0.30, right=0.98, top=0.80, bottom=0.18)
    _save(fig, path, tight=False)


def _save(fig: plt.Figure, path: Path, tight: bool = True) -> None:
    kwargs = {"bbox_inches": "tight"} if tight else {}
    fig.savefig(
        path,
        dpi=180,
        metadata={"Software": "Quantum Harness integrated report"},
        **kwargs,
    )
    plt.close(fig)
