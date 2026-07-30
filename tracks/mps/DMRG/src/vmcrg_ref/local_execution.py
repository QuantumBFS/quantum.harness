"""Bounded local execution helpers for the Issue #28 compute deviation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping, Sequence

from .artifacts import atomic_write_json, sha256_file


_TRACK_ROOT = Path(__file__).resolve().parents[2]


def resolve_worker_limit(requested: int | None, tasks: int) -> int:
    """Resolve one explicit worker cap without exceeding available tasks."""
    task_count = int(tasks)
    if task_count <= 0:
        raise ValueError("task count must be positive")
    value = max(1, os.cpu_count() or 1) if requested is None else int(requested)
    if value <= 0:
        raise ValueError("worker limit must be positive")
    return min(value, task_count)


def _linux_memory_bytes() -> tuple[int, int]:
    values: dict[str, int] = {}
    source = Path("/proc/meminfo")
    if source.is_file():
        for line in source.read_text(encoding="ascii").splitlines():
            name, separator, remainder = line.partition(":")
            if not separator:
                continue
            fields = remainder.split()
            if fields and fields[0].isdigit():
                multiplier = 1024 if len(fields) > 1 and fields[1] == "kB" else 1
                values[name] = int(fields[0]) * multiplier
    total = int(values.get("MemTotal", 0))
    available = int(values.get("MemAvailable", 0))
    if total > 0 and available > 0:
        return total, available
    page_size = int(os.sysconf("SC_PAGE_SIZE"))
    total = int(os.sysconf("SC_PHYS_PAGES")) * page_size
    available = int(os.sysconf("SC_AVPHYS_PAGES")) * page_size
    return total, available


def available_memory_bytes() -> int:
    """Return the currently available host memory in bytes."""
    return _linux_memory_bytes()[1]


def local_host_provenance(
    *,
    workers_per_bundle: int,
    max_parallel_bundles: int,
) -> dict[str, Any]:
    """Capture local hardware and the declared Issue #28 worker budget."""
    workers = resolve_worker_limit(workers_per_bundle, workers_per_bundle)
    parallel = int(max_parallel_bundles)
    if parallel <= 0:
        raise ValueError("maximum parallel bundle count must be positive")
    total, available = _linux_memory_bytes()
    affinity = (
        sorted(int(value) for value in os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else list(range(max(1, os.cpu_count() or 1)))
    )
    return {
        "node": platform.node() or "unknown-local-host",
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "logical_cpus": max(1, os.cpu_count() or 1),
        "cpu_affinity": affinity,
        "memory_total_bytes": total,
        "memory_available_bytes": available,
        "workers_per_bundle": workers,
        "max_parallel_bundles": parallel,
    }


def _write_coordinator_state(path: Path, state: Mapping[str, Any]) -> None:
    atomic_write_json(path, dict(state))


def _read_coordinator_state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("local coordinator state is invalid") from error
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("unsupported local coordinator state")
    return value


def run_bounded_process_schedule(
    commands: Mapping[str, Sequence[str]],
    *,
    output: str | Path,
    max_parallel: int,
    minimum_memory_for_parallel_bytes: int,
    resume: bool,
    environments: Mapping[str, Mapping[str, str]] | None = None,
    cwd: str | Path | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run uniquely named child commands with atomic state and fail-stop semantics."""
    ordered = [str(name) for name in commands]
    if not ordered or len(ordered) != len(set(ordered)):
        raise ValueError("local process schedule requires unique command names")
    parallel = int(max_parallel)
    minimum_memory = int(minimum_memory_for_parallel_bytes)
    if parallel <= 0:
        raise ValueError("maximum parallel process count must be positive")
    if minimum_memory <= 0:
        raise ValueError("parallel memory floor must be positive")
    destination = Path(output)
    state_path = destination / "local_coordinator.json"
    if destination.exists() and not resume and any(destination.iterdir()):
        raise FileExistsError(f"refusing to overwrite local coordinator output: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    logs = destination / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    if resume and state_path.is_file():
        state = _read_coordinator_state(state_path)
        if state.get("command_ids") != ordered:
            raise ValueError("local coordinator command set changed on resume")
        completed = [str(item) for item in state.get("completed", [])]
        attempts = {str(key): int(value) for key, value in dict(state.get("attempts", {})).items()}
        dispatch_order = [str(item) for item in state.get("dispatch_order", [])]
        failures = [str(item) for item in state.get("failed", [])]
    elif resume and destination.exists() and any(destination.iterdir()):
        raise ValueError("local coordinator resume state is missing")
    else:
        completed = []
        attempts = {}
        dispatch_order = []
        failures = []
        state = {
            "schema_version": 1,
            "command_ids": ordered,
            "completed": [],
            "failed": [],
            "aborted": [],
            "not_launched": ordered.copy(),
            "attempts": {},
            "dispatch_order": [],
            "maximum_observed_parallel": 0,
            "memory_downgrade_count": 0,
            "classification": "RUNNING",
        }
    completed_set = set(completed)
    pending = [name for name in ordered if name not in completed_set]
    environments = {} if environments is None else environments
    process_records: dict[str, dict[str, Any]] = {}
    running: dict[str, tuple[subprocess.Popen[bytes], Any, float]] = {}
    aborted: list[str] = [str(item) for item in state.get("aborted", [])]
    stop_launch = bool(failures)
    maximum_observed = int(state.get("maximum_observed_parallel", 0))
    memory_downgrades = int(state.get("memory_downgrade_count", 0))
    _write_coordinator_state(
        state_path,
        {
            **state,
            "metadata": dict(metadata or state.get("metadata", {})),
            "command_ids": ordered,
            "completed": completed,
            "failed": failures,
            "aborted": aborted,
            "not_launched": pending,
            "attempts": attempts,
            "dispatch_order": dispatch_order,
            "maximum_observed_parallel": maximum_observed,
            "memory_downgrade_count": memory_downgrades,
            "classification": "RUNNING" if not stop_launch else "PROTOCOL_FAILURE",
        },
    )

    while pending or running:
        if stop_launch and not running:
            break
        changed = False
        while pending and len(running) < parallel and not stop_launch:
            if running and available_memory_bytes() < minimum_memory:
                memory_downgrades += 1
                break
            name = pending.pop(0)
            log_path = logs / f"{name}.log"
            handle = log_path.open("ab")
            env = os.environ.copy()
            env.update({str(key): str(value) for key, value in environments.get(name, {}).items()})
            process = subprocess.Popen(
                [str(value) for value in commands[name]],
                stdout=handle,
                stderr=subprocess.STDOUT,
                cwd=None if cwd is None else str(cwd),
                env=env,
            )
            started = time.time()
            running[name] = (process, handle, started)
            attempts[name] = int(attempts.get(name, 0)) + 1
            dispatch_order.append(name)
            maximum_observed = max(maximum_observed, len(running))
            process_records[name] = {
                "pid": int(process.pid),
                "started_at": started,
                "log": str(log_path),
            }
            changed = True
            _write_coordinator_state(
                state_path,
                {
                    **state,
                    "metadata": dict(metadata or state.get("metadata", {})),
                    "command_ids": ordered,
                    "completed": completed,
                    "failed": failures,
                    "aborted": aborted,
                    "not_launched": pending,
                    "attempts": attempts,
                    "dispatch_order": dispatch_order,
                    "maximum_observed_parallel": maximum_observed,
                    "memory_downgrade_count": memory_downgrades,
                    "processes": process_records,
                    "classification": "RUNNING",
                },
            )
        for name in list(running):
            process, handle, started = running[name]
            return_code = process.poll()
            if return_code is None:
                continue
            handle.close()
            del running[name]
            record = process_records.setdefault(name, {})
            record.update(
                {
                    "return_code": int(return_code),
                    "finished_at": time.time(),
                    "elapsed_seconds": time.time() - started,
                }
            )
            if return_code == 0:
                completed.append(name)
            else:
                failures.append(name)
                stop_launch = True
                for sibling_name, (sibling, _, _) in list(running.items()):
                    if sibling.poll() is None:
                        sibling.terminate()
                changed = True
            changed = True
        if changed:
            ordered_completed = [name for name in ordered if name in set(completed)]
            ordered_failed = [name for name in ordered if name in set(failures)]
            ordered_aborted = [name for name in ordered if name in set(aborted)]
            _write_coordinator_state(
                state_path,
                {
                    **state,
                    "metadata": dict(metadata or state.get("metadata", {})),
                    "command_ids": ordered,
                    "completed": ordered_completed,
                    "failed": ordered_failed,
                    "aborted": ordered_aborted,
                    "not_launched": pending,
                    "attempts": attempts,
                    "dispatch_order": dispatch_order,
                    "maximum_observed_parallel": maximum_observed,
                    "memory_downgrade_count": memory_downgrades,
                    "processes": process_records,
                    "classification": "RUNNING",
                },
            )
        if not changed and running:
            time.sleep(0.05)
    completed = [name for name in ordered if name in set(completed)]
    failures = [name for name in ordered if name in set(failures)]
    result = {
        "schema_version": 1,
        "command_ids": ordered,
        "completed": completed,
        "failed": failures,
        "aborted": [name for name in ordered if name in set(aborted)],
        "not_launched": [name for name in ordered if name not in set(completed + failures + aborted)],
        "attempts": attempts,
        "dispatch_order": dispatch_order,
        "maximum_observed_parallel": maximum_observed,
        "memory_downgrade_count": memory_downgrades,
        "processes": process_records,
        "classification": "PROTOCOL_FAILURE" if failures or aborted else "RUN_COMPLETE",
    }
    _write_coordinator_state(
        state_path,
        {
            **result,
            "metadata": dict(metadata or state.get("metadata", {})),
        },
    )
    return result


def run_local_formal(
    protocol: str | Path,
    output: str | Path,
    *,
    workers_per_bundle: int = 8,
    max_parallel_bundles: int = 2,
    minimum_available_gib: float = 12.0,
    resume: bool = False,
    allow_large_local: bool = False,
) -> dict[str, Any]:
    """Run the frozen five formal bundles locally in bounded subprocess waves."""
    if not allow_large_local:
        raise ValueError("large local N4 requires allow_large_local=True")
    workers = int(workers_per_bundle)
    if workers <= 0 or workers > 8:
        raise ValueError("local N4 workers_per_bundle must lie in [1, 8]")
    parallel = int(max_parallel_bundles)
    if parallel <= 0 or parallel > 2:
        raise ValueError("local N4 maximum concurrency must lie in [1, 2]")
    minimum_gib = float(minimum_available_gib)
    if minimum_gib <= 0.0:
        raise ValueError("local N4 memory floor must be positive")
    protocol_path = Path(protocol).resolve()
    destination = Path(output).resolve()
    from .formal_protocol import load_formal_execution_protocol

    loaded_protocol, execution = load_formal_execution_protocol(protocol_path)
    frozen_resources = dict(execution["resources"])
    frozen_workers = frozen_resources.get("workers_per_bundle")
    if frozen_workers is not None and int(frozen_workers) != workers:
        raise ValueError("local N4 worker limit differs from frozen formal protocol")
    bundle_ids = [bundle.bundle_id for bundle in loaded_protocol.formal_bundles]
    if bundle_ids != [f"formal-{index}" for index in range(1, 6)]:
        raise ValueError("formal protocol seed bundle order is not formal-1 through formal-5")
    script = _TRACK_ROOT / "scripts" / "issue28_formal.py"
    commands: dict[str, list[str]] = {}
    environments: dict[str, dict[str, str]] = {}
    cache_root = Path(tempfile.gettempdir()) / f"issue28-numba-{destination.name}"
    for bundle_id in bundle_ids:
        bundle_output = destination / bundle_id
        commands[bundle_id] = [
            sys.executable,
            "-u",
            str(script),
            "--protocol",
            str(protocol_path),
            "--bundle",
            bundle_id,
            "--output",
            str(bundle_output),
            "--backend",
            "local",
            "--workers",
            str(workers),
            "--allow-large-local",
        ]
        if resume:
            commands[bundle_id].append("--resume")
        environments[bundle_id] = {
            "PYTHONHASHSEED": "0",
            "OMP_NUM_THREADS": str(workers),
            "MKL_NUM_THREADS": str(workers),
            "OPENBLAS_NUM_THREADS": str(workers),
            "NUMBA_NUM_THREADS": str(workers),
            "NUMBA_CACHE_DIR": str(cache_root / bundle_id),
        }
    host = local_host_provenance(
        workers_per_bundle=workers,
        max_parallel_bundles=parallel,
    )
    metadata = {
        "schema_version": 1,
        "stage": "N4",
        "execution_policy": "LOCAL_COMPUTE_DEVIATION",
        "backend": "local",
        "protocol_sha256": sha256_file(protocol_path),
        "workers_per_bundle": workers,
        "max_parallel_bundles": parallel,
        "minimum_available_gib": minimum_gib,
        "host": host,
    }
    schedule = run_bounded_process_schedule(
        commands,
        output=destination,
        max_parallel=parallel,
        minimum_memory_for_parallel_bytes=int(minimum_gib * 1024**3),
        resume=resume,
        environments=environments,
        cwd=_TRACK_ROOT,
        metadata=metadata,
    )
    if schedule["classification"] == "PROTOCOL_FAILURE":
        return {**schedule, "execution_policy": "LOCAL_COMPUTE_DEVIATION"}
    from .formal import classify_formal_root

    try:
        formal = classify_formal_root(destination, loaded_protocol)
    except (FileNotFoundError, OSError, ValueError) as error:
        formal = {
            "classification": "PROTOCOL_FAILURE",
            "reason": f"LOCAL_FORMAL_VERIFICATION_FAILED:{error}",
            "missing_bundles": [],
            "extra_bundles": [],
            "replacement_seed_allowed": False,
            "bundles": [],
            "unidentifiable_bundles": [],
        }
    result = {
        **schedule,
        "execution_policy": "LOCAL_COMPUTE_DEVIATION",
        "formal": formal,
        "classification": formal["classification"],
        "protocol_sha256": metadata["protocol_sha256"],
        "host": host,
    }
    atomic_write_json(destination / "local_run.json", result)
    return result
