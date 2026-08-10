#!/usr/bin/env python3
"""Create publication-ready evidence figures for the Issue #230 report."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.ticker import ScalarFormatter  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = PROJECT_ROOT / "outputs/final/certificate-summary.csv"
UPPER_FRONTIER_PATH = (
    PROJECT_ROOT / "outputs/final/upper-contraction-frontier.csv"
)
FIGURE_DIR = PROJECT_ROOT / "docs/issue-230/figures"
BETHE_CENTER = Decimal("-0.4431471805599452862267639829951804131269")


@dataclass(frozen=True)
class SummaryRow:
    delta: Decimal
    level: int
    lower: Decimal
    upper: Decimal
    lower_error: Decimal
    upper_error: Decimal
    source_role: str


def read_summary(path: Path) -> tuple[SummaryRow, ...]:
    with path.open(encoding="utf-8", newline="") as handle:
        return tuple(
            SummaryRow(
                delta=Decimal(row["delta"]),
                level=int(row["level"]),
                lower=Decimal(row["certified_lower"]),
                upper=Decimal(row["certified_upper"]),
                lower_error=Decimal(row["lower_error"]),
                upper_error=Decimal(row["upper_error"]),
                source_role=row["source_role"],
            )
            for row in csv.DictReader(handle)
        )


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "figure.dpi": 180,
            "savefig.dpi": 240,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linewidth": 0.7,
        }
    )


def _save(fig: plt.Figure, stem: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_DIR / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(FIGURE_DIR / f"{stem}.png", bbox_inches="tight")
    plt.close(fig)


def plot_xxx_nesting(rows: tuple[SummaryRow, ...]) -> None:
    selected = sorted(
        (row for row in rows if row.delta == Decimal("1")),
        key=lambda row: row.level,
    )
    colors = ["#8DA0CB", "#66C2A5", "#FC8D62", "#7B2CBF"]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    for y, (row, color) in enumerate(zip(selected, colors, strict=True)):
        lower = float(row.lower)
        upper = float(row.upper)
        axes[0].plot([lower, upper], [y, y], color=color, lw=5, solid_capstyle="round")
        axes[0].scatter([lower, upper], [y, y], color=color, s=28, zorder=3)
    axes[0].axvline(float(BETHE_CENTER), color="#222222", ls="--", lw=1.4)
    axes[0].set_yticks(range(len(selected)), [f"level {row.level}" for row in selected])
    axes[0].set_xlabel("Certified energy-density interval")
    axes[0].set_title("Hierarchy-wide containment")

    strongest = selected[-1]
    y = 0
    lower = float(strongest.lower)
    upper = float(strongest.upper)
    axes[1].plot([lower, upper], [y, y], color=colors[-1], lw=8, solid_capstyle="round")
    axes[1].scatter([lower, upper], [y, y], color=colors[-1], s=45, zorder=3)
    axes[1].axvline(float(BETHE_CENTER), color="#222222", ls="--", lw=1.4, label="Bethe value")
    padding = 0.00012
    axes[1].set_xlim(lower - padding, upper + padding)
    axes[1].set_yticks([0], ["level 47"])
    axes[1].set_xlabel("Certified energy density")
    axes[1].set_title("Depth-47 certified interval")
    axes[1].legend(frameon=False, loc="upper right")
    fig.suptitle("Exact XXX intervals contain the independent Bethe reference", fontweight="bold")
    fig.tight_layout()
    _save(fig, "xxx-interval-nesting")


def plot_endpoint_budget(rows: tuple[SummaryRow, ...]) -> None:
    selected = sorted(
        (row for row in rows if row.delta == Decimal("1")),
        key=lambda row: row.level,
    )
    labels = [f"L{row.level}" for row in selected]
    x = list(range(len(selected)))
    width = 0.36
    fig, ax = plt.subplots(figsize=(7.4, 4.5))
    lower_errors = [float(row.lower_error) for row in selected]
    upper_errors = [float(row.upper_error) for row in selected]
    ax.bar(
        [value - width / 2 for value in x],
        lower_errors,
        width,
        label="Lower-endpoint gap",
        color="#2A9D8F",
    )
    ax.bar(
        [value + width / 2 for value in x],
        upper_errors,
        width,
        label="Upper-endpoint gap",
        color="#E76F51",
    )
    ax.set_yscale("log")
    ax.set_xticks(x, labels)
    ax.set_ylabel("Certified distance from Bethe value")
    ax.set_xlabel("Hierarchy level")
    ax.set_title("Certified endpoint-error budget across the XXX hierarchy", fontweight="bold")
    ax.legend(frameon=False)
    ax.text(
        x[-1],
        max(lower_errors[-1], upper_errors[-1]) * 1.8,
        "proof-producing\nRG + rational MPS",
        ha="center",
        va="bottom",
        fontsize=9,
        color="#4C1D95",
    )
    fig.tight_layout()
    _save(fig, "endpoint-error-budget")


def plot_symmetry_compression() -> None:
    labels = ["D=4, depth=12", "D=6, depth=12"]
    dense = [18_449, 93_329]
    blocked = [2_058, 6_882]
    retained = [100 * blocked[i] / dense[i] for i in range(2)]
    x = [0, 1]
    width = 0.34
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    ax.bar(
        [value - width / 2 for value in x],
        dense,
        width,
        label="Dense variables",
        color="#B8C0FF",
    )
    ax.bar(
        [value + width / 2 for value in x],
        blocked,
        width,
        label="Native U(1) blocks",
        color="#5A189A",
    )
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(ScalarFormatter())
    ax.set_xticks(x, labels)
    ax.set_ylabel("Optimization variables (log scale)")
    ax.set_title("Native U(1) sectors unlock deeper certified RG", fontweight="bold")
    ax.legend(frameon=False)
    for index, percentage in enumerate(retained):
        ax.text(
            index + width / 2,
            blocked[index] * 1.2,
            f"{percentage:.1f}% retained",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#3C096C",
            fontweight="bold",
        )
    fig.tight_layout()
    _save(fig, "symmetry-compression")


def plot_upper_contraction_frontier(path: Path) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = tuple(csv.DictReader(handle))
    sites = [int(row["sites"]) for row in rows]
    errors = [float(Decimal(row["upper_error_to_bethe"])) for row in rows]
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    ax.plot(
        sites,
        errors,
        marker="o",
        markersize=7,
        lw=2.6,
        color="#C44536",
    )
    ax.fill_between(sites, errors, min(errors) * 0.7, color="#F4A261", alpha=0.2)
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xticks(sites, [f"{site // 1000}k" for site in sites])
    ax.set_xlabel("Exact rational-MPS block length")
    ax.set_ylabel("Certified upper-endpoint distance from Bethe value")
    ax.set_title(
        "Integer FLINT contraction extends the exact MPS frontier",
        fontweight="bold",
    )
    improvement = errors[0] / errors[-1]
    ax.annotate(
        f"{improvement:.2f}x smaller upper gap",
        xy=(sites[-1], errors[-1]),
        xytext=(sites[-3], errors[1] * 1.12),
        arrowprops={"arrowstyle": "->", "color": "#7F1D1D"},
        color="#7F1D1D",
        fontweight="bold",
        ha="center",
    )
    fig.tight_layout()
    _save(fig, "mps-upper-frontier")


def main() -> int:
    _style()
    rows = read_summary(SUMMARY_PATH)
    plot_xxx_nesting(rows)
    plot_endpoint_budget(rows)
    plot_symmetry_compression()
    plot_upper_contraction_frontier(UPPER_FRONTIER_PATH)
    print(f"delivery-figures: 4 pairs -> {FIGURE_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
