#!/usr/bin/env python3
"""Path-stratum closure and constrained-path bias decomposition."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from analyze_prefix_risk import chain_partitions
from cross_reweight import cross_reweight_ii_to_ti


STATIC_STRATA = (
    "dead_support",
    "alive_low_final_q",
    "alive_deep_prefix_not_low_q",
    "alive_regular_static",
    "ambiguous_support",
)


def _empty_strata() -> dict[str, dict[str, float]]:
    return {
        label: {"probability": 0.0, "energy": math.nan}
        for label in STATIC_STRATA
    }


def ii_strata_estimates(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if not rows:
        raise ValueError("II estimator requires rows")
    result = _empty_strata()
    for label in STATIC_STRATA:
        selected = [
            row for row in rows
            if row["primary_static_stratum"] == label
        ]
        result[label]["probability"] = len(selected) / len(rows)
        if selected:
            result[label]["energy"] = math.fsum(
                float(row["central_ii_etot"]) for row in selected
            ) / len(selected)
    direct = math.fsum(
        float(row["central_ii_etot"]) for row in rows
    ) / len(rows)
    closure = math.fsum(
        value["probability"] * value["energy"]
        for value in result.values() if value["probability"] > 0
    )
    return {
        "direct_energy": direct,
        "strata": result,
        "closure_residual": closure - direct,
    }


def ti_sign_reweighted(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if not rows:
        raise ValueError("TI estimator requires rows")
    signs = [int(row["sign_d_alf_ti"]) for row in rows]
    denominator = math.fsum(signs)
    if denominator == 0:
        raise ValueError("TI sign denominator vanishes")
    result = _empty_strata()
    for label in STATIC_STRATA:
        selected = [
            (sign, row) for sign, row in zip(signs, rows)
            if row["primary_static_stratum"] == label
        ]
        signed_mass = math.fsum(sign for sign, _row in selected)
        result[label]["probability"] = signed_mass / denominator
        if signed_mass != 0:
            result[label]["energy"] = math.fsum(
                sign * float(row["central_ti_etot"])
                for sign, row in selected
            ) / signed_mass
    direct = math.fsum(
        sign * float(row["central_ti_etot"])
        for sign, row in zip(signs, rows)
    ) / denominator
    closure = math.fsum(
        value["probability"] * value["energy"]
        for value in result.values()
        if value["probability"] != 0 and math.isfinite(value["energy"])
    )
    return {
        "direct_energy": direct,
        "mean_sign": denominator / len(rows),
        "strata": result,
        "closure_residual": closure - direct,
    }


def cp_symmetric_ti(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Reweight TI ALF-cut samples to the symmetric CP path measure."""
    if not rows:
        raise ValueError("CP-symmetric TI estimator requires rows")
    log_ratios = [
        float(row["logabs_d_ti"]) - float(row["logabs_d_alf_ti"])
        for row in rows
    ]
    maximum = max(log_ratios)
    magnitudes = [math.exp(value - maximum) for value in log_ratios]
    signs = [int(row["sign_d_ti"]) for row in rows]
    if any(sign not in (-1, 1) for sign in signs):
        raise ValueError("CP-symmetric TI encountered zero/invalid sign")
    weights = [
        sign * magnitude for sign, magnitude in zip(signs, magnitudes)
    ]
    denominator = math.fsum(weights)
    total_magnitude = math.fsum(magnitudes)
    if abs(denominator) <= 1.0e-14 * total_magnitude:
        raise ValueError("CP-symmetric TI signed denominator vanishes")

    result = _empty_strata()
    for label in STATIC_STRATA:
        selected = [
            (weight, row)
            for weight, row in zip(weights, rows)
            if row["primary_static_stratum"] == label
        ]
        signed_mass = math.fsum(weight for weight, _row in selected)
        result[label]["probability"] = signed_mass / denominator
        if signed_mass != 0.0:
            result[label]["energy"] = math.fsum(
                weight * float(row["central_ti_etot"])
                for weight, row in selected
            ) / signed_mass
    direct = math.fsum(
        weight * float(row["central_ti_etot"])
        for weight, row in zip(weights, rows)
    ) / denominator
    closure = math.fsum(
        value["probability"] * value["energy"]
        for value in result.values()
        if value["probability"] != 0 and math.isfinite(value["energy"])
    )
    normalized = sorted(
        (magnitude / total_magnitude for magnitude in magnitudes),
        reverse=True,
    )
    top_count = max(1, math.ceil(0.01 * len(normalized)))
    return {
        "direct_energy": direct,
        "mean_sign": denominator / total_magnitude,
        "ess": total_magnitude * total_magnitude
        / math.fsum(value * value for value in magnitudes),
        "maximum_normalized_weight": normalized[0],
        "top_one_percent_share": math.fsum(normalized[:top_count]),
        "strata": result,
        "closure_residual": closure - direct,
    }


