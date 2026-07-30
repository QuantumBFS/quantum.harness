"""Fixed-budget D+0 optimizer remediation after Phase 7 diagnosis."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import multiprocessing
import os
import subprocess
from pathlib import Path
from typing import Any

import jsonschema
import numpy as np

from route_d_plus.future.verify import load_json, sha256_file
from route_d_plus.train_dplus0 import train_seed

MODULE_ROOT = Path(__file__).resolve().parent
SEEDS = (848, 1848, 2848)
FORBIDDEN_SOURCE_TOKENS = (
    "benchmark_v0.ed_oracle",
    "benchmark_v0.fock_ed",
    "run_ed_oracle",
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def artifact(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    return {"path": str(resolved), "sha256": sha256_file(resolved)}


def validate(payload: dict[str, Any], schema_name: str) -> None:
    schema = load_json(MODULE_ROOT / schema_name)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    ).validate(payload)


def git_output(repo_root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def require_clean_revision(repo_root: Path) -> str:
    revision = git_output(repo_root, "rev-parse", "HEAD")
    if git_output(repo_root, "status", "--porcelain"):
        raise RuntimeError("remediation requires a clean source checkout")
    return revision


def _memory_mb() -> int:
    raw = (
        os.environ.get("SLURM_MEM_PER_NODE")
        or os.environ.get("SLURM_MEM_PER_CPU")
        or ""
    )
    if raw.lower().endswith("g"):
        return int(raw[:-1]) * 1024
    return int(raw)


def _slurm() -> dict[str, Any]:
    visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if not os.environ.get("SLURM_JOB_ID") or not visible:
        raise RuntimeError("remediation requires a Slurm GPU allocation")
    return {
        "job_id": os.environ["SLURM_JOB_ID"],
        "cluster_name": os.environ.get("SLURM_CLUSTER_NAME", "hpccube-xh5"),
        "node_list": os.environ.get("SLURM_NODELIST", "unknown"),
        "partition": os.environ.get("SLURM_JOB_PARTITION", "unknown"),
        "gpu_devices": [part for part in visible.split(",") if part],
        "cpus_per_task": int(os.environ.get("SLURM_CPUS_PER_TASK", "0")),
        "memory_mb": _memory_mb(),
    }


def _source_audit() -> None:
    for path in (
        MODULE_ROOT / "train_dplus0.py",
        MODULE_ROOT / "vmc.py",
        MODULE_ROOT / "coordinate.py",
    ):
        source = path.read_text(encoding="utf-8")
        matches = [
            token for token in FORBIDDEN_SOURCE_TOKENS if token in source
        ]
        if matches:
            raise RuntimeError(
                f"forbidden ED import/reference in optimizer source: "
                f"{path}: {matches}"
            )


def _run_one(request: dict[str, Any]) -> dict[str, Any]:
    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    result, checkpoint = train_seed(
        request["seed"],
        architecture=request["architecture"],
        architecture_sha256=request["architecture_sha256"],
        chains=request["protocol"]["chains"],
        updates=request["protocol"]["additional_updates"],
        samples_per_update=request["protocol"][
            "samples_per_update_per_chain"
        ],
        proposal_sweeps=request["protocol"]["proposal_sweeps"],
        final_samples_per_chain=request["protocol"][
            "final_samples_per_chain"
        ],
        initial_checkpoint=request["base_checkpoint"],
        learning_rate=request["protocol"]["learning_rate"],
        diagonal_shift=request["protocol"]["diagonal_shift"],
        trust_radius=request["protocol"]["trust_radius"],
        checkpoint_selection=request["protocol"]["checkpoint_selection"],
    )
    return {
        "started_at_utc": started_at,
        "finished_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "result": result,
        "checkpoint": checkpoint,
    }


def _finite(value: Any) -> bool:
    if isinstance(value, dict):
        return all(_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(_finite(item) for item in value)
    if isinstance(value, (float, np.floating)):
        return bool(np.isfinite(value))
    return True


def run(
    *,
    repo_root: Path,
    phase7_stage_gate_path: Path,
    protocol_path: Path,
    architecture_path: Path,
    checkpoint_paths: list[Path],
    output_dir: Path,
    output_path: Path,
) -> dict[str, Any]:
    revision = require_clean_revision(repo_root)
    _source_audit()
    phase7_gate = load_json(phase7_stage_gate_path)
    validate(phase7_gate, "future/stage-gate.schema.json")
    decision = phase7_gate["decision"]
    if (
        decision["benchmark_classification"] != "optimization-failure"
        or decision["capacity_action"] != "keep-D+0"
        or decision["capacity_protocol_modified"]
        or decision["checkpoint_modified"]
    ):
        raise RuntimeError("Phase 7 did not authorize D+0 optimizer remediation")
    protocol = load_json(protocol_path)
    validate(protocol, "optimization-remediation-protocol.schema.json")
    architecture = load_json(architecture_path)
    validate(architecture, "architecture.schema.json")
    architecture_sha256 = sha256_file(architecture_path)
    if len(checkpoint_paths) != 3:
        raise ValueError("remediation requires exactly three checkpoints")
    base_by_seed = {}
    path_by_seed = {}
    for path in checkpoint_paths:
        checkpoint = load_json(path)
        validate(checkpoint, "checkpoint.schema.json")
        seed = checkpoint["seed"]
        if seed in base_by_seed:
            raise ValueError(f"duplicate checkpoint seed: {seed}")
        if checkpoint["architecture_sha256"] != architecture_sha256:
            raise RuntimeError("checkpoint architecture hash mismatch")
        base_by_seed[seed] = checkpoint
        path_by_seed[seed] = path
    if tuple(sorted(base_by_seed)) != SEEDS:
        raise ValueError("checkpoint seeds differ from remediation protocol")

    requests = [
        {
            "seed": seed,
            "architecture": architecture,
            "architecture_sha256": architecture_sha256,
            "base_checkpoint": base_by_seed[seed],
            "protocol": protocol,
        }
        for seed in SEEDS
    ]
    context = multiprocessing.get_context("spawn")
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=3, mp_context=context
    ) as executor:
        completed = list(executor.map(_run_one, requests))

    output_dir.mkdir(parents=True, exist_ok=True)
    references = []
    intervals = []
    for seed, payload in zip(SEEDS, completed, strict=True):
        seed_dir = output_dir / f"seed-{seed}"
        seed_dir.mkdir(parents=True, exist_ok=True)
        raw_checkpoint = payload["checkpoint"]
        remediated_checkpoint = {
            "schema_version": (
                "challenge-15-route-d-plus-remediated-checkpoint-v1"
            ),
            "seed": seed,
            "n_electrons": 6,
            "two_q": 15,
            "capacity": "D+0",
            "architecture_sha256": architecture_sha256,
            "source_revision": revision,
            "base_checkpoint": artifact(path_by_seed[seed]),
            "ground_coefficients": raw_checkpoint["ground_coefficients"],
            "tower_coefficients": raw_checkpoint["tower_coefficients"],
            "additional_updates": protocol["additional_updates"],
            "total_updates": (
                base_by_seed[seed]["updates"]
                + protocol["additional_updates"]
            ),
            "chains": protocol["chains"],
            "samples_per_update_per_chain": protocol[
                "samples_per_update_per_chain"
            ],
            "proposal_sweeps": protocol["proposal_sweeps"],
            "learning_rate": protocol["learning_rate"],
            "diagonal_shift": protocol["diagonal_shift"],
            "trust_radius": protocol["trust_radius"],
            "final_samples_per_chain": protocol[
                "final_samples_per_chain"
            ],
            "checkpoint_selection": protocol["checkpoint_selection"],
            "ed_used_for_gradient": False,
            "ed_used_for_checkpoint_selection": False,
        }
        validate(
            remediated_checkpoint, "remediated-checkpoint.schema.json"
        )
        checkpoint_path = seed_dir / "checkpoint.json"
        write_json(checkpoint_path, remediated_checkpoint)

        result = payload["result"]
        finite = _finite(result)
        seed_certificate = {
            "schema_version": (
                "challenge-15-route-d-plus-optimization-"
                "remediation-seed-v1"
            ),
            "seed": seed,
            "source_revision": revision,
            "started_at_utc": payload["started_at_utc"],
            "finished_at_utc": payload["finished_at_utc"],
            "base_checkpoint": artifact(path_by_seed[seed]),
            "checkpoint": artifact(checkpoint_path),
            "initial_objective": result["initial_objective"],
            "final_training_objective": result[
                "final_training_objective"
            ],
            "final_ground": result["final_ground"],
            "final_tower": result["final_tower"],
            "final_gap": result["final_gap"],
            "final_gap_standard_error": result[
                "final_gap_standard_error"
            ],
            "trace": result["trace"],
            "gates": {
                "finite_trace": finite,
                "fixed_update_count": len(result["trace"]) == 48,
                "checkpoint_schema_valid": True,
                "no_ed_gradient": True,
                "no_ed_checkpoint_selection": True,
            },
            "passed": bool(finite and len(result["trace"]) == 48),
        }
        validate(
            seed_certificate,
            "optimization-remediation-seed.schema.json",
        )
        result_path = seed_dir / "seed-certificate.json"
        write_json(result_path, seed_certificate)
        references.append(
            {
                "seed": seed,
                "result": artifact(result_path),
                "checkpoint": artifact(checkpoint_path),
            }
        )
        intervals.append(
            (
                dt.datetime.fromisoformat(payload["started_at_utc"]),
                dt.datetime.fromisoformat(payload["finished_at_utc"]),
            )
        )

    ran_concurrently = (
        max(started for started, _ in intervals)
        < min(finished for _, finished in intervals)
    )
    certificate = {
        "schema_version": (
            "challenge-15-route-d-plus-optimization-remediation-v1"
        ),
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_revision": revision,
        "git_dirty": False,
        "phase7_stage_gate": artifact(phase7_stage_gate_path),
        "protocol": artifact(protocol_path),
        "architecture": artifact(architecture_path),
        "seed_results": references,
        "slurm": _slurm(),
        "gates": {
            "phase7_optimization_failure": True,
            "protocol_schema_valid": True,
            "architecture_unchanged": True,
            "three_seed_concurrent_execution": ran_concurrently,
            "all_seed_schemas_valid": True,
            "clean_source_revision": True,
            "gpu_slurm_evidence": True,
            "capacity_unchanged": True,
            "no_ed_gradient": True,
            "no_ed_checkpoint_selection": True,
        },
        "passed": bool(ran_concurrently),
    }
    validate(certificate, "optimization-remediation.schema.json")
    write_json(output_path, certificate)
    return certificate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--phase7-stage-gate", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--architecture", required=True, type=Path)
    parser.add_argument(
        "--checkpoint", required=True, action="append", type=Path
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    payload = run(
        repo_root=arguments.repo_root.resolve(),
        phase7_stage_gate_path=arguments.phase7_stage_gate.resolve(),
        protocol_path=arguments.protocol.resolve(),
        architecture_path=arguments.architecture.resolve(),
        checkpoint_paths=[
            path.resolve() for path in arguments.checkpoint
        ],
        output_dir=arguments.output_dir.resolve(),
        output_path=arguments.output.resolve(),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
