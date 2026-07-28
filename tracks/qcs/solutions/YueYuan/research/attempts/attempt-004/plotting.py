from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import analysis


REQUIRED_FIGURES = (
    "model_optimization_history.png",
    "hessian_spectrum.png",
    "queries_to_target_vs_k.png",
    "shots_to_target_vs_k.png",
    "advantage_vs_gap.png",
    "success_rate_vs_shots.png",
    "failure_mode.png",
    "recovery_study.png",
)


def _simple_line(path: Path, title: str, x, y, ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(x, y, marker="o")
    ax.set_title(title)
    ax.set_xlabel("index")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _band_line(path: Path, title: str, x, y, low, high, ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(x, y, marker="o")
    ax.fill_between(x, low, high, alpha=0.2)
    ax.set_title(title)
    ax.set_xlabel("index")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _interval_yerr(rows: list[dict], median_field: str, low_field: str, high_field: str):
    lower = []
    upper = []
    for row in rows:
        median = row[median_field]
        low = row[low_field] if row[low_field] is not None else median
        high = row[high_field] if row[high_field] is not None else median
        lower.append(max(0.0, median - low))
        upper.append(max(0.0, high - median))
    return [lower, upper]


def _plot_k_sweep(path: Path, rows: list[dict], metric: str, low: str, high: str, title: str, ylabel: str) -> None:
    max_shots = max([row["shots_per_query"] for row in rows], default=0)
    grouped = defaultdict(list)
    for row in rows:
        if row["method"] != "hessian_subspace_nelder_mead":
            continue
        if row["shots_per_query"] != max_shots or row[metric] is None:
            continue
        grouped[(row["system"], row["mismatch"])].append(row)

    fig, ax = plt.subplots(figsize=(7, 4.4))
    for (system, mismatch), items in sorted(grouped.items()):
        ordered = sorted(items, key=lambda row: row["k"])
        ax.errorbar(
            [row["k"] for row in ordered],
            [row[metric] for row in ordered],
            yerr=_interval_yerr(ordered, metric, low, high),
            marker="o",
            capsize=3,
            label=f"{system} {mismatch}",
        )
    ax.set_title(title)
    ax.set_xlabel("Hessian subspace dimension k")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_advantage(path: Path, rows: list[dict]) -> None:
    max_shots = max([row["shots_per_query"] for row in rows], default=0)
    benchmark_k = {"one_qubit_x": 3, "two_qubit_cz": 15}
    labels = []
    speedups = []
    for system in ("one_qubit_x", "two_qubit_cz"):
        for mismatch in ("small", "medium", "large"):
            full = _find_row(rows, system, mismatch, max_shots, "full_space_nelder_mead")
            hessian = _find_row(
                rows,
                system,
                mismatch,
                max_shots,
                "hessian_subspace_nelder_mead",
                benchmark_k[system],
            )
            if not full or not hessian:
                continue
            if full["median_queries_to_target"] is None or hessian["median_queries_to_target"] is None:
                continue
            labels.append(f"{system}\n{mismatch}")
            speedups.append(full["median_queries_to_target"] / hessian["median_queries_to_target"])

    _simple_bar(path, "Full-space / Hessian Query Ratio", labels, speedups, "query ratio")


def _plot_success_vs_shots(path: Path, rows: list[dict]) -> None:
    benchmark_k = {"one_qubit_x": 3, "two_qubit_cz": 15}
    grouped = defaultdict(list)
    for row in rows:
        if row["method"] == "full_space_nelder_mead":
            grouped[(row["system"], row["mismatch"], "full")].append(row)
        elif (
            row["method"] == "hessian_subspace_nelder_mead"
            and row["k"] == benchmark_k.get(row["system"])
        ):
            grouped[(row["system"], row["mismatch"], "hessian")].append(row)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), sharey=True)
    handles = []
    labels = []
    for ax, system in zip(axes, ("one_qubit_x", "two_qubit_cz")):
        for (row_system, mismatch, method), items in sorted(grouped.items()):
            if row_system != system:
                continue
            ordered = sorted(items, key=lambda row: row["shots_per_query"])
            handle = ax.errorbar(
                [row["shots_per_query"] for row in ordered],
                [row["success_rate"] for row in ordered],
                yerr=[
                    [row["success_rate"] - row["success_ci95_low"] for row in ordered],
                    [row["success_ci95_high"] - row["success_rate"] for row in ordered],
                ],
                marker="o",
                linestyle="-" if method == "hessian" else "--",
                capsize=3,
                label=f"{mismatch} {method}",
            )
            if system == "one_qubit_x":
                handles.append(handle)
                labels.append(f"{mismatch} {method}")
        ax.set_title(system)
        ax.set_xlabel("shots per query")
        ax.set_xscale("log", base=2)
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, alpha=0.3)
    axes[0].set_ylabel("success rate")
    fig.suptitle("Success Rate vs Shots")
    fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=8)
    fig.tight_layout(rect=[0, 0.18, 1, 0.95])
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_failure_mode(path: Path, rows: list[dict]) -> None:
    max_shots = max([row["shots_per_query"] for row in rows], default=0)
    benchmark_k = {"one_qubit_x": 3, "two_qubit_cz": 15}
    labels = []
    failures = []
    lower = []
    upper = []
    for system in ("one_qubit_x", "two_qubit_cz"):
        for mismatch in ("small", "medium", "large"):
            row = _find_row(
                rows,
                system,
                mismatch,
                max_shots,
                "hessian_subspace_nelder_mead",
                benchmark_k[system],
            )
            if not row:
                continue
            failure = 1.0 - row["success_rate"]
            labels.append(f"{system}\n{mismatch}")
            failures.append(failure)
            lower.append(max(0.0, failure - (1.0 - row["success_ci95_high"])))
            upper.append(max(0.0, (1.0 - row["success_ci95_low"]) - failure))

    fig, ax = plt.subplots(figsize=(7, 4.4))
    ax.bar(range(len(labels)), failures, yerr=[lower, upper], capsize=3)
    ax.set_title("Failure Mode")
    ax.set_ylabel("failure rate")
    ax.set_ylim(0.0, 1.05)
    ax.set_xticks(range(len(labels)), labels, rotation=35, ha="right")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_recovery_study(path: Path, rows: list[dict]) -> None:
    recovery_rows = analysis.recovery_study_rows(rows)
    max_shots = max([row["shots_per_query"] for row in recovery_rows], default=0)
    focus = [row for row in recovery_rows if row["shots_per_query"] == max_shots]
    labels = [f"{row['system']}\n{row['mismatch']}" for row in focus]
    benchmark = [row["benchmark_success_rate"] for row in focus]
    best = [row["best_success_rate"] for row in focus]
    xs = list(range(len(focus)))
    width = 0.38

    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    ax.bar([x - width / 2 for x in xs], benchmark, width=width, label="benchmark k")
    ax.bar([x + width / 2 for x in xs], best, width=width, label="best widened k")
    for x, row in zip(xs, focus):
        ax.text(
            x + width / 2,
            row["best_success_rate"] + 0.03,
            f"k={row['best_k']}",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    ax.set_title("Recovery From Widening Hessian k")
    ax.set_ylabel("success rate")
    ax.set_ylim(0.0, 1.1)
    ax.set_xticks(xs, labels, rotation=35, ha="right")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def make_device_informed_recovery(results_dir: Path) -> Path:
    results_dir = Path(results_dir)
    summary = analysis.write_summary(results_dir)
    analysis.write_device_informed_tables(results_dir, summary)
    rows = analysis.device_informed_recovery_rows(summary["groups"])
    figures = results_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    path = figures / "device_informed_recovery.png"
    labels = [f"{row['system']}\n{row['mismatch']}" for row in rows]
    fixed = [row["fixed_hessian_success_rate"] for row in rows]
    widen = [row["widen_only_success_rate"] for row in rows]
    informed = [row["device_informed_success_rate"] for row in rows]
    xs = list(range(len(rows)))
    width = 0.25

    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    ax.bar([x - width for x in xs], fixed, width=width, label="fixed Hessian")
    ax.bar(xs, widen, width=width, label="widen-only")
    ax.bar([x + width for x in xs], informed, width=width, label="device-informed")
    ax.set_title("Device-Informed Adaptive Recovery")
    ax.set_ylabel("success rate")
    ax.set_ylim(0.0, 1.1)
    ax.set_xticks(xs, labels, rotation=35, ha="right")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _simple_bar(path: Path, title: str, labels: list[str], values: list[float], ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.4))
    ax.bar(range(len(labels)), values)
    ax.axhline(1.0, color="black", linewidth=0.8, linestyle="--")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xticks(range(len(labels)), labels, rotation=35, ha="right")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _find_row(rows, system, mismatch, shots, method, k=None):
    for row in rows:
        if row["system"] != system or row["mismatch"] != mismatch:
            continue
        if row["shots_per_query"] != shots or row["method"] != method:
            continue
        if k is not None and row["k"] != k:
            continue
        return row
    return None


