"""Streaming block statistics for weakly self-dual Born trajectories."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import time

import numpy as np
from numpy.typing import NDArray

from .gaussian_born import (
    GaussianBornCircuit,
    MajoranaTransferQR,
    branch_probability,
    purity_residual,
    sample_branch,
    vortex_indicators,
)


@dataclass(frozen=True)
class SelfDualBlock:
    block: int
    rows: int
    spacetime_sublayers: int
    shannon_rate: float
    rao_blackwell_shannon_rate: float
    log_norm_rate: float
    e_density: float
    m_density: float
    maximum_exponent: float
    minimum_positive_exponent: float
    probability_normalization_error: float
    covariance_purity_residual: float
    qr_orthogonality_error: float


@dataclass(frozen=True)
class SelfDualRun:
    size: int
    replica: int
    seed: int
    burnin_rows: int
    measurement_rows: int
    block_rows: int
    qr_interval: int
    elapsed_seconds: float
    rows_per_second: float
    blocks: tuple[SelfDualBlock, ...]
    maximum_probability_normalization_error: float
    maximum_covariance_purity_residual: float
    maximum_qr_orthogonality_error: float

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["blocks"] = [asdict(block) for block in self.blocks]
        return payload


def _sample_layer_with_qr(
    circuit: GaussianBornCircuit,
    transfer: MajoranaTransferQR,
    rng: np.random.Generator,
) -> tuple[NDArray[np.int8], NDArray[np.int8], float, float, float, float]:
    s = np.empty(circuit.size, dtype=np.int8)
    t = np.empty(circuit.size, dtype=np.int8)
    log_probability = 0.0
    log_norm = 0.0
    normalization_error = 0.0
    conditional_entropy = 0.0
    for site in range(circuit.size):
        left, right, sign = circuit._z_pair(site)
        plus = branch_probability(
            circuit.correlator,
            left,
            right,
            1,
            circuit.beta,
            observable_sign=sign,
        )
        minus = branch_probability(
            circuit.correlator,
            left,
            right,
            -1,
            circuit.beta,
            observable_sign=sign,
        )
        normalization_error = max(normalization_error, abs(plus + minus - 1.0))
        conditional_entropy -= sum(
            probability * math.log(probability)
            for probability in (plus, minus)
            if probability > 0.0
        )
        circuit.correlator, outcome, lp, ln = sample_branch(
            circuit.correlator,
            left,
            right,
            circuit.beta,
            rng,
            observable_sign=sign,
        )
        s[site] = outcome
        log_probability += lp
        log_norm += ln
        transfer.apply_gate(left, right, outcome * sign, circuit.beta)
    for site in range(circuit.size):
        left, right = 2 * site, 2 * site + 1
        plus = branch_probability(
            circuit.correlator, left, right, 1, circuit.beta_prime
        )
        minus = branch_probability(
            circuit.correlator, left, right, -1, circuit.beta_prime
        )
        normalization_error = max(normalization_error, abs(plus + minus - 1.0))
        conditional_entropy -= sum(
            probability * math.log(probability)
            for probability in (plus, minus)
            if probability > 0.0
        )
        circuit.correlator, outcome, lp, ln = sample_branch(
            circuit.correlator, left, right, circuit.beta_prime, rng
        )
        t[site] = outcome
        log_probability += lp
        log_norm += ln
        transfer.apply_gate(left, right, outcome, circuit.beta_prime)
    transfer.finish_layer()
    return (
        s,
        t,
        log_probability,
        log_norm,
        conditional_entropy,
        normalization_error,
    )


def run_selfdual_trajectory(
    *,
    size: int,
    replica: int,
    seed: int,
    burnin_rows: int,
    measurement_rows: int,
    block_rows: int,
    qr_interval: int,
) -> SelfDualRun:
    if burnin_rows < 0 or measurement_rows < 1:
        raise ValueError("invalid trajectory lengths")
    if block_rows < 1 or measurement_rows % block_rows:
        raise ValueError("measurement_rows must be divisible by block_rows")
    rng = np.random.default_rng(seed)
    circuit = GaussianBornCircuit(size=size)
    transfer = MajoranaTransferQR(size=size, qr_interval=qr_interval)
    previous_s: NDArray[np.int8] | None = None
    previous_t: NDArray[np.int8] | None = None
    started = time.perf_counter()

    for _ in range(burnin_rows):
        (
            previous_s,
            previous_t,
            _lp,
            _ln,
            _entropy,
            _error,
        ) = _sample_layer_with_qr(circuit, transfer, rng)
    # Lyapunov rates and physical accumulators begin after burn-in.
    transfer = MajoranaTransferQR(size=size, qr_interval=qr_interval)

    blocks: list[SelfDualBlock] = []
    maximum_probability_error = 0.0
    maximum_purity_error = 0.0
    for block_index in range(measurement_rows // block_rows):
        block_log_probability = 0.0
        block_log_norm = 0.0
        block_conditional_entropy = 0.0
        e_count = 0
        m_count = 0
        probability_error = 0.0
        purity_error = 0.0
        start_layer = block_index * block_rows
        for _ in range(block_rows):
            s, t, lp, ln, entropy, error = _sample_layer_with_qr(
                circuit, transfer, rng
            )
            block_log_probability += lp
            block_log_norm += ln
            block_conditional_entropy += entropy
            probability_error = max(probability_error, error)
            purity_error = max(purity_error, purity_residual(circuit.correlator))
            if previous_s is not None and previous_t is not None:
                e_vortices, m_vortices = vortex_indicators(
                    previous_s, s, previous_t, t
                )
                e_count += int(np.count_nonzero(e_vortices))
                m_count += int(np.count_nonzero(m_vortices))
            previous_s = s
            previous_t = t
        completed_layers = start_layer + block_rows
        exponents = transfer.exponents(completed_layers)
        positive = exponents[exponents >= 0.0]
        blocks.append(
            SelfDualBlock(
                block=block_index,
                rows=block_rows,
                spacetime_sublayers=2 * block_rows,
                # One circuit cycle contains the alternating MZ and MX
                # measurement sublayers.  The paper's Ly counts sublayers.
                shannon_rate=-block_log_probability / (2 * size * block_rows),
                rao_blackwell_shannon_rate=(
                    block_conditional_entropy / (2 * size * block_rows)
                ),
                log_norm_rate=block_log_norm / (2 * size * block_rows),
                e_density=e_count / (size * block_rows),
                m_density=m_count / (size * block_rows),
                maximum_exponent=float(exponents[0]),
                minimum_positive_exponent=(
                    float(positive[-1]) if positive.size else math.nan
                ),
                probability_normalization_error=probability_error,
                covariance_purity_residual=purity_error,
                qr_orthogonality_error=transfer.maximum_orthogonality_error,
            )
        )
        maximum_probability_error = max(
            maximum_probability_error, probability_error
        )
        maximum_purity_error = max(maximum_purity_error, purity_error)

    elapsed = time.perf_counter() - started
    return SelfDualRun(
        size=size,
        replica=replica,
        seed=seed,
        burnin_rows=burnin_rows,
        measurement_rows=measurement_rows,
        block_rows=block_rows,
        qr_interval=qr_interval,
        elapsed_seconds=elapsed,
        rows_per_second=(burnin_rows + measurement_rows) / elapsed,
        blocks=tuple(blocks),
        maximum_probability_normalization_error=maximum_probability_error,
        maximum_covariance_purity_residual=maximum_purity_error,
        maximum_qr_orthogonality_error=transfer.maximum_orthogonality_error,
    )
