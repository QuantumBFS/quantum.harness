#!/usr/bin/env python3
"""Exactly contract the algebraic network with packed coordinate arrays."""

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
    from algebraic_ttn.packed import (
        build_packed_copy_absorbed_network,
        choose_horizontal_reflection_row,
        greedy_packed_hyper_contract,
        with_horizontal_reflection_domain,
    )
except ModuleNotFoundError as error:
    if error.name == "numpy":
        raise SystemExit(
            "The packed backend requires NumPy. Use the bundled workspace "
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
    return int(peak if sys.platform == "darwin" else peak * 1024)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-min", type=int, default=1)
    parser.add_argument("--n-max", type=int, default=10)
    parser.add_argument(
        "--horizontal-reflection",
        action="store_true",
        help="contract one exact row-reflection fundamental domain",
    )
    parser.add_argument(
        "--reflection-row",
        type=int,
        help="mirror-pair row; omit for topology-only automatic selection",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
    )
    args = parser.parse_args()
    symmetry_enabled = (
        args.horizontal_reflection or args.reflection_row is not None
    )
    if args.output_directory is None:
        directory_name = (
            "algebraic_packed_ttn_reflection"
            if symmetry_enabled
            else "algebraic_packed_ttn"
        )
        args.output_directory = ROOT / "results" / directory_name
    if args.summary is None:
        args.summary = args.output_directory / "summary.jsonl"
    args.output_directory.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)

    summaries = []
    for n in range(args.n_min, args.n_max + 1):
        started = time.perf_counter()
        tensors = build_packed_copy_absorbed_network(n)
        reflection_row = None
        if symmetry_enabled and n >= 2:
            reflection_row = (
                args.reflection_row
                if args.reflection_row is not None
                else choose_horizontal_reflection_row(tensors, n)
            )
            tensors = with_horizontal_reflection_domain(
                tensors, n, reflection_row
            )
        construction_seconds = time.perf_counter() - started
        contraction_started = time.perf_counter()
        scalar, tree, statistics = greedy_packed_hyper_contract(tensors)
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
            "backend": "sorted flat-coordinate and value uint64 arrays",
            "exactness_bound": (
                f"all entries <= 2*{n}^{n} < 2^64"
                if reflection_row is not None
                else f"all entries <= {n}^{n} < 2^64"
            ),
            "initial_tensors": len(tensors),
            "construction_seconds": construction_seconds,
            "contraction_seconds": contraction_seconds,
            "process_peak_rss_bytes": _peak_rss_bytes(),
            "tree_artifact": str(tree_path.relative_to(ROOT)),
            "uses_solution_enumeration": False,
            "uses_configuration_state_dp": False,
            "planner_inputs": "index incidence and dimensions only",
            "horizontal_reflection_domain": reflection_row is not None,
            "reflection_row_pair": (
                [reflection_row, n - 1 - reflection_row]
                if reflection_row is not None
                else None
            ),
            "representative_condition": (
                f"column_{reflection_row} < "
                f"column_{n - 1 - reflection_row}"
                if reflection_row is not None
                else None
            ),
            "orbit_weight": 2 if reflection_row is not None else 1,
            **statistics,
        }
        summaries.append(summary)
        print(
            f"N={n}: scalar={scalar}, max rank="
            f"{statistics['max_intermediate_rank']}, max packed tensor="
            f"{statistics['max_tensor_bytes'] / 1_000_000:.2f} MB, "
            f"time={contraction_seconds:.3f} s, "
            f"reflection pair={summary['reflection_row_pair']}"
        )

    with args.summary.open("w", encoding="utf-8") as stream:
        for summary in summaries:
            stream.write(json.dumps(summary, sort_keys=True) + "\n")
    print(f"wrote {len(summaries)} packed contraction trees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
