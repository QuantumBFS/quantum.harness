"""Coordinate-space sphere VMC with auditable statistical diagnostics.

The sampler consumes a callable returning ``log(Psi)``.  Its Metropolis ratio
therefore samples ``|Psi|^2`` with respect to the product sphere measure.
The coordinate Coulomb value is a bare-potential estimator; it is not a
projected-Hamiltonian local energy.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Callable

import numpy as np

from challenge15.spec import SphereSpec


Spinors = np.ndarray
LogAmplitude = Callable[[Spinors], complex]


@dataclass(frozen=True, slots=True)
class SamplerConfig:
    burn_in: int = 500
    samples: int = 1000
    thinning: int = 1
    chains: int = 4
    local_step: float = 0.7
    rigid_step: float = 0.7
    rigid_probability: float = 0.1
    target_acceptance: float = 0.5
    adapt_interval: int = 25
    adaptation_rate: float = 0.5
    seed: int = 0

    def __post_init__(self) -> None:
        for name in ("burn_in", "samples", "thinning", "chains", "adapt_interval"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive Python integer")
        for name in ("local_step", "rigid_step", "adaptation_rate"):
            value = getattr(self, name)
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("rigid_probability", "target_acceptance"):
            value = getattr(self, name)
            if not np.isfinite(value) or not 0.0 < value < 1.0:
                raise ValueError(f"{name} must lie strictly between zero and one")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed must be a Python integer")


@dataclass(frozen=True, slots=True)
class SamplingDiagnostics:
    """Samples or scalar-observable diagnostics from independent chains."""

    samples: np.ndarray | None = None
    estimate: float = float("nan")
    standard_error: float = float("nan")
    bare_potential_estimator_variance: float = float("nan")
    integrated_autocorrelation_time: float = float("nan")
    effective_sample_size: float = float("nan")
    split_rhat: float = float("nan")
    autocorrelation_window: int = 0
    autocorrelation_converged: bool = False
    autocorrelation_method: str = "fft_sokal_window"
    paired_covariance: float = float("nan")
    acceptance_rate: float = float("nan")
    local_acceptance_rate: float = float("nan")
    rigid_acceptance_rate: float = float("nan")
    local_proposals: int = 0
    rigid_proposals: int = 0
    pilot_proposals: int = 0
    pilot_acceptance_rate: float = float("nan")
    warmup_proposals: int = 0
    warmup_acceptance_rate: float = float("nan")
    adaptation_updates: int = 0
    final_local_step: float = float("nan")
    final_rigid_step: float = float("nan")
    widths_frozen: bool = True

    @classmethod
    def from_chains(cls, chains: np.ndarray) -> SamplingDiagnostics:
        values = _scalar_chains(chains)
        chain_count, draws = values.shape
        flattened = values.reshape(-1)
        variance = float(np.var(flattened, ddof=1))
        tau, window, converged = _sokal_autocorrelation(values)
        if variance == 0:
            tau = 1.0
            effective_sample_size = float(flattened.size)
            standard_error = 0.0
            converged = True
        elif converged:
            effective_sample_size = min(flattened.size, flattened.size / tau)
            standard_error = float(
                np.sqrt(variance / effective_sample_size)
            )
        else:
            effective_sample_size = float("nan")
            standard_error = float("nan")
        return cls(
            estimate=float(np.mean(flattened)),
            standard_error=standard_error,
            bare_potential_estimator_variance=variance,
            integrated_autocorrelation_time=tau,
            effective_sample_size=effective_sample_size,
            split_rhat=_split_rhat(values),
            autocorrelation_window=window,
            autocorrelation_converged=converged,
        )

    @classmethod
    def from_paired_gap(
        cls, lower_chains: np.ndarray, upper_chains: np.ndarray
    ) -> SamplingDiagnostics:
        lower = _scalar_chains(lower_chains)
        upper = _scalar_chains(upper_chains)
        if lower.shape != upper.shape:
            raise ValueError("paired chains must have identical shapes")
        result = cls.from_chains(upper - lower)
        covariance = float(
            np.cov(lower.reshape(-1), upper.reshape(-1), ddof=1)[0, 1]
        )
        return cls(
            estimate=result.estimate,
            standard_error=result.standard_error,
            bare_potential_estimator_variance=(
                result.bare_potential_estimator_variance
            ),
            integrated_autocorrelation_time=(
                result.integrated_autocorrelation_time
            ),
            effective_sample_size=result.effective_sample_size,
            split_rhat=result.split_rhat,
            autocorrelation_window=result.autocorrelation_window,
            autocorrelation_converged=result.autocorrelation_converged,
            autocorrelation_method=result.autocorrelation_method,
            paired_covariance=covariance,
        )

    def for_observable(
        self, observable: Callable[[Spinors], float]
    ) -> SamplingDiagnostics:
        if self.samples is None:
            raise ValueError("raw coordinate samples are not available")
        chain_count, draws = self.samples.shape[:2]
        values = np.empty((chain_count, draws), dtype=np.float64)
        for chain in range(chain_count):
            for draw in range(draws):
                values[chain, draw] = observable(self.samples[chain, draw])
        result = type(self).from_chains(values)
        return type(self)(
            estimate=result.estimate,
            standard_error=result.standard_error,
            bare_potential_estimator_variance=(
                result.bare_potential_estimator_variance
            ),
            integrated_autocorrelation_time=(
                result.integrated_autocorrelation_time
            ),
            effective_sample_size=result.effective_sample_size,
            split_rhat=result.split_rhat,
            autocorrelation_window=result.autocorrelation_window,
            autocorrelation_converged=result.autocorrelation_converged,
            autocorrelation_method=result.autocorrelation_method,
            acceptance_rate=self.acceptance_rate,
            local_acceptance_rate=self.local_acceptance_rate,
            rigid_acceptance_rate=self.rigid_acceptance_rate,
            local_proposals=self.local_proposals,
            rigid_proposals=self.rigid_proposals,
            pilot_proposals=self.pilot_proposals,
            pilot_acceptance_rate=self.pilot_acceptance_rate,
            warmup_proposals=self.warmup_proposals,
            warmup_acceptance_rate=self.warmup_acceptance_rate,
            adaptation_updates=self.adaptation_updates,
            final_local_step=self.final_local_step,
            final_rigid_step=self.final_rigid_step,
            widths_frozen=self.widths_frozen,
        )


class SphereMetropolis:
    """Metropolis sampler using reversible local and rigid SU(2) rotations."""

    def __init__(
        self,
        log_amplitude: LogAmplitude,
        spec: SphereSpec,
        config: SamplerConfig | None = None,
    ) -> None:
        if not callable(log_amplitude):
            raise TypeError("log_amplitude must be callable")
        self.log_amplitude = log_amplitude
        self.spec = spec
        self.config = config or SamplerConfig()

    def run(self, initial_spinors: np.ndarray | None = None) -> SamplingDiagnostics:
        config = self.config
        streams = np.random.SeedSequence(config.seed).spawn(config.chains + 1)
        pilot_rng = np.random.default_rng(streams[0])
        pilot_states = _initial_states(
            pilot_rng, 1, self.spec.particles, None
        )
        pilot_log_values = np.asarray(
            [self._log_probability(pilot_states[0])], dtype=np.float64
        )
        local_step = config.local_step
        rigid_step = config.rigid_step
        window_proposals = {"local": 0, "rigid": 0}
        window_accepts = {"local": 0, "rigid": 0}
        pilot_accepts = 0
        adaptation_updates = 0

        for sweep in range(config.burn_in):
            move, accepted = self._move(
                pilot_states,
                pilot_log_values,
                0,
                pilot_rng,
                local_step=local_step,
                rigid_step=rigid_step,
            )
            pilot_accepts += int(accepted)
            window_proposals[move] += 1
            window_accepts[move] += int(accepted)
            if (sweep + 1) % config.adapt_interval == 0:
                local_step = _adapt_width(
                    local_step,
                    window_accepts["local"],
                    window_proposals["local"],
                    config,
                )
                rigid_step = _adapt_width(
                    rigid_step,
                    window_accepts["rigid"],
                    window_proposals["rigid"],
                    config,
                )
                window_proposals = {"local": 0, "rigid": 0}
                window_accepts = {"local": 0, "rigid": 0}
                adaptation_updates += 1

        production_rngs = [
            np.random.default_rng(stream) for stream in streams[1:]
        ]
        states = _production_initial_states(
            production_rngs,
            config.chains,
            self.spec.particles,
            initial_spinors,
        )
        log_values = np.asarray(
            [self._log_probability(state) for state in states], dtype=np.float64
        )
        warmup_accepts = 0
        for _ in range(config.burn_in):
            for chain, rng in enumerate(production_rngs):
                _, accepted = self._move(
                    states,
                    log_values,
                    chain,
                    rng,
                    local_step=local_step,
                    rigid_step=rigid_step,
                )
                warmup_accepts += int(accepted)

        proposal_counts = {"local": 0, "rigid": 0}
        acceptance_counts = {"local": 0, "rigid": 0}
        samples = np.empty(
            (config.chains, config.samples, self.spec.particles, 2),
            dtype=np.complex128,
        )
        for draw in range(config.samples):
            for _ in range(config.thinning):
                for chain, rng in enumerate(production_rngs):
                    move, accepted = self._move(
                        states,
                        log_values,
                        chain,
                        rng,
                        local_step=local_step,
                        rigid_step=rigid_step,
                    )
                    proposal_counts[move] += 1
                    acceptance_counts[move] += int(accepted)
            samples[:, draw] = states

        local_proposals = proposal_counts["local"]
        rigid_proposals = proposal_counts["rigid"]
        total_proposals = local_proposals + rigid_proposals
        total_accepts = acceptance_counts["local"] + acceptance_counts["rigid"]
        return SamplingDiagnostics(
            samples=samples,
            acceptance_rate=total_accepts / total_proposals,
            local_acceptance_rate=_safe_rate(
                acceptance_counts["local"], local_proposals
            ),
            rigid_acceptance_rate=_safe_rate(
                acceptance_counts["rigid"], rigid_proposals
            ),
            local_proposals=local_proposals,
            rigid_proposals=rigid_proposals,
            pilot_proposals=config.burn_in,
            pilot_acceptance_rate=pilot_accepts / config.burn_in,
            warmup_proposals=config.chains * config.burn_in,
            warmup_acceptance_rate=warmup_accepts
            / (config.chains * config.burn_in),
            adaptation_updates=adaptation_updates,
            final_local_step=local_step,
            final_rigid_step=rigid_step,
            widths_frozen=True,
        )

    def _move(
        self,
        states: np.ndarray,
        log_values: np.ndarray,
        chain: int,
        rng: np.random.Generator,
        *,
        local_step: float,
        rigid_step: float,
    ) -> tuple[str, bool]:
        rigid = bool(rng.random() < self.config.rigid_probability)
        move = "rigid" if rigid else "local"
        width = rigid_step if rigid else local_step
        axis = rng.normal(size=3)
        angle = rng.normal(scale=width)
        rotation = su2_rotation(axis, angle)
        candidate = states[chain].copy()
        if rigid:
            candidate = candidate @ rotation.T
        else:
            particle = int(rng.integers(self.spec.particles))
            candidate[particle] = rotation @ candidate[particle]
        candidate_log_probability = self._log_probability(candidate)
        log_ratio = candidate_log_probability - log_values[chain]
        accepted = bool(
            np.isfinite(candidate_log_probability)
            and (log_ratio >= 0.0 or np.log(rng.random()) < log_ratio)
        )
        if accepted:
            states[chain] = candidate
            log_values[chain] = candidate_log_probability
        return move, accepted

    def _log_probability(self, spinors: np.ndarray) -> float:
        value = complex(np.asarray(self.log_amplitude(spinors)))
        return 2.0 * value.real


def su2_rotation(axis: np.ndarray, angle: float) -> np.ndarray:
    """Return ``exp(-i angle axis.sigma / 2)`` for a nonzero real axis."""

    vector = np.asarray(axis, dtype=np.float64)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise ValueError("axis must be a finite real vector of shape (3,)")
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        raise ValueError("axis must be nonzero")
    if not np.isfinite(angle):
        raise ValueError("angle must be finite")
    x, y, z = vector / norm
    cosine = np.cos(angle / 2.0)
    sine = np.sin(angle / 2.0)
    return np.asarray(
        [
            [cosine - 1j * sine * z, -sine * y - 1j * sine * x],
            [sine * y - 1j * sine * x, cosine + 1j * sine * z],
        ],
        dtype=np.complex128,
    )


def coulomb_value(spinors: np.ndarray, spec: SphereSpec) -> float:
    """Evaluate ``sum(i<j) 1/(r_ij/l_B)`` at one coordinate sample."""

    coordinates = np.asarray(spinors, dtype=np.complex128)
    if coordinates.shape != (spec.particles, 2):
        raise ValueError("spinors must have shape (spec.particles, 2)")
    norms = np.linalg.norm(coordinates, axis=1)
    if np.any(norms == 0) or not np.all(np.isfinite(norms)):
        raise ValueError("spinors must be finite and nonzero")
    normalized = coordinates / norms[:, None]
    value = 0.0
    radius_factor = 2.0 * np.sqrt(spec.q)
    for first in range(spec.particles):
        for second in range(first + 1, spec.particles):
            overlap_squared = abs(np.vdot(normalized[first], normalized[second])) ** 2
            separation_squared = max(0.0, 1.0 - overlap_squared)
            if separation_squared == 0.0:
                return float("inf")
            chord = radius_factor * np.sqrt(separation_squared)
            value += 1.0 / chord
    return float(value)


def energy_and_score_gradient(
    values: np.ndarray, scores: np.ndarray
) -> tuple[float, np.ndarray]:
    """Return bare-potential mean and the real complex-score covariance."""

    potential = np.asarray(values, dtype=np.float64)
    score = np.asarray(scores, dtype=np.complex128)
    if potential.ndim != 1:
        raise ValueError("values must be one-dimensional")
    if score.ndim < 1:
        raise ValueError("scores must be at least one-dimensional")
    if score.shape[0] != potential.size:
        raise ValueError("scores and values must have the same sample axis")
    if potential.size < 2:
        raise ValueError("at least two samples are required")
    if not np.all(np.isfinite(potential)) or not np.all(np.isfinite(score)):
        raise ValueError("scores and values must be finite")
    conjugate_score = np.conjugate(score)
    shaped_values = potential.reshape(
        (potential.size,) + (1,) * (score.ndim - 1)
    )
    covariance = potential.size / (potential.size - 1) * (
        np.mean(conjugate_score * shaped_values, axis=0)
        - np.mean(conjugate_score, axis=0) * np.mean(potential)
    )
    return float(np.mean(potential)), 2.0 * np.real(covariance)


def _production_initial_states(
    rngs: list[np.random.Generator],
    chains: int,
    particles: int,
    initial_spinors: np.ndarray | None,
) -> np.ndarray:
    if initial_spinors is None:
        return np.stack(
            [_initial_states(rng, 1, particles, None)[0] for rng in rngs]
        )
    initial = np.asarray(initial_spinors, dtype=np.complex128)
    if initial.shape == (particles, 2):
        if chains != 1:
            raise ValueError(
                "one shared initial state cannot seed multiple independent chains"
            )
        initial = initial[None, ...]
    if initial.shape != (chains, particles, 2):
        raise ValueError("initial_spinors must provide one state per chain")
    return _initial_states(rngs[0], chains, particles, initial)


def _initial_states(
    rng: np.random.Generator,
    chains: int,
    particles: int,
    initial_spinors: np.ndarray | None,
) -> np.ndarray:
    if initial_spinors is None:
        states = rng.normal(size=(chains, particles, 2)) + 1j * rng.normal(
            size=(chains, particles, 2)
        )
    else:
        initial = np.asarray(initial_spinors, dtype=np.complex128)
        if initial.shape == (particles, 2):
            states = np.broadcast_to(initial, (chains, particles, 2)).copy()
        elif initial.shape == (chains, particles, 2):
            states = initial.copy()
        else:
            raise ValueError(
                "initial_spinors must have shape (particles, 2) or "
                "(chains, particles, 2)"
            )
    norms = np.linalg.norm(states, axis=-1, keepdims=True)
    if np.any(norms == 0) or not np.all(np.isfinite(norms)):
        raise ValueError("initial spinors must be finite and nonzero")
    return states / norms


def _adapt_width(
    width: float, accepts: int, proposals: int, config: SamplerConfig
) -> float:
    if proposals == 0:
        return width
    rate = accepts / proposals
    updated = width * np.exp(config.adaptation_rate * (rate - config.target_acceptance))
    return float(np.clip(updated, 1e-4, pi))


def _safe_rate(accepts: int, proposals: int) -> float:
    return accepts / proposals if proposals else float("nan")


def _scalar_chains(chains: np.ndarray) -> np.ndarray:
    values = np.asarray(chains, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] < 2 or values.shape[1] < 4:
        raise ValueError("diagnostics require at least two chains and four draws")
    if not np.all(np.isfinite(values)):
        raise ValueError("chains must contain only finite values")
    return values


def _sokal_autocorrelation(
    chains: np.ndarray,
    *,
    window_factor: float = 5.0,
    minimum_lengths: float = 50.0,
) -> tuple[float, int, bool]:
    draws = chains.shape[1]
    centered = chains - np.mean(chains, axis=1, keepdims=True)
    transform_length = 1 << (2 * draws - 1).bit_length()
    transforms = np.fft.rfft(centered, n=transform_length, axis=1)
    autocovariance = np.fft.irfft(
        transforms * np.conjugate(transforms),
        n=transform_length,
        axis=1,
    )[:, :draws]
    autocovariance /= np.arange(draws, 0, -1)[None, :]
    mean_autocovariance = np.mean(autocovariance, axis=0)
    if mean_autocovariance[0] == 0.0:
        return 1.0, 0, True
    autocorrelation = mean_autocovariance / mean_autocovariance[0]
    tau_by_window = 2.0 * np.cumsum(autocorrelation) - 1.0
    maximum_window = max(1, draws // 2)
    last_window = maximum_window - 1
    for window in range(1, maximum_window):
        tau = max(1.0, float(tau_by_window[window]))
        plateau = tau_by_window[max(1, window // 2) : window + 1]
        relative_plateau_range = (
            float(np.max(plateau) - np.min(plateau)) / tau
        )
        if (
            window >= window_factor * tau
            and draws >= minimum_lengths * tau
            and relative_plateau_range <= 0.25
        ):
            return tau, window, True
    last_tau = max(1.0, float(tau_by_window[last_window]))
    return last_tau, last_window, False


def _split_rhat(chains: np.ndarray) -> float:
    half = chains.shape[1] // 2
    if half < 2:
        return float("nan")
    split = np.concatenate((chains[:, :half], chains[:, -half:]), axis=0)
    within = float(np.mean(np.var(split, axis=1, ddof=1)))
    between = half * float(np.var(np.mean(split, axis=1), ddof=1))
    if within == 0.0:
        return 1.0 if between == 0.0 else float("inf")
    variance = (half - 1.0) / half * within + between / half
    return float(np.sqrt(max(variance / within, 0.0)))
