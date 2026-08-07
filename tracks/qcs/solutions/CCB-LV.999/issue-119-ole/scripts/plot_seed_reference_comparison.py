#!/usr/bin/env python3
"""Plot seed-level OLE values against audited classical and quantum references."""

from __future__ import annotations

import argparse
import csv
import json
import tomllib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


STEM = "ole-seed-public-quantum-comparison"
T95_DF19 = 2.093024054408263
REFERENCES = {
    "bp_tn_chi192_raw": {
        "value": 0.8202512915,
        "method": "BP-TN chi=192",
        "processing": "raw",
        "error_bound": None,
        "source": (
            "https://github.com/quantum-advantage-tracker/"
            "quantum-advantage-tracker.github.io/issues/15"
        ),
    },
    "bp_tn_chi512_raw": {
        "value": 0.821658489,
        "method": "BP-TN chi=512",
        "processing": "raw",
        "error_bound": None,
        "source": (
            "https://github.com/quantum-advantage-tracker/"
            "quantum-advantage-tracker.github.io/issues/18"
        ),
    },
    "ibm_heron_r3": {
        "value": 0.824,
        "method": "IBM Heron R3",
        "processing": "global_rescaling",
        "error_bound": None,
        "source": (
            "https://github.com/quantum-advantage-tracker/"
            "quantum-advantage-tracker.github.io/issues/38"
        ),
    },
}


def _repo_paths() -> tuple[Path, Path]:
    solution_dir = Path(__file__).resolve().parents[1]
    repo_root = solution_dir.parents[4]
    return solution_dir, repo_root


def _load_seed_values(path: Path) -> tuple[list[int], np.ndarray, np.ndarray]:
    values: dict[int, dict[int, float]] = {}
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            seed = int(row["seed"])
            chi = int(row["chi"])
            sample = float(row["sample_value"])
            values.setdefault(seed, {})[chi] = sample

    seeds = sorted(values)
    missing = {
        seed: sorted({192, 512} - set(values[seed]))
        for seed in seeds
        if set(values[seed]) != {192, 512}
    }
    if missing:
        raise ValueError(f"each seed must contain exactly chi=192 and chi=512: {missing}")
    if seeds != list(range(1, 21)):
        raise ValueError(f"expected audited seed ids 1-20, got {seeds}")

    chi192 = np.array([values[seed][192] for seed in seeds], dtype=float)
    chi512 = np.array([values[seed][512] for seed in seeds], dtype=float)
    return seeds, chi192, chi512


def _load_summary(path: Path) -> dict[str, float | int | bool]:
    summary = tomllib.loads(path.read_text())["summary"]
    return {
        "n": int(summary["n"]),
        "mean": float(summary["mean"]),
        "standard_deviation": float(summary["standard_deviation"]),
        "standard_error": float(summary["standard_error"]),
        "accepted": bool(summary["accepted"]),
    }


def _current_metadata(summary: dict[str, float | int | bool]) -> dict[str, object]:
    if summary["n"] != 20:
        raise ValueError("this audited figure uses the df=19 Student-t interval for n=20")
    half_width = T95_DF19 * float(summary["standard_error"])
    mean = float(summary["mean"])
    return {
        **summary,
        "confidence_interval": "Student-t 95%, df=19",
        "ci95": [mean - half_width, mean + half_width],
    }


