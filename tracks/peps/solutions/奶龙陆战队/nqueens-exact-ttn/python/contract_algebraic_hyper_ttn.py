#!/usr/bin/env python3
"""Exactly contract the COPY-absorbed algebraic tensor hypergraph."""

import argparse
import json
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algebraic_ttn import build_copy_absorbed_network, greedy_hyper_contract

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
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-min", type=int, default=1)
    parser.add_argument("--n-max", type=int, default=8)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=ROOT / "results/algebraic_hyper_ttn",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT / "results/algebraic_hyper_ttn/summary.jsonl",
    )
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    summaries = []
    for n in range(args.n_min, args.n_max + 1):
        tracemalloc.start()
        started = time.perf_counter()
        tensors = build_copy_absorbed_network(n)
        construction_seconds = time.perf_counter() - started
        contraction_started = time.perf_counter()
        scalar, tree, statistics = greedy_hyper_contract(tensors)
        contraction_seconds = time.perf_counter() - contraction_started
        _, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        if scalar != REFERENCE_COUNTS[n]:
            raise AssertionError(f"N={n}: {scalar} != {REFERENCE_COUNTS[n]}")
        tree_path = args.output_directory / f"contraction_tree_n{n}.json"
        tree_path.write_text(
            json.dumps(tree, separators=(",", ":"), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        summaries.append(
            {
                "n": n,
                "exact_scalar": scalar,
                "initial_tensors": len(tensors),
                "construction_seconds": construction_seconds,
                "contraction_seconds": contraction_seconds,
                "peak_memory_bytes": peak_memory,
                "tree_artifact": str(tree_path.relative_to(ROOT)),
                **statistics,
                "uses_solution_enumeration": False,
                "uses_configuration_state_dp": False,
                "copy_absorption": "exact tensor identity",
                "planner_inputs": "index incidence and dimensions only",
            }
        )
        print(
            f"N={n}: scalar={scalar}, max rank={statistics['max_intermediate_rank']}, "
            f"max nnz={statistics['max_intermediate_nnz']}"
        )
    with args.summary.open("w", encoding="utf-8") as stream:
        for summary in summaries:
            stream.write(json.dumps(summary, sort_keys=True) + "\n")
    print(f"wrote {len(summaries)} COPY-absorbed contraction trees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
