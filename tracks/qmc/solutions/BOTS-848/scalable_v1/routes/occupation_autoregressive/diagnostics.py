"""Sparse construction and seeded rotation diagnostics for a spin-two tower."""

from __future__ import annotations

import cmath
import math
from collections.abc import Mapping
from numbers import Integral
from types import MappingProxyType

import numpy as np
from scipy.linalg import expm

from .operators import ladder_neighbors
from .tower import (
    FixedMMetropolisSampler,
    LadderComponent,
    LadderTower,
    spin2_ladder_coefficient,
)


_M_VALUES = (-2, -1, 0, 1, 2)
_LOG_COMPLEX128_MAX = math.log(np.finfo(np.float64).max)
_BLOCK_MEAN_SAMPLE_THRESHOLD = 8
_MAX_BLOCK_MEANS = 8
_ROTATION_CONFIDENCE_SIGMAS = 5.0


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer")
    return int(value)


def _amplitude(component: LadderComponent, state: int) -> complex:
    log_value = component.logpsi(state)
    if log_value.real == -math.inf:
        return 0.0j
    if log_value.real > _LOG_COMPLEX128_MAX:
        raise FloatingPointError("tower amplitude is outside complex128 range")
    with np.errstate(under="ignore"):
        value = cmath.exp(log_value)
    if not math.isfinite(value.real) or not math.isfinite(value.imag):
        raise FloatingPointError("tower amplitude is non-finite")
    return value


def _complex_sum(values: list[complex]) -> complex:
    return complex(
        math.fsum(value.real for value in values),
        math.fsum(value.imag for value in values),
    )


def _validated_tiny_states(
    tower: LadderTower,
    tiny_support_by_m: Mapping[int, object],
) -> Mapping[int, tuple[int, ...]]:
    if tower[0].n_electrons > 4:
        raise ValueError("tiny_support_by_m is restricted to tiny test fixtures")
    if set(tiny_support_by_m) != set(_M_VALUES):
        raise ValueError("tiny_support_by_m must contain exactly five sectors")
    validated: dict[int, tuple[int, ...]] = {}
    for m in _M_VALUES:
        raw_states = tiny_support_by_m[m]
        if isinstance(raw_states, (str, bytes)):
            raise TypeError("tiny support states must be an iterable of integers")
        try:
            states = tuple(tower[m]._validated_state(state) for state in raw_states)
        except TypeError as error:
            raise TypeError(
                "tiny support states must be an iterable of integers"
            ) from error
        if not states:
            raise ValueError("each tiny support sector must be non-empty")
        if len(set(states)) != len(states):
            raise ValueError("tiny support states must be unique within a sector")
        for state in states:
            _amplitude(tower[m], state)
        validated[m] = states
    return MappingProxyType(validated)


def _next_sampling_seed(
    rng: np.random.Generator,
    used_seeds: set[int],
) -> int:
    for _attempt in range(1024):
        seed = int(rng.integers(0, np.iinfo(np.int64).max))
        if seed not in used_seeds:
            used_seeds.add(seed)
            return seed
    raise RuntimeError("could not derive a unique deterministic sampling seed")


def _sample_chain(
    tower: LadderTower,
    *,
    target_m: int,
    rng: np.random.Generator,
    used_seeds: set[int],
    burn_in_steps: int,
    sample_count: int,
) -> tuple[int, ...]:
    batch = FixedMMetropolisSampler(tower, target_m=target_m).sample(
        n_samples=sample_count,
        burn_in_steps=burn_in_steps,
        seed=_next_sampling_seed(rng, used_seeds),
    )
    states = tuple(int(state) for state in batch.configs)
    for state in states:
        value = _amplitude(tower[target_m], state)
        if value == 0.0:
            raise ValueError("sampled tower amplitude must be finite and nonzero")
    return states


