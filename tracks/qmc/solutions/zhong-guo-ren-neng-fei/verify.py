#!/usr/bin/env python3
"""Numerical and exact checks for the issue #121 TN-semigroup construction.

The proof in README.md is the primary result. This program independently
checks known split-group anchors, total nonnegativity, the principal-minor
identity, the Fock-trace identity, novelty obstructions, and an exact
directed-closing-edge counterexample.
"""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from scipy.linalg import expm


RealArray = NDArray[np.float64]
ComplexArray = NDArray[np.complex128]


def product_exponentials(generators: list[RealArray]) -> RealArray:
    product = np.eye(generators[0].shape[0])
    for generator in generators:
        product = product @ expm(generator)
    return product


def det_i_plus(matrix: RealArray) -> float:
    return float(np.linalg.det(np.eye(matrix.shape[0]) + matrix))


def split_metric(n: int) -> RealArray:
    return np.diag(np.r_[np.ones(n), -np.ones(n)])


def split_lie_generator(
    rng: np.random.Generator, n: int, scale: float
) -> RealArray:
    eta = split_metric(n)
    raw = rng.normal(size=(2 * n, 2 * n))
    return scale * 0.5 * (raw - eta @ raw.T @ eta)


def split_cone_generator(
    rng: np.random.Generator, n: int, scale: float
) -> RealArray:
    eta = split_metric(n)
    lie_part = split_lie_generator(rng, n, scale)
    raw = rng.normal(size=(2 * n, 2 * n))
    positive = raw.T @ raw
    positive /= max(1.0, float(np.linalg.norm(positive, ord=2)))
    return lie_part + 0.5 * scale * eta @ positive


def test_known_anchors(
    rng: np.random.Generator, trials_per_cell: int
) -> dict[str, object]:
    lie_values: list[float] = []
    cone_values: list[float] = []
    max_lie_residual = 0.0
    max_cone_violation = 0.0

    for n in (1, 2, 3):
        eta = split_metric(n)
        for depth in (1, 2, 4, 8):
            for _ in range(trials_per_cell):
                lie_generators = [
                    split_lie_generator(rng, n, scale=0.22)
                    for _ in range(depth)
                ]
                lie_product = product_exponentials(lie_generators)
                lie_values.append(det_i_plus(lie_product))
                residual = np.linalg.norm(
                    lie_product.T @ eta @ lie_product - eta, ord=2
                )
                max_lie_residual = max(max_lie_residual, float(residual))

                cone_generators = [
                    split_cone_generator(rng, n, scale=0.14)
                    for _ in range(depth)
                ]
                for generator in cone_generators:
                    cone_matrix = generator.T @ eta + eta @ generator
                    minimum = float(np.linalg.eigvalsh(cone_matrix).min())
                    max_cone_violation = max(
                        max_cone_violation, max(0.0, -minimum)
                    )
                cone_values.append(
                    det_i_plus(product_exponentials(cone_generators))
                )

    tolerance = 1e-9
    return {
        "trials_per_dimension_depth_cell": trials_per_cell,
        "split_lie": {
            "samples": len(lie_values),
            "negative_count": sum(value < -tolerance for value in lie_values),
            "minimum_determinant": min(lie_values),
            "maximum_metric_residual": max_lie_residual,
        },
        "split_cone": {
            "samples": len(cone_values),
            "negative_count": sum(value < -tolerance for value in cone_values),
            "minimum_determinant": min(cone_values),
            "maximum_cone_violation": max_cone_violation,
        },
        "component_controls": {
            "O_minus_minus_determinant": det_i_plus(
                np.diag([-2.0, -0.5])
            ),
            "mixed_component_determinant": det_i_plus(
                np.diag([-1.0, 1.0])
            ),
        },
    }


def random_tridiagonal_metzler(
    rng: np.random.Generator, dimension: int, scale: float
) -> RealArray:
    generator = np.diag(rng.normal(scale=scale, size=dimension))
    if dimension > 1:
        upper = np.abs(rng.normal(scale=scale, size=dimension - 1))
        lower = np.abs(rng.normal(scale=scale, size=dimension - 1))
        generator += np.diag(upper, 1) + np.diag(lower, -1)
    return generator


def minimum_minor(matrix: RealArray) -> float:
    dimension = matrix.shape[0]
    answer = float("inf")
    indices = range(dimension)
    for order in range(1, dimension + 1):
        index_sets = list(combinations(indices, order))
        for rows in index_sets:
            for columns in index_sets:
                value = float(
                    np.linalg.det(matrix[np.ix_(rows, columns)])
                )
                answer = min(answer, value)
    return answer


def principal_minor_sum(matrix: RealArray) -> float:
    dimension = matrix.shape[0]
    total = 1.0
    indices = range(dimension)
    for order in range(1, dimension + 1):
        for subset in combinations(indices, order):
            total += float(np.linalg.det(matrix[np.ix_(subset, subset)]))
    return total


def generator_structure_violation(generator: RealArray) -> float:
    dimension = generator.shape[0]
    violation = 0.0
    for row in range(dimension):
        for column in range(dimension):
            if abs(row - column) > 1:
                violation = max(violation, abs(float(generator[row, column])))
            elif abs(row - column) == 1:
                violation = max(
                    violation, max(0.0, -float(generator[row, column]))
                )
    return violation


