#!/usr/bin/env python3
"""Resumable allocation and bounded execution for Haar-MIPT trajectories."""

import os

for _thread_variable in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_thread_variable] = "1"

import json
import math
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

import numpy as np

try:
    from haar_mipt_transfer import run_trajectory
except ImportError:  # imported from the repository root during tests
    from scripts.haar_mipt_transfer import run_trajectory


FAMILY_CODES = {"global_haar": 0, "product": 1}
_RECORD_FIELDS = {
    "schema_version",
    "L",
    "p",
    "initial_family",
    "sample_index",
    "seed",
    "burn_in_steps",
    "record_steps",
    "record_cost",
    "cumulative_record_cost",
    "runtime_seconds",
    "gate_count",
    "attempted_measurements",
    "outcome_counts",
}


def trajectory_seed(base_seed, L, family, sample_index):
    """Return the deterministic seed for one width/family/sample identity."""
    try:
        family_code = FAMILY_CODES[str(family)]
    except KeyError as error:
        raise ValueError("unknown initial-state family") from error
    sequence = np.random.SeedSequence(
        [int(base_seed), int(L), family_code, int(sample_index)]
    )
    return int(sequence.generate_state(1, dtype=np.uint64)[0])


def record_path(output_dir, L, family, sample_index):
    """Return the canonical path for one trajectory identity."""
    return (
        Path(output_dir)
        / "records"
        / f"L{int(L)}"
        / str(family)
        / f"trajectory_{int(sample_index):05d}.json"
    )


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


