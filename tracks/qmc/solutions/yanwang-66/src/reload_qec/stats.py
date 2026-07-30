"""Paired policy comparisons and multiple-testing utilities."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import binomtest


@dataclass(frozen=True)
class PairedComparison:
    shots: int
    baseline_only_failures: int
    candidate_only_failures: int
    both_failures: int
    neither_failures: int
    difference: float
    bootstrap_95_lower: float
    bootstrap_95_upper: float
    sign_test_pvalue: float

    def as_dict(self) -> dict[str, int | float]:
        return {
            "shots": self.shots,
            "baseline_only_failures": self.baseline_only_failures,
            "candidate_only_failures": self.candidate_only_failures,
            "both_failures": self.both_failures,
            "neither_failures": self.neither_failures,
            "difference": self.difference,
            "bootstrap_95_lower": self.bootstrap_95_lower,
            "bootstrap_95_upper": self.bootstrap_95_upper,
            "sign_test_pvalue": self.sign_test_pvalue,
        }


def paired_comparison(
    baseline_failure: np.ndarray,
    candidate_failure: np.ndarray,
    *,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> PairedComparison:
    baseline = np.asarray(baseline_failure, dtype=np.uint8).reshape(-1)
    candidate = np.asarray(candidate_failure, dtype=np.uint8).reshape(-1)
    if baseline.shape != candidate.shape or baseline.size == 0:
        raise ValueError("paired outcomes must have the same non-empty shape")
    if np.any(baseline > 1) or np.any(candidate > 1):
        raise ValueError("paired outcomes must be binary")
    if bootstrap_resamples < 1:
        raise ValueError("bootstrap_resamples must be positive")
    baseline_only = int(np.count_nonzero((baseline == 1) & (candidate == 0)))
    candidate_only = int(np.count_nonzero((baseline == 0) & (candidate == 1)))
    both = int(np.count_nonzero((baseline == 1) & (candidate == 1)))
    neither = int(baseline.size - baseline_only - candidate_only - both)
    probabilities = np.asarray(
        [baseline_only, baseline.size - baseline_only - candidate_only, candidate_only],
        dtype=np.float64,
    ) / baseline.size
    rng = np.random.Generator(np.random.PCG64(bootstrap_seed))
    bootstrap_counts = rng.multinomial(
        baseline.size,
        probabilities,
        size=bootstrap_resamples,
    )
    bootstrap_difference = (
        bootstrap_counts[:, 2] - bootstrap_counts[:, 0]
    ) / baseline.size
    lower, upper = np.quantile(bootstrap_difference, [0.025, 0.975])
    discordant = baseline_only + candidate_only
    pvalue = (
        1.0
        if discordant == 0
        else float(binomtest(candidate_only, discordant, 0.5).pvalue)
    )
    return PairedComparison(
        shots=int(baseline.size),
        baseline_only_failures=baseline_only,
        candidate_only_failures=candidate_only,
        both_failures=both,
        neither_failures=neither,
        difference=(candidate_only - baseline_only) / baseline.size,
        bootstrap_95_lower=float(lower),
        bootstrap_95_upper=float(upper),
        sign_test_pvalue=pvalue,
    )


def benjamini_hochberg(pvalues: np.ndarray) -> np.ndarray:
    values = np.asarray(pvalues, dtype=np.float64).reshape(-1)
    if np.any(~np.isfinite(values)) or np.any((values < 0) | (values > 1)):
        raise ValueError("p-values must be finite and inside [0,1]")
    if values.size == 0:
        return values.copy()
    order = np.argsort(values, kind="stable")
    ranked = values[order]
    adjusted_ranked = ranked * values.size / np.arange(1, values.size + 1)
    adjusted_ranked = np.minimum.accumulate(adjusted_ranked[::-1])[::-1]
    adjusted = np.empty_like(adjusted_ranked)
    adjusted[order] = np.minimum(1.0, adjusted_ranked)
    return adjusted
