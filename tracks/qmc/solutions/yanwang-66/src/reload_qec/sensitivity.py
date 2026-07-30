"""Generate the preregistered reload-cost sensitivity matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .config import SimulationRequest
from .matrix import _canonical_bytes, _policy_token, _probability_token


FAMILY_SCHEMA = "q66-cost-sensitivity-family-v1"
MATRIX_SCHEMA = "q66-cost-sensitivity-matrix-v1"
SENSITIVITY_SELECTION = {
    "distance": 5,
    "rounds": 10,
    "basis": ["X", "Z"],
    "p": 0.001,
    "p_m": 0.001,
    "p_loss": [0.001, 0.01, 0.03],
}
SENSITIVITY_POLICIES = [
    {"name": "immediate"},
    {"name": "periodic", "interval": 5},
    {"name": "periodic", "interval": 10},
    {"name": "threshold", "fraction": 0.05},
]
SENSITIVITY_RELOAD_CONFIGURATIONS = [
    {
        "configuration_id": "delay-1",
        "delay_rounds": 1,
        "reset_error_probability": 0.0,
        "failure_probability": 0.0,
    },
    {
        "configuration_id": "delay-2",
        "delay_rounds": 2,
        "reset_error_probability": 0.0,
        "failure_probability": 0.0,
    },
    {
        "configuration_id": "reset-0p001",
        "delay_rounds": 0,
        "reset_error_probability": 0.001,
        "failure_probability": 0.0,
    },
    {
        "configuration_id": "reset-0p01",
        "delay_rounds": 0,
        "reset_error_probability": 0.01,
        "failure_probability": 0.0,
    },
    {
        "configuration_id": "failure-0p001",
        "delay_rounds": 0,
        "reset_error_probability": 0.0,
        "failure_probability": 0.001,
    },
    {
        "configuration_id": "failure-0p01",
        "delay_rounds": 0,
        "reset_error_probability": 0.0,
        "failure_probability": 0.01,
    },
    {
        "configuration_id": "combined-moderate",
        "delay_rounds": 1,
        "reset_error_probability": 0.001,
        "failure_probability": 0.001,
    },
    {
        "configuration_id": "combined-severe",
        "delay_rounds": 2,
        "reset_error_probability": 0.01,
        "failure_probability": 0.01,
    },
]
SENSITIVITY_SAMPLING = {
    "initial_shots_per_cell": 20_000,
    "minimum_logical_failures_per_cell": 1_000,
    "maximum_shots_per_cell": 20_000_000,
    "growth": "double cumulative shots while all policies remain paired",
}
SENSITIVITY_BASELINE_REUSE = {
    "matrix_schema": "q66-discovery-matrix-v1",
    "policy": {"name": "none"},
    "ideal_reload": {
        "delay_rounds": 0,
        "reset_error_probability": 0.0,
        "failure_probability": 0.0,
    },
    "seed_derivation": "q66-discovery-seed-v1",
}
SENSITIVITY_PROVENANCE = {
    "contract": "WORKFLOW.md version 1.0 sections 5.2 and 9F",
    "headline_slice": "topics.md acceptance gate item 2",
    "selection_rule": "fixed before any discovery analysis",
}


class SensitivityError(ValueError):
    """Raised when the frozen sensitivity design changes or is incomplete."""


def _validate_families(families: dict[str, Any]) -> None:
    if not isinstance(families, dict):
        raise SensitivityError("cost-sensitivity family must be an object")
    expected_keys = {
        "schema_version",
        "selection",
        "policies",
        "reload_configurations",
        "sampling",
        "baseline_reuse",
        "provenance",
    }
    if set(families) != expected_keys:
        raise SensitivityError("cost-sensitivity family fields changed")
    if families.get("schema_version") != FAMILY_SCHEMA:
        raise SensitivityError("unsupported cost-sensitivity family schema")
    if families.get("selection") != SENSITIVITY_SELECTION:
        raise SensitivityError("cost-sensitivity headline selection changed")
    if families.get("policies") != SENSITIVITY_POLICIES:
        raise SensitivityError("cost-sensitivity policy set changed")
    if families.get("reload_configurations") != SENSITIVITY_RELOAD_CONFIGURATIONS:
        raise SensitivityError("cost-sensitivity reload costs changed")
    if families.get("sampling") != SENSITIVITY_SAMPLING:
        raise SensitivityError("cost-sensitivity sampling rule changed")
    if families.get("baseline_reuse") != SENSITIVITY_BASELINE_REUSE:
        raise SensitivityError("cost-sensitivity baseline reuse changed")
    if families.get("provenance") != SENSITIVITY_PROVENANCE:
        raise SensitivityError("cost-sensitivity provenance changed")


def _external_physical_key(
    selection: dict[str, Any], basis: str, p_loss: float
) -> dict[str, Any]:
    return {
        "distance": selection["distance"],
        "rounds": selection["rounds"],
        "basis": basis,
        "p": selection["p"],
        "p_m": selection["p_m"],
        "p_loss": p_loss,
    }


def _master_seed(physical_key: dict[str, Any]) -> int:
    digest = hashlib.sha256(
        b"q66-discovery-seed-v1\0" + _canonical_bytes(physical_key)
    ).digest()
    return int.from_bytes(digest[:8], "little")


def _run_id(
    basis: str,
    p_loss: float,
    configuration_id: str,
    policy: dict[str, Any],
) -> str:
    return "-".join(
        (
            "sens",
            "d5",
            "t10",
            basis.lower(),
            f"pl{_probability_token(float(p_loss))}",
            configuration_id,
            _policy_token(policy),
        )
    )


def validate_sensitivity_matrix(matrix: dict[str, Any]) -> None:
    expected_keys = {
        "schema_version",
        "groups",
        "group_count",
        "cell_count",
        "shots_per_cell",
        "shard_size",
        "source_commit",
        "environment_lock_sha256",
        "family_sha256",
        "sampling",
        "provenance",
    }
    if not isinstance(matrix, dict) or set(matrix) != expected_keys:
        raise SensitivityError("cost-sensitivity matrix fields changed")
    if matrix.get("schema_version") != MATRIX_SCHEMA:
        raise SensitivityError("unsupported cost-sensitivity matrix schema")
    if matrix.get("group_count") != 48 or matrix.get("cell_count") != 192:
        raise SensitivityError("cost-sensitivity matrix is not 48 groups/192 cells")
    if matrix.get("shots_per_cell") != 20_000:
        raise SensitivityError("cost-sensitivity initial shot count changed")
    shard_size = matrix.get("shard_size")
    if type(shard_size) is not int or not 1 <= shard_size <= 20_000:
        raise SensitivityError("cost-sensitivity shard size is invalid")
    source_commit = matrix.get("source_commit")
    environment_hash = matrix.get("environment_lock_sha256")
    family_hash = matrix.get("family_sha256")
    if not isinstance(source_commit, str) or not re.fullmatch(
        r"[0-9a-f]{40}", source_commit
    ):
        raise SensitivityError("cost-sensitivity source commit is invalid")
    for name, value in (
        ("environment lock", environment_hash),
        ("family", family_hash),
    ):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise SensitivityError(f"cost-sensitivity {name} hash is invalid")
    frozen_family = {
        "schema_version": FAMILY_SCHEMA,
        "selection": SENSITIVITY_SELECTION,
        "policies": SENSITIVITY_POLICIES,
        "reload_configurations": SENSITIVITY_RELOAD_CONFIGURATIONS,
        "sampling": SENSITIVITY_SAMPLING,
        "baseline_reuse": SENSITIVITY_BASELINE_REUSE,
        "provenance": SENSITIVITY_PROVENANCE,
    }
    if family_hash != hashlib.sha256(_canonical_bytes(frozen_family)).hexdigest():
        raise SensitivityError("cost-sensitivity family hash changed")
    if matrix.get("sampling") != SENSITIVITY_SAMPLING:
        raise SensitivityError("cost-sensitivity matrix sampling rule changed")
    if matrix.get("provenance") != SENSITIVITY_PROVENANCE:
        raise SensitivityError("cost-sensitivity matrix provenance changed")
    groups = matrix.get("groups")
    if not isinstance(groups, list) or len(groups) != 48:
        raise SensitivityError("cost-sensitivity matrix group layout changed")

    expected_layout = [
        (basis, p_loss, reload_value)
        for basis in SENSITIVITY_SELECTION["basis"]
        for p_loss in SENSITIVITY_SELECTION["p_loss"]
        for reload_value in SENSITIVITY_RELOAD_CONFIGURATIONS
    ]
    instance_files: set[str] = set()
    run_ids: set[str] = set()
    for group_index, (group, expected) in enumerate(
        zip(groups, expected_layout, strict=True)
    ):
        basis, p_loss, reload_value = expected
        physical_key = _external_physical_key(
            SENSITIVITY_SELECTION, str(basis), float(p_loss)
        )
        configuration_id = str(reload_value["configuration_id"])
        reload_config = {
            key: reload_value[key]
            for key in (
                "delay_rounds",
                "reset_error_probability",
                "failure_probability",
            )
        }
        baseline_reference = {
            "matrix_schema": "q66-discovery-matrix-v1",
            "physical_key": physical_key,
            "policy": {"name": "none"},
        }
        if not isinstance(group, dict) or set(group) != {
            "group_index",
            "physical_key",
            "reload_configuration_id",
            "reload",
            "baseline_reference",
            "requests",
        }:
            raise SensitivityError("cost-sensitivity matrix group fields changed")
        if (
            group["group_index"] != group_index
            or group["physical_key"] != physical_key
            or group["reload_configuration_id"] != configuration_id
            or group["reload"] != reload_config
            or group["baseline_reference"] != baseline_reference
        ):
            raise SensitivityError("cost-sensitivity matrix group identity changed")
        requests = group["requests"]
        if not isinstance(requests, list) or len(requests) != 4:
            raise SensitivityError("cost-sensitivity group is not four policies")
        if [request["policy"] for request in requests] != SENSITIVITY_POLICIES:
            raise SensitivityError("cost-sensitivity request policies changed")
        master_seed = _master_seed(physical_key)
        for request_value, policy in zip(
            requests, SENSITIVITY_POLICIES, strict=True
        ):
            request = SimulationRequest.from_dict(request_value)
            if request.run_id != _run_id(
                str(basis), float(p_loss), configuration_id, policy
            ):
                raise SensitivityError("cost-sensitivity run ID changed")
            if (
                request.distance != physical_key["distance"]
                or request.rounds != physical_key["rounds"]
                or request.basis != physical_key["basis"]
                or request.p != physical_key["p"]
                or request.p_m != physical_key["p_m"]
                or request.p_loss != physical_key["p_loss"]
                or request.shots != 20_000
                or request.shot_start != 0
                or request.shard_size != shard_size
                or request.master_seed != master_seed
                or request.policy.as_dict() != policy
                or {
                    "delay_rounds": request.reload.delay_rounds,
                    "reset_error_probability": (
                        request.reload.reset_error_probability
                    ),
                    "failure_probability": request.reload.failure_probability,
                }
                != reload_config
                or request.source_commit != source_commit
                or request.environment_lock_sha256 != environment_hash
            ):
                raise SensitivityError("cost-sensitivity request changed")
            instance_files.add(str(request.instance_file))
            if request.run_id in run_ids:
                raise SensitivityError("cost-sensitivity matrix has duplicate run IDs")
            run_ids.add(request.run_id)
    if len(instance_files) != 1 or len(run_ids) != 192:
        raise SensitivityError("cost-sensitivity matrix pairing identity changed")


def load_sensitivity_matrix(path: Path) -> dict[str, Any]:
    matrix = json.loads(path.read_text(encoding="ascii"))
    validate_sensitivity_matrix(matrix)
    return matrix


def generate_sensitivity_matrix(
    families: dict[str, Any],
    *,
    instance_file: Path,
    source_commit: str,
    environment_lock_sha256: str,
    shard_size: int,
) -> dict[str, Any]:
    _validate_families(families)
    selection = families["selection"]
    shots = int(families["sampling"]["initial_shots_per_cell"])
    groups = []
    for basis in selection["basis"]:
        for p_loss in selection["p_loss"]:
            physical_key = _external_physical_key(selection, basis, p_loss)
            master_seed = _master_seed(physical_key)
            for reload_value in families["reload_configurations"]:
                configuration_id = reload_value["configuration_id"]
                reload_config = {
                    key: reload_value[key]
                    for key in (
                        "delay_rounds",
                        "reset_error_probability",
                        "failure_probability",
                    )
                }
                requests = []
                for policy in families["policies"]:
                    run_id = _run_id(
                        basis,
                        float(p_loss),
                        configuration_id,
                        policy,
                    )
                    request = {
                        "schema_version": "q66-simulation-request-v1",
                        "run_id": run_id,
                        "instance_file": str(instance_file),
                        "distance": 5,
                        "rounds": 10,
                        "basis": basis,
                        "shots": shots,
                        "shot_start": 0,
                        "shard_size": shard_size,
                        "master_seed": master_seed,
                        "noise": {
                            "p": selection["p"],
                            "p_m": selection["p_m"],
                            "p_loss": p_loss,
                        },
                        "reload": reload_config,
                        "policy": policy,
                        "provenance": {
                            "source_commit": source_commit,
                            "environment_lock_sha256": environment_lock_sha256,
                        },
                    }
                    SimulationRequest.from_dict(request)
                    requests.append(request)
                groups.append(
                    {
                        "group_index": len(groups),
                        "physical_key": physical_key,
                        "reload_configuration_id": configuration_id,
                        "reload": reload_config,
                        "baseline_reference": {
                            "matrix_schema": "q66-discovery-matrix-v1",
                            "physical_key": physical_key,
                            "policy": {"name": "none"},
                        },
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
        "family_sha256": hashlib.sha256(_canonical_bytes(families)).hexdigest(),
        "sampling": families["sampling"],
        "provenance": families["provenance"],
    }
    validate_sensitivity_matrix(matrix)
    return matrix


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--families", type=Path, required=True)
    parser.add_argument("--instances", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--environment-lock-sha256", required=True)
    parser.add_argument("--shard-size", type=int, default=4_096)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    families = json.loads(args.families.read_text(encoding="utf-8"))
    matrix = generate_sensitivity_matrix(
        families,
        instance_file=args.instances,
        source_commit=args.source_commit,
        environment_lock_sha256=args.environment_lock_sha256,
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


if __name__ == "__main__":
    main()
