#!/usr/bin/env python3
"""Prepare or run the selected-ladder Stage 6 matrix on the local CPU."""

from __future__ import annotations

import argparse
from collections import deque
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence


TRACK_ROOT = Path(__file__).resolve().parents[1]
SRC = TRACK_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spinglass3d.science_pilot import (  # noqa: E402
    PILOT_NEEDS_EXTENSION,
    PILOT_PASS,
)
from spinglass3d.stage6 import (  # noqa: E402
    LOCAL_EXECUTION_POLICY,
    MEASUREMENT_CADENCE,
    load_selected_science_cell,
    prepare_selected_science_run,
)
from vmcrg_ref.artifacts import atomic_write_json, sha256_file  # noqa: E402
from vmcrg_ref.local_execution import (  # noqa: E402
    available_memory_bytes,
    local_host_provenance,
)


def _read_json(path: Path, name: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{name} is not readable JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{name} must contain an object")
    return value


def _artifact_inventory(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }


def science_cell_state(spec: object, output: str | Path) -> dict[str, object]:
    """Classify one local cell from immutable output or resumable work."""

    from spinglass3d.science_pilot import SciencePilotSpec

    if not isinstance(spec, SciencePilotSpec):
        raise TypeError("spec must be SciencePilotSpec")
    destination = Path(output)
    work = destination.parent / f".{destination.name}.science-work"
    if destination.exists():
        if destination.is_symlink() or not destination.is_dir():
            raise ValueError("science cell output must be a real directory")
        manifest_path = destination / "manifest.json"
        manifest = _read_json(manifest_path, "science cell manifest")
        if (
            manifest.get("schema_version") != 1
            or manifest.get("stage") != "stage6"
            or manifest.get("scope") != "scientific-stage6-pilot-cell"
            or manifest.get("classification") != PILOT_PASS
            or manifest.get("spec_sha256") != spec.sha256
            or manifest.get("cell_id") != spec.cell_id
            or manifest.get("production_freeze_allowed") is not False
        ):
            raise ValueError("science cell terminal manifest is invalid")
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, dict) or artifacts != _artifact_inventory(destination):
            raise ValueError("science cell artifact inventory or hash is invalid")
        return {"state": "PASS", "resume": False, "status": manifest}
    if not work.exists():
        return {"state": "NEW", "resume": False, "status": None}
    if work.is_symlink() or not work.is_dir():
        raise ValueError("science cell work path must be a real directory")
    status_path = work / "status.json"
    checkpoints = work / "checkpoints"
    complete_checkpoints = tuple(
        path
        for path in checkpoints.glob("checkpoint-*")
        if path.is_dir() and (path / "metadata.json").is_file()
    ) if checkpoints.is_dir() else ()
    if not status_path.is_file():
        if complete_checkpoints:
            return {"state": "RESUME", "resume": True, "status": None}
        raise ValueError("science work exists without status or a complete checkpoint")
    status = _read_json(status_path, "science cell status")
    if status.get("spec_sha256") != spec.sha256 or status.get("cell_id") != spec.cell_id:
        raise ValueError("science cell status does not match the selected spec")
    classification = status.get("classification")
    if classification != PILOT_NEEDS_EXTENSION:
        if complete_checkpoints:
            return {"state": "RESUME", "resume": True, "status": status}
        raise ValueError("science cell status is neither terminal nor resumable")
    progress = status.get("progress")
    if not isinstance(progress, dict):
        raise ValueError("science cell extension progress is missing")
    target = int(progress.get("equilibration_target", 0))
    if target >= spec.equilibration_maximum_sweeps:
        return {
            "state": "SCIENTIFIC_NEGATIVE",
            "resume": False,
            "status": status,
        }
    if not complete_checkpoints:
        raise ValueError("science cell extension has no complete checkpoint")
    return {"state": "RESUME", "resume": True, "status": status}


def _cpu_slots(parallel: int, workers: int) -> tuple[tuple[int, ...], ...]:
    affinity = (
        tuple(sorted(int(value) for value in os.sched_getaffinity(0)))
        if hasattr(os, "sched_getaffinity")
        else tuple(range(max(1, os.cpu_count() or 1)))
    )
    required = parallel * workers
    if required > len(affinity):
        raise ValueError(
            f"local Stage 6 requests {required} CPUs but affinity exposes {len(affinity)}"
        )
    return tuple(
        affinity[index * workers : (index + 1) * workers]
        for index in range(parallel)
    )


def _write_state(path: Path, state: Mapping[str, Any]) -> None:
    atomic_write_json(path, dict(state))


