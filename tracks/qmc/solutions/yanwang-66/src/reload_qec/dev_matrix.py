"""Generate the frozen public development-validator request matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .config import SimulationRequest


FAMILY_SCHEMA = "q66-dev-validator-family-v1"
MATRIX_SCHEMA = "q66-dev-validator-matrix-v1"
EXPECTED_POLICIES = (
    {"name": "none"},
    {"name": "immediate"},
    {"name": "periodic", "interval": "d"},
    {"name": "threshold", "fraction": 0.05},
)
EXPECTED_WORKLOADS = (
    {
        "workload_id": "dev-d3-t3-x",
        "distance": 3,
        "rounds": 3,
        "basis": "X",
        "noise": {"p": 0.001, "p_m": 0.001, "p_loss": 0.003},
    },
    {
        "workload_id": "dev-d3-t6-z",
        "distance": 3,
        "rounds": 6,
        "basis": "Z",
        "noise": {"p": 0.003, "p_m": 0.001, "p_loss": 0.01},
    },
    {
        "workload_id": "dev-d5-t5-x",
        "distance": 5,
        "rounds": 5,
        "basis": "X",
        "noise": {"p": 0.001, "p_m": 0.003, "p_loss": 0.003},
    },
    {
        "workload_id": "dev-d5-t10-z",
        "distance": 5,
        "rounds": 10,
        "basis": "Z",
        "noise": {"p": 0.003, "p_m": 0.003, "p_loss": 0.01},
    },
)
EXPECTED_RELOAD = {
    "delay_rounds": 0,
    "reset_error_probability": 0.0,
    "failure_probability": 0.0,
}


class DevMatrixError(ValueError):
    """Raised when the public validator family changes unexpectedly."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def _seed(workload: dict[str, Any]) -> int:
    digest = hashlib.sha256(
        b"q66-dev-validator-seed-v1\0" + _canonical_bytes(workload)
    ).digest()
    return int.from_bytes(digest[:8], "little")


def _policy(value: dict[str, Any], distance: int) -> dict[str, Any]:
    result = dict(value)
    if result.get("name") == "periodic" and result.get("interval") == "d":
        result["interval"] = distance
    return result


def generate_dev_matrix(
    family: dict[str, Any],
    *,
    instance_file: Path,
    source_commit: str,
    environment_lock_sha256: str,
) -> dict[str, Any]:
    if family.get("schema_version") != FAMILY_SCHEMA:
        raise DevMatrixError("unsupported development-validator family schema")
    if (
        family.get("shots_per_cell") != 2_048
        or family.get("shard_size") != 2_048
        or family.get("warmup_runs") != 1
        or family.get("timed_runs") != 3
    ):
        raise DevMatrixError("development timing/repetition contract changed")
    workloads = family.get("workloads")
    policies = family.get("policies")
    if not isinstance(workloads, list) or len(workloads) != 4:
        raise DevMatrixError("development matrix must contain four workloads")
    if not isinstance(policies, list) or len(policies) != 4:
        raise DevMatrixError("development matrix must contain four policies")
    if tuple(workloads) != EXPECTED_WORKLOADS:
        raise DevMatrixError("development workload values/order changed")
    if tuple(policies) != EXPECTED_POLICIES:
        raise DevMatrixError("development policy values/order changed")
    if family.get("reload") != EXPECTED_RELOAD:
        raise DevMatrixError("development reload controls changed")

    cells = []
    run_ids: set[str] = set()
    for workload_index, workload in enumerate(workloads):
        distance = int(workload["distance"])
        master_seed = _seed(workload)
        for policy_index, policy_value in enumerate(policies):
            policy = _policy(policy_value, distance)
            policy_token = policy["name"]
            if policy["name"] == "periodic":
                policy_token += f"-{policy['interval']}"
            elif policy["name"] == "threshold":
                policy_token += "-005"
            run_id = f"{workload['workload_id']}-{policy_token}"
            if run_id in run_ids:
                raise DevMatrixError(f"duplicate development run ID {run_id}")
            run_ids.add(run_id)
            request_value = {
                "schema_version": "q66-simulation-request-v1",
                "run_id": run_id,
                "instance_file": str(instance_file),
                "distance": distance,
                "rounds": int(workload["rounds"]),
                "basis": workload["basis"],
                "shots": 2_048,
                "shot_start": 0,
                "shard_size": 2_048,
                "master_seed": master_seed,
                "noise": dict(workload["noise"]),
                "reload": dict(family["reload"]),
                "policy": policy,
                "provenance": {
                    "source_commit": source_commit,
                    "environment_lock_sha256": environment_lock_sha256,
                },
            }
            SimulationRequest.from_dict(request_value)
            cells.append(
                {
                    "cell_index": len(cells),
                    "workload_index": workload_index,
                    "policy_index": policy_index,
                    "workload_id": workload["workload_id"],
                    "request": request_value,
                }
            )
    return {
        "schema_version": MATRIX_SCHEMA,
        "cell_count": len(cells),
        "workload_count": len(workloads),
        "policies_per_workload": len(policies),
        "warmup_runs": 1,
        "timed_runs": 3,
        "source_commit": source_commit,
        "environment_lock_sha256": environment_lock_sha256,
        "family_sha256": hashlib.sha256(_canonical_bytes(family)).hexdigest(),
        "cells": cells,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", type=Path, required=True)
    parser.add_argument("--instances", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--environment-lock-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    family = json.loads(args.family.read_text(encoding="utf-8"))
    matrix = generate_dev_matrix(
        family,
        instance_file=args.instances,
        source_commit=args.source_commit,
        environment_lock_sha256=args.environment_lock_sha256,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(matrix, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )
    print(json.dumps({"cells": matrix["cell_count"], "out": str(args.out)}))


if __name__ == "__main__":
    main()
