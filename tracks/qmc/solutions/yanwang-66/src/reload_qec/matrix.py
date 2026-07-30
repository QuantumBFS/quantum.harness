"""Generate and execute the frozen 2240-cell discovery matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .candidate import run as run_candidate
from .config import SimulationRequest


MATRIX_SCHEMA = "q66-discovery-matrix-v1"


class MatrixError(ValueError):
    """Raised when a discovery matrix is incomplete or inconsistent."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def _probability_token(value: float) -> str:
    return f"{value:.4g}".replace(".", "p").replace("-", "m").replace("+", "p")


def _policy_token(policy: dict[str, Any]) -> str:
    if policy["name"] in {"none", "immediate"}:
        return policy["name"]
    if policy["name"] == "periodic":
        return f"periodic-{policy['interval']}"
    if policy["name"] == "threshold":
        return f"threshold-{_probability_token(float(policy['fraction']))}"
    raise MatrixError(f"unsupported policy {policy!r}")


def _resolve_rounds(value: Any, distance: int) -> int:
    if value == "d":
        return distance
    if value == "2d":
        return 2 * distance
    raise MatrixError(f"unsupported rounds token {value!r}")


def _resolve_policy(value: dict[str, Any], distance: int) -> dict[str, Any]:
    policy = dict(value)
    if policy.get("name") == "periodic":
        if policy.get("interval") == "d":
            policy["interval"] = distance
        elif policy.get("interval") == "2d":
            policy["interval"] = 2 * distance
    return policy


def generate_matrix(
    families: dict[str, Any],
    *,
    instance_file: Path,
    source_commit: str,
    environment_lock_sha256: str,
    shots: int,
    shard_size: int,
) -> dict[str, Any]:
    if families.get("schema_version") != "q66-benchmark-family-v1":
        raise MatrixError("unsupported benchmark family schema")
    groups = []
    for distance in families["distance"]:
        for rounds_token in families["rounds"]:
            rounds = _resolve_rounds(rounds_token, distance)
            for basis in families["basis"]:
                for p, p_m in families["pauli_measurement_pairs"]:
                    for p_loss in families["loss_probability"]:
                        physical_key = {
                            "distance": distance,
                            "rounds": rounds,
                            "basis": basis,
                            "p": p,
                            "p_m": p_m,
                            "p_loss": p_loss,
                        }
                        seed_digest = hashlib.sha256(
                            b"q66-discovery-seed-v1\0" + _canonical_bytes(physical_key)
                        ).digest()
                        master_seed = int.from_bytes(seed_digest[:8], "little")
                        requests = []
                        for policy_value in families["policies"]:
                            policy = _resolve_policy(policy_value, distance)
                            run_id = "-".join(
                                (
                                    "disc",
                                    f"d{distance}",
                                    f"t{rounds}",
                                    basis.lower(),
                                    f"p{_probability_token(float(p))}",
                                    f"pm{_probability_token(float(p_m))}",
                                    f"pl{_probability_token(float(p_loss))}",
                                    _policy_token(policy),
                                )
                            )
                            requests.append(
                                {
                                    "schema_version": "q66-simulation-request-v1",
                                    "run_id": run_id,
                                    "instance_file": str(instance_file),
                                    "distance": distance,
                                    "rounds": rounds,
                                    "basis": basis,
                                    "shots": shots,
                                    "shot_start": 0,
                                    "shard_size": shard_size,
                                    "master_seed": master_seed,
                                    "noise": {"p": p, "p_m": p_m, "p_loss": p_loss},
                                    "reload": dict(families["ideal_reload"]),
                                    "policy": policy,
                                    "provenance": {
                                        "source_commit": source_commit,
                                        "environment_lock_sha256": environment_lock_sha256,
                                    },
                                }
                            )
                        groups.append(
                            {
                                "group_index": len(groups),
                                "physical_key": physical_key,
                                "requests": requests,
                            }
                        )
    matrix = {
        "schema_version": MATRIX_SCHEMA,
        "groups": groups,
        "group_count": len(groups),
        "cell_count": sum(len(group["requests"]) for group in groups),
        "shots_per_cell": shots,
        "shard_size": shard_size,
        "source_commit": source_commit,
        "environment_lock_sha256": environment_lock_sha256,
        "family_provenance": families["provenance"],
    }
    if matrix["group_count"] != 280 or matrix["cell_count"] != 2_240:
        raise MatrixError(
            f"frozen matrix expanded to {matrix['group_count']} groups/"
            f"{matrix['cell_count']} cells instead of 280/2240"
        )
    run_ids = [
        request["run_id"]
        for group in groups
        for request in group["requests"]
    ]
    if len(set(run_ids)) != len(run_ids):
        raise MatrixError("matrix contains duplicate run IDs")
    return matrix


