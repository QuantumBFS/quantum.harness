#!/usr/bin/env python3
"""Benchmark a complete two-replica parallel-tempering ladder."""

from __future__ import annotations

import argparse
import importlib.metadata
from pathlib import Path
import platform
import sys
import time
from typing import Sequence

import numpy as np


TRACK_ROOT = Path(__file__).resolve().parents[1]
SRC = TRACK_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spinglass3d.backend import BackendCase, checkpoint_nbytes  # noqa: E402
from spinglass3d.jax_backend import JaxParallelTemperingBackend  # noqa: E402
from spinglass3d.model import EABonds  # noqa: E402
from vmcrg_ref.artifacts import atomic_write_json  # noqa: E402


def _positive_integer(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{name} must be an integer")
    if int(value) < 1:
        raise ValueError(f"{name} must be positive")
    return int(value)


def run_pt_smoke(
    *,
    length: int,
    temperature_count: int,
    chain_pairs: int,
    warmup_sweeps: int,
    measured_sweeps: int,
    seed: int,
    required_platform: str,
    output: str | Path,
) -> dict[str, object]:
    import jax

    length = _positive_integer(length, "length")
    temperature_count = _positive_integer(temperature_count, "temperature_count")
    chain_pairs = _positive_integer(chain_pairs, "chain_pairs")
    warmup_sweeps = _positive_integer(warmup_sweeps, "warmup_sweeps")
    measured_sweeps = _positive_integer(measured_sweeps, "measured_sweeps")
    seed = _positive_integer(seed, "seed")
    if temperature_count < 2:
        raise ValueError("temperature_count must be at least two")
    if required_platform not in {"cpu", "gpu"}:
        raise ValueError("required_platform must be cpu or gpu")
    destination = Path(output)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite PT smoke output: {destination}")
    devices = jax.devices()
    actual_platform = jax.default_backend()
    if actual_platform != required_platform or not devices or any(
        device.platform != required_platform for device in devices
    ):
        raise RuntimeError(
            f"required JAX platform {required_platform!r}, got "
            f"backend={actual_platform!r} devices={devices!r}"
        )
    if not bool(jax.config.jax_enable_x64):
        raise RuntimeError("JAX float64 mode is required")

    seed_sequence = np.random.SeedSequence(seed)
    bond_seed, spin_seed = seed_sequence.spawn(2)
    bonds = EABonds.sample(length, np.random.default_rng(bond_seed))
    spins = np.random.default_rng(spin_seed).choice(
        np.array([-1, 1], dtype=np.int8),
        size=(1, temperature_count, 2 * chain_pairs, length, length, length),
    )
    betas = np.linspace(1.0 / 2.0, 1.0 / 0.8, temperature_count, dtype=np.float64)
    case = BackendCase(
        spins=spins,
        bonds=bonds.values[None, ...],
        betas=betas,
        seed=seed,
    )
    backend = JaxParallelTemperingBackend(case)
    print(
        f"PT smoke phase=compile L={length} temperatures={temperature_count} "
        f"chain_pairs={chain_pairs}",
        flush=True,
    )
    compile_started = time.perf_counter()
    backend.run_sweeps(warmup_sweeps)
    compile_wall_seconds = time.perf_counter() - compile_started
    proposals_before = backend.proposed_changes
    accepts_before = backend.accepted_changes
    swap_attempts_before = backend.swap_attempts.copy()
    swap_accepts_before = backend.swap_accepts.copy()

    measured_started = time.perf_counter()
    backend.run_sweeps(measured_sweeps)
    measured_wall_seconds = time.perf_counter() - measured_started
    measured_proposals = backend.proposed_changes - proposals_before
    measured_accepts = backend.accepted_changes - accepts_before
    measured_swap_attempts = backend.swap_attempts - swap_attempts_before
    measured_swap_accepts = backend.swap_accepts - swap_accepts_before
    if np.any(measured_swap_attempts <= 0):
        raise RuntimeError("PT smoke did not exercise every swap edge")
    edge_acceptance = measured_swap_accepts / measured_swap_attempts
    fields = backend.overlap_fields()
    overlap_binary = bool(np.all((fields == -1) | (fields == 1)))
    labels = backend.replica_ids
    expected_labels = np.arange(temperature_count, dtype=np.int64)
    label_permutations = bool(
        np.all(
            np.sort(labels, axis=1)
            == expected_labels[None, :, None]
        )
    )
    resources = backend.resource_snapshot()
    checkpoint = backend.checkpoint_state()
    manifest: dict[str, object] = {
        "schema_version": 1,
        "classification": "PASS",
        "scope": "stage6-pt-backend-smoke-only",
        "runtime": {
            "host": platform.node(),
            "python": platform.python_version(),
            "jax": importlib.metadata.version("jax"),
            "jaxlib": importlib.metadata.version("jaxlib"),
            "numpy": importlib.metadata.version("numpy"),
            "default_backend": actual_platform,
            "devices": [str(device) for device in devices],
            "device_platforms": [device.platform for device in devices],
            "x64_enabled": bool(jax.config.jax_enable_x64),
        },
        "benchmark": {
            "length": length,
            "temperature_count": temperature_count,
            "chain_pairs": chain_pairs,
            "states": temperature_count * 2 * chain_pairs,
            "warmup_sweeps": warmup_sweeps,
            "measured_sweeps": measured_sweeps,
            "compile_wall_seconds": compile_wall_seconds,
            "backend_compile_seconds": float(resources["compile_seconds"]),
            "measured_wall_seconds": measured_wall_seconds,
            "measured_proposals": measured_proposals,
            "warm_spin_proposals_per_second": (
                measured_proposals / measured_wall_seconds
            ),
            "accepted_changes_per_second": measured_accepts / measured_wall_seconds,
            "checkpoint_bytes": checkpoint_nbytes(checkpoint),
            "peak_host_memory_bytes": int(resources["host_rss_bytes"]),
            "peak_device_memory_bytes": int(resources["device_memory_bytes"]),
        },
        "parallel_tempering": {
            "temperature_min": 0.8,
            "temperature_max": 2.0,
            "betas": [float(value) for value in betas],
            "edge_attempts": [int(value) for value in measured_swap_attempts],
            "edge_accepts": [int(value) for value in measured_swap_accepts],
            "edge_acceptance": [float(value) for value in edge_acceptance],
            "round_trips_min": int(np.min(backend.round_trips)),
            "round_trips_max": int(np.max(backend.round_trips)),
            "replica_labels_are_permutations": label_permutations,
            "overlap_binary": overlap_binary,
        },
        "seed": seed,
    }
    if not overlap_binary or not label_permutations:
        raise RuntimeError("PT state invariants failed")
    destination.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(destination, manifest)
    print(
        "PT smoke phase=complete "
        f"proposals_per_second={manifest['benchmark']['warm_spin_proposals_per_second']:.6g} "
        f"output={destination}",
        flush=True,
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--temperatures", type=int, required=True)
    parser.add_argument("--chain-pairs", type=int, required=True)
    parser.add_argument("--warmup-sweeps", type=int, default=1)
    parser.add_argument("--sweeps", type=int, required=True)
    parser.add_argument("--seed", type=int, default=2026073193)
    parser.add_argument("--require-platform", choices=("cpu", "gpu"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run_pt_smoke(
            length=args.length,
            temperature_count=args.temperatures,
            chain_pairs=args.chain_pairs,
            warmup_sweeps=args.warmup_sweeps,
            measured_sweeps=args.sweeps,
            seed=args.seed,
            required_platform=args.require_platform,
            output=args.output,
        )
    except (FileExistsError, RuntimeError, TypeError, ValueError) as error:
        print(f"PT smoke failed closed: {error}", file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
