#!/usr/bin/env python3
"""Contract with row-mirror reuse and column-reflection even sectors."""

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
    from algebraic_ttn.block_reduction import (
        AcceleratorUnavailable,
        create_block_reducer,
    )
    from algebraic_ttn.parity import build_parity_copy_absorbed_network
    from algebraic_ttn.symmetric_parity import (
        SymmetricParityBudgetExceeded,
        greedy_symmetric_parity_contract,
    )
except ModuleNotFoundError as error:
    if error.name == "numpy":
        raise SystemExit(
            "The combined symmetry backend requires NumPy. Use the bundled "
            "workspace Python or install NumPy in an isolated environment."
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
    11: 2680,
    12: 14200,
    13: 73712,
    14: 365596,
}


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def _cuda_device_list(value: str) -> tuple[int, ...]:
    try:
        devices = tuple(int(item) for item in value.split(",") if item)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "CUDA devices must be comma-separated nonnegative integers"
        ) from error
    if not devices:
        raise argparse.ArgumentTypeError("at least one CUDA device is required")
    if len(set(devices)) != len(devices) or any(
        device < 0 for device in devices
    ):
        raise argparse.ArgumentTypeError(
            "CUDA devices must be unique nonnegative integers"
        )
    return devices


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-min", type=int, default=1)
    parser.add_argument("--n-max", type=int, default=10)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=ROOT / "results/algebraic_symmetric_parity_ttn",
    )
    parser.add_argument(
        "--max-join-pairs",
        type=int,
        help=(
            "stop before materializing a join larger than this many pairs; "
            "omitting the option performs the unbounded exact contraction"
        ),
    )
    parser.add_argument(
        "--join-chunk-pairs",
        type=int,
        help=(
            "stream larger joins through disk-backed blocks containing at "
            "most this many pairs"
        ),
    )
    parser.add_argument(
        "--streaming-temp-directory",
        type=Path,
        help="directory for temporary disk-backed streaming tensors",
    )
    parser.add_argument(
        "--streaming-merge-strategy",
        choices=("sorted-runs", "single-sort"),
        default="sorted-runs",
        help="external aggregation strategy for streamed joins",
    )
    parser.add_argument(
        "--block-reducer",
        choices=("numpy", "cuda"),
        default="numpy",
        help=(
            "exact contraction backend; CUDA also generates streamed "
            "grouped-join contributions directly on GPU"
        ),
    )
    parser.add_argument(
        "--cuda-device",
        type=int,
        default=0,
        help=(
            "CUDA device index within CUDA_VISIBLE_DEVICES when "
            "--block-reducer=cuda"
        ),
    )
    parser.add_argument(
        "--cuda-devices",
        type=_cuda_device_list,
        help=(
            "comma-separated CUDA device indices for exact multi-GPU "
            "grouped joins and key reduction; overrides --cuda-device"
        ),
    )
    parser.add_argument(
        "--cuda-min-records",
        type=int,
        default=1_000_000,
        help=(
            "keep smaller joins on the exact NumPy path; larger joins use "
            "GPU-native grouped contribution generation "
            "(default: 1000000)"
        ),
    )
    parser.add_argument(
        "--cuda-records-per-device",
        type=int,
        default=2_000_000,
        help=(
            "legacy in-memory key-range reducer records per active device; "
            "streamed grouped joins balance fixed-size work batches across "
            "all listed devices (default: 2000000)"
        ),
    )
    parser.add_argument(
        "--planner-tie-break",
        choices=("coverage-first", "symmetry-first"),
        default="coverage-first",
        help="tie break after topology width and rank are equal",
    )
    parser.add_argument(
        "--row-reflection-blocks",
        action="store_true",
        help=(
            "store self-mirror intermediate tensors in an additional exact "
            "row-reflection orbit sector"
        ),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT / "results/algebraic_symmetric_parity_ttn/summary.jsonl",
    )
    args = parser.parse_args()
    if args.max_join_pairs is not None and args.max_join_pairs < 0:
        parser.error("--max-join-pairs must be nonnegative")
    if args.join_chunk_pairs is not None and args.join_chunk_pairs <= 0:
        parser.error("--join-chunk-pairs must be positive")
    if args.cuda_device < 0:
        parser.error("--cuda-device must be nonnegative")
    if args.cuda_min_records < 0:
        parser.error("--cuda-min-records must be nonnegative")
    if args.cuda_records_per_device <= 0:
        parser.error("--cuda-records-per-device must be positive")
    try:
        block_reducer = create_block_reducer(
            args.block_reducer,
            cuda_device=args.cuda_device,
            cuda_devices=args.cuda_devices,
            cuda_min_records=args.cuda_min_records,
            cuda_records_per_device=args.cuda_records_per_device,
        )
    except (AcceleratorUnavailable, ValueError) as error:
        parser.error(str(error))
    args.output_directory.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)

    summaries = []
    for n in range(args.n_min, args.n_max + 1):
        started = time.perf_counter()
        tensors = build_parity_copy_absorbed_network(n)
        construction_seconds = time.perf_counter() - started
        contraction_started = time.perf_counter()
        try:
            scalar, tree, statistics = greedy_symmetric_parity_contract(
                tensors,
                n,
                max_join_pairs=args.max_join_pairs,
                join_chunk_pairs=args.join_chunk_pairs,
                streaming_temp_directory=args.streaming_temp_directory,
                streaming_merge_strategy=args.streaming_merge_strategy,
                planner_tie_break=args.planner_tie_break,
                row_reflection_blocks=args.row_reflection_blocks,
                block_reducer=block_reducer,
            )
        except SymmetricParityBudgetExceeded as error:
            contraction_seconds = time.perf_counter() - contraction_started
            summary = {
                **error.report,
                "backend": (
                    "row-reflection DAG plus column even sectors"
                ),
                "exactness_bound": f"all entries <= {n}^{n} < 2^64",
                "initial_tensors": len(tensors),
                "construction_seconds": construction_seconds,
                "contraction_seconds": contraction_seconds,
                "process_peak_rss_bytes": _peak_rss_bytes(),
                "row_reflection_subtree_reuse": True,
                "column_reflection_sector": "even",
                "join_chunk_pairs": args.join_chunk_pairs,
                "streaming_merge_strategy": args.streaming_merge_strategy,
                "planner_tie_break": args.planner_tie_break,
                "row_reflection_blocks": args.row_reflection_blocks,
                "uses_solution_enumeration": False,
                "uses_configuration_state_dp": False,
                "planner_inputs": (
                    "index incidence, dimensions, factor coverage, "
                    "row-reflection orbits"
                ),
            }
            summaries.append(summary)
            print(
                f"N={n}: stopped at step {error.report['blocked_step']}; "
                f"join needs {error.report['required_join_pairs']:,} "
                f"pairs > budget {error.report['max_join_pairs_budget']:,}"
            )
            continue
        contraction_seconds = time.perf_counter() - contraction_started
        expected = REFERENCE_COUNTS.get(n)
        if expected is not None and scalar != expected:
            raise AssertionError(f"N={n}: {scalar} != {expected}")

        tree_path = args.output_directory / f"contraction_tree_n{n}.json"
        tree_path.write_text(
            json.dumps(tree, separators=(",", ":"), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        try:
            tree_artifact = str(tree_path.relative_to(ROOT))
        except ValueError:
            tree_artifact = str(tree_path)
        summary = {
            "n": n,
            "exact_scalar": scalar,
            "backend": "row-reflection DAG plus column even sectors",
            "exactness_bound": f"all entries <= {n}^{n} < 2^64",
            "initial_tensors": len(tensors),
            "construction_seconds": construction_seconds,
            "contraction_seconds": contraction_seconds,
            "process_peak_rss_bytes": _peak_rss_bytes(),
            "tree_artifact": tree_artifact,
            "row_reflection_subtree_reuse": True,
            "column_reflection_sector": "even",
            "join_chunk_pairs": args.join_chunk_pairs,
            "streaming_merge_strategy": args.streaming_merge_strategy,
            "planner_tie_break": args.planner_tie_break,
            "row_reflection_blocks": args.row_reflection_blocks,
            "uses_solution_enumeration": False,
            "uses_configuration_state_dp": False,
            "planner_inputs": (
                "index incidence, dimensions, factor coverage, "
                "row-reflection orbits"
            ),
            **statistics,
        }
        summaries.append(summary)
        print(
            f"N={n}: scalar={scalar}, executed="
            f"{statistics['executed_contractions']}/"
            f"{statistics['conceptual_contractions']}, reuses="
            f"{statistics['mirror_reuses']}, max even tensor="
            f"{statistics['max_tensor_bytes'] / 1_000_000:.2f} MB, "
            f"reducer={statistics['block_reducer_backend']}, "
            f"time={contraction_seconds:.3f} s"
        )

    with args.summary.open("w", encoding="utf-8") as stream:
        for summary in summaries:
            stream.write(json.dumps(summary, sort_keys=True) + "\n")
    close_reducer = getattr(block_reducer, "close", None)
    if close_reducer is not None:
        close_reducer()
    print(f"wrote {len(summaries)} combined-symmetry DAGs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
