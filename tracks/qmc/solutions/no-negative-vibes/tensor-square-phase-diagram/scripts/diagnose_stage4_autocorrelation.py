#!/usr/bin/env python3
"""Diagnose which monitored observable causes Stage 4 ESS early stops."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import statistics

from tensor_square.stage4 import MONITORED_TAU_KEYS


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _summaries(root: Path) -> list[dict[str, object]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(
            root.glob("cells/*/production/replica_*/summary.json")
        )
    ]


def _diagnose(rows: list[dict[str, object]]) -> dict[str, object]:
    records: list[dict[str, object]] = []
    for row in rows:
        config = dict(row["config"])
        tau = {
            key: float(row[key])
            for key in MONITORED_TAU_KEYS
        }
        worst_key = max(tau, key=tau.get)
        final_audit = dict(row["final_audit"])
        records.append(
            {
                "cell_id": row["cell_id"],
                "replica": int(row["replica"]),
                "status": row["status"],
                "cohort": row["cohort"],
                "m": int(config["m"]),
                "beta": float(config["beta"]),
                "g_b_over_g_a": float(config["g_b_over_g_a"]),
                "t": float(config["t"]),
                "mu": float(config["mu"]),
                "measurements": int(row["measurements"]),
                "realized_measurement_sweeps": int(
                    row["realized_measurement_sweeps"]
                ),
                "worst_tau_key": worst_key,
                "worst_tau_int": tau[worst_key],
                "achieved_ess": int(row["measurements"])
                / (2.0 * tau[worst_key]),
                "final_reason": final_audit["reason"],
                **tau,
            }
        )

    by_status = Counter(str(row["status"]) for row in records)
    worst_by_status: dict[str, dict[str, int]] = {}
    for status in by_status:
        worst_by_status[status] = dict(
            Counter(
                str(row["worst_tau_key"])
                for row in records
                if row["status"] == status
            )
        )
    grouped: dict[tuple[float, int], list[dict[str, object]]] = defaultdict(list)
    for row in records:
        grouped[(float(row["beta"]), int(row["m"]))].append(row)
    beta_size = []
    for (beta, m), group in sorted(grouped.items()):
        beta_size.append(
            {
                "beta": beta,
                "m": m,
                "replicas": len(group),
                "complete": sum(
                    row["status"] == "COMPLETE" for row in group
                ),
                "early_stop": sum(
                    row["status"] == "EARLY_STOP" for row in group
                ),
                "median_worst_tau_int": statistics.median(
                    float(row["worst_tau_int"]) for row in group
                ),
                "maximum_worst_tau_int": max(
                    float(row["worst_tau_int"]) for row in group
                ),
            }
        )
    tau_by_key = {}
    for key in MONITORED_TAU_KEYS:
        tau_by_key[key] = {
            status: {
                "median": statistics.median(
                    float(row[key])
                    for row in records
                    if row["status"] == status
                ),
                "maximum": max(
                    float(row[key])
                    for row in records
                    if row["status"] == status
                ),
            }
            for status in by_status
        }
    return {
        "replicas": len(records),
        "status_counts": dict(by_status),
        "worst_observable_counts_by_status": worst_by_status,
        "beta_size_audit": beta_size,
        "tau_by_key_and_status": tau_by_key,
        "records": records,
    }


def _write_records(path: Path, records: list[dict[str, object]]) -> None:
    fields = sorted({key for row in records for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-results-dir", required=True, type=Path)
    parser.add_argument("--m10-results-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    production = _diagnose(_summaries(args.production_results_dir))
    m10 = _diagnose(_summaries(args.m10_results_dir))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_records(
        args.output_dir / "production_tau_records.csv",
        list(production.pop("records")),
    )
    _write_records(
        args.output_dir / "m10_tau_records.csv",
        list(m10.pop("records")),
    )
    summary = {"production": production, "m10": m10}
    _atomic_json(args.output_dir / "autocorrelation_diagnosis.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
