#!/usr/bin/env python3
"""Join ALF fields, C++ path summaries, and prefix diagnostics for τ estimates."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import statistics

from path_archive import ArchiveReader
from prefix_file import records as prefix_records


NEAR_NODE_SIGMA = 1.0e-6


def make_scores(
    archive_index: Path,
    replay_summary: Path,
    prefix_path: Path,
) -> list[dict[str, object]]:
    with replay_summary.open(newline="") as handle:
        summary = {
            int(row["sample_id"]): row for row in csv.DictReader(handle)
        }
    prefixes: dict[int, list] = {}
    for row in prefix_records(prefix_path):
        prefixes.setdefault(row.sample_id, []).append(row)
    if set(prefixes) != set(summary):
        raise ValueError("prefix and replay summary sample IDs differ")
    for rows in prefixes.values():
        rows.sort(key=lambda row: row.slice)
    training_ids = [
        sample_id for sample_id, row in summary.items()
        if int(row["chain"]) in (0, 1, 2) and row["alive"] == "1"
    ]
    if not training_ids:
        raise ValueError("pilot has no alive training-chain paths")
    lengths = {len(prefixes[sample_id]) for sample_id in training_ids}
    if len(lengths) != 1:
        raise ValueError("pilot prefixes have inconsistent lengths")
    length = lengths.pop()
    reference = [
        statistics.median(
            prefixes[sample_id][slice_index].logq
            for sample_id in training_ids
        )
        for slice_index in range(length)
    ]
    alive_final = [
        float(row["log_q_prop"]) for row in summary.values()
        if row["alive"] == "1" and math.isfinite(float(row["log_q_prop"]))
    ]
    if not alive_final:
        raise ValueError("pilot has no finite alive final logQ")
    censor_floor = min(alive_final) - 20.0

    index = json.loads(archive_index.read_text())
    result: list[dict[str, object]] = []
    seen: set[int] = set()
    for entry in index["entries"]:
        path = Path(entry["path"])
        if not path.is_absolute():
            path = (archive_index.parent / path).resolve()
        reader = ArchiveReader(path)
        side = reader.header.lx
        for record in reader.records():
            sample_id = record.sample_id
            if sample_id not in summary or sample_id in seen:
                raise ValueError("archive/replay sample identity mismatch")
            seen.add(sample_id)
            replay = summary[sample_id]
            prefix = prefixes[sample_id]
            deviations = [
                row.logq - reference[index]
                for index, row in enumerate(prefix)
                if row.alive and math.isfinite(row.logq)
            ]
            minimum_detrended = (
                min(deviations) if deviations else censor_floor
            )
            if replay["alive"] != "1":
                minimum_detrended = min(minimum_detrended, censor_floor)
            logq_final = float(replay["log_q_prop"])
            if not math.isfinite(logq_final):
                logq_final = censor_floor
            field_sum = sum(record.fields)
            staggered = 0
            for index, field in enumerate(record.fields):
                site = index % reader.header.nsites
                x, y = site % side, site // side
                staggered += (1 if (x + y) % 2 == 0 else -1) * field
            near_node_count = sum(
                row.alive and row.sigma_min <= NEAR_NODE_SIGMA
                for row in prefix
            )
            result.append({
                "sample_id": sample_id,
                "ensemble": entry["ensemble"],
                "chain": int(entry["chain"]),
                "sweep": record.sweep_id,
                "frozen_etotal": record.central_etot,
                "field_sum": field_sum,
                "staggered_field_sum": staggered,
                "logQ_final": logq_final,
                "minimum_detrended_prefix_logQ": minimum_detrended,
                "near_node_count": near_node_count,
                "alive": int(replay["alive"]),
            })
    if seen != set(summary):
        raise ValueError("replay summary has samples absent from archives")
    return sorted(result, key=lambda row: (
        row["ensemble"], row["chain"], row["sweep"]
    ))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-index", type=Path, required=True)
    parser.add_argument("--replay-summary", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = make_scores(
        args.archive_index, args.replay_summary, args.prefix
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"pilot scores: {len(rows)} paths -> {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