def _write_json_atomic(value, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(_jsonable(value), handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)
    return path


def write_trajectory_record_atomic(record, output_dir):
    """Atomically persist one trajectory record in its canonical directory."""
    path = record_path(
        output_dir,
        record["L"],
        record["initial_family"],
        record["sample_index"],
    )
    return _write_json_atomic(record, path)


def _normalized_sample_counts(sample_counts):
    normalized = {}
    for raw_L, raw_count in sample_counts.items():
        L, count = int(raw_L), int(raw_count)
        if L in normalized:
            raise ValueError("duplicate width after JSON key normalization")
        normalized[L] = count
    return normalized


def _validate_config(config):
    required = {
        "schema_version", "stage", "sizes", "sample_counts", "families",
        "p", "base_seed", "burn_in_multiplier", "record_multiplier",
        "workers", "soft_deadline_seconds",
    }
    if not required.issubset(config):
        raise ValueError("production config is missing required fields")
    counts = _normalized_sample_counts(config["sample_counts"])
    if int(config["schema_version"]) != 1:
        raise ValueError("unsupported production schema")
    if str(config["stage"]) not in {"pilot", "production"}:
        raise ValueError("stage must be pilot or production")
    if sorted(map(int, config["sizes"])) != sorted(counts):
        raise ValueError("sizes and sample_counts disagree")
    if list(config["families"]) != list(FAMILY_CODES):
        raise ValueError("both initial-state families are required")
    if not counts or any(L < 2 or L % 2 or count <= 0
                         for L, count in counts.items()):
        raise ValueError("sample counts require positive counts at even widths")
    if not 0.0 <= float(config["p"]) <= 1.0:
        raise ValueError("p must be a probability")
    if int(config["burn_in_multiplier"]) != 4:
        raise ValueError("burn-in multiplier must be four")
    if int(config["record_multiplier"]) != 24:
        raise ValueError("record multiplier must be twenty-four")
    if int(config["workers"]) <= 0:
        raise ValueError("workers must be positive")
    deadline = float(config["soft_deadline_seconds"])
    if not math.isfinite(deadline) or deadline < 0.0:
        raise ValueError("soft deadline must be finite and nonnegative")
    normalized = dict(config)
    normalized["sample_counts"] = counts
    normalized["sizes"] = sorted(counts)
    normalized["base_seed"] = int(config["base_seed"])
    normalized["p"] = float(config["p"])
    normalized["workers"] = int(config["workers"])
    normalized["soft_deadline_seconds"] = deadline
    return normalized


def _as_exact_int(value, name):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be an integer")
    converted = int(value)
    if isinstance(value, (float, np.floating)) and not value.is_integer():
        raise ValueError(f"{name} must be an integer")
    if isinstance(value, str) or converted != value:
        raise ValueError(f"{name} must be an integer")
    return converted


def _validate_record(record, expected_config):
    if not isinstance(record, dict) or set(record) != _RECORD_FIELDS:
        raise ValueError("trajectory record has the wrong schema")
    config = _validate_config(expected_config)
    if _as_exact_int(record["schema_version"], "schema_version") != 1:
        raise ValueError("trajectory record has the wrong schema version")
    L = _as_exact_int(record["L"], "L")
    family = str(record["initial_family"])
    index = _as_exact_int(record["sample_index"], "sample_index")
    if L not in config["sample_counts"]:
        raise ValueError("trajectory width is outside the allocation")
    if family not in FAMILY_CODES:
        raise ValueError("trajectory family is outside the allocation")
    if not 0 <= index < config["sample_counts"][L]:
        raise ValueError("trajectory sample index is outside the allocation")
    if not math.isclose(float(record["p"]), config["p"],
                        rel_tol=0.0, abs_tol=1e-15):
        raise ValueError("trajectory uses a different measurement probability")
    expected_seed = trajectory_seed(config["base_seed"], L, family, index)
    if _as_exact_int(record["seed"], "seed") != expected_seed:
        raise ValueError("trajectory has the wrong deterministic seed")
    if _as_exact_int(record["burn_in_steps"], "burn_in_steps") != 4 * L:
        raise ValueError("trajectory has the wrong burn-in length")
    record_steps = _as_exact_int(record["record_steps"], "record_steps")
    if record_steps != 24 * L:
        raise ValueError("trajectory has the wrong record length")
    cost = float(record["record_cost"])
    runtime = float(record["runtime_seconds"])
    if not math.isfinite(cost) or cost < 0.0:
        raise ValueError("trajectory has invalid record cost")
    if not math.isfinite(runtime) or runtime < 0.0:
        raise ValueError("trajectory has invalid runtime")
    cumulative = np.asarray(record["cumulative_record_cost"], dtype=float)
    if cumulative.shape != (record_steps,):
        raise ValueError("trajectory has the wrong cumulative-cost length")
    if (not np.all(np.isfinite(cumulative)) or np.any(cumulative < 0.0)
            or np.any(np.diff(cumulative) < -1e-12)):
        raise ValueError("trajectory cumulative cost is not finite and monotone")
    if not math.isclose(float(cumulative[-1]), cost,
                        rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError("trajectory cumulative cost does not end at record cost")
    if _as_exact_int(record["gate_count"], "gate_count") != 14 * L**2:
        raise ValueError("trajectory has the wrong gate count")
    attempted = _as_exact_int(
        record["attempted_measurements"], "attempted_measurements"
    )
    outcomes = record["outcome_counts"]
    if not isinstance(outcomes, list) or len(outcomes) != 2:
        raise ValueError("trajectory has invalid outcome counts")
    outcome_counts = [_as_exact_int(value, "outcome count") for value in outcomes]
    if attempted < 0 or any(value < 0 for value in outcome_counts):
        raise ValueError("trajectory has negative measurement counts")
    if sum(outcome_counts) != attempted:
        raise ValueError("outcome counts do not sum to attempted measurements")


def load_valid_records(output_dir, expected_config):
    """Load valid resumable records while isolating every invalid file."""
    output_dir = Path(output_dir)
    config = _validate_config(expected_config)
    records, invalid, seen = [], [], set()
    for path in sorted((output_dir / "records").glob("L*/*/trajectory_*.json")):
        try:
            with path.open(encoding="utf-8") as handle:
                record = json.load(handle)
            _validate_record(record, config)
            identity = (
                int(record["L"]),
                str(record["initial_family"]),
                int(record["sample_index"]),
            )
            if identity in seen:
                raise ValueError("duplicate trajectory identity")
            if path != record_path(output_dir, *identity):
                raise ValueError("trajectory path does not match record identity")
            seen.add(identity)
            records.append(record)
        except (OSError, ValueError, TypeError, KeyError,
                OverflowError, json.JSONDecodeError):
            invalid.append(path)
    records.sort(key=lambda item: (
        int(item["L"]), str(item["initial_family"]), int(item["sample_index"])
    ))
    return records, invalid


def build_tasks(sample_counts, completed):
    """Build missing tasks in balanced, large-width-first order."""
    counts = _normalized_sample_counts(sample_counts)
    if not counts or any(L < 2 or L % 2 or count <= 0
                         for L, count in counts.items()):
        raise ValueError("sample counts require positive counts at even widths")
    completed = {
        (int(L), str(family), int(index)) for L, family, index in completed
    }
    completion = {}
    for L, requested in counts.items():
        for family in FAMILY_CODES:
            done = sum((L, family, index) in completed
                       for index in range(requested))
            completion[L, family] = done / requested
    tasks = []
    for L, requested in counts.items():
        for family in FAMILY_CODES:
            for index in range(requested):
                if (L, family, index) not in completed:
                    tasks.append({
                        "L": L,
                        "family": family,
                        "sample_index": index,
                        "requested_samples": requested,
                    })
    tasks.sort(key=lambda task: (
        completion[task["L"], task["family"]],
        -task["L"],
        task["family"],
        task["sample_index"],
    ))
    return tasks


def pilot_allocation(records, target_se=2e-4, minimum=512,
                     batch=64, cap=25000):
    """Return equal-family production totals estimated from pilot variance."""
    target_se = float(target_se)
    minimum, batch, cap = int(minimum), int(batch), int(cap)
    if target_se <= 0.0 or minimum <= 0 or batch <= 0 or cap <= 0:
        raise ValueError("allocation parameters must be positive")
    result = {}
    for L in sorted({int(record["L"]) for record in records}):
        stdevs = []
        for family in FAMILY_CODES:
            values = [
                float(record["record_cost"])
                / (L * int(record["record_steps"]))
                for record in records
                if int(record["L"]) == L
                and str(record["initial_family"]) == family
            ]
            if len(values) < 2:
                raise ValueError("pilot needs both family variances")
            stdevs.append(float(np.std(values, ddof=1)))
        effective = 0.5 * float(np.hypot(*stdevs))
        uncapped = batch * math.ceil(
            max(minimum, (effective / target_se) ** 2) / batch
        )
        requested = min(cap, int(uncapped))
        result[L] = {
            "requested_per_family": requested,
            "effective_stdev": effective,
            "projected_se": effective / math.sqrt(requested),
            "cap_limited": bool(uncapped > cap),
        }
    return result


def project_runtime(records, requested_counts, workers):
    """Project only the missing runtime, with family-specific pilot means."""
    requested_counts = _normalized_sample_counts(requested_counts)
    workers = int(workers)
    if workers <= 0:
        raise ValueError("workers must be positive")
    cpu_seconds, missing_total = 0.0, 0
    for L, requested in requested_counts.items():
        for family in FAMILY_CODES:
            group = [record for record in records
                     if int(record["L"]) == L
                     and str(record["initial_family"]) == family]
            missing = max(0, requested - len(group))
            if missing:
                runtimes = [float(record["runtime_seconds"]) for record in group]
                if not runtimes or any(
                    not math.isfinite(value) or value < 0.0 for value in runtimes
                ):
                    raise ValueError(
                        f"runtime projection needs pilot records for L={L} {family}"
                    )
                cpu_seconds += missing * float(np.mean(runtimes))
                missing_total += missing
    wall_seconds = 1.20 * cpu_seconds / workers
    memory_mib = workers * 12
    route = (
        "local"
        if wall_seconds <= 600.0 and memory_mib < 16 * 1024
        else "remote"
    )
    return {
        "missing_trajectories": missing_total,
        "projected_cpu_seconds": cpu_seconds,
        "projected_wall_seconds": wall_seconds,
        "worker_memory_mib": memory_mib,
        "route": route,
    }


def _actual_counts(records, sample_counts):
    counts = {
        f"L{L}/{family}": 0
        for L in sorted(sample_counts)
        for family in FAMILY_CODES
    }
    for record in records:
        counts[f"L{int(record['L'])}/{record['initial_family']}"] += 1
    return counts


def _width_estimate(records, L):
    groups = []
    for family in FAMILY_CODES:
        values = [
            float(record["record_cost"])
            / (L * int(record["record_steps"]))
            for record in records
            if int(record["L"]) == L
            and str(record["initial_family"]) == family
        ]
        if not values:
            return None, None
        groups.append(values)
    estimate = 0.5 * sum(float(np.mean(values)) for values in groups)
    if any(len(values) < 2 for values in groups):
        return estimate, None
    standard_error = 0.5 * math.sqrt(sum(
        float(np.var(values, ddof=1)) / len(values) for values in groups
    ))
    return estimate, standard_error


def _project_remaining(records, sample_counts, workers):
    all_runtimes = [float(record["runtime_seconds"]) for record in records]
    fallback = float(np.mean(all_runtimes)) if all_runtimes else float("nan")
    cpu_seconds = 0.0
    for L, requested in sample_counts.items():
        for family in FAMILY_CODES:
            group = [float(record["runtime_seconds"]) for record in records
                     if int(record["L"]) == L
                     and str(record["initial_family"]) == family]
            missing = max(0, requested - len(group))
            mean = float(np.mean(group)) if group else fallback
            if missing and math.isfinite(mean):
                cpu_seconds += missing * mean
    return 1.20 * cpu_seconds / workers if all_runtimes else float("nan")


def _progress_line(records, sample_counts, elapsed, workers):
    actual = _actual_counts(records, sample_counts)
    count_text = " ".join(
        f"{key}={value}/{sample_counts[int(key.split('/')[0][1:])]}"
        for key, value in actual.items()
    )
    estimates = []
    for L in sorted(sample_counts):
        estimate, standard_error = _width_estimate(records, L)
        if estimate is not None:
            se_text = "undefined" if standard_error is None else f"{standard_error:.3e}"
            estimates.append(f"tilde_f_L{L}={estimate:.8f} se={se_text}")
    remaining = _project_remaining(records, sample_counts, workers)
    remaining_text = "undefined" if not math.isfinite(remaining) else f"{remaining:.1f}s"
    return (
        f"elapsed={elapsed:.1f}s completed={len(records)}/"
        f"{2 * sum(sample_counts.values())} {count_text} "
        f"{' '.join(estimates)} projected_remaining={remaining_text}"
    )


def run_ensemble(config, output_dir, approved=False,
                 trajectory_runner=run_trajectory,
                 executor_factory=ProcessPoolExecutor):
    """Resume and run a bounded pilot or explicitly approved production stage."""
    if config["stage"] == "production" and not approved:
        raise PermissionError(
            "production requires --approved after projection review"
        )
    config = _validate_config(config)
    sample_counts = config["sample_counts"]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    records, invalid = load_valid_records(output_dir, config)
    for path in invalid:
        print(f"invalid trajectory record: {path}", flush=True)
    completed = {
        (int(record["L"]), str(record["initial_family"]),
         int(record["sample_index"]))
        for record in records
    }
    pending = deque(build_tasks(sample_counts, completed))
    started = time.monotonic()
    futures = {}
    deadline_reached = False

    def submit_one(executor):
        nonlocal deadline_reached
        if not pending:
            return False
        if time.monotonic() - started >= config["soft_deadline_seconds"]:
            deadline_reached = True
            return False
        task = pending.popleft()
        seed = trajectory_seed(
            config["base_seed"], task["L"], task["family"],
            task["sample_index"]
        )
        future = executor.submit(
            trajectory_runner,
            L=task["L"],
            p=config["p"],
            seed=seed,
            initial_family=task["family"],
            burn_in_steps=4 * task["L"],
            record_steps=24 * task["L"],
        )
        futures[future] = (task, seed)
        return True

    with executor_factory(max_workers=config["workers"]) as executor:
        while len(futures) < config["workers"] and submit_one(executor):
            pass
        while futures:
            done, _ = wait(tuple(futures), return_when=FIRST_COMPLETED)
            for future in done:
                task, seed = futures.pop(future)
                record = dict(future.result())
                record["sample_index"] = int(task["sample_index"])
                record["seed"] = int(seed)
                _validate_record(record, config)
                write_trajectory_record_atomic(record, output_dir)
                records.append(_jsonable(record))
                records.sort(key=lambda item: (
                    int(item["L"]), str(item["initial_family"]),
                    int(item["sample_index"])
                ))
                print(_progress_line(
                    records, sample_counts, time.monotonic() - started,
                    config["workers"]
                ), flush=True)
            while len(futures) < config["workers"] and submit_one(executor):
                pass

    elapsed = time.monotonic() - started
    records, final_invalid = load_valid_records(output_dir, config)
    actual_counts = _actual_counts(records, sample_counts)
    requested_complete = all(
        actual_counts[f"L{L}/{family}"] == requested
        for L, requested in sample_counts.items()
        for family in FAMILY_CODES
    )
    checkpoint = {
        "actual_counts": actual_counts,
        "requested_complete": requested_complete,
        "deadline_reached": bool(deadline_reached and not requested_complete),
        "elapsed_seconds": elapsed,
        "invalid_records": [str(path) for path in final_invalid],
    }
    _write_json_atomic(checkpoint, output_dir / "run_checkpoint.json")
    return checkpoint