def _configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 8.5,
            "axes.labelsize": 9,
            "axes.titlesize": 9.5,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.2,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.2,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def _plot(
    seeds: list[int],
    chi192: np.ndarray,
    chi512: np.ndarray,
    current192: dict[str, object],
    current512: dict[str, object],
    output_dir: Path,
) -> tuple[Path, Path]:
    _configure_style()

    orange = "#E69F00"
    blue = "#0072B2"
    purple = "#CC79A7"
    gray = "#777777"

    fig, (ax_seed, ax_summary) = plt.subplots(
        1,
        2,
        figsize=(7.2, 4.25),
        gridspec_kw={"width_ratios": [2.15, 1.15]},
        sharey=True,
    )
    x = np.asarray(seeds, dtype=float)

    ax_seed.vlines(x, chi192, chi512, color="#B8B8B8", linewidth=0.7, alpha=0.9)
    ax_seed.scatter(
        x - 0.09,
        chi192,
        s=25,
        marker="o",
        facecolor=orange,
        edgecolor="black",
        linewidth=0.35,
        label="This work, chi=192",
        zorder=3,
    )
    ax_seed.scatter(
        x + 0.09,
        chi512,
        s=24,
        marker="s",
        facecolor=blue,
        edgecolor="black",
        linewidth=0.35,
        label="This work, chi=512",
        zorder=3,
    )
    ax_seed.axhline(
        REFERENCES["bp_tn_chi192_raw"]["value"],
        color=orange,
        linestyle="--",
        label="Tracker BP-TN chi=192, raw",
        zorder=1,
    )
    ax_seed.axhline(
        REFERENCES["bp_tn_chi512_raw"]["value"],
        color=blue,
        linestyle="-.",
        label="Tracker BP-TN chi=512, raw",
        zorder=1,
    )
    ax_seed.axhline(
        REFERENCES["ibm_heron_r3"]["value"],
        color=purple,
        linestyle=":",
        linewidth=1.8,
        label="IBM Heron R3, global-rescaled",
        zorder=1,
    )
    ax_seed.set_title("a  Individual computational-basis seeds", loc="left", fontweight="bold")
    ax_seed.set_xlabel("Seed ID")
    ax_seed.set_ylabel("Operator Loschmidt echo")
    ax_seed.set_xticks(seeds)
    ax_seed.set_xlim(0.45, 20.55)
    ax_seed.grid(axis="y", color="#D8D8D8", linewidth=0.55, alpha=0.75)
    ax_seed.spines["top"].set_visible(False)
    ax_seed.spines["right"].set_visible(False)

    categories = [
        "This work\nchi=192",
        "Tracker\nchi=192 raw",
        "This work\nchi=512",
        "Tracker\nchi=512 raw",
        "IBM Heron R3\nglobal-rescaled",
    ]
    xpos = np.arange(len(categories))
    current_means = [float(current192["mean"]), float(current512["mean"])]
    current_errors = [
        current_means[0] - float(current192["ci95"][0]),
        current_means[1] - float(current512["ci95"][0]),
    ]
    ax_summary.errorbar(
        [xpos[0], xpos[2]],
        current_means,
        yerr=current_errors,
        fmt="none",
        ecolor=gray,
        elinewidth=1.2,
        capsize=3,
        label="This work: 95% Student-t CI",
        zorder=2,
    )
    ax_summary.scatter(
        xpos[0],
        current_means[0],
        s=44,
        marker="o",
        facecolor=orange,
        edgecolor="black",
        linewidth=0.5,
        zorder=3,
    )
    ax_summary.scatter(
        xpos[2],
        current_means[1],
        s=42,
        marker="s",
        facecolor=blue,
        edgecolor="black",
        linewidth=0.5,
        zorder=3,
    )
    ax_summary.scatter(
        xpos[1],
        REFERENCES["bp_tn_chi192_raw"]["value"],
        s=47,
        marker="o",
        facecolor="white",
        edgecolor=orange,
        linewidth=1.5,
        zorder=3,
    )
    ax_summary.scatter(
        xpos[3],
        REFERENCES["bp_tn_chi512_raw"]["value"],
        s=45,
        marker="s",
        facecolor="white",
        edgecolor=blue,
        linewidth=1.5,
        zorder=3,
    )
    ax_summary.scatter(
        xpos[4],
        REFERENCES["ibm_heron_r3"]["value"],
        s=55,
        marker="D",
        facecolor="white",
        edgecolor=purple,
        linewidth=1.5,
        zorder=3,
    )
    ax_summary.set_title("b  Mean and published values", loc="left", fontweight="bold")
    ax_summary.set_xticks(xpos, categories, rotation=32, ha="right")
    ax_summary.set_xlim(-0.55, 4.55)
    ax_summary.grid(axis="y", color="#D8D8D8", linewidth=0.55, alpha=0.75)
    ax_summary.spines["top"].set_visible(False)
    ax_summary.spines["right"].set_visible(False)
    ax_summary.text(
        0.98,
        0.02,
        "Published entries provide no error bounds",
        transform=ax_summary.transAxes,
        ha="right",
        va="bottom",
        color="#555555",
        fontsize=7,
    )

    all_values = np.concatenate(
        [
            chi192,
            chi512,
            np.array([record["value"] for record in REFERENCES.values()], dtype=float),
        ]
    )
    margin = 0.003
    ax_seed.set_ylim(float(all_values.min() - margin), float(all_values.max() + margin))

    handles, labels = ax_seed.get_legend_handles_labels()
    summary_handles, summary_labels = ax_summary.get_legend_handles_labels()
    fig.legend(
        handles + summary_handles,
        labels + summary_labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.065),
        ncol=3,
        frameon=False,
        handlelength=2.5,
        columnspacing=1.4,
    )
    fig.suptitle(
        "49x648 operator Loschmidt echo: seed-level and reference comparison",
        y=0.985,
        fontsize=11,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.015,
        "Current BP-TN and tracker BP-TN values are raw; the IBM hardware value is "
        "global-rescaled and is shown as a contextual comparison.",
        ha="center",
        va="bottom",
        fontsize=7.2,
        color="#444444",
    )
    fig.subplots_adjust(left=0.09, right=0.985, top=0.90, bottom=0.33, wspace=0.17)

    output_dir.mkdir(parents=True, exist_ok=True)
    png = output_dir / f"{STEM}.png"
    pdf = output_dir / f"{STEM}.pdf"
    fig.savefig(png, dpi=400, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return png, pdf


def main() -> int:
    solution_dir, repo_root = _repo_paths()
    default_results = repo_root / "results" / "issue119-ole-g2-paired-rest"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=default_results / "g2-paired-20.csv",
    )
    parser.add_argument(
        "--chi192-summary",
        type=Path,
        default=(
            solution_dir
            / "runs"
            / "baseline-49x648"
            / "delta-0p15"
            / "chi-192"
            / "summary.toml"
        ),
    )
    parser.add_argument(
        "--chi512-summary",
        type=Path,
        default=(
            solution_dir
            / "runs"
            / "baseline-49x648"
            / "delta-0p15"
            / "chi-512"
            / "summary.toml"
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=default_results)
    args = parser.parse_args()

    seeds, chi192, chi512 = _load_seed_values(args.input_csv)
    current192 = _current_metadata(_load_summary(args.chi192_summary))
    current512 = _current_metadata(_load_summary(args.chi512_summary))
    if not np.isclose(float(current192["mean"]), float(chi192.mean()), atol=1.0e-14):
        raise ValueError("chi=192 summary mean does not match seed-level CSV")
    if not np.isclose(float(current512["mean"]), float(chi512.mean()), atol=1.0e-14):
        raise ValueError("chi=512 summary mean does not match seed-level CSV")

    png, pdf = _plot(seeds, chi192, chi512, current192, current512, args.output_dir)
    metadata = {
        "figure": "49x648 OLE seed-level and reference comparison",
        "source_data": str(args.input_csv.resolve()),
        "seed_ids": seeds,
        "seed_count": len(seeds),
        "seed_values": {
            str(seed): {"chi192": float(v192), "chi512": float(v512)}
            for seed, v192, v512 in zip(seeds, chi192, chi512, strict=True)
        },
        "current": {"chi192": current192, "chi512": current512},
        "references": REFERENCES,
        "comparability_note": (
            "Current and public BP-TN values are raw. The IBM Heron R3 value uses "
            "global rescaling by the unmitigated delta=0 signal and has no published "
            "error bound, so it is a contextual rather than like-for-like comparison."
        ),
    }
    metadata_path = args.output_dir / f"{STEM}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")

    print(f"png={png}")
    print(f"pdf={pdf}")
    print(f"metadata={metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
