#!/usr/bin/env python3
"""Compare detailed heat-bath surprisal on low-proposal TI paths and controls."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
import json
import math
from pathlib import Path
import statistics
from typing import Mapping, Sequence


def surprisal_metrics(
    probabilities: Sequence[float],
    slices: Sequence[int],
) -> dict[str, float | int]:
    if (
        not probabilities or len(probabilities) != len(slices)
        or any(not 0.0 < value <= 1.0 for value in probabilities)
    ):
        raise ValueError("surprisal metrics need valid paired probabilities")
    values = [-math.log(value) for value in probabilities]
    ordered = sorted(values, reverse=True)
    total = math.fsum(values)
    by_slice: dict[int, float] = defaultdict(float)
    for value, slice_index in zip(values, slices):
        by_slice[int(slice_index)] += value
    return {
        "total_surprisal": total,
        "largest_event_surprisal": ordered[0],
        "top_10_event_share": math.fsum(ordered[:10]) / total,
        "top_100_event_share": math.fsum(ordered[:100]) / total,
        "count_q_lt_1e3": sum(
            probability < 1.0e-3 for probability in probabilities
        ),
        "count_q_lt_1e6": sum(
            probability < 1.0e-6 for probability in probabilities
        ),
        "minimum_q": min(probabilities),
        "peak_surprisal_slice": max(by_slice, key=by_slice.get),
        "peak_slice_surprisal": max(by_slice.values()),
        "slice_surprisal_std": statistics.pstdev(by_slice.values()),
    }


def analyze(
    steps_path: Path,
    selection_path: Path,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    selection = json.loads(selection_path.read_text())["selected"]
    metadata = {str(row["sample_id"]): row for row in selection}
    probabilities: dict[str, list[float]] = defaultdict(list)
    slices: dict[str, list[int]] = defaultdict(list)
    minimum_sigma: dict[str, float] = defaultdict(lambda: math.inf)
    with steps_path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["kind"] != "site":
                continue
            path_id = row["path_id"]
            probabilities[path_id].append(float(row["q_selected"]))
            slices[path_id].append(int(row["slice"]))
            minimum_sigma[path_id] = min(
                minimum_sigma[path_id],
                float(row["sigma_min_up"]),
                float(row["sigma_min_down"]),
            )
    per_path = []
    for path_id in sorted(probabilities):
        sample_id = path_id.rsplit("_", 1)[-1]
        if sample_id not in metadata:
            raise ValueError("trace path is absent from selection metadata")
        per_path.append({
            "path_id": path_id,
            **metadata[sample_id],
            **surprisal_metrics(
                probabilities[path_id], slices[path_id]
            ),
            "minimum_event_sigma": minimum_sigma[path_id],
        })
    low_cases = [
        row for row in per_path
        if row["role"] == "case" and row["ensemble"] == "TI"
        and "proposal_low" in row["labels"]
    ]
    controls = []
    for case in low_cases:
        matches = [
            row for row in per_path
            if row["role"] == "control"
            and int(row["case_id"]) == int(case["case_id"])
        ]
        if len(matches) != 1:
            raise ValueError("low-proposal case lacks one matched control")
        controls.extend(matches)
    if not low_cases:
        raise ValueError("no detailed TI low-proposal cases")
    metrics = (
        "total_surprisal", "largest_event_surprisal",
        "top_10_event_share", "top_100_event_share",
        "count_q_lt_1e3", "count_q_lt_1e6", "minimum_q",
        "peak_surprisal_slice", "peak_slice_surprisal",
        "slice_surprisal_std", "minimum_event_sigma",
    )

    def means(rows: Sequence[Mapping[str, object]]) -> dict[str, float]:
        return {
            key: statistics.mean(float(row[key]) for row in rows)
            for key in metrics
        }

    case_mean = means(low_cases)
    control_mean = means(controls)
    summary = {
        "schema_version": 1,
        "low_proposal_cases": len(low_cases),
        "matched_controls": len(controls),
        "case_mean": case_mean,
        "control_mean": control_mean,
        "case_minus_control": {
            key: case_mean[key] - control_mean[key] for key in metrics
        },
        "interpretation_metrics": {
            "extra_total_surprisal":
                case_mean["total_surprisal"]
                - control_mean["total_surprisal"],
            "rare_q_lt_1e3_count_ratio":
                case_mean["count_q_lt_1e3"]
                / control_mean["count_q_lt_1e3"],
            "top_100_share_ratio":
                case_mean["top_100_event_share"]
                / control_mean["top_100_event_share"],
        },
    }
    selected_ids = {
        int(row["sample_id"]) for row in low_cases + controls
    }
    output_rows = [
        row for row in per_path if int(row["sample_id"]) in selected_ids
    ]
    return summary, output_rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    args = parser.parse_args()
    summary, rows = analyze(args.steps, args.selection)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    with args.output_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"trace dynamics: cases={summary['low_proposal_cases']} "
        f"controls={summary['matched_controls']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
