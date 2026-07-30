#!/usr/bin/env python3
"""Build a transparent preliminary summary of successful active BP-TN cells."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import statistics


CHIS = (64, 128, 192)


def _mean_se(values: list[float]) -> dict[str, float | int]:
    if not values:
        raise ValueError("cannot summarize an empty sample")
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "se": (
            statistics.stdev(values) / math.sqrt(len(values))
            if len(values) > 1
            else 0.0
        ),
    }


def _successful_by_chi(records: list[dict]) -> dict[int, dict[int, float]]:
    by_chi = {chi: {} for chi in CHIS}
    for record in records:
        if (
            record.get("status") != "success"
            or str(record.get("params", {}).get("delta")) != "0.15"
        ):
            continue
        chi = int(record["params"]["chi"])
        if chi not in by_chi:
            continue
        seed = int(record["params"]["seed"])
        value = float(record["result"]["sample_value"])
        if not math.isfinite(value):
            raise ValueError(f"non-finite sample at chi={chi}, seed={seed}")
        if seed in by_chi[chi]:
            raise ValueError(f"duplicate sample at chi={chi}, seed={seed}")
        by_chi[chi][seed] = value
    return by_chi


def _paired(by_chi: dict[int, dict[int, float]], low: int, high: int) -> dict:
    common = sorted(set(by_chi[low]) & set(by_chi[high]))
    result = _mean_se(
        [by_chi[high][seed] - by_chi[low][seed] for seed in common]
    )
    return {"common_seeds": common, **result}


def summarize(records: list[dict]) -> dict:
    """Summarize all available samples and the strictly matched three-χ subset."""
    by_chi = _successful_by_chi(records)
    missing = {
        str(chi): sorted(set(range(1, 21)) - set(by_chi[chi]))
        for chi in CHIS
    }
    common = sorted(set.intersection(*(set(by_chi[chi]) for chi in CHIS)))
    return {
        "classification": "preliminary_incomplete_grid",
        "available": {
            str(chi): _mean_se(list(by_chi[chi].values()))
            for chi in CHIS
        },
        "missing_seeds": missing,
        "three_chi_common_seeds": common,
        "matched": {
            str(chi): _mean_se([by_chi[chi][seed] for seed in common])
            for chi in CHIS
        },
        "paired_drift": {
            "64_to_128": _paired(by_chi, 64, 128),
            "128_to_192": _paired(by_chi, 128, 192),
        },
        "samples": {
            str(chi): [
                {"seed": seed, "value": value}
                for seed, value in sorted(by_chi[chi].items())
            ]
            for chi in CHIS
        },
    }


def external_anchors() -> dict[str, dict]:
    """Return cited context values with instance and normalization attached."""
    return {
        "baseline_current_bp_raw_chi512": {
            "instance": "49x648",
            "normalization": "raw",
            "method": "BP-TN",
            "chi": 512,
            "value": 0.8183229131612796,
            "se": 0.0019858354,
        },
        "baseline_public_bp_raw_chi512": {
            "instance": "49x648",
            "normalization": "raw",
            "method": "BP-TN",
            "chi": 512,
            "value": 0.8216584890,
        },
        "baseline_current_pepo_raw": {
            "instance": "49x648",
            "normalization": "raw",
            "method": "Heisenberg PEPO",
            "dop": 512,
            "chi_env": 64,
            "value": 0.8225508376024053,
        },
        "active_public_bp_raw_chi512": {
            "instance": "49x1296",
            "normalization": "raw",
            "method": "BP-TN",
            "chi": 512,
            "value": 0.88157984,
        },
        "active_public_bp_rescaled_chi512": {
            "instance": "49x1296",
            "normalization": "delta0_rescaled",
            "method": "BP-TN",
            "chi": 512,
            "value": 0.94257142,
        },
        "active_single_path_mc": {
            "instance": "49x1296",
            "normalization": "phase_insensitive_approximation",
            "method": "single-path Pauli MC",
            "value": 0.619,
        },
        "active_ibm_rescaled": {
            "instance": "49x1296",
            "normalization": "global_rescaled",
            "method": "IBM Heron R3",
            "interval": [0.649, 0.662],
        },
    }


def _load_records(run_dir: Path) -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((run_dir / "cells").glob("*/manifest.json"))
    ]


def _write_csv(summary: dict, anchors: dict, path: Path) -> None:
    fields = [
        "kind",
        "instance",
        "normalization",
        "method",
        "chi",
        "n",
        "mean_or_value",
        "se",
        "interval_low",
        "interval_high",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for chi in CHIS:
            available = summary["available"][str(chi)]
            writer.writerow(
                {
                    "kind": "current_available",
                    "instance": "49x1296",
                    "normalization": "raw",
                    "method": "BP-TN",
                    "chi": chi,
                    "n": available["n"],
                    "mean_or_value": available["mean"],
                    "se": available["se"],
                }
            )
        for name, anchor in anchors.items():
            interval = anchor.get("interval", ["", ""])
            writer.writerow(
                {
                    "kind": name,
                    "instance": anchor["instance"],
                    "normalization": anchor["normalization"],
                    "method": anchor["method"],
                    "chi": anchor.get("chi", ""),
                    "n": "",
                    "mean_or_value": anchor.get("value", ""),
                    "se": anchor.get("se", ""),
                    "interval_low": interval[0],
                    "interval_high": interval[1],
                }
            )


def _plot(summary: dict, anchors: dict, output_stem: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 9,
            "axes.labelsize": 10,
            "axes.titlesize": 10,
            "legend.fontsize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
        }
    )
    blue = "#0072B2"
    orange = "#D55E00"
    grey = "#666666"
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.45), constrained_layout=True)

    ax = axes[0]
    for chi in CHIS:
        samples = summary["samples"][str(chi)]
        offsets = [0.9 * ((item["seed"] % 7) - 3) for item in samples]
        ax.scatter(
            [chi + offset for offset in offsets],
            [item["value"] for item in samples],
            s=12,
            alpha=0.35,
            color=blue,
            linewidths=0,
        )
        available = summary["available"][str(chi)]
        ax.errorbar(
            chi,
            available["mean"],
            yerr=available["se"],
            fmt="o",
            color=blue,
            markeredgecolor="black",
            markeredgewidth=0.5,
            capsize=3,
            zorder=4,
        )
        ax.annotate(
            f"n={available['n']}",
            (chi, available["mean"]),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )
    public_raw = anchors["active_public_bp_raw_chi512"]["value"]
    ax.scatter(
        [512],
        [public_raw],
        marker="*",
        s=100,
        facecolor="white",
        edgecolor=orange,
        linewidth=1.3,
        zorder=5,
        label="Published raw BP-TN (no error bar)",
    )
    ax.set(
        xlabel="BP-TN bond dimension χ",
        ylabel="Raw OLE",
        title="A  Active raw BP-TN finite-χ trend",
        xticks=[64, 128, 192, 512],
        ylim=(0.30, 0.98),
    )
    ax.legend(frameon=False, loc="lower right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax = axes[1]
    labels = [
        "Current BP-TN\nχ=192 raw",
        "Single-path MC\nphase-insensitive",
        "IBM Heron R3\nglobal-rescaled",
        "Published BP-TN\nχ=512 raw",
        "Published BP-TN\nχ=512 δ=0-rescaled",
    ]
    y = list(range(len(labels)))[::-1]
    current = summary["available"]["192"]
    values = [
        current["mean"],
        anchors["active_single_path_mc"]["value"],
        statistics.fmean(anchors["active_ibm_rescaled"]["interval"]),
        anchors["active_public_bp_raw_chi512"]["value"],
        anchors["active_public_bp_rescaled_chi512"]["value"],
    ]
    errors = [
        current["se"],
        0.0,
        (
            anchors["active_ibm_rescaled"]["interval"][1]
            - anchors["active_ibm_rescaled"]["interval"][0]
        )
        / 2,
        0.0,
        0.0,
    ]
    colors = [blue, grey, orange, blue, orange]
    markers = ["o", "x", "s", "o", "s"]
    for yi, value, error, color, marker in zip(
        y, values, errors, colors, markers, strict=True
    ):
        ax.errorbar(
            value,
            yi,
            xerr=error if error else None,
            fmt=marker,
            color=color,
            capsize=3,
            markersize=6,
        )
    ax.set(
        xlabel="Reported OLE value",
        title="B  External published context",
        yticks=y,
        yticklabels=labels,
        xlim=(0.56, 0.98),
    )
    ax.grid(axis="x", color="#dddddd", linewidth=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(
        handles=[
            Line2D([0], [0], marker="o", color="none", markerfacecolor=blue,
                   markeredgecolor=blue, label="raw"),
            Line2D([0], [0], marker="s", color="none", markerfacecolor=orange,
                   markeredgecolor=orange, label="rescaled"),
            Line2D([0], [0], marker="x", color=grey, label="different approximation"),
        ],
        frameon=False,
        loc="upper right",
    )
    fig.savefig(output_stem.with_suffix(".png"), dpi=300)
    fig.savefig(output_stem.with_suffix(".pdf"))
    plt.close(fig)


def write_outputs(summary: dict, anchors: dict, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "preliminary-comparison.json"
    csv_path = output_dir / "preliminary-comparison.csv"
    plot_stem = output_dir / "preliminary-active-comparison"
    json_path.write_text(
        json.dumps(
            {"summary": summary, "external_anchors": anchors},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_csv(summary, anchors, csv_path)
    _plot(summary, anchors, plot_stem)
    return {
        "json": json_path,
        "csv": csv_path,
        "png": plot_stem.with_suffix(".png"),
        "pdf": plot_stem.with_suffix(".pdf"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    summary = summarize(_load_records(args.run_dir))
    outputs = write_outputs(summary, external_anchors(), args.output_dir or args.run_dir)
    print(f"classification={summary['classification']}", flush=True)
    print(
        "available_counts="
        + ",".join(
            f"{chi}:{summary['available'][str(chi)]['n']}" for chi in CHIS
        ),
        flush=True,
    )
    print(
        f"three_chi_common={len(summary['three_chi_common_seeds'])}",
        flush=True,
    )
    for name, path in outputs.items():
        print(f"{name}={path}", flush=True)


if __name__ == "__main__":
    main()
