"""Fixed-budget physical-block confirmation statistics.

The physical block, not an individual shot, is the primary independent unit.
These functions intentionally do not implement optional stopping.  A reported
interval describes the finite frozen confirmation window; long-run apparatus
claims additionally require a justified stationarity/mixing model.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class PairedBlockObservation:
    """Two binomial batches acquired in the same physical block."""

    block_id: str
    selected_successes: int
    selected_shots: int
    baseline_successes: int
    baseline_shots: int
    order_code: str

    def __post_init__(self) -> None:
        if (
            not self.block_id
            or self.selected_shots <= 0
            or self.baseline_shots <= 0
            or not 0 <= self.selected_successes <= self.selected_shots
            or not 0 <= self.baseline_successes <= self.baseline_shots
            or self.order_code not in {"SC", "CS"}
        ):
            raise ValueError("paired block observation is invalid")

    @property
    def difference(self) -> float:
        return (
            self.selected_successes / self.selected_shots
            - self.baseline_successes / self.baseline_shots
        )


@dataclass(frozen=True)
class PairedBlockEstimate:
    n_blocks: int
    estimate: float
    standard_error: float
    confidence_level: float
    interval_low: float
    interval_high: float
    estimand: str = "finite_window_block_average_effect"


@dataclass(frozen=True)
class OverdispersionDiagnostic:
    n_batches: int
    pooled_probability: float
    pearson_statistic: float
    degrees_of_freedom: int
    dispersion_ratio: float
    p_value: float


def paired_block_estimate(
    blocks: Sequence[PairedBlockObservation],
    *,
    confidence_level: float = 0.95,
) -> PairedBlockEstimate:
    """Student-t interval over pre-randomized physical-block differences."""

    if (
        len(blocks) < 2
        or not math.isfinite(confidence_level)
        or not 0.0 < confidence_level < 1.0
    ):
        raise ValueError("paired estimate requires >=2 blocks and valid confidence")
    differences = np.asarray(
        [block.difference for block in blocks], dtype=float
    )
    estimate = float(np.mean(differences))
    standard_error = float(
        np.std(differences, ddof=1) / math.sqrt(len(differences))
    )
    if standard_error == 0.0:
        low = high = estimate
    else:
        critical = float(
            stats.t.ppf(
                0.5 + confidence_level / 2.0,
                df=len(differences) - 1,
            )
        )
        low = estimate - critical * standard_error
        high = estimate + critical * standard_error
    return PairedBlockEstimate(
        n_blocks=len(blocks),
        estimate=estimate,
        standard_error=standard_error,
        confidence_level=confidence_level,
        interval_low=float(low),
        interval_high=float(high),
    )


def block_bootstrap_interval(
    blocks: Sequence[PairedBlockObservation],
    *,
    confidence_level: float = 0.95,
    resamples: int = 9_999,
    seed: int | np.random.Generator = 0,
) -> tuple[float, float]:
    """Percentile interval from whole-block resampling.

    This requires independent or sufficiently weakly dependent blocks.  It is
    not valid for unresolved AR(1), random-walk, jump, or carryover residuals.
    """

    if (
        len(blocks) < 2
        or type(resamples) is not int
        or resamples < 100
        or not math.isfinite(confidence_level)
        or not 0.0 < confidence_level < 1.0
    ):
        raise ValueError("block bootstrap configuration is invalid")
    values = np.asarray([block.difference for block in blocks], dtype=float)
    rng = seed if isinstance(seed, np.random.Generator) else np.random.default_rng(seed)
    # Chunking keeps the real 9,999-resample confirmation bounded in memory.
    means = np.empty(resamples, dtype=float)
    chunk = 2_048
    for start in range(0, resamples, chunk):
        stop = min(resamples, start + chunk)
        indices = rng.integers(
            0, len(values), size=(stop - start, len(values))
        )
        means[start:stop] = np.mean(values[indices], axis=1)
    alpha = (1.0 - confidence_level) / 2.0
    low, high = np.quantile(means, (alpha, 1.0 - alpha))
    return float(low), float(high)


def randomization_sign_flip_pvalue(
    blocks: Sequence[PairedBlockObservation],
    *,
    alternative: str = "greater",
    monte_carlo_draws: int = 99_999,
    seed: int | np.random.Generator = 0,
) -> float:
    """Monte-Carlo paired sign-flip p-value for the sharp no-effect null."""

    if alternative not in {"greater", "less", "two-sided"}:
        raise ValueError("alternative is invalid")
    if type(monte_carlo_draws) is not int or monte_carlo_draws < 1_000:
        raise ValueError("monte_carlo_draws must be at least 1000")
    values = np.asarray([block.difference for block in blocks], dtype=float)
    if values.size < 2:
        raise ValueError("sign-flip test requires at least two blocks")
    observed = float(np.mean(values))
    rng = seed if isinstance(seed, np.random.Generator) else np.random.default_rng(seed)
    exceed = 0
    chunk = 4_096
    for start in range(0, monte_carlo_draws, chunk):
        count = min(chunk, monte_carlo_draws - start)
        signs = rng.integers(0, 2, size=(count, len(values))) * 2 - 1
        randomized = np.mean(signs * values, axis=1)
        if alternative == "greater":
            exceed += int(np.count_nonzero(randomized >= observed))
        elif alternative == "less":
            exceed += int(np.count_nonzero(randomized <= observed))
        else:
            exceed += int(
                np.count_nonzero(np.abs(randomized) >= abs(observed))
            )
    return float((exceed + 1) / (monte_carlo_draws + 1))


def binomial_overdispersion_diagnostic(
    successes: Sequence[int],
    shots: Sequence[int],
) -> OverdispersionDiagnostic:
    """Pearson extra-binomial diagnostic for exchangeable batches only."""

    success = np.asarray(successes)
    trials = np.asarray(shots)
    if (
        success.ndim != 1
        or trials.ndim != 1
        or len(success) != len(trials)
        or len(success) < 3
        or not np.issubdtype(success.dtype, np.integer)
        or not np.issubdtype(trials.dtype, np.integer)
        or np.any(trials <= 0)
        or np.any(success < 0)
        or np.any(success > trials)
    ):
        raise ValueError("binomial batches are invalid")
    pooled = float(np.sum(success) / np.sum(trials))
    degrees = len(success) - 1
    if pooled in {0.0, 1.0}:
        statistic = 0.0
        p_value = 1.0
        ratio = 0.0
    else:
        variance = trials * pooled * (1.0 - pooled)
        statistic = float(
            np.sum((success - trials * pooled) ** 2 / variance)
        )
        ratio = statistic / degrees
        p_value = float(stats.chi2.sf(statistic, df=degrees))
    return OverdispersionDiagnostic(
        n_batches=len(success),
        pooled_probability=pooled,
        pearson_statistic=statistic,
        degrees_of_freedom=degrees,
        dispersion_ratio=float(ratio),
        p_value=p_value,
    )


def lag_correlation(values: Sequence[float], *, lag: int = 1) -> float:
    """Diagnostic correlation; a non-significant value is not proof of no drift."""

    array = np.asarray(values, dtype=float)
    if (
        array.ndim != 1
        or len(array) <= lag
        or type(lag) is not int
        or lag <= 0
        or not np.all(np.isfinite(array))
    ):
        raise ValueError("lag-correlation input is invalid")
    left = array[:-lag] - np.mean(array[:-lag])
    right = array[lag:] - np.mean(array[lag:])
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return 0.0 if denominator == 0.0 else float(np.dot(left, right) / denominator)


def wilson_interval(
    successes: int,
    trials: int,
    *,
    confidence_level: float = 0.95,
) -> tuple[float, float]:
    """Wilson score interval used to evaluate Monte-Carlo acceptance rates."""

    if (
        type(successes) is not int
        or type(trials) is not int
        or not 0 <= successes <= trials
        or trials <= 0
        or not 0.0 < confidence_level < 1.0
    ):
        raise ValueError("Wilson interval inputs are invalid")
    z = float(stats.norm.ppf(0.5 + confidence_level / 2.0))
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    center = (proportion + z * z / (2.0 * trials)) / denominator
    half = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / trials
            + z * z / (4.0 * trials * trials)
        )
        / denominator
    )
    return float(center - half), float(center + half)
