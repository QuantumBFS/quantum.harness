"""Adjoint-lift determinant positivity and an exact cosh transfer gate.

For every invertible real matrix with positive determinant,

    B(X) = X tensor X^{-T}

obeys ``det(I+B(X)) >= 0``.  The family is multiplicatively closed because
``B(X)B(Y)=B(XY)``.  It also preserves the commutation metric, so this module
records the construction as a structured pseudo-orthogonal subgroup rather
than claiming an unrelated new positivity principle.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np
from scipy.linalg import expm

from oracle.tn_bond_hs import number_conserving_gaussian_fock_matrix


@dataclass(frozen=True)
class AdjointLiftHistory:
    base_product: np.ndarray
    lifted_product: np.ndarray
    weight: float
    pairing_formula: float
    closure_residual: float


@dataclass(frozen=True)
class AdjointCoshDecomposition:
    base_half_kinetic: np.ndarray
    lifted_half_kinetic: np.ndarray
    base_field_propagators: tuple[np.ndarray, np.ndarray]
    lifted_field_propagators: tuple[np.ndarray, np.ndarray]
    fock_half_kinetic: np.ndarray
    fock_field_gates: tuple[np.ndarray, np.ndarray]
    interaction_gate: np.ndarray
    lifted_charge_generator: np.ndarray


def _real_square(matrix: np.ndarray, *, name: str) -> np.ndarray:
    candidate = np.asarray(matrix, dtype=float)
    if candidate.ndim != 2 or candidate.shape[0] != candidate.shape[1]:
        raise ValueError(f"{name} must be square")
    if candidate.shape[0] < 1:
        raise ValueError(f"{name} must be nonempty")
    if not np.all(np.isfinite(candidate)):
        raise ValueError(f"{name} must have finite entries")
    return candidate


def adjoint_lift(base_matrix: np.ndarray) -> np.ndarray:
    """Return ``X tensor X^{-T}`` for an orientation-preserving matrix."""

    matrix = _real_square(base_matrix, name="base_matrix")
    determinant = float(np.linalg.det(matrix))
    if determinant <= 0.0:
        raise ValueError("base_matrix must have positive determinant")
    return np.kron(matrix, np.linalg.inv(matrix).T)


def commutation_metric(base_dimension: int) -> np.ndarray:
    """Return the swap metric on ``R^m tensor R^m``."""

    if base_dimension < 1:
        raise ValueError("base_dimension must be positive")
    dimension = base_dimension**2
    metric = np.zeros((dimension, dimension))
    for first in range(base_dimension):
        for second in range(base_dimension):
            source = first * base_dimension + second
            target = second * base_dimension + first
            metric[target, source] = 1.0
    return metric


def commutation_metric_residual(base_matrix: np.ndarray) -> float:
    """Check ``B^T K B=K`` for the adjoint lift."""

    matrix = _real_square(base_matrix, name="base_matrix")
    lifted = adjoint_lift(matrix)
    metric = commutation_metric(matrix.shape[0])
    return float(np.linalg.norm(lifted.T @ metric @ lifted - metric))


def adjoint_pairing_formula(base_matrix: np.ndarray) -> float:
    """Evaluate the eigenvalue-pair square formula for the determinant."""

    matrix = _real_square(base_matrix, name="base_matrix")
    determinant = float(np.linalg.det(matrix))
    if determinant <= 0.0:
        raise ValueError("base_matrix must have positive determinant")
    eigenvalues = np.linalg.eigvals(matrix).astype(complex)
    numerator = complex(2.0 ** matrix.shape[0])
    for left in range(matrix.shape[0]):
        for right in range(left + 1, matrix.shape[0]):
            numerator *= (eigenvalues[left] + eigenvalues[right]) ** 2
    value = numerator / determinant ** (matrix.shape[0] - 1)
    if abs(value.imag) > 1e-7 * max(1.0, abs(value.real)):
        raise ArithmeticError("pairing formula did not evaluate to a real value")
    return float(value.real)


def adjoint_lift_history(
    base_factors: Sequence[np.ndarray],
) -> AdjointLiftHistory:
    """Multiply an arbitrary history and retain exact adjoint closure."""

    factors = tuple(
        _real_square(factor, name="base factor")
        for factor in base_factors
    )
    if not factors:
        raise ValueError("at least one base factor is required")
    shape = factors[0].shape
    if any(factor.shape != shape for factor in factors):
        raise ValueError("all base factors must have the same shape")
    if any(np.linalg.det(factor) <= 0.0 for factor in factors):
        raise ValueError("every base factor must have positive determinant")

    base_product = np.eye(shape[0])
    lifted_product = np.eye(shape[0] ** 2)
    for factor in factors:
        base_product = base_product @ factor
        lifted_product = lifted_product @ adjoint_lift(factor)
    expected = adjoint_lift(base_product)
    weight = float(
        np.linalg.det(np.eye(expected.shape[0]) + lifted_product)
    )
    return AdjointLiftHistory(
        base_product=base_product,
        lifted_product=lifted_product,
        weight=weight,
        pairing_formula=adjoint_pairing_formula(base_product),
        closure_residual=float(np.linalg.norm(lifted_product - expected)),
    )


def adjoint_lifted_generator(base_generator: np.ndarray) -> np.ndarray:
    """Return ``A tensor I - I tensor A^T``."""

    generator = _real_square(base_generator, name="base_generator")
    identity = np.eye(generator.shape[0])
    return np.kron(generator, identity) - np.kron(
        identity,
        generator.T,
    )


def adjoint_cosh_decomposition(
    *,
    time_step: float,
    kinetic_generator: np.ndarray,
    channel_generator: np.ndarray,
    field_coupling: float,
) -> AdjointCoshDecomposition:
    """Build a positive two-field gate in the adjoint-lift family."""

    if not math.isfinite(time_step) or time_step <= 0.0:
        raise ValueError("time_step must be positive and finite")
    if not math.isfinite(field_coupling) or field_coupling <= 0.0:
        raise ValueError("field_coupling must be positive and finite")
    kinetic = _real_square(
        kinetic_generator,
        name="kinetic_generator",
    )
    channel = _real_square(
        channel_generator,
        name="channel_generator",
    )
    if kinetic.shape != channel.shape:
        raise ValueError("kinetic and channel generators must have equal shape")
    if not np.allclose(kinetic, kinetic.T, atol=1e-12):
        raise ValueError("kinetic_generator must be symmetric")
    if not np.allclose(channel, channel.T, atol=1e-12):
        raise ValueError("channel_generator must be symmetric")

    base_half = expm(-0.5 * time_step * kinetic)
    lifted_half = adjoint_lift(base_half)
    positive = expm(field_coupling * channel)
    negative = expm(-field_coupling * channel)
    base_fields = (
        base_half @ positive @ base_half,
        base_half @ negative @ base_half,
    )
    lifted_fields = tuple(adjoint_lift(field) for field in base_fields)
    fock_half = number_conserving_gaussian_fock_matrix(lifted_half)
    fock_fields = tuple(
        number_conserving_gaussian_fock_matrix(field)
        for field in lifted_fields
    )
    pure_fields = (
        adjoint_lift(positive),
        adjoint_lift(negative),
    )
    interaction = 0.5 * sum(
        (
            number_conserving_gaussian_fock_matrix(field)
            for field in pure_fields
        ),
        start=np.zeros_like(fock_half),
    )
    return AdjointCoshDecomposition(
        base_half_kinetic=base_half,
        lifted_half_kinetic=lifted_half,
        base_field_propagators=base_fields,
        lifted_field_propagators=lifted_fields,
        fock_half_kinetic=fock_half,
        fock_field_gates=fock_fields,
        interaction_gate=interaction,
        lifted_charge_generator=adjoint_lifted_generator(channel),
    )
