#!/usr/bin/env python3
"""Generate the two 4x4 report figures from compact replay evidence."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import statistics
from typing import Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


BLUE = "#4477AA"
RED = "#CC6677"
PDF_METADATA = {
    "Creator": "Quantum Harness CP-AFQMC ergodicity audit",
    "CreationDate": None,
    "ModDate": None,
}


def _truth(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = 0.5 * (start + end - 1)
        for position in range(start, end):
            ranks[order[position]] = rank
        start = end
    return ranks


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        raise ValueError("correlation requires paired nontrivial samples")
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    numerator = math.fsum(
        (a - left_mean) * (b - right_mean)
        for a, b in zip(left, right)
    )
    denominator = math.sqrt(
        math.fsum((value - left_mean) ** 2 for value in left)
        * math.fsum((value - right_mean) ** 2 for value in right)
    )
    return numerator / denominator


def _spearman(left: Sequence[float], right: Sequence[float]) -> float:
    return _pearson(_ranks(left), _ranks(right))


def load_rows(path: Path) -> list[dict[str, float | int | bool]]:
    with path.open(newline="") as handle:
        source = list(csv.DictReader(handle))
    rows: list[dict[str, float | int | bool]] = []
    for row in source:
        if row["ensemble"] != "TI":
            continue
        if not _truth(row["alive"]) or _truth(row["numerically_ambiguous"]):
            continue
        rows.append(
            {
                "sample_id": int(row["sample_id"]),
                "log_weight": float(row["logabs_d_ti"]),
                "log_efficiency": (
                    float(row["log_q_prop"]) - float(row["logabs_d_ti"])
                ),
                "prefix_barrier": float(row["prefix_barrier"]),
                "worst": False,
            }
        )
    if not rows:
        raise ValueError("no alive, unambiguous TI paths")
    count = max(1, math.ceil(0.01 * len(rows)))
    worst_ids = {
        int(row["sample_id"])
        for row in sorted(
            rows,
            key=lambda item: (
                float(item["log_efficiency"]), int(item["sample_id"])
            ),
        )[:count]
    }
    weight_center = statistics.median(
        float(row["log_weight"]) for row in rows
    )
    efficiency_center = statistics.median(
        float(row["log_efficiency"]) for row in rows
    )
    for row in rows:
        row["worst"] = int(row["sample_id"]) in worst_ids
        row["log_weight_centered"] = float(row["log_weight"]) - weight_center
        row["log_efficiency_centered"] = (
            float(row["log_efficiency"]) - efficiency_center
        )
    return rows


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans"],
            "font.size": 9,
            "axes.labelsize": 10,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def _split(
    rows: Iterable[dict[str, float | int | bool]],
) -> tuple[list[dict[str, float | int | bool]], list[dict[str, float | int | bool]]]:
    rows = list(rows)
    return (
        [row for row in rows if not bool(row["worst"])],
        [row for row in rows if bool(row["worst"])],
    )


def _save(fig: plt.Figure, prefix: Path) -> None:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        prefix.with_suffix(".pdf"),
        bbox_inches="tight",
        metadata=PDF_METADATA,
    )
    fig.savefig(
        prefix.with_suffix(".png"),
        dpi=300,
        bbox_inches="tight",
        metadata={"Software": PDF_METADATA["Creator"]},
    )
    plt.close(fig)


def plot_weight_efficiency(
    rows: Sequence[dict[str, float | int | bool]], output: Path
) -> None:
    regular, worst = _split(rows)
    fig, ax = plt.subplots(figsize=(4.45, 3.45))
    ax.scatter(
        [row["log_weight_centered"] for row in regular],
        [row["log_efficiency_centered"] for row in regular],
        s=9,
        alpha=0.30,
        color=BLUE,
        edgecolors="none",
        rasterized=True,
    )
    ax.scatter(
        [row["log_weight_centered"] for row in worst],
        [row["log_efficiency_centered"] for row in worst],
        s=28,
        color=RED,
        edgecolors="black",
        linewidths=0.4,
        label="worst 1%",
        zorder=3,
    )
    ax.axvline(0.0, color="0.4", linestyle="--", linewidth=0.9)
    ax.set_xlabel(
        r"$\log D_{\mathrm{TI}}-\mathrm{median}(\log D_{\mathrm{TI}})$"
    )
    ax.set_ylabel(
        r"$\log(Q_{\mathrm{CP}}/D_{\mathrm{TI}})$ (centered)"
    )
    ax.legend(frameon=False, loc="lower left")
    _save(fig, output)


def plot_prefix_barrier(
    rows: Sequence[dict[str, float | int | bool]], output: Path
) -> float:
    regular, worst = _split(rows)
    barriers = [float(row["prefix_barrier"]) for row in rows]
    efficiencies = [float(row["log_efficiency"]) for row in rows]
    rho = _spearman(efficiencies, barriers)
    fig, ax = plt.subplots(figsize=(4.45, 3.45))
    ax.scatter(
        [row["prefix_barrier"] for row in regular],
        [row["log_efficiency_centered"] for row in regular],
        s=9,
        alpha=0.30,
        color=BLUE,
        edgecolors="none",
        rasterized=True,
    )
    ax.scatter(
        [row["prefix_barrier"] for row in worst],
        [row["log_efficiency_centered"] for row in worst],
        s=28,
        color=RED,
        edgecolors="black",
        linewidths=0.4,
        zorder=3,
    )
    ax.text(
        0.04,
        0.07,
        rf"Spearman $\rho={rho:.3f}$",
        transform=ax.transAxes,
    )
    ax.set_xlabel("prefix barrier")
    ax.set_ylabel(
        r"$\log(Q_{\mathrm{CP}}/D_{\mathrm{TI}})$ (centered)"
    )
    _save(fig, output)
    return rho


def main() -> int:
    solution = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=solution / "data/replay_strata.csv",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=solution / "data/sampling_efficiency_summary.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=solution / "figures",
    )
    args = parser.parse_args()

    _style()
    rows = load_rows(args.input)
    plot_weight_efficiency(
        rows, args.output_dir / "pqmc_weight_efficiency"
    )
    rho = plot_prefix_barrier(rows, args.output_dir / "prefix_barrier")

    expected = json.loads(args.summary.read_text())
    expected_rho = float(
        expected["correlations"]["spearman_efficiency_vs_prefix_barrier"]
    )
    expected_worst = {
        int(row["sample_id"]) for row in expected["worst_paths"]
    }
    actual_worst = {
        int(row["sample_id"]) for row in rows if bool(row["worst"])
    }
    if abs(rho - expected_rho) > 1.0e-12:
        raise RuntimeError(f"rho mismatch: {rho} != {expected_rho}")
    if actual_worst != expected_worst:
        raise RuntimeError("worst-one-percent sample IDs do not match summary")
    print(
        f"figures generated: paths={len(rows)} worst={len(actual_worst)} "
        f"rho={rho:.6f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
