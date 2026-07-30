#!/usr/bin/env python3
"""Contract the fixed algebraic N-queens tensor network exactly."""

import argparse
import json
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algebraic_ttn import build_pair_factor_network, greedy_contract

# Validation constants only. They are never read by network construction,
# contraction planning, or tensor contraction.
REFERENCE_COUNTS = {
    1: 1,
    2: 0,
    3: 0,
    4: 2,
    5: 10,
    6: 4,
    7: 40,
    8: 92,
    9: 352,
    10: 724,
    11: 2680,
    12: 14200,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-min", type=int, default=1)
    parser.add_argument("--n-max", type=int, default=7)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=ROOT / "results/algebraic_ttn",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT / "results/algebraic_ttn/summary.jsonl",
    )
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object]] = []

    for n in range(args.n_min, args.n_max + 1):
        tracemalloc.start()
        started = time.perf_counter()
        local_tensors = build_pair_factor_network(n)
        construction_seconds = time.perf_counter() - started
        contraction_started = time.perf_counter()
        scalar, tree, statistics = greedy_contract(local_tensors)
        contraction_seconds = time.perf_counter() - contraction_started
        _, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        expected = REFERENCE_COUNTS.get(n)
        if expected is not None and scalar != expected:
            raise AssertionError(
                f"algebraic contraction mismatch for N={n}: {scalar} != {expected}"
            )
        tree_path = args.output_directory / f"contraction_tree_n{n}.json"
        tree_path.write_text(
            json.dumps(tree, separators=(",", ":"), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        summary = {
            "n": n,
            "exact_scalar": scalar,
            "initial_tensors": len(local_tensors),
            "construction_seconds": construction_seconds,
            "contraction_seconds": contraction_seconds,
            "peak_memory_bytes": peak_memory,
            "tree_artifact": str(tree_path.relative_to(ROOT)),
            **statistics,
            "uses_solution_enumeration": False,
            "uses_configuration_state_dp": False,
            "planner_inputs": "index labels and dimensions only",
        }
        summaries.append(summary)
        print(
            f"N={n}: scalar={scalar}, max rank={statistics['max_intermediate_rank']}, "
            f"max nnz={statistics['max_intermediate_nnz']}"
        )

    args.summary.parent.mkdir(parents=True, exist_ok=True)
    with args.summary.open("w", encoding="utf-8") as stream:
        for summary in summaries:
            stream.write(json.dumps(summary, sort_keys=True) + "\n")
    print(f"wrote {len(summaries)} algebraic contraction trees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
