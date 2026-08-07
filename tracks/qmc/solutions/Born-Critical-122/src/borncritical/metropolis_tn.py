"""Independent dense transfer contraction and local-record Metropolis sampler."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from numpy.typing import NDArray

from .conventions import SELFDUAL_THETA, selfdual_couplings


@dataclass(frozen=True)
class MetropolisResult:
    records: NDArray[np.int8]
    log_probabilities: NDArray[np.float64]
    log_norms: NDArray[np.float64]
    acceptance_rate: float
    burnin_log_probability: NDArray[np.float64]


class DenseRecordContraction:
    """Contract a fixed weak-measurement record without Gaussian covariance code."""

    def __init__(
        self, size: int, layers: int, theta: float = SELFDUAL_THETA
    ) -> None:
        if size < 2 or size > 12:
            raise ValueError("dense contraction requires 2 <= size <= 12")
        if layers < 1:
            raise ValueError("layers must be positive")
        self.size = size
        self.layers = layers
        self.variable_count = 2 * size * layers
        self.beta, self.beta_prime = selfdual_couplings(theta)
        basis = np.arange(1 << size, dtype=np.uint64)
        self.zz_eigenvalues = []
        self.flip_permutations = []
        for site in range(size):
            left = ((basis >> np.uint64(site)) & np.uint64(1)).astype(np.int8)
            right = (
                (basis >> np.uint64((site + 1) % size)) & np.uint64(1)
            ).astype(np.int8)
            self.zz_eigenvalues.append(1.0 - 2.0 * (left ^ right))
            self.flip_permutations.append(
                (basis ^ np.uint64(1 << site)).astype(np.int64)
            )
        self._normalization_log = layers * size * (
            math.log(2.0 * math.cosh(self.beta))
            + math.log(2.0 * math.cosh(self.beta_prime))
        )

    def log_norm(self, bits: NDArray[np.integer] | tuple[int, ...]) -> float:
        record = np.asarray(bits, dtype=np.int8)
        if record.shape != (self.variable_count,) or np.any(
            (record != 0) & (record != 1)
        ):
            raise ValueError("record must be a binary vector of fixed length")
        state = np.full(
            1 << self.size, 1.0 / math.sqrt(float(1 << self.size)), dtype=float
        )
        cursor = 0
        cosine = math.cosh(0.5 * self.beta_prime)
        sine = math.sinh(0.5 * self.beta_prime)
        for _ in range(self.layers):
            for site in range(self.size):
                outcome = 1.0 if record[cursor] == 0 else -1.0
                cursor += 1
                state *= np.exp(
                    0.5 * outcome * self.beta * self.zz_eigenvalues[site]
                )
            for site in range(self.size):
                outcome = 1.0 if record[cursor] == 0 else -1.0
                cursor += 1
                previous = state
                state = (
                    cosine * previous
                    + outcome * sine * previous[self.flip_permutations[site]]
                )
        squared_norm = float(state @ state)
        if squared_norm <= 0.0 or not math.isfinite(squared_norm):
            raise FloatingPointError("non-positive or non-finite record norm")
        return 0.5 * math.log(squared_norm)

    def log_probability(
        self, bits: NDArray[np.integer] | tuple[int, ...]
    ) -> float:
        return 2.0 * self.log_norm(bits) - self._normalization_log


def local_metropolis(
    evaluator: DenseRecordContraction,
    *,
    seed: int,
    burnin_sweeps: int,
    samples: int,
    sweeps_per_sample: int = 1,
) -> MetropolisResult:
    if burnin_sweeps < 1 or samples < 2 or sweeps_per_sample < 1:
        raise ValueError("invalid Metropolis lengths")
    rng = np.random.default_rng(seed)
    record = rng.integers(
        0, 2, size=evaluator.variable_count, dtype=np.int8
    )
    log_norm = evaluator.log_norm(record)
    accepted = attempted = 0
    burn_trace = np.empty(burnin_sweeps, dtype=float)

    def sweep() -> None:
        nonlocal log_norm, accepted, attempted
        for index in rng.permutation(evaluator.variable_count):
            record[index] ^= np.int8(1)
            proposed = evaluator.log_norm(record)
            log_acceptance = 2.0 * (proposed - log_norm)
            attempted += 1
            if log_acceptance >= 0.0 or math.log(float(rng.random())) < log_acceptance:
                log_norm = proposed
                accepted += 1
            else:
                record[index] ^= np.int8(1)

    for sweep_index in range(burnin_sweeps):
        sweep()
        burn_trace[sweep_index] = (
            2.0 * log_norm - evaluator._normalization_log
        )

    records = np.empty(
        (samples, evaluator.variable_count), dtype=np.int8
    )
    log_norms = np.empty(samples, dtype=float)
    for sample in range(samples):
        for _ in range(sweeps_per_sample):
            sweep()
        records[sample] = record
        log_norms[sample] = log_norm
    return MetropolisResult(
        records=records,
        log_probabilities=2.0 * log_norms - evaluator._normalization_log,
        log_norms=log_norms,
        acceptance_rate=accepted / attempted,
        burnin_log_probability=burn_trace,
    )


def integrated_autocorrelation_time(values: NDArray[np.floating]) -> float:
    """Initial-positive-sequence estimate, in units of stored samples."""

    data = np.asarray(values, dtype=float)
    if data.ndim != 1 or data.size < 8 or not np.all(np.isfinite(data)):
        raise ValueError("autocorrelation input must contain >=8 finite values")
    centered = data - np.mean(data)
    variance_sum = float(centered @ centered)
    if variance_sum == 0.0:
        return 0.5
    tau = 0.5
    maximum_lag = min(data.size // 4, 1000)
    for lag in range(1, maximum_lag + 1):
        rho = float(centered[:-lag] @ centered[lag:] / variance_sum)
        if rho <= 0.0:
            break
        tau += rho
        if lag > 6.0 * tau:
            break
    return max(0.5, tau)
