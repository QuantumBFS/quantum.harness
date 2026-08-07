"""Certificates for fixed non-unitary similarity orbits.

A fixed similarity does not create a new positivity mechanism.  It does,
however, turn every already-positive auxiliary-field history into an exactly
isospectral pseudo-Hermitian history:

    B'_s = S^{-1} B_s S.

This module makes the invariance, metric, and non-uniqueness explicit so that
unconventional model mappings cannot be mistaken for new matrix theorems.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.linalg import expm


@dataclass(frozen=True)
class SimilarityHistory:
    original_product: np.ndarray
    transformed_product: np.ndarray
    original_weight: complex
    transformed_weight: complex
    conjugacy_residual: float


@dataclass(frozen=True)
class PseudoHermitianOrbit:
    hermitian_partner: np.ndarray
    nonhermitian_hamiltonian: np.ndarray
    similarity: np.ndarray
    metric: np.ndarray
    similarity_residual: float
    pseudo_hermiticity_residual: float
    similarity_condition_number: float
    metric_condition_number: float


@dataclass(frozen=True)
class StarkSimilarityModel:
    orbit: PseudoHermitianOrbit
    diagonal_partner: np.ndarray
    shift: np.ndarray
    shear_similarity: np.ndarray
    expected_local_hamiltonian: np.ndarray
    uses_fourier_partner: bool


@dataclass(frozen=True)
class StarToChainImpurityModel:
    """Fixed four-orbital Wilson/Lanczos calibration model.

    This is a standard star-to-chain mapping and therefore an ``L2``
    calibration, not a new positivity mechanism.  The orthogonal change of
    orbitals fixes the impurity orbital, so an onsite Hubbard interaction
    remains at the endpoint of the chain.
    """

    chain_hamiltonian: np.ndarray
    star_hamiltonian: np.ndarray
    chain_to_star: np.ndarray
    impurity_projector: np.ndarray
    kinetic_half_step_chain: np.ndarray
    time_step: float
    interaction: float
    hirsch_lambda: float
    hirsch_prefactor: float


def _square_matrix(matrix: np.ndarray, *, name: str) -> np.ndarray:
    candidate = np.asarray(matrix, dtype=complex)
    if candidate.ndim != 2 or candidate.shape[0] != candidate.shape[1]:
        raise ValueError(f"{name} must be square")
    if candidate.shape[0] < 1:
        raise ValueError(f"{name} must be nonempty")
    if not np.all(np.isfinite(candidate)):
        raise ValueError(f"{name} must have finite entries")
    return candidate


def _invertible_matrix(
    matrix: np.ndarray,
    *,
    name: str,
    expected_dimension: int | None = None,
) -> np.ndarray:
    candidate = _square_matrix(matrix, name=name)
    if expected_dimension is not None and candidate.shape != (
        expected_dimension,
        expected_dimension,
    ):
        raise ValueError(
            f"{name} must have shape "
            f"({expected_dimension}, {expected_dimension})"
        )
    if np.linalg.matrix_rank(candidate) != candidate.shape[0]:
        raise ValueError(f"{name} must be invertible")
    return candidate


def determinant_history_weight(factors: Sequence[np.ndarray]) -> complex:
    """Return ``det(I + B_1 ... B_L)`` for a nonempty matrix history."""

    matrices = tuple(
        _square_matrix(factor, name="history factor")
        for factor in factors
    )
    if not matrices:
        raise ValueError("at least one history factor is required")
    shape = matrices[0].shape
    if any(matrix.shape != shape for matrix in matrices):
        raise ValueError("all history factors must have the same shape")

    product = np.eye(shape[0], dtype=complex)
    for matrix in matrices:
        product = product @ matrix
    return complex(np.linalg.det(np.eye(shape[0]) + product))


def similarity_history(
    factors: Sequence[np.ndarray],
    similarity: np.ndarray,
) -> SimilarityHistory:
    """Conjugate every time slice and certify determinant-weight invariance."""

    matrices = tuple(
        _square_matrix(factor, name="history factor")
        for factor in factors
    )
    if not matrices:
        raise ValueError("at least one history factor is required")
    shape = matrices[0].shape
    if any(matrix.shape != shape for matrix in matrices):
        raise ValueError("all history factors must have the same shape")
    transform = _invertible_matrix(
        similarity,
        name="similarity",
        expected_dimension=shape[0],
    )
    inverse = np.linalg.inv(transform)

    original_product = np.eye(shape[0], dtype=complex)
    transformed_product = np.eye(shape[0], dtype=complex)
    for matrix in matrices:
        original_product = original_product @ matrix
        transformed_product = (
            transformed_product @ inverse @ matrix @ transform
        )

    expected = inverse @ original_product @ transform
    identity = np.eye(shape[0], dtype=complex)
    return SimilarityHistory(
        original_product=original_product,
        transformed_product=transformed_product,
        original_weight=complex(np.linalg.det(identity + original_product)),
        transformed_weight=complex(
            np.linalg.det(identity + transformed_product)
        ),
        conjugacy_residual=float(
            np.linalg.norm(transformed_product - expected)
        ),
    )


def pseudo_hermitian_orbit(
    hermitian_partner: np.ndarray,
    similarity: np.ndarray,
) -> PseudoHermitianOrbit:
    """Return ``H=S^{-1}hS`` and its positive metric ``eta=S^dagger S``."""

    partner = _square_matrix(
        hermitian_partner,
        name="hermitian_partner",
    )
    if not np.allclose(partner, partner.conj().T, atol=1e-12):
        raise ValueError("hermitian_partner must be Hermitian")
    transform = _invertible_matrix(
        similarity,
        name="similarity",
        expected_dimension=partner.shape[0],
    )
    inverse = np.linalg.inv(transform)
    nonhermitian = inverse @ partner @ transform
    metric = transform.conj().T @ transform

    similarity_residual = np.linalg.norm(
        transform @ nonhermitian @ inverse - partner
    )
    pseudo_residual = np.linalg.norm(
        nonhermitian.conj().T @ metric - metric @ nonhermitian
    )
    return PseudoHermitianOrbit(
        hermitian_partner=partner,
        nonhermitian_hamiltonian=nonhermitian,
        similarity=transform,
        metric=metric,
        similarity_residual=float(similarity_residual),
        pseudo_hermiticity_residual=float(pseudo_residual),
        similarity_condition_number=float(np.linalg.cond(transform)),
        metric_condition_number=float(np.linalg.cond(metric)),
    )


def tensor_square_similarity_history(
    base_factors: Sequence[np.ndarray],
    lifted_similarity: np.ndarray,
) -> SimilarityHistory:
    """Conjugate an arbitrary-depth tensor-square history by one fixed map."""

    bases = tuple(
        _square_matrix(factor, name="base factor")
        for factor in base_factors
    )
    if not bases:
        raise ValueError("at least one base factor is required")
    shape = bases[0].shape
    if any(matrix.shape != shape for matrix in bases):
        raise ValueError("all base factors must have the same shape")
    lifted = tuple(np.kron(matrix, matrix) for matrix in bases)
    return similarity_history(lifted, lifted_similarity)


def _discrete_fourier(dimension: int) -> np.ndarray:
    indices = np.arange(dimension)
    phase = np.exp(
        2j * np.pi * np.outer(indices, indices) / float(dimension)
    )
    return phase / np.sqrt(float(dimension))


def stark_similarity_model(
    *,
    dimension: int,
    level_spacing: float,
    shear: float,
    fourier_partner: bool = False,
) -> StarkSimilarityModel:
    """Build an exact local unidirectional Stark chain.

    With ``D=spacing*diag(0,...,n-1)``, the nilpotent right shift ``N``, and
    ``S=exp(shear*N)``,

        S^{-1} D S = D - shear*spacing*N.

    The right-hand side has only onsite terms and one-way nearest-neighbour
    hopping, while its positive metric ``S^dagger S`` is dense.  If
    ``fourier_partner`` is true, a Fourier unitary is folded into the
    similarity.  This produces a dense Hermitian partner without changing the
    non-Hermitian chain or its metric.  The optional form is deliberately a
    non-uniqueness calibration, not a new physical result.
    """

    if dimension < 2:
        raise ValueError("dimension must be at least two")
    if not np.isfinite(level_spacing) or level_spacing == 0.0:
        raise ValueError("level_spacing must be finite and nonzero")
    if not np.isfinite(shear):
        raise ValueError("shear must be finite")

    diagonal = level_spacing * np.diag(np.arange(dimension, dtype=float))
    shift = np.diag(np.ones(dimension - 1), k=1)
    shear_similarity = expm(shear * shift)
    expected_local = diagonal - shear * level_spacing * shift

    if fourier_partner:
        fourier = _discrete_fourier(dimension)
        partner = fourier @ diagonal @ fourier.conj().T
        similarity = fourier @ shear_similarity
    else:
        partner = diagonal
        similarity = shear_similarity

    orbit = pseudo_hermitian_orbit(partner, similarity)
    return StarkSimilarityModel(
        orbit=orbit,
        diagonal_partner=diagonal.astype(complex),
        shift=shift.astype(complex),
        shear_similarity=shear_similarity.astype(complex),
        expected_local_hamiltonian=expected_local.astype(complex),
        uses_fourier_partner=fourier_partner,
    )


def build_star_to_chain_impurity_mwe(
    *,
    time_step: float = 0.2,
    interaction: float = 4.0,
) -> StarToChainImpurityModel:
    """Build the fixed four-orbital star-to-chain impurity MWE.

    The chain has negative nearest-neighbour hopping, hence
    ``-h_chain`` is a tridiagonal Metzler generator.  Its exponential is
    totally nonnegative.  A real orthogonal matrix that fixes orbital zero
    converts the chain into a dense Hermitian star bath without moving the
    impurity interaction.

    The returned Hirsch parameter obeys

    ``cosh(lambda) = exp(time_step * interaction / 2)``.

    This executable example is the standard Wilson/Lanczos construction.  It
    demonstrates a physical interface to the TN proof, but is not evidence
    for a novel sign-free Hamiltonian class.
    """

    if not np.isfinite(time_step) or time_step <= 0.0:
        raise ValueError("time_step must be finite and positive")
    if not np.isfinite(interaction) or interaction < 0.0:
        raise ValueError("interaction must be finite and nonnegative")

    chain = np.asarray(
        [
            [0.0, -1.0, 0.0, 0.0],
            [-1.0, 0.4, -0.8, 0.0],
            [0.0, -0.8, 0.9, -0.6],
            [0.0, 0.0, -0.6, 1.5],
        ]
    )
    bath_rotation = np.asarray(
        [
            [1.0 / np.sqrt(3.0), 1.0 / np.sqrt(2.0), 1.0 / np.sqrt(6.0)],
            [1.0 / np.sqrt(3.0), -1.0 / np.sqrt(2.0), 1.0 / np.sqrt(6.0)],
            [1.0 / np.sqrt(3.0), 0.0, -2.0 / np.sqrt(6.0)],
        ]
    )
    chain_to_star = np.zeros((4, 4), dtype=float)
    chain_to_star[0, 0] = 1.0
    chain_to_star[1:, 1:] = bath_rotation
    star = chain_to_star @ chain @ chain_to_star.T
    projector = np.diag([1.0, 0.0, 0.0, 0.0])
    hirsch_lambda = float(
        np.arccosh(np.exp(time_step * interaction / 2.0))
    )
    hirsch_prefactor = float(
        0.5 * np.exp(-time_step * interaction / 4.0)
    )

    return StarToChainImpurityModel(
        chain_hamiltonian=chain,
        star_hamiltonian=star,
        chain_to_star=chain_to_star,
        impurity_projector=projector,
        kinetic_half_step_chain=expm(-0.5 * time_step * chain),
        time_step=float(time_step),
        interaction=float(interaction),
        hirsch_lambda=hirsch_lambda,
        hirsch_prefactor=hirsch_prefactor,
    )


def star_to_chain_hirsch_branch(
    model: StarToChainImpurityModel,
    *,
    field: int,
    spin: int,
    basis: str = "chain",
) -> np.ndarray:
    """Return one symmetric-Trotter Hirsch branch for one spin flavor.

    ``spin=+1`` and ``spin=-1`` denote the two Hubbard flavors.  In the chain
    basis every branch is totally nonnegative.  The star-basis branch is its
    fixed orthogonal conjugate and is generally dense.
    """

    if field not in (-1, 1):
        raise ValueError("field must be -1 or 1")
    if spin not in (-1, 1):
        raise ValueError("spin must be -1 or 1")
    if basis not in ("chain", "star"):
        raise ValueError("basis must be 'chain' or 'star'")

    field_factor = np.eye(4)
    field_factor[0, 0] = np.exp(
        spin * model.hirsch_lambda * field
    )
    half_step = model.kinetic_half_step_chain
    chain_branch = half_step @ field_factor @ half_step
    if basis == "chain":
        return chain_branch
    transform = model.chain_to_star
    return transform @ chain_branch @ transform.T


def star_to_chain_hirsch_history(
    model: StarToChainImpurityModel,
    fields: Sequence[int],
    *,
    spin: int,
) -> SimilarityHistory:
    """Certify one complete Hirsch history in chain and star bases."""

    field_values = tuple(int(field) for field in fields)
    if not field_values:
        raise ValueError("at least one Hirsch field is required")
    factors = tuple(
        star_to_chain_hirsch_branch(
            model,
            field=field,
            spin=spin,
            basis="chain",
        )
        for field in field_values
    )
    return similarity_history(factors, model.chain_to_star.T)
