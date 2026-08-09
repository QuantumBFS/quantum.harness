"""Fail-closed exact Verifier for the five issue #133 campaign gates."""

from __future__ import annotations

import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, cast


class VerificationError(ValueError):
    """A frozen identity, gate clause, or exact certificate failed."""


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError("duplicate JSON key")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicates
    )
    if type(value) is not dict:
        raise VerificationError("document must be an object")
    return value


def _digest(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _valid_digest(document: dict[str, Any]) -> bool:
    return document.get("digest") == _digest(
        {key: value for key, value in document.items() if key != "digest"}
    )


def verify(
    challenge: dict[str, Any], gate: dict[str, Any], solution: dict[str, Any]
) -> dict[str, Any]:
    """Derive exact observables without trusting Solver claims."""

    if not (
        _valid_digest(challenge) and _valid_digest(gate) and _valid_digest(solution)
    ):
        raise VerificationError("document identity drift")
    if (
        gate.get("challenge_id") != challenge.get("challenge_id")
        or gate.get("challenge_digest") != challenge.get("digest")
        or gate.get("acceptance_rules") != challenge.get("preregistered_gate")
        or solution.get("challenge_id") != challenge.get("challenge_id")
        or solution.get("challenge_digest") != challenge.get("digest")
        or solution.get("gate_digest") != gate.get("digest")
        or type(solution.get("certificate")) is not dict
    ):
        raise VerificationError("challenge/gate/certificate binding mismatch")

    certificate = solution["certificate"]
    kind = challenge.get("kind")
    if kind == "exact-rank":
        observables = _verify_rank(challenge, certificate)
    elif kind == "optimal-matrix-chain":
        observables = _verify_chain(challenge, certificate)
    elif kind == "transfer-spectral-gap":
        observables = _verify_gap(challenge, certificate)
    elif kind == "mps-gauge-equivalence":
        observables = _verify_gauge(challenge, certificate)
    else:
        raise VerificationError("unknown challenge kind")
    return {
        "schema_version": "wangtheophys.issue133.verification.v1",
        "accepted": True,
        "challenge_digest": challenge["digest"],
        "gate_digest": gate["digest"],
        "certificate_digest": solution["digest"],
        "observables": observables,
    }


def _verify_rank(
    challenge: dict[str, Any], certificate: dict[str, Any]
) -> dict[str, Any]:
    matrix = challenge["input"]["matrix"]
    left = certificate.get("left_factor")
    right = certificate.get("right_factor")
    if not (
        _integer_matrix(matrix) and _integer_matrix(left) and _integer_matrix(right)
    ):
        raise VerificationError("rank witness must contain integer matrices")
    exact_matrix = cast(list[list[int]], matrix)
    left_factor = cast(list[list[int]], left)
    right_factor = cast(list[list[int]], right)
    if len(left_factor) != len(exact_matrix) or len(right_factor[0]) != len(
        exact_matrix[0]
    ):
        raise VerificationError("rank factor shape mismatch")
    inner = len(right_factor)
    if any(len(row) != inner for row in left_factor):
        raise VerificationError("rank factor inner dimension mismatch")
    product = _multiply(left_factor, right_factor)
    exact_rank = _rank(exact_matrix)
    rules = challenge["preregistered_gate"]
    expected_rank = rules["expected_rank"]
    minor = rules["required_minor"]
    rows = minor["rows"]
    columns = minor["columns"]
    determinant = (
        exact_matrix[rows[0]][columns[0]] * exact_matrix[rows[1]][columns[1]]
        - exact_matrix[rows[0]][columns[1]] * exact_matrix[rows[1]][columns[0]]
    )
    if (
        product != exact_matrix
        or inner != expected_rank
        or exact_rank != expected_rank
        or certificate.get("claimed_rank") != expected_rank
        or determinant == 0
    ):
        raise VerificationError("exact rank gate failed")
    return {
        "exact_rank": exact_rank,
        "factor_inner_dimension": inner,
        "minor_determinant": determinant,
    }


def _verify_chain(
    challenge: dict[str, Any], certificate: dict[str, Any]
) -> dict[str, Any]:
    dimensions = challenge["input"]["dimensions"]
    if type(dimensions) is not list or any(
        type(value) is not int or value < 1 for value in dimensions
    ):
        raise VerificationError("invalid chain dimensions")
    candidates = _all_chains(dimensions)
    optimum = min(cost for cost, _ in candidates)
    expressions = {expression for cost, expression in candidates if cost == optimum}
    if (
        certificate.get("minimum_cost") != optimum
        or certificate.get("parenthesization") not in expressions
    ):
        raise VerificationError("global contraction optimum gate failed")
    return {
        "enumerated_parenthesizations": len(candidates),
        "minimum_cost": optimum,
        "optimal_count": len(expressions),
    }


def _verify_gap(
    challenge: dict[str, Any], certificate: dict[str, Any]
) -> dict[str, Any]:
    matrix = challenge["input"]["matrix"]
    values = certificate.get("eigenvalues_descending")
    vectors = certificate.get("eigenvectors")
    if not (_integer_matrix(matrix) and _integer_matrix(vectors)) or values != [
        4,
        2,
        1,
    ]:
        raise VerificationError("spectral witness fields changed")
    exact_matrix = cast(list[list[int]], matrix)
    eigenvectors = cast(list[list[int]], vectors)
    eigenvalues = cast(list[int], values)
    if len(eigenvectors) != 3 or any(len(vector) != 3 for vector in eigenvectors):
        raise VerificationError("incomplete eigenbasis")
    for value, vector in zip(eigenvalues, eigenvectors, strict=True):
        if _matvec(exact_matrix, vector) != [value * component for component in vector]:
            raise VerificationError("eigenpair equation failed")
    basis_det = _det3(
        [[eigenvectors[column][row] for column in range(3)] for row in range(3)]
    )
    trace = sum(exact_matrix[index][index] for index in range(3))
    coefficients = [1, -trace, 14, -_det3(exact_matrix)]
    gap = eigenvalues[0] - eigenvalues[1]
    if (
        basis_det == 0
        or coefficients != certificate.get("characteristic_coefficients")
        or gap != certificate.get("spectral_gap")
        or gap <= 0
    ):
        raise VerificationError("spectral gap gate failed")
    return {
        "basis_determinant": basis_det,
        "eigenvalues_descending": eigenvalues,
        "spectral_gap": gap,
    }


def _verify_gauge(
    challenge: dict[str, Any], certificate: dict[str, Any]
) -> dict[str, Any]:
    source = challenge["input"]["source_slices"]
    target = challenge["input"]["target_slices"]
    gauge = certificate.get("gauge")
    inverse = certificate.get("inverse_gauge")
    if not all(_integer_matrix(value) for value in (gauge, inverse)):
        raise VerificationError("gauge witness must be exact integer matrices")
    exact_gauge = cast(list[list[int]], gauge)
    exact_inverse = cast(list[list[int]], inverse)
    identity = [[1, 0], [0, 1]]
    determinant = (
        exact_gauge[0][0] * exact_gauge[1][1] - exact_gauge[0][1] * exact_gauge[1][0]
    )
    if (
        _multiply(exact_gauge, exact_inverse) != identity
        or _multiply(exact_inverse, exact_gauge) != identity
        or determinant == 0
    ):
        raise VerificationError("gauge inverse gate failed")
    for source_slice, target_slice in zip(source, target, strict=True):
        transformed = _multiply(_multiply(exact_inverse, source_slice), exact_gauge)
        if transformed != target_slice:
            raise VerificationError("MPS gauge equation failed")
    return {
        "bond_dimension": 2,
        "gauge_determinant": determinant,
        "verified_slices": len(source),
    }


def _integer_matrix(value: object) -> bool:
    return (
        type(value) is list
        and bool(value)
        and all(
            type(row) is list and bool(row) and all(type(item) is int for item in row)
            for row in value
        )
    )


def _multiply(left: list[list[int]], right: list[list[int]]) -> list[list[int]]:
    if not left or not right or any(len(row) != len(right) for row in left):
        raise VerificationError("matrix multiplication shape mismatch")
    width = len(right[0])
    if any(len(row) != width for row in right):
        raise VerificationError("ragged matrix")
    return [
        [sum(left[i][k] * right[k][j] for k in range(len(right))) for j in range(width)]
        for i in range(len(left))
    ]


def _matvec(matrix: list[list[int]], vector: list[int]) -> list[int]:
    return [
        sum(row[index] * vector[index] for index in range(len(vector)))
        for row in matrix
    ]


def _rank(matrix: list[list[int]]) -> int:
    rows = [[Fraction(value) for value in row] for row in matrix]
    rank = 0
    for column in range(len(rows[0])):
        pivot = next(
            (index for index in range(rank, len(rows)) if rows[index][column]), None
        )
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        scale = rows[rank][column]
        rows[rank] = [value / scale for value in rows[rank]]
        for index, row in enumerate(rows):
            if index != rank and row[column]:
                factor = row[column]
                rows[index] = [
                    value - factor * pivot_value
                    for value, pivot_value in zip(row, rows[rank], strict=True)
                ]
        rank += 1
    return rank


def _all_chains(dimensions: list[int]) -> list[tuple[int, str]]:
    def build(left: int, right: int) -> list[tuple[int, int, int, str]]:
        if left == right:
            return [(dimensions[left], dimensions[left + 1], 0, f"A{left + 1}")]
        result = []
        for split in range(left, right):
            for l_rows, l_cols, l_cost, l_expr in build(left, split):
                for r_rows, r_cols, r_cost, r_expr in build(split + 1, right):
                    if l_cols != r_rows:
                        raise VerificationError("matrix-chain shape mismatch")
                    result.append(
                        (
                            l_rows,
                            r_cols,
                            l_cost + r_cost + l_rows * l_cols * r_cols,
                            f"({l_expr}{r_expr})",
                        )
                    )
        return result

    return [
        (cost, expression) for _, _, cost, expression in build(0, len(dimensions) - 2)
    ]


def _det3(matrix: list[list[int]]) -> int:
    return (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 3:
        return 2
    try:
        result = verify(*(_load(Path(argument)) for argument in arguments))
    except (
        OSError,
        json.JSONDecodeError,
        VerificationError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        print(str(error), file=sys.stderr)
        return 3
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
