#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


COLORS = {"unbiased": "#D55E00", "traditional": "#0072B2", "traditional_mps": "#009E73"}
LABELS = {"unbiased": "Unbiased", "traditional": "Traditional", "traditional_mps": "Traditional + MPS"}


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 8,
            "axes.labelsize": 9,
            "axes.titlesize": 9,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def save(fig, directory: Path, name: str) -> None:
    fig.tight_layout()
    fig.savefig(directory / f"{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(directory / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def load_aggregate(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def select_plot_rows(
    rows: list[dict[str, str]],
    length: int | None = None,
    rg_levels: int | None = None,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    if not rows:
        return [], {}
    selected_length = max(int(row["length"]) for row in rows) if length is None else length
    at_length = [row for row in rows if int(row["length"]) == selected_length]
    selected_rg = (
        min(int(row["rg_levels"]) for row in at_length)
        if rg_levels is None
        else rg_levels
    )
    selected = [row for row in at_length if int(row["rg_levels"]) == selected_rg]
    return selected, {"length": selected_length, "rg_levels": selected_rg}


def grouped_errorbar(rows, quantity: str, ylabel: str, output: Path, name: str) -> None:
    fig, ax = plt.subplots(figsize=(4.8, 3.0))
    for arm in ("unbiased", "traditional", "traditional_mps"):
        selected = sorted((row for row in rows if row["arm"] == arm), key=lambda row: int(row["chi"]))
        if not selected:
            continue
        x = np.asarray([int(row["chi"]) for row in selected])
        y = np.asarray([float(row[f"{quantity}_mean"]) for row in selected])
        error = np.asarray([float(row.get(f"{quantity}_sem", 0.0) or 0.0) for row in selected])
        ax.errorbar(x, y, yerr=error, marker="o", capsize=3, color=COLORS[arm], label=LABELS[arm])
    ax.set_xlabel("MPS bond dimension chi")
    ax.set_ylabel(ylabel)
    ax.legend(frameon=False)
    save(fig, output, name)


def plot_objectives(root: Path, output: Path, selection: dict[str, int]) -> None:
    fig, ax = plt.subplots(figsize=(5.2, 3.1))
    found = False
    for training_path in sorted(root.rglob("training.json")):
        summary_path = training_path.parent / "summary.json"
        if summary_path.exists() and selection:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            if int(summary.get("length", -1)) != selection["length"] or int(
                summary.get("rg_levels", -1)
            ) != selection["rg_levels"]:
                continue
        training = json.loads(training_path.read_text(encoding="utf-8"))
        trajectory = training.get("trajectory", [])
        if not trajectory:
            continue
        found = True
        chi = training["chi"]
        seed = training["seed"]
        ax.plot(
            [row["step"] + 1 for row in trajectory],
            [row["objective"] for row in trajectory],
            color={2: "#56B4E9", 4: "#009E73", 8: "#CC79A7"}.get(chi, "#000000"),
            alpha=0.55,
            label=f"chi={chi}, seed={seed}",
        )
    if not found:
        plt.close(fig)
        return
    ax.set_xlabel("Optimization step")
    ax.set_ylabel("Cumulative VMCRG objective change")
    handles, labels = ax.get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    ax.legend(unique.values(), unique.keys(), frameon=False, ncol=2)
    save(fig, output, "objective_vs_step")


def plot_training_patch_distance(root: Path, output: Path, selection: dict[str, int]) -> None:
    fig, ax = plt.subplots(figsize=(5.2, 3.1))
    found = False
    for training_path in sorted(root.rglob("training.json")):
        summary_path = training_path.parent / "summary.json"
        if summary_path.exists() and selection:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            if int(summary.get("length", -1)) != selection["length"] or int(
                summary.get("rg_levels", -1)
            ) != selection["rg_levels"]:
                continue
        training = json.loads(training_path.read_text(encoding="utf-8"))
        trajectory = training.get("trajectory", [])
        if not trajectory:
            continue
        found = True
        ax.plot(
            [row["step"] + 1 for row in trajectory],
            [row["patch_total_variation"] for row in trajectory],
            alpha=0.55,
            label=f"chi={training['chi']}, seed={training['seed']}",
        )
    if not found:
        plt.close(fig)
        return
    ax.set_xlabel("Optimization step")
    ax.set_ylabel("Patch total variation distance")
    ax.legend(frameon=False, ncol=2)
    save(fig, output, "patch_distance_vs_step")


def plot_runtime(root: Path, output: Path) -> None:
    benchmark = root / "benchmarks/benchmark.json"
    if not benchmark.exists():
        return
    rows = json.loads(benchmark.read_text(encoding="utf-8"))["rows"]
    chi = np.asarray([row["chi"] for row in rows])
    fig, ax = plt.subplots(figsize=(5.0, 3.1))
    ax.plot(chi, [row["direct_per_patch_seconds"] for row in rows], marker="o", label="Direct MPS")
    ax.plot(chi, [row["lookup_per_patch_seconds"] for row in rows], marker="s", label="512 lookup")
    ax.plot(chi, [row["incremental_proposal_seconds"] for row in rows], marker="^", label="Incremental proposal")
    ax.set_yscale("log")
    ax.set_xlabel("MPS bond dimension chi")
    ax.set_ylabel("Wall time per operation (s)")
    ax.legend(frameon=False)
    save(fig, output, "runtime_comparison")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create publication-style Challenge #28 figures")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1] / "results/mps_challenge")
    args = parser.parse_args()
    output = args.root / "figures"
    output.mkdir(parents=True, exist_ok=True)
    style()
    rows = load_aggregate(args.root / "summary_aggregate.csv")
    rows, selection = select_plot_rows(rows)
    (output / "plot_selection.json").write_text(
        json.dumps(selection, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    plot_objectives(args.root, output, selection)
    plot_training_patch_distance(args.root, output, selection)
    if rows:
        grouped_errorbar(rows, "patch_tv", "Patch total variation distance", output, "error_vs_bond_dimension")
        grouped_errorbar(rows, "two_point_10", "Residual correlation C(1,0)", output, "two_point_correlations")
        grouped_errorbar(rows, "four_spin", "Held-out four-spin expectation", output, "held_out_four_spin")
        grouped_errorbar(rows, "tau_int", "Integrated autocorrelation time (sweeps)", output, "autocorrelation_comparison")
        grouped_errorbar(rows, "ess_per_second", "Effective samples per second (1/s)", output, "ess_per_second")
    plot_runtime(args.root, output)
    print(f"figures written to {output}", flush=True)


if __name__ == "__main__":
    main()
