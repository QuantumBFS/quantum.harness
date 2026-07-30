#!/usr/bin/env python3
"""Optional noise extensions for the Liu et al. Fig. 4 workflow.

These utilities are executable building blocks, not an assertion that Fig. 4(f)
can be independently reproduced.  The paper does not publish the pulse array,
MQDT interaction curves, decay branching ratios, or laser-noise spectra needed
for that claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.integrate import solve_ivp


SINGLE_BASIS = ("0", "1", "r", "rprime")
SINGLE_INDEX = {state: index for index, state in enumerate(SINGLE_BASIS)}


@dataclass(frozen=True)
class FullModelParameters:
    """Angular frequencies are in rad/μs and time is in μs."""

    delta_rprime: float = 2.0 * np.pi * 16.1
    blockade_rr: float = np.inf
    blockade_rrprime: float = np.inf
    blockade_rprimerprime: float = np.inf


def single_atom_hamiltonian(
    control: complex,
    delta_rprime: float,
    doppler_shift: float = 0.0,
) -> np.ndarray:
    """Four-level rotating-frame Hamiltonian.

    The raising operator is |r><1| − |r′><0|, matching the paper's
    two-atom perfect-blockade convention.
    """
    hamiltonian = np.zeros((4, 4), dtype=np.complex128)
    r = SINGLE_INDEX["r"]
    rp = SINGLE_INDEX["rprime"]
    zero = SINGLE_INDEX["0"]
    one = SINGLE_INDEX["1"]
    hamiltonian[rp, rp] = delta_rprime + doppler_shift
    hamiltonian[r, r] = doppler_shift
    hamiltonian[r, one] = control / 2.0
    hamiltonian[one, r] = np.conj(control) / 2.0
    hamiltonian[rp, zero] = -control / 2.0
    hamiltonian[zero, rp] = -np.conj(control) / 2.0
    return hamiltonian


def full_two_atom_hamiltonian(
    control: complex,
    parameters: FullModelParameters,
    doppler_shifts: tuple[float, float] = (0.0, 0.0),
) -> np.ndarray:
    """Unreduced 16-state Hamiltonian with finite pair-state blockades."""
    identity = np.eye(4, dtype=np.complex128)
    first = single_atom_hamiltonian(
        control, parameters.delta_rprime, doppler_shifts[0]
    )
    second = single_atom_hamiltonian(
        control, parameters.delta_rprime, doppler_shifts[1]
    )
    hamiltonian = np.kron(first, identity) + np.kron(identity, second)
    r = SINGLE_INDEX["r"]
    rp = SINGLE_INDEX["rprime"]
    pair_shifts = {
        (r, r): parameters.blockade_rr,
        (r, rp): parameters.blockade_rrprime,
        (rp, r): parameters.blockade_rrprime,
        (rp, rp): parameters.blockade_rprimerprime,
    }
    for (left, right), shift in pair_shifts.items():
        if np.isfinite(shift):
            hamiltonian[4 * left + right, 4 * left + right] += shift
    return hamiltonian


def distance_scaled_blockade(
    nominal_blockade: float,
    distance: float,
    nominal_distance: float = 2.0,
    exponent: int = 6,
) -> float:
    """V(R)=V(R₀)(R₀/R)^exponent; parameters must be supplied externally."""
    if distance <= 0.0:
        raise ValueError("distance must be positive")
    return nominal_blockade * (nominal_distance / distance) ** exponent


def lindblad_rhs(
    hamiltonian: np.ndarray,
    collapse_operators: tuple[np.ndarray, ...],
) -> Callable[[float, np.ndarray], np.ndarray]:
    """Return a trace-preserving Lindblad master-equation right-hand side."""
    dimension = hamiltonian.shape[0]

    def rhs(_: float, flattened: np.ndarray) -> np.ndarray:
        density = flattened.reshape(dimension, dimension)
        derivative = -1j * (hamiltonian @ density - density @ hamiltonian)
        for collapse in collapse_operators:
            rate_operator = collapse.conj().T @ collapse
            derivative += (
                collapse @ density @ collapse.conj().T
                - 0.5 * (rate_operator @ density + density @ rate_operator)
            )
        return derivative.reshape(-1)

    return rhs


def propagate_lindblad_piecewise(
    density0: np.ndarray,
    times: np.ndarray,
    hamiltonians: np.ndarray,
    collapse_operators: tuple[np.ndarray, ...] = (),
    rtol: float = 1e-9,
    atol: float = 1e-11,
) -> np.ndarray:
    """Adaptive master-equation propagation for piecewise Hamiltonians."""
    density = np.asarray(density0, dtype=np.complex128)
    output = [density.copy()]
    for index, hamiltonian in enumerate(hamiltonians):
        interval = (float(times[index]), float(times[index + 1]))
        result = solve_ivp(
            lindblad_rhs(hamiltonian, collapse_operators),
            interval,
            density.reshape(-1),
            method="DOP853",
            rtol=rtol,
            atol=atol,
        )
        if not result.success:
            raise RuntimeError(result.message)
        density = result.y[:, -1].reshape(density.shape)
        output.append(density.copy())
    return np.asarray(output)


def ou_noise(
    times: np.ndarray,
    rms: float,
    correlation_time: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Stationary Ornstein–Uhlenbeck amplitude or phase-noise trace."""
    times = np.asarray(times, dtype=float)
    noise = np.empty(len(times), dtype=float)
    noise[0] = rng.normal(0.0, rms)
    for index, interval in enumerate(np.diff(times), 1):
        decay = np.exp(-interval / correlation_time)
        noise[index] = (
            decay * noise[index - 1]
            + rms * np.sqrt(1.0 - decay**2) * rng.normal()
        )
    return noise


