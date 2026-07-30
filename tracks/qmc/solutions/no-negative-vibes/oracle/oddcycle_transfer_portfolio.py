"""Deterministic discrete-transfer Hamiltonian portfolio construction."""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations

import numpy as np
import sympy as sp

from oracle.oddcycle_local_hs_scan import (
    forbidden_label_indices,
    locality_specs,
)
from oracle.oddcycle_word_operator import (
    NormalOrderedLabel,
    WordPairColumn,
    normal_ordered_labels,
    normal_ordered_monomial,
)


_LOG_RECONSTRUCTION_TOLERANCE = 1.0e-10


@dataclass(frozen=True)
class TransferPortfolioRecord:
    """One exactly shifted transfer and its numerical Hamiltonian diagnostics."""

    status: str
    seed: int
    sample_index: int
    source_words: tuple[tuple[int, ...], ...]
    source_transpose_words: tuple[tuple[int, ...], ...]
    exact_weights: tuple[sp.Rational, ...]
    exact_shift: int
    exact_vacuum_value: sp.Rational
    exact_minimum_row_margin: sp.Rational
    minimum_eigenvalue: float | None
    log_reconstruction_residual: float | None
    coordinate_reconstruction_residual: float | None
    body_order_norms: Mapping[int, float]
    forbidden_support_norms: Mapping[str, float]
    gaussian_grade_distance: float | None
    interaction_norm: float


def _validate_inputs(
    columns: Sequence[WordPairColumn],
    seed: int,
    sample_count: int,
) -> tuple[WordPairColumn, ...]:
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TypeError("seed must be an integer")
    if (
        not isinstance(sample_count, int)
        or isinstance(sample_count, bool)
        or sample_count < 0
    ):
        raise ValueError("sample_count must be a nonnegative integer")

    normalized = tuple(columns)
    if sample_count and not normalized:
        raise ValueError("columns must be nonempty when samples are requested")
    if not normalized:
        return normalized
    if any(not isinstance(column, WordPairColumn) for column in normalized):
        raise TypeError("columns must contain WordPairColumn records")

    dimension = normalized[0].fock_pair.rows
    labels = set(normalized[0].coordinates)
    if (
        dimension != normalized[0].fock_pair.cols
        or dimension < 2
        or dimension & (dimension - 1)
    ):
        raise ValueError("column Fock matrices must have power-of-two dimension")
    for column in normalized:
        if column.fock_pair.shape != (dimension, dimension):
            raise ValueError("columns must use one Fock dimension")
        if column.fock_pair != column.fock_pair.T:
            raise ValueError("column Fock matrices must be exactly symmetric")
        if set(column.coordinates) != labels:
            raise ValueError("columns must use one common coordinate basis")
    return normalized


def _sample_positive_rational_weights(
    generator: random.Random,
    count: int,
) -> tuple[sp.Rational, ...]:
    numerators = tuple(generator.randint(1, 16) for _ in range(count))
    denominator = sum(numerators)
    return tuple(sp.Rational(value, denominator) for value in numerators)


def _exact_shifted_transfer(
    columns: tuple[WordPairColumn, ...],
    weights: tuple[sp.Rational, ...],
) -> tuple[sp.ImmutableMatrix, int, sp.Rational, sp.Rational]:
    dimension = columns[0].fock_pair.rows
    weighted_sum = sp.zeros(dimension)
    for weight, column in zip(weights, columns, strict=True):
        weighted_sum += weight * column.fock_pair

    row_requirements = tuple(
        sp.cancel(
            sum(
                abs(weighted_sum[row, column])
                for column in range(dimension)
                if column != row
            )
            - weighted_sum[row, row]
        )
        for row in range(dimension)
    )
    maximum_requirement = max(row_requirements)
    shift = int(sp.floor(maximum_requirement)) + 1
    transfer = sp.ImmutableMatrix(weighted_sum + shift * sp.eye(dimension))
    row_margins = tuple(
        sp.cancel(shift - requirement) for requirement in row_requirements
    )
    minimum_margin = sp.Rational(min(row_margins))
    vacuum_value = sp.Rational(transfer[0, 0])
    if minimum_margin <= 0:
        raise ArithmeticError("exact diagonal-dominance shift is not strict")
    if vacuum_value <= 0:
        raise ArithmeticError("an SPD transfer must have positive vacuum entry")
    return transfer, shift, vacuum_value, minimum_margin


