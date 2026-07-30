"""Run executable negative candidates against the SCNet validator guards."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
from pathlib import Path
from typing import Any

from .dev_validator import _candidate_tree_sha256, _run_candidate
from .validate_artifacts import ValidationError, validate_run


CONTROL_SCHEMA = "q66-negative-control-report-v2"
CONTROL_NAMES = (
    "wrong-answer",
    "cheater",
    "timeout",
    "env-escape",
    "background-escape",
)


class NegativeControlError(RuntimeError):
    """Raised when a negative candidate is not rejected by its intended guard."""


def _make_control_tree_owner_writable(root: Path) -> None:
    """Normalize an ephemeral control copied from a read-only snapshot."""

    for path in (root, *root.rglob("*")):
        mode = path.stat(follow_symlinks=False).st_mode
        if stat.S_ISLNK(mode):
            raise NegativeControlError(f"control tree contains a symlink: {path}")
        path.chmod(mode | stat.S_IWUSR)


def _canonical_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="ascii",
    )


def _request_for_control(base_request: Path, name: str, out: Path) -> Path:
    value = json.loads(base_request.read_text(encoding="ascii"))
    value["run_id"] = f"negative-control-{name}"
    value["shots"] = 8
    value["shot_start"] = 0
    value["shard_size"] = 8
    value["master_seed"] = 66_000_066
    _canonical_json(out, value)
    return out


def _run_one(
    *, name: str, controls_root: Path, base_request: Path, result_root: Path
) -> dict[str, Any]:
    control_root = result_root / name
    candidate_root = control_root / "candidate"
    shutil.copytree(controls_root / name, candidate_root)
    _make_control_tree_owner_writable(candidate_root)
    request_path = _request_for_control(
        base_request, name, control_root / "request.json"
    )
    output_root = control_root / "candidate-output"
    before_hash = _candidate_tree_sha256(candidate_root)
    result = _run_candidate(
        candidate_root=candidate_root,
        request_path=request_path,
        run_root=output_root,
        timeout_seconds=2 if name == "timeout" else 120,
    )
    stdout = result.pop("stdout")
    stderr = result.pop("stderr")
    after_hash = _candidate_tree_sha256(candidate_root)
    evidence: dict[str, Any] = {
        **result,
        "candidate_tree_sha256_before": before_hash,
        "candidate_tree_sha256_after": after_hash,
        "stdout": stdout,
        "stderr": stderr,
    }

    if name == "wrong-answer":
        if result["timed_out"] or result["return_code"] != 0:
            raise NegativeControlError("wrong-answer did not produce a valid artifact")
        try:
            validate_run(output_root)
        except ValidationError as exc:
            if "exact replay mismatch" not in str(exc):
                raise NegativeControlError(
                    f"wrong-answer hit the wrong guard: {exc}"
                ) from exc
            evidence["rejection"] = "exact-replay-rejected"
            evidence["validation_error"] = str(exc)
        else:
            raise NegativeControlError("wrong-answer candidate was accepted")
    elif name == "cheater":
        if result["timed_out"] or result["return_code"] != 23:
            raise NegativeControlError("cheater was not rejected on an unseen seed")
        evidence["rejection"] = "candidate-process-failed-on-unseen-seed"
    elif name == "timeout":
        if not result["timed_out"] or result["return_code"] == 0:
            raise NegativeControlError("timeout candidate escaped its deadline")
        try:
            child_pid = int(json.loads(stdout.splitlines()[0])["child_pid"])
        except (IndexError, KeyError, ValueError, json.JSONDecodeError) as exc:
            raise NegativeControlError("timeout candidate did not report its child") from exc
        if Path(f"/proc/{child_pid}").exists():
            raise NegativeControlError("timeout child survived process-group termination")
        evidence["child_pid"] = child_pid
        evidence["rejection"] = "candidate-process-timed-out-and-group-terminated"
    elif name == "env-escape":
        try:
            escape = json.loads(stdout.splitlines()[0])
        except (IndexError, json.JSONDecodeError) as exc:
            raise NegativeControlError("env-escape returned invalid evidence") from exc
        if escape.get("socket_errno") != 1:
            raise NegativeControlError("env-escape created a socket")
        if before_hash == after_hash:
            raise NegativeControlError("env-escape write was not detected")
        evidence["rejection"] = "candidate-source-tree-mutated"
        evidence["socket_errno"] = escape["socket_errno"]
    elif name == "background-escape":
        try:
            child_pid = int(json.loads(stdout.splitlines()[0])["child_pid"])
        except (IndexError, KeyError, ValueError, json.JSONDecodeError) as exc:
            raise NegativeControlError(
                "background-escape candidate did not report its child"
            ) from exc
        cleanup = result["process_cleanup"]
        if result["timed_out"] or result["return_code"] != 0:
            raise NegativeControlError(
                "background-escape candidate leader did not exit normally"
            )
        if not cleanup["background_processes_detected"]:
            raise NegativeControlError(
                "background-escape child was not detected after leader exit"
            )
        if child_pid not in cleanup["background_process_ids"]:
            raise NegativeControlError(
                "background-escape child identity was not captured"
            )
        if not cleanup["process_group_cleared"]:
            raise NegativeControlError(
                "background-escape child survived post-exit cleanup"
            )
        evidence["child_pid"] = child_pid
        evidence["rejection"] = "background-process-detected-and-terminated"
    else:
        raise NegativeControlError(f"unknown control {name}")
    evidence["status"] = "rejected-as-expected"
    return evidence


def run_controls(
    *, controls_root: Path, base_request: Path, output_root: Path
) -> dict[str, Any]:
    slurm_job_id = os.environ.get("SLURM_JOB_ID")
    if not slurm_job_id:
        raise NegativeControlError("negative controls must run inside Slurm")
    if output_root.exists():
        raise NegativeControlError(f"control output already exists: {output_root}")
    output_root.mkdir(parents=True)
    results = {
        name: _run_one(
            name=name,
            controls_root=controls_root,
            base_request=base_request,
            result_root=output_root,
        )
        for name in CONTROL_NAMES
    }
    report = {
        "schema_version": CONTROL_SCHEMA,
        "status": "passed",
        "slurm_job_id": slurm_job_id,
        "controls": results,
    }
    _canonical_json(output_root / "report.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--controls-root", type=Path, required=True)
    parser.add_argument("--base-request", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_controls(
        controls_root=args.controls_root,
        base_request=args.base_request,
        output_root=args.output_root,
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
