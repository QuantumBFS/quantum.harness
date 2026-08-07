"""Command-line entry point for reproducible VQETape experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vqetape.compiler import compile_vqe
from vqetape.spatial_candidates import (
    search_spatial_candidates,
    search_symmetry_candidates,
)
from vqetape.spec import CompileRequest, TFIMVQESpec
from vqetape.tn_candidates import search_tn_candidates


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compile and benchmark exact TFIM VQE value-and-gradient programs."
    )
    parser.add_argument("--nqubits", required=True, type=int)
    parser.add_argument("--depth", required=True, type=int)
    parser.add_argument(
        "--mode",
        choices=(
            "statevector",
            "direct-tn",
            "spatial-transfer",
            "symmetry",
        ),
        default="statevector",
    )
    parser.add_argument("--coupling", type=float, default=1.0)
    parser.add_argument("--field", type=float, default=1.0)
    parser.add_argument(
        "--initial-state",
        choices=("zero", "plus"),
        default="plus",
    )
    parser.add_argument(
        "--dtype",
        choices=("complex64", "complex128"),
        default="complex64",
    )
    parser.add_argument("--memory-budget-gib", required=True, type=float)
    parser.add_argument("--expected-steps", required=True, type=int)
    parser.add_argument("--warm-repeats", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    request = CompileRequest(
        spec=TFIMVQESpec(
            nqubits=args.nqubits,
            depth=args.depth,
            coupling=args.coupling,
            field=args.field,
            initial_state=args.initial_state,
            dtype=args.dtype,
        ),
        memory_budget_bytes=int(args.memory_budget_gib * 1024**3),
        expected_vqe_steps=args.expected_steps,
        warm_repeats=args.warm_repeats,
        seed=args.seed,
        timeout_seconds=args.timeout_seconds,
    )
    if args.mode == "direct-tn":
        compiled = search_tn_candidates(request)
    elif args.mode == "spatial-transfer":
        compiled = search_spatial_candidates(request)
    elif args.mode == "symmetry":
        compiled = search_symmetry_candidates(request)
    else:
        compiled = compile_vqe(request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(compiled.to_report(), indent=2, allow_nan=False),
        encoding="utf-8",
    )
    print(
        f"selected={compiled.selected.config.label} "
        f"warm={compiled.selected.warm_seconds_median:.6f}s "
        f"rss={compiled.selected.peak_rss_bytes / 1024**2:.1f}MiB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
