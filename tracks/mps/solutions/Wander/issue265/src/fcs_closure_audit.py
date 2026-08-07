"""Cumulant-level audit of the one- and two-Burgers interpretations.

The functions in this module isolate two exact algebraic facts.

First, averaging a stochastic Burgers current does not produce the same
deterministic Burgers current evaluated on the averaged field.  The missing
flux is proportional to the local variance.

Second, if the two asymptotic chiral modes are independent copies with
opposite skewness, odd cumulants of their sum cancel while even cumulants add.
In particular, the excess kurtosis of the sum is one half of the single-mode
excess kurtosis.  This is stronger than spin-flip symmetry: symmetry forces
odd cumulants to vanish but does not fix the fourth cumulant.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


Array = np.ndarray


def noise_averaged_burgers_flux_defect(
    mean: Array,
    second_moment: Array,
    *,
    coupling: float = 1.0,
    chirality: int = 1,
) -> Array:
    """Return ``<j(u)> - j(<u>)`` for a quadratic Burgers current.

    For ``j(u) = chirality * coupling * u**2 / 2``, the defect is

    ``chirality * coupling * Var(u) / 2``.

    Its spatial derivative is the term omitted when a stochastic Burgers
    equation is incorrectly converted to a deterministic equation merely by
    setting the mean of the noise to zero.
    """

    if chirality not in (-1, 1):
        raise ValueError("chirality must be -1 or +1")
    mean = np.asarray(mean, dtype=float)
    second_moment = np.asarray(second_moment, dtype=float)
    if mean.shape != second_moment.shape:
        raise ValueError("mean and second_moment must have the same shape")
    variance = second_moment - mean**2
    return 0.5 * float(chirality) * float(coupling) * variance


def opposite_chirality_sum_cumulants(
    single_mode_cumulants: Sequence[float],
    *,
    observable_scale: float = 1.0,
) -> Array:
    """Cumulants of two independent, equally distributed reflected modes.

    Let ``X`` have cumulants ``kappa_n`` and let the opposite-chirality mode
    ``Y`` be an independent reflected copy, so
    ``kappa_n(Y) = (-1)**n kappa_n(X)``.  For the observable
    ``M = observable_scale * (X + Y)``,

    ``kappa_n(M) = observable_scale**n * (1 + (-1)**n) * kappa_n(X)``.

    The input sequence starts with the first cumulant.
    """

    cumulants = np.asarray(single_mode_cumulants, dtype=float)
    if cumulants.ndim != 1 or cumulants.size < 2:
        raise ValueError("Need a one-dimensional sequence with at least two cumulants")
    orders = np.arange(1, cumulants.size + 1)
    reflection_factor = 1.0 + (-1.0) ** orders
    return float(observable_scale) ** orders * reflection_factor * cumulants


def standardized_cumulants(cumulants: Sequence[float]) -> dict[str, float]:
    """Return skewness and excess kurtosis from cumulants one through four."""

    cumulants = np.asarray(cumulants, dtype=float)
    if cumulants.ndim != 1 or cumulants.size < 4:
        raise ValueError("Need cumulants through fourth order")
    variance = float(cumulants[1])
    if variance <= 0:
        raise ValueError("Second cumulant must be positive")
    return {
        "skewness": float(cumulants[2] / variance**1.5),
        "excess_kurtosis": float(cumulants[3] / variance**2),
    }


def independent_two_burgers_standardized_prediction(
    *,
    single_mode_skewness: float,
    single_mode_excess_kurtosis: float,
) -> dict[str, float]:
    """Standardized FCS prediction for two independent opposite modes.

    Equal variances and reflected distributions imply zero skewness and one
    half of the single-mode excess kurtosis.  The single-mode skewness is
    retained in the output only to make the cancellation explicit.
    """

    return {
        "single_mode_skewness": float(single_mode_skewness),
        "single_mode_excess_kurtosis": float(single_mode_excess_kurtosis),
        "combined_skewness": 0.0,
        "combined_excess_kurtosis": 0.5 * float(single_mode_excess_kurtosis),
    }


def gaussian_separation(
    prediction: float,
    observation: float,
    observation_stderr: float,
) -> float:
    """Return the signed separation in reported observational standard errors.

    This is a diagnostic rather than a full hypothesis-test statistic because
    it does not include uncertainty in the asymptotic theory or finite-time
    corrections.
    """

    if observation_stderr <= 0:
        raise ValueError("observation_stderr must be positive")
    return (float(prediction) - float(observation)) / float(observation_stderr)


def published_fcs_audit(
    *,
    baik_rains_skewness: float = 0.36,
    baik_rains_excess_kurtosis: float = 0.29,
    experimental_excess_kurtosis: float = -0.05,
    experimental_stderr: float = 0.02,
) -> dict[str, object]:
    """Assemble the rounded literature values used in the closed-loop audit.

    The defaults are the values tabulated by Rosenberg et al. (Science 2024).
    De Nardis, Gopalakrishnan and Vasseur predict that independent
    two-Burgers decoupling halves the Baik--Rains excess kurtosis.
    """

    prediction = independent_two_burgers_standardized_prediction(
        single_mode_skewness=baik_rains_skewness,
        single_mode_excess_kurtosis=baik_rains_excess_kurtosis,
    )
    separation = gaussian_separation(
        prediction["combined_excess_kurtosis"],
        experimental_excess_kurtosis,
        experimental_stderr,
    )
    experimental_interval_95 = [
        float(experimental_excess_kurtosis - 1.96 * experimental_stderr),
        float(experimental_excess_kurtosis + 1.96 * experimental_stderr),
    ]
    return {
        "baik_rains": {
            "skewness": float(baik_rains_skewness),
            "excess_kurtosis": float(baik_rains_excess_kurtosis),
        },
        "independent_two_burgers": prediction,
        "experiment": {
            "excess_kurtosis": float(experimental_excess_kurtosis),
            "stderr": float(experimental_stderr),
            "interval_95_from_reported_stderr": experimental_interval_95,
        },
        "prediction_minus_experiment_in_reported_stderr": float(separation),
        "finite_time_verdict": (
            "The independent two-Burgers FCS prediction is incompatible with "
            "the reported finite-time kurtosis; symmetry-level odd-cumulant "
            "cancellation remains valid."
        ),
        "scope_guardrail": (
            "The separation is not an asymptotic no-go theorem because the "
            "two-Burgers decoupling is itself a long-time fixed-point claim."
        ),
    }
