"""Backend-independent public experiment contracts.

No class in this module may import QuTiP or expose a simulator state. Programs
are laboratory-like instructions; gates and calibration circuits are composed
above this layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
import math
from typing import Mapping, Tuple, Union


@dataclass(frozen=True)
class ConstantPulse:
    """A constant rotating-frame control pulse.

    Args:
        duration_us: Pulse duration in microseconds.
        amplitude_rad_per_us: On-resonance angular Rabi frequency.
        phase_rad: Drive phase in radians.
        detuning_rad_per_us: Drive detuning in angular frequency units.
    """

    duration_us: float
    amplitude_rad_per_us: float
    phase_rad: float = 0.0
    detuning_rad_per_us: float = 0.0

    def __post_init__(self) -> None:
        if self.duration_us <= 0:
            raise ValueError("pulse duration_us must be positive")
        if self.amplitude_rad_per_us < 0:
            raise ValueError("pulse amplitude_rad_per_us must be non-negative")


@dataclass(frozen=True)
class Prepare:
    """Prepare a computational-basis state, e.g. ``"01"``."""

    bitstring: str


@dataclass(frozen=True)
class Play:
    """Play a pulse on one named actuator channel and target atoms."""

    channel: str
    targets: Tuple[int, ...]
    pulse: ConstantPulse

    def __post_init__(self) -> None:
        if not self.channel:
            raise ValueError("channel must be non-empty")
        if not self.targets:
            raise ValueError("targets must be non-empty")
        if len(set(self.targets)) != len(self.targets):
            raise ValueError("targets must be unique")


@dataclass(frozen=True)
class ParallelPlay:
    """Play multiple actuator channels concurrently for one time segment.

    All component pulses must have the same duration.  This is required for
    two-photon ladders, Raman control, simultaneous global/local fields, and
    other laboratory operations whose Hamiltonian is a sum of active drives.
    """

    plays: Tuple[Play, ...]

    def __post_init__(self) -> None:
        if not self.plays:
            raise ValueError("ParallelPlay requires at least one component")
        duration = self.plays[0].pulse.duration_us
        if any(
            abs(play.pulse.duration_us - duration) > 1e-12
            for play in self.plays[1:]
        ):
            raise ValueError("all ParallelPlay components must have equal duration")
        addressed = [
            (play.channel, atom)
            for play in self.plays
            for atom in play.targets
        ]
        if len(addressed) != len(set(addressed)):
            raise ValueError(
                "a channel/target pair may appear only once in ParallelPlay"
            )

    @property
    def duration_us(self) -> float:
        return self.plays[0].pulse.duration_us


@dataclass(frozen=True)
class Delay:
    """Wait while the configured drift Hamiltonian remains active."""

    duration_us: float

    def __post_init__(self) -> None:
        if self.duration_us < 0:
            raise ValueError("delay duration_us must be non-negative")


@dataclass(frozen=True)
class Measure:
    """Request destructive computational-basis measurement."""

    basis: str = "computational"

    def __post_init__(self) -> None:
        if self.basis != "computational":
            raise ValueError("the reduced runtime currently supports computational measurement only")


Operation = Union[Prepare, Play, ParallelPlay, Delay, Measure]


@dataclass(frozen=True)
class ExperimentProgram:
    """An immutable, time-ordered sequence of laboratory operations."""

    operations: Tuple[Operation, ...] = ()
    name: str = "unnamed"

    def then(self, operation: Operation) -> "ExperimentProgram":
        """Return a new program with ``operation`` appended."""

        return ExperimentProgram(self.operations + (operation,), self.name)


@dataclass(frozen=True)
class ResourceUsage:
    """Public accounting for one execution request."""

    shots: int
    pulses_per_shot: int
    pulse_time_per_shot_us: float
    sequence_time_per_shot_us: float
    total_sequence_time_us: float
    channel_time_per_shot_us: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "channel_time_per_shot_us",
            MappingProxyType(dict(self.channel_time_per_shot_us)),
        )


@dataclass(frozen=True)
class AtomReadout:
    """One atom's public camera-derived readout record.

    Both signals are experimentally observable. ``retained`` and
    ``classified_state`` are derived from those signals; no latent level or
    simulator truth is included.
    """

    state_signal_photoelectrons: float
    occupancy_signal_photoelectrons: float
    classified_state: str
    retained: bool

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.state_signal_photoelectrons)
            or not math.isfinite(self.occupancy_signal_photoelectrons)
            or not self.classified_state
        ):
            raise ValueError("atom readout signals and classification must be valid")


@dataclass(frozen=True)
class ShotReadout:
    """Public camera-derived records for one physical shot."""

    atoms: Tuple[AtomReadout, ...]
    outcome: str

    def __post_init__(self) -> None:
        if not self.atoms:
            raise ValueError("shot readout requires at least one atom")
        expected = "".join(atom.classified_state for atom in self.atoms)
        if self.outcome != expected:
            raise ValueError("shot outcome must match atom classifications")


@dataclass(frozen=True)
class ExperimentResult:
    """Raw public output returned to a controller.

    It intentionally contains no state, channel, fidelity, gradient, Hessian,
    hidden noise realization, or random seed.
    """

    execution_id: str
    counts: Mapping[str, int]
    shot_outcomes: Tuple[str, ...]
    public_timestamp_us: float
    status: str
    resources: ResourceUsage
    metadata: Mapping[str, str] = field(default_factory=dict)
    shot_readouts: Tuple[ShotReadout, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "counts", MappingProxyType(dict(self.counts)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        if self.shot_readouts and tuple(
            record.outcome for record in self.shot_readouts
        ) != self.shot_outcomes:
            raise ValueError("shot_readouts must align with shot_outcomes")
