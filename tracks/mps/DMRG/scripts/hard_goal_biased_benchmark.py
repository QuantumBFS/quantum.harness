#!/usr/bin/env python3
"""Benchmark the real TT-biased JAX paired parallel-tempering kernel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Sequence

import numpy as np


TRACK_ROOT = Path(__file__).resolve().parents[1]
SRC = TRACK_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vmcrg_ref.artifacts import atomic_write_json  # noqa: E402
from spinglass3d.backend import BackendCase, checkpoint_nbytes  # noqa: E402
from spinglass3d.bias import BiasRoute, OverlapBias  # noqa: E402
from spinglass3d.jax_biased_backend import JaxBiasedPairBackend  # noqa: E402
from spinglass3d.linear_bias import LinearFeatureBasis  # noqa: E402
from spinglass3d.templates import TemplateEncoder  # noqa: E402
from spinglass3d.tensor_train import LocalTensorTrain, SymmetricLocalTT  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--temperatures", type=int, required=True)
    parser.add_argument("--pairs", type=int, required=True)
    parser.add_argument("--sweeps", type=int, required=True)
    parser.add_argument("--route", choices=("B", "C"), required=True)
    parser.add_argument("--chi", choices=(2, 4, 8), type=int, required=True)
    parser.add_argument("--require-platform", choices=("cpu", "gpu"), required=True)
    parser.add_argument("--seed", type=int, default=2026073225)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _build_bias(route: str, chi: int, seed: int) -> OverlapBias:
    encoder = TemplateEncoder("cube", conditioned=True, rg_level=1)
    tt = SymmetricLocalTT(
        LocalTensorTrain.random(encoder.token_count, chi, seed=seed),
        encoder,
    )
    if route == "C":
        return OverlapBias(
            BiasRoute.C_LINEAR_PLUS_TT,
            LinearFeatureBasis.cube_v1(),
            np.array([0.10, -0.06, 0.03, 0.02, -0.01]),
            tt,
        )
    return OverlapBias(BiasRoute.B_CONDITIONED_TT, None, np.empty(0), tt)


def run_benchmark(args: argparse.Namespace) -> dict[str, object]:
    for name in ("length", "temperatures", "pairs", "sweeps"):
        if int(getattr(args, name)) < 1:
            raise ValueError(f"{name} must be positive")
    if args.length % 3:
        raise ValueError("length must be divisible by three")
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite benchmark: {args.output}")
    case = BackendCase.random(
        length=args.length,
        temperatures=args.temperatures,
        samples=1,
        walkers=2 * args.pairs,
        seed=args.seed,
    )
    bias = _build_bias(args.route, args.chi, args.seed + 1)
    backend = JaxBiasedPairBackend(
        case,
        bias,
        required_platform=args.require_platform,
    )
    started = time.perf_counter()
    backend.run_sweeps(args.sweeps, progress_every=max(1, args.sweeps // 10))
    elapsed = time.perf_counter() - started
    resources = backend.resource_snapshot()
    steady_seconds = max(elapsed - float(resources["compile_seconds"]), 1e-12)
    record = {
        "schema_version": 1,
        "backend": resources["backend"],
        "platform": resources["platform"],
        "device": resources["device"],
        "float64_enabled": resources["float64_enabled"],
        "length": args.length,
        "temperatures": args.temperatures,
        "pairs": args.pairs,
        "sweeps": args.sweeps,
        "route": args.route,
        "template": "conditioned_cube",
        "chi": args.chi,
        "spin_proposals": backend.proposed_changes,
        "accepted_changes": backend.accepted_changes,
        "spin_proposals_per_second": backend.proposed_changes / steady_seconds,
        "accepted_changes_per_second": backend.accepted_changes / steady_seconds,
        "elapsed_seconds": elapsed,
        "steady_seconds": steady_seconds,
        "compile_seconds": resources["compile_seconds"],
        "lookup_build_seconds": resources["lookup_build_seconds"],
        "peak_host_memory_bytes": resources["host_rss_bytes"],
        "peak_device_memory_bytes": resources["device_memory_bytes"],
        "checkpoint_bytes": checkpoint_nbytes(backend.checkpoint_state()),
        "bias_signature": resources["bias_signature"],
        "provenance": "real SymmetricLocalTT-derived frozen cube lookup",
    }
    atomic_write_json(args.output, record)
    return record


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        record = run_benchmark(args)
    except Exception as error:
        print(
            f"biased benchmark failed closed: {type(error).__name__}: {error}",
            file=sys.stderr,
            flush=True,
        )
        return 2
    print(json.dumps(record, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
