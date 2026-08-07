"""Summarize exact and heuristic attempts to beat the learned 156-gate graph."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


CELL_PATTERN = re.compile(r"^\s+(\d+)\s+(\$_[A-Z0-9]+_)\s*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mdfa-search", action="append", type=Path, required=True)
    parser.add_argument("--abc-exact-summary", type=Path, required=True)
    parser.add_argument("--abc-polynomial-summary", type=Path, required=True)
    parser.add_argument("--abc-fast-aox-stat", type=Path, required=True)
    parser.add_argument("--abc-default-aox-stat", type=Path, required=True)
    parser.add_argument("--abc-delay-stat", action="append", type=Path, required=True)
    parser.add_argument("--output-summary", type=Path, required=True)
    return parser.parse_args()


def parse_stat(path: Path) -> dict[str, Any]:
    breakdown: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = CELL_PATTERN.match(line)
        if match:
            breakdown[match.group(2)] = int(match.group(1))
    if not breakdown:
        raise ValueError(f"no cells parsed from {path}")
    counted = sum(
        count
        for cell_type, count in breakdown.items()
        if cell_type != "$_NOT_"
    )
    return {
        "path": path.as_posix(),
        "counted_gates": counted,
        "free_NOT_cells": breakdown.get("$_NOT_", 0),
        "cell_breakdown": breakdown,
    }


def main() -> None:
    args = parse_args()
    searches = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in args.mdfa_search
    ]
    if len(searches) != 3:
        raise ValueError("expected three independent MDFA searches")
    for search in searches:
        if search["verification"]["all_32_inputs_exact"]:
            raise ValueError("a seven-gate MDFA was found; summary is stale")
        if search["verification"]["total_hamming_mismatch"] != 4:
            raise ValueError("unexpected best MDFA mismatch")
    abc_exact = json.loads(
        args.abc_exact_summary.read_text(encoding="utf-8")
    )
    abc_polynomial = json.loads(
        args.abc_polynomial_summary.read_text(encoding="utf-8")
    )
    for result in (abc_exact, abc_polynomial):
        verification = result["verification"]
        if not (
            verification["matches_source_network"]
            and verification["matches_clean_domain"]
        ):
            raise ValueError("ABC result is not independently exact")
    fast_aox = parse_stat(args.abc_fast_aox_stat)
    default_aox = parse_stat(args.abc_default_aox_stat)
    delay_scans = [parse_stat(path) for path in args.abc_delay_stat]
    if len(delay_scans) != 5:
        raise ValueError("expected five delay-constrained mappings")
    if {scan["counted_gates"] for scan in delay_scans} != {156}:
        raise ValueError("delay scan no longer reproduces 156 gates")

    summary = {
        "kind": "learned-156-gate-minimization-audit",
        "gate_model": {
            "two_input_AND_OR_XOR_with_free_edge_inversion": True,
            "equivalent_single_gate_families": [
                "AND",
                "NAND",
                "ANDNOT",
                "OR",
                "NOR",
                "ORNOT",
                "XOR",
                "XNOR",
            ],
            "NOT_cost": 0,
        },
        "claims": {
            "best_verified_gate_count": 156,
            "abc_independently_returns_156": True,
            "abc_delay_scan_all_return_156": True,
            "seven_gate_mdfa_found": False,
            "seven_gate_mdfa_search_is_not_a_lower_bound_proof": True,
            "total_seven_gate_candidates_evaluated": sum(
                search["evaluations"] for search in searches
            ),
            "best_seven_gate_total_hamming_mismatch": min(
                search["verification"]["total_hamming_mismatch"]
                for search in searches
            ),
            "no_tested_method_beats_156": True,
        },
        "mdfa_seven_gate_searches": [
            {
                "seed": search["seed"],
                "evaluations": search["evaluations"],
                "all_32_inputs_exact": search["verification"][
                    "all_32_inputs_exact"
                ],
                "best_total_hamming_mismatch": search["verification"][
                    "total_hamming_mismatch"
                ],
            }
            for search in searches
        ],
        "abc_results": {
            "fast_free_inversion_library": abc_exact,
            "five_delay_targets": delay_scans,
            "fast_AND_OR_XOR_only": fast_aox,
            "default_AND_OR_XOR_only": default_aox,
            "learned_polynomial_recompiled": abc_polynomial,
        },
        "interpretation": {
            "lower_bound_proved": False,
            "result": (
                "Independent global mapping matches 156 gates but does not "
                "improve it; heuristic seven-gate MDFA searches also fail."
            ),
        },
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary["claims"], indent=2))


if __name__ == "__main__":
    main()
