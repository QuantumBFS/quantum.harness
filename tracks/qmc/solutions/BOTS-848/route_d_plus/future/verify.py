"""Read-only dependency and artifact verifier for Route D+ Phases 7--11.

The module validates metadata envelopes only.  It has no import path to the ED
or training implementations and never chooses model capacity.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import jsonschema

SCHEMA_VERSION = "challenge-15-route-d-plus-future-aggregate-v1"
SCHEMA_DIR = Path(__file__).resolve().parent
STAGE_KINDS = {
    "phase7": {"ed-sector", "overlap", "span-ceiling"},
    "phase8": {"dplus1-seed", "dplus2-seed"},
    "phase9": {"heldout-ed"},
    "phase10": {"chirality"},
    "phase11": {"beyond-ed"},
}
STAGE_DECISIONS = {
    "phase7": "phase7-capacity-decision",
    "phase8": "phase8-architecture-selection",
    "phase9": "phase9-heldout-summary",
    "phase10": "phase10-chirality-summary",
    "phase11": "phase11-beyond-ed-summary",
}
STAGE_PREREQUISITES = {
    "phase7": {
        "phase6-frozen-checkpoint-gate",
        "user-authorized-phase7-reveal",
        "dplus0-remediation-gate",
    },
    "phase8": "phase7-capacity-gate",
    "phase9": "architecture-freeze",
    "phase10": "architecture-freeze",
    "phase11": "architecture-freeze",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def schema_validator(name: str) -> jsonschema.Draft202012Validator:
    schema = load_json(SCHEMA_DIR / name)
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    )


def validate_payload(payload: dict[str, Any], schema_name: str) -> None:
    schema_validator(schema_name).validate(payload)


def require_artifact(reference: dict[str, Any]) -> Path:
    path = Path(reference["path"]).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"artifact does not exist: {path}")
    actual = sha256_file(path)
    if actual != reference["sha256"]:
        raise ValueError(
            f"artifact hash mismatch for {path}: "
            f"{actual} != {reference['sha256']}"
        )
    return path


def require_isolated_path(run_root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"task run_dir must be a safe relative path: {relative}")
    resolved = (run_root / candidate).resolve()
    if not resolved.is_relative_to(run_root.resolve()):
        raise ValueError(f"task run_dir escapes run root: {relative}")
    return resolved


def git_revision(repo_root: Path) -> tuple[str, bool]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return revision, dirty


def validate_dependency(reference: dict[str, Any]) -> dict[str, Any]:
    path = require_artifact(reference)
    payload = load_json(path)
    validate_payload(payload, "dependency.schema.json")
    if payload["kind"] != reference["kind"]:
        raise ValueError(f"dependency kind mismatch for {path}")
    return payload


def _validate_phase7_tasks(tasks: list[dict[str, Any]]) -> None:
    sectors = [task for task in tasks if task["kind"] == "ed-sector"]
    if len(tasks) != 7 or len(sectors) != 5:
        raise ValueError("Phase 7 requires five sectors, overlap, and span")
    if sorted(task.get("m_sector") for task in sectors) != [-2, -1, 0, 1, 2]:
        raise ValueError("Phase 7 must register each M=-2..2 exactly once")
    if sum(task["kind"] == "overlap" for task in tasks) != 1:
        raise ValueError("Phase 7 requires exactly one overlap task")
    if sum(task["kind"] == "span-ceiling" for task in tasks) != 1:
        raise ValueError("Phase 7 requires exactly one span-ceiling task")
    if any(task["n_electrons"] != 6 for task in tasks):
        raise ValueError("Phase 7 reveal is fixed to N=6")


def _validate_phase8_tasks(tasks: list[dict[str, Any]]) -> None:
    for capacity, kind in (("D+1", "dplus1-seed"), ("D+2", "dplus2-seed")):
        subset = [task for task in tasks if task["kind"] == kind]
        if len(subset) < 3:
            raise ValueError(f"Phase 8 requires at least three {capacity} seeds")
        seeds = [task.get("seed") for task in subset]
        if None in seeds or len(seeds) != len(set(seeds)):
            raise ValueError(f"Phase 8 {capacity} seeds must be unique")
        if any(task.get("capacity") != capacity for task in subset):
            raise ValueError(f"Phase 8 capacity tag mismatch for {capacity}")


def validate_dispatch(
    payload: dict[str, Any],
    *,
    run_root: Path | None = None,
    verify_prerequisites: bool = True,
) -> None:
    validate_payload(payload, "dispatch.schema.json")
    stage = payload["stage"]
    tasks = payload["tasks"]
    if any(task["kind"] not in STAGE_KINDS[stage] for task in tasks):
        raise ValueError(f"task kind does not belong to {stage}")
    task_ids = [task["task_id"] for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("duplicate task_id in dispatch")

    declared_root = Path(payload["run_root"]).resolve()
    if run_root is not None and declared_root != run_root.resolve():
        raise ValueError("dispatch run_root differs from requested run root")
    directories = [
        require_isolated_path(declared_root, task["run_dir"])
        for task in tasks
    ]
    if len(directories) != len(set(directories)):
        raise ValueError("task run directories are not isolated")

    expected = STAGE_PREREQUISITES[stage]
    dependencies = {
        item["kind"]: item for item in payload["prerequisites"]
    }
    expected_kinds = expected if isinstance(expected, set) else {expected}
    present = expected_kinds.intersection(dependencies)
    if len(present) != 1:
        raise ValueError(
            f"{stage} requires exactly one of {sorted(expected_kinds)}"
        )
    if verify_prerequisites:
        resolved = {
            kind: validate_dependency(reference)
            for kind, reference in dependencies.items()
        }
        if stage == "phase8":
            action = resolved[next(iter(present))]["capacity_action"]
            if action != "trigger-preregistered-D+1-D+2":
                raise ValueError("Phase 8 was not triggered by the Phase 7 gate")

    if stage == "phase7":
        _validate_phase7_tasks(tasks)
    elif stage == "phase8":
        _validate_phase8_tasks(tasks)


def validate_task_certificate(
    payload: dict[str, Any],
    *,
    task: dict[str, Any],
    dispatch: dict[str, Any],
    verify_artifacts: bool = True,
) -> None:
    validate_payload(payload, "task-certificate.schema.json")
    expected = {
        "stage": dispatch["stage"],
        "task_id": task["task_id"],
        "kind": task["kind"],
        "source_revision": dispatch["source_revision"],
    }
    mismatches = {
        key: (payload.get(key), value)
        for key, value in expected.items()
        if payload.get(key) != value
    }
    if mismatches:
        raise ValueError(f"task certificate mismatch: {mismatches}")
    expected_dir = require_isolated_path(
        Path(dispatch["run_root"]),
        task["run_dir"],
    )
    if Path(payload["run_dir"]).resolve() != expected_dir:
        raise ValueError("task certificate run_dir mismatch")
    if not set(task["required_gates"]).issubset(payload["gates"]):
        raise ValueError("task certificate omits pre-registered gates")
    dispatched_inputs = {
        (reference["path"], reference["sha256"])
        for reference in dispatch["prerequisites"]
    }
    certified_inputs = {
        (reference["path"], reference["sha256"])
        for reference in payload["input_artifacts"]
    }
    if not dispatched_inputs.issubset(certified_inputs):
        raise ValueError("task certificate omits dispatched prerequisites")

    if verify_artifacts:
        for reference in payload["input_artifacts"]:
            require_artifact(reference)
        for reference in payload["logs"].values():
            require_artifact(reference)
        domain = payload["domain_certificate"]
        domain_path = require_artifact(domain)
        schema_path = Path(domain["schema_path"]).resolve()
        if sha256_file(schema_path) != domain["schema_sha256"]:
            raise ValueError("domain schema hash mismatch")
        schema = load_json(schema_path)
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(
            schema,
            format_checker=jsonschema.FormatChecker(),
        ).validate(load_json(domain_path))
        if payload.get("checkpoint") is not None:
            require_artifact(payload["checkpoint"])


def validate_stage_gate(
    payload: dict[str, Any],
    *,
    dispatch: dict[str, Any],
) -> None:
    validate_payload(payload, "stage-gate.schema.json")
    if payload["stage"] != dispatch["stage"]:
        raise ValueError("stage gate stage differs from dispatch")
    if payload["source_revision"] != dispatch["source_revision"]:
        raise ValueError("stage gate source revision differs from dispatch")
    expected_tasks = {task["task_id"] for task in dispatch["tasks"]}
    if set(payload["task_ids"]) != expected_tasks:
        raise ValueError("stage gate does not cover the exact task set")
    expected_kind = STAGE_DECISIONS[dispatch["stage"]]
    if payload["decision"]["kind"] != expected_kind:
        raise ValueError("stage gate decision kind differs from stage")
    if dispatch["stage"] == "phase7":
        classification = payload["decision"]["benchmark_classification"]
        action = payload["decision"]["capacity_action"]
        expected_action = (
            "trigger-preregistered-D+1-D+2"
            if classification == "expression-limited"
            else "keep-D+0"
        )
        if action != expected_action:
            raise ValueError("Phase 7 classification/capacity action mismatch")
    elif dispatch["stage"] == "phase8":
        require_artifact(payload["decision"]["architecture_freeze"])


def require_gpu_slurm_environment() -> tuple[str, str]:
    job_id = os.environ.get("SLURM_JOB_ID", "")
    cluster = os.environ.get("SLURM_CLUSTER_NAME", "")
    visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if not job_id or not cluster:
        raise RuntimeError("aggregate verification requires a Slurm job")
    if not visible or visible in {"NoDevFiles", "-1"}:
        raise RuntimeError("aggregate verification requires a GPU allocation")
    return job_id, cluster


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def aggregate(
    *,
    dispatch_path: Path,
    stage_gate_path: Path,
    repo_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    job_id, cluster = require_gpu_slurm_environment()
    dispatch = load_json(dispatch_path)
    validate_dispatch(dispatch)
    revision, dirty = git_revision(repo_root)
    if dirty or revision != dispatch["source_revision"]:
        raise RuntimeError("aggregate requires the clean dispatched revision")

    certificate_references = []
    for task in dispatch["tasks"]:
        run_dir = require_isolated_path(
            Path(dispatch["run_root"]),
            task["run_dir"],
        )
        certificate_path = run_dir / "task-certificate.json"
        certificate = load_json(certificate_path)
        validate_task_certificate(
            certificate,
            task=task,
            dispatch=dispatch,
        )
        certificate_references.append(
            {
                "task_id": task["task_id"],
                "path": str(certificate_path.resolve()),
                "sha256": sha256_file(certificate_path),
            }
        )

    stage_gate = load_json(stage_gate_path)
    validate_stage_gate(stage_gate, dispatch=dispatch)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "stage": dispatch["stage"],
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_revision": revision,
        "dispatch": {
            "path": str(dispatch_path.resolve()),
            "sha256": sha256_file(dispatch_path),
        },
        "stage_gate": {
            "path": str(stage_gate_path.resolve()),
            "sha256": sha256_file(stage_gate_path),
        },
        "task_certificates": certificate_references,
        "gates": {
            "dispatch_schema_valid": True,
            "prerequisite_hashes_valid": True,
            "exact_task_set": True,
            "isolated_run_directories": True,
            "all_task_schemas_valid": True,
            "all_artifact_hashes_valid": True,
            "clean_consistent_source_revision": True,
            "gpu_slurm_evidence": True,
            "stage_gate_schema_valid": True,
            "stage_gate_matches_tasks": True,
        },
        "passed": True,
        "slurm_job_id": job_id,
        "slurm_cluster_name": cluster,
    }
    validate_payload(payload, "aggregate-certificate.schema.json")
    write_json_atomic(output_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("--dispatch", required=True, type=Path)
    preflight_parser.add_argument("--repo-root", required=True, type=Path)

    list_parser = subparsers.add_parser("list-tasks")
    list_parser.add_argument("--dispatch", required=True, type=Path)

    task_parser = subparsers.add_parser("verify-task")
    task_parser.add_argument("--dispatch", required=True, type=Path)
    task_parser.add_argument("--task-id", required=True)

    aggregate_parser = subparsers.add_parser("aggregate")
    aggregate_parser.add_argument("--dispatch", required=True, type=Path)
    aggregate_parser.add_argument("--stage-gate", required=True, type=Path)
    aggregate_parser.add_argument("--repo-root", required=True, type=Path)
    aggregate_parser.add_argument("--output", required=True, type=Path)

    arguments = parser.parse_args()
    dispatch = load_json(arguments.dispatch.resolve())
    if arguments.command == "preflight":
        validate_dispatch(dispatch)
        revision, dirty = git_revision(arguments.repo_root.resolve())
        if dirty or revision != dispatch["source_revision"]:
            raise RuntimeError("preflight requires the clean dispatched revision")
        print(json.dumps({"passed": True, "stage": dispatch["stage"]}))
    elif arguments.command == "list-tasks":
        validate_dispatch(dispatch)
        for task in dispatch["tasks"]:
            run_dir = require_isolated_path(
                Path(dispatch["run_root"]),
                task["run_dir"],
            )
            print(f"{task['task_id']}\t{run_dir}")
    elif arguments.command == "verify-task":
        validate_dispatch(dispatch)
        tasks = {
            task["task_id"]: task for task in dispatch["tasks"]
        }
        task = tasks[arguments.task_id]
        run_dir = require_isolated_path(
            Path(dispatch["run_root"]),
            task["run_dir"],
        )
        validate_task_certificate(
            load_json(run_dir / "task-certificate.json"),
            task=task,
            dispatch=dispatch,
        )
        print(json.dumps({"passed": True, "task_id": arguments.task_id}))
    else:
        payload = aggregate(
            dispatch_path=arguments.dispatch.resolve(),
            stage_gate_path=arguments.stage_gate.resolve(),
            repo_root=arguments.repo_root.resolve(),
            output_path=arguments.output.resolve(),
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