def run_local_stage6(
    run_spec: str | Path,
    *,
    max_parallel: int,
    workers_per_cell: int,
    minimum_available_gib: float,
    checkpoint_every: int,
    resume: bool,
    allow_large_local: bool,
) -> dict[str, object]:
    """Run every preregistered cell, requeueing only declared extensions."""

    if not allow_large_local:
        raise ValueError("large local Stage 6 requires --allow-large-local")
    parallel = int(max_parallel)
    workers = int(workers_per_cell)
    if parallel < 1 or workers < 1 or checkpoint_every < 1:
        raise ValueError("parallelism, workers, and checkpoint cadence must be positive")
    minimum_memory = int(float(minimum_available_gib) * 1024**3)
    if minimum_memory < 1:
        raise ValueError("minimum available memory must be positive")
    slots = _cpu_slots(parallel, workers)
    run_spec_path = Path(run_spec).resolve()
    raw = _read_json(run_spec_path, "Stage 6 science run spec")
    cells = raw.get("cells")
    if not isinstance(cells, list) or len(cells) != 120:
        raise ValueError("local Stage 6 requires the complete 120-cell matrix")
    resolved: dict[str, tuple[object, Path, int]] = {}
    for cell in cells:
        if not isinstance(cell, dict):
            raise ValueError("Stage 6 science cell entry is invalid")
        cell_id = str(cell.get("cell_id"))
        selector = int(cell.get("array_index", 0))
        spec, output = load_selected_science_cell(
            run_spec_path,
            selector,
            track_root=TRACK_ROOT,
            repo_root=TRACK_ROOT,
        )
        if spec.cell_id != cell_id:
            raise ValueError("Stage 6 array selector changed cell identity")
        resolved[cell_id] = (spec, output, selector)
    ordered = tuple(str(cell["cell_id"]) for cell in cells)
    if len(resolved) != len(ordered):
        raise ValueError("Stage 6 cell IDs are not unique")

    run_root = (TRACK_ROOT / str(raw["run_dir"])).resolve()
    state_root = run_root / "local-run"
    state_path = state_root / "local_stage6.json"
    log_root = state_root / "logs"
    if state_root.exists() and not resume and any(state_root.iterdir()):
        raise FileExistsError("local Stage 6 state exists; explicit --resume is required")
    state_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(exist_ok=True)
    previous: dict[str, object] = {}
    if resume and state_path.is_file():
        previous = _read_json(state_path, "local Stage 6 state")
        if previous.get("run_spec_sha256") != sha256_file(run_spec_path):
            raise ValueError("local Stage 6 run spec changed on resume")
    elif resume and any(state_root.iterdir()) and not state_path.is_file():
        raise ValueError("local Stage 6 resume state is missing")

    passed: list[str] = []
    negatives: list[str] = []
    pending: deque[str] = deque()
    for cell_id in ordered:
        spec, output, _ = resolved[cell_id]
        observed = science_cell_state(spec, output)
        if observed["state"] == "PASS":
            passed.append(cell_id)
        elif observed["state"] == "SCIENTIFIC_NEGATIVE":
            negatives.append(cell_id)
        else:
            pending.append(cell_id)
    attempts = {
        str(name): int(value)
        for name, value in dict(previous.get("attempts", {})).items()
    }
    extensions = {
        str(name): int(value)
        for name, value in dict(previous.get("extensions", {})).items()
    }
    active: dict[int, tuple[str, subprocess.Popen[bytes], Any, float]] = {}
    protocol_failures: list[str] = []
    interrupted = False
    script = TRACK_ROOT / "scripts/hard_goal_science_pilot_cell.py"
    python = sys.executable
    host = local_host_provenance(
        workers_per_bundle=workers,
        max_parallel_bundles=parallel,
    )

    def snapshot(classification: str) -> dict[str, object]:
        active_records = {
            name: {
                "pid": int(process.pid),
                "slot": slot,
                "started_at": started,
            }
            for slot, (name, process, _handle, started) in active.items()
        }
        return {
            "schema_version": 1,
            "stage": "stage6",
            "classification": classification,
            "execution_policy": LOCAL_EXECUTION_POLICY,
            "remote_execution": False,
            "run_spec": str(run_spec_path),
            "run_spec_sha256": sha256_file(run_spec_path),
            "cell_count": len(ordered),
            "passed": [name for name in ordered if name in set(passed)],
            "scientific_negative": [name for name in ordered if name in set(negatives)],
            "protocol_failures": protocol_failures,
            "pending": list(pending),
            "active": active_records,
            "attempts": attempts,
            "extensions": extensions,
            "max_parallel": parallel,
            "workers_per_cell": workers,
            "minimum_available_gib": float(minimum_available_gib),
            "checkpoint_every": int(checkpoint_every),
            "host": host,
        }

    def stop_children() -> None:
        for _slot, (_name, process, _handle, _started) in active.items():
            if process.poll() is None:
                process.terminate()

    def handle_signal(_signum: int, _frame: object) -> None:
        nonlocal interrupted
        interrupted = True
        stop_children()

    old_handlers = {
        signum: signal.signal(signum, handle_signal)
        for signum in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        _write_state(state_path, snapshot("RUNNING"))
        while pending or active:
            if interrupted or protocol_failures:
                stop_children()
            for slot in range(parallel):
                if (
                    slot in active
                    or not pending
                    or interrupted
                    or protocol_failures
                ):
                    continue
                if active and available_memory_bytes() < minimum_memory:
                    break
                cell_id = pending.popleft()
                spec, output, selector = resolved[cell_id]
                observed = science_cell_state(spec, output)
                command = [
                    "taskset",
                    "-c",
                    ",".join(str(value) for value in slots[slot]),
                    python,
                    str(script),
                    "--run-spec",
                    str(run_spec_path),
                    "--selector",
                    str(selector),
                    "--require-platform",
                    "cpu",
                    "--checkpoint-every",
                    str(checkpoint_every),
                    "--measurement-cadence",
                    str(MEASUREMENT_CADENCE),
                ]
                if observed["resume"]:
                    command.append("--resume")
                log = (log_root / f"{cell_id}.log").open("ab")
                environment = os.environ.copy()
                environment.update(
                    {
                        "HARNESS_TRACK_ROOT": str(TRACK_ROOT),
                        "HARNESS_REPO_ROOT": str(TRACK_ROOT),
                        "OMP_NUM_THREADS": str(workers),
                        "MKL_NUM_THREADS": str(workers),
                        "OPENBLAS_NUM_THREADS": str(workers),
                        "NUMBA_NUM_THREADS": str(workers),
                        "PYTHONHASHSEED": "0",
                    }
                )
                process = subprocess.Popen(
                    command,
                    cwd=TRACK_ROOT,
                    env=environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                active[slot] = (cell_id, process, log, time.time())
                attempts[cell_id] = attempts.get(cell_id, 0) + 1
                print(
                    f"Stage 6 local start cell={cell_id} slot={slot} "
                    f"attempt={attempts[cell_id]}",
                    flush=True,
                )
                _write_state(state_path, snapshot("RUNNING"))

            changed = False
            for slot in tuple(active):
                cell_id, process, log, started = active[slot]
                return_code = process.poll()
                if return_code is None:
                    continue
                log.close()
                del active[slot]
                spec, output, _selector = resolved[cell_id]
                try:
                    observed = science_cell_state(spec, output)
                except Exception as error:
                    protocol_failures.append(
                        f"{cell_id}:STATE_VALIDATION:{type(error).__name__}:{error}"
                    )
                    observed = {"state": "PROTOCOL_FAILURE", "resume": False}
                if return_code == 0 and observed["state"] == "PASS":
                    passed.append(cell_id)
                elif return_code == 3 and observed["state"] == "RESUME":
                    extensions[cell_id] = extensions.get(cell_id, 0) + 1
                    pending.append(cell_id)
                elif return_code == 3 and observed["state"] == "SCIENTIFIC_NEGATIVE":
                    negatives.append(cell_id)
                else:
                    protocol_failures.append(
                        f"{cell_id}:EXIT_{return_code}:STATE_{observed['state']}"
                    )
                print(
                    f"Stage 6 local finish cell={cell_id} state={observed['state']} "
                    f"exit={return_code} elapsed={time.time() - started:.1f}s",
                    flush=True,
                )
                changed = True
            if changed:
                _write_state(state_path, snapshot("RUNNING"))
            if active and not changed:
                time.sleep(0.2)
            elif not active and (interrupted or protocol_failures):
                break
    finally:
        stop_children()
        for _slot, (_name, process, handle, _started) in tuple(active.items()):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            handle.close()
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)

    if interrupted:
        classification = "INTERRUPTED"
    elif protocol_failures:
        classification = "PROTOCOL_FAILURE"
    elif negatives:
        classification = "SCIENTIFIC_NEGATIVE"
    elif len(passed) == len(ordered):
        classification = "SCIENCE_CELLS_PASS"
    else:
        classification = "INCOMPLETE"
    result = snapshot(classification)
    _write_state(state_path, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    prepare = subcommands.add_parser("prepare")
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--selection-l12", type=Path, required=True)
    prepare.add_argument("--selection-l18", type=Path, required=True)
    prepare.add_argument("--selection-l24", type=Path, required=True)
    prepare.add_argument("--selection-l27", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    run = subcommands.add_parser("run")
    run.add_argument("--run-spec", type=Path, required=True)
    run.add_argument("--max-parallel", type=int, default=4)
    run.add_argument("--workers-per-cell", type=int, default=8)
    run.add_argument("--minimum-available-gib", type=float, default=8.0)
    run.add_argument("--checkpoint-every", type=int, default=256)
    run.add_argument("--resume", action="store_true")
    run.add_argument("--allow-large-local", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            package = prepare_selected_science_run(
                args.config,
                {
                    12: args.selection_l12,
                    18: args.selection_l18,
                    24: args.selection_l24,
                    27: args.selection_l27,
                },
                args.output,
                track_root=TRACK_ROOT,
                repo_root=TRACK_ROOT,
            )
            print(
                f"Stage 6 local package cells={package['cell_count']} "
                f"output={args.output}",
                flush=True,
            )
            return 0
        result = run_local_stage6(
            args.run_spec,
            max_parallel=args.max_parallel,
            workers_per_cell=args.workers_per_cell,
            minimum_available_gib=args.minimum_available_gib,
            checkpoint_every=args.checkpoint_every,
            resume=args.resume,
            allow_large_local=args.allow_large_local,
        )
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0 if result["classification"] == "SCIENCE_CELLS_PASS" else 2
    except Exception as error:
        print(
            f"Stage 6 local failed closed: {type(error).__name__}: {error}",
            file=sys.stderr,
            flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
