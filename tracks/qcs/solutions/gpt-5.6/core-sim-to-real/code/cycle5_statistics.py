"""Frozen statistical utilities for Challenge-113 cycle 5.

The functions in this module operate on truth-cell summaries.  Nested
finite-shot replicates must be aggregated before calling the bootstrap
functions; treating replicates as independent truths would understate
uncertainty.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.stats import beta


@dataclass(frozen=True)
class CertificationResult:
    """One-sided exact binomial target-certificate result."""

    successes: int
    shots: int
    confidence: float
    estimated_infidelity: float
    upper_infidelity: float
    target_infidelity: float
    certified: bool


def clopper_pearson_upper_failures(
    failures: int,
    shots: int,
    *,
    confidence: float = 0.995,
) -> float:
    """Return the one-sided exact upper bound on a binomial failure rate.

    For zero observed failures, the Beta quantile reduces to
    ``1 - (1-confidence)**(1/shots)``.  A full-failure observation has upper
    bound one.
    """

    if not isinstance(failures, (int, np.integer)):
        raise TypeError("failures must be an integer")
    if not isinstance(shots, (int, np.integer)):
        raise TypeError("shots must be an integer")
    if shots <= 0:
        raise ValueError("shots must be positive")
    if failures < 0 or failures > shots:
        raise ValueError("failures must lie in [0, shots]")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie in (0, 1)")
    if failures == shots:
        return 1.0
    return float(beta.ppf(confidence, failures + 1, shots - failures))


def certify_target_from_counts(
    successes: int,
    shots: int,
    *,
    target_infidelity: float = 1e-3,
    confidence: float = 0.995,
) -> CertificationResult:
    """Certify a target using only observed binomial counts."""

    if not isinstance(successes, (int, np.integer)):
        raise TypeError("successes must be an integer")
    if successes < 0 or successes > shots:
        raise ValueError("successes must lie in [0, shots]")
    if not 0.0 < target_infidelity < 1.0:
        raise ValueError("target_infidelity must lie in (0, 1)")
    failures = shots - successes
    upper = clopper_pearson_upper_failures(
        failures, shots, confidence=confidence
    )
    return CertificationResult(
        successes=int(successes),
        shots=int(shots),
        confidence=float(confidence),
        estimated_infidelity=float(failures / shots),
        upper_infidelity=upper,
        target_infidelity=float(target_infidelity),
        certified=bool(upper <= target_infidelity),
    )


def counts_from_sampled_fidelity(
    sampled_fidelity: float,
    shots: int,
    *,
    tolerance: float = 1e-9,
) -> int:
    """Recover the integer success count from a binomial sample mean.

    This is permitted only for values produced as ``successes / shots``.
    Non-grid values are rejected rather than silently rounded.
    """

    if not np.isfinite(sampled_fidelity):
        raise ValueError("sampled_fidelity must be finite")
    if sampled_fidelity < 0.0 or sampled_fidelity > 1.0:
        raise ValueError("sampled_fidelity must lie in [0, 1]")
    if shots <= 0:
        raise ValueError("shots must be positive")
    successes = int(round(float(sampled_fidelity) * shots))
    reconstructed = successes / shots
    if abs(reconstructed - float(sampled_fidelity)) > tolerance:
        raise ValueError(
            "sampled_fidelity is not compatible with an integer binomial count"
        )
    return successes


def aggregate_nested_replicates(
    rows: Iterable[Mapping[str, Any]],
    *,
    truth_keys: Sequence[str],
    value_key: str,
    reducer: Callable[[np.ndarray], float] = np.mean,
) -> list[dict[str, Any]]:
    """Aggregate replicate-level values to independent truth-cell values."""

    grouped: dict[tuple[Any, ...], list[float]] = {}
    for row in rows:
        key = tuple(row[name] for name in truth_keys)
        grouped.setdefault(key, []).append(float(row[value_key]))
    output: list[dict[str, Any]] = []
    for key, values in sorted(grouped.items(), key=lambda item: repr(item[0])):
        arr = np.asarray(values, dtype=float)
        output.append(
            {
                **dict(zip(truth_keys, key, strict=True)),
                value_key: float(reducer(arr)),
                "nested_replicates": int(arr.size),
            }
        )
    return output


def stratified_truth_bootstrap(
    rows: Sequence[Mapping[str, Any]],
    *,
    value: Callable[[Sequence[Mapping[str, Any]]], float],
    stratum_key: str = "family",
    samples: int = 20_000,
    seed: int = 260650,
    confidence: float = 0.95,
) -> dict[str, float | int]:
    """Bootstrap independent truth cells while preserving stratum sizes."""

    if not rows:
        raise ValueError("rows cannot be empty")
    if samples <= 0:
        raise ValueError("samples must be positive")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie in (0, 1)")

    strata: dict[Any, list[Mapping[str, Any]]] = {}
    for row in rows:
        strata.setdefault(row[stratum_key], []).append(row)

    rng = np.random.default_rng(seed)
    draws = np.empty(samples, dtype=float)
    for index in range(samples):
        resample: list[Mapping[str, Any]] = []
        for group in strata.values():
            choices = rng.integers(0, len(group), size=len(group))
            resample.extend(group[int(choice)] for choice in choices)
        draws[index] = float(value(resample))

    alpha = 1.0 - confidence
    return {
        "estimate": float(value(rows)),
        "lower": float(np.quantile(draws, alpha / 2.0)),
        "upper": float(np.quantile(draws, 1.0 - alpha / 2.0)),
        "confidence": float(confidence),
        "bootstrap_samples": int(samples),
        "independent_truth_cells": int(len(rows)),
        "strata": int(len(strata)),
        "seed": int(seed),
    }


def _smoke() -> None:
    zero_failure = certify_target_from_counts(32768, 32768)
    assert zero_failure.certified
    assert 0.0 < zero_failure.upper_infidelity < 1e-3

    targetish = certify_target_from_counts(32768 - 33, 32768)
    assert not targetish.certified
    assert targetish.upper_infidelity > 1e-3

    recovered = counts_from_sampled_fidelity(32760 / 32768, 32768)
    assert recovered == 32760

    rows = [
        {"family": "a", "truth": 1, "value": 0.0},
        {"family": "a", "truth": 1, "value": 1.0},
        {"family": "a", "truth": 2, "value": 1.0},
        {"family": "a", "truth": 2, "value": 1.0},
    ]
    truth_rows = aggregate_nested_replicates(
        rows, truth_keys=("family", "truth"), value_key="value"
    )
    assert len(truth_rows) == 2
    interval = stratified_truth_bootstrap(
        truth_rows,
        value=lambda sample: float(np.mean([row["value"] for row in sample])),
        samples=100,
    )
    assert interval["independent_truth_cells"] == 2


if __name__ == "__main__":
    _smoke()
    print("cycle5_statistics smoke: PASS", flush=True)

