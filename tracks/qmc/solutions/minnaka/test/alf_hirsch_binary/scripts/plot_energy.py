#!/usr/bin/env python3
"""Plot chain-resolved ALF binary-Hirsch energy diagnostics."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.dont_write_bytecode = True
import analyze  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_ROOT = PROJECT_ROOT / "results"
OKABE_ITO = [
    "#E69F00",
    "#56B4E9",
    "#009E73",
    "#0072B2",
    "#D55E00",
    "#CC79A7",
]
MARKERS = ["o", "s", "^", "D", "v", "P"]


def main() -> None:
    rows = list(
        csv.DictReader(
            (RESULTS_ROOT / "energy_bins.csv").open(encoding="utf-8")
        )
    )
    summary = json.loads(
        (RESULTS_ROOT / "summary.json").read_text(encoding="utf-8")
    )
    reference = summary["comparison"]["alf_reference_energy"]
    reference_error = summary["comparison"]["alf_reference_error"]
    combined = summary["observables"]["total_energy"]

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 8,
            "axes.labelsize": 9,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.linewidth": 0.8,
        }
    )
    fig, (ax_bins, ax_means) = plt.subplots(
        1,
        2,
        figsize=(7.0, 3.1),
        gridspec_kw={"width_ratios": [1.7, 1.0]},
    )

    chain_means = []
    chain_errors = []
    for chain in range(6):
        chain_rows = [
            row for row in rows if int(row["chain"]) == chain
        ]
        bins = [int(row["bin"]) for row in chain_rows]
        energies = [float(row["total_energy"]) for row in chain_rows]
        retained = energies[1:]
        mean, error = analyze.jackknife_ratio(
            retained, [1.0] * len(retained)
        )
        chain_means.append(mean)
        chain_errors.append(error)

        ax_bins.plot(
            bins[1:],
            retained,
            color=OKABE_ITO[chain],
            marker=MARKERS[chain],
            markersize=4,
            linewidth=0.8,
            label=f"Chain {chain}",
        )
        ax_bins.scatter(
            bins[0],
            energies[0],
            color=OKABE_ITO[chain],
            marker="x",
            s=22,
            linewidths=1.0,
            alpha=0.75,
        )

    for axis in (ax_bins, ax_means):
        axis.axhspan(
            reference - reference_error,
            reference + reference_error,
            color="#999999",
            alpha=0.22,
            linewidth=0,
            label="ALF reference uncertainty",
        )
        axis.axhline(
            reference,
            color="#333333",
            linestyle="--",
            linewidth=1.0,
            label="ALF reference",
        )
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.set_ylabel("Total energy (t)")

    ax_bins.set_xlabel("Bin within chain")
    ax_bins.set_xticks(range(1, 8))
    ax_bins.text(
        0.02,
        0.03,
        "×: omitted equilibration bin",
        transform=ax_bins.transAxes,
        fontsize=7,
        color="#555555",
    )
    handles, labels = ax_bins.get_legend_handles_labels()
    ax_bins.legend(
        handles[:6] + handles[-2:],
        labels[:6] + labels[-2:],
        frameon=False,
        ncol=2,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.23),
    )

    for chain, (mean, error) in enumerate(
        zip(chain_means, chain_errors)
    ):
        ax_means.errorbar(
            chain,
            mean,
            yerr=error,
            color=OKABE_ITO[chain],
            marker=MARKERS[chain],
            markersize=5,
            capsize=2.5,
            linewidth=1.0,
        )
    ax_means.errorbar(
        6.5,
        combined["mean"],
        yerr=combined["error"],
        color="#000000",
        marker="*",
        markersize=8,
        capsize=3,
        linewidth=1.2,
        label="Combined (n=36)",
    )
    ax_means.set_xticks([0, 1, 2, 3, 4, 5, 6.5])
    ax_means.set_xticklabels(["0", "1", "2", "3", "4", "5", "All"])
    ax_means.set_xlabel("Chain")
    ax_means.legend(frameon=False, loc="upper right")
    ax_means.text(
        0.03,
        0.03,
        "Error bars: ALF 2.4 jackknife",
        transform=ax_means.transAxes,
        fontsize=7,
        color="#555555",
    )

    fig.suptitle(
        "Binary Hirsch projector QMC: 4×4 Hubbard model, U/t = 4",
        fontsize=10,
        y=1.02,
    )
    fig.tight_layout()
    fig.savefig(
        RESULTS_ROOT / "energy_bins.png",
        dpi=300,
        bbox_inches="tight",
    )
    fig.savefig(
        RESULTS_ROOT / "energy_bins.pdf",
        bbox_inches="tight",
    )
    plt.close(fig)


if __name__ == "__main__":
    main()
