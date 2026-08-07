"""Dense Hilbert-space oracle for short weakly self-dual Born circuits."""

from __future__ import annotations

from dataclasses import dataclass
import itertools
import math

import numpy as np
from numpy.typing import NDArray

from .conventions import SELFDUAL_THETA, selfdual_couplings
from .majorana_oracle import (
    PAULI_X,
    PAULI_Z,
    _site_operator,
)

ComplexVector = NDArray[np.complex128]


@dataclass(frozen=True)
class CircuitOutcome:
    bits: tuple[int, ...]
    probability: float
    gaussian_probability: float
    log_norm: float


def _plus_state(size: int) -> ComplexVector:
    state = np.ones(1 << size, dtype=np.complex128)
    return state / math.sqrt(float(1 << size))


def _involution_gate(
    state: ComplexVector,
    involution: NDArray[np.complex128],
    outcome: int,
    strength: float,
) -> tuple[ComplexVector, float, float]:
    unnormalized = (
        math.cosh(0.5 * strength) * state
        + outcome * math.sinh(0.5 * strength) * (involution @ state)
    )
    squared_norm = float(np.vdot(unnormalized, unnormalized).real)
    probability = squared_norm / (2.0 * math.cosh(strength))
    return unnormalized / math.sqrt(squared_norm), probability, 0.5 * math.log(
        squared_norm
    )


def apply_record_dense(
    size: int,
    layers: int,
    bits: tuple[int, ...],
    *,
    theta: float = SELFDUAL_THETA,
) -> tuple[float, float]:
    """Return normalized Born probability and unnormalized circuit log norm."""

    if len(bits) != 2 * size * layers:
        raise ValueError("record length must equal 2*size*layers")
    beta, beta_prime = selfdual_couplings(theta)
    state = _plus_state(size)
    probability = 1.0
    log_norm = 0.0
    cursor = 0
    for _layer in range(layers):
        for site in range(size):
            outcome = 1 if bits[cursor] == 0 else -1
            cursor += 1
            zz = _site_operator(size, site, PAULI_Z) @ _site_operator(
                size, (site + 1) % size, PAULI_Z
            )
            state, conditional, increment = _involution_gate(
                state, zz, outcome, beta
            )
            probability *= conditional
            log_norm += increment
        for site in range(size):
            outcome = 1 if bits[cursor] == 0 else -1
            cursor += 1
            x = _site_operator(size, site, PAULI_X)
            state, conditional, increment = _involution_gate(
                state, x, outcome, beta_prime
            )
            probability *= conditional
            log_norm += increment
    return probability, log_norm


def apply_record_gaussian(
    size: int,
    layers: int,
    bits: tuple[int, ...],
    *,
    theta: float = SELFDUAL_THETA,
) -> tuple[float, float]:
    """Evaluate the same fixed record with Gaussian conditional updates."""

    from .gaussian_born import GaussianBornCircuit, apply_branch

    if len(bits) != 2 * size * layers:
        raise ValueError("record length must equal 2*size*layers")
    circuit = GaussianBornCircuit(size=size, theta=theta)
    log_probability = 0.0
    log_norm = 0.0
    cursor = 0
    for _layer in range(layers):
        for site in range(size):
            outcome = 1 if bits[cursor] == 0 else -1
            cursor += 1
            left, right, sign = circuit._z_pair(site)
            circuit.correlator, lp, ln = apply_branch(
                circuit.correlator,
                left,
                right,
                outcome,
                circuit.beta,
                observable_sign=sign,
            )
            log_probability += lp
            log_norm += ln
        for site in range(size):
            outcome = 1 if bits[cursor] == 0 else -1
            cursor += 1
            circuit.correlator, lp, ln = apply_branch(
                circuit.correlator,
                2 * site,
                2 * site + 1,
                outcome,
                circuit.beta_prime,
            )
            log_probability += lp
            log_norm += ln
    return math.exp(log_probability), log_norm


def enumerate_circuit_distribution(
    size: int,
    layers: int,
    *,
    vacuum_only: bool = False,
    max_variables: int = 20,
) -> tuple[CircuitOutcome, ...]:
    variable_count = 2 * size * layers
    if variable_count > max_variables:
        raise ValueError(
            f"{variable_count} variables exceeds max_variables={max_variables}"
        )
    raw: list[CircuitOutcome] = []
    for bits in itertools.product((0, 1), repeat=variable_count):
        if vacuum_only:
            first_s = bits[:size]
            if sum(first_s) % 2:
                continue
        dense_probability, dense_log_norm = apply_record_dense(size, layers, bits)
        gaussian_probability, _ = apply_record_gaussian(size, layers, bits)
        raw.append(
            CircuitOutcome(
                bits=bits,
                probability=dense_probability,
                gaussian_probability=gaussian_probability,
                log_norm=dense_log_norm,
            )
        )
    normalization = math.fsum(item.probability for item in raw)
    gaussian_normalization = math.fsum(
        item.gaussian_probability for item in raw
    )
    return tuple(
        CircuitOutcome(
            bits=item.bits,
            probability=item.probability / normalization,
            gaussian_probability=item.gaussian_probability
            / gaussian_normalization,
            log_norm=item.log_norm,
        )
        for item in raw
    )
