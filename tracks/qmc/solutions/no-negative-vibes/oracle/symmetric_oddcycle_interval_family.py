"""Exact interval certificate for a continuous symmetric-oddcycle alphabet.

Every letter may independently choose

    B(z) or B(z).T,  99/100 <= z <= 101/100.

All interval propagation uses integer endpoints with one shared denominator
per time layer.  Floating-point arithmetic is not part of the certificate.
"""

from __future__ import annotations

from fractions import Fraction

import sympy as sp

from .exterior_exact5_shared_cone import exact_compound_matrix


SCHEMA = "symmetric-oddcycle-independent-interval-family-v1"
INTERVAL_DENOMINATOR = 100
INTERVAL_LOWER_NUMERATOR = 99
INTERVAL_UPPER_NUMERATOR = 101

_Interval = tuple[int, int]
_IntervalMatrix = tuple[tuple[_Interval, ...], ...]
_SparseIntervalRows = tuple[
    tuple[tuple[int, _Interval], ...],
    ...,
]


def symbolic_family_matrix() -> sp.ImmutableMatrix:
    """Return the one-parameter atom ``B(z)``."""

    z = sp.symbols("z", real=True)
    return sp.ImmutableMatrix(
        [
            [0, 0, 2, 0, 0],
            [2, 0, 0, 0, 0],
            [0, 2, 0, 1, 0],
            [0, 0, 0, 1, 1],
            [0, 0, -z, 0, 1],
        ]
    )


def _rational_payload(value: Fraction) -> dict[str, int]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
    }


def _interval_multiply(left: _Interval, right: _Interval) -> _Interval:
    products = (
        left[0] * right[0],
        left[0] * right[1],
        left[1] * right[0],
        left[1] * right[1],
    )
    return min(products), max(products)


def _affine_interval_numerators(
    expression: sp.Expr,
    variable: sp.Symbol,
) -> _Interval:
    polynomial = sp.Poly(expression, variable)
    if polynomial.degree() > 1:
        raise ValueError("compound atom entry is not affine in z")
    constant = int(polynomial.nth(0))
    linear = int(polynomial.nth(1))
    endpoints = (
        constant * INTERVAL_DENOMINATOR
        + linear * INTERVAL_LOWER_NUMERATOR,
        constant * INTERVAL_DENOMINATOR
        + linear * INTERVAL_UPPER_NUMERATOR,
    )
    return min(endpoints), max(endpoints)


def _sparse_interval_rows(
    matrix: sp.MatrixBase,
    variable: sp.Symbol,
) -> _SparseIntervalRows:
    return tuple(
        tuple(
            (column, _affine_interval_numerators(matrix[row, column], variable))
            for column in range(matrix.cols)
            if matrix[row, column] != 0
        )
        for row in range(matrix.rows)
    )


def _interval_identity(dimension: int) -> _IntervalMatrix:
    return tuple(
        tuple(
            (int(row == column), int(row == column))
            for column in range(dimension)
        )
        for row in range(dimension)
    )


def _left_multiply_interval(
    left: _SparseIntervalRows,
    right: _IntervalMatrix,
) -> _IntervalMatrix:
    dimension = len(right)
    result = []
    for sparse_row in left:
        output_row = []
        for column in range(dimension):
            lower = 0
            upper = 0
            for index, coefficient in sparse_row:
                product = _interval_multiply(
                    coefficient,
                    right[index][column],
                )
                lower += product[0]
                upper += product[1]
            output_row.append((lower, upper))
        result.append(tuple(output_row))
    return tuple(result)


def _family_compound_atoms() -> dict[
    int,
    tuple[_SparseIntervalRows, _SparseIntervalRows],
]:
    matrix = symbolic_family_matrix()
    variable = next(iter(matrix.free_symbols))
    return {
        grade: tuple(
            _sparse_interval_rows(
                exact_compound_matrix(atom, grade),
                variable,
            )
            for atom in (matrix, matrix.T)
        )
        for grade in (1, 2, 3, 4)
    }


