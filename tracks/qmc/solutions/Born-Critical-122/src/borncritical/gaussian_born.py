"""Born-rule trajectories for the weakly self-dual Majorana circuit.

The circuit is the one in Eq. (11) of arXiv:2502.14034.  Every local
involution ``A`` (``X_j`` or ``Z_j Z_{j+1}``) has two normalized Kraus
branches

    K_s = exp(s * beta * A / 2) / sqrt(2 cosh(beta)),  s = +/-1.

For a state with ``a = <A>``, the branch probability is therefore

    p_s = (1 + s tanh(beta) a) / 2.

The state is represented by the real antisymmetric Majorana correlator
``G[p,q] = <i gamma_p gamma_q>``.  A branch update is a rank-two
Gaussian update and does not require a Hilbert space of dimension ``2**L``.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from .conventions import SELFDUAL_THETA, selfdual_couplings

FloatMatrix = NDArray[np.float64]
IntVector = NDArray[np.int8]


class RandomSource(Protocol):
    def random(self) -> float: ...


def plus_state_correlator(size: int) -> FloatMatrix:
    """Return ``G`` for the even-parity product state ``|+>**size``."""

    if size < 2 or size % 2:
        raise ValueError("the periodic vacuum circuit requires even size >= 2")
    correlator = np.zeros((2 * size, 2 * size), dtype=np.float64)
    for site in range(size):
        correlator[2 * site, 2 * site + 1] = 1.0
        correlator[2 * site + 1, 2 * site] = -1.0
    return correlator


def purity_residual(correlator: FloatMatrix) -> float:
    """Maximum residual of antisymmetry and the pure-state identity G^2=-I."""

    value = np.asarray(correlator, dtype=np.float64)
    identity = np.eye(value.shape[0], dtype=np.float64)
    return max(
        float(np.max(np.abs(value + value.T))),
        float(np.max(np.abs(value @ value + identity))),
    )


def branch_probability(
    correlator: FloatMatrix,
    left: int,
    right: int,
    outcome: int,
    strength: float,
    *,
    observable_sign: int = 1,
) -> float:
    """Return the normalized probability of one weak-parity outcome."""

    if outcome not in (-1, 1):
        raise ValueError("outcome must be -1 or +1")
    if observable_sign not in (-1, 1):
        raise ValueError("observable_sign must be -1 or +1")
    expectation = observable_sign * float(correlator[left, right])
    probability = 0.5 * (1.0 + outcome * math.tanh(strength) * expectation)
    if probability < -1e-15 or probability > 1.0 + 1e-15:
        raise FloatingPointError(f"invalid conditional probability {probability}")
    return min(1.0, max(0.0, probability))


def apply_branch(
    correlator: FloatMatrix,
    left: int,
    right: int,
    outcome: int,
    strength: float,
    *,
    observable_sign: int = 1,
) -> tuple[FloatMatrix, float, float]:
    """Apply one branch and return ``(updated_G, log_probability, log_norm)``.

    ``log_norm`` is the change of the logarithm of the norm under the
    *unnormalized* gate ``exp(outcome*strength*A/2)``.  The normalized
    Kraus probability differs by the known POVM factor ``2*cosh(strength)``.
    """

    value = np.asarray(correlator, dtype=np.float64)
    if value.ndim != 2 or value.shape[0] != value.shape[1]:
        raise ValueError("correlator must be square")
    if not (0 <= left < value.shape[0] and 0 <= right < value.shape[0]):
        raise IndexError("Majorana index outside correlator")
    if left == right:
        raise ValueError("Majorana indices must be distinct")
    probability = branch_probability(
        value,
        left,
        right,
        outcome,
        strength,
        observable_sign=observable_sign,
    )
    if probability <= 0.0:
        raise FloatingPointError("attempted a zero-probability Born branch")

    effective_outcome = outcome * observable_sign
    q = math.tanh(strength)
    selected = float(value[left, right])
    denominator = 1.0 + effective_outcome * q * selected
    attenuation = math.sqrt(max(0.0, 1.0 - q * q)) / denominator

    updated = value.copy()
    other = np.ones(value.shape[0], dtype=bool)
    other[[left, right]] = False
    indices = np.flatnonzero(other)

    # Bilinears sharing one Majorana anticommute with the measured parity.
    updated[left, indices] = attenuation * value[left, indices]
    updated[indices, left] = -updated[left, indices]
    updated[right, indices] = attenuation * value[right, indices]
    updated[indices, right] = -updated[right, indices]

    # Disjoint bilinears commute.  Wick's theorem turns the four-point
    # function into this rank-two outer-product correction.
    correction = (
        np.outer(value[left, indices], value[right, indices])
        - np.outer(value[right, indices], value[left, indices])
    )
    updated[np.ix_(indices, indices)] = (
        value[np.ix_(indices, indices)]
        - effective_outcome * q * correction / denominator
    )

    selected_updated = (selected + effective_outcome * q) / denominator
    updated[left, right] = selected_updated
    updated[right, left] = -selected_updated
    np.fill_diagonal(updated, 0.0)
    updated = 0.5 * (updated - updated.T)

    log_probability = math.log(probability)
    log_norm = 0.5 * (
        log_probability + math.log(2.0 * math.cosh(strength))
    )
    return updated, log_probability, log_norm


def sample_branch(
    correlator: FloatMatrix,
    left: int,
    right: int,
    strength: float,
    rng: RandomSource,
    *,
    observable_sign: int = 1,
) -> tuple[FloatMatrix, int, float, float]:
    probability_plus = branch_probability(
        correlator,
        left,
        right,
        1,
        strength,
        observable_sign=observable_sign,
    )
    outcome = 1 if float(rng.random()) < probability_plus else -1
    updated, log_probability, log_norm = apply_branch(
        correlator,
        left,
        right,
        outcome,
        strength,
        observable_sign=observable_sign,
    )
    return updated, outcome, log_probability, log_norm


@dataclass(frozen=True)
class BornLayer:
    s: IntVector
    t: IntVector
    log_probability: float
    log_norm: float
    max_probability_normalization_error: float
    purity_residual: float


@dataclass
class GaussianBornCircuit:
    """A normalized Born trajectory in the even, periodic-spin sector."""

    size: int
    theta: float = SELFDUAL_THETA

    def __post_init__(self) -> None:
        if self.size < 2 or self.size % 2:
            raise ValueError("size must be even and at least two")
        beta, beta_prime = selfdual_couplings(self.theta)
        self.beta = beta
        self.beta_prime = beta_prime
        self.correlator = plus_state_correlator(self.size)
        self.total_log_probability = 0.0
        self.total_log_norm = 0.0
        self.layers = 0
        self.previous_s: IntVector | None = None

    def _z_pair(self, site: int) -> tuple[int, int, int]:
        if site < self.size - 1:
            return 2 * site + 1, 2 * (site + 1), 1
        # Z_{L-1} Z_0 = -P i gamma_{2L-1} gamma_0 and P=+1.
        return 2 * self.size - 1, 0, -1

    def sample_layer(self, rng: RandomSource) -> BornLayer:
        s = np.empty(self.size, dtype=np.int8)
        t = np.empty(self.size, dtype=np.int8)
        layer_log_probability = 0.0
        layer_log_norm = 0.0
        max_normalization_error = 0.0

        # Fixed manifest order: all spatial ZZ gates, then all onsite X gates.
        for site in range(self.size):
            left, right, sign = self._z_pair(site)
            plus = branch_probability(
                self.correlator,
                left,
                right,
                1,
                self.beta,
                observable_sign=sign,
            )
            minus = branch_probability(
                self.correlator,
                left,
                right,
                -1,
                self.beta,
                observable_sign=sign,
            )
            max_normalization_error = max(
                max_normalization_error, abs(plus + minus - 1.0)
            )
            (
                self.correlator,
                s[site],
                log_probability,
                log_norm,
            ) = sample_branch(
                self.correlator,
                left,
                right,
                self.beta,
                rng,
                observable_sign=sign,
            )
            layer_log_probability += log_probability
            layer_log_norm += log_norm

        for site in range(self.size):
            left, right = 2 * site, 2 * site + 1
            plus = branch_probability(
                self.correlator, left, right, 1, self.beta_prime
            )
            minus = branch_probability(
                self.correlator, left, right, -1, self.beta_prime
            )
            max_normalization_error = max(
                max_normalization_error, abs(plus + minus - 1.0)
            )
            (
                self.correlator,
                t[site],
                log_probability,
                log_norm,
            ) = sample_branch(
                self.correlator, left, right, self.beta_prime, rng
            )
            layer_log_probability += log_probability
            layer_log_norm += log_norm

        self.total_log_probability += layer_log_probability
        self.total_log_norm += layer_log_norm
        self.layers += 1
        residual = purity_residual(self.correlator)
        return BornLayer(
            s=s,
            t=t,
            log_probability=layer_log_probability,
            log_norm=layer_log_norm,
            max_probability_normalization_error=max_normalization_error,
            purity_residual=residual,
        )


class MajoranaTransferQR:
    """QR-stabilized single-particle transfer evolution for one trajectory."""

    def __init__(self, size: int, qr_interval: int = 1) -> None:
        if size < 2 or size % 2:
            raise ValueError("size must be even and at least two")
        if qr_interval < 1:
            raise ValueError("qr_interval must be positive")
        self.size = size
        self.mode_count = 2 * size
        self.qr_interval = qr_interval
        self.basis = np.eye(self.mode_count, dtype=np.float64)
        self.log_diagonal = np.zeros(self.mode_count, dtype=np.float64)
        self.layers_since_qr = 0
        self.qr_count = 0
        self.maximum_orthogonality_error = 0.0

    def apply_gate(
        self,
        left: int,
        right: int,
        effective_outcome: int,
        strength: float,
    ) -> None:
        if effective_outcome not in (-1, 1):
            raise ValueError("effective_outcome must be -1 or +1")
        left_row = self.basis[left].copy()
        right_row = self.basis[right].copy()
        cosine = math.cosh(strength)
        sine = effective_outcome * math.sinh(strength)
        self.basis[left] = cosine * left_row + sine * right_row
        self.basis[right] = sine * left_row + cosine * right_row

    def finish_layer(self) -> None:
        self.layers_since_qr += 1
        if self.layers_since_qr >= self.qr_interval:
            self.stabilize()

    def stabilize(self) -> None:
        if self.layers_since_qr == 0:
            return
        q_matrix, r_matrix = np.linalg.qr(self.basis)
        diagonal = np.diag(r_matrix).copy()
        signs = np.where(diagonal < 0.0, -1.0, 1.0)
        q_matrix *= signs[None, :]
        diagonal *= signs
        if np.any(diagonal <= 0.0) or not np.all(np.isfinite(diagonal)):
            raise FloatingPointError("singular or non-finite Majorana QR diagonal")
        self.log_diagonal += np.log(diagonal)
        self.basis = q_matrix
        error = float(
            np.max(
                np.abs(
                    self.basis.T @ self.basis
                    - np.eye(self.mode_count, dtype=np.float64)
                )
            )
        )
        self.maximum_orthogonality_error = max(
            self.maximum_orthogonality_error, error
        )
        self.qr_count += 1
        self.layers_since_qr = 0

    def exponents(self, layers: int) -> FloatMatrix:
        if layers < 1:
            raise ValueError("layers must be positive")
        self.stabilize()
        return np.sort(self.log_diagonal / layers)[::-1]


def vortex_indicators(
    previous_s: IntVector,
    current_s: IntVector,
    previous_t: IntVector,
    current_t: IntVector,
) -> tuple[NDArray[np.bool_], NDArray[np.bool_]]:
    """Return temporal ``e`` and ``m`` kinks.

    This is the circuit gauge of Fig. 6(a): an m vortex terminates a temporal
    kink of the ZZ evolution sign, and an e vortex terminates a temporal kink
    of the X evolution sign.  These are gauge-invariant vortex observables,
    unlike the fraction of negative gates.
    """

    previous = np.asarray(previous_s, dtype=np.int8)
    spatial = np.asarray(current_s, dtype=np.int8)
    previous_temporal = np.asarray(previous_t, dtype=np.int8)
    temporal = np.asarray(current_t, dtype=np.int8)
    if not (
        previous.shape
        == spatial.shape
        == previous_temporal.shape
        == temporal.shape
    ):
        raise ValueError("s/t rows must have identical shapes")
    m_vortices = previous * spatial == -1
    e_vortices = previous_temporal * temporal == -1
    return e_vortices, m_vortices
