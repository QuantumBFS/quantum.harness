#!/usr/bin/env python3
"""Resumable two-hour fixed-count RBIM Nishimori-point production run."""

import os

for _thread_variable in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_thread_variable] = "1"

import argparse
import json
import math
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

import numpy as np

try:
    from random_bond_ising_analysis import (
        aggregate_sample_records,
        central_charge_ensemble_summary,
        write_ensemble_artifacts,
    )
    from random_bond_ising_transfer import run_fixed_count_strip
except ImportError:  # imported from the repository root during tests
    from scripts.random_bond_ising_analysis import (
        aggregate_sample_records,
        central_charge_ensemble_summary,
        write_ensemble_artifacts,
    )
    from scripts.random_bond_ising_transfer import run_fixed_count_strip


DEFAULT_SAMPLE_COUNTS = {4: 192, 5: 160, 6: 128, 8: 96, 9: 96, 10: 80, 12: 64}
BENCHMARK_SECONDS = {
    4: 21.88,
    5: 21.77,
    6: 25.75,
    8: 32.33,
    9: 38.41,
    10: 42.99,
    12: 80.51,
}


def sample_seed(base_seed, L, sample_index):
    """Return a deterministic independent seed for one width/sample pair."""
    sequence = np.random.SeedSequence(
        [int(base_seed), int(L), int(sample_index)]
    )
    return int(sequence.generate_state(1, dtype=np.uint64)[0])


def build_tasks(sample_counts, completed):
    """Return missing sample tasks in balanced, slow-width-first order."""
    normalized = {int(L): int(count) for L, count in sample_counts.items()}
    if not normalized or any(L < 2 or count <= 0 for L, count in normalized.items()):
        raise ValueError("sample counts require positive counts at widths L >= 2")
    completed = {(int(L), int(index)) for L, index in completed}
    tasks = []
    for L, count in normalized.items():
        for sample_index in range(count):
            if (L, sample_index) not in completed:
                tasks.append(
                    {
                        "L": L,
                        "sample_index": sample_index,
                        "requested_samples": count,
                    }
                )
    tasks.sort(
        key=lambda item: (
            item["sample_index"] / item["requested_samples"],
            -BENCHMARK_SECONDS.get(item["L"], float(item["L"])),
            item["L"],
        )
    )
    return tasks