def exact_independent_letter_finite_audit() -> dict[str, object]:
    """Certify every independently varying word through length twelve."""

    atoms = _family_compound_atoms()
    level = [
        (
            _interval_identity(5),
            _interval_identity(10),
            _interval_identity(10),
            _interval_identity(5),
            "",
        )
    ]
    global_full: tuple[int, int, str] | None = None
    global_complementary: tuple[int, int, str] | None = None
    per_depth = []
    word_count = 0
    for depth in range(1, 13):
        level = [
            (
                _left_multiply_interval(atoms[1][symbol], grade1),
                _left_multiply_interval(atoms[2][symbol], grade2),
                _left_multiply_interval(atoms[3][symbol], grade3),
                _left_multiply_interval(atoms[4][symbol], grade4),
                word + str(symbol),
            )
            for grade1, grade2, grade3, grade4, word in level
            for symbol in (0, 1)
        ]
        scale = INTERVAL_DENOMINATOR**depth
        depth_full: tuple[int, int, str] | None = None
        depth_complementary: tuple[int, int, str] | None = None
        for grade1, grade2, grade3, grade4, word in level:
            complementary_lower = (
                (1 + 8**depth) * scale
                + sum(grade2[index][index][0] for index in range(10))
                + sum(grade3[index][index][0] for index in range(10))
            )
            full_lower = (
                complementary_lower
                + sum(grade1[index][index][0] for index in range(5))
                + sum(grade4[index][index][0] for index in range(5))
            )
            full_record = (full_lower, scale, word)
            complementary_record = (complementary_lower, scale, word)
            if depth_full is None or (
                full_lower * depth_full[1] < depth_full[0] * scale
            ):
                depth_full = full_record
            if depth_complementary is None or (
                complementary_lower * depth_complementary[1]
                < depth_complementary[0] * scale
            ):
                depth_complementary = complementary_record
        assert depth_full is not None and depth_complementary is not None
        if depth_full[0] <= 0 or depth_complementary[0] <= 0:
            raise RuntimeError("independent-letter finite interval gate failed")
        if global_full is None or (
            depth_full[0] * global_full[1]
            < global_full[0] * depth_full[1]
        ):
            global_full = depth_full
        if global_complementary is None or (
            depth_complementary[0] * global_complementary[1]
            < global_complementary[0] * depth_complementary[1]
        ):
            global_complementary = depth_complementary
        word_count += len(level)
        per_depth.append(
            {
                "depth": depth,
                "word_count": len(level),
                "full_lower_bound": _rational_payload(
                    Fraction(depth_full[0], depth_full[1])
                ),
                "full_witness": depth_full[2],
            }
        )
    assert global_full is not None and global_complementary is not None
    return {
        "status": "exact-independent-letter-finite-certificate",
        "max_depth": 12,
        "word_count": word_count,
        "parameter_choices": "independent-per-letter",
        "global_full_lower_bound": _rational_payload(
            Fraction(global_full[0], global_full[1])
        ),
        "global_full_witness": global_full[2],
        "global_complementary_lower_bound": _rational_payload(
            Fraction(global_complementary[0], global_complementary[1])
        ),
        "global_complementary_witness": global_complementary[2],
        "per_depth": tuple(per_depth),
    }