def _sampled_states(
    tower: LadderTower,
    *,
    rng: np.random.Generator,
    used_seeds: set[int],
    burn_in_steps: int,
    sample_count: int,
) -> Mapping[int, tuple[int, ...]]:
    sampled: dict[int, tuple[int, ...]] = {}
    for m in _M_VALUES:
        sampled[m] = _sample_chain(
            tower,
            target_m=m,
            rng=rng,
            used_seeds=used_seeds,
            burn_in_steps=burn_in_steps,
            sample_count=sample_count,
        )
    return MappingProxyType(sampled)


def _tower_ladder_residual(
    tower: LadderTower,
    sector_states: Mapping[int, tuple[int, ...]],
) -> float:
    residuals: list[float] = []
    for direction in (1, -1):
        source_m = 0
        for _step in range(2):
            target_m = source_m + direction
            coefficient = spin2_ladder_coefficient(source_m, direction)
            for target in sector_states[target_m]:
                inverse = ladder_neighbors(
                    target,
                    tower[target_m].two_q,
                    direction=-direction,
                )
                sparse_action = _complex_sum(
                    [
                        complex(weight) * _amplitude(tower[source_m], source)
                        for source, weight in inverse.items()
                    ]
                )
                derived = coefficient * _amplitude(tower[target_m], target)
                scale = max(1.0, abs(sparse_action), abs(derived))
                residuals.append(abs(sparse_action - derived) / scale)
            source_m = target_m
    result = max(residuals, default=0.0)
    if not math.isfinite(result):
        raise FloatingPointError("tower ladder residual is non-finite")
    return result


def _spin_rotation(
    two_j: int,
    axis: np.ndarray,
    angle: float,
) -> np.ndarray:
    dimension = two_j + 1
    j = 0.5 * two_j
    m_values = np.arange(dimension, dtype=np.float64) - j
    raising = np.zeros((dimension, dimension), dtype=np.complex128)
    for index, m in enumerate(m_values[:-1]):
        raising[index + 1, index] = math.sqrt(j * (j + 1.0) - m * (m + 1.0))
    lowering = raising.T.conj()
    jx = 0.5 * (raising + lowering)
    jy = (raising - lowering) / (2.0j)
    jz = np.diag(m_values).astype(np.complex128)
    generator = axis[0] * jx + axis[1] * jy + axis[2] * jz
    rotation = np.asarray(expm(-1.0j * angle * generator), dtype=np.complex128)
    if not np.all(np.isfinite(rotation.real)) or not np.all(
        np.isfinite(rotation.imag)
    ):
        raise FloatingPointError("spin rotation matrix is non-finite")
    return rotation


def _occupied_orbitals(state: int, two_q: int) -> tuple[int, ...]:
    return tuple(
        orbital for orbital in range(two_q + 1) if state & (1 << orbital)
    )


def _rotation_minor(
    rotation: np.ndarray,
    target: int,
    source: int,
    two_q: int,
) -> complex:
    target_orbitals = _occupied_orbitals(target, two_q)
    source_orbitals = _occupied_orbitals(source, two_q)
    if len(target_orbitals) != len(source_orbitals):
        raise ValueError("rotation determinants must have equal particle count")
    minor = np.linalg.det(rotation[np.ix_(target_orbitals, source_orbitals)])
    value = complex(minor)
    if not math.isfinite(value.real) or not math.isfinite(value.imag):
        raise FloatingPointError("rotation determinant minor is non-finite")
    return value


def _block_mean_summary(
    values: list[complex],
) -> tuple[complex, float, float]:
    sample_count = len(values)
    if sample_count < _BLOCK_MEAN_SAMPLE_THRESHOLD:
        raise ValueError(
            "production rotation sample_count is too small for block means"
        )
    block_count = min(
        _MAX_BLOCK_MEANS,
        max(4, math.isqrt(sample_count)),
    )
    blocks = np.array_split(
        np.asarray(values, dtype=np.complex128),
        block_count,
    )
    block_means = [
        _complex_sum([complex(value) for value in block]) / len(block)
        for block in blocks
    ]
    sample_mean = _complex_sum(values) / sample_count
    center = _complex_sum(block_means) / block_count
    squared_deviations = [
        abs(block_mean - center) ** 2 for block_mean in block_means
    ]
    standard_error = math.sqrt(
        math.fsum(squared_deviations)
        / (block_count * (block_count - 1))
    )
    if not math.isfinite(standard_error):
        raise FloatingPointError("rotation block-mean error is non-finite")
    midpoint = block_count // 2
    early_mean = _complex_sum(block_means[:midpoint]) / midpoint
    late_count = block_count - midpoint
    late_mean = _complex_sum(block_means[midpoint:]) / late_count
    drift = float(abs(early_mean - late_mean))
    if not math.isfinite(drift):
        raise FloatingPointError("rotation block drift is non-finite")
    return sample_mean, standard_error, drift


