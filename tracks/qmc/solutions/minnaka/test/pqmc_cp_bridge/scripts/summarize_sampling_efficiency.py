#!/usr/bin/env python3
"""Summarize UHF-CP sampling efficiency and bottleneck field patterns."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from path_archive import ArchiveReader


def worst_efficiency_rows(
    rows: Iterable[Mapping[str, object]], *, fraction: float = 0.01
) -> list[dict[str, object]]:
    values = [dict(row) for row in rows]
    if not values or not 0.0 < fraction <= 1.0:
        raise ValueError("sampling-efficiency selection is empty or invalid")
    for row in values:
        row["log_sampling_efficiency"] = (
            float(row["log_q_prop"]) - float(row["logabs_d_ti"])
        )
    count = max(1, math.ceil(fraction * len(values)))
    return sorted(
        values,
        key=lambda row: (
            float(row["log_sampling_efficiency"]),
            int(row["sample_id"]),
        ),
    )[:count]


def field_descriptor(
    fields: Sequence[int],
    coordinates: Sequence[tuple[int, int]],
) -> dict[str, int]:
    if len(fields) != len(coordinates) or not fields:
        raise ValueError("field descriptor needs matching fields/sites")
    if any(value not in (-1, 1) for value in fields):
        raise ValueError("field descriptor requires binary fields")
    by_xy = {
        coordinate: int(value)
        for coordinate, value in zip(coordinates, fields)
    }
    side = round(math.sqrt(len(fields)))
    if side * side != len(fields):
        raise ValueError("field descriptor requires a square lattice")
    uniform = sum(fields)
    staggered = sum(
        value * (-1 if (x + y) % 2 else 1)
        for value, (x, y) in zip(fields, coordinates)
    )
    walls = 0
    for x, y in coordinates:
        walls += by_xy[(x, y)] != by_xy[((x + 1) % side, y)]
        walls += by_xy[(x, y)] != by_xy[(x, (y + 1) % side)]
    plus = sum(value == 1 for value in fields)
    checker = [
        1 if (x + y) % 2 == 0 else -1
        for x, y in coordinates
    ]
    checker_distance = min(
        sum(left != right for left, right in zip(fields, checker)),
        sum(left != -right for left, right in zip(fields, checker)),
    )
    mask = sum(
        (1 if value == 1 else 0) << index
        for index, value in enumerate(fields)
    )
    return {
        "abs_uniform": abs(uniform),
        "abs_staggered": abs(staggered),
        "domain_walls": walls,
        "distance_constant": min(plus, len(fields) - plus),
        "distance_checkerboard": checker_distance,
        "mask": mask,
    }


def _log_mean(values: Sequence[float]) -> float:
    maximum = max(values)
    return maximum + math.log(math.fsum(
        math.exp(value - maximum) for value in values
    )) - math.log(len(values))


def _rank(values: Sequence[float]) -> list[float]:
    ordered = sorted(range(len(values)), key=lambda index: values[index])
    result = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and \
                values[ordered[end]] == values[ordered[start]]:
            end += 1
        rank = 0.5 * (start + end - 1)
        for position in range(start, end):
            result[ordered[position]] = rank
        start = end
    return result


def _correlation(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        raise ValueError("correlation needs paired values")
    mean_left = statistics.mean(left)
    mean_right = statistics.mean(right)
    numerator = math.fsum(
        (a - mean_left) * (b - mean_right)
        for a, b in zip(left, right)
    )
    denominator = math.sqrt(
        math.fsum((value - mean_left) ** 2 for value in left)
        * math.fsum((value - mean_right) ** 2 for value in right)
    )
    return numerator / denominator


def _spearman(left: Sequence[float], right: Sequence[float]) -> float:
    return _correlation(_rank(left), _rank(right))


def _coordinates(path: Path) -> list[tuple[int, int]]:
    rows = [
        tuple(int(value) for value in line.split())
        for line in path.read_text().splitlines() if line.strip()
    ]
    rows.sort(key=lambda row: row[0])
    return [(row[2], row[3]) for row in rows]


def _records(
    archive_root: Path, wanted: set[int]
) -> dict[int, object]:
    result = {}
    for path in sorted((archive_root / "TI").glob("chain_*.qhpath")):
        for record in ArchiveReader(path).records():
            if record.sample_id in wanted:
                result[record.sample_id] = record
    if set(result) != wanted:
        raise ValueError("not every TI analysis path is in the local archive")
    return result


def _descriptor_for_row(
    row: Mapping[str, object],
    records: Mapping[int, object],
    coordinates: Sequence[tuple[int, int]],
) -> dict[str, int]:
    record = records[int(row["sample_id"])]
    slice_index = int(row["prefix_barrier_slice"])
    sites = len(coordinates)
    fields = record.fields[
        slice_index * sites:(slice_index + 1) * sites
    ]
    return {
        **field_descriptor(fields, coordinates),
        "bottleneck_slice": slice_index,
    }


def _mean_metrics(
    values: Sequence[Mapping[str, int]],
) -> dict[str, float]:
    keys = (
        "abs_uniform", "abs_staggered", "domain_walls",
        "distance_constant", "distance_checkerboard",
        "bottleneck_slice",
    )
    return {
        key: statistics.mean(float(row[key]) for row in values)
        for key in keys
    }


def _weighted_energy_jackknife(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, float | int]:
    if not rows:
        raise ValueError("energy jackknife needs rows")
    chains = sorted({int(row["chain"]) for row in rows})
    log_ratio = [
        float(row["logabs_d_ti"]) - float(row["logabs_d_alf_ti"])
        for row in rows
    ]
    maximum = max(log_ratio)
    weights = [math.exp(value - maximum) for value in log_ratio]

    def estimate(excluded: int | None = None) -> float:
        selected = [
            (weight, row)
            for weight, row in zip(weights, rows)
            if excluded is None or int(row["chain"]) != excluded
        ]
        denominator = math.fsum(weight for weight, _row in selected)
        return math.fsum(
            weight * float(row["central_ti_etot"])
            for weight, row in selected
        ) / denominator

    energy = estimate()
    leave_one_out = [estimate(chain) for chain in chains]
    center = statistics.mean(leave_one_out)
    sigma = math.sqrt(
        (len(chains) - 1) / len(chains)
        * math.fsum((value - center) ** 2 for value in leave_one_out)
    )
    return {
        "energy": energy,
        "jackknife_sigma": sigma,
        "chains": len(chains),
        "paths": len(rows),
    }


def analyze(
    strata_path: Path,
    archive_root: Path,
    site_map: Path,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    with strata_path.open(newline="") as handle:
        source = list(csv.DictReader(handle))
    ti = [
        row for row in source
        if row["ensemble"] == "TI"
        and str(row["alive"]).lower() in {"1", "true"}
        and str(row["numerically_ambiguous"]).lower() not in {"1", "true"}
    ]
    if not ti:
        raise ValueError("no unambiguous alive TI paths")
    worst = worst_efficiency_rows(ti)
    efficiency = [
        float(row["log_q_prop"]) - float(row["logabs_d_ti"])
        for row in ti
    ]
    log_weight = [float(row["logabs_d_ti"]) for row in ti]
    barrier = [float(row["prefix_barrier"]) for row in ti]
    log_sigma = [math.log10(float(row["min_sigma"])) for row in ti]
    median_weight = statistics.median(log_weight)
    arithmetic_log_mean = _log_mean(log_weight)
    coordinates = _coordinates(site_map)
    records = _records(
        archive_root, {int(row["sample_id"]) for row in ti}
    )
    all_descriptors = [
        _descriptor_for_row(row, records, coordinates) for row in ti
    ]
    worst_descriptors = [
        _descriptor_for_row(row, records, coordinates) for row in worst
    ]
    worst_output = []
    for row, descriptor in zip(worst, worst_descriptors):
        worst_output.append({
            "sample_id": int(row["sample_id"]),
            "chain": int(row["chain"]),
            "sweep": int(row["sweep"]),
            "log_sampling_efficiency":
                float(row["log_sampling_efficiency"]),
            "log_true_weight_minus_median":
                float(row["logabs_d_ti"]) - median_weight,
            "log_true_weight_minus_arithmetic_log_mean":
                float(row["logabs_d_ti"]) - arithmetic_log_mean,
            "prefix_barrier": float(row["prefix_barrier"]),
            "prefix_barrier_slice": int(row["prefix_barrier_slice"]),
            "min_sigma": float(row["min_sigma"]),
            "min_selected_q": float(row["min_selected_q"]),
            **descriptor,
        })
    held_out = [
        row for row in ti if 64 <= int(row["chain"]) < 128
    ]
    summary = {
        "schema_version": 1,
        "definitions": {
            "log_sampling_efficiency": "log_q_prop - logabs_d_ti",
            "worst_fraction": 0.01,
            "typical_weight_threshold": "median(logabs_d_ti)",
            "arithmetic_weight_threshold":
                "log(mean(exp(logabs_d_ti)))",
            "bottleneck": "minimum prefix log-q relative to TI training median",
        },
        "population": {
            "paths": len(ti),
            "excluded_numerically_ambiguous": (
                sum(
                    row["ensemble"] == "TI"
                    and str(row["numerically_ambiguous"]).lower()
                    in {"1", "true"}
                    for row in source
                )
            ),
            "all_alive": all(
                str(row["alive"]).lower() in {"1", "true"}
                for row in source if row["ensemble"] == "TI"
            ),
            "all_positive_ti_weight": all(
                int(row["sign_d_ti"]) == 1
                for row in source if row["ensemble"] == "TI"
            ),
        },
        "worst_one_percent": {
            "paths": len(worst),
            "at_or_above_typical_weight": sum(
                float(row["logabs_d_ti"]) >= median_weight
                for row in worst
            ),
            "at_or_above_arithmetic_mean_weight": sum(
                float(row["logabs_d_ti"]) >= arithmetic_log_mean
                for row in worst
            ),
            "bottleneck_in_last_quarter": sum(
                int(row["prefix_barrier_slice"]) >= 315
                for row in worst
            ),
            "unique_bottleneck_masks": len({
                row["mask"] for row in worst_descriptors
            }),
        },
        "correlations": {
            "spearman_efficiency_vs_prefix_barrier":
                _spearman(efficiency, barrier),
            "spearman_efficiency_vs_log10_min_sigma":
                _spearman(efficiency, log_sigma),
            "spearman_log_q_vs_log_true_weight": _spearman(
                [float(row["log_q_prop"]) for row in ti],
                log_weight,
            ),
        },
        "bottleneck_field_metrics": {
            "all_paths_mean": _mean_metrics(all_descriptors),
            "worst_one_percent_mean": _mean_metrics(worst_descriptors),
        },
        "held_out_cp_symmetric_energy_unambiguous":
            _weighted_energy_jackknife(held_out),
        "worst_paths": worst_output,
    }
    plot_rows = []
    for row, descriptor in zip(ti, all_descriptors):
        plot_rows.append({
            "sample_id": int(row["sample_id"]),
            "log_weight_centered": float(row["logabs_d_ti"]) - median_weight,
            "log_efficiency_centered": (
                float(row["log_q_prop"]) - float(row["logabs_d_ti"])
                - statistics.median(efficiency)
            ),
            "prefix_barrier": float(row["prefix_barrier"]),
            "bottleneck_slice": descriptor["bottleneck_slice"],
            "min_sigma": float(row["min_sigma"]),
            "worst": int(row["sample_id"]) in {
                int(item["sample_id"]) for item in worst
            },
        })
    return summary, worst_output, plot_rows


def write_worst(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def plot_summary(
    rows: Sequence[Mapping[str, object]],
    summary: Mapping[str, object],
    output_prefix: Path,
) -> None:
    regular = [row for row in rows if not row["worst"]]
    worst = [row for row in rows if row["worst"]]
    blue = "#4477AA"
    red = "#CC6677"
    fig, axes = plt.subplots(2, 2, figsize=(8.0, 6.2))
    ax = axes[0, 0]
    ax.scatter(
        [row["log_weight_centered"] for row in regular],
        [row["log_efficiency_centered"] for row in regular],
        s=9, alpha=0.32, color=blue, edgecolors="none",
    )
    ax.scatter(
        [row["log_weight_centered"] for row in worst],
        [row["log_efficiency_centered"] for row in worst],
        s=23, color=red, edgecolors="black", linewidths=0.3,
        label="worst 1%",
    )
    ax.axvline(0.0, color="0.35", linestyle="--", linewidth=0.8)
    ax.set_xlabel(r"$\log D_{\rm TI}-{\rm median}(\log D_{\rm TI})$")
    ax.set_ylabel(r"$\log(Q_{\rm CP}/D_{\rm TI})$ (centered)")
    ax.legend(frameon=False, fontsize=8)

    ax = axes[0, 1]
    ax.scatter(
        [row["prefix_barrier"] for row in regular],
        [row["log_efficiency_centered"] for row in regular],
        s=9, alpha=0.32, color=blue, edgecolors="none",
    )
    ax.scatter(
        [row["prefix_barrier"] for row in worst],
        [row["log_efficiency_centered"] for row in worst],
        s=23, color=red, edgecolors="black", linewidths=0.3,
    )
    rho = summary["correlations"][
        "spearman_efficiency_vs_prefix_barrier"
    ]
    ax.text(
        0.04, 0.07, rf"Spearman $\rho={rho:.3f}$",
        transform=ax.transAxes, fontsize=8,
    )
    ax.set_xlabel("prefix barrier")
    ax.set_ylabel(r"$\log(Q_{\rm CP}/D_{\rm TI})$ (centered)")

    ax = axes[1, 0]
    bins = list(range(0, 441, 20))
    ax.hist(
        [row["bottleneck_slice"] for row in regular], bins=bins,
        density=True, histtype="stepfilled", alpha=0.35,
        color=blue, label="all other paths",
    )
    ax.hist(
        [row["bottleneck_slice"] for row in worst], bins=bins,
        density=True, histtype="step", linewidth=1.8,
        color=red, label="worst 1%",
    )
    ax.axvline(315, color="0.35", linestyle="--", linewidth=0.8)
    ax.set_xlabel("bottleneck slice")
    ax.set_ylabel("density")
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1, 1]
    metrics = summary["bottleneck_field_metrics"]
    labels = [
        r"$|\Sigma x|/16$", r"$|\Sigma(-1)^i x_i|/16$",
        "domain walls/32", "distance to constant/8",
        "distance to checkerboard/8",
    ]
    keys = [
        "abs_uniform", "abs_staggered", "domain_walls",
        "distance_constant", "distance_checkerboard",
    ]
    scales = [16, 16, 32, 8, 8]
    all_values = [
        metrics["all_paths_mean"][key] / scale
        for key, scale in zip(keys, scales)
    ]
    worst_values = [
        metrics["worst_one_percent_mean"][key] / scale
        for key, scale in zip(keys, scales)
    ]
    positions = list(range(len(labels)))
    ax.bar(
        [value - 0.18 for value in positions], all_values,
        width=0.36, color=blue, alpha=0.75, label="all paths",
    )
    ax.bar(
        [value + 0.18 for value in positions], worst_values,
        width=0.36, color=red, alpha=0.85, label="worst 1%",
    )
    ax.set_xticks(positions, labels, rotation=25, ha="right", fontsize=7)
    ax.set_ylabel("normalized descriptor")
    ax.legend(frameon=False, fontsize=8)
    ax.set_ylim(0.0, 1.0)

    for label, ax in zip(("a", "b", "c", "d"), axes.flat):
        ax.set_title(
            f"({label})", loc="left", pad=7, fontweight="bold",
        )
    fig.tight_layout()
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_prefix.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(
        output_prefix.with_suffix(".png"), dpi=300, bbox_inches="tight"
    )
    plt.close(fig)


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    bridge = root / "test/pqmc_cp_bridge"
    parser = argparse.ArgumentParser()
    parser.add_argument("--strata", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument(
        "--site-map", type=Path,
        default=bridge / "assets/trials/site_map.dat",
    )
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--plot-prefix", type=Path, required=True)
    args = parser.parse_args()
    summary, worst, plot_rows = analyze(
        args.strata, args.archive_root, args.site_map
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    write_worst(args.output_csv, worst)
    plot_summary(plot_rows, summary, args.plot_prefix)
    print(
        f"sampling efficiency: paths={summary['population']['paths']} "
        f"worst={summary['worst_one_percent']['paths']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
