"""SCNet-only subprocess runner for the public development validator."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .analyze import AnalysisError
from .config import SimulationRequest
from .dev_matrix import MATRIX_SCHEMA
from .sandbox import (
    SANDBOX_SCHEMA,
    install_candidate_sandbox,
    network_denial_preflight,
)
from .validate_artifacts import ValidationError, validate_run


RUNNER_SCHEMA = "q66-dev-validator-cell-v2"
PROCESS_GROUP_TERM_GRACE_SECONDS = 2.0
PROCESS_GROUP_KILL_GRACE_SECONDS = 5.0


class DevValidatorError(RuntimeError):
    """Raised when validator infrastructure or a candidate run fails."""


def _canonical_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="ascii",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_tree_sha256(candidate_root: Path) -> str:
    source_root = candidate_root / "src"
    paths = sorted(
        path
        for path in source_root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )
    paths.extend(
        path
        for path in (
            candidate_root / "pyproject.toml",
            candidate_root / "sitecustomize.py",
            candidate_root / "usercustomize.py",
        )
        if path.is_file()
    )
    paths = sorted(set(paths))
    if not paths:
        raise DevValidatorError(f"candidate source tree is empty: {source_root}")
    digest = hashlib.sha256()
    for path in paths:
        if path.is_symlink():
            raise DevValidatorError(f"candidate source must not be a symlink: {path}")
        relative = path.relative_to(candidate_root).as_posix().encode("ascii")
        digest.update(len(relative).to_bytes(4, "little"))
        digest.update(relative)
        digest.update(bytes.fromhex(_sha256(path)))
    return digest.hexdigest()


def _load_matrix(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    if value.get("schema_version") != MATRIX_SCHEMA:
        raise DevValidatorError("unsupported development matrix schema")
    cells = value.get("cells")
    if (
        not isinstance(cells, list)
        or len(cells) != 16
        or value.get("cell_count") != 16
        or value.get("warmup_runs") != 1
        or value.get("timed_runs") != 3
    ):
        raise DevValidatorError("development matrix shape/repetitions changed")
    for cell_index, cell in enumerate(cells):
        if cell.get("cell_index") != cell_index:
            raise DevValidatorError("development cell order is not contiguous")
        SimulationRequest.from_dict(cell["request"])
    return value


def _candidate_environment(candidate_root: Path) -> dict[str, str]:
    environment = dict(os.environ)
    trusted_source_root = Path(__file__).resolve().parents[1]
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(candidate_root / "src"), str(trusted_source_root))
    )
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONHASHSEED"] = "0"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    for key in (
        "http_proxy",
        "https_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "all_proxy",
    ):
        environment.pop(key, None)
    return environment


def repetition_request(
    base_request: dict[str, Any], repetition: int
) -> dict[str, Any]:
    if repetition < 0:
        raise DevValidatorError("repetition must be non-negative")
    request_value = dict(base_request)
    request_value["run_id"] = f"{base_request['run_id']}-repeat-{repetition}"
    request_value["shot_start"] = repetition * int(request_value["shots"])
    SimulationRequest.from_dict(request_value)
    return request_value


def _live_process_group_members(process_group_id: int) -> list[int]:
    """Return non-zombie members of a candidate process group."""

    members = []
    for process_root in Path("/proc").iterdir():
        if not process_root.name.isdigit():
            continue
        try:
            stat = (process_root / "stat").read_text(encoding="ascii")
            fields = stat[stat.rfind(")") + 2 :].split()
            state = fields[0]
            observed_group_id = int(fields[2])
        except (FileNotFoundError, IndexError, PermissionError, ValueError):
            continue
        if observed_group_id == process_group_id and state != "Z":
            members.append(int(process_root.name))
    return sorted(members)


def _wait_for_process_group_exit(process_group_id: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _live_process_group_members(process_group_id):
            return True
        time.sleep(0.05)
    return not _live_process_group_members(process_group_id)


def _clear_background_processes(process_group_id: int) -> dict[str, Any]:
    """Terminate descendants left behind after the candidate leader exits."""

    initial_members = _live_process_group_members(process_group_id)
    signals_sent = []
    if initial_members:
        try:
            os.killpg(process_group_id, signal.SIGTERM)
        except ProcessLookupError:
            pass
        else:
            signals_sent.append("SIGTERM")
        cleared = _wait_for_process_group_exit(
            process_group_id, PROCESS_GROUP_TERM_GRACE_SECONDS
        )
        if not cleared:
            try:
                os.killpg(process_group_id, signal.SIGKILL)
            except ProcessLookupError:
                pass
            else:
                signals_sent.append("SIGKILL")
            cleared = _wait_for_process_group_exit(
                process_group_id, PROCESS_GROUP_KILL_GRACE_SECONDS
            )
    else:
        cleared = True
    return {
        "background_processes_detected": bool(initial_members),
        "background_process_ids": initial_members,
        "background_process_signals": signals_sent,
        "process_group_cleared": cleared,
    }


def _run_candidate(
    *,
    candidate_root: Path,
    request_path: Path,
    run_root: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "reload_qec.candidate",
        "--request",
        str(request_path),
        "--out",
        str(run_root),
    ]
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=candidate_root,
        env=_candidate_environment(candidate_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        preexec_fn=install_candidate_sandbox,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
    process_cleanup = _clear_background_processes(process.pid)
    elapsed = time.monotonic() - started
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {
        "command": command,
        "return_code": process.returncode,
        "timed_out": timed_out,
        "candidate_wall_seconds": elapsed,
        "children_max_rss_kib": int(usage.ru_maxrss),
        "stdout": stdout,
        "stderr": stderr,
        "process_cleanup": process_cleanup,
    }


def run_cell(
    *,
    matrix_path: Path,
    candidate_root: Path,
    candidate_id: str,
    output_root: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", candidate_id):
        raise DevValidatorError("candidate ID contains unsupported characters")
    array_job_id = os.environ.get("SLURM_ARRAY_JOB_ID")
    array_task_id = os.environ.get("SLURM_ARRAY_TASK_ID")
    if not array_job_id or array_task_id is None:
        raise DevValidatorError("development validator must run as a Slurm array")
    try:
        cell_index = int(array_task_id)
    except ValueError as exc:
        raise DevValidatorError("invalid Slurm array task ID") from exc
    if output_root.name != array_job_id:
        raise DevValidatorError("validator output root differs from Slurm array ID")
    matrix = _load_matrix(matrix_path)
    if not 0 <= cell_index < len(matrix["cells"]):
        raise DevValidatorError("Slurm task is outside the development matrix")

    candidate_root = candidate_root.resolve(strict=True)
    candidate_entry = candidate_root / "src/reload_qec/candidate.py"
    if not candidate_entry.is_file():
        raise DevValidatorError(f"candidate entry point is missing: {candidate_entry}")
    cell = matrix["cells"][cell_index]
    cell_root = output_root / f"cell-{cell_index:02d}"
    if cell_root.exists():
        raise DevValidatorError(f"validator output already exists: {cell_root}")
    cell_root.mkdir(parents=True)
    repetitions = matrix["warmup_runs"] + matrix["timed_runs"]
    candidate_tree_sha256 = _candidate_tree_sha256(candidate_root)
    sandbox = network_denial_preflight(sys.executable)
    if sandbox.get("schema_version") != SANDBOX_SCHEMA:
        raise DevValidatorError("candidate sandbox preflight schema mismatch")
    runs = []
    status = "passed"
    deadline = time.monotonic() + timeout_seconds
    for repetition in range(repetitions):
        remaining_seconds = int(deadline - time.monotonic())
        if remaining_seconds <= 0:
            status = "rejected"
            runs.append(
                {
                    "repetition": repetition,
                    "timing_role": "warmup" if repetition == 0 else "timed",
                    "validation": "cell-wall-time-exhausted",
                }
            )
            break
        request_value = repetition_request(cell["request"], repetition)
        request_path = cell_root / f"request-{repetition}.json"
        _canonical_json(request_path, request_value)
        repetition_root = cell_root / f"repeat-{repetition}"
        result = _run_candidate(
            candidate_root=candidate_root,
            request_path=request_path,
            run_root=repetition_root,
            timeout_seconds=remaining_seconds,
        )
        (cell_root / f"repeat-{repetition}.stdout").write_text(
            result.pop("stdout"), encoding="utf-8"
        )
        (cell_root / f"repeat-{repetition}.stderr").write_text(
            result.pop("stderr"), encoding="utf-8"
        )
        result["repetition"] = repetition
        result["timing_role"] = "warmup" if repetition == 0 else "timed"
        result["run_id"] = request_value["run_id"]
        result["shot_start"] = request_value["shot_start"]
        result["shots"] = request_value["shots"]
        if _candidate_tree_sha256(candidate_root) != candidate_tree_sha256:
            status = "rejected"
            result["validation"] = "candidate-source-tree-mutated"
            runs.append(result)
            break
        if result["process_cleanup"]["background_processes_detected"]:
            status = "rejected"
            result["validation"] = "candidate-background-process-detected"
            runs.append(result)
            break
        if not result["process_cleanup"]["process_group_cleared"]:
            status = "rejected"
            result["validation"] = "candidate-background-process-survived"
            runs.append(result)
            break
        if result["timed_out"] or result["return_code"] != 0:
            status = "rejected"
            result["validation"] = "candidate-process-failed"
            runs.append(result)
            break
        validation_started = time.monotonic()
        try:
            validate_run(repetition_root)
        except (
            AnalysisError,
            ValidationError,
            FileNotFoundError,
            KeyError,
            ValueError,
        ) as exc:
            status = "rejected"
            result["validation"] = "exact-replay-rejected"
            result["validation_error"] = {
                "type": type(exc).__name__,
                "detail": str(exc),
            }
            runs.append(result)
            break
        result["validator_wall_seconds"] = time.monotonic() - validation_started
        result["validation"] = "exact-replay-passed"
        runs.append(result)
        if time.monotonic() > deadline:
            status = "rejected"
            result["validation"] = "cell-wall-time-exhausted-after-replay"
            break

    report = {
        "schema_version": RUNNER_SCHEMA,
        "status": status,
        "slurm_array_job_id": array_job_id,
        "slurm_array_task_id": array_task_id,
        "matrix": str(matrix_path),
        "matrix_sha256": _sha256(matrix_path),
        "cell_index": cell_index,
        "workload_id": cell["workload_id"],
        "candidate_root": str(candidate_root),
        "candidate_id": candidate_id,
        "candidate_tree_sha256": candidate_tree_sha256,
        "sandbox": sandbox,
        "filesystem_guard": "candidate-tree-sha256-before-and-after-every-run",
        "timeout_seconds": timeout_seconds,
        "runs": runs,
    }
    _canonical_json(cell_root / "runner-report.json", report)
    if status != "passed":
        raise DevValidatorError(
            f"candidate failed in cell {cell_index}; see {cell_root}"
        )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=2_700)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.timeout_seconds <= 0 or args.timeout_seconds > 2_700:
        raise DevValidatorError("timeout must be inside (0,2700]")
    report = run_cell(
        matrix_path=args.matrix,
        candidate_root=args.candidate_root,
        candidate_id=args.candidate_id,
        output_root=args.output_root,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
