#!/usr/bin/env python3
"""Plot the audited Stage 4 coverage and numerical-only sentinel evidence."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _number(row: dict[str, str], key: str) -> float:
    return float(row[key])


def _save(fig: plt.Figure, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output.with_suffix(".png"), dpi=220, bbox_inches="tight")
    fig.savefig(output.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def _coverage_plot(rows: list[dict[str, str]], output_dir: Path) -> None:
    core = [row for row in rows if row["cohort"] == "half_filled_core"]
    g_values = (0.25, 0.5, 1.0)
    t_values = (0.25, 0.5, 1.0)
    panels: list[tuple[str, float | None]] = [
        ("All Stage 4 cells (of 6)", None),
        (r"$\beta=4$ cells (of 3)", 4.0),
        (r"$\beta=8$ cells (of 3)", 8.0),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.2), constrained_layout=True)
    for axis, (title, beta) in zip(axes, panels):
        matrix = np.zeros((len(g_values), len(t_values)))
        for g_index, g_ratio in enumerate(g_values):
            for t_index, t in enumerate(t_values):
                selected = [
                    row
                    for row in core
                    if _number(row, "g_b_over_g_a") == g_ratio
                    and _number(row, "t") == t
                    and (
                        beta is None
                        or _number(row, "beta") == beta
                    )
                ]
                matrix[g_index, t_index] = sum(
                    row["audit_status"] == "PASS" for row in selected
                )
        maximum = 6 if beta is None else 3
        image = axis.imshow(
            matrix,
            origin="lower",
            cmap="viridis",
            vmin=0,
            vmax=maximum,
            aspect="equal",
        )
        for g_index in range(len(g_values)):
            for t_index in range(len(t_values)):
                axis.text(
                    t_index,
                    g_index,
                    f"{int(matrix[g_index, t_index])}",
                    ha="center",
                    va="center",
                    color="white" if matrix[g_index, t_index] < maximum / 2 else "black",
                    fontsize=10,
                )
        axis.set_xticks(range(len(t_values)), [str(value) for value in t_values])
        axis.set_yticks(range(len(g_values)), [str(value) for value in g_values])
        axis.set_xlabel(r"$t/g_A$")
        axis.set_ylabel(r"$g_B/g_A$")
        axis.set_title(title, fontsize=10)
        fig.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    fig.suptitle(
        "Stage 4 cells with all four replicas at ESS ≥ 40",
        fontsize=12,
    )
    _save(fig, output_dir / "stage4_audited_coverage")


def _sentinel_plot(
    rows: list[dict[str, str]],
    release: dict[str, object],
    m10_summary: dict[str, object] | None,
    output_dir: Path,
) -> None:
    selected = release.get("selected")
    if not isinstance(selected, dict):
        return
    chosen = sorted(
        [
            row
            for row in rows
            if row["cohort"] == "half_filled_core"
            and row["audit_status"] == "PASS"
            and _number(row, "g_b_over_g_a")
            == float(selected["g_b_over_g_a"])
            and _number(row, "t") == float(selected["t"])
            and _number(row, "mu") == float(selected["mu"])
            and _number(row, "beta") == float(selected["beta"])
        ],
        key=lambda row: int(float(row["m"])),
    )
    if len(chosen) != 3:
        return
    sizes = np.array([_number(row, "m") for row in chosen])
    partial = (
        dict(m10_summary["m10_passing_replica_aggregate"])
        if m10_summary is not None
        else None
    )
    fig, axes = plt.subplots(2, 2, figsize=(8.2, 6.4), constrained_layout=True)
    plots = [
        ("q_combined", r"$Q_{\rm combined}$"),
        ("staggered_structure", r"$S(\pi)$"),
    ]
    for axis, (metric, label) in zip(axes[0], plots):
        axis.errorbar(
            sizes,
            [_number(row, f"{metric}_mean") for row in chosen],
            yerr=[_number(row, f"{metric}_stderr") for row in chosen],
            marker="o",
            capsize=3,
        )
        if partial is not None:
            axis.errorbar(
                [10],
                [float(partial[f"{metric}_mean"])],
                yerr=[float(partial[f"{metric}_stderr"])],
                marker="s",
                markerfacecolor="none",
                capsize=3,
                color="black",
                label="m=10 passing subset",
            )
            axis.legend(frameon=False, fontsize=8)
        axis.set_xlabel("$m$")
        axis.set_ylabel(label)
        axis.grid(alpha=0.25)
    for metric, label, color in (
        ("q_a_susceptibility", r"$\chi_A$", "tab:blue"),
        ("q_b_susceptibility", r"$\chi_B$", "tab:orange"),
    ):
        axes[1, 0].errorbar(
            sizes,
            [_number(row, f"{metric}_mean") for row in chosen],
            yerr=[_number(row, f"{metric}_stderr") for row in chosen],
            marker="o",
            capsize=3,
            label=label,
            color=color,
        )
        if partial is not None:
            axes[1, 0].errorbar(
                [10],
                [float(partial[f"{metric}_mean"])],
                yerr=[float(partial[f"{metric}_stderr"])],
                marker="s",
                markerfacecolor="none",
                capsize=3,
                color=color,
            )
    axes[1, 0].set_xlabel("$m$")
    axes[1, 0].set_ylabel("contact-subtracted susceptibility")
    axes[1, 0].legend(frameon=False)
    axes[1, 0].grid(alpha=0.25)
    for metric, label, color in (
        ("q_a_binder", r"$U_A$", "tab:blue"),
        ("q_b_binder", r"$U_B$", "tab:orange"),
        ("correlation_length_over_m", r"$\xi/m$", "tab:green"),
    ):
        axes[1, 1].errorbar(
            sizes,
            [_number(row, f"{metric}_mean") for row in chosen],
            yerr=[_number(row, f"{metric}_stderr") for row in chosen],
            marker="o",
            capsize=3,
            label=label,
            color=color,
        )
        if partial is not None:
            axes[1, 1].errorbar(
                [10],
                [float(partial[f"{metric}_mean"])],
                yerr=[float(partial[f"{metric}_stderr"])],
                marker="s",
                markerfacecolor="none",
                capsize=3,
                color=color,
            )
    axes[1, 1].set_xlabel("$m$")
    axes[1, 1].set_ylabel("dimensionless diagnostic")
    axes[1, 1].set_yscale("symlog", linthresh=0.1)
    axes[1, 1].legend(frameon=False)
    axes[1, 1].grid(alpha=0.25)
    fig.suptitle(
        (
            r"Numerical-only sentinel selection: "
            rf"$g_B/g_A={float(selected['g_b_over_g_a']):g}$, "
            rf"$t/g_A={float(selected['t']):g}$, "
            rf"$\beta g_A={float(selected['beta']):g}$"
            "\nNot thermodynamic phase evidence"
            + (
                "; m=10 marker uses 2/4 passing replicas"
                if partial is not None
                else ""
            )
        ),
        fontsize=11,
    )
    _save(fig, output_dir / "stage4_beta4_sentinel_selection")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell-table", required=True, type=Path)
    parser.add_argument("--sentinel-release", required=True, type=Path)
    parser.add_argument("--m10-summary", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    rows = _read_rows(args.cell_table)
    release = json.loads(args.sentinel_release.read_text(encoding="utf-8"))
    m10_summary = (
        json.loads(args.m10_summary.read_text(encoding="utf-8"))
        if args.m10_summary is not None
        else None
    )
    _coverage_plot(rows, args.output_dir)
    _sentinel_plot(rows, release, m10_summary, args.output_dir)


if __name__ == "__main__":
    main()
