"""Environment and reduced-model configuration."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping, Tuple


@dataclass(frozen=True)
class TransitionCouplingSpec:
    """One extra transition driven by the same physical actuator.

    ``relative_rabi`` is the complex Rabi-frequency ratio relative to the
    channel's primary ``transition``.  A complex value preserves relative
    Clebsch--Gordan signs and optical phases while the public pulse supplies
    the shared amplitude, phase, detuning and noise realization.
    """

    transition: str
    relative_rabi: complex

    def __post_init__(self) -> None:
        value = complex(self.relative_rabi)
        if not self.transition:
            raise ValueError("coupled transition identifier must be non-empty")
        if not math.isfinite(value.real) or not math.isfinite(value.imag):
            raise ValueError("relative Rabi coefficient must be finite")
        if value == 0:
            raise ValueError("relative Rabi coefficient must be non-zero")
        object.__setattr__(self, "relative_rabi", value)


@dataclass(frozen=True)
class ChannelLevelShiftSpec:
    """Pulse-amplitude-dependent diagonal shift from one physical actuator.

    The backend adds
    ``coefficient * |Omega_actual|**amplitude_power |level><level|``.
    The coefficient therefore uses the units required to return ``rad/us``.
    The default quadratic power represents an effective AC Stark shift.
    """

    level: str
    coefficient: float
    amplitude_power: float = 2.0
    label: str = "channel-level-shift"

    def __post_init__(self) -> None:
        if not self.level:
            raise ValueError("channel level shift must reference a level")
        if not math.isfinite(self.coefficient):
            raise ValueError("channel level-shift coefficient must be finite")
        if (
            not math.isfinite(self.amplitude_power)
            or self.amplitude_power <= 0
        ):
            raise ValueError("channel level-shift power must be positive")


@dataclass(frozen=True)
class ChannelSpec:
    """A public physical actuator channel and its command limits.

    The legacy ``transition`` remains the reference transition with relative
    Rabi coefficient one.  ``additional_transition_couplings`` lets the same
    laser or RF actuator coherently drive other transitions.  All such terms
    share the public waveform and hidden channel noise.
    """

    name: str
    transition: str
    addressing: str
    max_amplitude_rad_per_us: float
    max_abs_detuning_rad_per_us: float
    min_duration_us: float = 0.0
    additional_transition_couplings: Tuple[TransitionCouplingSpec, ...] = ()
    level_shifts: Tuple[ChannelLevelShiftSpec, ...] = ()

    def __post_init__(self) -> None:
        if not self.transition:
            raise ValueError("transition identifier must be non-empty")
        if self.addressing not in {"local", "global"}:
            raise ValueError("addressing must be 'local' or 'global'")
        if self.max_amplitude_rad_per_us <= 0:
            raise ValueError("max amplitude must be positive")
        if self.max_abs_detuning_rad_per_us < 0:
            raise ValueError("max detuning must be non-negative")
        extras = tuple(self.additional_transition_couplings)
        transitions = (self.transition,) + tuple(
            coupling.transition for coupling in extras
        )
        if len(transitions) != len(set(transitions)):
            raise ValueError("channel transition couplings must be unique")
        object.__setattr__(
            self,
            "additional_transition_couplings",
            extras,
        )
        shifts = tuple(self.level_shifts)
        if len({shift.level for shift in shifts}) != len(shifts):
            raise ValueError("channel level shifts must reference unique levels")
        object.__setattr__(self, "level_shifts", shifts)

    @property
    def transition_couplings(self) -> Tuple[TransitionCouplingSpec, ...]:
        """All coherently driven transitions, including the unit reference."""

        return (
            TransitionCouplingSpec(self.transition, 1.0 + 0.0j),
            *self.additional_transition_couplings,
        )


@dataclass(frozen=True)
class ReducedModelConfig:
    """Truth parameters for the initial ``|0>, |1>, |r>`` backend.

    All rates and Hamiltonian coefficients are angular frequencies in rad/us.
    The profile is an interface-validation model, not the final Cs model.
    """

    blockade_rad_per_us: float
    qubit_drift_detuning_rad_per_us: float = 0.0
    rydberg_drift_detuning_rad_per_us: float = 0.0
    rydberg_relaxation_rate_per_us: float = 0.0
    qubit_dephasing_rate_per_us: float = 0.0

    def __post_init__(self) -> None:
        if self.blockade_rad_per_us < 0:
            raise ValueError("blockade must be non-negative")
        if self.rydberg_relaxation_rate_per_us < 0:
            raise ValueError("relaxation rate must be non-negative")
        if self.qubit_dephasing_rate_per_us < 0:
            raise ValueError("dephasing rate must be non-negative")


@dataclass(frozen=True)
class EnvironmentConfig:
    """Complete configuration for one reduced experimental environment."""

    atom_positions_um: Tuple[Tuple[float, ...], ...]
    channels: Mapping[str, ChannelSpec]
    model: ReducedModelConfig
    profile_name: str = "reduced-three-level"

    def __post_init__(self) -> None:
        if not self.atom_positions_um:
            raise ValueError("at least one atom is required")
        positions = tuple(
            tuple(float(value) for value in position)
            for position in self.atom_positions_um
        )
        if any(
            len(position) not in (2, 3)
            or not all(math.isfinite(value) for value in position)
            for position in positions
        ):
            raise ValueError("atom positions must be finite 2D or 3D vectors")
        if len(self.channels) == 0:
            raise ValueError("at least one channel is required")
        for name, spec in self.channels.items():
            if name != spec.name:
                raise ValueError("channel mapping key must equal ChannelSpec.name")
        object.__setattr__(self, "channels", MappingProxyType(dict(self.channels)))
        object.__setattr__(self, "atom_positions_um", positions)

    @property
    def n_atoms(self) -> int:
        return len(self.atom_positions_um)