def _finite_rotation_residual(
    tower: LadderTower,
    sector_states: Mapping[int, tuple[int, ...]],
    *,
    rng: np.random.Generator,
    used_seeds: set[int],
    burn_in_steps: int,
    sample_count: int,
    rotation_probes: int,
    exact_tiny: bool,
) -> float:
    residuals: list[float] = []
    source_m = 0
    source_component = tower[source_m]
    for probe_index in range(rotation_probes):
        target_m = _M_VALUES[probe_index % len(_M_VALUES)]
        if exact_tiny:
            source_states = sector_states[source_m]
            target_states = sector_states[target_m]
            target = target_states[int(rng.integers(0, len(target_states)))]
        else:
            replica_count = (
                2
                if sample_count >= _BLOCK_MEAN_SAMPLE_THRESHOLD
                else 4
            )
            source_chains = tuple(
                _sample_chain(
                    tower,
                    target_m=source_m,
                    rng=rng,
                    used_seeds=used_seeds,
                    burn_in_steps=burn_in_steps,
                    sample_count=sample_count,
                )
                for _replica in range(replica_count)
            )
            target = _sample_chain(
                tower,
                target_m=target_m,
                rng=rng,
                used_seeds=used_seeds,
                burn_in_steps=burn_in_steps,
                sample_count=1,
            )[0]

        spin_two_rotation: np.ndarray | None = None
        one_body_rotation: np.ndarray | None = None
        for _attempt in range(128):
            axis = np.asarray(rng.normal(size=3), dtype=np.float64)
            axis_norm = float(np.linalg.norm(axis))
            if not math.isfinite(axis_norm) or axis_norm == 0.0:
                continue
            axis /= axis_norm
            angle = float(rng.uniform(0.35, 1.25))
            candidate_spin_two = _spin_rotation(4, axis, angle)
            if abs(candidate_spin_two[target_m + 2, source_m + 2]) <= 1.0e-7:
                continue
            spin_two_rotation = candidate_spin_two
            one_body_rotation = _spin_rotation(
                source_component.two_q,
                axis,
                angle,
            )
            break
        if spin_two_rotation is None or one_body_rotation is None:
            raise RuntimeError("could not construct a nondegenerate rotation probe")

        if exact_tiny:
            rotated = _complex_sum(
                [
                    _rotation_minor(
                        one_body_rotation,
                        target,
                        source,
                        source_component.two_q,
                    )
                    * _amplitude(source_component, source)
                    for source in source_states
                ]
            )
            standard_error = 0.0
            drift_allowance = 0.0
        else:
            chain_summaries: list[tuple[complex, float, float]] = []
            for source_states in source_chains:
                importance_terms: list[complex] = []
                for source in source_states:
                    amplitude = _amplitude(source_component, source)
                    probability = abs(amplitude) ** 2
                    if probability == 0.0 or not math.isfinite(probability):
                        raise ValueError(
                            "importance samples require finite nonzero amplitudes"
                        )
                    importance_terms.append(
                        _rotation_minor(
                            one_body_rotation,
                            target,
                            source,
                            source_component.two_q,
                        )
                        * amplitude
                        / probability
                    )
                if len(importance_terms) >= _BLOCK_MEAN_SAMPLE_THRESHOLD:
                    summary = _block_mean_summary(importance_terms)
                else:
                    summary = (
                        _complex_sum(importance_terms)
                        / len(importance_terms),
                        0.0,
                        0.0,
                    )
                chain_summaries.append(summary)
            chain_means = [summary[0] for summary in chain_summaries]
            rotated = _complex_sum(chain_means) / len(chain_means)
            within_chain_error = math.sqrt(
                math.fsum(summary[1] ** 2 for summary in chain_summaries)
            ) / len(chain_summaries)
            between_chain_error = math.sqrt(
                math.fsum(abs(mean - rotated) ** 2 for mean in chain_means)
                / (len(chain_means) * (len(chain_means) - 1))
            )
            standard_error = math.hypot(
                within_chain_error,
                between_chain_error,
            )
            maximum_chain_disagreement = max(
                (
                    abs(left - right)
                    for index, left in enumerate(chain_means)
                    for right in chain_means[index + 1 :]
                ),
                default=0.0,
            )
            drift_allowance = math.fsum(
                summary[2] for summary in chain_summaries
            ) + maximum_chain_disagreement

        predicted = (
            spin_two_rotation[target_m + 2, source_m + 2]
            * _amplitude(tower[target_m], target)
        )
        scale = float(
            max(np.finfo(np.float64).eps, abs(rotated), abs(predicted))
        )
        raw_difference = float(abs(rotated - predicted))
        if exact_tiny:
            residual = raw_difference / scale
        else:
            roundoff = (
                64.0
                * np.finfo(np.float64).eps
                * max(1.0, abs(rotated), abs(predicted))
            )
            excess = max(
                0.0,
                raw_difference
                - _ROTATION_CONFIDENCE_SIGMAS * standard_error
                - drift_allowance
                - float(roundoff),
            )
            residual = excess / scale
        residuals.append(float(residual))
    result = max(residuals, default=0.0)
    if not math.isfinite(result):
        raise FloatingPointError("finite rotation residual is non-finite")
    return result


