#!/usr/bin/env python3
"""Direct path-reweighting statistics with cross-chain record-slot bins."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import statistics
from typing import Iterable, Mapping, Sequence


def _integer(row: Mapping[str, object], key: str) -> int:
    try:
        return int(str(row[key]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {key} in replay summary") from exc


def _real(row: Mapping[str, object], key: str) -> float:
    try:
        value = float(str(row[key]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {key} in replay summary") from exc
    if not math.isfinite(value):
        raise ValueError(f"non-finite {key} in replay summary")
    return value


def read_summary_rows(paths: Iterable[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    fieldnames: list[str] | None = None
    for path in paths:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            if fieldnames is None:
                fieldnames = reader.fieldnames
            elif reader.fieldnames != fieldnames:
                raise ValueError("replay summary columns differ")
            rows.extend(reader)
    sample_ids = [_integer(row, "sample_id") for row in rows]
    if not rows or len(sample_ids) != len(set(sample_ids)):
        raise ValueError("replay summaries are empty or duplicate sample IDs")
    return rows


def _jackknife_error(values: Sequence[float]) -> float:
    if len(values) < 2:
        raise ValueError("jackknife requires at least two values")
    center = statistics.mean(values)
    return math.sqrt(
        (len(values) - 1) / len(values)
        * math.fsum((value - center) ** 2 for value in values)
    )


def compute_direct_reweight(
    source_rows: Sequence[Mapping[str, object]],
    *,
    expected_chains: int,
    paths_per_chain: int,
    target_error: float = 0.01,
    green_stability_pass: bool = False,
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    """Return summary, raw path rows, cross-chain bins, and chain LOO rows."""
    if expected_chains < 2 or paths_per_chain < 2:
        raise ValueError("at least two chains and two paths per chain are required")
    if target_error <= 0.0 or not math.isfinite(target_error):
        raise ValueError("target error must be finite and positive")
    if len(source_rows) != expected_chains * paths_per_chain:
        raise ValueError("replay row count does not match the requested rectangle")

    by_chain: dict[int, list[Mapping[str, object]]] = {}
    sample_ids: set[int] = set()
    for row in source_rows:
        if str(row.get("ensemble", "")).upper() != "TI":
            raise ValueError("direct reweighting requires only the TI ensemble")
        sample_id = _integer(row, "sample_id")
        if sample_id in sample_ids:
            raise ValueError("duplicate sample ID")
        sample_ids.add(sample_id)
        by_chain.setdefault(_integer(row, "chain"), []).append(row)
    chains = sorted(by_chain)
    if chains != list(range(expected_chains)):
        raise ValueError("global chain IDs must be contiguous from zero")

    prepared: list[dict[str, object]] = []
    for chain in chains:
        ordered = sorted(by_chain[chain], key=lambda row: _integer(row, "sweep"))
        sweeps = [_integer(row, "sweep") for row in ordered]
        if len(ordered) != paths_per_chain or len(sweeps) != len(set(sweeps)):
            raise ValueError("each chain must have unique, complete path slots")
        for slot, row in enumerate(ordered, start=1):
            sign_cp = _integer(row, "sign_d_ti")
            sign_alf = _integer(row, "sign_d_alf_ti")
            if sign_cp not in (-1, 0, 1) or sign_alf not in (-1, 0, 1):
                raise ValueError("determinant signs must be -1, 0, or 1")
            sign = sign_cp * sign_alf
            prepared.append({
                "sample_id": _integer(row, "sample_id"),
                "chain": chain,
                "slot": slot,
                "sweep": _integer(row, "sweep"),
                "weight_sign": sign,
                "log_weight": _real(row, "boundary_cut_log_ratio_ti"),
                "energy": _real(row, "central_ti_etot"),
            })

    log_shift = max(float(row["log_weight"]) for row in prepared)
    for row in prepared:
        magnitude = math.exp(float(row["log_weight"]) - log_shift)
        sign = int(row["weight_sign"])
        row["weight_scaled"] = sign * magnitude
        row["denominator_scaled"] = sign * magnitude
        row["numerator_scaled"] = (
            sign * magnitude * float(row["energy"])
        )

    bins: list[dict[str, object]] = []
    for slot in range(1, paths_per_chain + 1):
        selected = [row for row in prepared if row["slot"] == slot]
        if len(selected) != expected_chains:
            raise RuntimeError("cross-chain record slot is incomplete")
        numerator = math.fsum(
            float(row["numerator_scaled"]) for row in selected
        )
        denominator = math.fsum(
            float(row["denominator_scaled"]) for row in selected
        )
        if not math.isfinite(denominator) or abs(denominator) < 1.0e-300:
            raise ValueError("cross-chain bin denominator vanishes")
        bins.append({
            "slot": slot,
            "chains": expected_chains,
            "numerator_scaled": numerator,
            "denominator_scaled": denominator,
            "energy": numerator / denominator,
        })

    bin_energies = [float(row["energy"]) for row in bins]
    bin_mean = statistics.mean(bin_energies)
    bin_error = statistics.stdev(bin_energies) / math.sqrt(len(bin_energies))
    total_numerator = math.fsum(
        float(row["numerator_scaled"]) for row in prepared
    )
    total_denominator = math.fsum(
        float(row["denominator_scaled"]) for row in prepared
    )
    if abs(total_denominator) < 1.0e-300:
        raise ValueError("global reweighting denominator vanishes")
    global_ratio = total_numerator / total_denominator

    chain_sums = {
        chain: (
            math.fsum(
                float(row["numerator_scaled"])
                for row in prepared if row["chain"] == chain
            ),
            math.fsum(
                float(row["denominator_scaled"])
                for row in prepared if row["chain"] == chain
            ),
        )
        for chain in chains
    }
    loo: list[dict[str, object]] = []
    for chain in chains:
        denominator = total_denominator - chain_sums[chain][1]
        if abs(denominator) < 1.0e-300:
            raise ValueError("leave-one-chain denominator vanishes")
        loo.append({
            "excluded_chain": chain,
            "energy": (
                total_numerator - chain_sums[chain][0]
            ) / denominator,
        })
    loo_error = _jackknife_error(
        [float(row["energy"]) for row in loo]
    )

    magnitudes = [abs(float(row["weight_scaled"])) for row in prepared]
    magnitude_sum = math.fsum(magnitudes)
    magnitude_square_sum = math.fsum(value * value for value in magnitudes)
    if magnitude_sum <= 0.0 or magnitude_square_sum <= 0.0:
        raise ValueError("all direct weights vanish")
    normalized = sorted(
        (value / magnitude_sum for value in magnitudes), reverse=True
    )
    top_count = max(1, math.ceil(0.01 * len(normalized)))
    signs = [int(row["weight_sign"]) for row in prepared]
    nonpositive = sum(
        sign <= 0 or not math.isfinite(float(row["weight_scaled"]))
        for sign, row in zip(signs, prepared)
    )
    statistical_pass = (
        bin_error <= target_error
        and nonpositive == 0
        and len(bins) == paths_per_chain
    )
    summary: dict[str, object] = {
        "schema_version": 1,
        "estimator": "direct_ratio_of_sums",
        "chains": expected_chains,
        "paths_per_chain": paths_per_chain,
        "paths": len(prepared),
        "cross_chain_bins": len(bins),
        "global_log_weight_shift": log_shift,
        "energy_cross_chain_bin_mean": bin_mean,
        "energy_error_cross_chain_bins": bin_error,
        "energy_global_ratio": global_ratio,
        "aggregation_consistency_difference": bin_mean - global_ratio,
        "leave_one_chain_jackknife_error": loo_error,
        "leave_one_chain_min": min(float(row["energy"]) for row in loo),
        "leave_one_chain_max": max(float(row["energy"]) for row in loo),
        "effective_sample_size": magnitude_sum ** 2 / magnitude_square_sum,
        "maximum_normalized_weight": normalized[0],
        "top_one_percent_weight_share": math.fsum(normalized[:top_count]),
        "mean_weight_sign": math.fsum(signs) / len(signs),
        "nonpositive_or_nonfinite_weight_count": nonpositive,
        "target_error": target_error,
        "direct_reweight_statistical_precision_pass": statistical_pass,
        "green_stability_pass": bool(green_stability_pass),
    }
    return summary, prepared, bins, loo


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty product: {path.name}")
    fieldnames = list(rows[0])
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def write_products(
    source_rows: Sequence[Mapping[str, object]],
    output_dir: Path,
    *,
    expected_chains: int,
    paths_per_chain: int,
    target_error: float = 0.01,
    green_stability_pass: bool = False,
) -> dict[str, object]:
    summary, raw, bins, loo = compute_direct_reweight(
        source_rows,
        expected_chains=expected_chains,
        paths_per_chain=paths_per_chain,
        target_error=target_error,
        green_stability_pass=green_stability_pass,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "raw_path_statistics.csv", raw)
    _write_csv(output_dir / "cross_chain_bins.csv", bins)
    _write_csv(output_dir / "leave_one_chain_jackknife.csv", loo)
    (output_dir / "direct_reweight_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--replay-summary", type=Path, action="append", required=True
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-chains", type=int, default=1920)
    parser.add_argument("--paths-per-chain", type=int, default=50)
    parser.add_argument("--target-error", type=float, default=0.01)
    parser.add_argument("--green-stability-pass", action="store_true")
    args = parser.parse_args()
    rows = read_summary_rows(args.replay_summary)
    result = write_products(
        rows,
        args.output_dir,
        expected_chains=args.expected_chains,
        paths_per_chain=args.paths_per_chain,
        target_error=args.target_error,
        green_stability_pass=args.green_stability_pass,
    )
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
