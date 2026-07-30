"""Independent hash/schema readback for D+0 optimizer remediation."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import jsonschema

from route_d_plus.future.verify import load_json, sha256_file

MODULE_ROOT = Path(__file__).resolve().parent
SEEDS = (848, 1848, 2848)


def artifact(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    return {"path": str(resolved), "sha256": sha256_file(resolved)}


def validate(payload: dict[str, Any], schema_name: str) -> None:
    schema = load_json(MODULE_ROOT / schema_name)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    ).validate(payload)


def require(reference: dict[str, str]) -> Path:
    path = Path(reference["path"]).resolve()
    if sha256_file(path) != reference["sha256"]:
        raise RuntimeError(f"artifact hash mismatch: {path}")
    return path


def git_output(repo_root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def slurm() -> dict[str, Any]:
    visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if not os.environ.get("SLURM_JOB_ID") or not visible:
        raise RuntimeError("readback requires a Slurm GPU allocation")
    return {
        "job_id": os.environ["SLURM_JOB_ID"],
        "cluster_name": os.environ.get("SLURM_CLUSTER_NAME", "hpccube-xh5"),
        "node_list": os.environ.get("SLURM_NODELIST", "unknown"),
        "partition": os.environ.get("SLURM_JOB_PARTITION", "unknown"),
        "gpu_devices": [part for part in visible.split(",") if part],
    }


def verify(
    *,
    repo_root: Path,
    certificate_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    revision = git_output(repo_root, "rev-parse", "HEAD")
    if git_output(repo_root, "status", "--porcelain"):
        raise RuntimeError("readback requires a clean source checkout")
    certificate = load_json(certificate_path)
    validate(certificate, "optimization-remediation.schema.json")
    subprocess.run(
        ["git", "cat-file", "-e", f"{certificate['source_revision']}^{{commit}}"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )

    phase7_path = require(certificate["phase7_stage_gate"])
    phase7 = load_json(phase7_path)
    validate(phase7, "future/stage-gate.schema.json")
    if (
        phase7["decision"]["benchmark_classification"]
        != "optimization-failure"
    ):
        raise RuntimeError("remediation trigger changed")
    protocol_path = require(certificate["protocol"])
    validate(
        load_json(protocol_path),
        "optimization-remediation-protocol.schema.json",
    )
    architecture_path = require(certificate["architecture"])
    validate(load_json(architecture_path), "architecture.schema.json")

    observed = []
    references = []
    for reference in certificate["seed_results"]:
        result_path = require(reference["result"])
        result = load_json(result_path)
        validate(
            result, "optimization-remediation-seed.schema.json"
        )
        checkpoint_path = require(reference["checkpoint"])
        checkpoint = load_json(checkpoint_path)
        validate(checkpoint, "remediated-checkpoint.schema.json")
        require(checkpoint["base_checkpoint"])
        if (
            result["seed"] != reference["seed"]
            or checkpoint["seed"] != reference["seed"]
            or result["checkpoint"]["sha256"]
            != reference["checkpoint"]["sha256"]
        ):
            raise RuntimeError("seed remediation lineage mismatch")
        observed.append(reference["seed"])
        references.append(reference)
    if tuple(sorted(observed)) != SEEDS:
        raise RuntimeError("remediation seed set is not exact")

    payload = {
        "schema_version": (
            "challenge-15-route-d-plus-optimization-"
            "remediation-readback-v1"
        ),
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_revision": certificate["source_revision"],
        "verifier_revision": revision,
        "remediation_certificate": artifact(certificate_path),
        "seed_results": references,
        "slurm": slurm(),
        "gates": {
            "aggregate_schema_valid": True,
            "aggregate_hash_valid": True,
            "phase7_trigger_hash_valid": True,
            "protocol_hash_and_schema_valid": True,
            "architecture_hash_and_schema_valid": True,
            "exact_three_seed_set": True,
            "all_seed_hashes_and_schemas_valid": True,
            "all_checkpoint_hashes_and_schemas_valid": True,
            "all_base_checkpoint_hashes_valid": True,
            "clean_traceable_source_revisions": True,
            "gpu_slurm_evidence": True,
        },
        "passed": True,
    }
    validate(
        payload, "optimization-remediation-readback.schema.json"
    )
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--certificate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    payload = verify(
        repo_root=arguments.repo_root.resolve(),
        certificate_path=arguments.certificate.resolve(),
        output_path=arguments.output.resolve(),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
