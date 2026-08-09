#!/usr/bin/env python3
from __future__ import annotations

import argparse
from decimal import Decimal, localcontext
from fractions import Fraction
import json
from pathlib import Path

from trottercert.hpc_artifacts import (
    coordinate_terms_to_json,
    merge_coordinate_series,
    read_shard_gzip,
    sha256_file,
    write_manifest_atomic,
    write_shard_gzip,
)
from trottercert.intervals import cube_root_four_interval


def _pair(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def _decimal(value: Fraction, digits: int = 18) -> str:
    with localcontext() as context:
        context.prec = digits
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def reduce_shards(
    input_root: Path,
    *,
    expected_stages: int,
    order: int,
    output: Path,
    summary_path: Path,
) -> dict[str, object]:
    payloads: dict[int, dict[str, object]] = {}
    commits: set[str] = set()
    for stage in range(expected_stages):
        cell = input_root / f"stage-{stage:02d}"
        payload_path = cell / "shard.json.gz"
        manifest_path = cell / "manifest.json"
        if not payload_path.is_file() or not manifest_path.is_file():
            raise ValueError(f"missing shard or manifest for stage {stage}")
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("status") != "complete":
            raise ValueError(f"stage {stage} manifest is not complete")
        if manifest.get("output_sha256") != sha256_file(payload_path):
            raise ValueError(f"stage {stage} payload digest mismatch")
        payload = read_shard_gzip(payload_path)
        if payload.get("stage_index") != stage:
            raise ValueError(f"stage {stage} payload index mismatch")
        if payload.get("stage_count") != expected_stages:
            raise ValueError(f"stage {stage} stage-count mismatch")
        if payload.get("order") != order:
            raise ValueError(f"stage {stage} order mismatch")
        if payload.get("formula_id") != "five_copy_suzuki_fourth_order_exact_cubic":
            raise ValueError(f"stage {stage} formula mismatch")
        series = payload.get("series")
        if not isinstance(series, list) or len(series) != order + 1:
            raise ValueError(f"stage {stage} series length mismatch")
        commits.add(str(manifest.get("git_commit")))
        payloads[stage] = payload
    if len(commits) != 1:
        raise ValueError("shard manifests do not share one git commit")

    forward = merge_coordinate_series(
        [payloads[index]["series"] for index in range(expected_stages)]
    )
    reverse = merge_coordinate_series(
        [payloads[index]["series"] for index in reversed(range(expected_stages))]
    )
    if forward != reverse:
        raise ArithmeticError("forward and reverse exact shard reductions differ")
    root = cube_root_four_interval(30)
    degree = forward[order]
    cell_l1 = sum(
        (coefficient.enclose(root).abs_upper() for coefficient in degree.values()),
        Fraction(),
    )
    site_l1 = cell_l1 / 4
    merged_payload = {
        "schema_version": 1,
        "kind": "issue128_exact_right_generator_degree",
        "formula_id": "five_copy_suzuki_fourth_order_exact_cubic",
        "source_commit": next(iter(commits)),
        "source_stage_count": expected_stages,
        "degree": order,
        "terms": coordinate_terms_to_json(degree),
        "cell_pauli_l1_upper": _pair(cell_l1),
        "site_pauli_l1_upper": _pair(site_l1),
    }
    write_shard_gzip(output, merged_payload)
    summary = {
        "schema_version": 1,
        "kind": "issue128_d8_reduction_summary",
        "status": "complete",
        "source_commit": next(iter(commits)),
        "source_stage_count": expected_stages,
        "order": order,
        "degree_term_counts": {
            str(index): len(terms) for index, terms in enumerate(forward)
        },
        "cell_pauli_l1_upper": _pair(cell_l1),
        "cell_pauli_l1_upper_decimal": _decimal(cell_l1),
        "site_pauli_l1_upper": _pair(site_l1),
        "site_pauli_l1_upper_decimal": _decimal(site_l1),
        "output": output.name,
        "output_sha256": sha256_file(output),
        "reduction_order_check": "forward_equals_reverse",
    }
    write_manifest_atomic(summary_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--expected-stages", type=int, default=31)
    parser.add_argument("--order", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    arguments = parser.parse_args()
    summary = reduce_shards(
        arguments.input_root,
        expected_stages=arguments.expected_stages,
        order=arguments.order,
        output=arguments.output,
        summary_path=arguments.summary,
    )
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
