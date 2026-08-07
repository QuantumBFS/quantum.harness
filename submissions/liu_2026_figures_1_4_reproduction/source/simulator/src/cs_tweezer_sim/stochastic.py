"""Hidden stochastic scopes and physical shot-realization models.

The public controller never receives objects from this module.  A benchmark
author configures latent variables here, while the runtime exposes only raw
finite-shot records.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Hashable, Mapping, Protocol, Sequence

import numpy as np

from .backend import SampledTimeTrace, SimulationContext
from .contracts import Delay, ExperimentProgram, ParallelPlay, Play


BOLTZMANN_J_PER_K = 1.380649e-23
HBAR_J_S = 1.054571817e-34
ATOMIC_MASS_KG = 1.66053906660e-27
CS133_MASS_KG = 132.905451961 * ATOMIC_MASS_KG


class TemporalScope(str, Enum):
    """Lifetime of one latent draw."""

    FIXED = "fixed"
    ITERATION = "iteration"
    SHOT = "shot"
    WITHIN_SHOT = "within_shot"


@dataclass(frozen=True)
class GaussianBlockSpec:
    """A jointly Gaussian latent block with explicit temporal scope.

    ``iteration_ar1_rho`` is meaningful only for iteration-scoped blocks.  A
    nonzero value evolves the full multivariate draw as a stationary AR(1)
    process with marginal covariance ``covariance``.  The default zero keeps
    the original independent, lazily sampled iteration behavior, including
    its random-number consumption order.
    """

    name: str
    keys: tuple[str, ...]
    mean: tuple[float, ...]
    covariance: tuple[tuple[float, ...], ...]
    scope: TemporalScope
    iteration_ar1_rho: float = 0.0

    def __post_init__(self) -> None:
        if not self.name or not self.keys or len(set(self.keys)) != len(self.keys):
            raise ValueError("Gaussian block name and keys must be non-empty/unique")
        dimension = len(self.keys)
        covariance = np.asarray(self.covariance, dtype=float)
        rho = float(self.iteration_ar1_rho)
        if len(self.mean) != dimension or covariance.shape != (
            dimension,
            dimension,
        ):
            raise ValueError("Gaussian mean/covariance dimensions do not match keys")
        if not np.all(np.isfinite(covariance)) or not np.all(
            np.isfinite(self.mean)
        ):
            raise ValueError("Gaussian parameters must be finite")
        if not np.allclose(covariance, covariance.T, atol=1e-14, rtol=0.0):
            raise ValueError("Gaussian covariance must be symmetric")
        if float(np.min(np.linalg.eigvalsh(covariance))) < -1e-12:
            raise ValueError("Gaussian covariance must be positive semidefinite")
        if not math.isfinite(rho) or abs(rho) >= 1.0:
            raise ValueError(
                "iteration_ar1_rho must be finite with absolute value below one"
            )
        if rho != 0.0 and self.scope is not TemporalScope.ITERATION:
            raise ValueError(
                "nonzero iteration_ar1_rho requires iteration scope"
            )
        object.__setattr__(self, "iteration_ar1_rho", rho)


class StochasticScopeEngine:
    """Cache random draws at their declared physical time scope."""

    def __init__(
        self,
        blocks: Sequence[GaussianBlockSpec],
        *,
        seed: int | np.random.Generator = 0,
    ):
        self._blocks = {block.name: block for block in blocks}
        if len(self._blocks) != len(tuple(blocks)):
            raise ValueError("Gaussian block names must be unique")
        self._rng = (
            seed if isinstance(seed, np.random.Generator)
            else np.random.default_rng(seed)
        )
        self._fixed: dict[str, np.ndarray] = {}
        self._iteration: dict[str, np.ndarray] = {}
        self._iteration_ar1_state: dict[str, np.ndarray] = {}
        self._shot: dict[str, np.ndarray] = {}
        self._within: dict[tuple[str, Hashable], np.ndarray] = {}
        self._within_arrays: dict[tuple[str, tuple[int, ...]], np.ndarray] = {}
        self.iteration_index = -1
        self.shot_index = -1

    def begin_iteration(self) -> int:
        self.iteration_index += 1
        self.shot_index = -1
        self._iteration.clear()
        self._shot.clear()
        self._within.clear()
        self._within_arrays.clear()
        for block in self._blocks.values():
            if (
                block.scope is TemporalScope.ITERATION
                and block.iteration_ar1_rho != 0.0
            ):
                values = self._advance_iteration_ar1(block)
                self._iteration[block.name] = values
        return self.iteration_index

    def begin_shot(self) -> int:
        if self.iteration_index < 0:
            raise RuntimeError("begin_iteration must precede begin_shot")
        self.shot_index += 1
        self._shot.clear()
        self._within.clear()
        self._within_arrays.clear()
        return self.shot_index

    def standard_normal_array(
        self, name: str, shape: tuple[int, ...]
    ) -> np.ndarray:
        """Return one cached shot-scoped independent standard-normal array.

        This vectorized path is for FFT/state-space realization sources whose
        dimension depends on program duration and therefore cannot be declared
        as a fixed :class:`GaussianBlockSpec`.
        """

        if self.shot_index < 0:
            raise RuntimeError("standard-normal arrays require an active shot")
        if not name or not shape or any(size <= 0 for size in shape):
            raise ValueError("standard-normal array name/shape must be valid")
        key = (name, tuple(int(size) for size in shape))
        if key not in self._within_arrays:
            self._within_arrays[key] = np.asarray(
                self._rng.standard_normal(shape), dtype=float
            )
        return self._within_arrays[key].copy()

    def sample(
        self, name: str, *, within_shot_token: Hashable | None = None
    ) -> Mapping[str, float]:
        try:
            block = self._blocks[name]
        except KeyError as exc:
            raise KeyError(f"unknown Gaussian block: {name}") from exc
        cache: dict
        cache_key: str | tuple[str, Hashable]
        if block.scope is TemporalScope.FIXED:
            cache, cache_key = self._fixed, name
        elif block.scope is TemporalScope.ITERATION:
            if self.iteration_index < 0:
                raise RuntimeError("iteration-scoped draw requested too early")
            cache, cache_key = self._iteration, name
        elif block.scope is TemporalScope.SHOT:
            if self.shot_index < 0:
                raise RuntimeError("shot-scoped draw requested too early")
            cache, cache_key = self._shot, name
        else:
            if self.shot_index < 0 or within_shot_token is None:
                raise RuntimeError(
                    "within-shot draw requires an active shot and explicit token"
                )
            cache, cache_key = self._within, (name, within_shot_token)
        if cache_key not in cache:
            cache[cache_key] = self._draw(block)
        values = cache[cache_key]
        return {
            key: float(values[index]) for index, key in enumerate(block.keys)
        }

    def _draw(self, block: GaussianBlockSpec) -> np.ndarray:
        covariance = np.asarray(block.covariance, dtype=float)
        return self._draw_gaussian(
            np.asarray(block.mean, dtype=float), covariance
        )

    def _draw_gaussian(
        self, mean: np.ndarray, covariance: np.ndarray
    ) -> np.ndarray:
        if np.all(covariance == 0.0):
            return np.asarray(mean, dtype=float)
        return np.asarray(
            self._rng.multivariate_normal(
                np.asarray(mean, dtype=float),
                covariance,
                check_valid="raise",
            ),
            dtype=float,
        )

    def _advance_iteration_ar1(
        self, block: GaussianBlockSpec
    ) -> np.ndarray:
        """Advance one stationary multivariate iteration process.

        The first active iteration is sampled directly from the stationary
        marginal.  Later innovations have covariance
        ``(1 - rho**2) * covariance``.  Advancing happens in
        :meth:`begin_iteration`, not on first access, so an unqueried latent
        still evolves across physical blocks.
        """

        previous = self._iteration_ar1_state.get(block.name)
        if previous is None:
            values = self._draw(block)
        else:
            mean = np.asarray(block.mean, dtype=float)
            covariance = np.asarray(block.covariance, dtype=float)
            rho = block.iteration_ar1_rho
            innovation = self._draw_gaussian(
                np.zeros_like(mean), (1.0 - rho**2) * covariance
            )
            values = mean + rho * (previous - mean) + innovation
        values = np.asarray(values, dtype=float)
        self._iteration_ar1_state[block.name] = values
        return values


class ShotNoiseModel(Protocol):
    """Internal source of one hidden classical simulation context."""

    def blocks(self, n_atoms: int) -> tuple[GaussianBlockSpec, ...]:
        ...

    def context(
        self, engine: StochasticScopeEngine, n_atoms: int
    ) -> SimulationContext:
        ...


def experiment_program_duration_us(program: ExperimentProgram) -> float:
    """Return physical sequence duration without inspecting a backend."""

    duration = 0.0
    for operation in program.operations:
        if isinstance(operation, Play):
            duration += operation.pulse.duration_us
        elif isinstance(operation, ParallelPlay):
            duration += operation.duration_us
        elif isinstance(operation, Delay):
            duration += operation.duration_us
    return duration


def draw_shot_contexts(
    model: ShotNoiseModel,
    *,
    n_atoms: int,
    count: int,
    seed: int,
) -> tuple[SimulationContext, ...]:
    """Draw a reproducible validator-side sequence of shot contexts.

    Public runtimes draw the same kind of contexts internally and never return
    them.  This helper exists for paired offline mechanism ablations.
    """

    if count <= 0:
        raise ValueError("context count must be positive")
    engine = StochasticScopeEngine(model.blocks(n_atoms), seed=seed)
    engine.begin_iteration()
    contexts = []
    for _ in range(count):
        engine.begin_shot()
        contexts.append(model.context(engine, n_atoms))
    return tuple(contexts)


def draw_program_contexts(
    model: ShotNoiseModel,
    program: ExperimentProgram,
    *,
    n_atoms: int,
    count: int,
    seed: int,
) -> tuple[SimulationContext, ...]:
    """Draw validator-visible contexts including within-shot trajectories."""

    if count <= 0:
        raise ValueError("context count must be positive")
    engine = StochasticScopeEngine(model.blocks(n_atoms), seed=seed)
    engine.begin_iteration()
    contexts = []
    for _ in range(count):
        engine.begin_shot()
        if hasattr(model, "context_for_program"):
            context = model.context_for_program(engine, n_atoms, program)
        else:
            context = model.context(engine, n_atoms)
        contexts.append(context)
    return tuple(contexts)


@dataclass(frozen=True)
class CompositeShotNoiseModel:
    """Compose physical models while preserving their latent dependencies."""

    models: tuple[ShotNoiseModel, ...]

    def blocks(self, n_atoms: int) -> tuple[GaussianBlockSpec, ...]:
        blocks = tuple(
            block for model in self.models for block in model.blocks(n_atoms)
        )
        if len({block.name for block in blocks}) != len(blocks):
            raise ValueError("composed physical noise block names must be unique")
        return blocks

    def context(
        self, engine: StochasticScopeEngine, n_atoms: int
    ) -> SimulationContext:
        return SimulationContext.combine(
            *(model.context(engine, n_atoms) for model in self.models)
        )

    def context_for_program(
        self,
        engine: StochasticScopeEngine,
        n_atoms: int,
        program: ExperimentProgram,
    ) -> SimulationContext:
        return SimulationContext.combine(
            *(
                model.context_for_program(engine, n_atoms, program)
                if hasattr(model, "context_for_program")
                else model.context(engine, n_atoms)
                for model in self.models
            )
        )


@dataclass(frozen=True)
class OpticalWavevectorComponent:
    """One signed photon wavevector in a multiphoton transition.

    ``direction_xyz`` is normalized during validation.  Positive
    ``signed_multiplicity`` represents absorption and a negative value can
    represent stimulated emission in a Raman process.  The class contains no
    atom-species assumptions.
    """

    wavelength_nm: float
    direction_xyz: tuple[float, float, float]
    signed_multiplicity: float = 1.0

    def __post_init__(self) -> None:
        direction = np.asarray(self.direction_xyz, dtype=float)
        multiplicity = float(self.signed_multiplicity)
        if (
            not math.isfinite(self.wavelength_nm)
            or self.wavelength_nm <= 0
            or direction.shape != (3,)
            or not np.all(np.isfinite(direction))
            or not math.isfinite(multiplicity)
            or multiplicity == 0
        ):
            raise ValueError("optical wavevector component is invalid")
        norm = float(np.linalg.norm(direction))
        if norm == 0:
            raise ValueError("optical wavevector direction must be non-zero")
        object.__setattr__(
            self,
            "direction_xyz",
            tuple(float(value) for value in direction / norm),
        )
        object.__setattr__(self, "signed_multiplicity", multiplicity)

    @property
    def vector_rad_per_m(self) -> tuple[float, float, float]:
        magnitude = (
            self.signed_multiplicity
            * 2.0
            * math.pi
            / (self.wavelength_nm * 1e-9)
        )
        return tuple(magnitude * value for value in self.direction_xyz)


def effective_wavevector_vector_rad_per_m(
    components: Sequence[OpticalWavevectorComponent],
) -> tuple[float, float, float]:
    """Return the vector sum for an arbitrary multiphoton process."""

    terms = tuple(components)
    if not terms:
        raise ValueError("at least one optical wavevector component is required")
    vector = np.sum(
        np.asarray([term.vector_rad_per_m for term in terms], dtype=float),
        axis=0,
    )
    return tuple(float(value) for value in vector)


def effective_wavevector_magnitude_rad_per_m(
    components: Sequence[OpticalWavevectorComponent],
) -> float:
    """Return ``|k_eff|`` for an arbitrary multiphoton process."""

    return float(
        np.linalg.norm(effective_wavevector_vector_rad_per_m(components))
    )


def single_photon_effective_wavevector_rad_per_m(
    wavelength_nm: float,
) -> float:
    """Return ``2*pi/lambda`` for a one-photon transition."""

    return effective_wavevector_magnitude_rad_per_m(
        (OpticalWavevectorComponent(wavelength_nm, (0.0, 0.0, 1.0)),)
    )


def two_photon_effective_wavevector_rad_per_m(
    wavelengths_nm: tuple[float, float],
) -> float:
    """Return the legacy counter-propagating ladder-wavevector mismatch.

    The first beam points along ``+z`` and the second along ``-z``.  This
    preserves the original Cs convention while delegating the calculation to
    the species-independent vector composition.
    """

    if len(wavelengths_nm) != 2:
        raise ValueError("two-photon construction requires two wavelengths")
    return effective_wavevector_magnitude_rad_per_m(
        (
            OpticalWavevectorComponent(
                wavelengths_nm[0], (0.0, 0.0, 1.0)
            ),
            OpticalWavevectorComponent(
                wavelengths_nm[1], (0.0, 0.0, -1.0)
            ),
        )
    )


def thermal_velocity_sigma_m_per_s(
    temperature_uk: float, *, mass_kg: float = CS133_MASS_KG
) -> float:
    if temperature_uk < 0 or mass_kg <= 0:
        raise ValueError("temperature must be non-negative and mass positive")
    return math.sqrt(BOLTZMANN_J_PER_K * temperature_uk * 1e-6 / mass_kg)


def doppler_t2_us(
    temperature_uk: float,
    *,
    wavelengths_nm: tuple[float, float] = (459.4459, 1040.03),
    mass_kg: float = CS133_MASS_KG,
    effective_wavevector_rad_per_m: float | None = None,
) -> float:
    """Gaussian 1/e coherence time for a configured transition.

    ``effective_wavevector_rad_per_m`` is the species-independent path.  When
    omitted, the legacy two-wavelength Cs-compatible construction is used.
    """

    sigma_v = thermal_velocity_sigma_m_per_s(
        temperature_uk, mass_kg=mass_kg
    )
    if sigma_v == 0:
        return math.inf
    wavevector = (
        two_photon_effective_wavevector_rad_per_m(wavelengths_nm)
        if effective_wavevector_rad_per_m is None
        else float(effective_wavevector_rad_per_m)
    )
    if not math.isfinite(wavevector) or wavevector <= 0:
        raise ValueError("effective wavevector must be finite and positive")
    return math.sqrt(2.0) / (wavevector * sigma_v) * 1e6


def analytic_doppler_coherence(time_us: float, t2_us: float) -> float:
    """Return Gaussian two-photon Doppler coherence at the requested time."""

    if time_us < 0 or t2_us <= 0:
        raise ValueError("time must be non-negative and T2 positive")
    return math.exp(-((time_us / t2_us) ** 2))


@dataclass(frozen=True)
class DopplerNoiseModel:
    """Shot-static velocity mapped to one or more driven upper levels.

    Multiple upper levels driven by the same optical actuator can share the
    same atomic velocity and therefore the same Doppler shift.  The legacy
    ``rydberg_level`` remains the primary level for backward compatibility.
    """

    temperature_uk: float
    wavelengths_nm: tuple[float, float] = (459.4459, 1040.03)
    rydberg_level: str = "r"
    block_name: str = "doppler_velocity"
    mass_kg: float = CS133_MASS_KG
    effective_wavevector_rad_per_m: float | None = None
    additional_shifted_levels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        levels = (self.rydberg_level, *self.additional_shifted_levels)
        if (
            self.temperature_uk < 0
            or self.mass_kg <= 0
            or not self.rydberg_level
            or not self.block_name
            or any(not level for level in levels)
            or len(levels) != len(set(levels))
        ):
            raise ValueError("Doppler model parameters are invalid")
        if self.effective_wavevector_rad_per_m is not None and (
            not math.isfinite(self.effective_wavevector_rad_per_m)
            or self.effective_wavevector_rad_per_m <= 0
        ):
            raise ValueError("effective wavevector must be finite and positive")
        object.__setattr__(
            self,
            "additional_shifted_levels",
            tuple(self.additional_shifted_levels),
        )

    @property
    def wavevector_rad_per_m(self) -> float:
        """Configured scalar ``|k_eff|`` used for the velocity projection."""

        if self.effective_wavevector_rad_per_m is not None:
            return float(self.effective_wavevector_rad_per_m)
        return two_photon_effective_wavevector_rad_per_m(
            self.wavelengths_nm
        )

    def blocks(self, n_atoms: int) -> tuple[GaussianBlockSpec, ...]:
        sigma = thermal_velocity_sigma_m_per_s(
            self.temperature_uk, mass_kg=self.mass_kg
        )
        return (
            GaussianBlockSpec(
                self.block_name,
                tuple(f"atom_{atom}_velocity_m_per_s" for atom in range(n_atoms)),
                (0.0,) * n_atoms,
                tuple(
                    tuple(sigma**2 if row == column else 0.0 for column in range(n_atoms))
                    for row in range(n_atoms)
                ),
                TemporalScope.SHOT,
            ),
        )

    def context(
        self, engine: StochasticScopeEngine, n_atoms: int
    ) -> SimulationContext:
        velocities = engine.sample(self.block_name)
        wavevector = self.wavevector_rad_per_m
        offsets = {
            (atom, level): (
                wavevector
                * velocities[f"atom_{atom}_velocity_m_per_s"]
                * 1e-6
            )
            for atom in range(n_atoms)
            for level in (
                self.rydberg_level,
                *self.additional_shifted_levels,
            )
        }
        return SimulationContext(level_energy_offsets_rad_per_us=offsets)


def harmonic_position_sigma_um(
    temperature_uk: float,
    trap_frequency_khz: float,
    *,
    mass_kg: float = CS133_MASS_KG,
) -> float:
    """Exact thermal quantum-harmonic-oscillator position standard deviation."""

    if temperature_uk <= 0 or trap_frequency_khz <= 0 or mass_kg <= 0:
        raise ValueError("temperature, frequency and mass must be positive")
    omega = 2.0 * math.pi * trap_frequency_khz * 1e3
    argument = (
        HBAR_J_S * omega
        / (2.0 * BOLTZMANN_J_PER_K * temperature_uk * 1e-6)
    )
    coth = 1.0 / math.tanh(argument)
    variance_m2 = HBAR_J_S / (2.0 * mass_kg * omega) * coth
    return math.sqrt(variance_m2) * 1e6


@dataclass(frozen=True)
class GaussianBeamCouplingSpec:
    """One channel/atom Gaussian transverse-mode coupling."""

    channel: str
    atom: int
    waist_um: float
    center_um: tuple[float, float, float]

    def __post_init__(self) -> None:
        if not self.channel or self.atom < 0 or self.waist_um <= 0:
            raise ValueError("beam channel/atom/waist is invalid")


@dataclass(frozen=True)
class ThermalPositionRealization:
    """Validator-visible hidden positions and their derived context."""

    positions_um: tuple[tuple[float, float, float], ...]
    context: SimulationContext


@dataclass(frozen=True)
class ThermalPositionNoiseModel:
    """One position draw jointly controls beam coupling and pair blockade."""

    nominal_positions_um: tuple[tuple[float, float, float], ...]
    sigma_xyz_um: tuple[tuple[float, float, float], ...]
    beams: tuple[GaussianBeamCouplingSpec, ...]
    pair_interaction_label: str = "measured blockade"
    blockade_power: float = 6.0
    block_name: str = "thermal_position"

    def __post_init__(self) -> None:
        if len(self.nominal_positions_um) != len(self.sigma_xyz_um):
            raise ValueError("one position sigma tuple is required per atom")
        if any(value < 0 for sigma in self.sigma_xyz_um for value in sigma):
            raise ValueError("position sigmas must be non-negative")

    def blocks(self, n_atoms: int) -> tuple[GaussianBlockSpec, ...]:
        if n_atoms != len(self.nominal_positions_um):
            raise ValueError("thermal position model atom count mismatch")
        keys = tuple(
            f"atom_{atom}_{axis}_displacement_um"
            for atom in range(n_atoms)
            for axis in ("x", "y", "z")
        )
        variances = tuple(
            value**2 for sigma in self.sigma_xyz_um for value in sigma
        )
        dimension = len(keys)
        return (
            GaussianBlockSpec(
                self.block_name,
                keys,
                (0.0,) * dimension,
                tuple(
                    tuple(
                        variances[row] if row == column else 0.0
                        for column in range(dimension)
                    )
                    for row in range(dimension)
                ),
                TemporalScope.SHOT,
            ),
        )

    def realization(
        self, engine: StochasticScopeEngine, n_atoms: int
    ) -> ThermalPositionRealization:
        draw = engine.sample(self.block_name)
        positions = tuple(
            tuple(
                self.nominal_positions_um[atom][axis_index]
                + draw[
                    f"atom_{atom}_{('x', 'y', 'z')[axis_index]}_displacement_um"
                ]
                for axis_index in range(3)
            )
            for atom in range(n_atoms)
        )
        amplitudes: dict[tuple[str, int], float] = {}
        for beam in self.beams:
            if beam.atom >= n_atoms:
                raise ValueError("beam references an atom outside the model")
            actual = positions[beam.atom]
            nominal = self.nominal_positions_um[beam.atom]
            actual_rho2 = (
                (actual[0] - beam.center_um[0]) ** 2
                + (actual[1] - beam.center_um[1]) ** 2
            )
            nominal_rho2 = (
                (nominal[0] - beam.center_um[0]) ** 2
                + (nominal[1] - beam.center_um[1]) ** 2
            )
            amplitudes[(beam.channel, beam.atom)] = math.exp(
                -(actual_rho2 - nominal_rho2) / beam.waist_um**2
            )
        interactions: dict[tuple[int, int, str], float] = {}
        for first in range(n_atoms):
            for second in range(first + 1, n_atoms):
                nominal_distance = math.dist(
                    self.nominal_positions_um[first],
                    self.nominal_positions_um[second],
                )
                actual_distance = math.dist(positions[first], positions[second])
                if nominal_distance <= 0 or actual_distance <= 0:
                    raise ValueError("pair distances must be positive")
                interactions[
                    (first, second, self.pair_interaction_label)
                ] = (nominal_distance / actual_distance) ** self.blockade_power
        return ThermalPositionRealization(
            positions,
            SimulationContext(
                channel_amplitude_scales=amplitudes,
                pair_interaction_scales=interactions,
            ),
        )

    def context(
        self, engine: StochasticScopeEngine, n_atoms: int
    ) -> SimulationContext:
        return self.realization(engine, n_atoms).context


@dataclass(frozen=True)
class PulseEnergyNoiseModel:
    """Channel pulse-energy noise plus optional atom-local Rabi error.

    ``energy_scope=ITERATION`` models one common pulse-energy calibration state
    shared by every candidate in a physical block.  In that mode
    ``iteration_ar1_rho`` can add stationary correlation across blocks.  The
    default remains the original independent shot-static model.
    """

    channels: tuple[str, ...]
    energy_covariance: tuple[tuple[float, ...], ...]
    local_rabi_fractional_sigma: float = 0.0
    energy_block_name: str = "pulse_energy"
    local_block_name: str = "local_rabi"
    energy_scope: TemporalScope = TemporalScope.SHOT
    iteration_ar1_rho: float = 0.0

    def __post_init__(self) -> None:
        if not self.channels or len(set(self.channels)) != len(self.channels):
            raise ValueError("pulse-energy channels must be non-empty and unique")
        if self.local_rabi_fractional_sigma < 0:
            raise ValueError("local Rabi sigma must be non-negative")

    def blocks(self, n_atoms: int) -> tuple[GaussianBlockSpec, ...]:
        dimension = len(self.channels)
        energy = GaussianBlockSpec(
            self.energy_block_name,
            tuple(f"channel_{channel}_fractional_energy" for channel in self.channels),
            (0.0,) * dimension,
            self.energy_covariance,
            self.energy_scope,
            iteration_ar1_rho=self.iteration_ar1_rho,
        )
        if self.local_rabi_fractional_sigma == 0:
            return (energy,)
        local_keys = tuple(
            f"channel_{channel}_atom_{atom}_fractional_rabi"
            for channel in self.channels
            for atom in range(n_atoms)
        )
        local_dimension = len(local_keys)
        variance = self.local_rabi_fractional_sigma**2
        local = GaussianBlockSpec(
            self.local_block_name,
            local_keys,
            (0.0,) * local_dimension,
            tuple(
                tuple(variance if row == column else 0.0 for column in range(local_dimension))
                for row in range(local_dimension)
            ),
            TemporalScope.SHOT,
        )
        return energy, local

    def context(
        self, engine: StochasticScopeEngine, n_atoms: int
    ) -> SimulationContext:
        energy = engine.sample(self.energy_block_name)
        local = (
            engine.sample(self.local_block_name)
            if self.local_rabi_fractional_sigma > 0
            else {}
        )
        amplitudes: dict[tuple[str, int], float] = {}
        for channel in self.channels:
            fractional_energy = energy[
                f"channel_{channel}_fractional_energy"
            ]
            common_amplitude = math.sqrt(max(0.0, 1.0 + fractional_energy))
            for atom in range(n_atoms):
                local_scale = 1.0 + local.get(
                    f"channel_{channel}_atom_{atom}_fractional_rabi", 0.0
                )
                amplitudes[(channel, atom)] = (
                    common_amplitude * max(0.0, local_scale)
                )
        return SimulationContext(channel_amplitude_scales=amplitudes)


def _identity_matrix_tuple(dimension: int) -> tuple[tuple[float, ...], ...]:
    return tuple(
        tuple(1.0 if row == column else 0.0 for column in range(dimension))
        for row in range(dimension)
    )


def _validated_correlation(
    matrix: tuple[tuple[float, ...], ...],
    dimension: int,
    *,
    label: str,
) -> tuple[tuple[float, ...], ...]:
    normalized = matrix or _identity_matrix_tuple(dimension)
    values = np.asarray(normalized, dtype=float)
    if values.shape != (dimension, dimension):
        raise ValueError(f"{label} correlation dimension mismatch")
    if not np.allclose(values, values.T, atol=1e-14, rtol=0.0):
        raise ValueError(f"{label} correlation must be symmetric")
    if not np.allclose(np.diag(values), 1.0, atol=1e-14, rtol=0.0):
        raise ValueError(f"{label} correlation diagonal must equal one")
    if float(np.min(np.linalg.eigvalsh(values))) < -1e-12:
        raise ValueError(f"{label} correlation must be positive semidefinite")
    return tuple(tuple(float(value) for value in row) for row in values)


@dataclass(frozen=True)
class LaserPhaseFrequencyRealization:
    """Validator-side time series generated for one shot."""

    phase_traces_rad: Mapping[str, SampledTimeTrace]
    frequency_traces_hz: Mapping[str, SampledTimeTrace]
    context: SimulationContext


@dataclass(frozen=True)
class LaserPhaseFrequencyNoiseModel:
    """Correlated laser/RF phase generated from physical frequency processes.

    The model combines a shot-quasistatic carrier offset, white frequency
    noise represented by Wiener phase increments, and stationary
    Ornstein--Uhlenbeck frequency noise.  It emits only phase trajectories, so
    no frequency component is double-counted as a detuning.
    """

    channels: tuple[str, ...]
    lorentzian_linewidth_fwhm_hz: tuple[float, ...]
    quasistatic_frequency_covariance_hz2: tuple[tuple[float, ...], ...]
    ou_frequency_sigma_hz: tuple[float, ...]
    sample_interval_us: float
    ou_correlation_time_us: float = 1.0
    phase_diffusion_correlation: tuple[tuple[float, ...], ...] = ()
    ou_innovation_correlation: tuple[tuple[float, ...], ...] = ()
    block_prefix: str = "laser_phase_frequency"

    def __post_init__(self) -> None:
        dimension = len(self.channels)
        if (
            not self.channels
            or len(set(self.channels)) != dimension
            or len(self.lorentzian_linewidth_fwhm_hz) != dimension
            or len(self.ou_frequency_sigma_hz) != dimension
        ):
            raise ValueError("laser channels and parameter vectors must match")
        if (
            self.sample_interval_us <= 0
            or self.ou_correlation_time_us <= 0
            or any(value < 0 for value in self.lorentzian_linewidth_fwhm_hz)
            or any(value < 0 for value in self.ou_frequency_sigma_hz)
        ):
            raise ValueError("laser noise scales and time constants must be positive")
        covariance = np.asarray(
            self.quasistatic_frequency_covariance_hz2, dtype=float
        )
        if covariance.shape != (dimension, dimension):
            raise ValueError("quasistatic frequency covariance dimension mismatch")
        if not np.allclose(covariance, covariance.T, atol=1e-14, rtol=0.0):
            raise ValueError("quasistatic frequency covariance must be symmetric")
        if float(np.min(np.linalg.eigvalsh(covariance))) < -1e-12:
            raise ValueError(
                "quasistatic frequency covariance must be positive semidefinite"
            )
        object.__setattr__(
            self,
            "phase_diffusion_correlation",
            _validated_correlation(
                self.phase_diffusion_correlation,
                dimension,
                label="phase diffusion",
            ),
        )
        object.__setattr__(
            self,
            "ou_innovation_correlation",
            _validated_correlation(
                self.ou_innovation_correlation,
                dimension,
                label="OU innovation",
            ),
        )

    def blocks(self, n_atoms: int) -> tuple[GaussianBlockSpec, ...]:
        del n_atoms
        keys = tuple(f"channel_{channel}" for channel in self.channels)
        dimension = len(keys)
        blocks = [
            GaussianBlockSpec(
                f"{self.block_prefix}_quasistatic_hz",
                keys,
                (0.0,) * dimension,
                self.quasistatic_frequency_covariance_hz2,
                TemporalScope.SHOT,
            ),
            GaussianBlockSpec(
                f"{self.block_prefix}_white_standard",
                keys,
                (0.0,) * dimension,
                self.phase_diffusion_correlation,
                TemporalScope.WITHIN_SHOT,
            ),
            GaussianBlockSpec(
                f"{self.block_prefix}_ou_initial_standard",
                keys,
                (0.0,) * dimension,
                self.ou_innovation_correlation,
                TemporalScope.SHOT,
            ),
            GaussianBlockSpec(
                f"{self.block_prefix}_ou_innovation_standard",
                keys,
                (0.0,) * dimension,
                self.ou_innovation_correlation,
                TemporalScope.WITHIN_SHOT,
            ),
        ]
        return tuple(blocks)

    def realization(
        self,
        engine: StochasticScopeEngine,
        n_atoms: int,
        duration_us: float,
    ) -> LaserPhaseFrequencyRealization:
        if duration_us < 0:
            raise ValueError("program duration must be non-negative")
        quasi_draw = engine.sample(f"{self.block_prefix}_quasistatic_hz")
        initial_draw = engine.sample(
            f"{self.block_prefix}_ou_initial_standard"
        )
        quasi = np.asarray(
            [quasi_draw[f"channel_{channel}"] for channel in self.channels],
            dtype=float,
        )
        ou_sigma = np.asarray(self.ou_frequency_sigma_hz, dtype=float)
        ou_frequency = ou_sigma * np.asarray(
            [initial_draw[f"channel_{channel}"] for channel in self.channels],
            dtype=float,
        )
        linewidth = np.asarray(self.lorentzian_linewidth_fwhm_hz, dtype=float)
        interval_s = self.sample_interval_us * 1e-6
        ou_decay = math.exp(
            -self.sample_interval_us / self.ou_correlation_time_us
        )
        ou_innovation_scale = ou_sigma * math.sqrt(1.0 - ou_decay**2)
        step_count = max(
            1, int(math.ceil(duration_us / self.sample_interval_us))
        )
        phase = np.zeros(len(self.channels), dtype=float)
        phase_values = [[0.0] for _ in self.channels]
        frequency_values = [
            [float(quasi[index] + ou_frequency[index])]
            for index in range(len(self.channels))
        ]
        for step in range(step_count):
            white_draw = engine.sample(
                f"{self.block_prefix}_white_standard",
                within_shot_token=("white", step),
            )
            white = np.asarray(
                [white_draw[f"channel_{channel}"] for channel in self.channels],
                dtype=float,
            )
            phase += (
                2.0 * math.pi * (quasi + ou_frequency) * interval_s
                + np.sqrt(2.0 * math.pi * linewidth * interval_s) * white
            )
            for index, value in enumerate(phase):
                phase_values[index].append(float(value))

            innovation_draw = engine.sample(
                f"{self.block_prefix}_ou_innovation_standard",
                within_shot_token=("ou", step),
            )
            innovation = np.asarray(
                [
                    innovation_draw[f"channel_{channel}"]
                    for channel in self.channels
                ],
                dtype=float,
            )
            ou_frequency = ou_decay * ou_frequency + (
                ou_innovation_scale * innovation
            )
            for index, value in enumerate(quasi + ou_frequency):
                frequency_values[index].append(float(value))

        phase_traces = {
            channel: SampledTimeTrace(
                self.sample_interval_us,
                tuple(phase_values[index]),
                interpolation="linear",
            )
            for index, channel in enumerate(self.channels)
        }
        frequency_traces = {
            channel: SampledTimeTrace(
                self.sample_interval_us,
                tuple(frequency_values[index]),
                interpolation="zoh",
            )
            for index, channel in enumerate(self.channels)
        }
        context = SimulationContext(
            channel_phase_offset_traces_rad={
                (channel, atom): phase_traces[channel]
                for channel in self.channels
                for atom in range(n_atoms)
            }
        )
        return LaserPhaseFrequencyRealization(
            phase_traces,
            frequency_traces,
            context,
        )

    def context(
        self, engine: StochasticScopeEngine, n_atoms: int
    ) -> SimulationContext:
        return self.realization(engine, n_atoms, 0.0).context

    def context_for_program(
        self,
        engine: StochasticScopeEngine,
        n_atoms: int,
        program: ExperimentProgram,
    ) -> SimulationContext:
        return self.realization(
            engine,
            n_atoms,
            experiment_program_duration_us(program),
        ).context


@dataclass(frozen=True)
class ZeemanLevelShiftSpec:
    """Scalar energy polynomial for one configured physical level."""

    level: str
    linear_rad_per_us_per_g: float = 0.0
    quadratic_rad_per_us_per_g2: float = 0.0

    def __post_init__(self) -> None:
        if not self.level:
            raise ValueError("Zeeman level name must be non-empty")
        if not np.all(
            np.isfinite(
                (
                    self.linear_rad_per_us_per_g,
                    self.quadratic_rad_per_us_per_g2,
                )
            )
        ):
            raise ValueError("Zeeman coefficients must be finite")

    def energy_rad_per_us(self, field_g: float) -> float:
        return (
            self.linear_rad_per_us_per_g * field_g
            + self.quadratic_rad_per_us_per_g2 * field_g**2
        )


@dataclass(frozen=True)
class MagneticFieldRealization:
    """Validator-side magnetic fields and their Hamiltonian context."""

    base_fields_g: tuple[float, ...]
    field_traces_g: tuple[SampledTimeTrace, ...]
    context: SimulationContext


@dataclass(frozen=True)
class MagneticFieldNoiseModel:
    """Iteration/shot/within-shot magnetic noise mapped through Zeeman shifts."""

    bias_field_g: float
    level_shifts: tuple[ZeemanLevelShiftSpec, ...]
    iteration_common_sigma_g: float = 0.0
    shot_common_sigma_g: float = 0.0
    shot_local_sigma_g: float = 0.0
    within_shot_common_sigma_g: float = 0.0
    within_shot_local_sigma_g: float = 0.0
    within_shot_correlation_time_us: float = 1.0
    sample_interval_us: float = 0.01
    block_prefix: str = "magnetic_field"

    def __post_init__(self) -> None:
        if (
            not self.level_shifts
            or len({spec.level for spec in self.level_shifts})
            != len(self.level_shifts)
        ):
            raise ValueError("Zeeman level shifts must be non-empty and unique")
        sigmas = (
            self.iteration_common_sigma_g,
            self.shot_common_sigma_g,
            self.shot_local_sigma_g,
            self.within_shot_common_sigma_g,
            self.within_shot_local_sigma_g,
        )
        if (
            not np.isfinite(self.bias_field_g)
            or any(value < 0 for value in sigmas)
            or self.within_shot_correlation_time_us <= 0
            or self.sample_interval_us <= 0
        ):
            raise ValueError("magnetic-field scales and times must be valid")

    def blocks(self, n_atoms: int) -> tuple[GaussianBlockSpec, ...]:
        local_keys = tuple(f"atom_{atom}" for atom in range(n_atoms))
        local_covariance = tuple(
            tuple(
                self.shot_local_sigma_g**2 if row == column else 0.0
                for column in range(n_atoms)
            )
            for row in range(n_atoms)
        )
        within_keys = ("common",) + local_keys
        within_dimension = len(within_keys)
        return (
            GaussianBlockSpec(
                f"{self.block_prefix}_iteration_common_g",
                ("common",),
                (0.0,),
                ((self.iteration_common_sigma_g**2,),),
                TemporalScope.ITERATION,
            ),
            GaussianBlockSpec(
                f"{self.block_prefix}_shot_common_g",
                ("common",),
                (0.0,),
                ((self.shot_common_sigma_g**2,),),
                TemporalScope.SHOT,
            ),
            GaussianBlockSpec(
                f"{self.block_prefix}_shot_local_g",
                local_keys,
                (0.0,) * n_atoms,
                local_covariance,
                TemporalScope.SHOT,
            ),
            GaussianBlockSpec(
                f"{self.block_prefix}_within_initial_standard",
                within_keys,
                (0.0,) * within_dimension,
                _identity_matrix_tuple(within_dimension),
                TemporalScope.SHOT,
            ),
            GaussianBlockSpec(
                f"{self.block_prefix}_within_innovation_standard",
                within_keys,
                (0.0,) * within_dimension,
                _identity_matrix_tuple(within_dimension),
                TemporalScope.WITHIN_SHOT,
            ),
        )

    def realization(
        self,
        engine: StochasticScopeEngine,
        n_atoms: int,
        duration_us: float,
    ) -> MagneticFieldRealization:
        if duration_us < 0:
            raise ValueError("program duration must be non-negative")
        iteration = engine.sample(
            f"{self.block_prefix}_iteration_common_g"
        )["common"]
        shot_common = engine.sample(
            f"{self.block_prefix}_shot_common_g"
        )["common"]
        local_draw = engine.sample(f"{self.block_prefix}_shot_local_g")
        base_fields = tuple(
            self.bias_field_g
            + iteration
            + shot_common
            + local_draw[f"atom_{atom}"]
            for atom in range(n_atoms)
        )
        static_offsets = {
            (atom, spec.level): spec.energy_rad_per_us(base_fields[atom])
            - spec.energy_rad_per_us(self.bias_field_g)
            for atom in range(n_atoms)
            for spec in self.level_shifts
        }

        within_active = (
            self.within_shot_common_sigma_g > 0
            or self.within_shot_local_sigma_g > 0
        )
        if not within_active or duration_us == 0:
            return MagneticFieldRealization(
                base_fields,
                (),
                SimulationContext(
                    level_energy_offsets_rad_per_us=static_offsets
                ),
            )

        initial = engine.sample(
            f"{self.block_prefix}_within_initial_standard"
        )
        common = self.within_shot_common_sigma_g * initial["common"]
        local = np.asarray(
            [
                self.within_shot_local_sigma_g
                * initial[f"atom_{atom}"]
                for atom in range(n_atoms)
            ],
            dtype=float,
        )
        decay = math.exp(
            -self.sample_interval_us
            / self.within_shot_correlation_time_us
        )
        innovation_factor = math.sqrt(1.0 - decay**2)
        step_count = max(
            1, int(math.ceil(duration_us / self.sample_interval_us))
        )
        field_values = [
            [base_fields[atom] + common + local[atom]]
            for atom in range(n_atoms)
        ]
        for step in range(step_count):
            innovation = engine.sample(
                f"{self.block_prefix}_within_innovation_standard",
                within_shot_token=step,
            )
            common = decay * common + (
                self.within_shot_common_sigma_g
                * innovation_factor
                * innovation["common"]
            )
            for atom in range(n_atoms):
                local[atom] = decay * local[atom] + (
                    self.within_shot_local_sigma_g
                    * innovation_factor
                    * innovation[f"atom_{atom}"]
                )
                field_values[atom].append(
                    float(base_fields[atom] + common + local[atom])
                )
        field_traces = tuple(
            SampledTimeTrace(
                self.sample_interval_us,
                tuple(values),
                interpolation="linear",
            )
            for values in field_values
        )
        energy_traces = {
            (atom, spec.level): SampledTimeTrace(
                self.sample_interval_us,
                tuple(
                    spec.energy_rad_per_us(field)
                    - spec.energy_rad_per_us(base_fields[atom])
                    for field in field_values[atom]
                ),
                interpolation="linear",
            )
            for atom in range(n_atoms)
            for spec in self.level_shifts
        }
        return MagneticFieldRealization(
            base_fields,
            field_traces,
            SimulationContext(
                level_energy_offsets_rad_per_us=static_offsets,
                level_energy_offset_traces_rad_per_us=energy_traces,
            ),
        )

    def context(
        self, engine: StochasticScopeEngine, n_atoms: int
    ) -> SimulationContext:
        return self.realization(engine, n_atoms, 0.0).context

    def context_for_program(
        self,
        engine: StochasticScopeEngine,
        n_atoms: int,
        program: ExperimentProgram,
    ) -> SimulationContext:
        return self.realization(
            engine,
            n_atoms,
            experiment_program_duration_us(program),
        ).context


@dataclass(frozen=True)
class OneSidedCrossSpectralDensity:
    """Sampled one-sided frequency-noise cross spectral density.

    Each matrix has units Hz^2/Hz and must be Hermitian positive semidefinite.
    Linear interpolation between adjacent matrices preserves both properties.
    Values outside the supplied frequency range are zero.
    """

    channels: tuple[str, ...]
    frequencies_hz: tuple[float, ...]
    csd_hz2_per_hz: tuple[tuple[tuple[complex, ...], ...], ...]

    def __post_init__(self) -> None:
        dimension = len(self.channels)
        frequencies = np.asarray(self.frequencies_hz, dtype=float)
        if (
            not self.channels
            or len(set(self.channels)) != dimension
            or len(frequencies) < 2
            or len(self.csd_hz2_per_hz) != len(frequencies)
        ):
            raise ValueError("cross-PSD channels/frequency samples are invalid")
        if (
            not np.all(np.isfinite(frequencies))
            or frequencies[0] < 0
            or np.any(np.diff(frequencies) <= 0)
        ):
            raise ValueError("cross-PSD frequencies must be finite and increasing")
        normalized = []
        for matrix in self.csd_hz2_per_hz:
            values = np.asarray(matrix, dtype=complex)
            if values.shape != (dimension, dimension):
                raise ValueError("cross-PSD matrix dimension mismatch")
            if not np.all(np.isfinite(values)):
                raise ValueError("cross-PSD matrices must be finite")
            if not np.allclose(values, values.conj().T, atol=1e-12, rtol=0.0):
                raise ValueError("cross-PSD matrices must be Hermitian")
            if np.max(np.abs(np.imag(np.diag(values)))) > 1e-12:
                raise ValueError("cross-PSD auto spectra must be real")
            if float(np.min(np.linalg.eigvalsh(values))) < -1e-10:
                raise ValueError("cross-PSD matrices must be positive semidefinite")
            normalized.append(
                tuple(
                    tuple(complex(value) for value in row)
                    for row in values
                )
            )
        object.__setattr__(
            self,
            "frequencies_hz",
            tuple(float(value) for value in frequencies),
        )
        object.__setattr__(self, "csd_hz2_per_hz", tuple(normalized))

    def matrix_at(self, frequency_hz: float) -> np.ndarray:
        """Return the linearly interpolated Hermitian PSD matrix."""

        frequencies = np.asarray(self.frequencies_hz)
        if frequency_hz < frequencies[0] or frequency_hz > frequencies[-1]:
            return np.zeros(
                (len(self.channels), len(self.channels)), dtype=complex
            )
        upper = int(np.searchsorted(frequencies, frequency_hz, side="left"))
        if upper == 0:
            return np.asarray(self.csd_hz2_per_hz[0], dtype=complex)
        if upper == len(frequencies):
            return np.asarray(self.csd_hz2_per_hz[-1], dtype=complex)
        if frequencies[upper] == frequency_hz:
            return np.asarray(self.csd_hz2_per_hz[upper], dtype=complex)
        lower = upper - 1
        fraction = (
            (frequency_hz - frequencies[lower])
            / (frequencies[upper] - frequencies[lower])
        )
        return (
            (1.0 - fraction)
            * np.asarray(self.csd_hz2_per_hz[lower], dtype=complex)
            + fraction
            * np.asarray(self.csd_hz2_per_hz[upper], dtype=complex)
        )

    def integrated_auto_variances_hz2(self) -> tuple[float, ...]:
        """Trapezoidal integral of each supplied auto PSD."""

        matrices = np.asarray(self.csd_hz2_per_hz, dtype=complex)
        return tuple(
            float(
                np.trapezoid(
                    np.real(matrices[:, index, index]),
                    np.asarray(self.frequencies_hz),
                )
            )
            for index in range(len(self.channels))
        )


@lru_cache(maxsize=32)
def _spectral_shaping_factors(
    spectrum: OneSidedCrossSpectralDensity,
    sample_count: int,
    dt_s: float,
    remove_dc: bool,
) -> np.ndarray:
    """Cache per-grid CSD square roots including one-sided normalization."""

    sample_rate_hz = 1.0 / dt_s
    frequencies = np.fft.rfftfreq(sample_count, d=dt_s)
    dimension = len(spectrum.channels)
    factors = np.zeros(
        (len(frequencies), dimension, dimension), dtype=complex
    )
    for index, frequency in enumerate(frequencies):
        if index == 0 and remove_dc:
            continue
        matrix = spectrum.matrix_at(float(frequency))
        eigenvalues, eigenvectors = np.linalg.eigh(matrix)
        factor = eigenvectors @ np.diag(
            np.sqrt(np.maximum(eigenvalues, 0.0))
        ) @ eigenvectors.conj().T
        endpoint = index == 0 or (
            sample_count % 2 == 0 and index == len(frequencies) - 1
        )
        if endpoint and np.max(np.abs(np.imag(matrix))) > 1e-12:
            raise ValueError(
                "DC/Nyquist cross-PSD matrices must be real symmetric"
            )
        normalization = math.sqrt(
            sample_rate_hz if endpoint else sample_rate_hz / 2.0
        )
        factors[index] = normalization * factor
    factors.setflags(write=False)
    return factors


@dataclass(frozen=True)
class SpectralLaserFrequencyNoiseModel:
    """Generate correlated real frequency noise from a measured one-sided CSD."""

    spectrum: OneSidedCrossSpectralDensity
    sample_interval_us: float
    remove_dc: bool = True
    minimum_trace_duration_us: float = 0.0
    block_prefix: str = "spectral_laser_frequency"

    def __post_init__(self) -> None:
        if (
            self.sample_interval_us <= 0
            or self.minimum_trace_duration_us < 0
            or not self.block_prefix
        ):
            raise ValueError("spectral noise sample interval/prefix is invalid")

    def blocks(self, n_atoms: int) -> tuple[GaussianBlockSpec, ...]:
        del n_atoms
        # A zero-variance sentinel lets CompositeShotNoiseModel reject duplicate
        # spectral namespaces even though the duration-dependent FFT array is
        # drawn through the vectorized scope-engine path.
        return (
            GaussianBlockSpec(
                f"{self.block_prefix}_namespace",
                ("sentinel",),
                (0.0,),
                ((0.0,),),
                TemporalScope.FIXED,
            ),
        )

    def realization(
        self,
        engine: StochasticScopeEngine,
        n_atoms: int,
        duration_us: float,
    ) -> LaserPhaseFrequencyRealization:
        if duration_us < 0:
            raise ValueError("program duration must be non-negative")
        covered_duration_us = max(
            duration_us, self.minimum_trace_duration_us
        )
        sample_count = max(
            2,
            int(
                math.ceil(
                    covered_duration_us / self.sample_interval_us
                )
            ),
        )
        dt_s = self.sample_interval_us * 1e-6
        sample_rate_hz = 1.0 / dt_s
        nyquist_hz = 0.5 * sample_rate_hz
        if self.spectrum.frequencies_hz[-1] > nyquist_hz * (1.0 + 1e-12):
            raise ValueError("cross-PSD exceeds the realization Nyquist frequency")
        dimension = len(self.spectrum.channels)
        white = engine.standard_normal_array(
            f"{self.block_prefix}_time_white",
            (sample_count, dimension),
        )
        white_fft = np.fft.rfft(white, axis=0)
        factors = _spectral_shaping_factors(
            self.spectrum,
            sample_count,
            dt_s,
            self.remove_dc,
        )
        shaped_fft = np.einsum("kij,kj->ki", factors, white_fft)
        frequency_values = np.fft.irfft(
            shaped_fft, n=sample_count, axis=0
        )
        phase_values = np.vstack(
            (
                np.zeros((1, dimension)),
                np.cumsum(
                    2.0 * math.pi * frequency_values * dt_s,
                    axis=0,
                ),
            )
        )
        frequency_with_endpoint = np.vstack(
            (frequency_values, frequency_values[-1])
        )
        phase_traces = {
            channel: SampledTimeTrace(
                self.sample_interval_us,
                tuple(float(value) for value in phase_values[:, index]),
                interpolation="linear",
            )
            for index, channel in enumerate(self.spectrum.channels)
        }
        frequency_traces = {
            channel: SampledTimeTrace(
                self.sample_interval_us,
                tuple(
                    float(value)
                    for value in frequency_with_endpoint[:, index]
                ),
                interpolation="zoh",
            )
            for index, channel in enumerate(self.spectrum.channels)
        }
        return LaserPhaseFrequencyRealization(
            phase_traces,
            frequency_traces,
            SimulationContext(
                channel_phase_offset_traces_rad={
                    (channel, atom): phase_traces[channel]
                    for channel in self.spectrum.channels
                    for atom in range(n_atoms)
                }
            ),
        )

    def context(
        self, engine: StochasticScopeEngine, n_atoms: int
    ) -> SimulationContext:
        return self.realization(engine, n_atoms, 0.0).context

    def context_for_program(
        self,
        engine: StochasticScopeEngine,
        n_atoms: int,
        program: ExperimentProgram,
    ) -> SimulationContext:
        return self.realization(
            engine,
            n_atoms,
            experiment_program_duration_us(program),
        ).context


@dataclass(frozen=True)
class PolynomialLevelShiftSpec:
    """Calibrated scalar-field shift ``a*x + b*x^2`` for one level."""

    level: str
    linear_rad_per_us_per_field: float = 0.0
    quadratic_rad_per_us_per_field2: float = 0.0

    def __post_init__(self) -> None:
        if not self.level or not np.all(
            np.isfinite(
                (
                    self.linear_rad_per_us_per_field,
                    self.quadratic_rad_per_us_per_field2,
                )
            )
        ):
            raise ValueError("polynomial level-shift specification is invalid")

    def energy_rad_per_us(self, field: float) -> float:
        return (
            self.linear_rad_per_us_per_field * field
            + self.quadratic_rad_per_us_per_field2 * field**2
        )


@dataclass(frozen=True)
class ScalarFieldRealization:
    """Validator-side scalar fields and their level-energy context."""

    base_fields: tuple[float, ...]
    field_traces: tuple[SampledTimeTrace, ...]
    context: SimulationContext


@dataclass(frozen=True)
class ScalarFieldNoiseModel:
    """Generic scoped scalar field for trap-light or electric Stark shifts."""

    field_name: str
    field_unit: str
    bias_field: float
    level_shifts: tuple[PolynomialLevelShiftSpec, ...]
    iteration_common_sigma: float = 0.0
    shot_common_sigma: float = 0.0
    shot_local_sigma: float = 0.0
    within_shot_common_sigma: float = 0.0
    within_shot_local_sigma: float = 0.0
    within_shot_correlation_time_us: float = 1.0
    sample_interval_us: float = 0.01
    block_prefix: str = "scalar_field"

    def __post_init__(self) -> None:
        sigmas = (
            self.iteration_common_sigma,
            self.shot_common_sigma,
            self.shot_local_sigma,
            self.within_shot_common_sigma,
            self.within_shot_local_sigma,
        )
        if (
            not self.field_name
            or not self.field_unit
            or not self.level_shifts
            or len({spec.level for spec in self.level_shifts})
            != len(self.level_shifts)
            or not np.isfinite(self.bias_field)
            or any(value < 0 for value in sigmas)
            or self.within_shot_correlation_time_us <= 0
            or self.sample_interval_us <= 0
            or not self.block_prefix
        ):
            raise ValueError("scalar-field model parameters are invalid")

    def blocks(self, n_atoms: int) -> tuple[GaussianBlockSpec, ...]:
        local_keys = tuple(f"atom_{atom}" for atom in range(n_atoms))
        within_keys = ("common",) + local_keys
        return (
            GaussianBlockSpec(
                f"{self.block_prefix}_iteration_common",
                ("common",),
                (0.0,),
                ((self.iteration_common_sigma**2,),),
                TemporalScope.ITERATION,
            ),
            GaussianBlockSpec(
                f"{self.block_prefix}_shot_common",
                ("common",),
                (0.0,),
                ((self.shot_common_sigma**2,),),
                TemporalScope.SHOT,
            ),
            GaussianBlockSpec(
                f"{self.block_prefix}_shot_local",
                local_keys,
                (0.0,) * n_atoms,
                tuple(
                    tuple(
                        self.shot_local_sigma**2 if row == column else 0.0
                        for column in range(n_atoms)
                    )
                    for row in range(n_atoms)
                ),
                TemporalScope.SHOT,
            ),
            GaussianBlockSpec(
                f"{self.block_prefix}_within_initial_standard",
                within_keys,
                (0.0,) * len(within_keys),
                _identity_matrix_tuple(len(within_keys)),
                TemporalScope.SHOT,
            ),
            GaussianBlockSpec(
                f"{self.block_prefix}_within_innovation_standard",
                within_keys,
                (0.0,) * len(within_keys),
                _identity_matrix_tuple(len(within_keys)),
                TemporalScope.WITHIN_SHOT,
            ),
        )

    def realization(
        self,
        engine: StochasticScopeEngine,
        n_atoms: int,
        duration_us: float,
    ) -> ScalarFieldRealization:
        if duration_us < 0:
            raise ValueError("program duration must be non-negative")
        iteration = engine.sample(
            f"{self.block_prefix}_iteration_common"
        )["common"]
        shot_common = engine.sample(
            f"{self.block_prefix}_shot_common"
        )["common"]
        local_draw = engine.sample(f"{self.block_prefix}_shot_local")
        base_fields = tuple(
            self.bias_field
            + iteration
            + shot_common
            + local_draw[f"atom_{atom}"]
            for atom in range(n_atoms)
        )
        static_offsets = {
            (atom, spec.level): spec.energy_rad_per_us(base_fields[atom])
            - spec.energy_rad_per_us(self.bias_field)
            for atom in range(n_atoms)
            for spec in self.level_shifts
        }
        within_active = (
            self.within_shot_common_sigma > 0
            or self.within_shot_local_sigma > 0
        )
        if not within_active or duration_us == 0:
            return ScalarFieldRealization(
                base_fields,
                (),
                SimulationContext(
                    level_energy_offsets_rad_per_us=static_offsets
                ),
            )
        initial = engine.sample(
            f"{self.block_prefix}_within_initial_standard"
        )
        common = self.within_shot_common_sigma * initial["common"]
        local = np.asarray(
            [
                self.within_shot_local_sigma * initial[f"atom_{atom}"]
                for atom in range(n_atoms)
            ],
            dtype=float,
        )
        decay = math.exp(
            -self.sample_interval_us
            / self.within_shot_correlation_time_us
        )
        innovation_factor = math.sqrt(1.0 - decay**2)
        step_count = max(
            1, int(math.ceil(duration_us / self.sample_interval_us))
        )
        field_values = [
            [base_fields[atom] + common + local[atom]]
            for atom in range(n_atoms)
        ]
        for step in range(step_count):
            innovation = engine.sample(
                f"{self.block_prefix}_within_innovation_standard",
                within_shot_token=step,
            )
            common = decay * common + (
                self.within_shot_common_sigma
                * innovation_factor
                * innovation["common"]
            )
            for atom in range(n_atoms):
                local[atom] = decay * local[atom] + (
                    self.within_shot_local_sigma
                    * innovation_factor
                    * innovation[f"atom_{atom}"]
                )
                field_values[atom].append(
                    float(base_fields[atom] + common + local[atom])
                )
        field_traces = tuple(
            SampledTimeTrace(
                self.sample_interval_us,
                tuple(values),
                interpolation="linear",
            )
            for values in field_values
        )
        energy_traces = {
            (atom, spec.level): SampledTimeTrace(
                self.sample_interval_us,
                tuple(
                    spec.energy_rad_per_us(field)
                    - spec.energy_rad_per_us(base_fields[atom])
                    for field in field_values[atom]
                ),
                interpolation="linear",
            )
            for atom in range(n_atoms)
            for spec in self.level_shifts
        }
        return ScalarFieldRealization(
            base_fields,
            field_traces,
            SimulationContext(
                level_energy_offsets_rad_per_us=static_offsets,
                level_energy_offset_traces_rad_per_us=energy_traces,
            ),
        )

    def context(
        self, engine: StochasticScopeEngine, n_atoms: int
    ) -> SimulationContext:
        return self.realization(engine, n_atoms, 0.0).context

    def context_for_program(
        self,
        engine: StochasticScopeEngine,
        n_atoms: int,
        program: ExperimentProgram,
    ) -> SimulationContext:
        return self.realization(
            engine,
            n_atoms,
            experiment_program_duration_us(program),
        ).context


def arc_dc_polarizability_to_quadratic_shift_rad_per_us_per_vpcm2(
    polarizability_mhz_cm2_per_v2: float,
) -> float:
    """Convert ARC's alpha to the coefficient of ``E^2`` in rad/us.

    ARC 3.10.2's :meth:`StarkMap.getPolarizability` implementation fits
    ``Delta nu = offset - 0.5 * alpha * E^2`` with alpha in MHz cm^2/V^2.
    Since one MHz is one cycle/us, the angular coefficient is
    ``-2*pi*0.5*alpha = -pi*alpha``.  The explicit minus sign matters:
    ARC returns a positive alpha for the Cs 69S pilot used by this project.
    """

    if not np.isfinite(polarizability_mhz_cm2_per_v2):
        raise ValueError("ARC polarizability must be finite")
    return -math.pi * polarizability_mhz_cm2_per_v2
