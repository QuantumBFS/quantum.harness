"""Joint, provenance-audited optimization of the shared L=0/L=2 model."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping, Sequence

import jax
import jax.numpy as jnp
import numpy as np
import optax
from flax import serialization

from challenge15.model import ModelConfig, ProjectedPfaffianNQS
from challenge15.spec import SphereSpec
from challenge15.vmc import coulomb_value


ENERGY_TOLERANCE_EC = 1e-4
GAP_RELATIVE_TOLERANCE = 0.002
OVERLAP_CHANGE_TOLERANCE = 1e-3
REQUIRED_RANK_DOUBLINGS = 2
REQUIRED_SEED_COUNT = 5
MINIMUM_PASSING_SEEDS = 4


@dataclass(frozen=True, slots=True)
class TrainConfig:
    steps: int
    rank: int
    seed: int
    batch_size: int = 8
    learning_rate: float = 1e-3
    weight_l0: float = 0.5
    weight_l2: float = 0.5
    hidden_width: int = 16
    depth: int = 1
    token_width: int = 4
    fourier_order: int = 2
    projection_block_size: int = 64

    def __post_init__(self) -> None:
        for name in (
            "steps",
            "rank",
            "batch_size",
            "hidden_width",
            "token_width",
            "fourier_order",
            "projection_block_size",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive Python integer")
        if isinstance(self.depth, bool) or not isinstance(self.depth, int) or self.depth < 0:
            raise ValueError("depth must be a nonnegative Python integer")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed must be a Python integer")
        if not np.isfinite(self.learning_rate) or self.learning_rate <= 0:
            raise ValueError("learning_rate must be finite and positive")
        weights = np.asarray((self.weight_l0, self.weight_l2), dtype=np.float64)
        if not np.all(np.isfinite(weights)) or np.any(weights <= 0):
            raise ValueError("sector weights must be finite and positive")
        if not np.isclose(float(np.sum(weights)), 1.0, rtol=0.0, atol=1e-14):
            raise ValueError("sector weights must sum to one")


@dataclass(frozen=True, slots=True)
class TrainingStep:
    index: int
    sector_order: tuple[int, int]
    loss: float
    energy_l0: float
    energy_l2: float
    norm_l0: float
    norm_l2: float
    gradient_norm_l0: float
    gradient_norm_l2: float
    acceptance_rate_l0: float | None
    acceptance_rate_l2: float | None
    diagnostic_parameter_state: str
    paired_batch_sha256: str
    prng_before: tuple[int, ...]
    prng_batch: tuple[int, ...]
    prng_after: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class TrainResult:
    shared_parameters: Any
    optimizer_state: Any
    steps: tuple[TrainingStep, ...]
    prng_provenance: tuple[tuple[str, tuple[int, ...]], ...]
    parameter_sha256: str
    rank: int
    seed: int


@dataclass(frozen=True, slots=True)
class RankEvaluation:
    rank: int
    energy_l0: float
    energy_l2: float
    sigma_diff_l0: float = 0.0
    sigma_diff_l2: float = 0.0
    sigma_diff_gap: float = 0.0
    overlap_l0: float | None = None
    overlap_l2: float | None = None

    @property
    def gap(self) -> float:
        return self.energy_l2 - self.energy_l0


@dataclass(frozen=True, slots=True)
class SeedRankEvaluation:
    rank: int
    seed: int
    energy_l0: float
    energy_l2: float
    overlap_l0: float | None = None
    overlap_l2: float | None = None

    @property
    def gap(self) -> float:
        return self.energy_l2 - self.energy_l0


@dataclass(frozen=True, slots=True)
class RankTransition:
    lower_rank: int
    upper_rank: int
    delta_energy_l0: float
    delta_energy_l2: float
    delta_gap: float
    energy_l0_bound: float
    energy_l2_bound: float
    gap_bound: float
    overlap_change_l0: float | None
    overlap_change_l2: float | None
    passed: bool


@dataclass(frozen=True, slots=True)
class RankConvergence:
    accepted: bool
    transitions: tuple[RankTransition, ...]
    reason: str


def train_joint_sectors(
    problem: Any,
    config: TrainConfig,
    *,
    initial_parameters: Any | None = None,
    initial_optimizer_state: Any | None = None,
) -> TrainResult:
    """Optimize both sectors from one parameter tree on identical coordinate batches.

    This deterministic path is intended for smoke optimization. Production
    acceptance remains the responsibility of exact/stochastic evaluation gates.
    """

    if not isinstance(config, TrainConfig):
        raise TypeError("config must be a TrainConfig")
    spec = _problem_spec(problem)
    model_config = ModelConfig(
        rank=config.rank,
        hidden_width=config.hidden_width,
        depth=config.depth,
        token_width=config.token_width,
        fourier_order=config.fourier_order,
        block_size=config.projection_block_size,
    )
    model = ProjectedPfaffianNQS(model_config)
    master = jax.random.key(config.seed)
    initial_master = _key_tuple(master)
    master, init_key = jax.random.split(master)
    initial_spinors = _coordinate_batch(init_key, 1, spec.particles)[0]
    optimizer = optax.adam(config.learning_rate)
    if initial_parameters is None:
        if initial_optimizer_state is not None:
            raise ValueError("initial optimizer state requires initial parameters")
        parameters = model.init(init_key, spec, initial_spinors, target_l=0)["params"]
        optimizer_state = optimizer.init(parameters)
    else:
        parameters = initial_parameters
        template = model.init(init_key, spec, initial_spinors, target_l=0)["params"]
        if jax.tree.structure(parameters) != jax.tree.structure(template):
            raise ValueError("initial parameter tree does not match TrainConfig")
        for supplied, expected in zip(
            jax.tree.leaves(parameters), jax.tree.leaves(template), strict=True
        ):
            if supplied.shape != expected.shape:
                raise ValueError("initial parameter shapes do not match TrainConfig")
        optimizer_state = (
            optimizer.init(parameters)
            if initial_optimizer_state is None
            else initial_optimizer_state
        )
    provenance: list[tuple[str, tuple[int, ...]]] = [
        ("master", initial_master),
        ("initialization", _key_tuple(init_key)),
        ("post_initialization", _key_tuple(master)),
    ]
    history: list[TrainingStep] = []

    for step_index in range(config.steps):
        before = _key_tuple(master)
        master, batch_key = jax.random.split(master)
        batch = _coordinate_batch(batch_key, config.batch_size, spec.particles)
        potentials = jnp.asarray(
            [coulomb_value(np.asarray(point), spec) for point in np.asarray(batch)],
            dtype=jnp.float64,
        )
        sector_order = (0, 2) if step_index % 2 == 0 else (2, 0)

        def sector_objective(candidate, target_l):
            amplitudes = jnp.stack(
                [
                    model.apply(
                        {"params": candidate},
                        spec,
                        point,
                        target_l=target_l,
                    )
                    for point in batch
                ]
            )
            weights = jnp.square(jnp.abs(amplitudes))
            norm = jnp.sum(weights)
            energy = jnp.sum(weights * potentials) / jnp.maximum(
                norm, jnp.finfo(jnp.float64).tiny
            )
            return energy, norm

        energies: dict[int, jax.Array] = {}
        norms: dict[int, jax.Array] = {}
        sector_gradients = {}
        for target_l in sector_order:
            (energies[target_l], norms[target_l]), sector_gradients[target_l] = (
                jax.value_and_grad(sector_objective, has_aux=True)(
                    parameters, target_l
                )
            )
        loss = config.weight_l0 * energies[0] + config.weight_l2 * energies[2]
        gradients = jax.tree.map(
            lambda lower, upper: (
                config.weight_l0 * lower + config.weight_l2 * upper
            ),
            sector_gradients[0],
            sector_gradients[2],
        )
        gradient_norms = {
            target_l: _tree_l2_norm(sector_gradients[target_l])
            for target_l in (0, 2)
        }
        updates, optimizer_state = optimizer.update(
            gradients, optimizer_state, parameters
        )
        parameters = optax.apply_updates(parameters, updates)
        values = np.asarray(
            (loss, energies[0], energies[2], norms[0], norms[2]),
            dtype=np.float64,
        )
        if not np.all(np.isfinite(values)):
            raise FloatingPointError("joint optimization produced nonfinite diagnostics")
        energy_l0, energy_l2, norm_l0, norm_l2 = map(float, values[1:])
        history.append(
            TrainingStep(
                index=step_index,
                sector_order=sector_order,
                loss=float(values[0]),
                energy_l0=energy_l0,
                energy_l2=energy_l2,
                norm_l0=norm_l0,
                norm_l2=norm_l2,
                gradient_norm_l0=gradient_norms[0],
                gradient_norm_l2=gradient_norms[2],
                acceptance_rate_l0=None,
                acceptance_rate_l2=None,
                diagnostic_parameter_state="pre_update",
                paired_batch_sha256=_array_sha256(np.asarray(batch)),
                prng_before=before,
                prng_batch=_key_tuple(batch_key),
                prng_after=_key_tuple(master),
            )
        )
        provenance.extend(
            (
                (f"step_{step_index}.before", before),
                (f"step_{step_index}.batch", _key_tuple(batch_key)),
                (f"step_{step_index}.after", _key_tuple(master)),
            )
        )

    return TrainResult(
        shared_parameters=parameters,
        optimizer_state=optimizer_state,
        steps=tuple(history),
        prng_provenance=tuple(provenance),
        parameter_sha256=hashlib.sha256(serialization.to_bytes(parameters)).hexdigest(),
        rank=config.rank,
        seed=config.seed,
    )


def analyze_rank_convergence(
    evaluations: Sequence[RankEvaluation | Mapping[str, Any]],
) -> RankConvergence:
    """Apply immutable exact-sum gates; exact statistical sigma is always zero."""

    records = tuple(_rank_evaluation(value) for value in evaluations)
    if any(
        value != 0.0
        for record in records
        for value in (
            record.sigma_diff_l0,
            record.sigma_diff_l2,
            record.sigma_diff_gap,
        )
    ):
        return RankConvergence(
            False,
            (),
            "exact rank convergence requires every sigma_diff to be zero",
        )
    return _analyze_rank_evaluations(records)


def analyze_stochastic_rank_convergence(
    evaluations: Sequence[SeedRankEvaluation | Mapping[str, Any]],
) -> RankConvergence:
    """Apply the same gates to identically paired stochastic seed records."""

    records = tuple(_seed_rank_evaluation(value) for value in evaluations)
    if not records:
        return RankConvergence(False, (), "stochastic rank evaluations are empty")
    identities = [(record.rank, record.seed) for record in records]
    if len(identities) != len(set(identities)):
        return RankConvergence(False, (), "stochastic rank records contain duplicates")
    ranks = sorted({record.rank for record in records})
    if any(upper != 2 * lower for lower, upper in zip(ranks, ranks[1:])):
        return RankConvergence(False, (), "ranks must be consecutive doublings")
    by_rank = {
        rank: {record.seed: record for record in records if record.rank == rank}
        for rank in ranks
    }
    seed_sets = [set(by_rank[rank]) for rank in ranks]
    if any(seeds != seed_sets[0] for seeds in seed_sets[1:]):
        return RankConvergence(
            False, (), "adjacent ranks require identical paired seed sets"
        )
    seeds = sorted(seed_sets[0])
    if len(seeds) < 2:
        return RankConvergence(
            False, (), "stochastic convergence requires at least two paired seeds"
        )
    aggregates: list[RankEvaluation] = []
    previous_rank: int | None = None
    for rank in ranks:
        current = [by_rank[rank][seed] for seed in seeds]
        sigma_l0 = sigma_l2 = sigma_gap = 0.0
        if previous_rank is not None:
            previous = [by_rank[previous_rank][seed] for seed in seeds]
            sigma_l0 = _paired_seed_standard_error(
                previous, current, "energy_l0"
            )
            sigma_l2 = _paired_seed_standard_error(
                previous, current, "energy_l2"
            )
            sigma_gap = _paired_seed_standard_error(previous, current, "gap")
        aggregates.append(
            RankEvaluation(
                rank=rank,
                energy_l0=float(np.mean([record.energy_l0 for record in current])),
                energy_l2=float(np.mean([record.energy_l2 for record in current])),
                sigma_diff_l0=sigma_l0,
                sigma_diff_l2=sigma_l2,
                sigma_diff_gap=sigma_gap,
                overlap_l0=_mean_optional_overlap(current, "overlap_l0"),
                overlap_l2=_mean_optional_overlap(current, "overlap_l2"),
            )
        )
        previous_rank = rank
    return _analyze_rank_evaluations(tuple(aggregates))


def _analyze_rank_evaluations(
    records: tuple[RankEvaluation, ...],
) -> RankConvergence:
    if len(records) < 3:
        return RankConvergence(False, (), "two consecutive rank doublings are required")
    if any(
        not np.isfinite(value)
        for record in records
        for value in (
            record.energy_l0,
            record.energy_l2,
            record.sigma_diff_l0,
            record.sigma_diff_l2,
            record.sigma_diff_gap,
        )
    ):
        return RankConvergence(False, (), "nonfinite energy or uncertainty")
    if any(
        value < 0
        for record in records
        for value in (
            record.sigma_diff_l0,
            record.sigma_diff_l2,
            record.sigma_diff_gap,
        )
    ):
        return RankConvergence(False, (), "uncertainty must be nonnegative")
    if any(record.gap <= 0 for record in records):
        return RankConvergence(False, (), "finite-size L=2 gap must remain positive")
    if any(upper.rank != 2 * lower.rank for lower, upper in zip(records, records[1:])):
        return RankConvergence(False, (), "ranks must be consecutive doublings")

    transitions = tuple(
        _rank_transition(lower, upper)
        for lower, upper in zip(records, records[1:])
    )
    final_two = transitions[-REQUIRED_RANK_DOUBLINGS:]
    accepted = (
        len(final_two) == REQUIRED_RANK_DOUBLINGS
        and all(item.passed for item in final_two)
    )
    if accepted:
        reason = "last two consecutive rank doublings pass every gate"
    elif any(
        item.energy_l0_bound > ENERGY_TOLERANCE_EC
        or item.energy_l2_bound > ENERGY_TOLERANCE_EC
        or item.gap_bound
        > GAP_RELATIVE_TOLERANCE * abs(records[index + 1].gap)
        for index, item in enumerate(transitions)
    ):
        reason = "energy/gap change plus uncertainty exceeds tolerance"
    else:
        reason = "overlap change exceeds tolerance"
    return RankConvergence(accepted, transitions, reason)


def _rank_transition(
    lower: RankEvaluation,
    upper: RankEvaluation,
) -> RankTransition:
    delta_l0 = abs(upper.energy_l0 - lower.energy_l0)
    delta_l2 = abs(upper.energy_l2 - lower.energy_l2)
    delta_gap = abs(upper.gap - lower.gap)
    bound_l0 = delta_l0 + 2.0 * upper.sigma_diff_l0
    bound_l2 = delta_l2 + 2.0 * upper.sigma_diff_l2
    bound_gap = delta_gap + 2.0 * upper.sigma_diff_gap
    overlap_l0 = _overlap_change(lower.overlap_l0, upper.overlap_l0)
    overlap_l2 = _overlap_change(lower.overlap_l2, upper.overlap_l2)
    overlap_pass = all(
        value is None or value <= OVERLAP_CHANGE_TOLERANCE
        for value in (overlap_l0, overlap_l2)
    )
    passed = (
        bound_l0 <= ENERGY_TOLERANCE_EC
        and bound_l2 <= ENERGY_TOLERANCE_EC
        and bound_gap <= GAP_RELATIVE_TOLERANCE * abs(upper.gap)
        and overlap_pass
    )
    return RankTransition(
        lower_rank=lower.rank,
        upper_rank=upper.rank,
        delta_energy_l0=delta_l0,
        delta_energy_l2=delta_l2,
        delta_gap=delta_gap,
        energy_l0_bound=bound_l0,
        energy_l2_bound=bound_l2,
        gap_bound=bound_gap,
        overlap_change_l0=overlap_l0,
        overlap_change_l2=overlap_l2,
        passed=passed,
    )


def _overlap_change(first: float | None, second: float | None) -> float | None:
    if first is None and second is None:
        return None
    if first is None or second is None:
        return float("inf")
    if not np.isfinite(first) or not np.isfinite(second):
        return float("inf")
    return abs(second - first)


def _rank_evaluation(value: RankEvaluation | Mapping[str, Any]) -> RankEvaluation:
    if isinstance(value, RankEvaluation):
        return value
    if isinstance(value, Mapping):
        return RankEvaluation(**value)
    raise TypeError("rank evaluations must be RankEvaluation objects or mappings")


def _seed_rank_evaluation(
    value: SeedRankEvaluation | Mapping[str, Any],
) -> SeedRankEvaluation:
    if isinstance(value, SeedRankEvaluation):
        return value
    if isinstance(value, Mapping):
        return SeedRankEvaluation(**value)
    raise TypeError(
        "stochastic evaluations must be SeedRankEvaluation objects or mappings"
    )


def _paired_seed_standard_error(previous, current, field: str) -> float:
    differences = np.asarray(
        [
            getattr(upper, field) - getattr(lower, field)
            for lower, upper in zip(previous, current, strict=True)
        ],
        dtype=np.float64,
    )
    return float(np.std(differences, ddof=1) / np.sqrt(differences.size))


def _mean_optional_overlap(records, field: str) -> float | None:
    values = [getattr(record, field) for record in records]
    if all(value is None for value in values):
        return None
    if any(value is None or not np.isfinite(value) for value in values):
        return float("nan")
    return float(np.mean(values))


def _problem_spec(problem: Any) -> SphereSpec:
    if isinstance(problem, SphereSpec):
        return problem
    if isinstance(problem, Mapping):
        candidate = problem.get("spec")
    else:
        candidate = getattr(problem, "spec", None)
    if isinstance(candidate, SphereSpec):
        return candidate
    particles = getattr(problem, "particles", None)
    if particles is not None:
        return SphereSpec(particles)
    raise TypeError("problem must be a SphereSpec or expose a SphereSpec as .spec")


def _coordinate_batch(key: jax.Array, batch_size: int, particles: int) -> jax.Array:
    components = jax.random.normal(
        key, (batch_size, particles, 2, 2), dtype=jnp.float64
    )
    spinors = components[..., 0] + 1j * components[..., 1]
    return spinors / jnp.linalg.norm(spinors, axis=-1, keepdims=True)


def _key_tuple(key: jax.Array) -> tuple[int, ...]:
    return tuple(int(value) for value in np.asarray(jax.random.key_data(key)).reshape(-1))


def _tree_l2_norm(tree) -> float:
    squared = sum(
        jnp.sum(jnp.square(jnp.abs(leaf))) for leaf in jax.tree.leaves(tree)
    )
    return float(jnp.sqrt(squared))


def _array_sha256(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(contiguous.dtype.str.encode("ascii"))
    digest.update(repr(contiguous.shape).encode("ascii"))
    digest.update(contiguous.tobytes())
    return digest.hexdigest()
