"""Generate the preregistered independent-seed confirmation matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .config import SimulationRequest
from .matrix import _canonical_bytes, _policy_token, _probability_token


FAMILY_SCHEMA = "q66-confirmation-family-v1"
MATRIX_SCHEMA = "q66-confirmation-matrix-v1"
SEED_DOMAIN = b"q66-confirmation-seed-v1\0"
CONFIRMATION_SELECTION = {
    "distance": 5,
    "rounds": 10,
    "basis": ["X", "Z"],
    "p": 0.001,
    "p_m": 0.001,
    "p_loss": [0.001, 0.003, 0.01, 0.03],
}
CONFIRMATION_POLICIES = [
    {"name": "none"},
    {"name": "immediate"},
    {"name": "periodic", "interval": 5},
    {"name": "periodic", "interval": 10},
    {"name": "threshold", "fraction": 0.05},
]
CONFIRMATION_RELOAD = {
    "delay_rounds": 0,
    "reset_error_probability": 0.0,
    "failure_probability": 0.0,
}
CONFIRMATION_SAMPLING = {
    "initial_shots_per_cell": 20_000,
    "minimum_logical_failures_per_cell": 1_000,
    "maximum_shots_per_cell": 20_000_000,
    "growth": "double cumulative shots while all 5 policies remain paired",
    "paired_precision": {
        "confidence": 0.95,
        "required_comparison_fraction": 0.8,
        "half_width_rule": "max(0.2 * p_L(none), 0.0001)",
    },
}
CONFIRMATION_SEED = {
    "derivation": "sha256-domain-separated-little-endian-u64",
    "domain": "q66-confirmation-seed-v1",
    "independent_of": "q66-discovery-seed-v1",
}
CONFIRMATION_PROVENANCE = {
    "contract": "WORKFLOW.md version 1.0 sections 5.3, 9F, and 10",
    "headline_slice": "topics.md acceptance gate items 2 and 3",
    "selection_rule": "fixed before any discovery analysis",
}


class ConfirmationError(ValueError):
    """Raised when the frozen confirmation design changes or is incomplete."""


def _validate_families(families: dict[str, Any]) -> None:
    if not isinstance(families, dict):
        raise ConfirmationError("confirmation family must be an object")
    expected_keys = {
        "schema_version",
        "selection",
        "policies",
        "reload",
        "sampling",
        "seed",
        "provenance",
    }
    if set(families) != expected_keys:
        raise ConfirmationError("confirmation family fields changed")
    if families.get("schema_version") != FAMILY_SCHEMA:
        raise ConfirmationError("unsupported confirmation family schema")
    if families.get("selection") != CONFIRMATION_SELECTION:
        raise ConfirmationError("confirmation headline selection changed")
    if families.get("policies") != CONFIRMATION_POLICIES:
        raise ConfirmationError("confirmation policy set changed")
    if families.get("reload") != CONFIRMATION_RELOAD:
        raise ConfirmationError("confirmation reload model is not ideal")
    if families.get("sampling") != CONFIRMATION_SAMPLING:
        raise ConfirmationError("confirmation sampling rule changed")
    if families.get("seed") != CONFIRMATION_SEED:
        raise ConfirmationError("confirmation seed contract changed")
    if families.get("provenance") != CONFIRMATION_PROVENANCE:
        raise ConfirmationError("confirmation provenance changed")


def _physical_key(
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
    digest = hashlib.sha256(SEED_DOMAIN + _canonical_bytes(physical_key)).digest()
    return int.from_bytes(digest[:8], "little")


def _run_id(basis: str, p_loss: float, policy: dict[str, Any]) -> str:
    return "-".join(
        (
            "confirm",
            "d5",
            "t10",
            basis.lower(),
            f"pl{_probability_token(float(p_loss))}",
            _policy_token(policy),
        )
    )


def validate_confirmation_matrix(matrix: dict[str, Any]) -> None:
    """Reject any executable confirmation matrix that drifts from the freeze."""

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
        "seed",
        "provenance",
    }
    if not isinstance(matrix, dict) or set(matrix) != expected_keys:
        raise ConfirmationError("confirmation matrix fields changed")
    if matrix.get("schema_version") != MATRIX_SCHEMA:
        raise ConfirmationError("unsupported confirmation matrix schema")
    if matrix.get("group_count") != 8 or matrix.get("cell_count") != 40:
        raise ConfirmationError("confirmation matrix is not 8 groups/40 cells")
    if matrix.get("shots_per_cell") != 20_000:
        raise ConfirmationError("confirmation initial shot count changed")
    shard_size = matrix.get("shard_size")
    if type(shard_size) is not int or shard_size < 1 or shard_size > 20_000:
        raise ConfirmationError("confirmation shard size is invalid")
    source_commit = matrix.get("source_commit")
    environment_hash = matrix.get("environment_lock_sha256")
    family_hash = matrix.get("family_sha256")
    if not isinstance(source_commit, str) or not re.fullmatch(
        r"[0-9a-f]{40}", source_commit
    ):
        raise ConfirmationError("confirmation source commit is invalid")
    for name, value in (
        ("environment lock", environment_hash),
        ("family", family_hash),
    ):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ConfirmationError(f"confirmation {name} hash is invalid")
    if matrix.get("sampling") != CONFIRMATION_SAMPLING:
        raise ConfirmationError("confirmation matrix sampling rule changed")
    if matrix.get("seed") != CONFIRMATION_SEED:
        raise ConfirmationError("confirmation matrix seed contract changed")
    if matrix.get("provenance") != CONFIRMATION_PROVENANCE:
        raise ConfirmationError("confirmation matrix provenance changed")
    groups = matrix.get("groups")
    if not isinstance(groups, list) or len(groups) != 8:
        raise ConfirmationError("confirmation matrix group layout changed")
    instance_files = set()
    run_ids = set()
    expected_physical_keys = [
        _physical_key(CONFIRMATION_SELECTION, basis, p_loss)
        for basis in CONFIRMATION_SELECTION["basis"]
        for p_loss in CONFIRMATION_SELECTION["p_loss"]
    ]
    for group_index, (group, expected_physical_key) in enumerate(
        zip(groups, expected_physical_keys, strict=True)
    ):
        if not isinstance(group, dict) or set(group) != {
            "group_index",
            "physical_key",
            "requests",
        }:
            raise ConfirmationError("confirmation group fields changed")
        if group.get("group_index") != group_index:
            raise ConfirmationError("confirmation group order is not contiguous")
        if group.get("physical_key") != expected_physical_key:
            raise ConfirmationError("confirmation physical group order changed")
        requests = group.get("requests")
        if not isinstance(requests, list) or len(requests) != 5:
            raise ConfirmationError("confirmation group is not five paired policies")
        if [request.get("policy") for request in requests] != CONFIRMATION_POLICIES:
            raise ConfirmationError("confirmation request policy order changed")
        expected_seed = _master_seed(expected_physical_key)
        for request_value, policy in zip(
            requests, CONFIRMATION_POLICIES, strict=True
        ):
            request = SimulationRequest.from_dict(request_value)
            if request.run_id != _run_id(
                expected_physical_key["basis"],
                expected_physical_key["p_loss"],
                policy,
            ):
                raise ConfirmationError("confirmation run ID changed")
            if (
                request.distance != expected_physical_key["distance"]
                or request.rounds != expected_physical_key["rounds"]
                or request.basis != expected_physical_key["basis"]
                or request.p != expected_physical_key["p"]
                or request.p_m != expected_physical_key["p_m"]
                or request.p_loss != expected_physical_key["p_loss"]
                or request.shots != 20_000
                or request.shot_start != 0
                or request.shard_size != shard_size
                or request.master_seed != expected_seed
                or request.policy.as_dict() != policy
                or {
                    "delay_rounds": request.reload.delay_rounds,
                    "reset_error_probability": (
                        request.reload.reset_error_probability
                    ),
                    "failure_probability": request.reload.failure_probability,
                }
                != CONFIRMATION_RELOAD
                or request.source_commit != source_commit
                or request.environment_lock_sha256 != environment_hash
            ):
                raise ConfirmationError("confirmation request changed")
            instance_files.add(str(request.instance_file))
            if request.run_id in run_ids:
                raise ConfirmationError("confirmation matrix has duplicate run IDs")
            run_ids.add(request.run_id)
    if len(instance_files) != 1 or len(run_ids) != 40:
        raise ConfirmationError("confirmation matrix pairing identity changed")


def load_confirmation_matrix(path: Path) -> dict[str, Any]:
    matrix = json.loads(path.read_text(encoding="ascii"))
    validate_confirmation_matrix(matrix)
    return matrix


def generate_confirmation_matrix(
    families: dict[str, Any],
    *,
    instance_file: Path,
    source_commit: str,
    environment_lock_sha256: str,
    shard_size: int,
) -> dict[str, Any]:
    _validate_families(families)
    selection = families["selection"]
    reload_config = families["reload"]
    shots = int(families["sampling"]["initial_shots_per_cell"])
    groups = []
    for basis in selection["basis"]:
        for p_loss in selection["p_loss"]:
            physical_key = _physical_key(selection, basis, p_loss)
            master_seed = _master_seed(physical_key)
            requests = []
            for policy in families["policies"]:
                run_id = _run_id(basis, p_loss, policy)
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
        "seed": families["seed"],
        "provenance": families["provenance"],
    }
    validate_confirmation_matrix(matrix)
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
    matrix = generate_confirmation_matrix(
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
