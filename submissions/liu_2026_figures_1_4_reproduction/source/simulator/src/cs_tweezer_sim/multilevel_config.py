"""Backend-independent configuration for arbitrary finite-level atom models."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import Mapping, Tuple

from .config import ChannelSpec


@dataclass(frozen=True)
class LevelSpec:
    """One local atomic or sink level.

    ``measurement_label`` is the raw symbol emitted by the idealized state
    discriminator.  Multiple physical levels may intentionally share a label.
    """

    name: str
    measurement_label: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("level name must be non-empty")
        if not self.measurement_label:
            raise ValueError("measurement label must be non-empty")


@dataclass(frozen=True)
class TransitionSpec:
    """Bind a transition identifier to two model levels.

    ``detuning_weights`` defines the diagonal rotating-frame operator multiplied
    by the detuning supplied with a pulse on this transition.  This supports
    ladder, Raman, microwave, and effective transitions without hard-coding
    their rotating-frame conventions in the backend.
    """

    name: str
    lower_level: str
    upper_level: str
    detuning_weights: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.lower_level or not self.upper_level:
            raise ValueError("transition names and levels must be non-empty")
        if self.lower_level == self.upper_level:
            raise ValueError("transition levels must be distinct")
        object.__setattr__(
            self,
            "detuning_weights",
            MappingProxyType(dict(self.detuning_weights)),
        )


@dataclass(frozen=True)
class DecaySpec:
    """One Lindblad population-transfer channel."""

    source_level: str
    target_level: str
    rate_per_us: float
    label: str = "unspecified"

    def __post_init__(self) -> None:
        if self.source_level == self.target_level:
            raise ValueError("decay source and target must be distinct")
        if self.rate_per_us < 0:
            raise ValueError("decay rate must be non-negative")


@dataclass(frozen=True)
class PairInteractionSpec:
    """Static interaction between a pair of occupied local levels."""

    first_level: str
    second_level: str
    strength_rad_per_us: float
    symmetric: bool = True
    label: str = "pair-interaction"
    atom_pair: Tuple[int, int] | None = None

    def __post_init__(self) -> None:
        if not self.first_level or not self.second_level:
            raise ValueError("pair interaction levels must be non-empty")
        if not math.isfinite(self.strength_rad_per_us):
            raise ValueError("pair interaction strength must be finite")
        if self.atom_pair is not None:
            pair = tuple(self.atom_pair)
            if (
                len(pair) != 2
                or pair[0] < 0
                or pair[1] <= pair[0]
            ):
                raise ValueError(
                    "atom_pair must contain ordered non-negative indices"
                )
            object.__setattr__(self, "atom_pair", pair)


@dataclass(frozen=True)
class StaticCouplingSpec:
    """One Hermitian off-diagonal single-atom Hamiltonian term.

    ``matrix_element_rad_per_us`` is
    ``<upper_level|H|lower_level>``.  The backend adds its Hermitian conjugate.
    This represents static mixing such as a transverse field or calibrated
    level coupling; diagonal shifts remain in ``static_level_energies``.
    """

    lower_level: str
    upper_level: str
    matrix_element_rad_per_us: complex
    label: str = "static-coupling"

    def __post_init__(self) -> None:
        value = complex(self.matrix_element_rad_per_us)
        if (
            not self.lower_level
            or not self.upper_level
            or self.lower_level == self.upper_level
        ):
            raise ValueError("static coupling levels must be non-empty and distinct")
        if not math.isfinite(value.real) or not math.isfinite(value.imag):
            raise ValueError("static coupling matrix element must be finite")
        if value == 0:
            raise ValueError("static coupling matrix element must be non-zero")
        object.__setattr__(self, "matrix_element_rad_per_us", value)


@dataclass(frozen=True)
class PairCouplingSpec:
    """Hermitian coupling between two ordered two-atom product states.

    The term is
    ``g |target[0],target[1]><source[0],source[1]| + h.c.`` for every atom
    pair in index order.  Exchange-related terms can be listed explicitly.
    The existing pair-interaction scale with this ``label`` also scales this
    matrix element, so thermal position noise can act on pair-state mixing.
    """

    source_levels: Tuple[str, str]
    target_levels: Tuple[str, str]
    matrix_element_rad_per_us: complex
    label: str = "pair-coupling"
    atom_pair: Tuple[int, int] | None = None

    def __post_init__(self) -> None:
        source = tuple(self.source_levels)
        target = tuple(self.target_levels)
        value = complex(self.matrix_element_rad_per_us)
        if len(source) != 2 or len(target) != 2:
            raise ValueError("pair coupling source and target must contain two levels")
        if not all(source) or not all(target) or source == target:
            raise ValueError("pair coupling product states must be non-empty and distinct")
        if not math.isfinite(value.real) or not math.isfinite(value.imag):
            raise ValueError("pair coupling matrix element must be finite")
        if value == 0:
            raise ValueError("pair coupling matrix element must be non-zero")
        if self.atom_pair is not None:
            pair = tuple(self.atom_pair)
            if (
                len(pair) != 2
                or pair[0] < 0
                or pair[1] <= pair[0]
            ):
                raise ValueError(
                    "atom_pair must contain ordered non-negative indices"
                )
            object.__setattr__(self, "atom_pair", pair)
        object.__setattr__(self, "source_levels", source)
        object.__setattr__(self, "target_levels", target)
        object.__setattr__(self, "matrix_element_rad_per_us", value)


@dataclass(frozen=True)
class ParameterProvenance:
    """Human- and machine-readable provenance for one profile parameter."""

    parameter: str
    value: float
    unit: str
    evidence_kind: str
    source: str
    locator: str
    derivation: str = ""
    software_version: str = ""


@dataclass(frozen=True)
class MultilevelModelConfig:
    """Truth model for a finite set of local levels."""

    levels: Tuple[LevelSpec, ...]
    computational_levels: Tuple[str, str]
    transitions: Mapping[str, TransitionSpec]
    static_level_energies_rad_per_us: Mapping[str, float]
    decays: Tuple[DecaySpec, ...] = ()
    pair_interactions: Tuple[PairInteractionSpec, ...] = ()
    static_couplings: Tuple[StaticCouplingSpec, ...] = ()
    pair_couplings: Tuple[PairCouplingSpec, ...] = ()

    def __post_init__(self) -> None:
        names = tuple(level.name for level in self.levels)
        if not names or len(names) != len(set(names)):
            raise ValueError("model levels must be non-empty and unique")
        if len(self.computational_levels) != 2:
            raise ValueError("exactly two computational levels are required")
        missing_computational = set(self.computational_levels) - set(names)
        if missing_computational:
            raise ValueError(
                f"unknown computational levels: {sorted(missing_computational)}"
            )
        for key, transition in self.transitions.items():
            if key != transition.name:
                raise ValueError("transition mapping key must equal transition name")
            missing = {
                transition.lower_level,
                transition.upper_level,
                *transition.detuning_weights,
            } - set(names)
            if missing:
                raise ValueError(
                    f"transition {key} references unknown levels {sorted(missing)}"
                )
        for level in self.static_level_energies_rad_per_us:
            if level not in names:
                raise ValueError(f"static energy references unknown level {level}")
        for decay in self.decays:
            missing = {decay.source_level, decay.target_level} - set(names)
            if missing:
                raise ValueError(f"decay references unknown levels {sorted(missing)}")
        for interaction in self.pair_interactions:
            missing = {
                interaction.first_level,
                interaction.second_level,
            } - set(names)
            if missing:
                raise ValueError(
                    f"pair interaction references unknown levels {sorted(missing)}"
                )
        for coupling in self.static_couplings:
            missing = {
                coupling.lower_level,
                coupling.upper_level,
            } - set(names)
            if missing:
                raise ValueError(
                    f"static coupling references unknown levels {sorted(missing)}"
                )
        for coupling in self.pair_couplings:
            missing = {
                *coupling.source_levels,
                *coupling.target_levels,
            } - set(names)
            if missing:
                raise ValueError(
                    f"pair coupling references unknown levels {sorted(missing)}"
                )
        object.__setattr__(
            self,
            "transitions",
            MappingProxyType(dict(self.transitions)),
        )
        object.__setattr__(
            self,
            "static_level_energies_rad_per_us",
            MappingProxyType(dict(self.static_level_energies_rad_per_us)),
        )


@dataclass(frozen=True)
class MultilevelEnvironmentConfig:
    """Complete benchmark-author configuration for a multilevel environment."""

    atom_positions_um: Tuple[Tuple[float, ...], ...]
    channels: Mapping[str, ChannelSpec]
    model: MultilevelModelConfig
    profile_name: str
    nominal_controls: Mapping[str, float] = field(default_factory=dict)
    provenance: Tuple[ParameterProvenance, ...] = ()

    def __post_init__(self) -> None:
        if not self.atom_positions_um:
            raise ValueError("at least one atom is required")
        positions = tuple(tuple(float(value) for value in position) for position in self.atom_positions_um)
        if any(
            len(position) not in (2, 3)
            or not all(math.isfinite(value) for value in position)
            for position in positions
        ):
            raise ValueError("atom positions must be finite 2D or 3D vectors")
        for term in (
            *self.model.pair_interactions,
            *self.model.pair_couplings,
        ):
            if (
                term.atom_pair is not None
                and term.atom_pair[1] >= len(positions)
            ):
                raise ValueError(
                    f"pair term {term.label} references atom index outside "
                    "the configured geometry"
                )
        for key, channel in self.channels.items():
            if key != channel.name:
                raise ValueError("channel mapping key must equal channel name")
            known_levels = {
                level.name for level in self.model.levels
            }
            missing_shift_levels = {
                shift.level for shift in channel.level_shifts
            } - known_levels
            if missing_shift_levels:
                raise ValueError(
                    f"channel {key} level shifts reference unknown levels "
                    f"{sorted(missing_shift_levels)}"
                )
            detuning_weights: dict[str, float] = {}
            for coupling in channel.transition_couplings:
                if coupling.transition not in self.model.transitions:
                    raise ValueError(
                        f"channel {key} references unknown transition "
                        f"{coupling.transition}"
                    )
                transition = self.model.transitions[coupling.transition]
                for level, weight in transition.detuning_weights.items():
                    previous = detuning_weights.get(level)
                    if previous is not None and not math.isclose(
                        previous,
                        weight,
                        rel_tol=0.0,
                        abs_tol=1e-12,
                    ):
                        raise ValueError(
                            f"channel {key} has incompatible detuning weights "
                            f"for level {level}: {previous} and {weight}"
                        )
                    detuning_weights[level] = weight
        object.__setattr__(self, "channels", MappingProxyType(dict(self.channels)))
        object.__setattr__(self, "atom_positions_um", positions)
        object.__setattr__(
            self,
            "nominal_controls",
            MappingProxyType(dict(self.nominal_controls)),
        )

    @property
    def n_atoms(self) -> int:
        return len(self.atom_positions_um)
