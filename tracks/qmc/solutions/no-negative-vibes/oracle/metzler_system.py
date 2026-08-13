from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
import sympy as sp
from sympy.polys.polyerrors import PolynomialError

from oracle.fock_basis import QuadraticBasisElement, parity_indices


@dataclass(frozen=True)
class MetzlerRow:
    parity: str
    target_state: int
    source_state: int

    def __post_init__(self) -> None:
        if self.parity not in ("even", "odd"):
            raise ValueError("row parity must be 'even' or 'odd'")
        if (
            not isinstance(self.target_state, int)
            or isinstance(self.target_state, bool)
            or not isinstance(self.source_state, int)
            or isinstance(self.source_state, bool)
        ):
            raise TypeError("row state indices must be integers")
        if self.target_state < 0 or self.source_state < 0:
            raise ValueError("row state indices must be nonnegative")
        if self.target_state == self.source_state:
            raise ValueError("a Metzler row must be off-diagonal")


@dataclass(frozen=True)
class ExactMetzlerSystem:
    labels: tuple[str, ...]
    rows: tuple[MetzlerRow, ...]
    coefficients: sp.ImmutableSparseMatrix

    def __post_init__(self) -> None:
        labels = tuple(self.labels)
        rows = tuple(self.rows)
        coefficients = sp.ImmutableSparseMatrix(self.coefficients)
        if any(not isinstance(label, str) or not label for label in labels):
            raise ValueError("system labels must be nonempty strings")
        if len(set(labels)) != len(labels):
            raise ValueError("system labels must be unique")
        if any(not isinstance(row, MetzlerRow) for row in rows):
            raise TypeError("system rows must be MetzlerRow records")
        if coefficients.shape != (len(rows), len(labels)):
            raise ValueError(
                "coefficient matrix shape must match the rows and labels"
            )
        object.__setattr__(self, "labels", labels)
        object.__setattr__(self, "rows", rows)
        object.__setattr__(self, "coefficients", coefficients)


def _is_power_of_two(value: int) -> bool:
    return value > 1 and value & (value - 1) == 0


def _is_exact_real_number(value: sp.Expr) -> bool:
    expression = sp.sympify(value)
    return (
        not expression.has(sp.Float)
        and expression.is_number is True
        and expression.is_real is True
        and expression.is_finite is True
    )


def _validate_exact_matrix(matrix: sp.MatrixBase, *, name: str) -> None:
    if any(not _is_exact_real_number(entry) for entry in matrix):
        raise ValueError(f"{name} must contain exact real finite numbers")


def _is_exact_zero(value: sp.Expr) -> bool:
    simplified = sp.simplify(value)
    if simplified == 0 or simplified.is_zero is True:
        return True
    if simplified.is_zero is False:
        return False
    raise ValueError("could not decide whether an exact matrix entry is zero")


