"""Tensor-square determinant positivity and its smallest physical HS gate."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np
from scipy.linalg import expm
import sympy as sp

from oracle.tn_bond_hs import number_conserving_gaussian_fock_matrix


@dataclass(frozen=True)
class TensorSquareHistory:
    base_product: np.ndarray
    lifted_product: np.ndarray
    weight: float


@dataclass(frozen=True)
class ExactIndependentFieldCounterexample:
    base_factors: tuple[sp.ImmutableMatrix, ...]
    onsite_field: sp.ImmutableMatrix
    weight: sp.Rational


@dataclass(frozen=True)
class TensorSquareDensityFields:
    base_propagators: tuple[np.ndarray, np.ndarray]
    lifted_propagators: tuple[np.ndarray, np.ndarray]
    kappa: float
    repulsive_coupling: float
    chemical_potential: float


@dataclass(frozen=True)
class PlaquetteTrotterDecomposition:
    base_half_kinetic: np.ndarray
    lifted_half_kinetic: np.ndarray
    fock_half_kinetic: np.ndarray
    base_field_propagators: tuple[np.ndarray, np.ndarray]
    lifted_field_propagators: tuple[np.ndarray, np.ndarray]
    fock_field_gates: tuple[np.ndarray, np.ndarray]
    interaction_gate: np.ndarray


def _validated_square_matrix(matrix: np.ndarray, *, name: str) -> np.ndarray:
    candidate = np.asarray(matrix, dtype=float)
    if candidate.ndim != 2 or candidate.shape[0] != candidate.shape[1]:
        raise ValueError(f"{name} must be square")
    if candidate.shape[0] < 1:
        raise ValueError(f"{name} must be nonempty")
    if not np.all(np.isfinite(candidate)):
        raise ValueError(f"{name} must have finite entries")
    return candidate


def tensor_square_weight(base_matrix: np.ndarray) -> float:
    """Evaluate ``det(I + X tensor X)`` for one real base matrix."""

    matrix = _validated_square_matrix(base_matrix, name="base_matrix")
    lifted = np.kron(matrix, matrix)
    return float(np.linalg.det(np.eye(lifted.shape[0]) + lifted))


def two_by_two_weight_formula(base_matrix: np.ndarray) -> float:
    """Return the exact two-invariant sum-of-squares formula for ``m=2``."""

    matrix = _validated_square_matrix(base_matrix, name="base_matrix")
    if matrix.shape != (2, 2):
        raise ValueError("base_matrix must have shape (2, 2)")
    trace = float(np.trace(matrix))
    determinant = float(np.linalg.det(matrix))
    return (1.0 + determinant) ** 2 * (
        (1.0 - determinant) ** 2 + trace**2
    )


def two_by_two_split_metric() -> np.ndarray:
    """Return the symmetric ``(2,2)`` metric ``epsilon tensor epsilon``."""

    epsilon = np.asarray([[0.0, 1.0], [-1.0, 0.0]])
    return np.kron(epsilon, epsilon)


def conformal_split_residual(base_matrix: np.ndarray) -> float:
    """Check ``B^T eta B = det(X)^2 eta`` for ``B=X tensor X``."""

    matrix = _validated_square_matrix(base_matrix, name="base_matrix")
    if matrix.shape != (2, 2):
        raise ValueError("base_matrix must have shape (2, 2)")
    lifted = np.kron(matrix, matrix)
    metric = two_by_two_split_metric()
    residual = (
        lifted.T @ metric @ lifted
        - float(np.linalg.det(matrix)) ** 2 * metric
    )
    return float(np.linalg.norm(residual))


def tensor_square_history(
    base_factors: Sequence[np.ndarray],
) -> TensorSquareHistory:
    """Multiply a history while retaining the exact tensor-square closure."""

    factors = tuple(
        _validated_square_matrix(factor, name="base factor")
        for factor in base_factors
    )
    if not factors:
        raise ValueError("at least one base factor is required")
    shape = factors[0].shape
    if any(factor.shape != shape for factor in factors):
        raise ValueError("all base factors must have the same shape")

    base_product = np.eye(shape[0])
    lifted_product = np.eye(shape[0] ** 2)
    for factor in factors:
        base_product = base_product @ factor
        lifted_product = lifted_product @ np.kron(factor, factor)
    weight = float(
        np.linalg.det(np.eye(lifted_product.shape[0]) + lifted_product)
    )
    return TensorSquareHistory(
        base_product=base_product,
        lifted_product=lifted_product,
        weight=weight,
    )


def independent_field_counterexample_exact(
) -> ExactIndependentFieldCounterexample:
    """Return the exact failure of arbitrary independent onsite fields."""

    first = sp.ImmutableMatrix([[2, -3], [-3, 7]])
    second = sp.ImmutableMatrix([[4, 4], [4, 5]])
    onsite = sp.ImmutableMatrix(
        sp.diag(16, 1, sp.Rational(1, 8), sp.Rational(1, 16))
    )
    product = (
        sp.kronecker_product(first, first)
        * onsite
        * sp.kronecker_product(second, second)
    )
    weight = sp.factor((sp.eye(4) + product).det())
    if not isinstance(weight, sp.Rational):
        raise RuntimeError("counterexample weight did not simplify to a rational")
    return ExactIndependentFieldCounterexample(
        base_factors=(first, second),
        onsite_field=onsite,
        weight=weight,
    )


def tensor_square_density_fields(
    field_coupling: float,
) -> TensorSquareDensityFields:
    """Construct the two tied diagonal fields on a four-mode square."""

    if not math.isfinite(field_coupling) or field_coupling <= 0.0:
        raise ValueError("field_coupling must be positive and finite")
    positive = np.diag(
        [math.exp(field_coupling), math.exp(-field_coupling)]
    )
    negative = np.diag(
        [math.exp(-field_coupling), math.exp(field_coupling)]
    )
    kappa = math.log(math.cosh(2.0 * field_coupling))
    return TensorSquareDensityFields(
        base_propagators=(positive, negative),
        lifted_propagators=(
            np.kron(positive, positive),
            np.kron(negative, negative),
        ),
        kappa=kappa,
        repulsive_coupling=2.0 * kappa,
        chemical_potential=kappa,
    )


def tensor_square_density_interaction_gate(
    field_coupling: float,
) -> np.ndarray:
    """Return the exact four-mode repulsive density gate generated by the fields.

    Modes are ordered ``(00,01,10,11)``.  The gate is

    ``exp[kappa (n_00+n_11-2 n_00 n_11)]``.
    """

    fields = tensor_square_density_fields(field_coupling)
    diagonal = np.empty(16)
    for state in range(16):
        first = (state >> 0) & 1
        last = (state >> 3) & 1
        exponent = fields.kappa * (first + last - 2 * first * last)
        diagonal[state] = math.exp(exponent)
    return np.diag(diagonal)


def square_kinetic_generator(*, hopping: float) -> np.ndarray:
    """Lift one base bond to the four-cycle Cartesian-square hopping graph."""

    if not math.isfinite(hopping):
        raise ValueError("hopping must be finite")
    base = np.asarray([[0.0, hopping], [hopping, 0.0]])
    identity = np.eye(2)
    return np.kron(base, identity) + np.kron(identity, base)


def plaquette_trotter_decomposition(
    *,
    time_step: float,
    hopping: float,
    field_coupling: float,
) -> PlaquetteTrotterDecomposition:
    """Build a positive two-field decomposition of one four-mode Trotter gate."""

    if not math.isfinite(time_step) or time_step <= 0.0:
        raise ValueError("time_step must be positive and finite")
    if not math.isfinite(hopping) or hopping < 0.0:
        raise ValueError("hopping must be nonnegative and finite")
    fields = tensor_square_density_fields(field_coupling)
    base_hopping = np.asarray([[0.0, hopping], [hopping, 0.0]])
    base_half = expm(0.5 * time_step * base_hopping)
    lifted_half = np.kron(base_half, base_half)
    fock_half = number_conserving_gaussian_fock_matrix(lifted_half)

    base_field_propagators = tuple(
        base_half @ field @ base_half
        for field in fields.base_propagators
    )
    lifted_field_propagators = tuple(
        np.kron(field, field)
        for field in base_field_propagators
    )
    fock_field_gates = tuple(
        number_conserving_gaussian_fock_matrix(field)
        for field in lifted_field_propagators
    )
    return PlaquetteTrotterDecomposition(
        base_half_kinetic=base_half,
        lifted_half_kinetic=lifted_half,
        fock_half_kinetic=fock_half,
        base_field_propagators=base_field_propagators,
        lifted_field_propagators=lifted_field_propagators,
        fock_field_gates=fock_field_gates,
        interaction_gate=tensor_square_density_interaction_gate(
            field_coupling
        ),
    )


def lifted_base_edge_generator(
    *,
    base_dimension: int,
    edge: tuple[int, int],
    coupling: float,
) -> np.ndarray:
    """Lift one local base edge to both coordinate strips."""

    if base_dimension < 2:
        raise ValueError("base_dimension must be at least two")
    left, right = edge
    if not 0 <= left < right < base_dimension:
        raise ValueError("edge must contain two ordered base indices")
    if not math.isfinite(coupling):
        raise ValueError("coupling must be finite")
    base = np.zeros((base_dimension, base_dimension))
    base[left, right] = coupling
    base[right, left] = coupling
    identity = np.eye(base_dimension)
    return np.kron(base, identity) + np.kron(identity, base)


def lifted_diagonal_field(base_field: np.ndarray) -> np.ndarray:
    """Return the diagonal potential ``v_(ij)=u_i+u_j`` as a flat vector."""

    field = np.asarray(base_field, dtype=float)
    if field.ndim != 1 or field.size < 1:
        raise ValueError("base_field must be a nonempty vector")
    if not np.all(np.isfinite(field)):
        raise ValueError("base_field must have finite entries")
    return np.add.outer(field, field).reshape(-1)
