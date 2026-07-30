"""Quantum-number-driven atomic environment compilation.

The public descriptors in this module are species independent.  Atomic
structure is supplied by an :class:`AtomicDataProvider`; the bundled ARC
adapter is one implementation for supported alkali atoms.  Pair interactions
follow the same provider boundary, so a tabulated, ARC, PairInteraction or
MQDT implementation can be substituted without changing the simulator.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import math
from types import MappingProxyType
from typing import Mapping, Protocol, Sequence

import numpy as np
from scipy.constants import hbar, physical_constants

from .config import ChannelSpec, TransitionCouplingSpec
from .multilevel_config import (
    DecaySpec,
    LevelSpec,
    MultilevelEnvironmentConfig,
    MultilevelModelConfig,
    PairCouplingSpec,
    PairInteractionSpec,
    ParameterProvenance,
    TransitionSpec,
)
from .stochastic import (
    MagneticFieldNoiseModel,
    ZeemanLevelShiftSpec,
)


BOHR_MAGNETON_J_PER_T = physical_constants["Bohr magneton"][0]
EV_TO_RAD_PER_US = physical_constants["electron volt"][0] / hbar * 1e-6
HZ_TO_RAD_PER_US = 2.0 * math.pi * 1e-6
GAUSS_TO_TESLA = 1e-4


def _is_half_integer(value: float) -> bool:
    return math.isfinite(value) and math.isclose(
        2.0 * value,
        round(2.0 * value),
        rel_tol=0.0,
        abs_tol=1e-10,
    )


def _unit_real_vector(
    vector: Sequence[float],
    *,
    label: str,
) -> tuple[float, float, float]:
    array = np.asarray(tuple(vector), dtype=float)
    if array.shape != (3,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{label} must be a finite three-vector")
    norm = float(np.linalg.norm(array))
    if norm == 0:
        raise ValueError(f"{label} must be non-zero")
    return tuple(float(value) for value in array / norm)


def _pad_position(position: Sequence[float]) -> tuple[float, float, float]:
    values = tuple(float(value) for value in position)
    if len(values) == 2:
        values = (*values, 0.0)
    if len(values) != 3 or not all(math.isfinite(value) for value in values):
        raise ValueError("atom positions must be finite 2D or 3D vectors")
    return values


@dataclass(frozen=True)
class AtomicStateDescriptor:
    """One physical sublevel or an explicit leakage/loss sink.

    ``n`` is the integer principal quantum number.  An MQDT effective
    principal quantum number such as the Yb value ``nu=52.3`` belongs in
    ``effective_principal_quantum_number``.  Keeping both concepts separate
    prevents a fitted/effective value from being passed silently to an
    integer-n atomic-data API such as ARC.
    """

    name: str
    measurement_label: str
    n: float | None = None
    l: int | None = None
    j: float | None = None
    s: float = 0.5
    f: float | None = None
    mf: float | None = None
    mj: float | None = None
    parity: int | None = None
    configuration: str = ""
    energy_offset_rad_per_us: float = 0.0
    effective_principal_quantum_number: float | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.measurement_label:
            raise ValueError("state name and measurement label are required")
        if not math.isfinite(self.energy_offset_rad_per_us):
            raise ValueError("state energy offset must be finite")
        quantum_values = (
            self.n,
            self.effective_principal_quantum_number,
            self.l,
            self.j,
        )
        if all(value is None for value in quantum_values):
            if any(
                value is not None
                for value in (self.f, self.mf, self.mj, self.parity)
            ):
                raise ValueError("sink states cannot carry angular quantum numbers")
            return
        if (
            self.l is None
            or self.j is None
            or (
                self.n is None
                and self.effective_principal_quantum_number is None
            )
        ):
            raise ValueError(
                "physical states require l, j and either integer n or "
                "effective principal quantum number"
            )
        if (
            (
                self.n is not None
                and (
                    not math.isfinite(float(self.n))
                    or int(self.n) != self.n
                    or int(self.n) <= 0
                )
            )
            or (
                self.effective_principal_quantum_number is not None
                and (
                    not math.isfinite(
                        self.effective_principal_quantum_number
                    )
                    or self.effective_principal_quantum_number <= 0
                )
            )
            or int(self.l) != self.l
            or int(self.l) < 0
            or not _is_half_integer(float(self.j))
            or float(self.j) < 0
            or not _is_half_integer(float(self.s))
            or float(self.s) < 0
        ):
            raise ValueError(
                "n, effective principal quantum number, l, j or s is invalid"
            )
        if self.f is not None:
            if (
                self.mf is None
                or not _is_half_integer(self.f)
                or self.f < 0
                or not _is_half_integer(self.mf)
                or abs(self.mf) > self.f
            ):
                raise ValueError("hyperfine states require valid F and mF")
        elif self.mf is not None:
            raise ValueError("mF requires F")
        if self.mj is not None and (
            not _is_half_integer(self.mj) or abs(self.mj) > float(self.j)
        ):
            raise ValueError("mJ must be a valid projection of J")
        if self.mf is not None and self.mj is not None:
            raise ValueError("choose either the coupled F,mF or J,mJ basis")
        if self.mf is None and self.mj is None:
            raise ValueError("physical sublevels require mF or mJ")
        if self.parity not in (None, -1, 1):
            raise ValueError("parity must be -1, +1 or unspecified")

    @property
    def is_sink(self) -> bool:
        return (
            self.n is None
            and self.effective_principal_quantum_number is None
        )

    @property
    def integer_n(self) -> int:
        if self.n is None:
            raise ValueError(
                f"state {self.name} does not have an integer principal n"
            )
        return int(self.n)


@dataclass(frozen=True)
class MagneticFieldDescriptor:
    """Nominal laboratory magnetic field and longitudinal noise scales."""

    vector_g: tuple[float, float, float]
    zero_field_quantization_axis_xyz: tuple[float, float, float] = (
        0.0,
        0.0,
        1.0,
    )
    iteration_common_sigma_g: float = 0.0
    shot_common_sigma_g: float = 0.0
    shot_local_sigma_g: float = 0.0
    within_shot_common_sigma_g: float = 0.0
    within_shot_local_sigma_g: float = 0.0
    within_shot_correlation_time_us: float = 1.0
    sample_interval_us: float = 0.01

    def __post_init__(self) -> None:
        vector = np.asarray(self.vector_g, dtype=float)
        if vector.shape != (3,) or not np.all(np.isfinite(vector)):
            raise ValueError("magnetic field must be a finite three-vector")
        axis = _unit_real_vector(
            self.zero_field_quantization_axis_xyz,
            label="zero-field quantization axis",
        )
        sigmas = (
            self.iteration_common_sigma_g,
            self.shot_common_sigma_g,
            self.shot_local_sigma_g,
            self.within_shot_common_sigma_g,
            self.within_shot_local_sigma_g,
        )
        if (
            any(not math.isfinite(value) or value < 0 for value in sigmas)
            or self.within_shot_correlation_time_us <= 0
            or self.sample_interval_us <= 0
        ):
            raise ValueError("magnetic noise scales and time constants are invalid")
        object.__setattr__(
            self,
            "vector_g",
            tuple(float(value) for value in vector),
        )
        object.__setattr__(
            self,
            "zero_field_quantization_axis_xyz",
            axis,
        )

    @property
    def magnitude_g(self) -> float:
        return float(np.linalg.norm(self.vector_g))

    @property
    def quantization_axis_xyz(self) -> tuple[float, float, float]:
        if self.magnitude_g == 0:
            return self.zero_field_quantization_axis_xyz
        return _unit_real_vector(
            self.vector_g,
            label="magnetic-field direction",
        )

    @property
    def has_noise(self) -> bool:
        return any(
            value > 0
            for value in (
                self.iteration_common_sigma_g,
                self.shot_common_sigma_g,
                self.shot_local_sigma_g,
                self.within_shot_common_sigma_g,
                self.within_shot_local_sigma_g,
            )
        )


@dataclass(frozen=True)
class LaserFieldDescriptor:
    """One physical laser in laboratory Cartesian coordinates."""

    name: str
    wavelength_nm: float
    propagation_direction_xyz: tuple[float, float, float]
    polarization_xyz: tuple[complex, complex, complex]
    detuning_rad_per_us: float = 0.0
    max_rabi_rad_per_us: float = 2.0 * math.pi * 100.0
    max_abs_detuning_rad_per_us: float = 2.0 * math.pi * 1000.0
    addressing: str = "global"

    def __post_init__(self) -> None:
        if (
            not self.name
            or not math.isfinite(self.wavelength_nm)
            or self.wavelength_nm <= 0
            or not math.isfinite(self.detuning_rad_per_us)
            or self.max_rabi_rad_per_us <= 0
            or self.max_abs_detuning_rad_per_us < 0
            or self.addressing not in {"global", "local"}
        ):
            raise ValueError("laser field parameters are invalid")
        direction = _unit_real_vector(
            self.propagation_direction_xyz,
            label="laser propagation direction",
        )
        polarization = np.asarray(self.polarization_xyz, dtype=complex)
        if polarization.shape != (3,) or not np.all(
            np.isfinite(polarization.real)
            & np.isfinite(polarization.imag)
        ):
            raise ValueError("laser polarization must be a finite complex vector")
        norm = float(np.linalg.norm(polarization))
        if norm == 0:
            raise ValueError("laser polarization must be non-zero")
        polarization = polarization / norm
        if abs(np.dot(np.asarray(direction), polarization)) > 1e-9:
            raise ValueError("laser polarization must be transverse to propagation")
        object.__setattr__(self, "propagation_direction_xyz", direction)
        object.__setattr__(
            self,
            "polarization_xyz",
            tuple(complex(value) for value in polarization),
        )

    def spherical_polarization(
        self,
        quantization_axis_xyz: Sequence[float],
    ) -> Mapping[int, complex]:
        """Return ``q=-1,0,+1`` amplitudes around the quantization axis.

        A deterministic transverse phase reference is constructed by projecting
        the laboratory x axis, or y when necessary, perpendicular to the
        quantization axis.
        """

        z_axis = np.asarray(
            _unit_real_vector(
                quantization_axis_xyz,
                label="quantization axis",
            )
        )
        reference = (
            np.asarray((1.0, 0.0, 0.0))
            if abs(z_axis[0]) < 0.9
            else np.asarray((0.0, 1.0, 0.0))
        )
        x_axis = reference - float(np.dot(reference, z_axis)) * z_axis
        x_axis = x_axis / np.linalg.norm(x_axis)
        y_axis = np.cross(z_axis, x_axis)
        polarization = np.asarray(self.polarization_xyz, dtype=complex)
        x_value = complex(np.dot(x_axis, polarization))
        y_value = complex(np.dot(y_axis, polarization))
        z_value = complex(np.dot(z_axis, polarization))
        components = {
            -1: (x_value + 1j * y_value) / math.sqrt(2.0),
            0: z_value,
            1: -(x_value - 1j * y_value) / math.sqrt(2.0),
        }
        return MappingProxyType(components)


@dataclass(frozen=True)
class LaserTransitionDescriptor:
    """One state-to-state transition driven by a named laser."""

    name: str
    lower_level: str
    upper_level: str
    laser: str
    reference_for_laser: bool = False

    def __post_init__(self) -> None:
        if (
            not self.name
            or not self.lower_level
            or not self.upper_level
            or not self.laser
            or self.lower_level == self.upper_level
        ):
            raise ValueError("laser transition descriptor is invalid")


@dataclass(frozen=True)
class SpectroscopicLevelRecord:
    """Provider-resolved level metadata retained outside the rotating frame."""

    state: AtomicStateDescriptor
    fine_structure_energy_ev: float | None
    internal_shift_rad_per_us: float


class AtomicDataProvider(Protocol):
    """Atomic structure boundary used by the environment compiler."""

    @property
    def provider_name(self) -> str: ...

    @property
    def provenance(self) -> tuple[ParameterProvenance, ...]: ...

    def fine_structure_energy_ev(
        self,
        state: AtomicStateDescriptor,
    ) -> float | None: ...

    def internal_energy_shift_rad_per_us(
        self,
        state: AtomicStateDescriptor,
        magnetic_field: MagneticFieldDescriptor,
    ) -> float: ...

    def zeeman_expansion_rad_per_us(
        self,
        state: AtomicStateDescriptor,
        bias_field_g: float,
    ) -> tuple[float, float]: ...

    def transition_wavelength_nm(
        self,
        lower: AtomicStateDescriptor,
        upper: AtomicStateDescriptor,
    ) -> float | None: ...

    def dipole_matrix_element_ea0(
        self,
        lower: AtomicStateDescriptor,
        upper: AtomicStateDescriptor,
        q: int,
    ) -> complex: ...


class ArcAlkaliAtomicDataProvider:
    """ARC 3.10.2 adapter for supported alkali species.

    Hyperfine states use ARC's exact Breit--Rabi diagonalization at the
    configured field magnitude.  The quantization axis is taken along the
    laboratory field vector, so its direction enters the polarization
    decomposition while the eigenenergies depend on the magnitude.
    """

    _SPECIES = {
        "cs133": "Caesium",
        "rb87": "Rubidium87",
        "rb85": "Rubidium85",
    }

    def __init__(self, species: str) -> None:
        normalized = species.lower().replace("-", "").replace("_", "")
        if normalized not in self._SPECIES:
            raise ValueError(
                f"ARC alkali provider does not support species {species!r}"
            )
        try:
            import arc
        except ImportError as exc:
            raise RuntimeError(
                "install the 'atomic' optional dependency to use ARC"
            ) from exc
        atom_class = getattr(arc, self._SPECIES[normalized])
        self._arc = arc
        self._atom = atom_class()
        self._species = normalized

    @property
    def provider_name(self) -> str:
        return f"ARC-{self._arc.__version__}-{self._species}"

    @property
    def provenance(self) -> tuple[ParameterProvenance, ...]:
        return (
            ParameterProvenance(
                "atomic_data_provider",
                float(self._arc.__version__.split(".")[0]),
                "software-major-version",
                "reference",
                "https://github.com/nikolasibalic/ARC-Alkali-Rydberg-Calculator",
                f"ARC {self._arc.__version__}, {self._species}",
                "energies, HFS, Breit-Rabi and dipole matrix elements",
                self._arc.__version__,
            ),
        )

    def _validate_physical(self, state: AtomicStateDescriptor) -> None:
        if state.is_sink:
            raise ValueError(f"sink state {state.name} has no atomic data")
        state.integer_n

    def fine_structure_energy_ev(
        self,
        state: AtomicStateDescriptor,
    ) -> float | None:
        if state.is_sink:
            return None
        self._validate_physical(state)
        return float(
            self._atom.getEnergy(
                state.integer_n,
                int(state.l),
                float(state.j),
                s=float(state.s),
            )
        )

    def _hyperfine_breit_rabi_hz(
        self,
        state: AtomicStateDescriptor,
        field_g: float,
    ) -> float:
        fields_t = np.asarray((field_g * GAUSS_TO_TESLA,), dtype=float)
        energies_hz, f_values, mf_values = self._atom.breitRabi(
            state.integer_n,
            int(state.l),
            float(state.j),
            fields_t,
        )
        matches = np.flatnonzero(
            np.isclose(f_values, state.f, rtol=0.0, atol=1e-10)
            & np.isclose(mf_values, state.mf, rtol=0.0, atol=1e-10)
        )
        if len(matches) != 1:
            raise ValueError(
                f"ARC could not resolve F,mF for state {state.name}"
            )
        return float(np.asarray(energies_hz)[0, int(matches[0])])

    def internal_energy_shift_rad_per_us(
        self,
        state: AtomicStateDescriptor,
        magnetic_field: MagneticFieldDescriptor,
    ) -> float:
        if state.is_sink:
            return state.energy_offset_rad_per_us
        self._validate_physical(state)
        if state.f is not None:
            atomic_shift = (
                self._hyperfine_breit_rabi_hz(
                    state,
                    magnetic_field.magnitude_g,
                )
                * HZ_TO_RAD_PER_US
            )
        else:
            energy_j = self._atom.getZeemanEnergyShift(
                int(state.l),
                float(state.j),
                float(state.mj),
                magnetic_field.magnitude_g * GAUSS_TO_TESLA,
                s=float(state.s),
            )
            atomic_shift = float(energy_j) / hbar * 1e-6
        return atomic_shift + state.energy_offset_rad_per_us

    def _field_dependent_shift(
        self,
        state: AtomicStateDescriptor,
        field_g: float,
    ) -> float:
        if state.f is not None:
            atomic_shift = (
                self._hyperfine_breit_rabi_hz(state, field_g)
                * HZ_TO_RAD_PER_US
            )
        else:
            energy_j = self._atom.getZeemanEnergyShift(
                int(state.l),
                float(state.j),
                float(state.mj),
                field_g * GAUSS_TO_TESLA,
                s=float(state.s),
            )
            atomic_shift = float(energy_j) / hbar * 1e-6
        return atomic_shift + state.energy_offset_rad_per_us

    def zeeman_expansion_rad_per_us(
        self,
        state: AtomicStateDescriptor,
        bias_field_g: float,
    ) -> tuple[float, float]:
        if state.is_sink:
            return (0.0, 0.0)
        step_g = max(1e-4, abs(bias_field_g) * 1e-5)
        minus = self._field_dependent_shift(state, bias_field_g - step_g)
        center = self._field_dependent_shift(state, bias_field_g)
        plus = self._field_dependent_shift(state, bias_field_g + step_g)
        linear = (plus - minus) / (2.0 * step_g)
        quadratic = (plus - 2.0 * center + minus) / (2.0 * step_g**2)
        return (linear, quadratic)

    def transition_wavelength_nm(
        self,
        lower: AtomicStateDescriptor,
        upper: AtomicStateDescriptor,
    ) -> float | None:
        self._validate_physical(lower)
        self._validate_physical(upper)
        wavelength_m = self._atom.getTransitionWavelength(
            lower.integer_n,
            int(lower.l),
            float(lower.j),
            upper.integer_n,
            int(upper.l),
            float(upper.j),
            s=float(lower.s),
            s2=float(upper.s),
        )
        return abs(float(wavelength_m)) * 1e9

    def dipole_matrix_element_ea0(
        self,
        lower: AtomicStateDescriptor,
        upper: AtomicStateDescriptor,
        q: int,
    ) -> complex:
        if q not in (-1, 0, 1):
            raise ValueError("dipole polarization q must be -1, 0 or +1")
        self._validate_physical(lower)
        self._validate_physical(upper)
        if lower.f is not None and upper.f is not None:
            value = self._atom.getDipoleMatrixElementHFS(
                lower.integer_n,
                int(lower.l),
                float(lower.j),
                float(lower.f),
                float(lower.mf),
                upper.integer_n,
                int(upper.l),
                float(upper.j),
                float(upper.f),
                float(upper.mf),
                q,
                s=float(lower.s),
            )
        elif lower.mj is not None and upper.mj is not None:
            value = self._atom.getDipoleMatrixElement(
                lower.integer_n,
                int(lower.l),
                float(lower.j),
                float(lower.mj),
                upper.integer_n,
                int(upper.l),
                float(upper.j),
                float(upper.mj),
                q,
                s=float(lower.s),
            )
        elif lower.f is not None and upper.mj is not None:
            value = self._atom.getDipoleMatrixElementHFStoFS(
                lower.integer_n,
                int(lower.l),
                float(lower.j),
                float(lower.f),
                float(lower.mf),
                upper.integer_n,
                int(upper.l),
                float(upper.j),
                float(upper.mj),
                q,
                s=float(lower.s),
            )
        else:
            raise ValueError(
                "ARC mixed fine-to-hyperfine reverse coupling is not exposed; "
                "reverse the transition or use a tabulated provider"
            )
        return complex(value)


@dataclass(frozen=True)
class TabulatedAtomicDataProvider:
    """Data-backed provider for Yb, measured values or frozen calculations."""

    name: str
    internal_shifts_rad_per_us: Mapping[str, float]
    dipoles_ea0: Mapping[tuple[str, str, int], complex]
    wavelengths_nm: Mapping[tuple[str, str], float] = field(
        default_factory=dict
    )
    fine_energies_ev: Mapping[str, float] = field(default_factory=dict)
    zeeman_coefficients: Mapping[str, tuple[float, float]] = field(
        default_factory=dict
    )
    source: str = "user-supplied table"

    def __post_init__(self) -> None:
        if not self.name or not self.source:
            raise ValueError("tabulated provider name and source are required")
        object.__setattr__(
            self,
            "internal_shifts_rad_per_us",
            MappingProxyType(dict(self.internal_shifts_rad_per_us)),
        )
        object.__setattr__(
            self,
            "dipoles_ea0",
            MappingProxyType(dict(self.dipoles_ea0)),
        )
        object.__setattr__(
            self,
            "wavelengths_nm",
            MappingProxyType(dict(self.wavelengths_nm or {})),
        )
        object.__setattr__(
            self,
            "fine_energies_ev",
            MappingProxyType(dict(self.fine_energies_ev or {})),
        )
        object.__setattr__(
            self,
            "zeeman_coefficients",
            MappingProxyType(dict(self.zeeman_coefficients or {})),
        )

    @property
    def provider_name(self) -> str:
        return self.name

    @property
    def provenance(self) -> tuple[ParameterProvenance, ...]:
        return (
            ParameterProvenance(
                "atomic_data_provider",
                1.0,
                "table",
                "configured",
                self.source,
                self.name,
            ),
        )

    def fine_structure_energy_ev(
        self,
        state: AtomicStateDescriptor,
    ) -> float | None:
        return self.fine_energies_ev.get(state.name)

    def internal_energy_shift_rad_per_us(
        self,
        state: AtomicStateDescriptor,
        magnetic_field: MagneticFieldDescriptor,
    ) -> float:
        linear, quadratic = self.zeeman_coefficients.get(
            state.name,
            (0.0, 0.0),
        )
        field = magnetic_field.magnitude_g
        return (
            self.internal_shifts_rad_per_us.get(state.name, 0.0)
            + linear * field
            + quadratic * field**2
            + state.energy_offset_rad_per_us
        )

    def zeeman_expansion_rad_per_us(
        self,
        state: AtomicStateDescriptor,
        bias_field_g: float,
    ) -> tuple[float, float]:
        linear, quadratic = self.zeeman_coefficients.get(
            state.name,
            (0.0, 0.0),
        )
        return (linear + 2.0 * quadratic * bias_field_g, quadratic)

    def transition_wavelength_nm(
        self,
        lower: AtomicStateDescriptor,
        upper: AtomicStateDescriptor,
    ) -> float | None:
        direct = self.wavelengths_nm.get((lower.name, upper.name))
        if direct is not None:
            return direct
        return self.wavelengths_nm.get((upper.name, lower.name))

    def dipole_matrix_element_ea0(
        self,
        lower: AtomicStateDescriptor,
        upper: AtomicStateDescriptor,
        q: int,
    ) -> complex:
        direct = self.dipoles_ea0.get((lower.name, upper.name, q))
        if direct is not None:
            return complex(direct)
        reverse = self.dipoles_ea0.get((upper.name, lower.name, -q))
        if reverse is None:
            return 0.0 + 0.0j
        return complex(reverse).conjugate()


@dataclass(frozen=True)
class PairHamiltonianTerms:
    interactions: tuple[PairInteractionSpec, ...] = ()
    couplings: tuple[PairCouplingSpec, ...] = ()
    provenance: tuple[ParameterProvenance, ...] = ()


class PairHamiltonianProvider(Protocol):
    """Geometry-dependent pair-Hamiltonian boundary."""

    def terms_for_pair(
        self,
        *,
        atom_pair: tuple[int, int],
        separation_vector_um: tuple[float, float, float],
        magnetic_field: MagneticFieldDescriptor,
        states: Mapping[str, AtomicStateDescriptor],
    ) -> PairHamiltonianTerms: ...


@dataclass(frozen=True)
class PowerLawPairHamiltonianProvider:
    """Reusable reduced pair model with optional axial anisotropy.

    The angular factor is ``1 + beta*P2(cos(theta))`` around the magnetic
    quantization axis.  It is useful for mechanism tests and fitted effective
    models; it is not a replacement for an ARC/PairInteraction/MQDT provider.
    """

    first_level: str
    second_level: str
    coefficient_rad_per_us_um_power: float
    power: float = 6.0
    anisotropy_beta: float = 0.0
    symmetric: bool = True
    label: str = "power-law-pair"
    source: str = "configured effective model"

    def __post_init__(self) -> None:
        if (
            not self.first_level
            or not self.second_level
            or not self.label
            or not math.isfinite(self.coefficient_rad_per_us_um_power)
            or not math.isfinite(self.power)
            or self.power <= 0
            or not math.isfinite(self.anisotropy_beta)
        ):
            raise ValueError("power-law pair provider parameters are invalid")

    def terms_for_pair(
        self,
        *,
        atom_pair: tuple[int, int],
        separation_vector_um: tuple[float, float, float],
        magnetic_field: MagneticFieldDescriptor,
        states: Mapping[str, AtomicStateDescriptor],
    ) -> PairHamiltonianTerms:
        missing = {self.first_level, self.second_level} - set(states)
        if missing:
            raise ValueError(f"pair provider references unknown levels {missing}")
        vector = np.asarray(separation_vector_um, dtype=float)
        distance = float(np.linalg.norm(vector))
        if distance <= 0:
            raise ValueError("pair separation must be positive")
        direction = vector / distance
        axis = np.asarray(magnetic_field.quantization_axis_xyz)
        cosine = float(np.dot(direction, axis))
        p2 = 0.5 * (3.0 * cosine**2 - 1.0)
        angular_factor = 1.0 + self.anisotropy_beta * p2
        strength = (
            self.coefficient_rad_per_us_um_power
            * angular_factor
            / distance**self.power
        )
        interaction = PairInteractionSpec(
            self.first_level,
            self.second_level,
            strength,
            self.symmetric,
            self.label,
            atom_pair,
        )
        provenance = (
            ParameterProvenance(
                f"{self.label}:{atom_pair[0]}-{atom_pair[1]}",
                strength,
                "rad/us",
                "configured",
                self.source,
                (
                    f"R={distance:.12g} um, cos(theta)={cosine:.12g}, "
                    f"power={self.power:.12g}, beta={self.anisotropy_beta:.12g}"
                ),
            ),
        )
        return PairHamiltonianTerms((interaction,), (), provenance)


@dataclass(frozen=True)
class TabulatedPairInteractionCurve:
    """One diagonal product-state matrix element sampled versus distance."""

    first_level: str
    second_level: str
    values_rad_per_us: tuple[float, ...]
    symmetric: bool = True
    label: str = "tabulated-pair-interaction"

    def __post_init__(self) -> None:
        values = tuple(float(value) for value in self.values_rad_per_us)
        if (
            not self.first_level
            or not self.second_level
            or not self.label
            or not values
            or not all(math.isfinite(value) for value in values)
        ):
            raise ValueError("tabulated pair-interaction curve is invalid")
        object.__setattr__(self, "values_rad_per_us", values)


@dataclass(frozen=True)
class TabulatedPairCouplingCurve:
    """One off-diagonal product-state matrix element sampled versus distance."""

    source_levels: tuple[str, str]
    target_levels: tuple[str, str]
    values_rad_per_us: tuple[complex, ...]
    label: str = "tabulated-pair-coupling"

    def __post_init__(self) -> None:
        source = tuple(self.source_levels)
        target = tuple(self.target_levels)
        values = tuple(complex(value) for value in self.values_rad_per_us)
        if (
            len(source) != 2
            or len(target) != 2
            or not all(source)
            or not all(target)
            or source == target
            or not self.label
            or not values
            or not all(
                math.isfinite(value.real) and math.isfinite(value.imag)
                for value in values
            )
        ):
            raise ValueError("tabulated pair-coupling curve is invalid")
        object.__setattr__(self, "source_levels", source)
        object.__setattr__(self, "target_levels", target)
        object.__setattr__(self, "values_rad_per_us", values)


@dataclass(frozen=True)
class TabulatedPairHamiltonianProvider:
    """Interpolate a frozen product-basis pair Hamiltonian over distance.

    The table can be exported from ARC, PairInteraction, an MQDT calculation,
    or an experimentally fitted model.  Diagonal curves become
    :class:`PairInteractionSpec` objects and off-diagonal curves become
    :class:`PairCouplingSpec` objects.  Consequently the existing tensor-product
    backend performs the pair-state mixing; the table must be expressed in the
    configured local product basis rather than an undocumented eigenbasis.

    A one-dimensional distance interpolation is intentionally strict.  When a
    table was computed for one field vector or one pair direction, provide the
    corresponding reference and tolerances.  Queries outside that domain are
    rejected rather than silently applying a radial curve to a different
    angular or Zeeman configuration.
    """

    distances_um: tuple[float, ...]
    interactions: tuple[TabulatedPairInteractionCurve, ...] = ()
    couplings: tuple[TabulatedPairCouplingCurve, ...] = ()
    source: str = "user-supplied pair-Hamiltonian table"
    table_version: str = ""
    reference_direction_xyz: tuple[float, float, float] | None = None
    maximum_direction_angle_rad: float = 0.0
    reference_magnetic_field_g: tuple[float, float, float] | None = None
    maximum_field_deviation_g: float = 0.0

    def __post_init__(self) -> None:
        distances = tuple(float(value) for value in self.distances_um)
        if (
            len(distances) < 2
            or not all(math.isfinite(value) and value > 0 for value in distances)
            or any(
                second <= first
                for first, second in zip(distances, distances[1:])
            )
            or (not self.interactions and not self.couplings)
            or not self.source
            or not math.isfinite(self.maximum_direction_angle_rad)
            or self.maximum_direction_angle_rad < 0
            or not math.isfinite(self.maximum_field_deviation_g)
            or self.maximum_field_deviation_g < 0
        ):
            raise ValueError("tabulated pair-Hamiltonian provider is invalid")
        expected = len(distances)
        if any(
            len(curve.values_rad_per_us) != expected
            for curve in (*self.interactions, *self.couplings)
        ):
            raise ValueError("every pair curve must match the distance grid")
        direction = self.reference_direction_xyz
        if direction is not None:
            direction = _unit_real_vector(
                direction,
                label="pair-table reference direction",
            )
        field_vector = self.reference_magnetic_field_g
        if field_vector is not None:
            field_array = np.asarray(field_vector, dtype=float)
            if field_array.shape != (3,) or not np.all(np.isfinite(field_array)):
                raise ValueError(
                    "pair-table reference magnetic field must be finite"
                )
            field_vector = tuple(float(value) for value in field_array)
        object.__setattr__(self, "distances_um", distances)
        object.__setattr__(self, "reference_direction_xyz", direction)
        object.__setattr__(
            self,
            "reference_magnetic_field_g",
            field_vector,
        )

    def _validate_domain(
        self,
        separation_vector_um: tuple[float, float, float],
        magnetic_field: MagneticFieldDescriptor,
    ) -> float:
        vector = np.asarray(separation_vector_um, dtype=float)
        distance = float(np.linalg.norm(vector))
        if distance < self.distances_um[0] or distance > self.distances_um[-1]:
            raise ValueError(
                f"pair distance {distance:.12g} um is outside table range "
                f"[{self.distances_um[0]:.12g}, {self.distances_um[-1]:.12g}]"
            )
        if self.reference_direction_xyz is not None:
            direction = vector / distance
            cosine = float(
                np.clip(
                    np.dot(direction, self.reference_direction_xyz),
                    -1.0,
                    1.0,
                )
            )
            angle = math.acos(cosine)
            if angle > self.maximum_direction_angle_rad + 1e-12:
                raise ValueError(
                    "pair direction is outside the tabulated angular domain"
                )
        if self.reference_magnetic_field_g is not None:
            deviation = float(
                np.linalg.norm(
                    np.asarray(magnetic_field.vector_g)
                    - np.asarray(self.reference_magnetic_field_g)
                )
            )
            if deviation > self.maximum_field_deviation_g + 1e-12:
                raise ValueError(
                    "magnetic field is outside the tabulated pair-Hamiltonian "
                    "domain"
                )
        return distance

    def _interpolate_real(
        self,
        distance_um: float,
        values: Sequence[float],
    ) -> float:
        return float(np.interp(distance_um, self.distances_um, values))

    def _interpolate_complex(
        self,
        distance_um: float,
        values: Sequence[complex],
    ) -> complex:
        array = np.asarray(tuple(values), dtype=complex)
        return complex(
            np.interp(distance_um, self.distances_um, array.real),
            np.interp(distance_um, self.distances_um, array.imag),
        )

    def terms_for_pair(
        self,
        *,
        atom_pair: tuple[int, int],
        separation_vector_um: tuple[float, float, float],
        magnetic_field: MagneticFieldDescriptor,
        states: Mapping[str, AtomicStateDescriptor],
    ) -> PairHamiltonianTerms:
        distance = self._validate_domain(
            separation_vector_um,
            magnetic_field,
        )
        known_levels = set(states)
        interactions: list[PairInteractionSpec] = []
        couplings: list[PairCouplingSpec] = []
        provenance: list[ParameterProvenance] = []
        for curve in self.interactions:
            missing = {curve.first_level, curve.second_level} - known_levels
            if missing:
                raise ValueError(
                    f"pair table references unknown levels {sorted(missing)}"
                )
            value = self._interpolate_real(
                distance,
                curve.values_rad_per_us,
            )
            interactions.append(
                PairInteractionSpec(
                    curve.first_level,
                    curve.second_level,
                    value,
                    curve.symmetric,
                    curve.label,
                    atom_pair,
                )
            )
            provenance.append(
                ParameterProvenance(
                    f"{curve.label}:{atom_pair[0]}-{atom_pair[1]}",
                    value,
                    "rad/us",
                    "interpolated-table",
                    self.source,
                    f"R={distance:.12g} um",
                    software_version=self.table_version,
                )
            )
        for curve in self.couplings:
            missing = {
                *curve.source_levels,
                *curve.target_levels,
            } - known_levels
            if missing:
                raise ValueError(
                    f"pair table references unknown levels {sorted(missing)}"
                )
            value = self._interpolate_complex(
                distance,
                curve.values_rad_per_us,
            )
            if abs(value) <= 1e-15:
                continue
            couplings.append(
                PairCouplingSpec(
                    curve.source_levels,
                    curve.target_levels,
                    value,
                    curve.label,
                    atom_pair,
                )
            )
            provenance.append(
                ParameterProvenance(
                    f"{curve.label}:{atom_pair[0]}-{atom_pair[1]}",
                    abs(value),
                    "rad/us",
                    "interpolated-table",
                    self.source,
                    f"R={distance:.12g} um; stored value is |matrix element|",
                    software_version=self.table_version,
                )
            )
        return PairHamiltonianTerms(
            tuple(interactions),
            tuple(couplings),
            tuple(provenance),
        )


@dataclass(frozen=True)
class AtomicEnvironmentDescription:
    """Complete quantum-number-level input to the generic compiler."""

    atom_positions_um: tuple[tuple[float, ...], ...]
    states: tuple[AtomicStateDescriptor, ...]
    computational_levels: tuple[str, str]
    lasers: tuple[LaserFieldDescriptor, ...]
    transitions: tuple[LaserTransitionDescriptor, ...]
    magnetic_field: MagneticFieldDescriptor
    decays: tuple[DecaySpec, ...] = ()
    pair_provider: PairHamiltonianProvider | None = None
    profile_name: str = "compiled-atomic-environment"

    def __post_init__(self) -> None:
        positions = tuple(_pad_position(position) for position in self.atom_positions_um)
        if not positions:
            raise ValueError("at least one atom position is required")
        state_names = tuple(state.name for state in self.states)
        laser_names = tuple(laser.name for laser in self.lasers)
        transition_names = tuple(item.name for item in self.transitions)
        if (
            not self.profile_name
            or not state_names
            or len(state_names) != len(set(state_names))
            or not laser_names
            or len(laser_names) != len(set(laser_names))
            or not transition_names
            or len(transition_names) != len(set(transition_names))
            or len(self.computational_levels) != 2
            or set(self.computational_levels) - set(state_names)
        ):
            raise ValueError("atomic environment identifiers are invalid")
        for transition in self.transitions:
            if (
                transition.lower_level not in state_names
                or transition.upper_level not in state_names
                or transition.laser not in laser_names
            ):
                raise ValueError(
                    f"transition {transition.name} references an unknown object"
                )
        object.__setattr__(self, "atom_positions_um", positions)


@dataclass(frozen=True)
class AtomicEnvironmentCompilation:
    """Compiler output plus spectroscopic and magnetic diagnostics."""

    environment: MultilevelEnvironmentConfig
    levels: tuple[SpectroscopicLevelRecord, ...]
    magnetic_noise: MagneticFieldNoiseModel | None
    warnings: tuple[str, ...] = ()


def _transition_coupling(
    provider: AtomicDataProvider,
    lower: AtomicStateDescriptor,
    upper: AtomicStateDescriptor,
    laser: LaserFieldDescriptor,
    quantization_axis_xyz: Sequence[float],
) -> complex:
    polarization = laser.spherical_polarization(quantization_axis_xyz)
    return sum(
        polarization[q] * provider.dipole_matrix_element_ea0(lower, upper, q)
        for q in (-1, 0, 1)
    )


def compile_atomic_environment(
    description: AtomicEnvironmentDescription,
    provider: AtomicDataProvider,
) -> AtomicEnvironmentCompilation:
    """Compile quantum numbers, fields, geometry and provider data.

    The static Hamiltonian contains provider-resolved internal HFS/Zeeman
    shifts and each laser's nominal detuning on its upper levels.  Pulse
    detuning therefore represents an additional scan around that nominal
    setting.
    """

    states = {state.name: state for state in description.states}
    lasers = {laser.name: laser for laser in description.lasers}
    level_records = tuple(
        SpectroscopicLevelRecord(
            state,
            provider.fine_structure_energy_ev(state),
            provider.internal_energy_shift_rad_per_us(
                state,
                description.magnetic_field,
            ),
        )
        for state in description.states
    )
    static_energies = {
        record.state.name: record.internal_shift_rad_per_us
        for record in level_records
    }
    transition_specs: dict[str, TransitionSpec] = {}
    channel_specs: dict[str, ChannelSpec] = {}
    upper_laser: dict[str, str] = {}
    warnings: list[str] = []

    for laser_name, laser in lasers.items():
        driven = tuple(
            transition
            for transition in description.transitions
            if transition.laser == laser_name
        )
        if not driven:
            raise ValueError(f"laser {laser_name} drives no transitions")
        references = tuple(item for item in driven if item.reference_for_laser)
        if len(references) > 1:
            raise ValueError(f"laser {laser_name} has multiple references")
        couplings: dict[str, complex] = {}
        detuning_adjusted_levels: set[str] = set()
        for transition in driven:
            previous = upper_laser.get(transition.upper_level)
            if previous is not None and previous != laser_name:
                raise ValueError(
                    f"upper level {transition.upper_level} is assigned to "
                    "multiple rotating laser frames"
                )
            upper_laser[transition.upper_level] = laser_name
            lower = states[transition.lower_level]
            upper = states[transition.upper_level]
            if lower.is_sink or upper.is_sink:
                raise ValueError("laser transitions cannot address sink states")
            transition_specs[transition.name] = TransitionSpec(
                transition.name,
                transition.lower_level,
                transition.upper_level,
                {transition.upper_level: -1.0},
            )
            couplings[transition.name] = _transition_coupling(
                provider,
                lower,
                upper,
                laser,
                description.magnetic_field.quantization_axis_xyz,
            )
            if transition.upper_level not in detuning_adjusted_levels:
                static_energies[transition.upper_level] -= (
                    laser.detuning_rad_per_us
                )
                detuning_adjusted_levels.add(transition.upper_level)
        reference = references[0] if references else driven[0]
        reference_coupling = couplings[reference.name]
        if abs(reference_coupling) <= 1e-15:
            raise ValueError(
                f"reference transition {reference.name} has zero coupling"
            )
        relative = {
            name: value / reference_coupling
            for name, value in couplings.items()
        }
        for name, value in relative.items():
            if abs(value) <= 1e-15:
                warnings.append(
                    f"transition {name} is dark for the configured polarization"
                )
        additional = tuple(
            TransitionCouplingSpec(item.name, relative[item.name])
            for item in driven
            if item.name != reference.name
        )
        channel_specs[laser_name] = ChannelSpec(
            laser_name,
            reference.name,
            laser.addressing,
            laser.max_rabi_rad_per_us,
            laser.max_abs_detuning_rad_per_us,
            additional_transition_couplings=additional,
        )

    pair_interactions: list[PairInteractionSpec] = []
    pair_couplings: list[PairCouplingSpec] = []
    provenance = list(provider.provenance)
    if description.pair_provider is not None:
        positions = tuple(np.asarray(position, dtype=float) for position in description.atom_positions_um)
        for first in range(len(positions)):
            for second in range(first + 1, len(positions)):
                terms = description.pair_provider.terms_for_pair(
                    atom_pair=(first, second),
                    separation_vector_um=tuple(
                        float(value)
                        for value in positions[second] - positions[first]
                    ),
                    magnetic_field=description.magnetic_field,
                    states=states,
                )
                pair_interactions.extend(
                    replace(term, atom_pair=(first, second))
                    for term in terms.interactions
                )
                pair_couplings.extend(
                    replace(term, atom_pair=(first, second))
                    for term in terms.couplings
                )
                provenance.extend(terms.provenance)

    model = MultilevelModelConfig(
        levels=tuple(
            LevelSpec(state.name, state.measurement_label)
            for state in description.states
        ),
        computational_levels=description.computational_levels,
        transitions=transition_specs,
        static_level_energies_rad_per_us=static_energies,
        decays=description.decays,
        pair_interactions=tuple(pair_interactions),
        pair_couplings=tuple(pair_couplings),
    )
    controls: dict[str, float] = {
        "magnetic_field_x_g": description.magnetic_field.vector_g[0],
        "magnetic_field_y_g": description.magnetic_field.vector_g[1],
        "magnetic_field_z_g": description.magnetic_field.vector_g[2],
        "magnetic_field_magnitude_g": description.magnetic_field.magnitude_g,
    }
    for laser in description.lasers:
        controls[f"{laser.name}_wavelength_nm"] = laser.wavelength_nm
        controls[f"{laser.name}_detuning_rad_per_us"] = (
            laser.detuning_rad_per_us
        )
        for axis, value in zip("xyz", laser.propagation_direction_xyz):
            controls[f"{laser.name}_k_direction_{axis}"] = value
    for atom, position in enumerate(description.atom_positions_um):
        for axis, value in zip("xyz", position):
            controls[f"atom_{atom}_position_{axis}_um"] = value

    environment = MultilevelEnvironmentConfig(
        atom_positions_um=description.atom_positions_um,
        channels=channel_specs,
        model=model,
        profile_name=description.profile_name,
        nominal_controls=controls,
        provenance=tuple(provenance),
    )

    magnetic_noise: MagneticFieldNoiseModel | None = None
    if description.magnetic_field.has_noise:
        level_shifts = tuple(
            ZeemanLevelShiftSpec(
                state.name,
                *provider.zeeman_expansion_rad_per_us(
                    state,
                    description.magnetic_field.magnitude_g,
                ),
            )
            for state in description.states
            if not state.is_sink
        )
        magnetic_noise = MagneticFieldNoiseModel(
            bias_field_g=0.0,
            level_shifts=level_shifts,
            iteration_common_sigma_g=(
                description.magnetic_field.iteration_common_sigma_g
            ),
            shot_common_sigma_g=(
                description.magnetic_field.shot_common_sigma_g
            ),
            shot_local_sigma_g=description.magnetic_field.shot_local_sigma_g,
            within_shot_common_sigma_g=(
                description.magnetic_field.within_shot_common_sigma_g
            ),
            within_shot_local_sigma_g=(
                description.magnetic_field.within_shot_local_sigma_g
            ),
            within_shot_correlation_time_us=(
                description.magnetic_field.within_shot_correlation_time_us
            ),
            sample_interval_us=description.magnetic_field.sample_interval_us,
            block_prefix=f"{description.profile_name}_magnetic",
        )
    return AtomicEnvironmentCompilation(
        environment,
        level_records,
        magnetic_noise,
        tuple(warnings),
    )