def noisy_controls(
    controls: np.ndarray,
    amplitude_noise: np.ndarray | float = 0.0,
    phase_noise: np.ndarray | float = 0.0,
) -> np.ndarray:
    """Apply fractional amplitude noise and phase noise to a control trace."""
    return np.asarray(controls) * (1.0 + amplitude_noise) * np.exp(
        1j * phase_noise
    )


def monte_carlo_average(
    sampler: Callable[[np.random.Generator], dict],
    simulator: Callable[[dict], float],
    samples: int,
    seed: int = 260605060,
) -> dict:
    """Generic deterministic-seed wrapper for Doppler/blockade/noise sampling."""
    rng = np.random.default_rng(seed)
    values = np.asarray(
        [simulator(sampler(rng)) for _ in range(samples)], dtype=float
    )
    return {
        "samples": int(samples),
        "mean": float(np.mean(values)),
        "standard_error": float(np.std(values, ddof=1) / np.sqrt(samples)),
        "seed": int(seed),
    }


def decay_collapse_operators(
    dimension: int,
    excited_indices: tuple[int, ...],
    branching: dict[tuple[int, int], float],
) -> tuple[np.ndarray, ...]:
    """Construct decay operators from explicitly supplied branching rates.

    ``branching[(excited, final)]`` is a rate in inverse μs.  No branching
    fractions are guessed because the paper does not report them.
    """
    operators = []
    for (excited, final), rate in branching.items():
        if excited not in excited_indices:
            raise ValueError(f"index {excited} is not a declared excited state")
        if rate < 0.0:
            raise ValueError("decay rates must be non-negative")
        collapse = np.zeros((dimension, dimension), dtype=np.complex128)
        collapse[final, excited] = np.sqrt(rate)
        operators.append(collapse)
    return tuple(operators)


def sample_gaussian_doppler(
    samples: int,
    rms_angular_shift: float,
    rng: np.random.Generator,
    correlated: bool = False,
) -> np.ndarray:
    """Sample two-atom Doppler angular shifts from a supplied rms width."""
    if samples <= 0 or rms_angular_shift < 0.0:
        raise ValueError("samples must be positive and rms shift non-negative")
    first = rng.normal(0.0, rms_angular_shift, samples)
    second = first.copy() if correlated else rng.normal(
        0.0, rms_angular_shift, samples
    )
    return np.column_stack([first, second])


def sample_blockade_from_distances(
    distances: np.ndarray,
    nominal_blockade: float,
    nominal_distance: float,
    exponent: int = 6,
) -> np.ndarray:
    """Map an externally supplied distance ensemble to a power-law blockade."""
    distances = np.asarray(distances, dtype=float)
    if np.any(distances <= 0.0):
        raise ValueError("all distances must be positive")
    return nominal_blockade * (nominal_distance / distances) ** exponent


def gaussian_noise_from_one_sided_psd(
    times: np.ndarray,
    frequencies: np.ndarray,
    psd: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Synthesize a real stationary trace from a supplied one-sided PSD.

    This utility can represent laser phase or fractional amplitude noise.  It
    requires the apparatus PSD as input and therefore cannot independently
    reproduce Figure 4(f) from the paper alone.
    """
    times = np.asarray(times, dtype=float)
    frequencies = np.asarray(frequencies, dtype=float)
    psd = np.asarray(psd, dtype=float)
    if frequencies.shape != psd.shape or np.any(psd < 0.0):
        raise ValueError("frequency and non-negative PSD arrays must match")
    if len(times) < 2 or np.any(np.diff(times) <= 0.0):
        raise ValueError("times must be strictly increasing")
    if len(frequencies) < 2:
        raise ValueError("at least two PSD frequency samples are required")
    widths = np.gradient(frequencies)
    phases = rng.uniform(0.0, 2.0 * np.pi, len(frequencies))
    amplitudes = np.sqrt(2.0 * psd * widths)
    return np.sum(
        amplitudes[:, None]
        * np.cos(2.0 * np.pi * frequencies[:, None] * times + phases[:, None]),
        axis=0,
    )