def load_matrix(path: Path) -> dict[str, Any]:
    matrix = json.loads(path.read_text(encoding="ascii"))
    if matrix.get("schema_version") != MATRIX_SCHEMA:
        raise MatrixError("unsupported matrix schema")
    if len(matrix.get("groups", [])) != matrix.get("group_count"):
        raise MatrixError("matrix group count mismatch")
    return matrix


def run_group(matrix_path: Path, group_index: int, output_root: Path) -> dict[str, Any]:
    matrix = load_matrix(matrix_path)
    if not 0 <= group_index < matrix["group_count"]:
        raise MatrixError(f"group index {group_index} outside matrix")
    group = matrix["groups"][group_index]
    if group["group_index"] != group_index:
        raise MatrixError("matrix group ordering mismatch")
    group_root = output_root / f"group-{group_index:03d}"
    if group_root.exists():
        raise FileExistsError(f"group output already exists: {group_root}")
    group_root.mkdir(parents=True)
    manifests = []
    for request_value in group["requests"]:
        request = SimulationRequest.from_dict(request_value)
        manifests.append(
            run_candidate(request, group_root / request.run_id, precheck=False)
        )
    matrix_sha256 = hashlib.sha256(matrix_path.read_bytes()).hexdigest()
    group_manifest = {
        "schema_version": "q66-discovery-group-v1",
        "matrix_sha256": matrix_sha256,
        "group_index": group_index,
        "slurm_array_job_id": os.environ.get("SLURM_ARRAY_JOB_ID"),
        "slurm_array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID"),
        "runs": [manifest["run_id"] for manifest in manifests],
    }
    (group_root / "group-manifest.json").write_text(
        json.dumps(group_manifest, sort_keys=True, indent=2) + "\n",
        encoding="ascii",
    )
    return group_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate")
    generate.add_argument("--families", type=Path, required=True)
    generate.add_argument("--instances", type=Path, required=True)
    generate.add_argument("--source-commit", required=True)
    generate.add_argument("--environment-lock-sha256", required=True)
    generate.add_argument("--shots", type=int, default=20_000)
    generate.add_argument("--shard-size", type=int, default=4_096)
    generate.add_argument("--out", type=Path, required=True)
    execute = subparsers.add_parser("run-group")
    execute.add_argument("--matrix", type=Path, required=True)
    execute.add_argument("--group-index", type=int, required=True)
    execute.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "generate":
        families = json.loads(args.families.read_text(encoding="utf-8"))
        matrix = generate_matrix(
            families,
            instance_file=args.instances,
            source_commit=args.source_commit,
            environment_lock_sha256=args.environment_lock_sha256,
            shots=args.shots,
            shard_size=args.shard_size,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(matrix, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="ascii",
        )
        print(
            json.dumps(
                {
                    "out": str(args.out),
                    "groups": matrix["group_count"],
                    "cells": matrix["cell_count"],
                },
                sort_keys=True,
            )
        )
    elif args.command == "run-group":
        print(
            json.dumps(
                run_group(args.matrix, args.group_index, args.output_root),
                sort_keys=True,
            )
        )
    else:
        raise MatrixError(f"unsupported command {args.command!r}")


if __name__ == "__main__":
    main()