def exact_independent_letter_block_tail() -> dict[str, object]:
    """Certify the uniform grade-(3,4) block bound for the continuum alphabet."""

    atoms = _family_compound_atoms()
    grade3_atoms = atoms[3]

    matrix = symbolic_family_matrix()
    variable = next(iter(matrix.free_symbols))
    diagonal = sp.diag(1, 1, 1, -1, 1)
    grade4_atoms = tuple(
        _sparse_interval_rows(
            diagonal * exact_compound_matrix(atom, 4) * diagonal,
            variable,
        )
        for atom in (matrix, matrix.T)
    )
    if any(
        coefficient[0] < 0
        for atom in grade4_atoms
        for row in atom
        for _, coefficient in row
    ):
        raise RuntimeError("uniform grade-four gauge is not nonnegative")
    if any(
        dict(atom[0]).get(0)
        != (8 * INTERVAL_DENOMINATOR, 8 * INTERVAL_DENOMINATOR)
        for atom in grade4_atoms
    ):
        raise RuntimeError("uniform grade-four loop is not exactly eight")

    level = [(_interval_identity(10), _interval_identity(5), "")]
    minimum_nonempty_remainder: tuple[int, int, int, str] | None = None
    minimum_block: tuple[int, int, int, int, str] | None = None
    for depth in range(1, 14):
        level = [
            (
                _left_multiply_interval(grade3_atoms[symbol], grade3),
                _left_multiply_interval(grade4_atoms[symbol], grade4),
                word + str(symbol),
            )
            for grade3, grade4, word in level
            for symbol in (0, 1)
        ]
        denominator = INTERVAL_DENOMINATOR ** (2 * depth)
        for grade3, grade4, word in level:
            frobenius_upper_numerator = sum(
                max(abs(entry[0]), abs(entry[1])) ** 2
                for row in grade3
                for entry in row
            )
            path_lower_squared_numerator = grade4[0][0][0] ** 2
            if depth <= 12:
                margin = (
                    10 * path_lower_squared_numerator
                    - frobenius_upper_numerator
                )
                if margin < 0:
                    raise RuntimeError("uniform short-remainder gate failed")
                record = (margin, denominator, depth, word)
                if minimum_nonempty_remainder is None or (
                    margin * minimum_nonempty_remainder[1]
                    < minimum_nonempty_remainder[0] * denominator
                ):
                    minimum_nonempty_remainder = record
            else:
                margin = (
                    path_lower_squared_numerator
                    - 100 * frobenius_upper_numerator
                )
                if margin <= 0:
                    raise RuntimeError("uniform 13-letter block gate failed")
                record = (
                    margin,
                    frobenius_upper_numerator,
                    path_lower_squared_numerator,
                    denominator,
                    word,
                )
                if minimum_block is None or margin < minimum_block[0]:
                    minimum_block = record
    assert minimum_nonempty_remainder is not None and minimum_block is not None
    return {
        "status": "exact-independent-letter-block-tail-certificate",
        "parameter_choices": "independent-per-letter",
        "grade4_atoms_interval_nonnegative": True,
        "common_loop_weight": 8,
        "block_length": 13,
        "block_word_count": 8192,
        "block_minimum_raw_margin": minimum_block[0],
        "block_scale_denominator": minimum_block[3],
        "block_witness": minimum_block[4],
        "block_frobenius_upper_numerator": minimum_block[1],
        "block_path_lower_squared_numerator": minimum_block[2],
        "short_remainder_word_count": 8191,
        "short_remainder_minimum_margin": {
            "empty_remainder": _rational_payload(Fraction(0)),
            "minimum_nonempty": _rational_payload(
                Fraction(
                    minimum_nonempty_remainder[0],
                    minimum_nonempty_remainder[1],
                )
            ),
            "minimum_nonempty_depth": minimum_nonempty_remainder[2],
            "minimum_nonempty_witness": minimum_nonempty_remainder[3],
        },
        "conclusion": (
            "chi3(W)+chi4(W)>0 for every independently varying "
            "word with length>=13"
        ),
    }


def _polynomial_interval(
    polynomial: sp.Poly,
    variable: sp.Symbol,
) -> tuple[Fraction, Fraction]:
    coefficients = [
        Fraction(int(polynomial.nth(power)))
        for power in range(polynomial.degree() + 1)
    ]
    lower = Fraction(INTERVAL_LOWER_NUMERATOR, INTERVAL_DENOMINATOR)
    upper = Fraction(INTERVAL_UPPER_NUMERATOR, INTERVAL_DENOMINATOR)
    result = (coefficients[-1], coefficients[-1])
    for coefficient in reversed(coefficients[:-1]):
        products = (
            result[0] * lower,
            result[0] * upper,
            result[1] * lower,
            result[1] * upper,
        )
        result = (
            min(products) + coefficient,
            max(products) + coefficient,
        )
    return result


