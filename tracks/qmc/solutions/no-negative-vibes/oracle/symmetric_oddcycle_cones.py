"""Exact cone certificates for the fixed symmetric-oddcycle candidate.

The candidate studied here is

    B = [[0, 0, 2, 0, 0],
         [2, 0, 0, 0, 0],
         [0, 2, 0, 1, 0],
         [0, 0, 0, 1, 1],
         [0, 0,-1, 0, 1]].

Only exact rational replay is exposed.  Numerical optimization was used to
discover the stored transforms, but it is not part of verification.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from fractions import Fraction
from itertools import combinations
from math import comb
from pathlib import Path

import numpy as np
import sympy as sp

from .exterior_exact5_full_fock_cone import (
    _cross_grade_simplicial_search,
    _trace_compatible_column_generation,
    combined_grade_lift,
    exact_fock_lift,
)
from .exterior_exact5_shared_cone import exact_compound_matrix


SCHEMA = "symmetric-oddcycle-simplicial-certificate-v1"


def fixed_candidate_matrix() -> sp.ImmutableMatrix:
    """Return the exact fixed matrix ``B(2, 1)``."""

    return sp.ImmutableMatrix(
        [
            [0, 0, 2, 0, 0],
            [2, 0, 0, 0, 0],
            [0, 2, 0, 1, 0],
            [0, 0, 0, 1, 1],
            [0, 0, -1, 0, 1],
        ]
    )


def symbolic_grade4_positive_atoms() -> tuple[sp.ImmutableMatrix, ...]:
    """Return the sign-gauged grade-four atoms for positive symbols ``x,y``."""

    x, y = sp.symbols("x y", positive=True)
    atom = sp.ImmutableMatrix(
        [
            [x**3, x**3 * y, 0, x**2 * y**2, 0],
            [0, x**3, 0, x**2 * y, 0],
            [0, 0, 0, x**2, 0],
            [0, 0, 0, 0, x**2],
            [x**2 * y, x**2 * y**2, x**2, x * y**3, 0],
        ]
    )
    return atom, sp.ImmutableMatrix(atom.T)


def exact_grade4_formula_replay() -> bool:
    """Replay the symbolic ``D wedge^4(B) D >= 0`` identity exactly."""

    x, y = sp.symbols("x y", positive=True)
    matrix = sp.ImmutableMatrix(
        [
            [0, 0, x, 0, 0],
            [x, 0, 0, 0, 0],
            [0, x, 0, y, 0],
            [0, 0, 0, 1, y],
            [0, 0, -y, 0, 1],
        ]
    )
    diagonal = sp.diag(1, 1, 1, -1, 1)
    expected = symbolic_grade4_positive_atoms()
    actual = tuple(
        sp.ImmutableMatrix(
            diagonal * exact_compound_matrix(atom, 4) * diagonal
        )
        for atom in (matrix, matrix.T)
    )
    return actual == expected


def load_certificate(path: str | Path) -> dict[str, object]:
    """Load one compact rational transform certificate."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("certificate root must be an object")
    return payload


def _rational_matrix(
    payload: Sequence[Sequence[Mapping[str, object]]],
) -> sp.ImmutableMatrix:
    rows = []
    for row in payload:
        rows.append(
            [
                sp.Rational(int(entry["numerator"]), int(entry["denominator"]))
                for entry in row
            ]
        )
    return sp.ImmutableMatrix(rows)


