"""Search exact5 grade-2/3 sectors for one shared simplicial cone.

The fast exact gate decides the complete positive-diagonal / signed-monomial
class.  A numerical similarity search is only a discovery heuristic: a hit is
reported only after rationalization and exact SymPy replay for every atom.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import deque
from collections.abc import Mapping, Sequence
from fractions import Fraction
from pathlib import Path

import numpy as np
import sympy as sp
from scipy.optimize import minimize

from .exterior_candidates import (
    candidate_card,
    candidate_id,
    exact_atoms_from_card,
)
from .exterior_cone import subset_basis, transformed_nonnegative_margin


SCHEMA_VERSION = "exterior-exact5-shared-cone-v1"
DEFAULT_TARGETS = (
    ("exact5-oddcycle-block-pair", 61),
    ("exact5-oddcycle-block-pair", 97),
    ("exact5-oddcycle-block-pair", 100),
    ("exact5-oddcycle-block-pair", 124),
    ("exact5-oddcycle-block-pair", 211),
    ("exact5-oddcycle-block-pair", 244),
    ("exact5-shear-loop-pair", 61),
)


def _rational_payload(value: sp.Expr) -> dict[str, int]:
    rational = sp.Rational(value)
    return {
        "numerator": int(rational.p),
        "denominator": int(rational.q),
    }


def _matrix_payload(matrix: sp.MatrixBase) -> list[list[dict[str, int]]]:
    return [
        [_rational_payload(matrix[row, column]) for column in range(matrix.cols)]
        for row in range(matrix.rows)
    ]


def _validated_exact_matrices(
    matrices: Sequence[sp.MatrixBase],
) -> tuple[sp.ImmutableMatrix, ...]:
    if not matrices:
        raise ValueError("at least one matrix is required")
    checked = tuple(sp.ImmutableMatrix(matrix) for matrix in matrices)
    dimension = checked[0].rows
    if dimension < 1 or checked[0].cols != dimension:
        raise ValueError("matrices must be nonempty and square")
    if any(matrix.shape != (dimension, dimension) for matrix in checked):
        raise ValueError("matrices must have one common square size")
    if any(
        not bool(entry.is_rational)
        for matrix in checked
        for entry in matrix
    ):
        raise ValueError("matrices must contain exact rational entries")
    return checked


def exact_compound_matrix(
    matrix: sp.MatrixBase,
    grade: int,
) -> sp.ImmutableMatrix:
    """Return one exact exterior-power matrix in the shared basis convention."""

    exact = sp.ImmutableMatrix(matrix)
    if exact.rows != exact.cols:
        raise ValueError("matrix must be square")
    basis = subset_basis(exact.rows, grade)
    return sp.ImmutableMatrix(
        [
            [
                sp.det(exact.extract(rows, columns))
                for columns in basis
            ]
            for rows in basis
        ]
    )


def signed_monomial_triage(
    matrices: Sequence[sp.MatrixBase],
) -> dict[str, object]:
    """Decide exact feasibility under one shared signed-monomial similarity.

    A common permutation merely reorders the same sign constraints, while a
    positive diagonal rescales them without changing signs.  Thus the signed
    diagonal constraint graph decides the entire declared restricted class.
    """

    checked = _validated_exact_matrices(matrices)
    dimension = checked[0].rows
    obligations: dict[tuple[int, int], tuple[int, int]] = {}
    adjacency: list[list[tuple[int, int]]] = [[] for _ in range(dimension)]

    for atom_index, matrix in enumerate(checked):
        for row in range(dimension):
            diagonal = matrix[row, row]
            if diagonal < 0:
                return {
                    "status": "restricted-obstruction",
                    "class": "positive-diagonal-and-signed-monomial",
                    "witness": {
                        "kind": "negative-diagonal",
                        "atom": atom_index,
                        "index": row,
                        "value": _rational_payload(diagonal),
                    },
                }
            for column in range(dimension):
                if row == column or matrix[row, column] == 0:
                    continue
                required = 1 if matrix[row, column] > 0 else -1
                key = (row, column)
                previous = obligations.get(key)
                if previous is not None and previous[0] != required:
                    return {
                        "status": "restricted-obstruction",
                        "class": "positive-diagonal-and-signed-monomial",
                        "witness": {
                            "kind": "conflicting-entry-sign",
                            "row": row,
                            "column": column,
                            "first_atom": previous[1],
                            "second_atom": atom_index,
                        },
                    }
                obligations[key] = (required, atom_index)

    for (row, column), (required, _) in obligations.items():
        adjacency[row].append((column, required))
        adjacency[column].append((row, required))

    signs: list[int | None] = [None] * dimension
    for root in range(dimension):
        if signs[root] is not None:
            continue
        signs[root] = 1
        queue = deque((root,))
        while queue:
            row = queue.popleft()
            assert signs[row] is not None
            for column, required in adjacency[row]:
                proposed = signs[row] * required
                if signs[column] is None:
                    signs[column] = proposed
                    queue.append(column)
                elif signs[column] != proposed:
                    return {
                        "status": "restricted-obstruction",
                        "class": "positive-diagonal-and-signed-monomial",
                        "witness": {
                            "kind": "inconsistent-sign-cycle",
                            "row": row,
                            "column": column,
                            "required_product": required,
                        },
                    }

    diagonal = [int(sign) for sign in signs]
    transform = sp.diag(*diagonal)
    transformed = tuple(transform * matrix * transform for matrix in checked)
    if any(entry < 0 for matrix in transformed for entry in matrix):
        raise RuntimeError("signed constraint solver emitted a negative entry")
    minimum = min(entry for matrix in transformed for entry in matrix)
    return {
        "status": "exact-certificate",
        "method": "shared-signed-monomial",
        "class": "positive-diagonal-and-signed-monomial",
        "diagonal": diagonal,
        "minimum_entry": _rational_payload(minimum),
        "transformed_atoms": [_matrix_payload(matrix) for matrix in transformed],
    }


def exact_simplicial_certificate(
    matrices: Sequence[sp.MatrixBase],
    numerical_transform: Sequence[Sequence[float]] | np.ndarray,
    *,
    max_denominator: int,
) -> dict[str, object] | None:
    """Rationalize one numerical basis and accept only exact nonnegative replay."""

    checked = _validated_exact_matrices(matrices)
    if (
        not isinstance(max_denominator, int)
        or isinstance(max_denominator, bool)
        or max_denominator < 1
    ):
        raise ValueError("max_denominator must be a positive integer")
    numerical = np.asarray(numerical_transform, dtype=float)
    dimension = checked[0].rows
    if numerical.shape != (dimension, dimension):
        raise ValueError("numerical_transform must match the matrix dimension")
    if not np.all(np.isfinite(numerical)):
        raise ValueError("numerical_transform must be finite")

    rationalized = sp.ImmutableMatrix(
        [
            [
                sp.Rational(
                    Fraction(float(numerical[row, column])).limit_denominator(
                        max_denominator
                    ).numerator,
                    Fraction(float(numerical[row, column])).limit_denominator(
                        max_denominator
                    ).denominator,
                )
                for column in range(dimension)
            ]
            for row in range(dimension)
        ]
    )
    if rationalized.det() == 0:
        return None
    inverse = rationalized.inv()
    transformed = tuple(
        sp.ImmutableMatrix(inverse * matrix * rationalized)
        for matrix in checked
    )
    if any(entry < 0 for matrix in transformed for entry in matrix):
        return None
    minimum = min(entry for matrix in transformed for entry in matrix)
    return {
        "status": "exact-certificate",
        "method": "rationalized-common-simplicial",
        "max_denominator": max_denominator,
        "transform": _matrix_payload(rationalized),
        "minimum_entry": _rational_payload(minimum),
        "transformed_atoms": [_matrix_payload(matrix) for matrix in transformed],
    }


def _negative_objective_and_gradient(
    flat_transform: np.ndarray,
    matrices: tuple[np.ndarray, ...],
    *,
    target_margin: float,
    orthogonality_weight: float,
) -> tuple[float, np.ndarray]:
    dimension = matrices[0].shape[0]
    transform = flat_transform.reshape((dimension, dimension))
    try:
        inverse_transpose = np.linalg.inv(transform).T
    except np.linalg.LinAlgError:
        return 1.0e30, np.zeros_like(flat_transform)
    if not np.all(np.isfinite(inverse_transpose)):
        return 1.0e30, np.zeros_like(flat_transform)

    objective = 0.0
    gradient = np.zeros_like(transform)
    for matrix in matrices:
        transformed = np.linalg.solve(transform, matrix @ transform)
        shortfall = np.minimum(transformed - target_margin, 0.0)
        objective += 0.5 * float(np.sum(shortfall * shortfall))
        gradient += (
            matrix.T @ inverse_transpose @ shortfall
            - inverse_transpose @ shortfall @ transformed.T
        )

    gram_error = transform.T @ transform - np.eye(dimension)
    objective += 0.25 * orthogonality_weight * float(
        np.sum(gram_error * gram_error)
    )
    gradient += orthogonality_weight * transform @ gram_error
    return objective, gradient.ravel()


def _initial_transforms(
    matrices: tuple[np.ndarray, ...],
    *,
    attempts: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, ...]:
    dimension = matrices[0].shape[0]
    initials: list[np.ndarray] = [np.eye(dimension)]
    for matrix in matrices:
        _, vectors = np.linalg.eig(matrix)
        if np.max(np.abs(np.imag(vectors))) <= 1.0e-10:
            real = np.real(vectors)
            if np.linalg.matrix_rank(real) == dimension:
                initials.append(real / np.linalg.norm(real, axis=0))
    while len(initials) < attempts:
        orthogonal, _ = np.linalg.qr(rng.normal(size=(dimension, dimension)))
        shear = np.eye(dimension) + 0.35 * rng.normal(
            size=(dimension, dimension)
        )
        candidate = orthogonal @ shear
        if np.linalg.matrix_rank(candidate) == dimension:
            initials.append(candidate)
    return tuple(initials[:attempts])


def numerical_simplicial_search(
    matrices: Sequence[sp.MatrixBase],
    *,
    attempts: int,
    maxiter: int,
    rng_seed: int,
    tolerance: float,
    target_margin: float,
    max_denominator: int,
) -> dict[str, object]:
    """Heuristically search GL(d,R), promoting only exact rational hits."""

    checked = _validated_exact_matrices(matrices)
    if attempts < 0 or maxiter < 1:
        raise ValueError("attempts must be nonnegative and maxiter positive")
    if tolerance < 0.0 or target_margin < 0.0:
        raise ValueError("tolerances must be nonnegative")

    float_matrices = tuple(
        np.asarray(matrix.tolist(), dtype=float) for matrix in checked
    )
    scaled = tuple(
        matrix / max(1.0, float(np.max(np.abs(matrix))))
        for matrix in float_matrices
    )
    rng = np.random.default_rng(rng_seed)
    best: dict[str, object] = {
        "objective": None,
        "minimum_entry": None,
        "condition_number": None,
        "attempt": None,
    }
    weights = (1.0e-4, 1.0e-6, 1.0e-8)
    initials = _initial_transforms(scaled, attempts=attempts, rng=rng)
    for attempt_index, initial in enumerate(initials):
        weight = weights[attempt_index % len(weights)]

        def objective(flat: np.ndarray) -> tuple[float, np.ndarray]:
            return _negative_objective_and_gradient(
                flat,
                scaled,
                target_margin=target_margin,
                orthogonality_weight=weight,
            )

        result = minimize(
            objective,
            initial.ravel(),
            method="L-BFGS-B",
            jac=True,
            options={"maxiter": maxiter, "ftol": 1.0e-15, "gtol": 1.0e-10},
        )
        transform = np.asarray(result.x).reshape(initial.shape)
        condition = float(np.linalg.cond(transform))
        margin = transformed_nonnegative_margin(
            float_matrices,
            transform,
            tolerance=tolerance,
        )
        objective_value = float(result.fun)
        previous = best["objective"]
        if previous is None or objective_value < float(previous):
            best = {
                "objective": objective_value,
                "minimum_entry": margin,
                "condition_number": condition,
                "attempt": attempt_index,
                "optimizer_success": bool(result.success),
                "optimizer_message": str(result.message),
            }
        if (
            margin is None
            or not np.isfinite(condition)
            or condition > 1.0e10
        ):
            continue
        for denominator in (32, 128, 512, 2048, max_denominator):
            certificate = exact_simplicial_certificate(
                checked,
                transform,
                max_denominator=min(denominator, max_denominator),
            )
            if certificate is not None:
                certificate["numerical_discovery"] = {
                    "attempt": attempt_index,
                    "objective": objective_value,
                    "floating_minimum_entry": float(margin),
                    "condition_number": condition,
                }
                return certificate
    return {
        "status": "no-exact-certificate-found",
        "method": "numerical-common-simplicial",
        "attempts": attempts,
        "best": best,
    }


def search_card_shared_cones(
    card: Mapping[str, object],
    *,
    grades: Sequence[int] = (2, 3),
    attempts: int = 8,
    maxiter: int = 750,
    rng_seed: int = 121,
    tolerance: float = 1.0e-10,
    target_margin: float = 1.0e-7,
    max_denominator: int = 65536,
) -> dict[str, object]:
    """Search the requested exterior grades of one exact candidate card."""

    atoms = exact_atoms_from_card(card)
    dimension = atoms[0].rows
    checked_grades = tuple(int(grade) for grade in grades)
    if (
        not checked_grades
        or len(set(checked_grades)) != len(checked_grades)
        or any(not 0 <= grade <= dimension for grade in checked_grades)
    ):
        raise ValueError("grades must be unique valid exterior grades")

    grade_results: list[dict[str, object]] = []
    for grade in checked_grades:
        compounds = tuple(
            exact_compound_matrix(atom, grade) for atom in atoms
        )
        restricted = signed_monomial_triage(compounds)
        if restricted["status"] == "exact-certificate":
            result = restricted
        else:
            result = numerical_simplicial_search(
                compounds,
                attempts=attempts,
                maxiter=maxiter,
                rng_seed=rng_seed + 1009 * grade,
                tolerance=tolerance,
                target_margin=target_margin,
                max_denominator=max_denominator,
            )
        grade_results.append(
            {
                "grade": grade,
                "sector_dimension": compounds[0].rows,
                "restricted_triage": restricted,
                "search_result": result,
            }
        )

    exact_hit = all(
        grade["search_result"]["status"] == "exact-certificate"
        for grade in grade_results
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": candidate_id(card),
        "template": card["template"],
        "seed": card["seed"],
        "dimension": dimension,
        "status": (
            "exact-grade-shared-cones"
            if exact_hit
            else "no-complete-exact-certificate-found"
        ),
        "grades": grade_results,
    }


def search_targets(
    targets: Sequence[tuple[str, int]],
    **search_options: object,
) -> dict[str, object]:
    """Run a deterministic target tranche without loading survivor manifests."""

    results = [
        search_card_shared_cones(
            candidate_card(template=template, seed=seed),
            **search_options,
        )
        for template, seed in targets
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "targets": len(results),
        "exact_complete_hits": sum(
            result["status"] == "exact-grade-shared-cones"
            for result in results
        ),
        "results": results,
    }


def _parse_target(value: str) -> tuple[str, int]:
    template, separator, seed_text = value.rpartition(":")
    if not separator or not template:
        raise argparse.ArgumentTypeError("target must be TEMPLATE:SEED")
    try:
        seed = int(seed_text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("target seed must be an integer") from error
    return template, seed


def _parse_grades(value: str) -> tuple[int, ...]:
    try:
        grades = tuple(int(item) for item in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError("grades must be comma-separated integers") from error
    if not grades:
        raise argparse.ArgumentTypeError("at least one grade is required")
    return grades


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        action="append",
        type=_parse_target,
        help="TEMPLATE:SEED; repeatable (defaults to seven depth-16 survivors)",
    )
    parser.add_argument("--grades", type=_parse_grades, default=(2, 3))
    parser.add_argument("--attempts", type=int, default=8)
    parser.add_argument("--maxiter", type=int, default=750)
    parser.add_argument("--rng-seed", type=int, default=121)
    parser.add_argument("--tolerance", type=float, default=1.0e-10)
    parser.add_argument("--target-margin", type=float, default=1.0e-7)
    parser.add_argument("--max-denominator", type=int, default=65536)
    parser.add_argument("--output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    targets = tuple(args.target) if args.target else DEFAULT_TARGETS
    result = search_targets(
        targets,
        grades=args.grades,
        attempts=args.attempts,
        maxiter=args.maxiter,
        rng_seed=args.rng_seed,
        tolerance=args.tolerance,
        target_margin=args.target_margin,
        max_denominator=args.max_denominator,
    )
    if args.output is not None:
        _write_json_atomic(Path(args.output), result)
    print(
        json.dumps(
            result,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_TARGETS",
    "exact_compound_matrix",
    "exact_simplicial_certificate",
    "numerical_simplicial_search",
    "search_card_shared_cones",
    "search_targets",
    "signed_monomial_triage",
]
