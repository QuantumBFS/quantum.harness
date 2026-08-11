"""Hidden-history filters for resolution-degraded Born records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np
from numpy.typing import NDArray

from .channels import ConfusionChannel, ErasureChannel
from .self_dual import SELF_DUAL_BETA, SelfDualGaussianCylinder

ObservationChannel = ErasureChannel | ConfusionChannel
GateKind = Literal["zz", "x"]


class FilterCylinder(Protocol):
    length: int

    def zz_probability_plus(self, state: NDArray, bond: int) -> float: ...

    def x_probability_plus(self, state: NDArray, site: int) -> float: ...

    def update_zz(
        self, state: NDArray, bond: int, sign: int
    ) -> tuple[NDArray, float]: ...

    def update_x(
        self, state: NDArray, site: int, sign: int
    ) -> tuple[NDArray, float]: ...


@dataclass(frozen=True, slots=True)
class ExactBranch:
    """One posterior pure-state branch and its normalized weight."""

    weight: float
    state: NDArray


@dataclass(frozen=True, slots=True)
class DegradedRecordEstimate:
    """Block estimates of observed-record surprisal rates."""

    lengths: NDArray[np.int64]
    channel_name: str
    channel_parameter: float
    particles: int
    steps: int
    burn_in: int
    block_size: int
    blocks: NDArray[np.float64]

    @property
    def means(self) -> NDArray[np.float64]:
        return np.mean(self.blocks, axis=0)

    @property
    def covariance_of_mean(self) -> NDArray[np.float64]:
        return np.cov(self.blocks, rowvar=False, ddof=1) / self.blocks.shape[0]


def _gate_probability_plus(
    cylinder: FilterCylinder,
    state: NDArray,
    gate: tuple[GateKind, int],
) -> float:
    kind, index = gate
    if kind == "zz":
        return cylinder.zz_probability_plus(state, index)
    return cylinder.x_probability_plus(state, index)


def _gate_update(
    cylinder: FilterCylinder,
    state: NDArray,
    gate: tuple[GateKind, int],
    sign: int,
) -> tuple[NDArray, float]:
    kind, index = gate
    if kind == "zz":
        return cylinder.update_zz(state, index, sign)
    return cylinder.update_x(state, index, sign)


def exact_filter_observation(
    branches: list[ExactBranch],
    cylinder: FilterCylinder,
    gate: tuple[GateKind, int],
    observed: int,
    channel: ObservationChannel,
) -> tuple[list[ExactBranch], float]:
    """Apply one observed symbol while summing every latent sign exactly."""

    descendants: list[ExactBranch] = []
    likelihood = 0.0
    for branch in branches:
        probability_plus = _gate_probability_plus(
            cylinder, branch.state, gate
        )
        for sign, latent_probability in (
            (1, probability_plus),
            (-1, 1.0 - probability_plus),
        ):
            kernel = channel.conditional_probability(observed, sign)
            joint_weight = branch.weight * latent_probability * kernel
            if joint_weight == 0.0:
                continue
            updated, checked = _gate_update(
                cylinder, branch.state, gate, sign
            )
            if not np.isclose(checked, latent_probability, atol=1e-13):
                raise FloatingPointError("filter/model Born probabilities differ")
            descendants.append(ExactBranch(joint_weight, updated))
            likelihood += joint_weight
    if not np.isfinite(likelihood) or likelihood <= 0.0:
        raise FloatingPointError("observed symbol has zero filter likelihood")
    posterior = [
        ExactBranch(branch.weight / likelihood, branch.state)
        for branch in descendants
    ]
    return posterior, float(np.log(likelihood))


def particle_filter_observation(
    particles: list[NDArray],
    cylinder: FilterCylinder,
    gate: tuple[GateKind, int],
    observed: int,
    channel: ObservationChannel,
    *,
    sign_uniforms: NDArray[np.float64],
    resample_uniform: float,
) -> tuple[list[NDArray], float]:
    """Fully adapted particle update for one degraded observation."""

    count = len(particles)
    if count == 0:
        raise ValueError("particle filter requires at least one particle")
    uniforms = np.asarray(sign_uniforms, dtype=float)
    if uniforms.shape != (count,):
        raise ValueError("one sign uniform is required per particle")
    proposed: list[NDArray] = []
    weights = np.empty(count)
    for index, state in enumerate(particles):
        probability_plus = _gate_probability_plus(cylinder, state, gate)
        plus_joint = probability_plus * channel.conditional_probability(
            observed, 1
        )
        minus_joint = (1.0 - probability_plus) * (
            channel.conditional_probability(observed, -1)
        )
        predictive = plus_joint + minus_joint
        if predictive <= 0.0:
            raise FloatingPointError("particle has zero predictive likelihood")
        posterior_plus = plus_joint / predictive
        sign = 1 if uniforms[index] < posterior_plus else -1
        updated, _ = _gate_update(cylinder, state, gate, sign)
        proposed.append(updated)
        weights[index] = predictive
    likelihood = float(np.mean(weights))
    normalized = weights / np.sum(weights)
    cumulative = np.cumsum(normalized)
    start = (float(resample_uniform) % 1.0) / count
    points = start + np.arange(count) / count
    ancestors = np.searchsorted(cumulative, points, side="right")
    resampled = [proposed[int(index)].copy() for index in ancestors]
    return resampled, float(np.log(likelihood))


def gaussian_particle_filter_observation(
    particles: NDArray[np.float64],
    cylinder: SelfDualGaussianCylinder,
    gate: tuple[GateKind, int],
    observed: int,
    channel: ObservationChannel,
    *,
    sign_uniforms: NDArray[np.float64],
    resample_uniform: float,
) -> tuple[NDArray[np.float64], float]:
    """Vectorized fully adapted update for Gaussian covariance particles."""

    covariances = np.asarray(particles, dtype=float)
    if (
        covariances.ndim != 3
        or covariances.shape[0] < 1
        or covariances.shape[1:]
        != (cylinder.majorana_dimension, cylinder.majorana_dimension)
    ):
        raise ValueError(
            "particles must have shape (count, 2L, 2L)"
        )
    count = covariances.shape[0]
    uniforms = np.asarray(sign_uniforms, dtype=float)
    if uniforms.shape != (count,):
        raise ValueError("one sign uniform is required per particle")
    kind, index = gate
    if kind == "zz":
        first, second = cylinder._zz_indices(index)
    elif kind == "x":
        if not 0 <= index < cylinder.length:
            raise ValueError("site index out of range")
        first, second = 2 * index, 2 * index + 1
    else:
        raise ValueError("unknown gate kind")
    probabilities_plus = cylinder.bilinear_probability_plus_batch(
        covariances, first, second
    )
    plus_kernel = channel.conditional_probability(observed, 1)
    minus_kernel = channel.conditional_probability(observed, -1)
    plus_joint = probabilities_plus * plus_kernel
    minus_joint = (1.0 - probabilities_plus) * minus_kernel
    predictive = plus_joint + minus_joint
    if np.any(predictive <= 0.0) or not np.all(np.isfinite(predictive)):
        raise FloatingPointError(
            "particle has nonpositive predictive likelihood"
        )
    posterior_plus = plus_joint / predictive
    signs = np.where(uniforms < posterior_plus, 1, -1).astype(np.int8)
    proposed, _ = cylinder.update_bilinear_batch(
        covariances, first, second, signs
    )
    likelihood = float(np.mean(predictive))
    normalized = predictive / np.sum(predictive)
    cumulative = np.cumsum(normalized)
    start = (float(resample_uniform) % 1.0) / count
    points = start + np.arange(count) / count
    ancestors = np.searchsorted(cumulative, points, side="right")
    return proposed[ancestors].copy(), float(np.log(likelihood))


def _observe_latent(
    latent: int,
    channel: ObservationChannel,
    uniform: float,
) -> int:
    if isinstance(channel, ErasureChannel):
        return latent if uniform < channel.retain_probability else 0
    return -latent if uniform < channel.error_probability else latent


def _sample_true_gate(
    cylinder: SelfDualGaussianCylinder,
    state: NDArray[np.float64],
    gate: tuple[GateKind, int],
    uniform: float,
) -> tuple[NDArray[np.float64], int]:
    kind, index = gate
    if kind == "zz":
        updated, _, sign = cylinder.sample_zz(state, index, uniform)
    else:
        updated, _, sign = cylinder.sample_x(state, index, uniform)
    return updated, sign


def estimate_degraded_record_rates(
    lengths: list[int] | NDArray[np.int64],
    channel: ObservationChannel,
    *,
    beta: float = SELF_DUAL_BETA,
    particles: int = 256,
    steps: int = 2_000,
    burn_in: int = 200,
    block_size: int = 100,
    seed: int = 0,
    batched: bool = True,
) -> DegradedRecordEstimate:
    """Estimate observed-record entropy using hidden-history filtering."""

    sizes = np.sort(np.asarray(lengths, dtype=int))
    if (
        sizes.ndim != 1
        or sizes.size < 3
        or np.unique(sizes).size != sizes.size
        or np.any(sizes < 3)
    ):
        raise ValueError("lengths need at least three unique values >= 3")
    if particles < 1:
        raise ValueError("particles must be positive")
    if steps < block_size or steps % block_size:
        raise ValueError("steps must be a positive multiple of block_size")
    if burn_in < 0:
        raise ValueError("burn_in must be nonnegative")
    exact_rate: NDArray[np.float64] | None = None
    if isinstance(channel, ErasureChannel) and channel.retain_probability == 0.0:
        exact_rate = np.zeros(sizes.size)
    elif (
        isinstance(channel, ConfusionChannel)
        and channel.error_probability == 0.5
    ):
        # Each of the 2L observed gate outcomes is an independent fair bit,
        # irrespective of the latent Born history.
        exact_rate = 2.0 * sizes * np.log(2.0)
    if exact_rate is not None:
        blocks = np.broadcast_to(
            exact_rate,
            (steps // block_size, sizes.size),
        ).copy()
        parameter = (
            channel.retain_probability
            if isinstance(channel, ErasureChannel)
            else channel.error_probability
        )
        return DegradedRecordEstimate(
            lengths=sizes.astype(np.int64),
            channel_name=(
                "erasure"
                if isinstance(channel, ErasureChannel)
                else "confusion"
            ),
            channel_parameter=float(parameter),
            particles=particles,
            steps=steps,
            burn_in=burn_in,
            block_size=block_size,
            blocks=blocks,
        )
    cylinders = [
        SelfDualGaussianCylinder(int(length), beta) for length in sizes
    ]
    true_states = [cylinder.plus_covariance() for cylinder in cylinders]
    if batched:
        ensembles: list[NDArray[np.float64] | list[NDArray[np.float64]]] = [
            np.repeat(
                cylinder.plus_covariance()[None, :, :],
                particles,
                axis=0,
            )
            for cylinder in cylinders
        ]
    else:
        ensembles = [
            [cylinder.plus_covariance() for _ in range(particles)]
            for cylinder in cylinders
        ]
    data_rng = np.random.default_rng(seed)
    readout_rng = np.random.default_rng(
        np.random.SeedSequence([seed, 0xC0A2])
    )
    filter_rngs = [
        np.random.default_rng(
            np.random.SeedSequence([seed, int(length), 0xCEFF])
        )
        for length in sizes
    ]

    def row() -> NDArray[np.float64]:
        increments = np.zeros(sizes.size)
        max_length = int(sizes[-1])
        zz_uniforms = data_rng.random(max_length)
        x_uniforms = data_rng.random(max_length)
        zz_channel_uniforms = readout_rng.random(max_length)
        x_channel_uniforms = readout_rng.random(max_length)
        for width_index, (length, cylinder, filter_rng) in enumerate(
            zip(sizes, cylinders, filter_rngs, strict=True)
        ):
            width = int(length)
            gates = [
                *(("zz", index) for index in range(width)),
                *(("x", index) for index in range(width)),
            ]
            for gate in gates:
                kind, index = gate
                latent_uniform = (
                    zz_uniforms[index]
                    if kind == "zz"
                    else x_uniforms[index]
                )
                channel_uniform = (
                    zz_channel_uniforms[index]
                    if kind == "zz"
                    else x_channel_uniforms[index]
                )
                true_states[width_index], sign = _sample_true_gate(
                    cylinder,
                    true_states[width_index],
                    gate,
                    float(latent_uniform),
                )
                observed = _observe_latent(
                    sign, channel, float(channel_uniform)
                )
                sign_uniforms = filter_rng.random(particles)
                resample_uniform = float(filter_rng.random())
                if batched:
                    batch = ensembles[width_index]
                    if not isinstance(batch, np.ndarray):
                        raise TypeError("batched ensemble storage is invalid")
                    ensembles[width_index], log_likelihood = (
                        gaussian_particle_filter_observation(
                            batch,
                            cylinder,
                            gate,
                            observed,
                            channel,
                            sign_uniforms=sign_uniforms,
                            resample_uniform=resample_uniform,
                        )
                    )
                else:
                    scalar = ensembles[width_index]
                    if isinstance(scalar, np.ndarray):
                        raise TypeError("scalar ensemble storage is invalid")
                    ensembles[width_index], log_likelihood = (
                        particle_filter_observation(
                            scalar,
                            cylinder,
                            gate,
                            observed,
                            channel,
                            sign_uniforms=sign_uniforms,
                            resample_uniform=resample_uniform,
                        )
                    )
                increments[width_index] += log_likelihood
        return increments

    for _ in range(burn_in):
        row()
    blocks = np.empty((steps // block_size, sizes.size))
    for block in range(blocks.shape[0]):
        total = np.zeros(sizes.size)
        for _ in range(block_size):
            total += row()
        blocks[block] = -total / block_size
    parameter = (
        channel.retain_probability
        if isinstance(channel, ErasureChannel)
        else channel.error_probability
    )
    return DegradedRecordEstimate(
        lengths=sizes.astype(np.int64),
        channel_name=(
            "erasure" if isinstance(channel, ErasureChannel) else "confusion"
        ),
        channel_parameter=float(parameter),
        particles=particles,
        steps=steps,
        burn_in=burn_in,
        block_size=block_size,
        blocks=blocks,
    )