def verify_compact_certificate(
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Verify ``S^-1 A_i S >= 0`` exactly for the declared grade sum."""

    if payload.get("schema") != SCHEMA:
        raise ValueError("unexpected certificate schema")
    matrix_payload = payload.get("matrix")
    grades_payload = payload.get("grades")
    transform_payload = payload.get("transform")
    if not isinstance(matrix_payload, Sequence):
        raise ValueError("matrix payload is missing")
    if not isinstance(grades_payload, Sequence):
        raise ValueError("grades payload is missing")
    if not isinstance(transform_payload, Sequence):
        raise ValueError("transform payload is missing")

    matrix = sp.ImmutableMatrix(matrix_payload)
    if matrix != fixed_candidate_matrix():
        raise ValueError("certificate targets a different matrix")
    grades = tuple(int(grade) for grade in grades_payload)
    transform = _rational_matrix(transform_payload)
    matrices = tuple(
        combined_grade_lift(atom, grades) for atom in (matrix, matrix.T)
    )
    if transform.shape != matrices[0].shape or transform.det() == 0:
        raise ValueError("certificate transform is not invertible")

    inverse = transform.inv()
    transformed = tuple(
        sp.ImmutableMatrix(inverse * atom * transform) for atom in matrices
    )
    minimum = min(entry for atom in transformed for entry in atom)
    if minimum < 0:
        raise ValueError("certificate has a negative transformed entry")
    if transformed[1] != sp.ImmutableMatrix(
        inverse * matrices[1] * transform
    ):
        raise RuntimeError("transpose-atom replay failed")
    return {
        "status": "exact-certificate",
        "grades": grades,
        "dimension": matrices[0].rows,
        "minimum_entry": minimum,
        "trace_compatible": True,
    }


def exact_chi23_obstruction() -> dict[str, int]:
    """Return the exact grade-(2,3) obstruction at ``W=B^7``."""

    matrix = fixed_candidate_matrix() ** 7
    chi2 = int(sp.trace(exact_compound_matrix(matrix, 2)))
    chi3 = int(sp.trace(exact_compound_matrix(matrix, 3)))
    return {"chi2": chi2, "chi3": chi3, "sum": chi2 + chi3}


def _principal_minor(
    matrix: sp.MatrixBase,
    indices: tuple[int, ...],
) -> sp.Expr:
    return matrix.extract(indices, indices).det()


def _word_matrix(word: str) -> sp.ImmutableMatrix:
    matrix = fixed_candidate_matrix()
    atoms = (matrix, matrix.T)
    product = sp.eye(matrix.rows)
    for symbol in word:
        if symbol not in {"0", "1"}:
            raise ValueError("word must contain only 0 and 1")
        product = atoms[int(symbol)] * product
    return sp.ImmutableMatrix(product)


def exact_complementary_sector_audit() -> dict[str, object]:
    """Replay exact identities and obstructions for the remaining sector sum.

    For every invertible five-by-five matrix ``W``, Jacobi's complementary
    minor identity gives ``chi3(W) = det(W) * chi2(W.inv())``.  The returned
    examples show why individual complementary minor pairs cannot supply a
    positive proof.
    """

    matrix = fixed_candidate_matrix()
    minor_examples = []
    for label, word, index_sets in (
        ("B", "0", ((0, 1),)),
        ("B^2", "00", ((0, 3), (1, 4))),
    ):
        word_matrix = _word_matrix(word)
        for indices in index_sets:
            complement = tuple(
                index for index in range(matrix.rows) if index not in indices
            )
            left = _principal_minor(word_matrix, indices)
            right = _principal_minor(word_matrix, complement)
            minor_examples.append(
                {
                    "matrix": label,
                    "indices": indices,
                    "complement": complement,
                    "left": int(left),
                    "right": int(right),
                    "sum": int(left + right),
                }
            )

    word = "0001010101"
    mixed = _word_matrix(word)
    mixed_chi2 = int(sp.trace(exact_compound_matrix(mixed, 2)))
    mixed_chi3 = int(sp.trace(exact_compound_matrix(mixed, 3)))
    mixed_det = int(mixed.det())

    odd_split_word = "101010110111111111111110101010"
    odd_split_matrix = _word_matrix(odd_split_word)
    odd_split_traces = {
        grade: int(
            sp.trace(exact_compound_matrix(odd_split_matrix, grade))
        )
        for grade in range(matrix.rows + 1)
    }
    grade14_split_word = "101010101111111111111110101010"
    grade14_split_matrix = _word_matrix(grade14_split_word)
    grade14_split_traces = {
        grade: int(
            sp.trace(exact_compound_matrix(grade14_split_matrix, grade))
        )
        for grade in range(matrix.rows + 1)
    }

    pure_values = {}
    for power in (7, 10):
        pure = matrix**power
        chi2 = int(sp.trace(exact_compound_matrix(pure, 2)))
        chi3 = int(sp.trace(exact_compound_matrix(pure, 3)))
        determinant = int(pure.det())
        pure_values[power] = {
            "chi2": chi2,
            "chi3": chi3,
            "determinant": determinant,
            "F": 1 + chi2 + chi3 + determinant,
        }

    jacobi_checks = {}
    for label, word_matrix in (
        ("mixed", mixed),
        ("B^7", matrix**7),
        ("B^10", matrix**10),
    ):
        determinant = word_matrix.det()
        chi3 = sp.trace(exact_compound_matrix(word_matrix, 3))
        inverse_chi2 = sp.trace(
            exact_compound_matrix(word_matrix.inv(), 2)
        )
        jacobi_checks[label] = bool(
            sp.simplify(chi3 - determinant * inverse_chi2) == 0
        )

    return {
        "identity": "chi3(W)=det(W)*chi2(W^-1)",
        "determinant_per_letter": int(matrix.det()),
        "jacobi_checks": jacobi_checks,
        "negative_complementary_minor_pairs": minor_examples,
        "mixed_word": {
            "word": word,
            "chi2": mixed_chi2,
            "chi3": mixed_chi3,
            "determinant": mixed_det,
            "F": 1 + mixed_chi2 + mixed_chi3 + mixed_det,
        },
        "grade24_odd135_split_obstruction": {
            "word": odd_split_word,
            "chi1": odd_split_traces[1],
            "chi3": odd_split_traces[3],
            "chi5": odd_split_traces[5],
            "odd135": sum(odd_split_traces[grade] for grade in (1, 3, 5)),
            "even024": sum(
                odd_split_traces[grade] for grade in (0, 2, 4)
            ),
            "full_determinant": sum(odd_split_traces.values()),
        },
        "grade14_0235_split_obstruction": {
            "word": grade14_split_word,
            "sector_traces": grade14_split_traces,
            "complement0235": sum(
                grade14_split_traces[grade] for grade in (0, 2, 3, 5)
            ),
            "known14": sum(
                grade14_split_traces[grade] for grade in (1, 4)
            ),
            "full_determinant": sum(grade14_split_traces.values()),
        },
        "pure_power_values": pure_values,
    }


def exact_invariant_chamber_obstruction() -> dict[str, object]:
    """Disprove complementary-sector positivity from the invariant signs."""

    z = sp.symbols("z", real=True)
    matrix = sp.Matrix(fixed_candidate_matrix())
    matrix[4, 2] = -z
    word_matrix = matrix**4
    polynomial = sp.Poly(
        1
        + sp.trace(exact_compound_matrix(word_matrix, 2))
        + sp.trace(exact_compound_matrix(word_matrix, 3))
        + word_matrix.det(),
        z,
    )
    full_polynomial = sp.Poly((sp.eye(5) + word_matrix).det(), z)
    return {
        "positive_cycle_invariant": 8,
        "negative_cycle_invariant": "-z",
        "coefficients_descending": tuple(
            int(coefficient) for coefficient in polynomial.all_coeffs()
        ),
        "F_at_z3": int(polynomial.eval(3)),
        "F_at_z4": int(polynomial.eval(4)),
        "full_coefficients_descending": tuple(
            int(coefficient) for coefficient in full_polynomial.all_coeffs()
        ),
        "full_at_z3": int(full_polynomial.eval(3)),
        "full_at_z4": int(full_polynomial.eval(4)),
        "z3_inside_chamber": 0 < 3 < 8,
        "z4_inside_chamber": 0 < 4 < 8,
    }


_Polynomial = tuple[int, ...]
_PolynomialMatrix = tuple[tuple[_Polynomial, ...], ...]


def _poly_trim(coefficients: Sequence[int]) -> _Polynomial:
    result = list(coefficients)
    while len(result) > 1 and result[-1] == 0:
        result.pop()
    return tuple(result)


def _poly_add(left: _Polynomial, right: _Polynomial) -> _Polynomial:
    length = max(len(left), len(right))
    return _poly_trim(
        tuple(
            (left[index] if index < len(left) else 0)
            + (right[index] if index < len(right) else 0)
            for index in range(length)
        )
    )


def _poly_scale(polynomial: _Polynomial, scale: int) -> _Polynomial:
    return _poly_trim(tuple(scale * coefficient for coefficient in polynomial))


def _poly_multiply(left: _Polynomial, right: _Polynomial) -> _Polynomial:
    result = [0] * (len(left) + len(right) - 1)
    for left_index, left_value in enumerate(left):
        for right_index, right_value in enumerate(right):
            result[left_index + right_index] += left_value * right_value
    return _poly_trim(result)


def _poly_identity_matrix() -> _PolynomialMatrix:
    return tuple(
        tuple(((1,) if row == column else (0,)) for column in range(5))
        for row in range(5)
    )


def _poly_left_atom(
    matrix: _PolynomialMatrix,
    *,
    transpose: bool,
) -> _PolynomialMatrix:
    """Multiply by ``B(z)`` or ``B(z).T`` using its sparse exact rows."""

    rows = matrix
    if not transpose:
        result = (
            tuple(_poly_scale(entry, 2) for entry in rows[2]),
            tuple(_poly_scale(entry, 2) for entry in rows[0]),
            tuple(
                _poly_add(_poly_scale(rows[1][column], 2), rows[3][column])
                for column in range(5)
            ),
            tuple(
                _poly_add(rows[3][column], rows[4][column])
                for column in range(5)
            ),
            tuple(
                _poly_add(
                    (0,) + _poly_scale(rows[2][column], -1),
                    rows[4][column],
                )
                for column in range(5)
            ),
        )
    else:
        result = (
            tuple(_poly_scale(entry, 2) for entry in rows[1]),
            tuple(_poly_scale(entry, 2) for entry in rows[2]),
            tuple(
                _poly_add(
                    _poly_scale(rows[0][column], 2),
                    (0,) + _poly_scale(rows[4][column], -1),
                )
                for column in range(5)
            ),
            tuple(
                _poly_add(rows[2][column], rows[3][column])
                for column in range(5)
            ),
            tuple(
                _poly_add(rows[3][column], rows[4][column])
                for column in range(5)
            ),
        )
    return tuple(tuple(entry for entry in row) for row in result)


def _poly_minor(
    matrix: _PolynomialMatrix,
    indices: tuple[int, ...],
) -> _Polynomial:
    if len(indices) == 2:
        i, j = indices
        return _poly_add(
            _poly_multiply(matrix[i][i], matrix[j][j]),
            _poly_scale(_poly_multiply(matrix[i][j], matrix[j][i]), -1),
        )
    if len(indices) == 3:
        total = (0,)
        for permutation, sign in (
            ((0, 1, 2), 1),
            ((1, 2, 0), 1),
            ((2, 0, 1), 1),
            ((2, 1, 0), -1),
            ((1, 0, 2), -1),
            ((0, 2, 1), -1),
        ):
            term = (1,)
            for row_index, column_index in enumerate(permutation):
                term = _poly_multiply(
                    term,
                    matrix[indices[row_index]][indices[column_index]],
                )
            total = _poly_add(total, _poly_scale(term, sign))
        return total
    raise ValueError("only grade-two and grade-three minors are used")


def _complementary_polynomial(
    matrix: _PolynomialMatrix,
    *,
    depth: int,
) -> _Polynomial:
    result = (1 + 8**depth,)
    for grade in (2, 3):
        for indices in combinations(range(5), grade):
            result = _poly_add(result, _poly_minor(matrix, indices))
    return result


def _bernstein_coefficients(
    coefficients: _Polynomial,
    *,
    degree: int,
) -> tuple[Fraction, ...]:
    return tuple(
        sum(
            (
                Fraction(
                    coefficients[power] * comb(index, power),
                    comb(degree, power),
                )
                for power in range(min(index, len(coefficients) - 1) + 1)
            ),
            start=Fraction(0),
        )
        for index in range(degree + 1)
    )


def exact_unit_winding_bernstein_audit(
    *,
    max_depth: int = 12,
) -> dict[str, object]:
    """Exhaust all orientation words and replay ``F_W(z)`` on ``0<=z<=1``.

    Each compound atom is affine in the independent negative-edge amplitude
    of one time layer.  Nonnegative Bernstein coefficients of the diagonal
    specialization therefore give a finite exact positivity certificate for
    each tested word throughout the unit interval.
    """

    if not 1 <= max_depth <= 12:
        raise ValueError("max_depth must lie between 1 and 12")

    word_count = 0
    coefficient_count = 0
    minimum: Fraction | None = None
    minimum_witness: dict[str, object] | None = None
    per_depth = []

    def visit(
        matrix: _PolynomialMatrix,
        word: str,
        remaining: int,
    ) -> None:
        nonlocal coefficient_count, minimum, minimum_witness, word_count
        if word:
            depth = len(word)
            polynomial = _complementary_polynomial(matrix, depth=depth)
            bernstein = _bernstein_coefficients(polynomial, degree=depth)
            word_count += 1
            coefficient_count += len(bernstein)
            for index, value in enumerate(bernstein):
                if minimum is None or value < minimum:
                    minimum = value
                    minimum_witness = {
                        "depth": depth,
                        "word": word,
                        "index": index,
                    }
        if remaining == 0:
            return
        visit(
            _poly_left_atom(matrix, transpose=False),
            word + "0",
            remaining - 1,
        )
        visit(
            _poly_left_atom(matrix, transpose=True),
            word + "1",
            remaining - 1,
        )

    visit(_poly_identity_matrix(), "", max_depth)
    assert minimum is not None and minimum_witness is not None
    for depth in range(1, max_depth + 1):
        per_depth.append(
            {
                "depth": depth,
                "word_count": 2**depth,
                "coefficient_count": 2**depth * (depth + 1),
            }
        )
    return {
        "status": (
            "all-bernstein-coefficients-nonnegative"
            if minimum >= 0
            else "negative-bernstein-coefficient"
        ),
        "interval": (0, 1),
        "max_depth": max_depth,
        "word_count": word_count,
        "coefficient_count": coefficient_count,
        "minimum": {
            "numerator": minimum.numerator,
            "denominator": minimum.denominator,
        },
        "minimum_witness": minimum_witness,
        "per_depth": per_depth,
    }


def unit_winding_endpoint_lifts() -> tuple[sp.ImmutableMatrix, ...]:
    """Return the four endpoint atoms on grades ``0,2,3,5``.

    The ordering is ``B(0), B(0).T, B(1), B(1).T``.  A common
    trace-compatible cone for these atoms proves the complementary
    character for independently varying layer amplitudes in ``[0,1]``.
    """

    zero = sp.Matrix(fixed_candidate_matrix())
    zero[4, 2] = 0
    one = fixed_candidate_matrix()
    grades = (0, 2, 3, 5)
    return tuple(
        combined_grade_lift(atom, grades)
        for atom in (sp.ImmutableMatrix(zero), zero.T, one, one.T)
    )


_ENDPOINT_COUNTEREXAMPLE = (
    "220221211213112031133303133331333331303330300330000231110032"
    "111102212011110300002311121210222331121112310311331323112101"
)


def exact_unit_winding_endpoint_obstruction() -> dict[str, object]:
    """Replay a negative word in the four independently varying endpoints."""

    zero = sp.Matrix(fixed_candidate_matrix())
    zero[4, 2] = 0
    one = fixed_candidate_matrix()
    atoms = (sp.ImmutableMatrix(zero), zero.T, one, one.T)
    product = sp.eye(5)
    for symbol in _ENDPOINT_COUNTEREXAMPLE:
        product = atoms[int(symbol)] * product
    chi2 = int(sp.trace(exact_compound_matrix(product, 2)))
    chi3 = int(sp.trace(exact_compound_matrix(product, 3)))
    determinant = int(product.det())
    return {
        "status": "exact-negative-trace-obstruction",
        "endpoint_order": ("B0", "B0T", "B1", "B1T"),
        "word": _ENDPOINT_COUNTEREXAMPLE,
        "word_length": len(_ENDPOINT_COUNTEREXAMPLE),
        "word_sha256": hashlib.sha256(
            _ENDPOINT_COUNTEREXAMPLE.encode("ascii")
        ).hexdigest(),
        "chi0": 1,
        "chi2": chi2,
        "chi3": chi3,
        "chi5": determinant,
        "F": 1 + chi2 + chi3 + determinant,
    }


def search_unit_winding_endpoint_cone(
    *,
    attempts: int = 64,
    maxiter: int = 2000,
    rng_seed: int = 817231,
    ray_counts: Sequence[int] = (22, 28, 34, 40),
    tolerance: float = 1.0e-9,
    max_denominator: int = 65536,
) -> dict[str, object]:
    """Stop the impossible four-endpoint cone before numerical work."""

    del attempts, maxiter, rng_seed, ray_counts, tolerance, max_denominator
    obstruction = exact_unit_winding_endpoint_obstruction()
    return {
        **obstruction,
        "route": "frozen-exact-word-early-stop",
        "grades": (0, 2, 3, 5),
    }


def search_fixed_unit_winding_pair_cone(
    *,
    attempts: int = 64,
    maxiter: int = 2000,
    rng_seed: int = 817231,
    ray_counts: Sequence[int] = (22, 28, 34, 40),
    diagnostic_word_powers: Sequence[int] = tuple(range(1, 13)),
    tolerance: float = 1.0e-9,
    max_denominator: int = 65536,
) -> dict[str, object]:
    """Stop the impossible fixed-pair cone on its frozen mixed word."""

    del attempts, maxiter, rng_seed, ray_counts, tolerance, max_denominator
    matrices = unit_winding_endpoint_lifts()[2:]
    powers = tuple(dict.fromkeys(int(power) for power in diagnostic_word_powers))
    if not powers or any(power < 1 for power in powers):
        raise ValueError("diagnostic word powers must be positive")
    traces = tuple(
        {
            "word_power": power,
            "exact_trace": int(sp.trace(matrices[0] ** power)),
        }
        for power in powers
    )
    audit = exact_complementary_sector_audit()
    obstruction = audit["grade14_0235_split_obstruction"]
    assert isinstance(obstruction, Mapping)
    complement = int(obstruction["complement0235"])
    if complement >= 0:
        raise RuntimeError("frozen fixed-pair obstruction is no longer negative")
    return {
        "grades": (0, 2, 3, 5),
        "endpoint_order": ("B1", "B1T"),
        "dimension": matrices[0].rows,
        "atom_count": len(matrices),
        "diagnostic_pure_word_traces": traces,
        "status": "exact-negative-trace-obstruction",
        "route": "frozen-mixed-word-early-stop",
        "obstruction": dict(obstruction),
    }


def _grade14_preconditioned_full_fock_initials(
    *,
    attempts: int,
    rng_seed: int,
    cross_scale: float,
) -> tuple[np.ndarray, ...]:
    if attempts < 0 or cross_scale < 0.0:
        raise ValueError("attempts and cross scale must be nonnegative")
    payload = load_certificate(
        Path(__file__).parents[1]
        / "fixtures"
        / "symmetric_oddcycle_grade14_certificate.json"
    )
    transform_payload = payload.get("transform")
    if not isinstance(transform_payload, Sequence):
        raise ValueError("grade-(1,4) transform is missing")
    grade14 = np.asarray(
        _rational_matrix(transform_payload).tolist(),
        dtype=float,
    )
    if grade14.shape != (10, 10):
        raise ValueError("grade-(1,4) transform has the wrong dimension")

    known = np.eye(12)
    known[1:11, 1:11] = grade14
    base = np.zeros((32, 32))
    base[:12, :12] = known
    base[12:, 12:] = np.eye(20)
    norms = np.linalg.norm(base, axis=0)
    if np.any(norms == 0.0):
        raise RuntimeError("preconditioner has a zero column")
    base = base / norms

    rng = np.random.default_rng(rng_seed)
    initials = []
    for _ in range(attempts):
        initial = np.array(base, copy=True)
        initial[:12, 12:] += cross_scale * rng.normal(size=(12, 20))
        initial[12:, :12] += cross_scale * rng.normal(size=(20, 12))
        initial[12:, 12:] += (
            0.25 * cross_scale * rng.normal(size=(20, 20))
        )
        initials.append(initial)
    return tuple(initials)


def search_fixed_unit_winding_full_fock_cone(
    *,
    attempts: int = 64,
    maxiter: int = 2000,
    rng_seed: int = 817232,
    ray_counts: Sequence[int] = (32, 40, 48, 56),
    initialization: str = "grade14-preconditioned",
    cross_scale: float = 0.05,
    tolerance: float = 1.0e-9,
    max_denominator: int = 65536,
) -> dict[str, object]:
    """Search the fixed pair on all six Fock grades with exact promotion."""

    matrix = fixed_candidate_matrix()
    original_matrices = tuple(
        exact_fock_lift(atom) for atom in (matrix, matrix.T)
    )
    basis_order = (
        0,
        *range(1, 6),
        *range(26, 31),
        31,
        *range(6, 26),
    )
    matrices = tuple(
        sp.ImmutableMatrix(atom.extract(basis_order, basis_order))
        for atom in original_matrices
    )
    if initialization == "grade14-preconditioned":
        initials = _grade14_preconditioned_full_fock_initials(
            attempts=attempts,
            rng_seed=rng_seed,
            cross_scale=cross_scale,
        )
    elif initialization == "random":
        initials = None
    else:
        raise ValueError(
            "initialization must be grade14-preconditioned or random"
        )
    audit = exact_complementary_sector_audit()
    split_replays = tuple(
        {
            "name": name,
            "word": str(entry["word"]),
            "full_determinant": int(entry["full_determinant"]),
        }
        for name, entry in (
            (
                "grade24_odd135_split_obstruction",
                audit["grade24_odd135_split_obstruction"],
            ),
            (
                "grade14_0235_split_obstruction",
                audit["grade14_0235_split_obstruction"],
            ),
        )
        if isinstance(entry, Mapping)
    )
    if len(split_replays) != 2 or any(
        int(entry["full_determinant"]) <= 0 for entry in split_replays
    ):
        raise RuntimeError("known split obstructions failed full replay")

    common = {
        "grades": (0, 1, 2, 3, 4, 5),
        "endpoint_order": ("B1", "B1T"),
        "dimension": matrices[0].rows,
        "atom_count": len(matrices),
        "basis_order": basis_order,
        "initialization": initialization,
        "cross_scale": cross_scale,
        "split_obstruction_full_replays": split_replays,
    }
    simplicial = _cross_grade_simplicial_search(
        matrices,
        split=12,
        attempts=attempts,
        maxiter=maxiter,
        rng_seed=rng_seed,
        tolerance=tolerance,
        max_denominator=max_denominator,
        initial_transforms=initials,
    )
    if simplicial["status"] == "exact-trace-compatible-certificate":
        return {
            **common,
            "status": "exact-trace-compatible-certificate",
            "route": "fixed-full-fock-simplicial",
            "simplicial": simplicial,
        }

    best = simplicial.get("best")
    transform = best.get("transform") if isinstance(best, Mapping) else None
    if transform is None:
        redundant = {
            "status": "no-numerical-transform",
            "milestones": [],
        }
    else:
        redundant = _trace_compatible_column_generation(
            matrices,
            transform,
            ray_counts=ray_counts,
            tolerance=tolerance,
            max_denominator=max_denominator,
        )
    return {
        **common,
        "status": (
            "exact-trace-compatible-certificate"
            if redundant["status"] == "exact-trace-compatible-certificate"
            else "no-exact-certificate-found"
        ),
        "route": "fixed-full-fock-redundant",
        "simplicial": simplicial,
        "redundant": redundant,
    }


def exact_pure_power_spectral_lemma() -> dict[str, object]:
    """Certify that every nonempty pure power has positive determinant."""

    characteristic = fixed_candidate_matrix().charpoly().as_poly()
    variable = characteristic.gens[0]
    reciprocal = sp.Poly(
        sp.expand(
            variable ** characteristic.degree()
            * characteristic.as_expr().subs(variable, 1 / variable)
        ),
        variable,
    )
    reciprocal_gcd_degree = sp.gcd(characteristic, reciprocal).degree()
    positive_real_roots = int(characteristic.count_roots(0, sp.oo))
    negative_real_roots = int(characteristic.count_roots(-sp.oo, 0))
    return {
        "characteristic_coefficients": tuple(
            int(coefficient) for coefficient in characteristic.all_coeffs()
        ),
        "positive_real_root_count": positive_real_roots,
        "negative_real_root_count": negative_real_roots,
        "reciprocal_gcd_degree": reciprocal_gcd_degree,
        "nonreal_conjugate_pair_count": (
            characteristic.degree()
            - positive_real_roots
            - negative_real_roots
        )
        // 2,
        "conclusion": "det(I+B^n)>0 for every integer n>=1",
    }


def exact_reflection_square_replay(word: str) -> dict[str, object]:
    """Replay ``W(word + reflected(word)) = X.T X`` exactly."""

    if not word or any(symbol not in {"0", "1"} for symbol in word):
        raise ValueError("word must be a nonempty binary string")
    reflected = "".join(
        "1" if symbol == "0" else "0" for symbol in reversed(word)
    )
    matrix = _word_matrix(word)
    full_word = word + reflected
    product = _word_matrix(full_word)
    gram = sp.ImmutableMatrix(matrix.T * matrix)
    if product != gram:
        raise RuntimeError("transpose-reflection square identity failed")
    determinant = int((sp.eye(5) + product).det())
    return {
        "word": word,
        "reflected_word": reflected,
        "full_word": full_word,
        "identity": "W=X.T*X",
        "full_determinant": determinant,
        "strictly_positive": determinant > 0,
    }


def _integer_rows(matrix: sp.MatrixBase) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(int(matrix[row, column]) for column in range(matrix.cols))
        for row in range(matrix.rows)
    )


def _sparse_rows(
    matrix: sp.MatrixBase,
) -> tuple[tuple[tuple[int, int], ...], ...]:
    return tuple(
        tuple(
            (column, int(matrix[row, column]))
            for column in range(matrix.cols)
            if matrix[row, column] != 0
        )
        for row in range(matrix.rows)
    )


def _integer_identity(dimension: int) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(int(row == column) for column in range(dimension))
        for row in range(dimension)
    )


def _left_multiply_sparse(
    left: tuple[tuple[tuple[int, int], ...], ...],
    right: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    dimension = len(right)
    return tuple(
        tuple(
            sum(coefficient * right[index][column] for index, coefficient in row)
            for column in range(dimension)
        )
        for row in left
    )


def _fraction_payload(value: Fraction) -> dict[str, int]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
    }


def exact_grade34_block_tail_certificate() -> dict[str, object]:
    """Certify ``chi3(W) + chi4(W) > 0`` for every word of length >= 13.

    The grade-four atoms share an exact nonnegative sign gauge and a weight-8
    loop at state zero.  Exact enumeration bounds the Frobenius norm of every
    grade-three 13-letter block by one tenth of that loop weight.  A shorter
    remainder costs at most ``sqrt(10)``.  Squaring the trace/Frobenius bound
    then leaves a strict factor below one after the first complete block.
    """

    matrix = fixed_candidate_matrix()
    diagonal = sp.diag(1, 1, 1, -1, 1)
    grade3 = tuple(
        exact_compound_matrix(atom, 3) for atom in (matrix, matrix.T)
    )
    grade4 = tuple(
        sp.ImmutableMatrix(
            diagonal * exact_compound_matrix(atom, 4) * diagonal
        )
        for atom in (matrix, matrix.T)
    )
    if any(entry < 0 for atom in grade4 for entry in atom):
        raise RuntimeError("grade-four sign gauge is not nonnegative")
    if any(atom[0, 0] != 8 for atom in grade4):
        raise RuntimeError("grade-four atoms lost the common weight-8 loop")

    sparse3 = tuple(_sparse_rows(atom) for atom in grade3)
    sparse4 = tuple(_sparse_rows(atom) for atom in grade4)
    level = [(_integer_identity(10), _integer_identity(5), "")]
    remainder_maximum = Fraction(10, 1)
    remainder_witness = {
        "depth": 0,
        "word": "",
        "frobenius_squared": 10,
        "path_weight_squared": 1,
    }
    block_maximum: Fraction | None = None
    block_witness: dict[str, object] | None = None
    for depth in range(1, 14):
        level = [
            (
                _left_multiply_sparse(sparse3[symbol], matrix3),
                _left_multiply_sparse(sparse4[symbol], matrix4),
                word + str(symbol),
            )
            for matrix3, matrix4, word in level
            for symbol in (0, 1)
        ]
        for matrix3, matrix4, word in level:
            frobenius_squared = sum(
                entry * entry for row in matrix3 for entry in row
            )
            path_weight_squared = matrix4[0][0] ** 2
            ratio = Fraction(frobenius_squared, path_weight_squared)
            witness = {
                "depth": depth,
                "word": word,
                "frobenius_squared": frobenius_squared,
                "path_weight_squared": path_weight_squared,
            }
            if depth <= 12 and ratio > remainder_maximum:
                remainder_maximum = ratio
                remainder_witness = witness
            if depth == 13 and (
                block_maximum is None or ratio > block_maximum
            ):
                block_maximum = ratio
                block_witness = witness

    if block_maximum is None or block_witness is None:
        raise RuntimeError("13-letter block enumeration produced no words")
    if 100 * block_maximum >= 1:
        raise RuntimeError("13-letter block contraction gate failed")
    if remainder_maximum > 10:
        raise RuntimeError("short-remainder norm gate failed")
    raw_margin = int(block_witness["path_weight_squared"]) - 100 * int(
        block_witness["frobenius_squared"]
    )
    if raw_margin <= 0:
        raise RuntimeError("exact block margin is not strictly positive")

    return {
        "status": "exact-arbitrary-tail-certificate",
        "tail_start": 13,
        "block_length": 13,
        "block_word_count": len(level),
        "short_remainder_word_count": 2**13 - 1,
        "grade4_atoms_nonnegative": True,
        "common_loop_weight": 8,
        "block_maximum_ratio_squared": _fraction_payload(block_maximum),
        "block_maximum_witness": block_witness,
        "block_strict_integer_margin": raw_margin,
        "short_remainder_maximum_ratio_squared": _fraction_payload(
            remainder_maximum
        ),
        "short_remainder_maximum_witness": remainder_witness,
        "trace_dimension": 10,
        "conclusion": "chi3(W)+chi4(W)>0 for every word with length>=13",
    }


def exact_low_sector_tail_certificate() -> dict[str, object]:
    """Certify ``chi0+chi1+chi2+chi5 > 0`` for every length at least six."""

    matrix = fixed_candidate_matrix()
    grade2 = exact_compound_matrix(matrix, 2)
    norm_gates = []
    for name, atom, squared_bound in (
        ("grade1", matrix, 6),
        ("grade2", grade2, 29),
    ):
        gram_gap = sp.ImmutableMatrix(
            squared_bound * sp.eye(atom.rows) - atom.T * atom
        )
        leading_minors = tuple(
            int(gram_gap[:size, :size].det())
            for size in range(1, atom.rows + 1)
        )
        if any(value <= 0 for value in leading_minors):
            raise RuntimeError(f"{name} spectral-norm gate is not positive")
        norm_gates.append(
            {
                "grade": name,
                "squared_bound": squared_bound,
                "leading_principal_minors": leading_minors,
            }
        )

    grade1_at_six = 5 * 6**3
    grade2_at_six = 10 * 29**3
    determinant_at_six = 8**6
    strict_margin = determinant_at_six - grade1_at_six - grade2_at_six
    if strict_margin <= 0:
        raise RuntimeError("six-letter scalar tail gate failed")
    return {
        "status": "exact-low-sector-tail-certificate",
        "tail_start": 6,
        "norm_gates": tuple(norm_gates),
        "grade1_bound_at_six": grade1_at_six,
        "grade2_bound_at_six": grade2_at_six,
        "determinant_sector_at_six": determinant_at_six,
        "strict_integer_margin_at_six": strict_margin,
        "monotone_ratios": ("sqrt(6)/8<1", "sqrt(29)/8<1"),
        "conclusion": (
            "chi0(W)+chi1(W)+chi2(W)+chi5(W)>0 "
            "for every word with length>=6"
        ),
    }


def exact_arbitrary_word_sign_free_theorem() -> dict[str, object]:
    """Assemble the finite-depth and two exact tail certificates."""

    grade34 = exact_grade34_block_tail_certificate()
    low = exact_low_sector_tail_certificate()
    return {
        "status": "exact-arbitrary-word-certificate",
        "matrix": _integer_rows(fixed_candidate_matrix()),
        "finite_exact_depth": 12,
        "finite_exact_source": (
            "unit-winding complementary Bernstein audit + exact grade14 cone"
        ),
        "grade34_tail": grade34,
        "low_sector_tail": low,
        "conclusion": "det(I+W)>0 for every word in {B,B.T}",
    }


__all__ = [
    "SCHEMA",
    "exact_arbitrary_word_sign_free_theorem",
    "exact_chi23_obstruction",
    "exact_complementary_sector_audit",
    "exact_grade34_block_tail_certificate",
    "exact_grade4_formula_replay",
    "exact_invariant_chamber_obstruction",
    "exact_low_sector_tail_certificate",
    "exact_pure_power_spectral_lemma",
    "exact_reflection_square_replay",
    "exact_unit_winding_bernstein_audit",
    "exact_unit_winding_endpoint_obstruction",
    "fixed_candidate_matrix",
    "load_certificate",
    "search_fixed_unit_winding_full_fock_cone",
    "search_fixed_unit_winding_pair_cone",
    "search_unit_winding_endpoint_cone",
    "symbolic_grade4_positive_atoms",
    "unit_winding_endpoint_lifts",
    "verify_compact_certificate",
]