def _numerical_normal_ordered_coordinates(
    operator: np.ndarray,
    modes: int,
) -> tuple[
    tuple[NormalOrderedLabel, ...],
    np.ndarray,
    float,
]:
    labels = normal_ordered_labels(modes)
    residual = np.array(operator, dtype=np.float64, copy=True)
    coefficients = np.zeros(len(labels), dtype=np.float64)
    for index, label in enumerate(labels):
        monomial = np.asarray(
            normal_ordered_monomial(modes, label).tolist(),
            dtype=np.float64,
        )
        row = sum(1 << mode for mode in label.create)
        column = sum(1 << mode for mode in label.annihilate)
        pivot = monomial[row, column]
        if pivot not in (-1.0, 1.0):
            raise ArithmeticError("normal-ordered pivot is not a unit")
        coefficient = residual[row, column] / pivot
        coefficients[index] = coefficient
        if coefficient:
            residual -= coefficient * monomial
    reconstruction_residual = float(np.linalg.norm(residual, ord="fro"))
    return labels, coefficients, reconstruction_residual


def _numerical_gaussian_fock_lift(
    one_particle_matrix: np.ndarray,
) -> np.ndarray:
    modes = one_particle_matrix.shape[0]
    dimension = 1 << modes
    result = np.zeros((dimension, dimension), dtype=np.float64)
    result[0, 0] = 1.0
    for particles in range(1, modes + 1):
        subsets = tuple(combinations(range(modes), particles))
        for row_subset in subsets:
            row_mask = sum(1 << index for index in row_subset)
            for column_subset in subsets:
                column_mask = sum(1 << index for index in column_subset)
                minor = one_particle_matrix[np.ix_(row_subset, column_subset)]
                result[row_mask, column_mask] = float(np.linalg.det(minor))
    return result


def _gaussian_grade_distance(normalized_transfer: np.ndarray) -> float:
    dimension = normalized_transfer.shape[0]
    modes = dimension.bit_length() - 1
    grade_one = tuple(1 << index for index in range(modes))
    one_particle = normalized_transfer[np.ix_(grade_one, grade_one)]
    gaussian_lift = _numerical_gaussian_fock_lift(one_particle)
    return float(np.linalg.norm(normalized_transfer - gaussian_lift, ord="fro"))


def _inconclusive_record(
    *,
    seed: int,
    sample_index: int,
    columns: tuple[WordPairColumn, ...],
    weights: tuple[sp.Rational, ...],
    shift: int,
    vacuum_value: sp.Rational,
    minimum_margin: sp.Rational,
    minimum_eigenvalue: float | None,
    reconstruction_residual: float | None,
) -> TransferPortfolioRecord:
    return TransferPortfolioRecord(
        status="numerical-log-inconclusive",
        seed=seed,
        sample_index=sample_index,
        source_words=tuple(column.word for column in columns),
        source_transpose_words=tuple(
            column.transpose_word for column in columns
        ),
        exact_weights=weights,
        exact_shift=shift,
        exact_vacuum_value=vacuum_value,
        exact_minimum_row_margin=minimum_margin,
        minimum_eigenvalue=minimum_eigenvalue,
        log_reconstruction_residual=reconstruction_residual,
        coordinate_reconstruction_residual=None,
        body_order_norms={},
        forbidden_support_norms={},
        gaussian_grade_distance=None,
        interaction_norm=0.0,
    )