def _history_bands(histories: list[dict]):
    grouped = defaultdict(list)
    for row in histories:
        grouped[int(row["step"])].append(row["loss"])
    steps = sorted(grouped)[:120]
    medians = []
    lows = []
    highs = []
    for step in steps:
        values = sorted(grouped[step])
        medians.append(statistics.median(values))
        lows.append(analysis.percentile(values, 0.25))
        highs.append(analysis.percentile(values, 0.75))
    return steps, medians, lows, highs


def _spectrum_bands(spectra: list[dict]):
    if not spectra:
        return [0], [1.0], [1.0], [1.0]
    ordered = [sorted([abs(value) for value in row["eigenvalues"]], reverse=True) for row in spectra]
    width = min(len(row) for row in ordered)
    xs = list(range(width))
    medians = []
    lows = []
    highs = []
    for index in xs:
        values = [row[index] for row in ordered]
        medians.append(statistics.median(values))
        lows.append(analysis.percentile(values, 0.25))
        highs.append(analysis.percentile(values, 0.75))
    return xs, medians, lows, highs


def make_all(results_dir: Path) -> list[Path]:
    results_dir = Path(results_dir)
    figures = results_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    summary = analysis.write_summary(results_dir)
    analysis.write_summary_tables(results_dir, summary)
    rows = summary["groups"]
    histories = analysis.read_jsonl(results_dir / "open_loop_history.jsonl")
    spectra_path = results_dir / "hessian_spectra.json"
    spectra = json.loads(spectra_path.read_text()) if spectra_path.exists() else []

    steps, losses, loss_low, loss_high = _history_bands(histories)
    _band_line(
        figures / "model_optimization_history.png",
        "Model Optimization History",
        steps,
        losses,
        loss_low,
        loss_high,
        "infidelity",
    )
    ranks, eigenvalues, eigen_low, eigen_high = _spectrum_bands(spectra)
    _band_line(
        figures / "hessian_spectrum.png",
        "Hessian Spectrum",
        ranks,
        eigenvalues,
        eigen_low,
        eigen_high,
        "|eigenvalue|",
    )

    _plot_k_sweep(
        figures / "queries_to_target_vs_k.png",
        rows,
        "median_queries_to_target",
        "queries_to_target_q25",
        "queries_to_target_q75",
        "Queries To Target vs k",
        "queries",
    )
    _plot_k_sweep(
        figures / "shots_to_target_vs_k.png",
        rows,
        "median_shots_to_target",
        "shots_to_target_q25",
        "shots_to_target_q75",
        "Shots To Target vs k",
        "shots",
    )
    _plot_advantage(figures / "advantage_vs_gap.png", rows)
    _plot_success_vs_shots(figures / "success_rate_vs_shots.png", rows)
    _plot_failure_mode(figures / "failure_mode.png", rows)
    _plot_recovery_study(figures / "recovery_study.png", rows)
    return [figures / name for name in REQUIRED_FIGURES]
