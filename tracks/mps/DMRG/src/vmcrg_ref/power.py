"""Fixed-five-seed power estimates for the Issue #28 pilot."""

from __future__ import annotations

from typing import Any

import numpy as np


def estimate_five_seed_power(
    pilot_effects: np.ndarray,
    pilot_chain_variances: np.ndarray,
    bootstrap_seed: int,
    *,
    replicates: int = 10_000,
) -> dict[str, Any]:
    effects = np.asarray(pilot_effects, dtype=np.float64).reshape(-1)
    variances = np.asarray(pilot_chain_variances, dtype=np.float64).reshape(-1)
    if effects.size < 2 or effects.shape != variances.shape:
        raise ValueError("power pilot requires at least two matched effect/variance values")
    if not np.all(np.isfinite(effects)) or not np.all(np.isfinite(variances)):
        raise ValueError("power pilot inputs must be finite")
    if np.any(variances < 0.0) or replicates < 1000:
        raise ValueError("power pilot variances/replicate count are invalid")

    formal_seed_count = 5
    rng = np.random.default_rng(bootstrap_seed)
    simulated_means = np.empty(replicates, dtype=np.float64)
    simulated_ci_low = np.empty(replicates, dtype=np.float64)
    simulated_ci_high = np.empty(replicates, dtype=np.float64)
    for replicate in range(replicates):
        selected = rng.integers(0, effects.size, size=formal_seed_count)
        draws = rng.normal(effects[selected], np.sqrt(variances[selected]))
        mean = float(draws.mean())
        standard_error = float(draws.std(ddof=1) / np.sqrt(formal_seed_count))
        simulated_means[replicate] = mean
        simulated_ci_low[replicate] = mean - 1.96 * standard_error
        simulated_ci_high[replicate] = mean + 1.96 * standard_error
    widths = simulated_ci_high - simulated_ci_low
    return {
        "formal_seed_count": formal_seed_count,
        "pilot_effect_mean": float(effects.mean()),
        "pilot_effect_standard_deviation": float(effects.std(ddof=1)),
        "expected_ci_width": float(widths.mean()),
        "median_ci_width": float(np.median(widths)),
        "probability_mean_below_zero": float(np.mean(simulated_means < 0.0)),
        "probability_ci_below_zero": float(np.mean(simulated_ci_high < 0.0)),
        "simulation_replicates": int(replicates),
        "bootstrap_seed": int(bootstrap_seed),
        "postformal_seed_extension_allowed": False,
        "valid_negative_outcome": (
            "direction_correct_but_confidence_interval_misses_frozen_gate"
        ),
    }
