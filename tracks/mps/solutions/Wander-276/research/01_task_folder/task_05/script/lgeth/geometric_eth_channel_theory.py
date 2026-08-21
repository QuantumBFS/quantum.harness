"""Finite-channel cumulant identities used by the Geometric-ETH theory paper.

The exact content of this module is deliberately narrower than an ETH claim.
It implements the participation number for deterministic channel weights,
the weighted fourth-cumulant prediction, and the commutant dimension of a
finite complex matrix family.  A fixed-seed Monte Carlo calculation checks
the prediction for a non-Gaussian proper-complex population without fitting
an exponent.
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray


REGISTERED_CHANNEL_COUNTS = (4, 8, 16, 32, 64)
MONTE_CARLO_SEED = 20260817
MATRIX_DRAWS = 50_000
MATRIX_SHAPE = (2, 2)
BLOCK_COUNT = 25
RELATIVE_ERROR_THRESHOLD = 0.08
ACTIVE_PROBABILITY = 0.1
SINGLE_CHANNEL_KAPPA4 = 1.0 / ACTIVE_PROBABILITY - 2.0


def _validated_weights(weights: ArrayLike) -> NDArray[np.float64]:
    raw = np.asarray(weights)
    if np.iscomplexobj(raw):
        raise ValueError("weights must be real")
    values = np.asarray(raw, dtype=float)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("weights must be a nonempty one-dimensional array")
    if not np.all(np.isfinite(values)):
        raise ValueError("weights must be finite")
    norm_squared = float(np.dot(values, values))
    if not np.isfinite(norm_squared) or norm_squared <= 0.0:
        raise ValueError("weights must have nonzero finite L2 norm")
    return values


def normalize_weights(weights: ArrayLike) -> NDArray[np.float64]:
    """Return deterministic real weights with unit Euclidean norm."""

    values = _validated_weights(weights)
    return values / np.linalg.norm(values)


def effective_channel_number(weights: ArrayLike) -> float:
    """Return ``(sum w**2)**2 / sum w**4`` for nonzero real weights."""

    values = _validated_weights(weights)
    sum_two = float(np.sum(values**2))
    sum_four = float(np.sum(values**4))
    return sum_two**2 / sum_four


def predicted_cumulant_scale(
    weights: ArrayLike,
    channel_kappa4: ArrayLike,
) -> float:
    """Return the normalized connected fourth cumulant of weighted channels.

    The formula is exact for independent centered channels with finite fourth
    moments.  The input channel cumulants may differ and may have either sign.
    """

    values = _validated_weights(weights)
    kappa = np.asarray(channel_kappa4, dtype=float)
    if kappa.shape != values.shape:
        raise ValueError("weights and channel_kappa4 must have the same shape")
    if not np.all(np.isfinite(kappa)):
        raise ValueError("channel_kappa4 must be finite")
    denominator = float(np.sum(values**2)) ** 2
    return float(np.sum(values**4 * kappa) / denominator)


def complex_second_moments(
    samples: ArrayLike,
) -> tuple[NDArray[np.complex128], NDArray[np.complex128]]:
    """Estimate centered ordinary covariance and pseudocovariance.

    The first array axis enumerates independent observations; all remaining
    axes are vectorized into one complex response coordinate.  Population
    normalization (``1 / n``) is used because these moments define the Wick
    tensor rather than an unbiased finite-sample covariance estimator.
    """

    values = np.asarray(samples, dtype=complex)
    if values.ndim == 0 or values.shape[0] < 2:
        raise ValueError("samples must contain at least two observations")
    matrix = values.reshape(values.shape[0], -1)
    if not np.all(np.isfinite(matrix.real)) or not np.all(np.isfinite(matrix.imag)):
        raise ValueError("samples must be finite")
    centered = matrix - np.mean(matrix, axis=0, keepdims=True)
    covariance = centered.conj().T @ centered / centered.shape[0]
    # The line above has indices C_ij = E[z_i^* z_j].  The convention used in
    # the theorem is E[z_i z_j^*], its transpose.  Transposition also makes the
    # implementation explicit for non-real test panels.
    covariance = covariance.T
    pseudocovariance = centered.T @ centered / centered.shape[0]
    return covariance, pseudocovariance


def standardized_complex_fourth_cumulant(samples: ArrayLike) -> float:
    r"""Estimate the complete scalar complex fourth cumulant.

    For centered scalar responses this is
    ``E|z|^4 - 2 E|z|^2^2 - |E z^2|^2``, divided by the squared variance.
    Matrix entries are centered coordinate by coordinate and then pooled.
    The pseudocovariance subtraction is retained even when the population is
    proper complex.
    """

    values = np.asarray(samples, dtype=complex)
    if values.ndim == 0 or values.shape[0] < 2:
        raise ValueError("samples must contain at least two observations")
    matrix = values.reshape(values.shape[0], -1)
    if not np.all(np.isfinite(matrix.real)) or not np.all(np.isfinite(matrix.imag)):
        raise ValueError("samples must be finite")
    centered = matrix - np.mean(matrix, axis=0, keepdims=True)
    variance = float(np.mean(np.abs(centered) ** 2))
    if not np.isfinite(variance) or variance <= 0.0:
        raise ValueError("samples must have positive finite variance")
    pseudovariance = complex(np.mean(centered**2))
    fourth_moment = float(np.mean(np.abs(centered) ** 4))
    connected = fourth_moment - 2.0 * variance**2 - abs(pseudovariance) ** 2
    return float(connected / variance**2)


def commutant_dimension(
    matrices: Sequence[ArrayLike],
    tolerance: float,
) -> int:
    """Return the complex nullity of all commutator superoperators.

    A return value of one means that only scalar matrices commute with the
    supplied generators at the stated SVD tolerance.  This is an
    irreducibility test, not a statistical or ETH test.
    """

    if not isinstance(matrices, Sequence) or len(matrices) == 0:
        raise ValueError("matrices must be a nonempty sequence")
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("tolerance must be positive and finite")
    converted = [np.asarray(matrix, dtype=complex) for matrix in matrices]
    if any(matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] for matrix in converted):
        raise ValueError("every matrix must be square")
    shape = converted[0].shape
    if any(matrix.shape != shape for matrix in converted):
        raise ValueError("matrices must have a common shape")
    if any(
        not np.all(np.isfinite(matrix.real))
        or not np.all(np.isfinite(matrix.imag))
        for matrix in converted
    ):
        raise ValueError("matrices must be finite")

    dimension = shape[0]
    identity = np.eye(dimension, dtype=complex)
    superoperators = [
        np.kron(matrix.T, identity) - np.kron(identity, matrix)
        for matrix in converted
    ]
    stacked = np.vstack(superoperators)
    singular_values = np.linalg.svd(stacked, compute_uv=False)
    rank = int(np.count_nonzero(singular_values > tolerance))
    return dimension**2 - rank


def _encoded_complex_matrix(matrix: NDArray[np.complex128]) -> dict[str, list[list[float]]]:
    return {
        "real": np.asarray(matrix.real, dtype=float).tolist(),
        "imag": np.asarray(matrix.imag, dtype=float).tolist(),
    }


def _weight_profile(name: str, count: int) -> NDArray[np.float64]:
    if name == "equal":
        return normalize_weights(np.ones(count))
    if name == "linear_unequal":
        return normalize_weights(np.linspace(0.5, 1.5, count))
    raise ValueError(f"unknown weight profile: {name}")


def _non_gaussian_channel_block(
    rng: np.random.Generator,
    draws: int,
    channel_count: int,
) -> NDArray[np.complex128]:
    shape = (draws, channel_count, *MATRIX_SHAPE)
    active = rng.random(shape) < ACTIVE_PROBABILITY
    phases = np.asarray((1.0, 1.0j, -1.0, -1.0j), dtype=complex)
    phase_index = rng.integers(0, phases.size, size=shape)
    return active * phases[phase_index] / np.sqrt(ACTIVE_PROBABILITY)


def _monte_carlo_case(
    rng: np.random.Generator,
    profile: str,
    channel_count: int,
) -> dict[str, object]:
    weights = _weight_profile(profile, channel_count)
    draws_per_block = MATRIX_DRAWS // BLOCK_COUNT
    response_blocks: list[NDArray[np.complex128]] = []
    block_estimates: list[float] = []
    for _ in range(BLOCK_COUNT):
        channels = _non_gaussian_channel_block(
            rng,
            draws=draws_per_block,
            channel_count=channel_count,
        )
        response = np.einsum("a,darc->drc", weights, channels, optimize=True)
        response_blocks.append(response)
        block_estimates.append(standardized_complex_fourth_cumulant(response))

    responses = np.concatenate(response_blocks, axis=0)
    covariance, pseudocovariance = complex_second_moments(responses)
    empirical = standardized_complex_fourth_cumulant(responses)
    channel_kappa = np.full(channel_count, SINGLE_CHANNEL_KAPPA4)
    predicted = predicted_cumulant_scale(weights, channel_kappa)
    relative_error = abs(empirical - predicted) / abs(predicted)
    block_standard_error = float(
        np.std(block_estimates, ddof=1) / np.sqrt(BLOCK_COUNT)
    )
    flattened = responses.reshape(MATRIX_DRAWS, -1)

    return {
        "weight_profile": profile,
        "channel_count": int(channel_count),
        "effective_channel_number": float(effective_channel_number(weights)),
        "sum_weight_fourth": float(np.sum(weights**4)),
        "single_channel_standardized_fourth_cumulant": float(
            SINGLE_CHANNEL_KAPPA4
        ),
        "predicted_standardized_fourth_cumulant": float(predicted),
        "empirical_standardized_fourth_cumulant": float(empirical),
        "relative_error": float(relative_error),
        "block_standard_error": block_standard_error,
        "empirical_mean_norm": float(np.linalg.norm(np.mean(flattened, axis=0))),
        "ordinary_covariance": _encoded_complex_matrix(covariance),
        "pseudocovariance": _encoded_complex_matrix(pseudocovariance),
    }


@lru_cache(maxsize=1)
def _cached_theory_audit() -> dict[str, object]:
    equal_weight_checks = []
    for count in (2, 8, 32):
        weights = normalize_weights(np.ones(count))
        equal_weight_checks.append(
            bool(
                np.isclose(effective_channel_number(weights), count)
                and np.isclose(np.sum(weights**4), 1.0 / count)
            )
        )

    unequal_weights = np.array((0.25, 0.5, 1.0))
    unequal_kappa = np.array((3.0, -2.0, 7.0))
    unequal_manual = float(
        np.sum(unequal_weights**4 * unequal_kappa)
        / np.sum(unequal_weights**2) ** 2
    )
    unequal_check = bool(
        np.isclose(
            predicted_cumulant_scale(unequal_weights, unequal_kappa),
            unequal_manual,
        )
    )

    identity = np.eye(2, dtype=complex)
    sx = np.array(((0.0, 1.0), (1.0, 0.0)), dtype=complex)
    sz = np.array(((1.0, 0.0), (0.0, -1.0)), dtype=complex)
    commutants = {
        "irreducible_pauli_pair": commutant_dimension([sx, sz], 1e-12),
        "diagonal_generator": commutant_dimension([sz], 1e-12),
        "identity_generator": commutant_dimension([identity], 1e-12),
    }

    rng = np.random.default_rng(MONTE_CARLO_SEED)
    profiles = ("equal", "linear_unequal")
    monte_carlo_cases = [
        _monte_carlo_case(rng, profile, count)
        for profile in profiles
        for count in REGISTERED_CHANNEL_COUNTS
    ]
    maximum_relative_error = max(
        float(case["relative_error"]) for case in monte_carlo_cases
    )
    checks = {
        "weight_normalization": all(equal_weight_checks),
        "exact_cumulant_additivity": unequal_check,
        "complete_complex_second_moments": all(
            "ordinary_covariance" in case and "pseudocovariance" in case
            for case in monte_carlo_cases
        ),
        "scalar_commutant_audit": commutants
        == {
            "irreducible_pauli_pair": 1,
            "diagonal_generator": 2,
            "identity_generator": 4,
        },
        "monte_carlo_relative_error": maximum_relative_error
        <= RELATIVE_ERROR_THRESHOLD,
    }

    return {
        "registered_channel_counts": list(REGISTERED_CHANNEL_COUNTS),
        "weight_profiles": list(profiles),
        "seed": MONTE_CARLO_SEED,
        "matrix_draws": MATRIX_DRAWS,
        "matrix_shape": list(MATRIX_SHAPE),
        "block_count": BLOCK_COUNT,
        "channel_population": {
            "distribution": "Bernoulli-active four-phase complex matrix entries",
            "active_probability": ACTIVE_PROBABILITY,
            "centered": True,
            "finite_fourth_moment": True,
            "variance": 1.0,
            "pseudovariance": 0.0,
            "standardized_fourth_cumulant": SINGLE_CHANNEL_KAPPA4,
        },
        "exact_checks": {
            "equal_weight_counts": [2, 8, 32],
            "equal_weight_checks": equal_weight_checks,
            "unequal_weight_prediction": unequal_check,
            "commutant_dimensions": commutants,
        },
        "monte_carlo_cases": monte_carlo_cases,
        "maximum_relative_error_threshold": RELATIVE_ERROR_THRESHOLD,
        "maximum_relative_error": float(maximum_relative_error),
        "no_exponent_fit": True,
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "claim_boundary": [
            "The inverse-effective-channel law is a finite-channel consequence of independent centered channels with finite fourth moments and variance normalization.",
            "A scalar commutant tests irreducibility; irreducibility does not imply ETH, Gaussianity, or thermalization.",
            "The calculation does not establish an asymptotic or universal Geometric-ETH ensemble.",
        ],
    }


def run_theory_audit() -> dict[str, object]:
    """Return a deterministic, JSON-serializable theorem audit."""

    return deepcopy(_cached_theory_audit())


__all__ = [
    "commutant_dimension",
    "complex_second_moments",
    "effective_channel_number",
    "normalize_weights",
    "predicted_cumulant_scale",
    "run_theory_audit",
    "standardized_complex_fourth_cumulant",
]
