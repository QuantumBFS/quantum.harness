#!/usr/bin/env python3
"""Assemble audited challenge cells and bins into deterministic CSV tables."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from audit_challenge_results import AuditReport, audit_runs


CELL_COLUMNS = [
    "run_id",
    "cell_id",
    "lattice",
    "L",
    "hTrfd",
    "FixedDltau",
    "Dltau",
    "LTrot",
    "nprocs",
    "nWarm",
    "NmBin",
    "NSwep",
    "NmMeaConfg",
    "m2",
    "m2_error",
    "binder_Q",
    "binder_Q_error",
    "z_m2",
    "z_Q",
    "scan_kind",
    "quality_status",
]

BIN_COLUMNS = [
    "run_id",
    "cell_id",
    "lattice",
    "L",
    "hTrfd",
    "FixedDltau",
    "Dltau",
    "bin",
    "m2_bin",
    "m4_bin",
    "Q_bin",
]


def _ordered_records(audit: AuditReport):
    return sorted(
        audit.records,
        key=lambda record: (
            record.lattice,
            record.FixedDltau,
            record.L,
            record.hTrfd,
            record.run_id,
            record.cell_id,
        ),
    )


def assemble_cells(audit: AuditReport) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in _ordered_records(audit):
        values = {
            "run_id": record.run_id,
            "cell_id": record.cell_id,
            "lattice": record.lattice,
            "L": record.L,
            "hTrfd": record.hTrfd,
            "FixedDltau": record.FixedDltau,
            "Dltau": record.Dltau,
            "LTrot": record.LTrot,
            "nprocs": record.nprocs,
            "nWarm": record.nWarm,
            "NmBin": record.NmBin,
            "NSwep": record.NSwep,
            "NmMeaConfg": record.NmMeaConfg,
            "m2": record.m2,
            "m2_error": record.m2_error,
            "binder_Q": record.binder_Q,
            "binder_Q_error": record.binder_Q_error,
            "z_m2": record.z_m2,
            "z_Q": record.z_Q,
            "scan_kind": record.scan_kind,
            "quality_status": record.quality_status,
        }
        rows.append({name: values[name] for name in CELL_COLUMNS})
    return rows


def assemble_bins(audit: AuditReport) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in _ordered_records(audit):
        for bin_row in sorted(record.bins, key=lambda row: int(row["bin"])):
            values = {
                "run_id": record.run_id,
                "cell_id": record.cell_id,
                "lattice": record.lattice,
                "L": record.L,
                "hTrfd": record.hTrfd,
                "FixedDltau": record.FixedDltau,
                "Dltau": record.Dltau,
                "bin": int(bin_row["bin"]),
                "m2_bin": bin_row["m2_bin"],
                "m4_bin": bin_row["m4_bin"],
                "Q_bin": bin_row["Q_bin"],
            }
            rows.append({name: values[name] for name in BIN_COLUMNS})
    return rows


def _csv_value(value: Any) -> Any:
    if isinstance(value, float):
        return format(value, ".17g")
    return value


def _write_rows(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _csv_value(row[name]) for name in columns})


def write_dataset(audit: AuditReport, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_rows(output_dir / "cells.csv", CELL_COLUMNS, assemble_cells(audit))
    _write_rows(output_dir / "bins.csv", BIN_COLUMNS, assemble_bins(audit))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", action="append", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = audit_runs(args.run_dir)
    if report.failed_cells or report.missing_cells or report.duplicate_parameter_cells:
        raise RuntimeError("input audit failed; inspect audit.json before assembly")
    write_dataset(report, args.output_dir)
    print(
        f"assembled {report.total_cells} cells and "
        f"{sum(record.bin_count for record in report.records)} bins"
    )


if __name__ == "__main__":
    main()
