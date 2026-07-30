"""Grassmannian diagnostics and covariance-deformed Geometric-ETH models."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
from scipy.linalg import solve_sylvester


def _validated_row_isometry(
    rows: np.ndarray,
    tolerance: float = 1e-9,
) -> np.ndarray:
    matrix = np.asarray(rows, dtype=complex)
    if matrix.ndim != 2 or matrix.shape[0] < 1:
        raise ValueError("rows must be a nonempty two-dimensional matrix")
    if matrix.shape[0] > matrix.shape[1]:
        raise ValueError("a row isometry cannot have more rows than columns")
    residual = np.linalg.norm(
        matrix @ matrix.conj().T - np.eye(matrix.shape[0])
    )
    if residual > float(tolerance):
        raise ValueError("rows do not form an isometry")
    return matrix


def row_projector(rows: np.ndarray) -> np.ndarray:
    """Return the ambient projector onto a whitened channel row space."""

    matrix = _validated_row_isometry(rows)
    projector = matrix.conj().T @ matrix
    return 0.5 * (projector + projector.conj().T)


def mean_projector_anisotropy(
    row_isometries: Iterable[np.ndarray],
) -> dict[str, Any]:
    """Measure the departure of the ensemble mean projector from Haar."""

    matrices = [_validated_row_isometry(rows) for rows in row_isometries]
    if not matrices:
        raise ValueError("at least one row isometry is required")
    shape = matrices[0].shape
    if any(matrix.shape != shape for matrix in matrices):
        raise ValueError("all row isometries must have equal shape")
    rank, dimension = shape
    mean_projector = np.mean(
        [row_projector(matrix) for matrix in matrices],
        axis=0,
    )
    isotropic = (rank / dimension) * np.eye(dimension)
    difference = mean_projector - isotropic
    eigenvalues = np.linalg.eigvalsh(mean_projector)
    return {
        "rank": rank,
        "ambient_dimension": dimension,
        "samples": len(matrices),
        "trace": float(np.trace(mean_projector).real),
        "relative_frobenius": float(
            np.linalg.norm(difference) / np.linalg.norm(isotropic)
        ),
        "spectral_spread": float(eigenvalues[-1] - eigenvalues[0]),
        "minimum_eigenvalue": float(eigenvalues[0]),
        "maximum_eigenvalue": float(eigenvalues[-1]),
        "mean_projector": mean_projector,
    }


def coordinate_participation(rows: np.ndarray) -> dict[str, float]:
    """Return the effective number of ambient coordinates used by a row space."""

    projector = row_projector(rows)
    weights = np.diag(projector).real
    rank = float(np.sum(weights))
    denominator = float(np.sum(weights * weights))
    if denominator <= 0.0:
        raise RuntimeError("projector diagonal has zero quadratic weight")
    effective = rank * rank / denominator
    return {
        "effective_coordinates": effective,
        "fraction": effective / projector.shape[0],
    }


def polarization_imbalance(rows: np.ndarray) -> float:
    """Return normalized weight imbalance between the two channel halves."""

    projector = row_projector(rows)
    dimension = projector.shape[0]
    if dimension % 2:
        raise ValueError("polarization requires an even ambient dimension")
    half = dimension // 2
    plus = float(np.trace(projector[:half, :half]).real)
    minus = float(np.trace(projector[half:, half:]).real)
    rank = plus + minus
    return (plus - minus) / rank


def frame_overlap(first: np.ndarray, second: np.ndarray) -> float:
    """Return ``Tr(P_first P_second)`` without forming ambient projectors."""

    left = _validated_row_isometry(first)
    right = _validated_row_isometry(second)
    if left.shape != right.shape:
        raise ValueError("row isometries must have equal shape")
    overlap = left @ right.conj().T
    return float(np.linalg.norm(overlap) ** 2)


def haar_frame_overlap_mean(rank: int, dimension: int) -> float:
    """Return the exact mean frame overlap of independent Haar projectors."""

    rows = int(rank)
    columns = int(dimension)
    if rows < 1 or columns < rows:
        raise ValueError("require 1 <= rank <= dimension")
    return rows * rows / columns


def principal_angles(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """Return principal angles between two equal-dimensional row spaces."""

    left = _validated_row_isometry(first)
    right = _validated_row_isometry(second)
    if left.shape != right.shape:
        raise ValueError("row isometries must have equal shape")
    singular_values = np.linalg.svd(
        left @ right.conj().T,
        compute_uv=False,
    )
    return np.arccos(np.clip(singular_values, 0.0, 1.0))


def entry_fourth_ratio(row_isometries: Iterable[np.ndarray]) -> float:
    """Return ``E|Y_ia|^4 / E|Y_ia|^2^2`` over an isometry ensemble."""

    matrices = [_validated_row_isometry(rows) for rows in row_isometries]
    if not matrices:
        raise ValueError("at least one row isometry is required")
    squared = np.concatenate(
        [np.abs(matrix).ravel() ** 2 for matrix in matrices]
    )
    second = float(np.mean(squared))
    fourth = float(np.mean(squared * squared))
    return fourth / (second * second)


def regularize_covariance(
    covariance: np.ndarray,
    floor_fraction: float = 1e-3,
) -> np.ndarray:
    """Return a positive covariance with a scale-relative eigenvalue floor."""

    matrix = np.asarray(covariance, dtype=complex)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("covariance must be square")
    hermitian = 0.5 * (matrix + matrix.conj().T)
    values, vectors = np.linalg.eigh(hermitian)
    scale = float(values[-1])
    if scale <= 0.0 or values[0] < -1e-10 * scale:
        raise ValueError("covariance must be positive semidefinite")
    fraction = float(floor_fraction)
    if not 0.0 < fraction <= 1.0:
        raise ValueError("floor_fraction must lie in (0,1]")
    floored = np.maximum(values, fraction * scale)
    regularized = (vectors * floored[None, :]) @ vectors.conj().T
    trace = float(np.trace(regularized).real)
    return regularized * (matrix.shape[0] / trace)


def covariance_deformed_row_isometry(
    rank: int,
    covariance: np.ndarray,
    rng: np.random.Generator,
    floor_fraction: float = 1e-3,
) -> np.ndarray:
    """Sample an elliptical Gaussian row space and whiten its left metric."""

    regularized = regularize_covariance(
        covariance,
        floor_fraction=floor_fraction,
    )
    dimension = regularized.shape[0]
    rows = int(rank)
    if rows < 1 or rows > dimension:
        raise ValueError("require 1 <= rank <= covariance dimension")
    values, vectors = np.linalg.eigh(regularized)
    gaussian = (
        rng.normal(size=(rows, dimension))
        + 1j * rng.normal(size=(rows, dimension))
    ) / np.sqrt(2.0)
    channels = (
        gaussian * np.sqrt(values)[None, :]
    ) @ vectors.conj().T
    gram = channels @ channels.conj().T
    gram_values, gram_vectors = np.linalg.eigh(
        0.5 * (gram + gram.conj().T)
    )
    if gram_values[0] <= 0.0:
        raise RuntimeError("elliptical channel Gram matrix is singular")
    inverse_sqrt = (
        gram_vectors * (gram_values ** -0.5)[None, :]
    ) @ gram_vectors.conj().T
    row_isometry = inverse_sqrt @ channels
    _validated_row_isometry(row_isometry, tolerance=1e-8)
    return row_isometry


def covariance_deformed_row_isometries(
    rank: int,
    covariance: np.ndarray,
    samples: int,
    rng: np.random.Generator,
    floor_fraction: float = 1e-3,
) -> list[np.ndarray]:
    """Sample several elliptical row spaces with one covariance factorization."""

    regularized = regularize_covariance(
        covariance,
        floor_fraction=floor_fraction,
    )
    dimension = regularized.shape[0]
    rows = int(rank)
    count = int(samples)
    if rows < 1 or rows > dimension or count < 1:
        raise ValueError("require 1 <= rank <= dimension and samples >= 1")
    values, vectors = np.linalg.eigh(regularized)
    square_root_right = np.sqrt(values)[:, None] * vectors.conj().T
    result: list[np.ndarray] = []
    for _ in range(count):
        gaussian = (
            rng.normal(size=(rows, dimension))
            + 1j * rng.normal(size=(rows, dimension))
        ) / np.sqrt(2.0)
        channels = gaussian @ square_root_right
        gram = channels @ channels.conj().T
        gram_values, gram_vectors = np.linalg.eigh(
            0.5 * (gram + gram.conj().T)
        )
        if gram_values[0] <= 0.0:
            raise RuntimeError("elliptical channel Gram matrix is singular")
        inverse_sqrt = (
            gram_vectors * (gram_values ** -0.5)[None, :]
        ) @ gram_vectors.conj().T
        row_isometry = inverse_sqrt @ channels
        _validated_row_isometry(row_isometry, tolerance=1e-8)
        result.append(row_isometry)
    return result


def covariance_deformed_rows(
    rank: int,
    covariance: np.ndarray,
    samples: int,
    rng: np.random.Generator,
    floor_fraction: float = 1e-3,
):
    """Yield covariance-deformed row isometries without retaining the ensemble."""

    regularized = regularize_covariance(
        covariance,
        floor_fraction=floor_fraction,
    )
    dimension = regularized.shape[0]
    rows = int(rank)
    count = int(samples)
    if rows < 1 or rows > dimension or count < 1:
        raise ValueError("require 1 <= rank <= dimension and samples >= 1")
    values, vectors = np.linalg.eigh(regularized)
    square_root_right = np.sqrt(values)[:, None] * vectors.conj().T
    for _ in range(count):
        gaussian = (
            rng.normal(size=(rows, dimension))
            + 1j * rng.normal(size=(rows, dimension))
        ) / np.sqrt(2.0)
        channels = gaussian @ square_root_right
        gram = channels @ channels.conj().T
        gram_values, gram_vectors = np.linalg.eigh(
            0.5 * (gram + gram.conj().T)
        )
        if gram_values[0] <= 0.0:
            raise RuntimeError("elliptical channel Gram matrix is singular")
        inverse_sqrt = (
            gram_vectors * (gram_values ** -0.5)[None, :]
        ) @ gram_vectors.conj().T
        row_isometry = inverse_sqrt @ channels
        _validated_row_isometry(row_isometry, tolerance=1e-8)
        yield row_isometry


def covariance_first_order_variation(
    gaussian: np.ndarray,
    perturbation: np.ndarray,
    channel_form: np.ndarray,
) -> dict[str, np.ndarray]:
    """Return the exact first variation at ``C=I+epsilon*K``.

    The derivative of the inverse square root is fixed by its Sylvester
    equation, so no commutativity between ``G G^dagger`` and
    ``G K G^dagger`` is assumed.
    """

    G = np.asarray(gaussian, dtype=complex)
    K = np.asarray(perturbation, dtype=complex)
    J = np.asarray(channel_form, dtype=complex)
    if G.ndim != 2 or G.shape[0] > G.shape[1]:
        raise ValueError("gaussian must have shape rank x dimension")
    dimension = G.shape[1]
    if K.shape != (dimension, dimension):
        raise ValueError("perturbation shape disagrees with gaussian")
    if J.shape != (dimension, dimension):
        raise ValueError("channel form shape disagrees with gaussian")
    K = 0.5 * (K + K.conj().T)
    A = G @ G.conj().T
    values, vectors = np.linalg.eigh(0.5 * (A + A.conj().T))
    if values[0] <= 0.0:
        raise ValueError("gaussian matrix must have full row rank")
    square_root = (
        vectors * np.sqrt(values)[None, :]
    ) @ vectors.conj().T
    inverse_sqrt = (
        vectors * (values ** -0.5)[None, :]
    ) @ vectors.conj().T
    B = G @ K @ G.conj().T
    sylvester_source = -inverse_sqrt @ B @ inverse_sqrt
    delta_inverse_sqrt = solve_sylvester(
        square_root,
        square_root,
        sylvester_source,
    )
    Y = inverse_sqrt @ G
    delta_Y = (
        delta_inverse_sqrt @ G
        + 0.5 * inverse_sqrt @ G @ K
    )
    omega = Y @ J @ Y.conj().T
    delta_omega = (
        delta_Y @ J @ Y.conj().T
        + Y @ J @ delta_Y.conj().T
    )
    return {
        "Y": Y,
        "delta_Y": delta_Y,
        "omega": 0.5 * (omega + omega.conj().T),
        "delta_omega": 0.5
        * (delta_omega + delta_omega.conj().T),
        "delta_inverse_sqrt": delta_inverse_sqrt,
    }
