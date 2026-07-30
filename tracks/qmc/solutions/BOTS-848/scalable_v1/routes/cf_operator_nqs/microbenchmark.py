"""Frozen Route C exact-action admission benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform as platform_module
import statistics
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path

import jax
import numpy as np

from ...resources import peak_rss_bytes
from .jax_action import build_family_action_kernel
from .seeds import JKCFSeedFamily


_FROZEN_BATCH = 512
_FROZEN_WARMUPS = 2
_FROZEN_REPETITIONS = 5
_ACTION_BUDGET_SECONDS = 3600.0
_RSS_LIMIT_BYTES = 51539607552


def classify_record(record: Mapping[str, object]) -> dict[str, object]:
    medians = record["sector_median_seconds"]
    if not isinstance(medians, Mapping):
        raise TypeError("sector_median_seconds must be a mapping")
    projected = float(record["compile_seconds"]) + 2 * 2048 * max(
        float(medians["l0"]),
        float(medians["l2"]),
    )
    frozen_shape = (
        record["n_electrons"] == 6
        and record["two_q"] == 15
        and record["batch_size"] == _FROZEN_BATCH
        and record["warmup_repetitions"] == _FROZEN_WARMUPS
        and record["measured_repetitions"] == _FROZEN_REPETITIONS
    )
    green = (
        frozen_shape
        and bool(record["finite"])
        and projected <= _ACTION_BUDGET_SECONDS
        and int(record["peak_rss_bytes"]) <= _RSS_LIMIT_BYTES
    )
    return {
        "classification": "GREEN" if green else "RED",
        "projected_action_seconds": projected,
        "action_budget_seconds": _ACTION_BUDGET_SECONDS,
        "rss_limit_bytes": _RSS_LIMIT_BYTES,
        "frozen_shape": frozen_shape,
    }


def _normalized_configs(*, n_electrons: int, batch_size: int) -> np.ndarray:
    rng = np.random.default_rng(3848)
    values = rng.normal(size=(batch_size, n_electrons, 2)) + 1j * rng.normal(
        size=(batch_size, n_electrons, 2)
    )
    return np.asarray(
        values / np.linalg.norm(values, axis=-1, keepdims=True),
        dtype=np.complex128,
    )


def _block(outputs: tuple[object, object]) -> tuple[np.ndarray, np.ndarray]:
    outputs[1].block_until_ready()
    return np.asarray(outputs[0]), np.asarray(outputs[1])


def run_benchmark(
    *,
    n_electrons: int,
    batch_size: int,
    selected_platform: str,
    warmups: int,
    repetitions: int,
) -> dict[str, object]:
    two_q = 3 * (n_electrons - 1)
    family = JKCFSeedFamily(n_electrons=n_electrons, two_q=two_q)
    configs = _normalized_configs(
        n_electrons=n_electrons,
        batch_size=batch_size,
    )
    compile_times: dict[str, float] = {}
    warmup_times: dict[str, list[float]] = {}
    measured_times: dict[str, list[float]] = {}
    finite = True
    for sector in ("l0", "l2"):
        kernel = build_family_action_kernel(
            family,
            platform=selected_platform,
            sector=sector,
        )
        started = time.perf_counter()
        seeds, actions = _block(kernel(configs))
        compile_times[sector] = time.perf_counter() - started
        finite = finite and bool(np.all(np.isfinite(seeds))) and bool(
            np.all(np.isfinite(actions))
        )
        print(
            f"compile sector={sector} seconds={compile_times[sector]:.9f}",
            flush=True,
        )
        warmup_times[sector] = []
        for index in range(warmups):
            started = time.perf_counter()
            _block(kernel(configs))
            elapsed = time.perf_counter() - started
            warmup_times[sector].append(elapsed)
            print(
                f"warmup sector={sector} index={index + 1} seconds={elapsed:.9f}",
                flush=True,
            )
        measured_times[sector] = []
        for index in range(repetitions):
            started = time.perf_counter()
            seeds, actions = _block(kernel(configs))
            elapsed = time.perf_counter() - started
            measured_times[sector].append(elapsed)
            finite = finite and bool(np.all(np.isfinite(seeds))) and bool(
                np.all(np.isfinite(actions))
            )
            print(
                f"measure sector={sector} index={index + 1} seconds={elapsed:.9f}",
                flush=True,
            )
    protocol_path = Path(__file__).resolve().parents[2] / "protocol.json"
    source_root = Path(__file__).resolve().parents[7]
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    devices = jax.devices(selected_platform)
    record: dict[str, object] = {
        "schema": "route-c-action-microbenchmark-v1",
        "source_commit": source_commit,
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "n_electrons": n_electrons,
        "two_q": two_q,
        "batch_size": batch_size,
        "warmup_repetitions": warmups,
        "measured_repetitions": repetitions,
        "platform": selected_platform,
        "devices": [str(device) for device in devices],
        "python_version": sys.version,
        "host_platform": platform_module.platform(),
        "jax_version": jax.__version__,
        "dtype": "complex128",
        "compile_seconds_by_sector": compile_times,
        "compile_seconds": sum(compile_times.values()),
        "warmup_seconds": warmup_times,
        "measured_seconds": measured_times,
        "sector_median_seconds": {
            sector: statistics.median(values)
            for sector, values in measured_times.items()
        },
        "peak_rss_bytes": peak_rss_bytes(),
        "finite": finite,
    }
    record.update(classify_record(record))
    return record


def _write_atomic(path: Path, record: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-electrons", type=int, required=True)
    parser.add_argument("--batch-size", type=int, required=True)
    parser.add_argument("--platform", dest="selected_platform", required=True)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> None:
    arguments = _parser().parse_args()
    if arguments.n_electrons < 2 or arguments.batch_size <= 0:
        raise ValueError("n-electrons must be at least 2 and batch-size positive")
    if arguments.warmups < 0 or arguments.repetitions <= 0:
        raise ValueError("warmups must be nonnegative and repetitions positive")
    record = run_benchmark(
        n_electrons=arguments.n_electrons,
        batch_size=arguments.batch_size,
        selected_platform=arguments.selected_platform,
        warmups=arguments.warmups,
        repetitions=arguments.repetitions,
    )
    _write_atomic(arguments.output, record)
    print(
        f"classification={record['classification']} output={arguments.output}",
        flush=True,
    )


if __name__ == "__main__":
    main()


__all__ = ["classify_record", "run_benchmark"]
