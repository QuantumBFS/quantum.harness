"""Deterministic certificates for five frozen issue #133 TN problems."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


def digest(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def frozen_challenges() -> tuple[dict[str, Any], ...]:
    """Return five new challenges with their acceptance rules already frozen."""

    records: list[dict[str, Any]] = [
        {
            "schema_version": "wangtheophys.issue133.challenge.v1",
            "challenge_id": "issue133.new-01-exact-mpo-rank",
            "title": "Exact minimal MPO rank of a frozen integer operator",
            "kind": "exact-rank",
            "input": {
                "matrix": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
            },
            "preregistered_gate": {
                "expected_rank": 2,
                "required_minor": {"rows": [0, 1], "columns": [0, 1]},
                "arithmetic": "exact-integer",
            },
            "novelty_statement": "New live campaign item; not a #124-#128 calibration problem.",
            "frozen_at": "2026-07-30T12:20:00Z",
        },
        {
            "schema_version": "wangtheophys.issue133.challenge.v1",
            "challenge_id": "issue133.new-02-optimal-contraction",
            "title": "Globally optimal contraction of a frozen four-tensor chain",
            "kind": "optimal-matrix-chain",
            "input": {"dimensions": [2, 3, 4, 2, 5]},
            "preregistered_gate": {
                "objective": "minimum-scalar-multiplications",
                "requires_global_enumeration": True,
            },
            "novelty_statement": "New live campaign item; not a #124-#128 calibration problem.",
            "frozen_at": "2026-07-30T12:20:00Z",
        },
        {
            "schema_version": "wangtheophys.issue133.challenge.v1",
            "challenge_id": "issue133.new-03-transfer-gap",
            "title": "Exact spectral gap of a frozen transfer matrix",
            "kind": "transfer-spectral-gap",
            "input": {"matrix": [[3, 1, 0], [1, 3, 0], [0, 0, 1]]},
            "preregistered_gate": {
                "eigenvalue_order": "descending",
                "requires_complete_eigenbasis": True,
                "required_positive_gap": True,
            },
            "novelty_statement": "New live campaign item; not a #124-#128 calibration problem.",
            "frozen_at": "2026-07-30T12:20:00Z",
        },
        {
            "schema_version": "wangtheophys.issue133.challenge.v1",
            "challenge_id": "issue133.new-04-schmidt-rank",
            "title": "Exact Schmidt rank of a frozen bipartite coefficient tensor",
            "kind": "exact-rank",
            "input": {"matrix": [[1, 0, 1], [0, 1, 1], [1, 1, 2]]},
            "preregistered_gate": {
                "expected_rank": 2,
                "required_minor": {"rows": [0, 1], "columns": [0, 1]},
                "arithmetic": "exact-integer",
            },
            "novelty_statement": "New live campaign item; not a #124-#128 calibration problem.",
            "frozen_at": "2026-07-30T12:20:00Z",
        },
        {
            "schema_version": "wangtheophys.issue133.challenge.v1",
            "challenge_id": "issue133.new-05-mps-gauge-equivalence",
            "title": "Exact gauge equivalence of two frozen MPS tensor sets",
            "kind": "mps-gauge-equivalence",
            "input": {
                "source_slices": [[[1, 0], [0, 2]], [[0, 1], [1, 0]]],
                "target_slices": [[[1, -1], [0, 2]], [[-1, 0], [1, 1]]],
            },
            "preregistered_gate": {
                "equation": "target_s = inverse_gauge * source_s * gauge",
                "requires_exact_inverse": True,
                "arithmetic": "exact-integer",
            },
            "novelty_statement": "New live campaign item; not a #124-#128 calibration problem.",
            "frozen_at": "2026-07-30T12:20:00Z",
        },
    ]
    frozen = []
    for record in records:
        item = deepcopy(record)
        item["digest"] = digest(item)
        frozen.append(item)
    return tuple(frozen)


def solve_challenge(challenge: dict[str, Any], gate_digest: str) -> dict[str, Any]:
    """Emit a certificate; only the separate Verifier can emit a verdict."""

    unsigned = {key: value for key, value in challenge.items() if key != "digest"}
    if challenge.get("digest") != digest(unsigned):
        raise ValueError("challenge digest mismatch")
    challenge_id = challenge["challenge_id"]
    if challenge_id == "issue133.new-01-exact-mpo-rank":
        certificate: dict[str, Any] = {
            "claimed_rank": 2,
            "left_factor": [[1, 0], [0, 1], [0, 0], [0, 0]],
            "right_factor": [[1, 0, 0, 0], [0, 1, 0, 0]],
        }
    elif challenge_id == "issue133.new-02-optimal-contraction":
        cost, expression = _matrix_chain_solution(challenge["input"]["dimensions"])
        certificate = {"minimum_cost": cost, "parenthesization": expression}
    elif challenge_id == "issue133.new-03-transfer-gap":
        certificate = {
            "characteristic_coefficients": [1, -7, 14, -8],
            "eigenvalues_descending": [4, 2, 1],
            "eigenvectors": [[1, 1, 0], [1, -1, 0], [0, 0, 1]],
            "spectral_gap": 2,
        }
    elif challenge_id == "issue133.new-04-schmidt-rank":
        certificate = {
            "claimed_rank": 2,
            "left_factor": [[1, 0], [0, 1], [1, 1]],
            "right_factor": [[1, 0, 1], [0, 1, 1]],
        }
    elif challenge_id == "issue133.new-05-mps-gauge-equivalence":
        certificate = {
            "gauge": [[1, 1], [0, 1]],
            "inverse_gauge": [[1, -1], [0, 1]],
        }
    else:
        raise ValueError("unknown campaign challenge")
    result: dict[str, Any] = {
        "schema_version": "wangtheophys.issue133.certificate.v1",
        "challenge_id": challenge_id,
        "challenge_digest": challenge["digest"],
        "gate_digest": gate_digest,
        "certificate": certificate,
    }
    result["digest"] = digest(result)
    return result


def negative_control(solution: dict[str, Any]) -> dict[str, Any]:
    """Corrupt one essential witness field and rebind the document digest."""

    result = deepcopy(solution)
    challenge_id = result["challenge_id"]
    certificate = result["certificate"]
    if challenge_id in {
        "issue133.new-01-exact-mpo-rank",
        "issue133.new-04-schmidt-rank",
    }:
        certificate["left_factor"][0][0] = 0
    elif challenge_id == "issue133.new-02-optimal-contraction":
        certificate["minimum_cost"] += 1
    elif challenge_id == "issue133.new-03-transfer-gap":
        certificate["spectral_gap"] += 1
    elif challenge_id == "issue133.new-05-mps-gauge-equivalence":
        certificate["gauge"][0][0] = 2
    else:
        raise ValueError("unknown campaign challenge")
    result["digest"] = digest(
        {key: value for key, value in result.items() if key != "digest"}
    )
    return result


def _matrix_chain_solution(dimensions: list[int]) -> tuple[int, str]:
    count = len(dimensions) - 1
    costs = [[0] * count for _ in range(count)]
    expressions = [[f"A{index + 1}" for index in range(count)] for _ in range(count)]
    for width in range(2, count + 1):
        for left in range(count - width + 1):
            right = left + width - 1
            candidates = []
            for split in range(left, right):
                cost = (
                    costs[left][split]
                    + costs[split + 1][right]
                    + dimensions[left] * dimensions[split + 1] * dimensions[right + 1]
                )
                expression = (
                    f"({expressions[left][split]}{expressions[split + 1][right]})"
                )
                candidates.append((cost, expression))
            costs[left][right], expressions[left][right] = min(candidates)
    return costs[0][count - 1], expressions[0][count - 1]


__all__ = ["digest", "frozen_challenges", "negative_control", "solve_challenge"]
