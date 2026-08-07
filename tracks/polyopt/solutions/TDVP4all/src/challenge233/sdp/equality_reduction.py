"""Exact compression and parameterization of affine equality rows."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json

from challenge233.sdp.exact_linalg import (
    DEFAULT_MODULAR_PRIMES,
    rational_row_basis,
)
from challenge233.sdp.kyfan import (
    LinearEquality,
    RationalLinearForm,
)


@dataclass(frozen=True)
class AffineParameterization:
    offset: tuple[tuple[int, Fraction], ...]
    nullspace: tuple[
        tuple[tuple[int, Fraction], ...],
        ...,
    ]
    free_variables: tuple[int, ...]
    affine_nonzeros: int

    def __post_init__(self) -> None:
        offset = tuple(
            (int(index), Fraction(value))
            for index, value in self.offset
            if Fraction(value)
        )
        nullspace = tuple(
            tuple(
                (int(index), Fraction(value))
                for index, value in column
                if Fraction(value)
            )
            for column in self.nullspace
        )
        free_variables = tuple(
            int(index) for index in self.free_variables
        )
        if offset != tuple(sorted(offset)):
            raise ValueError(
                "parameterization offset must be sorted"
            )
        if any(column != tuple(sorted(column)) for column in nullspace):
            raise ValueError(
                "parameterization nullspace columns must be sorted"
            )
        if free_variables != tuple(sorted(set(free_variables))):
            raise ValueError(
                "parameterization free variables must be unique and sorted"
            )
        if len(nullspace) != len(free_variables):
            raise ValueError(
                "parameterization nullspace/free count mismatch"
            )
        affine_nonzeros = int(self.affine_nonzeros)
        if affine_nonzeros != (
            len(offset) + sum(len(column) for column in nullspace)
        ):
            raise ValueError(
                "parameterization affine nonzero count mismatch"
            )
        object.__setattr__(self, "offset", offset)
        object.__setattr__(self, "nullspace", nullspace)
        object.__setattr__(self, "free_variables", free_variables)
        object.__setattr__(
            self,
            "affine_nonzeros",
            affine_nonzeros,
        )


@dataclass(frozen=True)
class EqualityReduction:
    kept_identifiers: tuple[str, ...]
    duplicate_map: dict
    span_map: dict
    pivot_columns: tuple[int, ...]
    row_rank: int
    parameterization: AffineParameterization
    selected_view: str
    statistics: dict

    def __post_init__(self) -> None:
        kept = tuple(str(value) for value in self.kept_identifiers)
        pivots = tuple(int(value) for value in self.pivot_columns)
        row_rank = int(self.row_rank)
        if len(set(kept)) != len(kept):
            raise ValueError(
                "kept equality identifiers must be unique"
            )
        if pivots != tuple(sorted(set(pivots))):
            raise ValueError(
                "equality pivot columns must be unique and sorted"
            )
        if row_rank != len(kept) or row_rank != len(pivots):
            raise ValueError(
                "equality row rank does not match kept rows or pivots"
            )
        if not isinstance(
            self.parameterization,
            AffineParameterization,
        ):
            raise TypeError(
                "parameterization must be AffineParameterization"
            )
        if self.selected_view not in {
            "row-reduced",
            "parameterized",
        }:
            raise ValueError(
                "selected view must be row-reduced or parameterized"
            )
        object.__setattr__(self, "kept_identifiers", kept)
        object.__setattr__(self, "duplicate_map", dict(self.duplicate_map))
        object.__setattr__(self, "span_map", dict(self.span_map))
        object.__setattr__(self, "pivot_columns", pivots)
        object.__setattr__(self, "row_rank", row_rank)
        object.__setattr__(self, "statistics", dict(self.statistics))


def _exact_fill_cap(value) -> Fraction:
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError("fill cap must be an exact positive rational")
    try:
        value = Fraction(value)
    except (TypeError, ValueError, ZeroDivisionError) as error:
        raise TypeError(
            "fill cap must be an exact positive rational"
        ) from error
    if value <= 0:
        raise ValueError("fill cap must be positive")
    return value


def _validate_rows(equalities, number_of_variables):
    if (
        isinstance(number_of_variables, bool)
        or not isinstance(number_of_variables, int)
        or number_of_variables < 0
    ):
        raise ValueError(
            "number_of_variables must be a nonnegative integer"
        )
    equalities = tuple(equalities)
    if any(
        not isinstance(row, LinearEquality)
        for row in equalities
    ):
        raise TypeError("equalities must contain LinearEquality values")
    identifiers = tuple(row.identifier for row in equalities)
    if any(not identifier for identifier in identifiers):
        raise ValueError("equality identifiers must be non-empty")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("equality identifiers must be unique")
    for row in equalities:
        if any(
            not 0 <= variable < number_of_variables
            for variable, _ in row.form.terms
        ):
            raise ValueError(
                "equality variable index is out of range"
            )
    return equalities


def _augmented_row(form, number_of_variables):
    coefficients = dict(form.terms)
    return (
        form.constant,
        *(
            coefficients.get(index, Fraction(0))
            for index in range(number_of_variables)
        ),
    )


def _parameterization(rows, number_of_variables):
    matrix = [
        [
            *row[1:],
            -row[0],
        ]
        for row in rows
    ]
    pivot_columns = []
    pivot_row = 0
    for column in range(number_of_variables):
        selected = next(
            (
                row
                for row in range(pivot_row, len(matrix))
                if matrix[row][column]
            ),
            None,
        )
        if selected is None:
            continue
        matrix[pivot_row], matrix[selected] = (
            matrix[selected],
            matrix[pivot_row],
        )
        inverse = Fraction(1, 1) / matrix[pivot_row][column]
        matrix[pivot_row] = [
            inverse * value for value in matrix[pivot_row]
        ]
        for row in range(len(matrix)):
            if row == pivot_row or not matrix[row][column]:
                continue
            factor = matrix[row][column]
            matrix[row] = [
                left - factor * right
                for left, right in zip(
                    matrix[row],
                    matrix[pivot_row],
                )
            ]
        pivot_columns.append(column)
        pivot_row += 1
        if pivot_row == len(matrix):
            break
    for row in matrix[pivot_row:]:
        if not any(row[:-1]) and row[-1]:
            raise ValueError("inconsistent-equality-system")
    pivot_columns = tuple(pivot_columns)
    free_variables = tuple(
        column
        for column in range(number_of_variables)
        if column not in set(pivot_columns)
    )
    offset = tuple(
        (pivot, matrix[row][-1])
        for row, pivot in enumerate(pivot_columns)
        if matrix[row][-1]
    )
    nullspace = []
    for free in free_variables:
        column = [(free, Fraction(1))]
        column.extend(
            (
                pivot,
                -matrix[row][free],
            )
            for row, pivot in enumerate(pivot_columns)
            if matrix[row][free]
        )
        nullspace.append(tuple(sorted(column)))
    result = AffineParameterization(
        offset=offset,
        nullspace=tuple(nullspace),
        free_variables=free_variables,
        affine_nonzeros=(
            len(offset)
            + sum(len(column) for column in nullspace)
        ),
    )
    _verify_parameterization(rows, result)
    return pivot_columns, result


def _verify_parameterization(rows, parameterization):
    offset = dict(parameterization.offset)
    nullspace = tuple(
        dict(column) for column in parameterization.nullspace
    )
    for row in rows:
        terms = tuple(
            (variable, coefficient)
            for variable, coefficient in enumerate(row[1:])
            if coefficient
        )
        constant = row[0] + sum(
            coefficient * offset.get(variable, Fraction(0))
            for variable, coefficient in terms
        )
        if constant:
            raise ArithmeticError(
                "equality offset substitution failed"
            )
        for column in nullspace:
            coefficient = sum(
                value * column.get(variable, Fraction(0))
                for variable, value in terms
            )
            if coefficient:
                raise ArithmeticError(
                    "equality nullspace substitution failed"
                )


def _iter_affine_forms(value):
    if isinstance(value, RationalLinearForm):
        yield value
        return
    if hasattr(value, "upper_entries"):
        for entry in value.upper_entries:
            if not isinstance(entry.form, RationalLinearForm):
                raise TypeError(
                    "affine block entries must be rational forms"
                )
            yield entry.form
        return
    if isinstance(value, (tuple, list)):
        for item in value:
            yield from _iter_affine_forms(item)
        return
    raise TypeError(
        "affine_blocks must contain rational forms or sparse blocks"
    )


def _affine_nonzeros(form):
    return int(form.constant != 0) + len(form.terms)


def _substitute_form(form, parameterization):
    offset = dict(parameterization.offset)
    nullspace = tuple(
        dict(column) for column in parameterization.nullspace
    )
    coefficients = dict(form.terms)
    constant = form.constant + sum(
        coefficient * offset.get(variable, Fraction(0))
        for variable, coefficient in coefficients.items()
    )
    terms = []
    for free_position, column in enumerate(nullspace):
        value = sum(
            coefficient * column.get(variable, Fraction(0))
            for variable, coefficient in coefficients.items()
        )
        if value:
            terms.append((free_position, value))
    return RationalLinearForm(constant=constant, terms=tuple(terms))


def _primitive_hash(primitive):
    encoded = json.dumps(
        list(primitive),
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compress_equalities(
    equalities,
    number_of_variables,
    affine_blocks,
    fill_cap=Fraction(2),
) -> EqualityReduction:
    equalities = _validate_rows(
        equalities,
        number_of_variables,
    )
    fill_cap = _exact_fill_cap(fill_cap)
    rows = tuple(
        _augmented_row(row.form, number_of_variables)
        for row in equalities
    )
    exact = rational_row_basis(
        rows,
        modular_primes=DEFAULT_MODULAR_PRIMES,
    )
    kept_identifiers = tuple(
        equalities[index].identifier for index in exact.selected
    )
    span_map = {
        row.identifier: tuple(
            (
                kept_identifiers[selected_position],
                coefficient,
            )
            for selected_position, coefficient in reconstruction
        )
        for row, reconstruction in zip(
            equalities,
            exact.reconstruction,
        )
    }
    duplicate_map = {}
    primitive_first = {}
    primitive_scales = {}
    canonical_hashes = {}
    for row, values, primitive in zip(
        equalities,
        rows,
        exact.primitive_rows,
    ):
        scale = next(
            (
                value / primitive[index]
                for index, value in enumerate(values)
                if primitive[index]
            ),
            Fraction(1),
        )
        primitive_scales[row.identifier] = scale
        canonical_hashes[row.identifier] = _primitive_hash(primitive)
        if not any(primitive):
            continue
        if primitive in primitive_first:
            kept_identifier, kept_scale = primitive_first[primitive]
            duplicate_map[row.identifier] = {
                "kept_identifier": kept_identifier,
                "scale_to_kept": scale / kept_scale,
                "provenance": dict(row.provenance),
            }
        else:
            primitive_first[primitive] = (
                row.identifier,
                scale,
            )

    independent_rows = tuple(
        rows[index] for index in exact.selected
    )
    pivot_columns, parameterization = _parameterization(
        independent_rows,
        number_of_variables,
    )
    _verify_parameterization(rows, parameterization)
    if len(pivot_columns) != len(exact.selected):
        raise ArithmeticError(
            "affine coefficient rank differs from augmented row rank"
        )
    forms = tuple(_iter_affine_forms(tuple(affine_blocks)))
    row_reduced_nnz = sum(
        _affine_nonzeros(form) for form in forms
    )
    parameterized_forms = tuple(
        _substitute_form(form, parameterization)
        for form in forms
    )
    parameterized_nnz = sum(
        _affine_nonzeros(form)
        for form in parameterized_forms
    )
    free_count = len(parameterization.free_variables)
    row_reduced_kkt_proxy = (
        (number_of_variables + len(exact.selected)) ** 2
        + row_reduced_nnz
    )
    parameterized_kkt_proxy = (
        free_count**2 + parameterized_nnz
    )
    within_fill = (
        parameterized_nnz
        <= fill_cap * row_reduced_nnz
    )
    lower_kkt = (
        parameterized_kkt_proxy < row_reduced_kkt_proxy
    )
    if within_fill and lower_kkt:
        selected_view = "parameterized"
        reason = (
            "parameterized-within-fill-cap-and-lower-kkt-proxy"
        )
    else:
        selected_view = "row-reduced"
        reason = (
            "parameterized-fill-exceeds-cap"
            if not within_fill
            else "parameterized-kkt-proxy-not-lower"
        )
    statistics = {
        "original_row_count": len(equalities),
        "unique_primitive_row_count": len(primitive_first),
        "parameterization_input_row_count": len(independent_rows),
        "row_rank": len(exact.selected),
        "free_variable_count": free_count,
        "row_reduced_affine_nonzeros": row_reduced_nnz,
        "parameterized_affine_nonzeros": parameterized_nnz,
        "row_reduced_kkt_proxy": row_reduced_kkt_proxy,
        "parameterized_kkt_proxy": parameterized_kkt_proxy,
        "fill_cap": fill_cap,
        "selection_reason": reason,
        "modular_primes": exact.modular_primes,
        "used_modular_fallback": exact.used_fallback,
        "max_bit_length": exact.max_bit_length,
        "primitive_scales": primitive_scales,
        "canonical_row_sha256": canonical_hashes,
        "row_provenance": {
            row.identifier: dict(row.provenance)
            for row in equalities
        },
        "all_identifiers": tuple(
            row.identifier for row in equalities
        ),
    }
    return EqualityReduction(
        kept_identifiers=kept_identifiers,
        duplicate_map=duplicate_map,
        span_map=span_map,
        pivot_columns=pivot_columns,
        row_rank=len(exact.selected),
        parameterization=parameterization,
        selected_view=selected_view,
        statistics=statistics,
    )


def verify_equality_reduction(
    equalities,
    number_of_variables,
    affine_blocks,
    reduction: EqualityReduction,
    fill_cap=Fraction(2),
) -> dict:
    """Recompute and exactly compare every equality reduction field."""
    if not isinstance(reduction, EqualityReduction):
        raise TypeError("reduction must be an EqualityReduction")
    fill_cap = _exact_fill_cap(fill_cap)
    if reduction.statistics.get("fill_cap") != fill_cap:
        raise ValueError("equality fill cap mismatch")
    expected = compress_equalities(
        equalities,
        number_of_variables,
        affine_blocks,
        fill_cap=fill_cap,
    )
    if reduction.duplicate_map != expected.duplicate_map:
        raise ValueError("equality duplicate map mismatch")
    if reduction.span_map != expected.span_map:
        raise ValueError("equality span map mismatch")
    if reduction.kept_identifiers != expected.kept_identifiers:
        raise ValueError("equality kept-row inventory mismatch")
    if reduction.pivot_columns != expected.pivot_columns:
        raise ValueError("equality pivot-column inventory mismatch")
    if reduction.row_rank != expected.row_rank:
        raise ValueError("equality row rank mismatch")
    if (
        reduction.parameterization.offset
        != expected.parameterization.offset
    ):
        raise ValueError("equality parameterization offset mismatch")
    if (
        reduction.parameterization.nullspace
        != expected.parameterization.nullspace
    ):
        raise ValueError("equality parameterization nullspace mismatch")
    if (
        reduction.parameterization.free_variables
        != expected.parameterization.free_variables
    ):
        raise ValueError(
            "equality parameterization free-variable mismatch"
        )
    if (
        reduction.parameterization.affine_nonzeros
        != expected.parameterization.affine_nonzeros
    ):
        raise ValueError(
            "equality parameterization nonzero count mismatch"
        )
    if reduction.selected_view != expected.selected_view:
        raise ValueError("equality selected view mismatch")
    if (
        reduction.statistics.get("selection_reason")
        != expected.statistics["selection_reason"]
    ):
        raise ValueError("equality selection reason mismatch")
    if (
        reduction.statistics.get("primitive_scales")
        != expected.statistics["primitive_scales"]
    ):
        raise ValueError("equality primitive scale inventory mismatch")
    if (
        reduction.statistics.get("row_provenance")
        != expected.statistics["row_provenance"]
    ):
        raise ValueError("equality row provenance mismatch")
    if reduction.statistics != expected.statistics:
        raise ValueError("equality reduction statistics mismatch")
    return {
        "status": "verified",
        "row_rank": reduction.row_rank,
        "free_variable_count": len(
            reduction.parameterization.free_variables
        ),
        "selected_view": reduction.selected_view,
    }
