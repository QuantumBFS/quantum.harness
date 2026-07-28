#!/usr/bin/env python3
"""Assemble separated local MPS and MPO uncertainty records."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from lrtfim.local_uncertainty import (
    compare_chi,
    compare_k_crossing,
    numeric_shift,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison-spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _atomic_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    spec = json.loads(args.comparison_spec.read_text())
    comparisons = []
    for pair in spec.get("mps_pairs", []):
        reference = json.loads(Path(pair["chi128"]).read_text())
        candidate = json.loads(Path(pair["chi256"]).read_text())
        comparisons.append(compare_chi(reference, candidate))

    k_records = {}
    for cell in spec.get("k_cells", []):
        summary = json.loads(Path(cell["summary"]).read_text())
        key = (int(cell["K"]), int(cell["L"]), float(cell["Gamma"]))
        if int(summary["settings"]["num_exponentials"]) != key[0]:
            raise ValueError(f"K provenance mismatch for {key}")
        if int(summary["settings"]["length"]) != key[1]:
            raise ValueError(f"L provenance mismatch for {key}")
        if float(summary["settings"]["gamma"]) != key[2]:
            raise ValueError(f"Gamma provenance mismatch for {key}")
        k_records[key] = summary

    k_comparisons = []
    for length in (32, 64):
        for gamma in (1.56, 1.565):
            left = k_records.get((24, length, gamma))
            right = k_records.get((32, length, gamma))
            if left is None or right is None:
                continue
            k_comparisons.append(
                {
                    "length": length,
                    "gamma": gamma,
                    "gap": numeric_shift(
                        left["raw_observables"]["gap"],
                        right["raw_observables"]["gap"],
                    ),
                    "r_xi": numeric_shift(
                        left["raw_observables"]["r_xi"],
                        right["raw_observables"]["r_xi"],
                    ),
                    "energy_even": numeric_shift(
                        left["direct"]["even"]["energy"],
                        right["direct"]["even"]["energy"],
                    ),
                    "energy_odd": numeric_shift(
                        left["direct"]["odd"]["energy"],
                        right["direct"]["odd"]["energy"],
                    ),
                }
            )

    rxi_by_k = {}
    for k in (24, 32):
        by_length = {}
        for length in (32, 64):
            values = []
            for gamma in (1.56, 1.565):
                record = k_records.get((k, length, gamma))
                if record is None:
                    break
                values.append(record["raw_observables"]["r_xi"])
            if len(values) == 2:
                by_length[length] = values
        rxi_by_k[k] = by_length
    crossing = (
        compare_k_crossing(
            [1.56, 1.565],
            rxi_by_k[24],
            rxi_by_k[32],
        )
        if k_records
        else {"status": "pending"}
    )

    analysis = {
        "mps": {
            "status": "complete" if comparisons else "pending",
            "comparisons": comparisons,
        },
        "mpo": {
            "status": (
                "pending"
                if not k_records
                else (
                    "complete"
                    if crossing["status"] == "complete"
                    else "incomplete_cost_limited"
                )
            ),
            "crossing": crossing,
            "comparisons": k_comparisons,
        },
    }
    _atomic_json(args.output_dir / "analysis.json", analysis)
    rows = [
        {
            "length": item["length"],
            "gamma": item["gamma"],
            "chi_reference": item["chi"]["reference"],
            "chi_candidate": item["chi"]["candidate"],
            "gap_reference": item["gap"]["reference"],
            "gap_candidate": item["gap"]["candidate"],
            "gap_absolute_shift": item["gap"]["absolute"],
            "gap_relative_shift": item["gap"]["relative"],
            "r_xi_reference": item["r_xi"]["reference"],
            "r_xi_candidate": item["r_xi"]["candidate"],
            "r_xi_absolute_shift": item["r_xi"]["absolute"],
            "runtime_reference_seconds": item["runtime_seconds"][
                "reference_total"
            ],
            "runtime_candidate_seconds": item["runtime_seconds"][
                "candidate_total"
            ],
        }
        for item in comparisons
    ]
    _atomic_csv(
        args.output_dir / "mps-uncertainty.csv",
        rows,
        [
            "length",
            "gamma",
            "chi_reference",
            "chi_candidate",
            "gap_reference",
            "gap_candidate",
            "gap_absolute_shift",
            "gap_relative_shift",
            "r_xi_reference",
            "r_xi_candidate",
            "r_xi_absolute_shift",
            "runtime_reference_seconds",
            "runtime_candidate_seconds",
        ],
    )
    mpo_rows = [
        {
            "length": item["length"],
            "gamma": item["gamma"],
            "gap_K24": item["gap"]["reference"],
            "gap_K32": item["gap"]["candidate"],
            "gap_absolute_shift": item["gap"]["absolute"],
            "gap_relative_shift": item["gap"]["relative"],
            "r_xi_K24": item["r_xi"]["reference"],
            "r_xi_K32": item["r_xi"]["candidate"],
            "r_xi_absolute_shift": item["r_xi"]["absolute"],
        }
        for item in k_comparisons
    ]
    _atomic_csv(
        args.output_dir / "mpo-uncertainty.csv",
        mpo_rows,
        [
            "length",
            "gamma",
            "gap_K24",
            "gap_K32",
            "gap_absolute_shift",
            "gap_relative_shift",
            "r_xi_K24",
            "r_xi_K32",
            "r_xi_absolute_shift",
        ],
    )
    rxi_rows = []
    for (k, length, gamma), summary in sorted(k_records.items()):
        rxi_rows.append(
            {
                "K": k,
                "chi": summary["direct"]["even"]["requested_chi"],
                "length": length,
                "gamma": gamma,
                "r_xi": summary["raw_observables"]["r_xi"],
            }
        )
    _atomic_csv(
        args.output_dir / "rxi-by-chi-k.csv",
        rxi_rows,
        ["K", "chi", "length", "gamma", "r_xi"],
    )
    print(f"wrote {args.output_dir / 'analysis.json'}", flush=True)


if __name__ == "__main__":
    main()
