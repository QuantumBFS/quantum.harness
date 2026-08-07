#!/usr/bin/env python3
"""Training-only prefix references and static CP risk labels."""

from __future__ import annotations

import math
import argparse
import csv
import json
from pathlib import Path
import statistics
from typing import Iterable, Mapping, Sequence

from prefix_file import records as prefix_records


def chain_partitions(
    rows: Iterable[Mapping[str, object]],
) -> tuple[list[int], list[int]]:
    chains_by_ensemble: dict[str, set[int]] = {}
    for row in rows:
        chains_by_ensemble.setdefault(str(row["ensemble"]), set()).add(
            int(row["chain"])
        )
    if set(chains_by_ensemble) != {"II", "TI"}:
        raise ValueError("both II and TI ensembles are required")
    chains = sorted(chains_by_ensemble["TI"])
    if (
        chains_by_ensemble["II"] != chains_by_ensemble["TI"]
        or chains != list(range(len(chains)))
        or len(chains) < 2
        or len(chains) % 2
    ):
        raise ValueError(
            "ensembles need matching, contiguous, even chain sets"
        )
    midpoint = len(chains) // 2
    return chains[:midpoint], chains[midpoint:]


def prefix_reference(
    training_prefixes: Sequence[Mapping],
    training_chains: Iterable[int] = (0, 1, 2),
) -> list[float]:
    allowed = set(int(value) for value in training_chains)
    eligible = [
        row for row in training_prefixes
        if int(row["chain"]) in allowed and bool(row["alive"])
    ]
    if not eligible:
        raise ValueError("no alive training-chain prefixes")
    lengths = {len(row["logq"]) for row in eligible}
    if len(lengths) != 1:
        raise ValueError("training prefixes have inconsistent lengths")
    length = lengths.pop()
    return [
        statistics.median(float(row["logq"][step]) for row in eligible)
        for step in range(length)
    ]


def prefix_barrier(
    logq: Sequence[float], reference: Sequence[float]
) -> tuple[float, int]:
    if len(logq) != len(reference) or not logq:
        raise ValueError("prefix and reference lengths differ")
    deviations = [
        float(value) - float(baseline)
        for value, baseline in zip(logq, reference)
    ]
    if not all(math.isfinite(value) for value in deviations):
        raise ValueError("non-finite prefix deviation")
    location = min(range(len(deviations)), key=deviations.__getitem__)
    return -deviations[location], location


def assign_static_strata(
    summary: Mapping[str, object],
    thresholds: Mapping[str, float],
) -> dict[str, str]:
    ambiguous = bool(summary.get("numerically_ambiguous", False))
    alive = bool(summary.get("alive", False))
    if ambiguous:
        support = "ambiguous"
    else:
        support = "alive" if alive else "dead"
    if not alive or ambiguous:
        proposal = "not_applicable"
        prefix = "not_applicable"
        near_node = "not_applicable"
    else:
        proposal = (
            "lowest_1pct"
            if float(summary["log_q_prop"]) <= float(thresholds["q01"])
            else "regular"
        )
        prefix = (
            "highest_1pct"
            if float(summary["prefix_barrier"]) >= float(thresholds["b99"])
            else "regular"
        )
        near_node = (
            "highest_1pct"
            if float(summary["near_node_count"]) > 0
            and float(summary["near_node_count"]) >=
            float(thresholds["n99"])
            else "regular"
        )
    if support != "alive":
        primary = "dead_support" if support == "dead" else "ambiguous_support"
    elif proposal == "lowest_1pct":
        primary = "alive_low_final_q"
    elif prefix == "highest_1pct":
        primary = "alive_deep_prefix_not_low_q"
    else:
        primary = "alive_regular_static"
    return {
        "support": support,
        "proposal_risk": proposal,
        "prefix_risk": prefix,
        "near_node_risk": near_node,
        "primary_static_stratum": primary,
    }


def quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered or not 0.0 <= probability <= 1.0:
        raise ValueError("invalid quantile input")
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def ambiguous_sample_ids(document: Mapping[str, object]) -> set[int]:
    result: set[int] = set()
    top_level = document.get("numerically_ambiguous_sample_ids", [])
    if not isinstance(top_level, list):
        raise ValueError("replay validation has invalid ambiguous IDs")
    result.update(int(value) for value in top_level)
    payload = document.get("stabilization")
    if payload is not None:
        if not isinstance(payload, Mapping):
            raise ValueError("invalid stabilization validation payload")
        values = payload.get("numerically_ambiguous")
        if not isinstance(values, list):
            raise ValueError("stabilization validation lacks ambiguous IDs")
        result.update(int(value) for value in values)
    elif not result:
        values = document.get("numerically_ambiguous")
        if not isinstance(values, list):
            raise ValueError("replay validation lacks ambiguous IDs")
        result.update(int(value) for value in values)
    return result