def _jsonable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def write_sample_record_atomic(record, output_dir):
    """Atomically write one completed sample record and return its path."""
    output_dir = Path(output_dir)
    L = int(record["L"])
    sample_index = int(record["sample_index"])
    sample_dir = output_dir / "samples" / f"L{L}"
    sample_dir.mkdir(parents=True, exist_ok=True)
    final_path = sample_dir / f"sample_{sample_index:04d}.json"
    temporary_path = final_path.with_suffix(".json.tmp")
    with temporary_path.open("w", encoding="utf-8") as handle:
        json.dump(_jsonable(record), handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary_path.replace(final_path)
    return final_path


def _normalized_sample_counts(sample_counts):
    return {int(L): int(count) for L, count in sample_counts.items()}


def _validate_record(record, expected_config):
    required = {
        "L",
        "sample_index",
        "seed",
        "p",
        "coupling",
        "burn_in",
        "retained_rows",
        "block_length",
        "free_energy",
        "runtime_seconds",
        "antiferromagnetic_bonds",
        "total_retained_bonds",
        "disorder_ensemble",
    }
    if not required.issubset(record):
        raise ValueError("sample record is missing required fields")
    counts = _normalized_sample_counts(expected_config["sample_counts"])
    L = int(record["L"])
    sample_index = int(record["sample_index"])
    if L not in counts or not 0 <= sample_index < counts[L]:
        raise ValueError("sample record is outside the requested allocation")
    if not math.isclose(
        float(record["p"]), float(expected_config["p"]), rel_tol=0.0, abs_tol=1e-15
    ):
        raise ValueError("sample record has a different bond probability")
    for field in ("burn_in", "retained_rows", "block_length"):
        if int(record[field]) != int(expected_config[field]):
            raise ValueError(f"sample record has a different {field}")
    total_bonds = 2 * L * int(record["retained_rows"])
    expected_antiferromagnetic = int(round(float(record["p"]) * total_bonds))
    if int(record["total_retained_bonds"]) != total_bonds:
        raise ValueError("sample record has a wrong retained bond count")
    if int(record["antiferromagnetic_bonds"]) != expected_antiferromagnetic:
        raise ValueError("sample record has a wrong antiferromagnetic bond count")
    if str(record["disorder_ensemble"]) != "fixed_count":
        raise ValueError("sample record has the wrong disorder ensemble")
    if not math.isfinite(float(record["free_energy"])):
        raise ValueError("sample record has a non-finite free energy")


def load_valid_records(output_dir, expected_config):
    """Load resumable sample records and return (valid_records, invalid_paths)."""
    output_dir = Path(output_dir)
    records = []
    invalid = []
    seen = set()
    for path in sorted((output_dir / "samples").glob("L*/sample_*.json")):
        try:
            with path.open(encoding="utf-8") as handle:
                record = json.load(handle)
            _validate_record(record, expected_config)
            key = (int(record["L"]), int(record["sample_index"]))
            if key in seen:
                raise ValueError("duplicate sample record")
            seen.add(key)
            records.append(record)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            invalid.append(path)
    records.sort(key=lambda item: (int(item["L"]), int(item["sample_index"])))
    return records, invalid


def _counts_from_records(records, sample_counts):
    counts = {int(L): 0 for L in sample_counts}
    for record in records:
        counts[int(record["L"])] += 1
    return counts


def _progress_line(records, sample_counts, elapsed):
    actual = _counts_from_records(records, sample_counts)
    counts_text = " ".join(
        f"L{L}={actual[L]}/{int(sample_counts[L])}" for L in sorted(actual)
    )
    estimates = []
    for L in sorted(actual):
        values = [
            float(record["free_energy"])
            for record in records
            if int(record["L"]) == L
        ]
        if values:
            estimates.append(f"f{L}={np.mean(values):.8f}")
    return (
        f"elapsed={elapsed:.1f}s completed={len(records)}/"
        f"{sum(sample_counts.values())} {counts_text} {' '.join(estimates)}"
    )


def run_production(
    sample_counts,
    p,
    base_seed,
    burn_in,
    retained_rows,
    block_length,
    workers,
    soft_deadline_seconds,
    bootstrap_samples,
    output_dir,
    strip_runner=run_fixed_count_strip,
    executor_factory=ProcessPoolExecutor,
):
    """Run, resume, and analyze a bounded fixed-count sample ensemble."""
    sample_counts = _normalized_sample_counts(sample_counts)
    p = float(p)
    burn_in = int(burn_in)
    retained_rows = int(retained_rows)
    block_length = int(block_length)
    workers = int(workers)
    soft_deadline_seconds = float(soft_deadline_seconds)
    bootstrap_samples = int(bootstrap_samples)
    output_dir = Path(output_dir)
    if not 0.0 < p < 0.5:
        raise ValueError("p must satisfy 0 < p < 0.5")
    if burn_in < 0 or retained_rows <= 0 or block_length <= 0:
        raise ValueError("row counts must be positive and burn_in nonnegative")
    if retained_rows % block_length:
        raise ValueError("retained_rows must be a multiple of block_length")
    if workers <= 0 or soft_deadline_seconds < 0.0 or bootstrap_samples < 2:
        raise ValueError("workers, deadline, or bootstrap count is invalid")

    expected = {
        "p": p,
        "burn_in": burn_in,
        "retained_rows": retained_rows,
        "block_length": block_length,
        "sample_counts": sample_counts,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    records, invalid_paths = load_valid_records(output_dir, expected)
    for invalid_path in invalid_paths:
        print(f"invalid sample record: {invalid_path}", flush=True)
    completed = {(int(item["L"]), int(item["sample_index"])) for item in records}
    tasks = build_tasks(sample_counts, completed)
    pending = iter(tasks)
    started = time.monotonic()
    futures = {}
    deadline_reached = False

    def submit_one(executor):
        nonlocal deadline_reached
        elapsed = time.monotonic() - started
        if elapsed >= soft_deadline_seconds:
            deadline_reached = bool(tasks)
            return False
        try:
            task = next(pending)
        except StopIteration:
            return False
        seed = sample_seed(base_seed, task["L"], task["sample_index"])
        future = executor.submit(
            strip_runner,
            L=task["L"],
            p=p,
            seed=seed,
            burn_in=burn_in,
            retained_rows=retained_rows,
            block_length=block_length,
            progress=False,
        )
        futures[future] = (task, seed)
        return True

    with executor_factory(max_workers=workers) as executor:
        while len(futures) < workers and submit_one(executor):
            pass
        while futures:
            done, _ = wait(tuple(futures), return_when=FIRST_COMPLETED)
            for future in done:
                task, seed = futures.pop(future)
                record = dict(future.result())
                record["sample_index"] = int(task["sample_index"])
                record["seed"] = int(seed)
                _validate_record(record, expected)
                write_sample_record_atomic(record, output_dir)
                records.append(_jsonable(record))
                records.sort(
                    key=lambda item: (int(item["L"]), int(item["sample_index"]))
                )
                print(
                    _progress_line(records, sample_counts, time.monotonic() - started),
                    flush=True,
                )
            while len(futures) < workers and submit_one(executor):
                pass

    elapsed = time.monotonic() - started
    records, invalid_paths = load_valid_records(output_dir, expected)
    actual_counts = _counts_from_records(records, sample_counts)
    requested_complete = all(
        actual_counts[L] == sample_counts[L] for L in sample_counts
    )
    run_config = {
        "sizes": sorted(sample_counts),
        "sample_counts": sample_counts,
        "actual_counts": actual_counts,
        "p": p,
        "base_seed": int(base_seed),
        "burn_in": burn_in,
        "retained_rows": retained_rows,
        "block_length": block_length,
        "workers": workers,
        "soft_deadline_seconds": soft_deadline_seconds,
        "bootstrap_samples": bootstrap_samples,
        "elapsed_seconds": elapsed,
        "deadline_reached": bool(deadline_reached and not requested_complete),
        "requested_complete": requested_complete,
        "preliminary": True,
        "invalid_records": [str(path) for path in invalid_paths],
    }

    per_width = _counts_from_records(records, sample_counts)
    analysable = len(per_width) >= 4 and all(count >= 2 for count in per_width.values())
    if analysable:
        width_results = aggregate_sample_records(records)
        summary = central_charge_ensemble_summary(
            width_results, bootstrap_samples=bootstrap_samples, seed=base_seed + 20000
        )
        write_ensemble_artifacts(
            records, width_results, summary, run_config, output_dir
        )
        reported = summary["reported"]
        print(
            f"c_eff={reported['central_charge']:.8f} +/- "
            f"{reported['bootstrap_se']:.3e} (bootstrap)",
            flush=True,
        )
    else:
        with (output_dir / "run_config.json").open("w", encoding="utf-8") as handle:
            json.dump(_jsonable(run_config), handle, indent=2, sort_keys=True)
            handle.write("\n")
    return run_config


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=list(DEFAULT_SAMPLE_COUNTS))
    parser.add_argument(
        "--sample-counts",
        nargs="+",
        type=int,
        default=list(DEFAULT_SAMPLE_COUNTS.values()),
    )
    parser.add_argument("--p", type=float, default=0.1092212)
    parser.add_argument("--seed", type=int, default=1221092212)
    parser.add_argument("--burn-in", type=int, default=1000)
    parser.add_argument("--retained-rows", type=int, default=100000)
    parser.add_argument("--block-length", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--soft-deadline-seconds", type=float, default=6600.0)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/random_bond_ising_nishimori_two_hour"),
    )
    return parser


def main(argv=None):
    arguments = build_parser().parse_args(argv)
    if len(arguments.sizes) != len(arguments.sample_counts):
        raise ValueError("--sizes and --sample-counts must have equal lengths")
    run_production(
        sample_counts=dict(zip(arguments.sizes, arguments.sample_counts)),
        p=arguments.p,
        base_seed=arguments.seed,
        burn_in=arguments.burn_in,
        retained_rows=arguments.retained_rows,
        block_length=arguments.block_length,
        workers=arguments.workers,
        soft_deadline_seconds=arguments.soft_deadline_seconds,
        bootstrap_samples=arguments.bootstrap_samples,
        output_dir=arguments.output_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
