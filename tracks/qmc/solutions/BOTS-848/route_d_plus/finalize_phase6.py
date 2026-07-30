"""Finalize and independently read back the Route D+ Phase 6 exit gate."""

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

SCHEMA_VERSION = "challenge-15-route-d-plus-phase6-final-v1"
READBACK_VERSION = "challenge-15-route-d-plus-phase6-readback-v1"
MODULE_ROOT = Path(__file__).resolve().parent


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


def validate_payload(payload: dict[str, Any], schema_path: Path) -> None:
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
    validate_payload(payload, schema_path)
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
        raise RuntimeError("Phase 6 finalization requires Slurm")
    if not visible or visible in {"-1", "NoDevFiles"}:
        raise RuntimeError("Phase 6 finalization requires a GPU allocation")
    return {
        "job_id": job_id,
        "cluster_name": cluster,
        "hostname": platform.node(),
        "gpu_visible": visible,
    }


def finalize(
    *,
    repo_root: Path,
    phase6_path: Path,
    phase6a_path: Path,
    stdout_path: Path,
    stderr_path: Path,
    sacct_path: Path,
) -> dict[str, Any]:
    readback_job = require_gpu_slurm()
    revision = git_output(repo_root, "rev-parse", "HEAD")
    tree = git_output(repo_root, "rev-parse", "HEAD^{tree}")
    if git_output(repo_root, "status", "--porcelain"):
        raise RuntimeError("Phase 6 finalization requires a clean worktree")

    phase6 = load_json(phase6_path)
    validate_payload(phase6, MODULE_ROOT / "phase6.schema.json")
    if not phase6["passed"] or phase6["ed_accessed"]:
        raise RuntimeError("Phase 6 training certificate is not an exit")
    if phase6["git_commit"] != revision:
        raise RuntimeError("Phase 6 source revision differs from checkout")
    if sha256_file(phase6a_path) != phase6["phase6a_certificate_sha256"]:
        raise RuntimeError("Phase 6A certificate hash mismatch")
    phase6a_payload = load_json(phase6a_path)
    validate_payload(
        phase6a_payload,
        MODULE_ROOT / "phase6a.schema.json",
    )
    if not phase6a_payload["passed"]:
        raise RuntimeError("Phase 6A certificate did not pass")

    architecture_reference = phase6["architecture"]
    architecture_path = Path(architecture_reference["path"])
    architecture_schema = Path(architecture_reference["schema_path"])
    if sha256_file(architecture_path) != architecture_reference["sha256"]:
        raise RuntimeError("architecture hash mismatch")
    if sha256_file(architecture_schema) != architecture_reference["schema_sha256"]:
        raise RuntimeError("architecture schema hash mismatch")
    architecture = schema_artifact(architecture_path, architecture_schema)

    seed_artifacts = []
    for reference in phase6["checkpoints"]:
        checkpoint_path = Path(reference["path"])
        checkpoint_schema = Path(reference["schema_path"])
        symmetry_path = Path(reference["symmetry_path"])
        symmetry_schema = MODULE_ROOT / "symmetry.schema.json"
        if sha256_file(checkpoint_path) != reference["sha256"]:
            raise RuntimeError("checkpoint hash mismatch")
        if sha256_file(checkpoint_schema) != reference["schema_sha256"]:
            raise RuntimeError("checkpoint schema hash mismatch")
        if sha256_file(symmetry_path) != reference["symmetry_sha256"]:
            raise RuntimeError("symmetry hash mismatch")
        if sha256_file(symmetry_schema) != reference["symmetry_schema_sha256"]:
            raise RuntimeError("symmetry schema hash mismatch")
        seed_artifacts.append(
            {
                "seed": reference["seed"],
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
    if [item["seed"] for item in seed_artifacts] != [848, 1848, 2848]:
        raise RuntimeError("Phase 6 seed artifact set is not exact")

    audit_path = Path(phase6["blind_access_audit"]["path"])
    if sha256_file(audit_path) != phase6["blind_access_audit"]["sha256"]:
        raise RuntimeError("blind access audit hash mismatch")
    audit = load_json(audit_path)
    if (
        audit["denied_events"]
        or audit["loaded_forbidden_before"]
        or audit["loaded_forbidden_after"]
    ):
        raise RuntimeError("blind access audit is not empty")

    sacct_text = sacct_path.read_text(encoding="utf-8")
    job_id = str(phase6["slurm_job_id"])
    if (
        job_id not in sacct_text
        or "COMPLETED" not in sacct_text
        or "0:0" not in sacct_text
        or "gres/gpu=1" not in sacct_text
    ):
        raise RuntimeError("training sacct evidence is incomplete")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_revision": revision,
        "source_tree": tree,
        "source_clean": True,
        "phase6_certificate": artifact(phase6_path),
        "phase6a_certificate": artifact(phase6a_path),
        "architecture": architecture,
        "seed_artifacts": seed_artifacts,
        "blind_access_audit": artifact(audit_path),
        "training_job": {
            "job_id": job_id,
            "cluster_name": str(phase6["slurm_cluster_name"]),
            "state": "COMPLETED",
            "exit_code": "0:0",
            "stdout": artifact(stdout_path),
            "stderr": artifact(stderr_path),
            "sacct": artifact(sacct_path),
        },
        "readback_job": readback_job,
        "gates": {
            "phase6_schema_valid": True,
            "phase6a_hash_valid": True,
            "architecture_schema_hash_valid": True,
            "three_checkpoint_schema_hashes_valid": True,
            "three_symmetry_schema_hashes_valid": True,
            "blind_access_audit_valid": True,
            "training_logs_hash_valid": True,
            "training_slurm_completed": True,
            "clean_consistent_source_revision": True,
            "gpu_readback_allocation": True,
        },
        "architecture_frozen": True,
        "checkpoints_frozen": True,
        "ed_accessed": False,
        "passed": True,
    }
    validate_payload(payload, MODULE_ROOT / "phase6-final.schema.json")
    return payload


def verify(final_path: Path, repo_root: Path) -> dict[str, Any]:
    final = load_json(final_path)
    validate_payload(final, MODULE_ROOT / "phase6-final.schema.json")
    checks: dict[str, bool] = {
        "final_schema_valid": True,
        "source_revision": (
            final["source_revision"]
            == git_output(repo_root, "rev-parse", "HEAD")
        ),
        "source_clean": not bool(
            git_output(repo_root, "status", "--porcelain")
        ),
    }
    references = [
        final["phase6_certificate"],
        final["phase6a_certificate"],
        final["architecture"],
        final["blind_access_audit"],
        final["training_job"]["stdout"],
        final["training_job"]["stderr"],
        final["training_job"]["sacct"],
    ]
    for seed in final["seed_artifacts"]:
        references.extend((seed["checkpoint"], seed["symmetry"]))
    checks["all_artifact_hashes"] = all(
        sha256_file(Path(reference["path"])) == reference["sha256"]
        for reference in references
    )
    schema_references = [
        final["architecture"],
        *[
            reference
            for seed in final["seed_artifacts"]
            for reference in (seed["checkpoint"], seed["symmetry"])
        ],
    ]
    schemas_valid = True
    try:
        for reference in schema_references:
            if (
                sha256_file(Path(reference["schema_path"]))
                != reference["schema_sha256"]
            ):
                schemas_valid = False
                break
            validate_payload(
                load_json(Path(reference["path"])),
                Path(reference["schema_path"]),
            )
    except (FileNotFoundError, json.JSONDecodeError, jsonschema.ValidationError):
        schemas_valid = False
    checks["all_artifact_schemas"] = schemas_valid
    checks["exact_seed_set"] = [
        item["seed"] for item in final["seed_artifacts"]
    ] == [848, 1848, 2848]
    return {
        "schema_version": READBACK_VERSION,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "final_certificate": artifact(final_path),
        "source_revision": final["source_revision"],
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--repo-root", required=True, type=Path)
    finalize_parser.add_argument("--phase6", required=True, type=Path)
    finalize_parser.add_argument("--phase6a", required=True, type=Path)
    finalize_parser.add_argument("--stdout", required=True, type=Path)
    finalize_parser.add_argument("--stderr", required=True, type=Path)
    finalize_parser.add_argument("--sacct", required=True, type=Path)
    finalize_parser.add_argument("--output", required=True, type=Path)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--repo-root", required=True, type=Path)
    verify_parser.add_argument("--final", required=True, type=Path)
    verify_parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "finalize":
        payload = finalize(
            repo_root=args.repo_root.resolve(),
            phase6_path=args.phase6.resolve(),
            phase6a_path=args.phase6a.resolve(),
            stdout_path=args.stdout.resolve(),
            stderr_path=args.stderr.resolve(),
            sacct_path=args.sacct.resolve(),
        )
    else:
        payload = verify(
            args.final.resolve(),
            args.repo_root.resolve(),
        )
        validate_payload(
            payload,
            MODULE_ROOT / "phase6-readback.schema.json",
        )
    write_json(args.output.resolve(), payload)
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