def analyze(
    summary_path: Path,
    prefix_path: Path,
    ambiguous_ids: set[int] | None = None,
) -> tuple[list[dict[str, object]], dict[str, object], list[float]]:
    with summary_path.open(newline="") as handle:
        summary = list(csv.DictReader(handle))
    by_id = {int(row["sample_id"]): row for row in summary}
    if len(by_id) != len(summary):
        raise ValueError("duplicate replay summary sample ID")
    training_chains, held_out_chains = chain_partitions(summary)
    training_set = set(training_chains)
    prefixes: dict[int, list] = {}
    for row in prefix_records(prefix_path):
        prefixes.setdefault(row.sample_id, []).append(row)
    if set(prefixes) != set(by_id):
        raise ValueError("prefix/summary sample IDs differ")
    for rows in prefixes.values():
        rows.sort(key=lambda row: row.slice)
    training = [
        {
            "chain": int(row["chain"]),
            "alive": row["alive"] == "1",
            "logq": [item.logq for item in prefixes[int(row["sample_id"])]],
        }
        for row in summary
        if row["ensemble"] == "TI" and int(row["chain"]) in training_set
        and row["alive"] == "1"
    ]
    reference = prefix_reference(training, training_chains)
    intermediate: list[dict[str, object]] = []
    for row in summary:
        sample_id = int(row["sample_id"])
        alive = row["alive"] == "1"
        barrier = math.nan
        barrier_slice = -1
        if alive:
            barrier, barrier_slice = prefix_barrier(
                [item.logq for item in prefixes[sample_id]], reference
            )
        near_node_count = sum(
            item.alive and item.sigma_min <= 1.0e-6
            for item in prefixes[sample_id]
        )
        intermediate.append({
            **row,
            "sample_id": sample_id,
            "chain": int(row["chain"]),
            "alive": alive,
            "prefix_barrier": barrier,
            "prefix_barrier_slice": barrier_slice,
            "near_node_count": near_node_count,
            "numerically_ambiguous": sample_id in (ambiguous_ids or set()),
        })
    training_alive = [
        row for row in intermediate
        if row["ensemble"] == "TI" and row["chain"] in training_set
        and row["alive"] and not row["numerically_ambiguous"]
    ]
    if not training_alive:
        raise ValueError("no unambiguous alive TI training paths")
    thresholds = {
        "q01": quantile(
            [float(row["log_q_prop"]) for row in training_alive], 0.01
        ),
        "b99": quantile(
            [float(row["prefix_barrier"]) for row in training_alive], 0.99
        ),
        "n99": quantile(
            [float(row["near_node_count"]) for row in training_alive], 0.99
        ),
    }
    result = []
    for row in intermediate:
        labels = assign_static_strata(row, thresholds)
        result.append({**row, **labels})
    contract = {
        "schema_version": 1,
        "training_ensemble": "TI",
        "training_chains": training_chains,
        "held_out_chains": held_out_chains,
        "near_node_sigma_threshold": 1.0e-6,
        "thresholds": thresholds,
        "primary_static_strata": [
            "dead_support", "alive_low_final_q",
            "alive_deep_prefix_not_low_q", "alive_regular_static",
            "ambiguous_support",
        ],
    }
    return result, contract, reference


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--stability-validation", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contract-output", type=Path, required=True)
    parser.add_argument("--reference-output", type=Path, required=True)
    args = parser.parse_args()
    ambiguous: set[int] = set()
    if args.stability_validation:
        stability = json.loads(args.stability_validation.read_text())
        ambiguous = ambiguous_sample_ids(stability)
    rows, contract, reference = analyze(
        args.summary, args.prefix, ambiguous
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    args.contract_output.parent.mkdir(parents=True, exist_ok=True)
    args.contract_output.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n"
    )
    args.reference_output.parent.mkdir(parents=True, exist_ok=True)
    args.reference_output.write_text(json.dumps({
        "schema_version": 1,
        "training_ensemble": "TI",
        "training_chains": contract["training_chains"],
        "median_logq_by_slice": reference,
    }, indent=2, sort_keys=True) + "\n")
    print(
        f"static strata: {len(rows)} paths, "
        f"thresholds={contract['thresholds']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
