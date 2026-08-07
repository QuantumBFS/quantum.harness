"""Internal physics-backend protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, Mapping, Protocol

import numpy as np

from .contracts import ExperimentProgram


@dataclass(frozen=True)
class SimulationSnapshot:
    """Internal state returned by a physics backend."""

    state: Any
    duration_us: float
    pulse_time_us: float
    pulse_count: int
    channel_time_us: Mapping[str, float]


@dataclass(frozen=True)
class SampledTimeTrace:
    """A scalar hidden trajectory sampled on a uniform laboratory clock.

    Traces are clamped outside their sampled interval.  This makes a generated
    realization safe against floating-point endpoint roundoff while keeping
    the noise model responsible for covering the full program duration.
    """

    sample_interval_us: float
    values: tuple[float, ...]
    start_time_us: float = 0.0
    interpolation: Literal["linear", "zoh"] = "linear"

    def __post_init__(self) -> None:
        values = tuple(float(value) for value in self.values)
        if self.sample_interval_us <= 0:
            raise ValueError("trace sample interval must be positive")
        if not values or not np.all(np.isfinite(values)):
            raise ValueError("trace values must be non-empty and finite")
        if not np.isfinite(self.start_time_us):
            raise ValueError("trace start time must be finite")
        if self.interpolation not in {"linear", "zoh"}:
            raise ValueError("trace interpolation must be 'linear' or 'zoh'")
        object.__setattr__(self, "values", values)

    @property
    def end_time_us(self) -> float:
        return self.start_time_us + self.sample_interval_us * (
            len(self.values) - 1
        )

    def value_at(self, time_us: float) -> float:
        """Evaluate using linear interpolation or zero-order hold."""

        coordinate = (time_us - self.start_time_us) / self.sample_interval_us
        if coordinate <= 0 or len(self.values) == 1:
            return self.values[0]
        if coordinate >= len(self.values) - 1:
            return self.values[-1]
        lower = int(np.floor(coordinate))
        if self.interpolation == "zoh":
            return self.values[lower]
        fraction = coordinate - lower
        return (1.0 - fraction) * self.values[lower] + fraction * self.values[
            lower + 1
        ]

    def breakpoints(self, start_time_us: float, end_time_us: float) -> tuple[float, ...]:
        """Return sample knots strictly inside an evolution interval."""

        if end_time_us <= start_time_us or len(self.values) <= 1:
            return ()
        first_index = max(
            1,
            int(
                np.floor(
                    (start_time_us - self.start_time_us)
                    / self.sample_interval_us
                )
            )
            + 1,
        )
        last_index = min(
            len(self.values) - 1,
            int(
                np.ceil(
                    (end_time_us - self.start_time_us)
                    / self.sample_interval_us
                )
            )
            - 1,
        )
        return tuple(
            self.start_time_us + index * self.sample_interval_us
            for index in range(first_index, last_index + 1)
            if start_time_us
            < self.start_time_us + index * self.sample_interval_us
            < end_time_us
        )


TraceMap = Mapping[
    tuple[str, int] | tuple[int, str],
    SampledTimeTrace | tuple[SampledTimeTrace, ...],
]


def _freeze_trace_map(
    source: TraceMap,
) -> Mapping[
    tuple[str, int] | tuple[int, str], tuple[SampledTimeTrace, ...]
]:
    frozen = {}
    for key, traces in source.items():
        normalized = (traces,) if isinstance(traces, SampledTimeTrace) else tuple(traces)
        if not normalized or not all(
            isinstance(trace, SampledTimeTrace) for trace in normalized
        ):
            raise ValueError("trace mappings require SampledTimeTrace values")
        frozen[key] = normalized
    return MappingProxyType(frozen)


@dataclass(frozen=True)
class SimulationContext:
    """One hidden classical realization applied to a backend simulation.

    Keys are explicit atom/channel or atom/level identifiers so a global
    laboratory command can experience local Doppler and beam-coupling
    variations without changing the public experiment program.
    """

    channel_amplitude_scales: Mapping[tuple[str, int], float] = field(
        default_factory=dict
    )
    channel_detuning_offsets_rad_per_us: Mapping[tuple[str, int], float] = field(
        default_factory=dict
    )
    level_energy_offsets_rad_per_us: Mapping[tuple[int, str], float] = field(
        default_factory=dict
    )
    pair_interaction_scales: Mapping[tuple[int, int, str], float] = field(
        default_factory=dict
    )
    channel_phase_offset_traces_rad: TraceMap = field(default_factory=dict)
    channel_detuning_offset_traces_rad_per_us: TraceMap = field(
        default_factory=dict
    )
    level_energy_offset_traces_rad_per_us: TraceMap = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        amplitude = dict(self.channel_amplitude_scales)
        pair_scales: dict[tuple[int, int, str], float] = {}
        for key, value in self.pair_interaction_scales.items():
            first, second, label = key
            if first == second:
                raise ValueError("pair interaction context requires distinct atoms")
            pair_scales[(min(first, second), max(first, second), label)] = value
        if any(value < 0 for value in amplitude.values()):
            raise ValueError("channel amplitude scales must be non-negative")
        if any(value < 0 for value in pair_scales.values()):
            raise ValueError("pair interaction scales must be non-negative")
        object.__setattr__(
            self, "channel_amplitude_scales", MappingProxyType(amplitude)
        )
        object.__setattr__(
            self,
            "channel_detuning_offsets_rad_per_us",
            MappingProxyType(dict(self.channel_detuning_offsets_rad_per_us)),
        )
        object.__setattr__(
            self,
            "level_energy_offsets_rad_per_us",
            MappingProxyType(dict(self.level_energy_offsets_rad_per_us)),
        )
        object.__setattr__(
            self, "pair_interaction_scales", MappingProxyType(pair_scales)
        )
        object.__setattr__(
            self,
            "channel_phase_offset_traces_rad",
            _freeze_trace_map(self.channel_phase_offset_traces_rad),
        )
        object.__setattr__(
            self,
            "channel_detuning_offset_traces_rad_per_us",
            _freeze_trace_map(
                self.channel_detuning_offset_traces_rad_per_us
            ),
        )
        object.__setattr__(
            self,
            "level_energy_offset_traces_rad_per_us",
            _freeze_trace_map(self.level_energy_offset_traces_rad_per_us),
        )

    @property
    def is_nominal(self) -> bool:
        """Whether this context leaves every configured Hamiltonian unchanged."""

        return not (
            self.channel_amplitude_scales
            or self.channel_detuning_offsets_rad_per_us
            or self.level_energy_offsets_rad_per_us
            or self.pair_interaction_scales
            or self.channel_phase_offset_traces_rad
            or self.channel_detuning_offset_traces_rad_per_us
            or self.level_energy_offset_traces_rad_per_us
        )

    @staticmethod
    def _trace_sum(
        mapping: Mapping[
            tuple[str, int] | tuple[int, str],
            tuple[SampledTimeTrace, ...],
        ],
        key: tuple[str, int] | tuple[int, str],
        time_us: float,
    ) -> float:
        return sum(trace.value_at(time_us) for trace in mapping.get(key, ()))

    def channel_phase_offset_rad(
        self, channel: str, atom: int, time_us: float
    ) -> float:
        return self._trace_sum(
            self.channel_phase_offset_traces_rad,
            (channel, atom),
            time_us,
        )

    def channel_detuning_offset_rad_per_us(
        self, channel: str, atom: int, time_us: float
    ) -> float:
        return self.channel_detuning_offsets_rad_per_us.get(
            (channel, atom), 0.0
        ) + self._trace_sum(
            self.channel_detuning_offset_traces_rad_per_us,
            (channel, atom),
            time_us,
        )

    def level_energy_offset_rad_per_us(
        self, atom: int, level: str, time_us: float
    ) -> float:
        return self.level_energy_offsets_rad_per_us.get(
            (atom, level), 0.0
        ) + self._trace_sum(
            self.level_energy_offset_traces_rad_per_us,
            (atom, level),
            time_us,
        )

    def dynamic_breakpoints(
        self, start_time_us: float, duration_us: float
    ) -> tuple[float, ...]:
        """Union of every hidden trajectory knot inside an interval."""

        end_time_us = start_time_us + duration_us
        traces = (
            trace
            for mapping in (
                self.channel_phase_offset_traces_rad,
                self.channel_detuning_offset_traces_rad_per_us,
                self.level_energy_offset_traces_rad_per_us,
            )
            for values in mapping.values()
            for trace in values
        )
        return tuple(
            sorted(
                {
                    point
                    for trace in traces
                    for point in trace.breakpoints(start_time_us, end_time_us)
                }
            )
        )

    @classmethod
    def combine(cls, *contexts: "SimulationContext") -> "SimulationContext":
        """Compose independent physical effects with explicit algebra."""

        amplitudes: dict[tuple[str, int], float] = {}
        detunings: dict[tuple[str, int], float] = {}
        energies: dict[tuple[int, str], float] = {}
        interactions: dict[tuple[int, int, str], float] = {}
        phase_traces: dict[
            tuple[str, int], tuple[SampledTimeTrace, ...]
        ] = {}
        detuning_traces: dict[
            tuple[str, int], tuple[SampledTimeTrace, ...]
        ] = {}
        energy_traces: dict[
            tuple[int, str], tuple[SampledTimeTrace, ...]
        ] = {}
        for context in contexts:
            for key, value in context.channel_amplitude_scales.items():
                amplitudes[key] = amplitudes.get(key, 1.0) * value
            for key, value in (
                context.channel_detuning_offsets_rad_per_us.items()
            ):
                detunings[key] = detunings.get(key, 0.0) + value
            for key, value in context.level_energy_offsets_rad_per_us.items():
                energies[key] = energies.get(key, 0.0) + value
            for key, value in context.pair_interaction_scales.items():
                interactions[key] = interactions.get(key, 1.0) * value
            for key, traces in context.channel_phase_offset_traces_rad.items():
                phase_traces[key] = phase_traces.get(key, ()) + traces
            for key, traces in (
                context.channel_detuning_offset_traces_rad_per_us.items()
            ):
                detuning_traces[key] = detuning_traces.get(key, ()) + traces
            for key, traces in (
                context.level_energy_offset_traces_rad_per_us.items()
            ):
                energy_traces[key] = energy_traces.get(key, ()) + traces
        return cls(
            channel_amplitude_scales=amplitudes,
            channel_detuning_offsets_rad_per_us=detunings,
            level_energy_offsets_rad_per_us=energies,
            pair_interaction_scales=interactions,
            channel_phase_offset_traces_rad=phase_traces,
            channel_detuning_offset_traces_rad_per_us=detuning_traces,
            level_energy_offset_traces_rad_per_us=energy_traces,
        )


class PhysicsBackend(Protocol):
    """Minimal backend surface consumed by the experiment runtime."""

    n_atoms: int

    def simulate(
        self,
        program: ExperimentProgram,
        *,
        initial_state: Any | None = None,
        ignore_prepare: bool = False,
        context: SimulationContext | None = None,
    ) -> SimulationSnapshot:
        ...

    def outcome_probabilities(self, state: Any) -> dict[str, float]:
        ...

    def computational_amplitudes(self, state: Any) -> np.ndarray:
        ...

    def computational_basis_state(self, bitstring: str) -> Any:
        ...

    def local_level_product_state(self, levels: tuple[str, ...]) -> Any:
        ...
