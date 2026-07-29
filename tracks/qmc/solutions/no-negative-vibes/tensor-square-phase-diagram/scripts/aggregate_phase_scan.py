#!/usr/bin/env python3
"""Audit and aggregate the two Stage 3 shards into rough-map artifacts."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

from tensor_square.scan import classify_regions, coarse_grid, EXPERIMENT_ID


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: (
                        "; ".join(value)
                        if isinstance(value, list)
                        else value
                    )
                    for key, value in row.items()
                    if not isinstance(value, (dict, tuple))
                }
            )


def _flatten(payload: dict[str, object]) -> dict[str, object]:
    config = dict(payload["config"])
    row = {
        "cell_id": payload["cell_id"],
        "cell_index": payload["cell_index"],
        "machine": payload["machine"],
        "worker_id": payload["worker_id"],
        "seed": payload["seed"],
        "stability_retry": payload["stability_retry"],
        "stabilized": payload["stabilized"],
        **config,
    }
    for key, value in payload.items():
        if isinstance(value, (str, int, float, bool)) and key not in row:
            row[key] = value
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    expected = {cell.cell_id for cell in coarse_grid()}
    payloads: dict[str, dict[str, object]] = {}
    errors: list[dict[str, object]] = []
    duplicates: list[str] = []
    for path in sorted((args.results_dir / "cells").glob("*/summary.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        cell_id = str(payload["cell_id"])
        if cell_id in payloads:
            duplicates.append(cell_id)
        payloads[cell_id] = payload
    for path in sorted((args.results_dir / "cells").glob("*/error.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["cell_id"] not in payloads:
            errors.append(payload)

    rows = [
        _flatten(payload)
        for payload in payloads.values()
        if payload.get("status") == "COMPLETE"
    ]
    rows.sort(key=lambda row: int(row["cell_index"]))
    regions = classify_regions(rows)
    survivors = [
        row for row in regions if row["classification"] == "SURVIVE"
    ]
    extensions = [
        row for row in regions if row["classification"] == "EXTEND"
    ]
    stopped = [row for row in regions if row["classification"] == "STOP"]
    broken = [row for row in regions if row["classification"] == "BROKEN"]
    missing = sorted(expected - payloads.keys())
    unexpected = sorted(payloads.keys() - expected)
    stability_retries = sum(bool(row["stability_retry"]) for row in rows)
    minimum_sign = min(
        (float(row["direct_sign_mean"]) for row in rows),
        default=float("nan"),
    )
    maximum_log_error = max(
        (float(row["weight_log_error_mean"]) for row in rows),
        default=float("nan"),
    )
    summary = {
        "experiment_id": EXPERIMENT_ID,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "expected_cells": len(expected),
        "complete_cells": len(rows),
        "missing_cells": missing,
        "error_cells": [error["cell_id"] for error in errors],
        "duplicate_cells": duplicates,
        "unexpected_cells": unexpected,
        "stability_retries": stability_retries,
        "minimum_direct_sign": minimum_sign,
        "maximum_weight_log_error": maximum_log_error,
        "regions": len(regions),
        "classification_counts": {
            "SURVIVE": len(survivors),
            "EXTEND": len(extensions),
            "STOP": len(stopped),
            "BROKEN": len(broken),
        },
        "survivors": survivors,
        "extensions": extensions,
    }
    _write_csv(args.output_dir / "table.csv", rows)
    _write_csv(args.output_dir / "regions.csv", regions)
    _write_csv(args.output_dir / "survivors.csv", survivors)
    _write_csv(args.output_dir / "extensions.csv", extensions)
    _write_json(args.output_dir / "summary.json", summary)
    _write_json(args.output_dir / "survivors.json", survivors)
    lines = [
        "# Stage 3 coarse phase map",
        "",
        f"- Expected / complete cells: {len(expected)} / {len(rows)}",
        f"- Missing / errors / duplicates: {len(missing)} / {len(errors)} / {len(duplicates)}",
        f"- Stability retries: {stability_retries}",
        f"- Minimum direct sign: {minimum_sign:.12g}",
        f"- Maximum direct/structured log-weight error: {maximum_log_error:.6g}",
        (
            "- Region classifications: "
            f"SURVIVE={len(survivors)}, EXTEND={len(extensions)}, "
            f"STOP={len(stopped)}, BROKEN={len(broken)}"
        ),
        "",
        "Only SURVIVE and selected EXTEND regions receive dense-scan budget.",
    ]
    (args.output_dir / "summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
