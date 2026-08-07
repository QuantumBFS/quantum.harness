"""Exact clean-Ising cylinder transfer matrix and critical dispersion.

The symmetric row transfer matrix is

    T(s, s') = exp[K/2 E_h(s) + K sum_i s_i s'_i + K/2 E_h(s')],

where ``E_h(s)=sum_i s_i s_{i+1}`` contains exactly ``L`` directed
periodic bond slots.  In particular, ``L=2`` has two parallel horizontal
bonds, matching the stage-0 convention.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from numpy.typing import NDArray

from .conventions import ISING_K_CRITICAL
from .exact import spin_rows

FloatArray = NDArray[np.float64]

# Catalan's constant and the exact critical square-lattice Ising value
# phi_infinity = lim_L log(lambda_0(L))/L.
CATALAN = 0.91596559417721901505460351493238411077
CRITICAL_PHI_INFINITY = 0.5 * math.log(2.0) + 2.0 * CATALAN / math.pi


@dataclass(frozen=True)
class DominantEigenpair:
    log_eigenvalue: float
    relative_residual: float
    iterations: int


def symmetric_transfer_matrix(
    circumference: int, coupling: float = ISING_K_CRITICAL
) -> FloatArray:
    """Construct the positive symmetric row transfer matrix explicitly."""

    if circumference < 2:
        raise ValueError("circumference must be at least two")
    if not math.isfinite(coupling):
        raise ValueError("coupling must be finite")
    rows = spin_rows(circumference).astype(np.float64)
    horizontal = np.sum(
        rows * np.roll(rows, shift=-1, axis=1),
        axis=1,
        dtype=np.float64,
    )
    vertical = rows @ rows.T
    log_transfer = coupling * (
        0.5 * horizontal[:, None]
        + vertical
        + 0.5 * horizontal[None, :]
    )
    return np.exp(log_transfer)


def explicit_dominant_eigenpair(
    circumference: int,
    coupling: float = ISING_K_CRITICAL,
    *,
    tolerance: float = 2.0e-14,
    max_iterations: int = 20_000,
) -> DominantEigenpair:
    """Find the Perron root of the explicit matrix by residual-controlled power iteration."""

    if tolerance <= 0.0 or not math.isfinite(tolerance):
        raise ValueError("tolerance must be finite and positive")
    if max_iterations < 1:
        raise ValueError("max_iterations must be positive")
    transfer = symmetric_transfer_matrix(circumference, coupling)
    vector = np.ones(transfer.shape[0], dtype=np.float64)
    vector /= np.linalg.norm(vector)

    eigenvalue = math.nan
    relative_residual = math.inf
    for iteration in range(1, max_iterations + 1):
        product = transfer @ vector
        vector = product / np.linalg.norm(product)
        product = transfer @ vector
        eigenvalue = float(vector @ product)
        relative_residual = float(
            np.linalg.norm(product - eigenvalue * vector) / abs(eigenvalue)
        )
        if relative_residual <= tolerance:
            return DominantEigenpair(
                log_eigenvalue=math.log(eigenvalue),
                relative_residual=relative_residual,
                iterations=iteration,
            )
    raise RuntimeError(
        "dominant-eigenvalue iteration did not converge: "
        f"L={circumference}, residual={relative_residual:.3e}"
    )


def critical_gamma(momentum: FloatArray | float) -> FloatArray:
    """Critical Ising single-particle dispersion, gamma(q) >= 0."""

    values = np.asarray(momentum, dtype=np.float64)
    return 2.0 * np.arcsinh(np.abs(np.sin(0.5 * values)))


def critical_log_dominant_eigenvalue(circumference: int) -> float:
    """Return Onsager's dominant antiperiodic-sector eigenvalue at ``Kc``.

    For even ``L``, the Perron root uses momenta ``(2r+1) pi/L``:

        log lambda_0 = L log(2)/2 + sum_r gamma(q_r)/2.
    """

    if circumference < 2 or circumference % 2:
        raise ValueError("the frozen clean benchmark uses even L >= 2")
    momenta = (
        (2 * np.arange(circumference, dtype=np.float64) + 1.0)
        * math.pi
        / circumference
    )
    return float(
        0.5 * circumference * math.log(2.0)
        + 0.5 * np.sum(critical_gamma(momenta), dtype=np.float64)
    )


def critical_phi(circumference: int) -> float:
    """Positive log-partition density ``log(lambda_0)/L``."""

    return critical_log_dominant_eigenvalue(circumference) / circumference


def direct_torus_log_partition(
    circumference: int,
    length: int,
    coupling: float = ISING_K_CRITICAL,
) -> float:
    """Directly enumerate a tiny periodic-by-periodic lattice."""

    if circumference < 2 or length < 2:
        raise ValueError("direct torus enumeration requires L,N >= 2")
    spin_count = circumference * length
    if spin_count > 24:
        raise ValueError("direct torus enumeration is limited to 24 spins")
    integers = np.arange(1 << spin_count, dtype=np.uint64)[:, None]
    bits = (
        integers
        >> np.arange(spin_count, dtype=np.uint64)[None, :]
    ) & 1
    spins = (2 * bits.astype(np.int8) - 1).reshape(
        -1, length, circumference
    )
    energy = np.sum(
        spins * np.roll(spins, shift=-1, axis=2),
        axis=(1, 2),
        dtype=np.float64,
    )
    energy += np.sum(
        spins * np.roll(spins, shift=-1, axis=1),
        axis=(1, 2),
        dtype=np.float64,
    )
    logs = coupling * energy
    offset = float(np.max(logs))
    return offset + math.log(float(np.sum(np.exp(logs - offset))))


def transfer_torus_log_partition(
    circumference: int,
    length: int,
    coupling: float = ISING_K_CRITICAL,
) -> float:
    """Compute ``log Tr(T**length)`` for the explicit symmetric matrix."""

    if length < 2:
        raise ValueError("length must be at least two")
    transfer = symmetric_transfer_matrix(circumference, coupling)
    eigenvalues = np.linalg.eigvalsh(transfer)
    powered = np.power(eigenvalues, length)
    partition = float(np.sum(powered))
    if partition <= 0.0:
        raise FloatingPointError("finite torus partition function is not positive")
    return math.log(partition)
