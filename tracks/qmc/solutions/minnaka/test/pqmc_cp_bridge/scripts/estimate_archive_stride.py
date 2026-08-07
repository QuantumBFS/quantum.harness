#!/usr/bin/env python3
"""Choose a decorrelation stride from sweep-indexed archive diagnostics."""

from __future__ import annotations

import math
import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Iterable, Mapping, Sequence


REQUIRED_SCORE_COLUMNS = {
    "frozen_etotal",
    "field_sum",
    "staggered_field_sum",
    "logQ_final",
    "minimum_detrended_prefix_logQ",
    "near_node_count",
}


def integrated_autocorrelation_time(values: Sequence[float]) -> float:
    samples = [float(value) for value in values]
    if len(samples) < 4:
        raise ValueError("autocorrelation time requires at least four sweeps")
    if not all(math.isfinite(value) for value in samples):
        raise ValueError("autocorrelation input contains non-finite values")
    mean = math.fsum(samples) / len(samples)
    centered = [value - mean for value in samples]
    variance = math.fsum(value * value for value in centered) / len(centered)
    if variance <= 0.0:
        raise ValueError("autocorrelation input has zero variance")

    def rho(lag: int) -> float:
        return (
            math.fsum(
                centered[index] * centered[index + lag]
                for index in range(len(centered) - lag)
            )
            / len(centered)
            / variance
        )

    tau = 0.5
    lag = 1
    while lag + 1 < len(centered):
        pair = rho(lag) + rho(lag + 1)
        if pair <= 0.0:
            break
        tau += pair
        lag += 2
    return max(0.5, tau)


def choose_export_stride(tau_values: Mapping[str, float]) -> int:
    if not tau_values:
        raise ValueError("at least one autocorrelation time is required")
    maximum = max(float(value) for value in tau_values.values())
    if not math.isfinite(maximum) or maximum < 0.5:
        raise ValueError("invalid autocorrelation time")
    return max(20, math.ceil(5.0 * maximum))


def required_sweeps(
    target_records: int,
    stride: int,
    chains: int,
    burn_sweeps: int,
) -> int:
    if min(target_records, stride, chains) <= 0 or burn_sweeps < 0:
        raise ValueError("invalid archive workload")
    return burn_sweeps + stride * math.ceil(target_records / chains)


def validate_score_columns(columns: Iterable[str]) -> None:
    present = set(columns)
    missing = REQUIRED_SCORE_COLUMNS - present
    if missing:
        raise RuntimeError(
            "archive stride scores are missing required columns: "
            + ", ".join(sorted(missing))
        )


def estimate_stride(rows: Sequence[Mapping[str, object]]) -> dict:
    if not rows:
        raise ValueError("pilot score table is empty")
    validate_score_columns(rows[0].keys())
    groups: dict[tuple[str, int], list[Mapping[str, object]]] = {}
    for row in rows:
        groups.setdefault(
            (str(row["ensemble"]), int(row["chain"])), []
        ).append(row)
    expected = {
        (ensemble, chain) for ensemble in ("II", "TI") for chain in range(6)
    }
    if set(groups) != expected:
        raise ValueError("pilot scores require II/TI and six chains")
    tau: dict[str, float] = {}
    for group, values in sorted(groups.items()):
        values.sort(key=lambda row: int(row["sweep"]))
        sweeps = [int(row["sweep"]) for row in values]
        spacings = [
            right - left for left, right in zip(sweeps, sweeps[1:])
        ]
        if not spacings or len(set(spacings)) != 1 or spacings[0] <= 0:
            raise ValueError(f"pilot sweep spacing is irregular in {group}")
        spacing = spacings[0]
        for observable in sorted(REQUIRED_SCORE_COLUMNS):
            samples = [float(row[observable]) for row in values]
            try:
                tau_records = integrated_autocorrelation_time(samples)
            except ValueError as error:
                if "zero variance" not in str(error):
                    raise
                tau_records = 0.5
            tau[f"{group[0]}.chain{group[1]}.{observable}"] = (
                tau_records * spacing
            )
    stride = choose_export_stride(tau)
    return {
        "schema_version": 1,
        "tau_units": "sweeps",
        "tau": tau,
        "maximum_tau": max(tau.values()),
        "stride": stride,
        "rule": "max(20, ceil(5*max_tau))",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.scores.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = estimate_stride(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        f"archive stride={result['stride']} sweeps "
        f"(max tau={result['maximum_tau']:.3f})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