def support_restricted_ti(
    rows: Sequence[Mapping[str, object]],
) -> float:
    selected = [
        row for row in rows
        if str(row["alive"]).lower() in {"1", "true"}
        and not str(row.get("numerically_ambiguous", "0")).lower()
        in {"1", "true"}
    ]
    return float(cp_symmetric_ti(selected)["direct_energy"])


def decompose_frequency_within(
    ti: Mapping[str, Mapping[str, float]],
    cp: Mapping[str, Mapping[str, float]],
) -> dict[str, float]:
    labels = set(ti) | set(cp)
    frequency = 0.0
    within = 0.0
    ti_energy = 0.0
    cp_energy = 0.0
    for label in labels:
        ti_value = ti.get(label, {"probability": 0.0, "energy": math.nan})
        cp_value = cp.get(label, {"probability": 0.0, "energy": math.nan})
        p_ti = float(ti_value["probability"])
        p_cp = float(cp_value["probability"])
        e_ti = float(ti_value["energy"])
        e_cp = float(cp_value["energy"])
        if p_ti != 0:
            ti_energy += p_ti * e_ti
        if p_cp != 0:
            if not math.isfinite(e_ti) or not math.isfinite(e_cp):
                raise ValueError("occupied CP stratum lacks finite energies")
            cp_energy += p_cp * e_cp
            within += p_cp * (e_cp - e_ti)
        if math.isfinite(e_ti):
            frequency += (p_cp - p_ti) * e_ti
    residual = (cp_energy - ti_energy) - frequency - within
    return {
        "ti_energy": ti_energy,
        "cp_energy": cp_energy,
        "delta_frequency": frequency,
        "delta_within": within,
        "closure_residual": residual,
        "frequency_only_counterfactual": ti_energy + frequency,
    }


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    bridge = root / "test/pqmc_cp_bridge"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strata", type=Path,
        default=bridge / "replay/bulk/replay_strata.csv",
    )
    parser.add_argument("--split", choices=("held-out", "all"), default="held-out")
    parser.add_argument(
        "--output", type=Path,
        default=bridge / "results/energy_decomposition.json",
    )
    args = parser.parse_args()
    with args.strata.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if args.split == "held-out":
        _training, held_out = chain_partitions(rows)
        held_out_set = set(held_out)
        rows = [
            row for row in rows if int(row["chain"]) in held_out_set
        ]
    ii_rows = [row for row in rows if row["ensemble"] == "II"]
    ti_rows = [row for row in rows if row["ensemble"] == "TI"]
    ii = ii_strata_estimates(ii_rows)
    ti = ti_sign_reweighted(ti_rows)
    ti_cp = cp_symmetric_ti(ti_rows)
    cross = cross_reweight_ii_to_ti(ii_rows)
    output = {
        "schema_version": 1,
        "split": args.split,
        "ii": ii,
        "ti": ti,
        "ti_cp_symmetric": ti_cp,
        "support_restricted_ti_energy": support_restricted_ti(ti_rows),
        "cross_reweight_ii_to_ti": asdict(cross),
        "cp_frequency_within": None,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(
        output, indent=2, sort_keys=True, allow_nan=True
    ) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
