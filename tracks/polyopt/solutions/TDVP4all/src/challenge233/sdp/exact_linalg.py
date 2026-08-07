"""Deterministic exact sparse linear-algebra reductions."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math
from typing import Iterable, Mapping

from challenge233.sdp.algebra import (
    GaussianRational,
    ONE,
    ZERO,
)


DEFAULT_MODULAR_PRIMES = (
    2305843009213693951,
    2305843009213693921,
)


@dataclass(frozen=True)
class ExactColumnBasis:
    selected: tuple[int, ...]
    reconstruction: tuple[
        tuple[tuple[int, GaussianRational], ...],
        ...,
    ]
    kernel: tuple[
        tuple[tuple[int, GaussianRational], ...],
        ...,
    ]
    pivots: tuple[int, ...]


@dataclass(frozen=True)
class ExactRowBasis:
    selected: tuple[int, ...]
    pivot_columns: tuple[int, ...]
    reconstruction: tuple[tuple[tuple[int, Fraction], ...], ...]
    primitive_rows: tuple[tuple[int, ...], ...]
    modular_primes: tuple[int, ...]
    used_fallback: bool
    max_bit_length: int


def _fraction(value) -> Fraction:
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError("exact rational entries must not be bool or float")
    if isinstance(value, Fraction):
        return value
    return Fraction(value)


def primitive_integer_row(values) -> tuple[tuple[int, ...], Fraction]:
    """Return a sign-canonical primitive integer row and its signed scale."""
    values = tuple(_fraction(value) for value in values)
    denominator = math.lcm(
        *(value.denominator for value in values),
        1,
    )
    integers = tuple(
        value.numerator * (denominator // value.denominator)
        for value in values
    )
    divisor = math.gcd(*(abs(value) for value in integers), 0)
    if divisor == 0:
        return integers, Fraction(1)
    primitive = tuple(value // divisor for value in integers)
    scale = Fraction(divisor, denominator)
    first = next(value for value in primitive if value)
    if first < 0:
        primitive = tuple(-value for value in primitive)
        scale = -scale
    return primitive, scale


def _gaussian_divide(
    numerator: GaussianRational,
    denominator: GaussianRational,
) -> GaussianRational:
    norm = denominator.real**2 + denominator.imag**2
    if norm == 0:
        raise ZeroDivisionError("Gaussian rational division by zero")
    product = numerator * denominator.conjugate()
    return GaussianRational(product.real / norm, product.imag / norm)


def _gaussian_axpy(target, source, coefficient) -> None:
    for coordinate, value in source.items():
        updated = target.get(coordinate, ZERO) + coefficient * value
        if updated.is_zero:
            target.pop(coordinate, None)
        else:
            target[coordinate] = updated


def _gaussian_scale(source, coefficient):
    return {
        coordinate: coefficient * value
        for coordinate, value in source.items()
        if not (coefficient * value).is_zero
    }


def _normalize_gaussian_columns(columns):
    normalized = []
    for column in columns:
        if not isinstance(column, Mapping):
            raise TypeError("sparse Gaussian columns must be mappings")
        values = {}
        for raw_coordinate, value in column.items():
            if isinstance(raw_coordinate, bool) or not isinstance(
                raw_coordinate, int
            ):
                raise TypeError("sparse coordinates must be integers")
            if raw_coordinate < 0:
                raise ValueError("sparse coordinates must be nonnegative")
            if not isinstance(value, GaussianRational):
                raise TypeError(
                    "sparse values must be GaussianRational values"
                )
            if not value.is_zero:
                values[raw_coordinate] = value
        normalized.append(dict(sorted(values.items())))
    return tuple(normalized)


def _gaussian_combination(columns, terms):
    result = {}
    for index, coefficient in terms:
        _gaussian_axpy(result, columns[index], coefficient)
    return dict(sorted(result.items()))


def gaussian_column_basis(columns) -> ExactColumnBasis:
    """Select a stable exact basis and reconstruct every Gaussian column."""
    columns = _normalize_gaussian_columns(tuple(columns))
    pivot_rows = {}
    pivot_order = []
    selected = []
    reconstructions = []
    for original_index, source in enumerate(columns):
        residual = dict(source)
        coefficients = {}
        for pivot in sorted(pivot_rows):
            if pivot not in residual:
                continue
            vector, representation = pivot_rows[pivot]
            factor = _gaussian_divide(residual[pivot], vector[pivot])
            _gaussian_axpy(residual, vector, -factor)
            _gaussian_axpy(coefficients, representation, factor)
        if residual:
            pivot = min(residual)
            inverse = _gaussian_divide(ONE, residual[pivot])
            normalized = _gaussian_scale(residual, inverse)
            selected_position = len(selected)
            representation = {selected_position: inverse}
            _gaussian_axpy(representation, coefficients, -inverse)
            pivot_rows[pivot] = (normalized, representation)
            pivot_order.append(pivot)
            selected.append(original_index)
            reconstructions.append(((selected_position, ONE),))
        else:
            reconstructions.append(tuple(sorted(coefficients.items())))

    selected = tuple(selected)
    reconstruction = tuple(reconstructions)
    selected_set = set(selected)
    kernel = []
    for original_index, terms in enumerate(reconstruction):
        if original_index in selected_set:
            continue
        relation = {original_index: ONE}
        for selected_position, coefficient in terms:
            selected_index = selected[selected_position]
            _gaussian_axpy(
                relation,
                {selected_index: ONE},
                -coefficient,
            )
        kernel.append(tuple(sorted(relation.items())))
    result = ExactColumnBasis(
        selected=selected,
        reconstruction=reconstruction,
        kernel=tuple(kernel),
        pivots=tuple(pivot_order),
    )
    verify_column_reconstruction(columns, result)
    return result


def verify_column_reconstruction(columns, basis: ExactColumnBasis) -> None:
    """Raise unless every reconstruction and kernel relation is exact."""
    columns = _normalize_gaussian_columns(tuple(columns))
    if not isinstance(basis, ExactColumnBasis):
        raise TypeError("basis must be an ExactColumnBasis")
    if len(basis.reconstruction) != len(columns):
        raise ValueError("column reconstruction length is inconsistent")
    if len(set(basis.selected)) != len(basis.selected):
        raise ValueError("selected column indices must be unique")
    if any(not 0 <= index < len(columns) for index in basis.selected):
        raise ValueError("selected column index is out of range")
    selected_columns = tuple(columns[index] for index in basis.selected)
    for original_index, terms in enumerate(basis.reconstruction):
        if any(
            not 0 <= selected_position < len(selected_columns)
            for selected_position, _ in terms
        ):
            raise ValueError("column reconstruction index is out of range")
        reconstructed = _gaussian_combination(selected_columns, terms)
        if reconstructed != columns[original_index]:
            raise ValueError(
                f"column reconstruction failed at index {original_index}"
            )
    for relation in basis.kernel:
        if any(not 0 <= index < len(columns) for index, _ in relation):
            raise ValueError("column kernel index is out of range")
        if _gaussian_combination(columns, relation):
            raise ValueError("column kernel relation is not exact")
    if len(basis.pivots) != len(basis.selected):
        raise ValueError("column pivot count is inconsistent")
    if len(set(basis.pivots)) != len(basis.pivots):
        raise ValueError("column pivots must be unique")


def _normalize_rational_rows(rows):
    normalized = tuple(
        tuple(_fraction(value) for value in row)
        for row in rows
    )
    if not normalized:
        return normalized
    width = len(normalized[0])
    if width == 0:
        raise ValueError("rational rows must not be empty")
    if any(len(row) != width for row in normalized):
        raise ValueError("rational rows must have one common width")
    for row in normalized:
        if row[0] != 0 and all(value == 0 for value in row[1:]):
            raise ValueError("inconsistent-equality-system")
    return normalized


def _rational_axpy(target, source, coefficient) -> None:
    for coordinate, value in source.items():
        updated = target.get(coordinate, Fraction(0)) + coefficient * value
        if updated == 0:
            target.pop(coordinate, None)
        else:
            target[coordinate] = updated


def _row_dict(row):
    return {
        coordinate: value
        for coordinate, value in enumerate(row)
        if value
    }


def _select_exact_rows(rows, order):
    pivot_rows = {}
    selected = []
    for original_index in order:
        residual = _row_dict(rows[original_index])
        for pivot in sorted(pivot_rows):
            if pivot in residual:
                _rational_axpy(
                    residual,
                    pivot_rows[pivot],
                    -residual[pivot],
                )
        if not residual:
            continue
        pivot = min(residual)
        inverse = Fraction(1, 1) / residual[pivot]
        pivot_rows[pivot] = {
            coordinate: inverse * value
            for coordinate, value in residual.items()
        }
        selected.append(original_index)
    return tuple(selected)


def _fraction_mod_prime(value: Fraction, prime: int) -> int:
    denominator = value.denominator % prime
    if denominator == 0:
        raise ZeroDivisionError("row denominator vanishes modulo prime")
    return (
        (value.numerator % prime)
        * pow(denominator, -1, prime)
    ) % prime


def _select_modular_rows(rows, order, prime):
    if isinstance(prime, bool) or not isinstance(prime, int) or prime < 2:
        raise ValueError("modular hints must be integers at least two")
    pivot_rows = {}
    selected = []
    for original_index in order:
        residual = {
            coordinate: modular
            for coordinate, value in enumerate(rows[original_index])
            if (modular := _fraction_mod_prime(value, prime))
        }
        for pivot in sorted(pivot_rows):
            if pivot not in residual:
                continue
            factor = residual[pivot]
            for coordinate, value in pivot_rows[pivot].items():
                updated = (
                    residual.get(coordinate, 0) - factor * value
                ) % prime
                if updated:
                    residual[coordinate] = updated
                else:
                    residual.pop(coordinate, None)
        if not residual:
            continue
        pivot = min(residual)
        inverse = pow(residual[pivot], -1, prime)
        pivot_rows[pivot] = {
            coordinate: (inverse * value) % prime
            for coordinate, value in residual.items()
        }
        selected.append(original_index)
    return tuple(selected)


def _build_rational_echelon(rows, selected):
    pivot_rows = {}
    pivot_order = []
    for selected_position, original_index in enumerate(selected):
        residual = _row_dict(rows[original_index])
        coefficients = {}
        for pivot in sorted(pivot_rows):
            if pivot not in residual:
                continue
            vector, representation = pivot_rows[pivot]
            factor = residual[pivot]
            _rational_axpy(residual, vector, -factor)
            _rational_axpy(coefficients, representation, factor)
        if not residual:
            raise ArithmeticError("selected rational rows are dependent")
        pivot = min(residual)
        inverse = Fraction(1, 1) / residual[pivot]
        normalized = {
            coordinate: inverse * value
            for coordinate, value in residual.items()
        }
        representation = {selected_position: inverse}
        _rational_axpy(representation, coefficients, -inverse)
        pivot_rows[pivot] = (normalized, representation)
        pivot_order.append(pivot)
    return pivot_rows, tuple(pivot_order)


def _reconstruct_rational_rows(rows, pivot_rows):
    reconstruction = []
    for row in rows:
        residual = _row_dict(row)
        coefficients = {}
        for pivot in sorted(pivot_rows):
            if pivot not in residual:
                continue
            vector, representation = pivot_rows[pivot]
            factor = residual[pivot]
            _rational_axpy(residual, vector, -factor)
            _rational_axpy(coefficients, representation, factor)
        if residual:
            raise ArithmeticError("rational row lies outside selected span")
        reconstruction.append(tuple(sorted(coefficients.items())))
    return tuple(reconstruction)


def _bit_length(value: Fraction) -> int:
    return max(
        abs(value.numerator).bit_length(),
        value.denominator.bit_length(),
    )


def rational_row_basis(
    rows,
    modular_primes: Iterable[int] = DEFAULT_MODULAR_PRIMES,
) -> ExactRowBasis:
    """Select and exactly reconstruct a rational row-space basis."""
    rows = _normalize_rational_rows(tuple(rows))
    modular_primes = tuple(modular_primes)
    if any(
        isinstance(prime, bool)
        or not isinstance(prime, int)
        or prime < 2
        for prime in modular_primes
    ):
        raise ValueError("modular hints must be integers at least two")
    primitive_rows = tuple(
        primitive_integer_row(row)[0]
        for row in rows
    )
    unique_indices = []
    seen = set()
    for original_index, primitive in enumerate(primitive_rows):
        if not any(primitive) or primitive in seen:
            continue
        seen.add(primitive)
        unique_indices.append(original_index)
    unique_indices = tuple(unique_indices)
    selected = None
    pivot_rows = None
    pivot_columns = None
    reconstruction = None
    used_fallback = False
    if modular_primes and unique_indices:
        for prime in modular_primes:
            try:
                candidate = _select_modular_rows(
                    rows,
                    unique_indices,
                    prime,
                )
            except (ValueError, ZeroDivisionError):
                continue
            try:
                candidate_pivots, candidate_columns = (
                    _build_rational_echelon(rows, candidate)
                )
                candidate_reconstruction = (
                    _reconstruct_rational_rows(
                        rows,
                        candidate_pivots,
                    )
                )
            except ArithmeticError:
                continue
            selected = candidate
            pivot_rows = candidate_pivots
            pivot_columns = candidate_columns
            reconstruction = candidate_reconstruction
            break
        if selected is None:
            used_fallback = True
    if selected is None:
        selected = _select_exact_rows(rows, unique_indices)
        pivot_rows, pivot_columns = _build_rational_echelon(
            rows,
            selected,
        )
        reconstruction = _reconstruct_rational_rows(
            rows,
            pivot_rows,
        )
    all_fractions = [
        value
        for row in rows
        for value in row
    ] + [
        coefficient
        for terms in reconstruction
        for _, coefficient in terms
    ]
    integer_bits = [
        abs(value).bit_length()
        for row in primitive_rows
        for value in row
    ]
    result = ExactRowBasis(
        selected=selected,
        pivot_columns=pivot_columns,
        reconstruction=reconstruction,
        primitive_rows=primitive_rows,
        modular_primes=modular_primes,
        used_fallback=used_fallback,
        max_bit_length=max(
            [_bit_length(value) for value in all_fractions]
            + integer_bits
            + [0]
        ),
    )
    verify_row_reconstruction(rows, result)
    return result


def verify_row_reconstruction(rows, basis: ExactRowBasis) -> None:
    """Raise unless every rational row reconstruction is exact."""
    rows = _normalize_rational_rows(tuple(rows))
    if not isinstance(basis, ExactRowBasis):
        raise TypeError("basis must be an ExactRowBasis")
    if len(basis.reconstruction) != len(rows):
        raise ValueError("row reconstruction length is inconsistent")
    if len(basis.primitive_rows) != len(rows):
        raise ValueError("primitive row count is inconsistent")
    expected_primitive = tuple(
        primitive_integer_row(row)[0]
        for row in rows
    )
    if basis.primitive_rows != expected_primitive:
        raise ValueError("primitive row data is inconsistent")
    if len(set(basis.selected)) != len(basis.selected):
        raise ValueError("selected row indices must be unique")
    if any(not 0 <= index < len(rows) for index in basis.selected):
        raise ValueError("selected row index is out of range")
    selected_rows = tuple(
        _row_dict(rows[index]) for index in basis.selected
    )
    for original_index, terms in enumerate(basis.reconstruction):
        if any(
            not 0 <= selected_position < len(selected_rows)
            for selected_position, _ in terms
        ):
            raise ValueError("row reconstruction index is out of range")
        reconstructed = {}
        for selected_position, coefficient in terms:
            _rational_axpy(
                reconstructed,
                selected_rows[selected_position],
                coefficient,
            )
        if reconstructed != _row_dict(rows[original_index]):
            raise ValueError(
                f"row reconstruction failed at index {original_index}"
            )
    if len(set(basis.pivot_columns)) != len(basis.pivot_columns):
        raise ValueError("row pivots must be unique")
    if len(basis.pivot_columns) != len(basis.selected):
        raise ValueError("row pivot count is inconsistent")