def _validate_parity_blocks(
    parity_blocks: Iterable[Iterable[int]],
    *,
    dimension: int,
    modes: int,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    try:
        blocks = tuple(tuple(block) for block in parity_blocks)
    except TypeError as error:
        raise ValueError("parity blocks must be an iterable") from error
    if len(blocks) != 2:
        raise ValueError("exactly two parity blocks are required")

    flattened = tuple(index for block in blocks for index in block)
    if any(
        not isinstance(index, int) or isinstance(index, bool)
        for index in flattened
    ):
        raise ValueError("each parity-block state index must be an integer")
    if any(index < 0 or index >= dimension for index in flattened):
        raise ValueError("parity-block state index is outside the Fock space")
    if len(flattened) != dimension or len(set(flattened)) != dimension:
        raise ValueError("parity blocks must partition every Fock state once")

    expected_even, expected_odd = parity_indices(modes)
    if set(blocks[0]) != set(expected_even) or set(blocks[1]) != set(
        expected_odd
    ):
        raise ValueError(
            "parity blocks must be the fermionic even and odd sectors"
        )
    return blocks


def _preserves_blocks(
    matrix: sp.MatrixBase,
    blocks: tuple[tuple[int, ...], tuple[int, ...]],
) -> bool:
    even, odd = blocks
    for target_block, source_block in ((even, odd), (odd, even)):
        for target in target_block:
            for source in source_block:
                if not _is_exact_zero(matrix[target, source]):
                    return False
    return True


def _validate_transform(
    transform: sp.MatrixBase,
    parity_blocks: Iterable[Iterable[int]],
) -> tuple[sp.ImmutableSparseMatrix, tuple[tuple[int, ...], tuple[int, ...]]]:
    if not isinstance(transform, sp.MatrixBase):
        raise TypeError("transform must be a SymPy matrix")
    if transform.rows != transform.cols:
        raise ValueError("transform must be square")
    if not _is_power_of_two(transform.rows):
        raise ValueError("transform dimension must be a power of two")

    _validate_exact_matrix(transform, name="transform")
    dimension = transform.rows
    modes = dimension.bit_length() - 1
    blocks = _validate_parity_blocks(
        parity_blocks, dimension=dimension, modes=modes
    )

    orthogonality_residual = transform * transform.T - sp.eye(dimension)
    if any(not _is_exact_zero(entry) for entry in orthogonality_residual):
        raise ValueError("transform must be exactly orthogonal")
    if not _preserves_blocks(transform, blocks):
        raise ValueError("transform must preserve fermion parity")
    return sp.ImmutableSparseMatrix(transform), blocks


def _validate_basis(
    basis: Iterable[QuadraticBasisElement],
    *,
    dimension: int,
    blocks: tuple[tuple[int, ...], tuple[int, ...]],
) -> tuple[QuadraticBasisElement, ...]:
    try:
        elements = tuple(basis)
    except TypeError as error:
        raise ValueError("basis must be an iterable") from error
    if any(not isinstance(element, QuadraticBasisElement) for element in elements):
        raise TypeError("basis entries must be QuadraticBasisElement records")

    labels = tuple(element.label for element in elements)
    if any(not isinstance(label, str) or not label for label in labels):
        raise ValueError("basis labels must be nonempty strings")
    if len(set(labels)) != len(labels):
        raise ValueError("basis labels must be unique")

    for element in elements:
        if not isinstance(element.fock, sp.MatrixBase):
            raise TypeError(
                f"basis element {element.label!r} Fock operator "
                "must be a SymPy matrix"
            )
        if element.fock.shape != (dimension, dimension):
            raise ValueError(
                f"basis element {element.label!r} has the wrong dimension"
            )
        _validate_exact_matrix(
            element.fock, name=f"basis element {element.label!r}"
        )
        if not _preserves_blocks(element.fock, blocks):
            raise ValueError(
                f"basis element {element.label!r} must preserve fermion parity"
            )
    return elements


def compile_metzler_system(
    transform: sp.MatrixBase,
    basis: Iterable[QuadraticBasisElement],
    parity_blocks: Iterable[Iterable[int]],
) -> ExactMetzlerSystem:
    exact_transform, blocks = _validate_transform(transform, parity_blocks)
    elements = _validate_basis(
        basis, dimension=exact_transform.rows, blocks=blocks
    )
    conjugated = tuple(
        exact_transform * element.fock * exact_transform.T
        for element in elements
    )

    rows: list[MetzlerRow] = []
    entries: dict[tuple[int, int], sp.Expr] = {}
    for parity, block in zip(("even", "odd"), blocks, strict=True):
        for target_state in block:
            for source_state in block:
                if target_state == source_state:
                    continue
                row_values = tuple(
                    sp.simplify(matrix[target_state, source_state])
                    for matrix in conjugated
                )
                if all(_is_exact_zero(value) for value in row_values):
                    continue
                row_index = len(rows)
                rows.append(
                    MetzlerRow(parity, target_state, source_state)
                )
                for column_index, value in enumerate(row_values):
                    if not _is_exact_zero(value):
                        entries[(row_index, column_index)] = value

    coefficients = sp.ImmutableSparseMatrix(
        len(rows), len(elements), entries
    )
    return ExactMetzlerSystem(
        labels=tuple(element.label for element in elements),
        rows=tuple(rows),
        coefficients=coefficients,
    )


def numeric_coefficients(system: ExactMetzlerSystem) -> np.ndarray:
    if not isinstance(system, ExactMetzlerSystem):
        raise TypeError("system must be an ExactMetzlerSystem")
    result = np.empty(system.coefficients.shape, dtype=float)
    for row in range(system.coefficients.rows):
        for column in range(system.coefficients.cols):
            result[row, column] = float(system.coefficients[row, column])
    return result


def _number_word(value: int) -> str:
    words = {
        0: "zero",
        1: "one",
        2: "two",
        3: "three",
        4: "four",
        5: "five",
        6: "six",
        7: "seven",
        8: "eight",
        9: "nine",
        10: "ten",
    }
    return words.get(value, str(value))


def _exact_coefficients(
    coefficients: Sequence[sp.Expr] | Iterable[sp.Expr],
    *,
    expected: int,
) -> tuple[sp.Expr, ...]:
    try:
        values = tuple(sp.sympify(value) for value in coefficients)
    except TypeError as error:
        raise ValueError("coefficients must be an iterable") from error
    if len(values) != expected:
        raise ValueError(
            f"expected {_number_word(expected)} coefficients, got {len(values)}"
        )
    if any(not _is_exact_real_number(value) for value in values):
        raise ValueError("coefficients must be exact real finite numbers")
    return values


def exact_linear_combination(
    system: ExactMetzlerSystem,
    coefficients: Sequence[sp.Expr] | Iterable[sp.Expr],
) -> sp.ImmutableMatrix:
    if not isinstance(system, ExactMetzlerSystem):
        raise TypeError("system must be an ExactMetzlerSystem")
    values = _exact_coefficients(coefficients, expected=len(system.labels))
    vector = sp.ImmutableMatrix(len(values), 1, values)
    slacks = system.coefficients * vector
    return sp.ImmutableMatrix(slacks)


def _q_sqrt_two_coefficients(expression: sp.Expr) -> tuple[sp.Rational, sp.Rational]:
    value = sp.sympify(expression)
    if not _is_exact_real_number(value):
        raise ValueError("expression must be an exact real number in Q(sqrt(2))")

    normalized = sp.expand(sp.radsimp(value))
    generator = sp.sqrt(2)
    indeterminate = sp.Dummy("sqrt_two")
    lifted = normalized.xreplace({generator: indeterminate})
    try:
        polynomial = sp.Poly(lifted, indeterminate, domain="EX")
    except PolynomialError as error:
        raise ValueError("expression must lie in Q(sqrt(2))") from error
    if polynomial.degree() > 1:
        raise ValueError("expression must lie in Q(sqrt(2))")

    a = sp.simplify(polynomial.nth(0))
    b = sp.simplify(polynomial.nth(1))
    residual = sp.simplify(value - a - b * generator)
    if (
        not _is_exact_zero(residual)
        or a.is_Rational is not True
        or b.is_Rational is not True
    ):
        raise ValueError("expression must lie in Q(sqrt(2))")
    return sp.Rational(a), sp.Rational(b)


def exact_nonnegative(expression: sp.Expr) -> bool:
    a, b = _q_sqrt_two_coefficients(expression)
    if a >= 0 and b >= 0:
        return True
    if a < 0 and b < 0:
        return False
    if a >= 0:
        return bool(a * a >= 2 * b * b)
    return bool(2 * b * b >= a * a)


def verify_exact_metzler(
    system: ExactMetzlerSystem,
    coefficients: Sequence[sp.Expr] | Iterable[sp.Expr],
) -> bool:
    slacks = exact_linear_combination(system, coefficients)
    return all(exact_nonnegative(value) for value in slacks)
