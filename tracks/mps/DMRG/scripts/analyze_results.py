#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
import statistics


def sem(values: list[float]) -> float:
    return statistics.stdev(values) / len(values) ** 0.5 if len(values) > 1 else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect MPS VMCRG cell summaries without dropping failures")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1] / "results/mps_challenge")
    args = parser.parse_args()
    rows = []
    seen_dirs = set()
    for manifest_path in sorted(args.root.rglob("manifest.json")):
        seen_dirs.add(manifest_path.parent)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not manifest.get("success", False):
            rows.append(
                {
                    "status": "failed",
                    "path": str(manifest_path.parent),
                    "chi": manifest.get("params", {}).get("chi", ""),
                    "seed": manifest.get("params", {}).get("seed", ""),
                    "arm": "",
                    "error": manifest.get("error", "unknown failure"),
                }
            )
    for summary_path in sorted(args.root.rglob("summary.json")):
        if summary_path.parent in seen_dirs:
            manifest_path = summary_path.parent / "manifest.json"
            if manifest_path.exists() and not json.loads(manifest_path.read_text(encoding="utf-8")).get("success", False):
                continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        for arm, metrics in summary.get("evaluation", {}).items():
            rows.append(
                {
                    "status": "success",
                    "path": str(summary_path.parent),
                    "chi": summary.get("chi", ""),
                    "seed": summary.get("seed", ""),
                    "length": summary.get("length", ""),
                    "coarse_length": summary.get("coarse_length", ""),
                    "rg_levels": summary.get("rg_levels", ""),
                    "arm": arm,
                    "objective": summary.get("training", {}).get("final_record", {}).get("objective", ""),
                    "patch_tv": metrics["patch_distances"]["total_variation"],
                    "patch_js": metrics["patch_distances"]["jensen_shannon"],
                    "two_point_10": metrics["two_point_correlations"]["10"]["mean"],
                    "four_spin": metrics["held_out_multispin"]["four"]["mean"],
                    "six_spin": metrics["held_out_multispin"]["six"]["mean"],
                    "tau_int": metrics["autocorrelation"]["tau_int"],
                    "ess_per_second": metrics["autocorrelation"]["ess_per_second"],
                    "sweep_seconds": metrics["sweep_seconds"],
                    "acceptance_rate": metrics["acceptance_rate"],
                    "error": "",
                }
            )
    output = args.root / "summary_cells.csv"
    fieldnames = sorted({key for row in rows for key in row}) if rows else ["status"]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    groups: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("status") == "success":
            groups[
                (
                    str(row["length"]),
                    str(row["rg_levels"]),
                    str(row["chi"]),
                    str(row["arm"]),
                )
            ].append(row)
    aggregate = []
    quantities = ("objective", "patch_tv", "patch_js", "two_point_10", "four_spin", "six_spin", "tau_int", "ess_per_second", "sweep_seconds", "acceptance_rate")
    for (length, rg_levels, chi, arm), items in sorted(groups.items()):
        result = {
            "length": length,
            "coarse_length": items[0]["coarse_length"],
            "rg_levels": rg_levels,
            "chi": chi,
            "arm": arm,
            "seeds": len(items),
        }
        for quantity in quantities:
            values = [float(item[quantity]) for item in items if item.get(quantity) not in (None, "")]
            if values:
                result[f"{quantity}_mean"] = statistics.mean(values)
                result[f"{quantity}_sem"] = sem(values)
        aggregate.append(result)
    aggregate_path = args.root / "summary_aggregate.csv"
    aggregate_fields = sorted({key for row in aggregate for key in row}) if aggregate else ["chi", "arm", "seeds"]
    with aggregate_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=aggregate_fields)
        writer.writeheader()
        writer.writerows(aggregate)
    print(f"collected cells={len(rows)} aggregate_groups={len(aggregate)}", flush=True)


if __name__ == "__main__":
    main()
