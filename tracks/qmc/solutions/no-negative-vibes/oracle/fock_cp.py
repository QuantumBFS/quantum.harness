"""Completely-positive-cone tests for transformed Fock operators.

For an even number ``n=2r`` of fermion modes, the Fock dimension ``2^n`` is
the square of ``2^r``.  A fixed Fock-space similarity can therefore identify
Gaussian Fock operators with Liouville matrices acting on
``End(C^(2^r))``.  If every allowed slice is a completely positive map, then
arbitrary products remain completely positive and have nonnegative
Liouville trace.

This module owns only the representation-independent Choi tests and the
occupation-basis tensorization.  Candidate-specific six-mode searches live in
``fock_cp_screen.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

import numpy as np
from scipy.linalg import null_space


@dataclass(frozen=True)
class CompletePositivityCertificate:
    """Numerical Choi certificate for one finite linear map."""

    operator_dimension: int
    hermiticity_residual: float
    minimum_eigenvalue: float
    is_completely_positive: bool


@dataclass(frozen=True)
class ConditionalCompletePositivityCertificate:
    """Conditional Choi certificate for a continuous CP-semigroup generator."""

    operator_dimension: int
    hermiticity_residual: float
    minimum_conditional_eigenvalue: float
    conditional_block_norm: float
    is_conditionally_completely_positive: bool


def _operator_dimension(superoperator: np.ndarray) -> int:
    matrix = np.asarray(superoperator)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("superoperator must be square")
    dimension = math.isqrt(matrix.shape[0])
    if dimension * dimension != matrix.shape[0]:
        raise ValueError("superoperator dimension must be a perfect square")
    return dimension


def liouville_to_choi(
    superoperator: np.ndarray,
    *,
    operator_dimension: int | None = None,
) -> np.ndarray:
    """Reshuffle a column-vectorized Liouville matrix into its Choi matrix.

    The vectorization convention is ``vec(|a><b|)[a+d*b] = 1``.  Thus a
    one-Kraus map ``X -> K X K^dagger`` has Liouville matrix
    ``conjugate(K) tensor K`` and Choi matrix ``vec(K) vec(K)^dagger``.
    """

    matrix = np.asarray(superoperator, dtype=complex)
    inferred = _operator_dimension(matrix)
    if operator_dimension is None:
        operator_dimension = inferred
    if operator_dimension != inferred:
        raise ValueError("operator_dimension does not match superoperator shape")

    dimension = operator_dimension
    tensor = matrix.reshape(
        (dimension, dimension, dimension, dimension),
        order="F",
    )
    return tensor.transpose(0, 2, 1, 3).reshape(
        (dimension * dimension, dimension * dimension),
        order="F",
    )


def kraus_superoperator(kraus_operators: Iterable[np.ndarray]) -> np.ndarray:
    """Return the column-vectorized Liouville matrix of a Kraus map."""

    operators = tuple(np.asarray(operator, dtype=complex) for operator in kraus_operators)
    if not operators:
        raise ValueError("at least one Kraus operator is required")
    shape = operators[0].shape
    if len(shape) != 2 or shape[0] != shape[1]:
        raise ValueError("Kraus operators must be square")
    if any(operator.shape != shape for operator in operators):
        raise ValueError("all Kraus operators must have the same shape")

    dimension = shape[0]
    result = np.zeros((dimension * dimension, dimension * dimension), dtype=complex)
    for operator in operators:
        result += np.kron(operator.conj(), operator)
    return result


def _hermiticity_residual(matrix: np.ndarray) -> float:
    scale = max(1.0, float(np.linalg.norm(matrix)))
    return float(np.linalg.norm(matrix - matrix.conj().T)) / scale


def cp_map_certificate(
    superoperator: np.ndarray,
    *,
    tolerance: float = 1e-10,
) -> CompletePositivityCertificate:
    """Test complete positivity by the Choi criterion."""

    if tolerance < 0.0:
        raise ValueError("tolerance must be nonnegative")
    dimension = _operator_dimension(np.asarray(superoperator))
    choi = liouville_to_choi(
        superoperator,
        operator_dimension=dimension,
    )
    residual = _hermiticity_residual(choi)
    hermitian_choi = 0.5 * (choi + choi.conj().T)
    minimum = float(np.linalg.eigvalsh(hermitian_choi)[0])
    return CompletePositivityCertificate(
        operator_dimension=dimension,
        hermiticity_residual=residual,
        minimum_eigenvalue=minimum,
        is_completely_positive=(
            residual <= tolerance and minimum >= -tolerance
        ),
    )


def _orthogonal_complement_to_identity(dimension: int) -> np.ndarray:
    identity_vector = np.eye(dimension, dtype=complex).reshape(-1, order="F")
    identity_vector /= np.linalg.norm(identity_vector)
    complement = null_space(identity_vector.conj().reshape(1, -1))
    if complement.shape != (dimension * dimension, dimension * dimension - 1):
        raise RuntimeError("failed to construct the conditional Choi subspace")
    return complement


def conditional_cp_certificate(
    generator: np.ndarray,
    *,
    tolerance: float = 1e-10,
) -> ConditionalCompletePositivityCertificate:
    """Test the conditional Choi criterion for a CP-semigroup generator.

    Trace preservation is not imposed.  The criterion is positivity of the
    Choi matrix on the subspace orthogonal to ``vec(I)`` together with
    Hermiticity preservation.
    """

    if tolerance < 0.0:
        raise ValueError("tolerance must be nonnegative")
    dimension = _operator_dimension(np.asarray(generator))
    choi = liouville_to_choi(
        generator,
        operator_dimension=dimension,
    )
    residual = _hermiticity_residual(choi)
    hermitian_choi = 0.5 * (choi + choi.conj().T)
    complement = _orthogonal_complement_to_identity(dimension)
    conditional = complement.conj().T @ hermitian_choi @ complement
    conditional = 0.5 * (conditional + conditional.conj().T)
    minimum = float(np.linalg.eigvalsh(conditional)[0])
    conditional_norm = float(np.linalg.norm(conditional))
    return ConditionalCompletePositivityCertificate(
        operator_dimension=dimension,
        hermiticity_residual=residual,
        minimum_conditional_eigenvalue=minimum,
        conditional_block_norm=conditional_norm,
        is_conditionally_completely_positive=(
            residual <= tolerance and minimum >= -tolerance
        ),
    )


def fock_tensorization_order(
    *,
    modes: int,
    ket_modes: Sequence[int],
) -> tuple[int, ...]:
    """Map column-major operator indices to occupation-basis Fock states."""

    if modes <= 0 or modes % 2:
        raise ValueError("modes must be a positive even integer")
    ket = tuple(int(mode) for mode in ket_modes)
    if len(ket) != modes // 2 or len(set(ket)) != len(ket):
        raise ValueError("ket_modes must contain exactly half the modes")
    if any(mode < 0 or mode >= modes for mode in ket):
        raise ValueError("ket_modes contains an out-of-range mode")
    bra = tuple(mode for mode in range(modes) if mode not in set(ket))
    half_dimension = 1 << (modes // 2)

    def embed(mask: int, selected_modes: Sequence[int]) -> int:
        return sum(
            ((mask >> local_index) & 1) << physical_mode
            for local_index, physical_mode in enumerate(selected_modes)
        )

    return tuple(
        embed(ket_state, ket) | embed(bra_state, bra)
        for bra_state in range(half_dimension)
        for ket_state in range(half_dimension)
    )


def tensorize_fock_operator(
    operator: np.ndarray,
    *,
    ket_modes: Sequence[int],
    fock_transform: np.ndarray | None = None,
) -> np.ndarray:
    """Apply a fixed Fock transform and occupation-to-operator tensorization."""

    matrix = np.asarray(operator, dtype=complex)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("operator must be square")
    fock_dimension = matrix.shape[0]
    if fock_dimension <= 1 or fock_dimension & (fock_dimension - 1):
        raise ValueError("operator dimension must be a power of two")
    modes = fock_dimension.bit_length() - 1

    if fock_transform is not None:
        transform = np.asarray(fock_transform, dtype=complex)
        if transform.shape != matrix.shape:
            raise ValueError("fock_transform must match the operator shape")
        inverse = np.linalg.inv(transform)
        matrix = transform @ matrix @ inverse

    order = fock_tensorization_order(modes=modes, ket_modes=ket_modes)
    return matrix[np.ix_(order, order)]
