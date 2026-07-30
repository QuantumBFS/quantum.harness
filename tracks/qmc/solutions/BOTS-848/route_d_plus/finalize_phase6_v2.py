"""Finalize Phase 6 after an immutable-checkpoint measurement extension."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

import jsonschema

SCHEMA_VERSION = "challenge-15-route-d-plus-phase6-final-v2"
READBACK_VERSION = "challenge-15-route-d-plus-phase6-final-v2-readback"
MODULE_ROOT = Path(__file__).resolve().parent
SEEDS = (848, 1848, 2848)


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


def validate(payload: dict[str, Any], schema_path: Path) -> None:
    schema = load_json(schema_path)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    ).validate(payload)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def git_output(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def require_commit(repo_root: Path, revision: str) -> None:
    subprocess.run(
        ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def artifact(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return {"path": str(resolved), "sha256": sha256_file(resolved)}


def schema_artifact(
    path: Path,
    schema_path: Path,
) -> dict[str, str]:
    payload = load_json(path)
    validate(payload, schema_path)
    return {
        **artifact(path),
        "schema_path": str(schema_path.resolve()),
        "schema_sha256": sha256_file(schema_path),
    }


def require_gpu_slurm() -> dict[str, str]:
    job_id = os.environ.get("SLURM_JOB_ID", "")
    cluster = os.environ.get("SLURM_CLUSTER_NAME", "")
    visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if not job_id or not cluster:
        raise RuntimeError("Phase 6 v2 finalization requires Slurm")
    if not visible or visible in {"-1", "NoDevFiles"}:
        raise RuntimeError("Phase 6 v2 finalization requires a GPU")
    return {
        "job_id": job_id,
        "cluster_name": cluster,
        "hostname": platform.node(),
        "gpu_visible": visible,
    }


def require_job(
    *,
    job_id: str,
    state: str,
    exit_code: str,
    stdout_path: Path,
    stderr_path: Path,
    sacct_path: Path,
) -> dict[str, Any]:
    evidence = sacct_path.read_text(encoding="utf-8")
    requirements = (job_id, state, exit_code, "gres/gpu=1")
    missing = [value for value in requirements if value not in evidence]
    if missing:
        raise RuntimeError(f"incomplete Slurm evidence for {job_id}: {missing}")
    return {
        "job_id": job_id,
        "state": state,
        "exit_code": exit_code,
        "stdout": artifact(stdout_path),
        "stderr": artifact(stderr_path),
        "sacct": artifact(sacct_path),
    }


def exact_failed_gates(attempt: dict[str, Any]) -> list[str]:
    return sorted(
        gate for gate, passed in attempt["gates"].items() if not passed
    )


def finalize(
    *,
    repo_root: Path,
    attempt_path: Path,
    measurement_path: Path,
    phase6a_path: Path,
    training_job: dict[str, Any],
    attempt_readback_job: dict[str, Any],
    measurement_job: dict[str, Any],
) -> dict[str, Any]:
    finalizer_job = require_gpu_slurm()
    finalizer_revision = git_output(repo_root, "rev-parse", "HEAD")
    finalizer_tree = git_output(repo_root, "rev-parse", "HEAD^{tree}")
    if git_output(repo_root, "status", "--porcelain"):
        raise RuntimeError("Phase 6 v2 finalization requires a clean worktree")

    attempt = load_json(attempt_path)
    validate(attempt, MODULE_ROOT / "phase6-attempt.schema.json")
    if (
        exact_failed_gates(attempt) != ["gap_precision"]
        or attempt["ed_accessed"]
    ):
        raise RuntimeError("input attempt is not a sole precision failure")
    producer_revision = attempt["git_commit"]
    require_commit(repo_root, producer_revision)

    measurement = load_json(measurement_path)
    validate(measurement, MODULE_ROOT / "phase6-measurement.schema.json")
    if (
        not measurement["passed"]
        or measurement["ed_accessed"]
        or measurement["producer_source_revision"] != producer_revision
        or measurement["input_attempt"]["sha256"]
        != sha256_file(attempt_path)
    ):
        raise RuntimeError("measurement extension provenance mismatch")
    measurement_revision = measurement["measurement_source_revision"]
    require_commit(repo_root, measurement_revision)

    phase6a = load_json(phase6a_path)
    validate(phase6a, MODULE_ROOT / "phase6a.schema.json")
    if not phase6a["passed"]:
        raise RuntimeError("Phase 6A certificate did not pass")

    architecture_reference = attempt["architecture"]
    architecture_path = Path(architecture_reference["path"])
    architecture_schema = Path(architecture_reference["schema_path"])
    if (
        sha256_file(architecture_path) != architecture_reference["sha256"]
        or sha256_file(architecture_schema)
        != architecture_reference["schema_sha256"]
    ):
        raise RuntimeError("architecture reference mismatch")
    architecture = schema_artifact(architecture_path, architecture_schema)
    if (
        architecture["sha256"] != measurement["architecture"]["sha256"]
        or load_json(architecture_path)["source_revision"]
        != producer_revision
    ):
        raise RuntimeError("architecture provenance mismatch")

    seed_artifacts = []
    measurement_checkpoint_by_seed = {
        item["seed"]: item for item in measurement["checkpoints"]
    }
    for reference in attempt["checkpoints"]:
        seed = reference["seed"]
        checkpoint_path = Path(reference["path"])
        checkpoint_schema = Path(reference["schema_path"])
        symmetry_path = Path(reference["symmetry_path"])
        symmetry_schema = MODULE_ROOT / "symmetry.schema.json"
        if (
            sha256_file(checkpoint_path) != reference["sha256"]
            or sha256_file(checkpoint_schema) != reference["schema_sha256"]
            or sha256_file(symmetry_path) != reference["symmetry_sha256"]
            or sha256_file(symmetry_schema)
            != reference["symmetry_schema_sha256"]
        ):
            raise RuntimeError(f"seed {seed} frozen artifact mismatch")
        checkpoint = load_json(checkpoint_path)
        if (
            checkpoint["source_revision"] != producer_revision
            or checkpoint["architecture_sha256"] != architecture["sha256"]
            or measurement_checkpoint_by_seed[seed]["sha256"]
            != reference["sha256"]
        ):
            raise RuntimeError(f"seed {seed} checkpoint provenance mismatch")
        seed_artifacts.append(
            {
                "seed": seed,
                "checkpoint": schema_artifact(
                    checkpoint_path,
                    checkpoint_schema,
                ),
                "symmetry": schema_artifact(
                    symmetry_path,
                    symmetry_schema,
                ),
            }
        )
    if [item["seed"] for item in seed_artifacts] != list(SEEDS):
        raise RuntimeError("frozen seed set is not exact")

    audit_path = Path(attempt["blind_access_audit"]["path"])
    if sha256_file(audit_path) != attempt["blind_access_audit"]["sha256"]:
        raise RuntimeError("training blind-audit hash mismatch")
    audit = load_json(audit_path)
    if (
        audit["denied_events"]
        or audit["loaded_forbidden_before"]
        or audit["loaded_forbidden_after"]
    ):
        raise RuntimeError("training blind audit is not clean")

    task_references = []
    observed_tasks = set()
    for reference in measurement["tasks"]:
        task_path = Path(reference["certificate"]["path"])
        if sha256_file(task_path) != reference["certificate"]["sha256"]:
            raise RuntimeError("measurement task hash mismatch")
        task = load_json(task_path)
        validate(
            task,
            MODULE_ROOT / "phase6-measurement-task.schema.json",
        )
        identity = (task["seed"], task["sector"], task["chain"])
        if identity != (
            reference["seed"],
            reference["sector"],
            reference["chain"],
        ):
            raise RuntimeError("measurement task identity mismatch")
        for key in ("stdout", "stderr"):
            if (
                sha256_file(Path(reference[key]["path"]))
                != reference[key]["sha256"]
            ):
                raise RuntimeError(f"measurement task {key} mismatch")
        observed_tasks.add(identity)
        task_references.append(reference)
    expected_tasks = {
        (seed, sector, chain)
        for seed in SEEDS
        for sector in ("ground", "tower")
        for chain in range(4)
    }
    if observed_tasks != expected_tasks:
        raise RuntimeError("measurement task set is not exact")

    readback_stdout = Path(attempt_readback_job["stdout_path"])
    if "PHASE6_ATTEMPT_READBACK=passed" not in readback_stdout.read_text(
        encoding="utf-8"
    ):
        raise RuntimeError("attempt readback marker missing")
    jobs = {
        "training_attempt": require_job(**training_job),
        "attempt_readback": require_job(**attempt_readback_job),
        "measurement": require_job(**measurement_job),
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_revisions": {
            "checkpoint_producer": producer_revision,
            "measurement": measurement_revision,
            "finalizer": finalizer_revision,
            "finalizer_tree": finalizer_tree,
            "finalizer_clean": True,
        },
        "phase6a_certificate": artifact(phase6a_path),
        "input_attempt": artifact(attempt_path),
        "measurement_certificate": artifact(measurement_path),
        "architecture": architecture,
        "seed_artifacts": seed_artifacts,
        "training_blind_access_audit": artifact(audit_path),
        "measurement_tasks": task_references,
        "jobs": jobs,
        "finalizer_job": finalizer_job,
        "gates": {
            "phase6a_valid": True,
            "input_attempt_schema_valid": True,
            "sole_input_failure_gap_precision": True,
            "measurement_schema_valid": True,
            "measurement_all_gates_passed": True,
            "architecture_schema_hash_valid": True,
            "three_checkpoint_schema_hashes_valid": True,
            "three_symmetry_schema_hashes_valid": True,
            "training_blind_audit_valid": True,
            "exact_measurement_task_set_valid": True,
            "measurement_task_logs_hash_valid": True,
            "slurm_evidence_valid": True,
            "clean_traceable_source_revisions": True,
            "gpu_finalizer_allocation": True,
        },
        "architecture_frozen": True,
        "checkpoints_frozen": True,
        "checkpoint_selection_used_ed": False,
        "ed_accessed": False,
        "passed": True,
    }
    validate(payload, MODULE_ROOT / "phase6-final-v2.schema.json")
    return payload


def verify(final_path: Path, repo_root: Path) -> dict[str, Any]:
    final = load_json(final_path)
    validate(final, MODULE_ROOT / "phase6-final-v2.schema.json")
    checks = {
        "final_schema_valid": True,
        "finalizer_revision_available": True,
        "producer_revision_available": True,
        "measurement_revision_available": True,
        "source_clean": not bool(
            git_output(repo_root, "status", "--porcelain")
        ),
    }
    for revision in (
        final["source_revisions"]["checkpoint_producer"],
        final["source_revisions"]["measurement"],
        final["source_revisions"]["finalizer"],
    ):
        require_commit(repo_root, revision)
    references = [
        final["phase6a_certificate"],
        final["input_attempt"],
        final["measurement_certificate"],
        final["architecture"],
        final["training_blind_access_audit"],
    ]
    references.extend(
        reference
        for seed in final["seed_artifacts"]
        for reference in (seed["checkpoint"], seed["symmetry"])
    )
    references.extend(
        reference
        for task in final["measurement_tasks"]
        for reference in (
            task["certificate"],
            task["stdout"],
            task["stderr"],
        )
    )
    references.extend(
        reference
        for job in final["jobs"].values()
        for reference in (job["stdout"], job["stderr"], job["sacct"])
    )
    checks["all_artifact_hashes"] = all(
        sha256_file(Path(reference["path"])) == reference["sha256"]
        for reference in references
    )
    schemas_valid = True
    try:
        validate(
            load_json(Path(final["phase6a_certificate"]["path"])),
            MODULE_ROOT / "phase6a.schema.json",
        )
        validate(
            load_json(Path(final["input_attempt"]["path"])),
            MODULE_ROOT / "phase6-attempt.schema.json",
        )
        validate(
            load_json(Path(final["measurement_certificate"]["path"])),
            MODULE_ROOT / "phase6-measurement.schema.json",
        )
        validate(
            load_json(Path(final["architecture"]["path"])),
            Path(final["architecture"]["schema_path"]),
        )
        for seed in final["seed_artifacts"]:
            for reference in (seed["checkpoint"], seed["symmetry"]):
                validate(
                    load_json(Path(reference["path"])),
                    Path(reference["schema_path"]),
                )
        for task in final["measurement_tasks"]:
            validate(
                load_json(Path(task["certificate"]["path"])),
                MODULE_ROOT / "phase6-measurement-task.schema.json",
            )
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        jsonschema.ValidationError,
    ):
        schemas_valid = False
    checks["all_artifact_schemas"] = schemas_valid
    checks["exact_seed_set"] = [
        item["seed"] for item in final["seed_artifacts"]
    ] == list(SEEDS)
    checks["exact_task_set"] = {
        (item["seed"], item["sector"], item["chain"])
        for item in final["measurement_tasks"]
    } == {
        (seed, sector, chain)
        for seed in SEEDS
        for sector in ("ground", "tower")
        for chain in range(4)
    }
    return {
        "schema_version": READBACK_VERSION,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "final_certificate": artifact(final_path),
        "source_revisions": final["source_revisions"],
        "checks": checks,
        "passed": all(checks.values()),
    }


def job_arguments(args: argparse.Namespace, prefix: str) -> dict[str, Any]:
    attribute_prefix = prefix.replace("-", "_")
    return {
        "job_id": getattr(args, f"{attribute_prefix}_job_id"),
        "state": getattr(args, f"{attribute_prefix}_state"),
        "exit_code": getattr(args, f"{attribute_prefix}_exit_code"),
        "stdout_path": getattr(args, f"{attribute_prefix}_stdout").resolve(),
        "stderr_path": getattr(args, f"{attribute_prefix}_stderr").resolve(),
        "sacct_path": getattr(args, f"{attribute_prefix}_sacct").resolve(),
    }


def add_job_arguments(parser: argparse.ArgumentParser, prefix: str) -> None:
    parser.add_argument(f"--{prefix}-job-id", required=True)
    parser.add_argument(f"--{prefix}-state", required=True)
    parser.add_argument(f"--{prefix}-exit-code", required=True)
    parser.add_argument(f"--{prefix}-stdout", required=True, type=Path)
    parser.add_argument(f"--{prefix}-stderr", required=True, type=Path)
    parser.add_argument(f"--{prefix}-sacct", required=True, type=Path)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--repo-root", required=True, type=Path)
    finalize_parser.add_argument("--attempt", required=True, type=Path)
    finalize_parser.add_argument("--measurement", required=True, type=Path)
    finalize_parser.add_argument("--phase6a", required=True, type=Path)
    finalize_parser.add_argument("--output", required=True, type=Path)
    for prefix in ("training", "attempt-readback", "measurement"):
        add_job_arguments(finalize_parser, prefix)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--repo-root", required=True, type=Path)
    verify_parser.add_argument("--final", required=True, type=Path)
    verify_parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "finalize":
        payload = finalize(
            repo_root=args.repo_root.resolve(),
            attempt_path=args.attempt.resolve(),
            measurement_path=args.measurement.resolve(),
            phase6a_path=args.phase6a.resolve(),
            training_job=job_arguments(args, "training"),
            attempt_readback_job=job_arguments(args, "attempt_readback"),
            measurement_job=job_arguments(args, "measurement"),
        )
    else:
        payload = verify(args.final.resolve(), args.repo_root.resolve())
        validate(
            payload,
            MODULE_ROOT / "phase6-final-v2-readback.schema.json",
        )
    write_json(args.output.resolve(), payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
