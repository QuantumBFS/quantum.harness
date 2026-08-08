#!/usr/bin/env python3
"""Exactly contract the algebraic network with contiguous uint64 arrays."""

import argparse
import json
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from algebraic_ttn.compact import (
        build_compact_copy_absorbed_network,
        greedy_compact_hyper_contract,
    )
except ModuleNotFoundError as error:
    if error.name == "numpy":
        raise SystemExit(
            "The compact backend requires NumPy. Use the bundled workspace "
            "Python or install NumPy in an isolated environment."
        ) from error
    raise


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


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes; Linux reports KiB.
    return int(peak if sys.platform == "darwin" else peak * 1024)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-min", type=int, default=1)
    parser.add_argument("--n-max", type=int, default=9)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=ROOT / "results/algebraic_compact_ttn",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT / "results/algebraic_compact_ttn/summary.jsonl",
    )
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)

    summaries = []
    for n in range(args.n_min, args.n_max + 1):
        started = time.perf_counter()
        tensors = build_compact_copy_absorbed_network(n)
        construction_seconds = time.perf_counter() - started
        contraction_started = time.perf_counter()
        scalar, tree, statistics = greedy_compact_hyper_contract(tensors)
        contraction_seconds = time.perf_counter() - contraction_started
        expected = REFERENCE_COUNTS.get(n)
        if expected is not None and scalar != expected:
            raise AssertionError(f"N={n}: {scalar} != {expected}")

        tree_path = args.output_directory / f"contraction_tree_n{n}.json"
        tree_path.write_text(
            json.dumps(tree, separators=(",", ":"), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        summary = {
            "n": n,
            "exact_scalar": scalar,
            "backend": "contiguous dense numpy uint64",
            "exactness_bound": f"all entries <= {n}^{n} < 2^64",
            "initial_tensors": len(tensors),
            "construction_seconds": construction_seconds,
            "contraction_seconds": contraction_seconds,
            "process_peak_rss_bytes": _peak_rss_bytes(),
            "tree_artifact": str(tree_path.relative_to(ROOT)),
            "uses_solution_enumeration": False,
            "uses_configuration_state_dp": False,
            "planner_inputs": "index incidence and dimensions only",
            **statistics,
        }
        summaries.append(summary)
        print(
            f"N={n}: scalar={scalar}, max rank="
            f"{statistics['max_intermediate_rank']}, max tensor="
            f"{statistics['max_tensor_bytes'] / 1_000_000:.2f} MB, "
            f"time={contraction_seconds:.3f} s"
        )

    with args.summary.open("w", encoding="utf-8") as stream:
        for summary in summaries:
            stream.write(json.dumps(summary, sort_keys=True) + "\n")
    print(f"wrote {len(summaries)} compact contraction trees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
