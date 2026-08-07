#!/usr/bin/env python3
"""Small reference/JAX backend throughput and memory benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spinglass3d.backend import (  # noqa: E402
    BackendCase,
    BenchmarkRecord,
    NumpyReferenceBackend,
    checkpoint_nbytes,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--temperatures", type=int, required=True)
    parser.add_argument("--samples", type=int, required=True)
    parser.add_argument("--walkers", type=int, default=1)
    parser.add_argument("--sweeps", type=int, required=True)
    parser.add_argument("--backend", choices=("reference", "jax"), required=True)
    parser.add_argument("--seed", type=int, default=2026072920)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    case = BackendCase.random(
        length=args.length,
        temperatures=args.temperatures,
        samples=args.samples,
        walkers=args.walkers,
        seed=args.seed,
    )
    if args.backend == "reference":
        backend = NumpyReferenceBackend(case)
        provenance = "numpy-float64-reference"
    else:
        from spinglass3d.jax_backend import JaxBatchedBackend

        backend = JaxBatchedBackend(case)
        provenance = "jax-float64-independent-state-vmap"
    print(
        f"benchmark backend={args.backend} L={args.length} "
        f"states={args.samples * args.temperatures * args.walkers}",
        flush=True,
    )
    started = time.perf_counter()
    backend.sweeps(args.sweeps)
    elapsed = time.perf_counter() - started
    resources = backend.resource_snapshot()
    checkpoint = backend.checkpoint_state()
    record = BenchmarkRecord(
        backend=str(resources["backend"]),
        length=args.length,
        temperatures=args.temperatures,
        samples=args.samples,
        walkers=args.walkers,
        sweeps=args.sweeps,
        spin_proposals_per_second=backend.proposed_changes / elapsed,
        accepted_changes_per_second=backend.accepted_changes / elapsed,
        peak_host_memory_bytes=int(resources["host_rss_bytes"]),
        peak_device_memory_bytes=int(resources["device_memory_bytes"]),
        compile_seconds=float(resources.get("compile_seconds", 0.0)),
        checkpoint_bytes=checkpoint_nbytes(checkpoint),
        elapsed_seconds=elapsed,
        provenance=provenance,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    temporary.write_text(
        json.dumps(record.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(
        f"benchmark proposals_per_second={record.spin_proposals_per_second:.6g} "
        f"output={args.output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