def exact_uniform_low_sector_gate() -> dict[str, object]:
    """Certify uniform grade-one/two norm bounds for every interval letter."""

    matrix = symbolic_family_matrix()
    variable = next(iter(matrix.free_symbols))
    gates = []
    for name, atom, squared_bound in (
        ("grade1", matrix, 6),
        ("grade2", exact_compound_matrix(matrix, 2), 29),
    ):
        gram_gap = squared_bound * sp.eye(atom.rows) - atom.T * atom
        lower_bounds = []
        for size in range(1, atom.rows + 1):
            interval = _polynomial_interval(
                sp.Poly(sp.expand(gram_gap[:size, :size].det()), variable),
                variable,
            )
            if interval[0] <= 0:
                raise RuntimeError(f"uniform {name} norm gate failed")
            lower_bounds.append(_rational_payload(interval[0]))
        gates.append(
            {
                "grade": name,
                "squared_norm_bound": squared_bound,
                "leading_minor_lower_bounds": tuple(lower_bounds),
            }
        )
    margin_at_six = 8**6 - 5 * 6**3 - 10 * 29**3
    if margin_at_six <= 0:
        raise RuntimeError("uniform scalar-sector tail margin failed")
    return {
        "status": "exact-uniform-low-sector-certificate",
        "parameter_choices": "independent-per-letter",
        "norm_gates": tuple(gates),
        "tail_start": 6,
        "strict_integer_margin_at_six": margin_at_six,
        "conclusion": (
            "chi0(W)+chi1(W)+chi2(W)+chi5(W)>0 "
            "for every independently varying word with length>=6"
        ),
    }


def exact_interval_family_theorem() -> dict[str, object]:
    """Assemble the exact continuum-alphabet sign-free theorem."""

    finite = exact_independent_letter_finite_audit()
    block = exact_independent_letter_block_tail()
    low = exact_uniform_low_sector_gate()
    upper = Fraction(
        INTERVAL_UPPER_NUMERATOR,
        INTERVAL_DENOMINATOR,
    )
    if upper >= 8:
        raise RuntimeError("negative-real-axis logarithm gate failed")
    return {
        "schema": SCHEMA,
        "status": "exact-continuum-alphabet-certificate",
        "parameter_interval": {
            "lower": _rational_payload(
                Fraction(
                    INTERVAL_LOWER_NUMERATOR,
                    INTERVAL_DENOMINATOR,
                )
            ),
            "upper": _rational_payload(upper),
            "closed": True,
        },
        "alphabet": "{B(z), B(z).T : z in interval}",
        "parameter_choices": "independent-per-letter",
        "finite_depth": finite,
        "grade34_tail": block,
        "low_sector_tail": low,
        "real_logarithm_gate": {
            "determinant": 8,
            "negative_axis_polynomial": (
                "-x^5-2*x^4-x^3+(z-8)*x^2-16*x-8"
            ),
            "all_coefficients_strictly_negative_for_x_positive": True,
            "conclusion": "B(z) has no negative real eigenvalue",
        },
        "conclusion": (
            "det(I+W)>0 for every finite word over the continuum alphabet"
        ),
    }


__all__ = [
    "INTERVAL_DENOMINATOR",
    "INTERVAL_LOWER_NUMERATOR",
    "INTERVAL_UPPER_NUMERATOR",
    "SCHEMA",
    "exact_independent_letter_block_tail",
    "exact_independent_letter_finite_audit",
    "exact_interval_family_theorem",
    "exact_uniform_low_sector_gate",
    "symbolic_family_matrix",
]