def test_tn_semigroup(
    rng: np.random.Generator,
    trials_per_cell: int,
    minor_checks_per_cell: int,
    identity_checks_per_cell: int,
) -> dict[str, object]:
    determinants: list[float] = []
    minimum_checked_minor = float("inf")
    minor_violations = 0
    minor_checks = 0
    identity_checks = 0
    max_identity_error = 0.0
    max_structure_violation = 0.0
    tolerance = 2e-8

    for dimension in range(1, 9):
        for depth in (1, 2, 4, 8):
            for trial in range(trials_per_cell):
                generators = [
                    random_tridiagonal_metzler(
                        rng, dimension=dimension, scale=0.24
                    )
                    for _ in range(depth)
                ]
                max_structure_violation = max(
                    max_structure_violation,
                    *(generator_structure_violation(item) for item in generators),
                )
                product = product_exponentials(generators)
                determinant = det_i_plus(product)
                determinants.append(determinant)

                if trial < minor_checks_per_cell:
                    checked_minimum = minimum_minor(product)
                    minimum_checked_minor = min(
                        minimum_checked_minor, checked_minimum
                    )
                    minor_violations += int(checked_minimum < -tolerance)
                    minor_checks += 1

                if trial < identity_checks_per_cell:
                    expansion = principal_minor_sum(product)
                    max_identity_error = max(
                        max_identity_error, abs(expansion - determinant)
                    )
                    identity_checks += 1

    return {
        "dimensions": list(range(1, 9)),
        "depths": [1, 2, 4, 8],
        "trials_per_dimension_depth_cell": trials_per_cell,
        "samples": len(determinants),
        "determinant_below_one_count": sum(
            value < 1.0 - tolerance for value in determinants
        ),
        "negative_determinant_count": sum(
            value < -tolerance for value in determinants
        ),
        "minimum_determinant": min(determinants),
        "maximum_determinant": max(determinants),
        "exhaustive_all_minor_checks": minor_checks,
        "minor_violation_count": minor_violations,
        "minimum_checked_minor": minimum_checked_minor,
        "principal_identity_checks": identity_checks,
        "maximum_principal_identity_error": max_identity_error,
        "maximum_generator_structure_violation": max_structure_violation,
    }


def annihilation_operator(dimension: int, orbital: int) -> ComplexArray:
    fock_dimension = 1 << dimension
    operator = np.zeros((fock_dimension, fock_dimension), dtype=np.complex128)
    lower_mask = (1 << orbital) - 1
    for state in range(fock_dimension):
        if state & (1 << orbital):
            target = state ^ (1 << orbital)
            sign = -1 if (state & lower_mask).bit_count() % 2 else 1
            operator[target, state] = sign
    return operator


def quadratic_lift(matrix: ComplexArray) -> ComplexArray:
    dimension = matrix.shape[0]
    annihilators = [
        annihilation_operator(dimension, orbital) for orbital in range(dimension)
    ]
    result = np.zeros((1 << dimension, 1 << dimension), dtype=np.complex128)
    for row in range(dimension):
        creator = annihilators[row].conj().T
        for column in range(dimension):
            result += matrix[row, column] * creator @ annihilators[column]
    return result


def fock_trace_check(rng: np.random.Generator) -> dict[str, float | int]:
    dimension = 5
    sequence = [
        random_tridiagonal_metzler(rng, dimension, scale=0.2)
        for _ in range(5)
    ]
    one_particle_product = product_exponentials(sequence)
    determinant = det_i_plus(one_particle_product)

    fock_product = np.eye(1 << dimension, dtype=np.complex128)
    for generator in sequence:
        lift = quadratic_lift(generator.astype(np.complex128))
        fock_product = fock_product @ expm(lift)
    fock_trace = np.trace(fock_product)

    return {
        "one_particle_dimension": dimension,
        "fock_dimension": 1 << dimension,
        "determinant": determinant,
        "fock_trace_real": float(fock_trace.real),
        "fock_trace_imag": float(fock_trace.imag),
        "absolute_difference": float(abs(fock_trace - determinant)),
    }


def matrix_unit(dimension: int, row: int, column: int) -> RealArray:
    result = np.zeros((dimension, dimension))
    result[row, column] = 1.0
    return result


def numerical_rank(matrix: RealArray, tolerance: float = 1e-10) -> int:
    singular_values = np.linalg.svd(matrix, compute_uv=False)
    if singular_values.size == 0:
        return 0
    threshold = tolerance * max(matrix.shape) * singular_values[0]
    return int(np.sum(singular_values > threshold))


def kramers_commutant_dimension(dimension: int) -> int:
    identity = np.eye(dimension)
    generators = [
        matrix_unit(dimension, index, index)
        for index in range(dimension)
    ]
    for index in range(dimension - 1):
        generators.append(matrix_unit(dimension, index, index + 1))
        generators.append(matrix_unit(dimension, index + 1, index))

    constraints = [
        np.kron(generator.T, identity)
        - np.kron(identity, generator)
        for generator in generators
    ]
    stacked = np.vstack(constraints)
    return dimension * dimension - numerical_rank(stacked)