def evaluate_tower_diagnostics(
    tower: LadderTower,
    *,
    seed: int,
    burn_in_steps: int,
    sample_count: int,
    rotation_probes: int,
    tiny_support_by_m: Mapping[int, object] | None = None,
) -> Mapping[str, float]:
    """Evaluate four residuals without allocating a physical support.

    Tiny-support rotations retain their raw deterministic residual.  The
    production rotation field is the conservative excess left after seeded
    replica-chain sampling error and drift allowances are subtracted.
    """

    if not isinstance(tower, LadderTower):
        raise TypeError("tower must be a LadderTower")
    random_seed = _integer("seed", seed)
    burn_in = _integer("burn_in_steps", burn_in_steps)
    samples = _integer("sample_count", sample_count)
    probes = _integer("rotation_probes", rotation_probes)
    if random_seed < 0:
        raise ValueError("seed must be non-negative")
    if burn_in < 0:
        raise ValueError("burn_in_steps must be non-negative")
    if samples <= 0:
        raise ValueError("sample_count must be positive")
    if probes <= 0:
        raise ValueError("rotation_probes must be positive")
    rng = np.random.default_rng(random_seed)
    used_seeds: set[int] = set()
    exact_tiny = tiny_support_by_m is not None
    if tiny_support_by_m is None:
        sector_states = _sampled_states(
            tower,
            rng=rng,
            used_seeds=used_seeds,
            burn_in_steps=burn_in,
            sample_count=samples,
        )
    else:
        if not isinstance(tiny_support_by_m, Mapping):
            raise TypeError("tiny_support_by_m must be a mapping")
        sector_states = _validated_tiny_states(tower, tiny_support_by_m)

    result = {
        "lll_residual": 0.0,
        "particle_swap_residual": 0.0,
        "finite_rotation_residual": _finite_rotation_residual(
            tower,
            sector_states,
            rng=rng,
            used_seeds=used_seeds,
            burn_in_steps=burn_in,
            sample_count=samples,
            rotation_probes=probes,
            exact_tiny=exact_tiny,
        ),
        "tower_ladder_residual": _tower_ladder_residual(
            tower,
            sector_states,
        ),
    }
    if any(not math.isfinite(value) or value < 0.0 for value in result.values()):
        raise FloatingPointError("tower diagnostics must be finite and non-negative")
    return MappingProxyType(result)