def _analyze_sample(
    columns: tuple[WordPairColumn, ...],
    weights: tuple[sp.Rational, ...],
    *,
    seed: int,
    sample_index: int,
) -> TransferPortfolioRecord:
    transfer, shift, vacuum_value, minimum_margin = _exact_shifted_transfer(
        columns, weights
    )
    numerical_transfer = np.asarray(transfer.tolist(), dtype=np.float64)
    normalized_transfer = numerical_transfer / float(vacuum_value)

    try:
        transfer_eigenvalues, transfer_eigenvectors = np.linalg.eigh(
            normalized_transfer
        )
    except np.linalg.LinAlgError:
        return _inconclusive_record(
            seed=seed,
            sample_index=sample_index,
            columns=columns,
            weights=weights,
            shift=shift,
            vacuum_value=vacuum_value,
            minimum_margin=minimum_margin,
            minimum_eigenvalue=None,
            reconstruction_residual=None,
        )

    minimum_normalized_eigenvalue = float(np.min(transfer_eigenvalues))
    minimum_eigenvalue = (
        minimum_normalized_eigenvalue * float(vacuum_value)
    )
    if (
        not np.all(np.isfinite(transfer_eigenvalues))
        or minimum_normalized_eigenvalue <= 0.0
    ):
        return _inconclusive_record(
            seed=seed,
            sample_index=sample_index,
            columns=columns,
            weights=weights,
            shift=shift,
            vacuum_value=vacuum_value,
            minimum_margin=minimum_margin,
            minimum_eigenvalue=minimum_eigenvalue,
            reconstruction_residual=None,
        )

    log_eigenvalues = -np.log(transfer_eigenvalues)
    hamiltonian = (
        transfer_eigenvectors * log_eigenvalues
    ) @ transfer_eigenvectors.T
    hamiltonian = 0.5 * (hamiltonian + hamiltonian.T)

    try:
        hamiltonian_eigenvalues, hamiltonian_eigenvectors = np.linalg.eigh(
            hamiltonian
        )
    except np.linalg.LinAlgError:
        return _inconclusive_record(
            seed=seed,
            sample_index=sample_index,
            columns=columns,
            weights=weights,
            shift=shift,
            vacuum_value=vacuum_value,
            minimum_margin=minimum_margin,
            minimum_eigenvalue=minimum_eigenvalue,
            reconstruction_residual=None,
        )
    reconstructed_transfer = (
        hamiltonian_eigenvectors * np.exp(-hamiltonian_eigenvalues)
    ) @ hamiltonian_eigenvectors.T
    log_residual = float(
        np.linalg.norm(
            reconstructed_transfer - normalized_transfer,
            ord="fro",
        )
    )
    if (
        not math.isfinite(log_residual)
        or log_residual > _LOG_RECONSTRUCTION_TOLERANCE
    ):
        return _inconclusive_record(
            seed=seed,
            sample_index=sample_index,
            columns=columns,
            weights=weights,
            shift=shift,
            vacuum_value=vacuum_value,
            minimum_margin=minimum_margin,
            minimum_eigenvalue=minimum_eigenvalue,
            reconstruction_residual=log_residual,
        )

    modes = transfer.rows.bit_length() - 1
    labels, coefficients, coordinate_residual = (
        _numerical_normal_ordered_coordinates(hamiltonian, modes)
    )
    gaussian_distance = _gaussian_grade_distance(normalized_transfer)
    if (
        not np.all(np.isfinite(coefficients))
        or not math.isfinite(coordinate_residual)
        or not math.isfinite(gaussian_distance)
    ):
        return _inconclusive_record(
            seed=seed,
            sample_index=sample_index,
            columns=columns,
            weights=weights,
            shift=shift,
            vacuum_value=vacuum_value,
            minimum_margin=minimum_margin,
            minimum_eigenvalue=minimum_eigenvalue,
            reconstruction_residual=log_residual,
        )
    body_order_norms = {
        order: float(
            np.linalg.norm(
                coefficients[
                    [
                        index
                        for index, label in enumerate(labels)
                        if label.body_order == order
                    ]
                ]
            )
        )
        for order in range(modes + 1)
    }
    interaction_norm = float(
        np.linalg.norm(
            coefficients[
                [
                    index
                    for index, label in enumerate(labels)
                    if label.body_order >= 2
                ]
            ]
        )
    )
    forbidden_support_norms = {}
    for name, spec in locality_specs().items():
        forbidden = forbidden_label_indices(labels, spec)
        forbidden_support_norms[name] = float(
            np.linalg.norm(coefficients[list(forbidden)])
        )

    return TransferPortfolioRecord(
        status="numerical-log-conclusive",
        seed=seed,
        sample_index=sample_index,
        source_words=tuple(column.word for column in columns),
        source_transpose_words=tuple(
            column.transpose_word for column in columns
        ),
        exact_weights=weights,
        exact_shift=shift,
        exact_vacuum_value=vacuum_value,
        exact_minimum_row_margin=minimum_margin,
        minimum_eigenvalue=minimum_eigenvalue,
        log_reconstruction_residual=log_residual,
        coordinate_reconstruction_residual=coordinate_residual,
        body_order_norms=body_order_norms,
        forbidden_support_norms=forbidden_support_norms,
        gaussian_grade_distance=gaussian_distance,
        interaction_norm=interaction_norm,
    )


def _ranking_key(record: TransferPortfolioRecord) -> tuple[object, ...]:
    if record.status == "numerical-log-inconclusive":
        return (1, record.sample_index)
    forbidden = record.forbidden_support_norms
    return (
        0,
        forbidden["cluster-two-body"],
        forbidden["ring-arc3"],
        forbidden["ring-edge"],
        -record.interaction_norm,
        -float(record.gaussian_grade_distance),
        record.sample_index,
    )


def rank_transfer_portfolio(
    columns: Sequence[WordPairColumn],
    seed: int,
    sample_count: int,
) -> tuple[TransferPortfolioRecord, ...]:
    """Sample, diagnose, and deterministically rank shifted SPD transfers."""

    normalized_columns = _validate_inputs(columns, seed, sample_count)
    if sample_count == 0:
        return ()
    generator = random.Random(seed)
    records = tuple(
        _analyze_sample(
            normalized_columns,
            _sample_positive_rational_weights(
                generator, len(normalized_columns)
            ),
            seed=seed,
            sample_index=sample_index,
        )
        for sample_index in range(sample_count)
    )
    return tuple(sorted(records, key=_ranking_key))


__all__ = [
    "TransferPortfolioRecord",
    "rank_transfer_portfolio",
]