def majorana_rotation(diagonal: RealArray) -> RealArray:
    zero = np.zeros_like(diagonal)
    return np.block([[zero, diagonal], [-diagonal, zero]])


def majorana_j2_nullity(dimension: int) -> int:
    """Dimension of skew J satisfying {J, R(D)} = 0 for all diagonal D."""
    doubled = 2 * dimension
    skew_basis: list[RealArray] = []
    for row in range(doubled):
        for column in range(row + 1, doubled):
            basis = np.zeros((doubled, doubled))
            basis[row, column] = 1.0
            basis[column, row] = -1.0
            skew_basis.append(basis)

    rotations = [
        majorana_rotation(
            np.diag(
                [
                    1.0 if index == selected else 0.0
                    for index in range(dimension)
                ]
            )
        )
        for selected in range(dimension)
    ]
    columns = []
    for basis in skew_basis:
        image = np.concatenate(
            [
                (basis @ rotation + rotation @ basis).reshape(-1)
                for rotation in rotations
            ]
        )
        columns.append(image)
    constraint = np.column_stack(columns)
    return len(skew_basis) - numerical_rank(constraint)


def novelty_obstruction_checks() -> dict[str, object]:
    dimensions = list(range(2, 9))
    return {
        "dimensions": dimensions,
        "dirac_commutant_dimensions": [
            kramers_commutant_dimension(item) for item in dimensions
        ],
        "majorana_skew_J2_nullities": [
            majorana_j2_nullity(item) for item in dimensions
        ],
        "expected_for_no_kramers": "all commutant dimensions equal 1",
        "expected_for_no_2024_contraction_J2": "all nullities equal 0",
    }


def det3_integer(matrix: NDArray[np.object_]) -> int:
    a, b, c = matrix[0]
    d, e, f = matrix[1]
    g, h, i = matrix[2]
    return int(
        a * (e * i - f * h)
        - b * (d * i - f * g)
        + c * (d * h - e * g)
    )


def exact_closing_edge_counterexample() -> dict[str, object]:
    identity = np.eye(3, dtype=object)

    def integer_unit(row: int, column: int) -> NDArray[np.object_]:
        result = np.zeros((3, 3), dtype=object)
        result[row, column] = 1
        return result

    e12 = integer_unit(0, 1)
    e31 = integer_unit(2, 0)
    e23 = integer_unit(1, 2)
    elementary_factors = [
        identity + e12,
        identity + e12,
        identity + e12,
        identity + e31,
        identity + e23,
        identity + e23,
        identity + e23,
    ]
    product = identity.copy()
    for factor in elementary_factors:
        product = product @ factor
    determinant = det3_integer(identity + product)

    return {
        "word": ["E12", "E12", "E12", "E31", "E23", "E23", "E23"],
        "each_factor_is": "exp(Eij) = I + Eij because Eij^2 = 0",
        "product": [[int(value) for value in row] for row in product],
        "I_plus_product": [
            [int(value) for value in row] for row in identity + product
        ],
        "exact_integer_determinant": determinant,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trials",
        type=int,
        default=250,
        help="TN trials per dimension/depth cell (default: 250)",
    )
    parser.add_argument(
        "--anchor-trials",
        type=int,
        default=50,
        help="known-class anchor trials per cell (default: 50)",
    )
    parser.add_argument("--seed", type=int, default=121)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("results.json"),
    )
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    results = {
        "seed": args.seed,
        "known_anchors": test_known_anchors(rng, args.anchor_trials),
        "tn_semigroup": test_tn_semigroup(
            rng,
            trials_per_cell=args.trials,
            minor_checks_per_cell=2,
            identity_checks_per_cell=3,
        ),
        "fock_trace_check": fock_trace_check(rng),
        "novelty_obstruction_checks": novelty_obstruction_checks(),
        "exact_closing_edge_counterexample": (
            exact_closing_edge_counterexample()
        ),
    }
    args.output.write_text(
        json.dumps(results, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(results, indent=2, sort_keys=True), flush=True)

    known = results["known_anchors"]
    tn = results["tn_semigroup"]
    fock = results["fock_trace_check"]
    obstruction = results["novelty_obstruction_checks"]
    counterexample = results["exact_closing_edge_counterexample"]

    failed = (
        known["split_lie"]["negative_count"] != 0
        or known["split_cone"]["negative_count"] != 0
        or known["component_controls"]["O_minus_minus_determinant"] >= 0
        or abs(known["component_controls"]["mixed_component_determinant"]) > 1e-12
        or tn["determinant_below_one_count"] != 0
        or tn["minor_violation_count"] != 0
        or tn["maximum_principal_identity_error"] > 2e-7
        or fock["absolute_difference"] > 2e-8
        or any(
            value != 1
            for value in obstruction["dirac_commutant_dimensions"]
        )
        or any(
            value != 0
            for value in obstruction["majorana_skew_J2_nullities"]
        )
        or counterexample["exact_integer_determinant"] != -1
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
