"""Literature-anchored Cs profiles for the generic multilevel backend."""

from __future__ import annotations

from dataclasses import dataclass
import cmath
import math

from .config import ChannelSpec
from .multilevel_config import (
    DecaySpec,
    LevelSpec,
    MultilevelEnvironmentConfig,
    MultilevelModelConfig,
    PairInteractionSpec,
    ParameterProvenance,
    TransitionSpec,
)


TWOPI = 2.0 * math.pi
GRAHAM_2019_URL = "https://arxiv.org/abs/1908.06103"
RADNAEV_2025_URL = "https://arxiv.org/abs/2408.08288"
ARC_URL = "https://github.com/nikolasibalic/ARC-Alkali-Rydberg-Calculator"


@dataclass(frozen=True)
class RadnaevSingleIntermediateLadderParameters:
    """Analytic parameters for the deliberately reduced Cs ladder.

    ``intermediate_energy_rad_per_us`` is the positive rotating-frame energy
    ``D`` of the unresolved ``7P`` level.  With backend couplings
    ``(Omega/2) exp(-i phi)``, second-order elimination gives

    ``<1|H_eff|r> = -Omega_459*Omega_1040/(4D)
    * exp(-i*(phi_459 + phi_1040))``.

    This helper makes the sign and scaling convention executable.  It is not a
    hyperfine-, polarization-, Clebsch-Gordan-, or Zeeman-resolved Cs model.
    """

    intermediate_energy_rad_per_us: float
    omega_459_rad_per_us: float
    omega_1040_rad_per_us: float

    def __post_init__(self) -> None:
        values = (
            self.intermediate_energy_rad_per_us,
            self.omega_459_rad_per_us,
            self.omega_1040_rad_per_us,
        )
        if not all(math.isfinite(value) and value > 0.0 for value in values):
            raise ValueError("ladder energy and leg Rabi rates must be positive")

    @property
    def effective_rabi_rad_per_us(self) -> float:
        """Positive two-photon Rabi magnitude in the reduced-backend convention."""

        return (
            self.omega_459_rad_per_us
            * self.omega_1040_rad_per_us
            / (2.0 * self.intermediate_energy_rad_per_us)
        )

    @property
    def lower_light_shift_rad_per_us(self) -> float:
        """Positive magnitude of the generated ``-|1><1|`` light shift."""

        return self.omega_459_rad_per_us**2 / (
            4.0 * self.intermediate_energy_rad_per_us
        )

    @property
    def upper_light_shift_rad_per_us(self) -> float:
        """Positive magnitude of the generated ``-|r><r|`` light shift."""

        return self.omega_1040_rad_per_us**2 / (
            4.0 * self.intermediate_energy_rad_per_us
        )

    @property
    def two_photon_compensation_rad_per_us(self) -> float:
        """Static ``|r>`` energy that equalizes the two generated light shifts."""

        return (
            self.omega_1040_rad_per_us**2
            - self.omega_459_rad_per_us**2
        ) / (4.0 * self.intermediate_energy_rad_per_us)

    def schur_effective_coupling(
        self,
        *,
        phase_459_rad: float,
        phase_1040_rad: float,
    ) -> complex:
        """Return ``<1|H_eff|r>`` from the one-level Schur complement."""

        if not (
            math.isfinite(phase_459_rad) and math.isfinite(phase_1040_rad)
        ):
            raise ValueError("optical phases must be finite")
        magnitude = -(
            self.omega_459_rad_per_us
            * self.omega_1040_rad_per_us
            / (4.0 * self.intermediate_energy_rad_per_us)
        )
        return magnitude * cmath.exp(
            -1j * (phase_459_rad + phase_1040_rad)
        )


def radnaev_single_intermediate_ladder_parameters(
    *,
    adiabatic_detuning_scale: float = 1.0,
) -> RadnaevSingleIntermediateLadderParameters:
    """Derive the nominal one-intermediate-state ladder and its scale family.

    The validation scale ``s`` applies
    ``D -> sD`` and ``Omega_459, Omega_1040 -> sqrt(s) Omega``.  It therefore
    holds the effective Rabi rate, both light shifts, and their differential
    compensation fixed while suppressing finite-detuning corrections.
    """

    if (
        not math.isfinite(adiabatic_detuning_scale)
        or adiabatic_detuning_scale <= 0.0
    ):
        raise ValueError("adiabatic_detuning_scale must be finite and positive")

    intermediate_energy = TWOPI * 2100.0 * adiabatic_detuning_scale
    effective_rabi = TWOPI * 3.0
    lower_light_shift = TWOPI * 2.0
    omega_459 = math.sqrt(
        4.0 * intermediate_energy * lower_light_shift
    )
    omega_1040 = (
        2.0 * intermediate_energy * effective_rabi / omega_459
    )
    return RadnaevSingleIntermediateLadderParameters(
        intermediate_energy_rad_per_us=intermediate_energy,
        omega_459_rad_per_us=omega_459,
        omega_1040_rad_per_us=omega_1040,
    )


def equal_leg_rabi_for_effective_drive(
    *,
    one_photon_detuning_rad_per_us: float,
    effective_rabi_rad_per_us: float,
) -> float:
    """Return equal single-photon Rabi rates in the adiabatic convention.

    With Hamiltonian couplings ``Omega_1/2`` and ``Omega_2/2``,
    ``Omega_eff = Omega_1 Omega_2 / (2 |Delta|)``.
    """

    if one_photon_detuning_rad_per_us == 0:
        raise ValueError("one-photon detuning must be non-zero")
    if effective_rabi_rad_per_us <= 0:
        raise ValueError("effective Rabi frequency must be positive")
    return math.sqrt(
        2.0
        * abs(one_photon_detuning_rad_per_us)
        * effective_rabi_rad_per_us
    )


def _cs_ladder_levels() -> tuple[LevelSpec, ...]:
    return (
        LevelSpec("0", "0"),
        LevelSpec("1", "1"),
        LevelSpec("e", "E"),
        LevelSpec("r", "R"),
        LevelSpec("loss", "L"),
    )


def _cs_ladder_transitions() -> dict[str, TransitionSpec]:
    return {
        "01": TransitionSpec("01", "0", "1", {"1": -1.0}),
        "1e": TransitionSpec("1e", "1", "e", {"e": -1.0, "r": -1.0}),
        "er": TransitionSpec("er", "e", "r", {"r": -1.0}),
    }


def graham_2019_scattering_profile(
    *,
    n_atoms: int = 1,
    include_intermediate_decay: bool = True,
    effective_rabi_mhz: float = 4.5,
) -> MultilevelEnvironmentConfig:
    """Cs 66S ladder profile for the published 7P scattering-limit check.

    This deliberately isolates intermediate-state scattering.  Every 7P decay
    is routed to a failure sink, matching the paper's scattering-probability
    calculation rather than asserting a hyperfine-resolved branching model.
    """

    detuning = TWOPI * 680.0
    effective_rabi = TWOPI * effective_rabi_mhz
    leg_rabi = equal_leg_rabi_for_effective_drive(
        one_photon_detuning_rad_per_us=detuning,
        effective_rabi_rad_per_us=effective_rabi,
    )
    lifetime_us = 0.155
    decays = (
        (DecaySpec("e", "loss", 1.0 / lifetime_us, "7P1/2 scattering"),)
        if include_intermediate_decay
        else ()
    )
    model = MultilevelModelConfig(
        levels=_cs_ladder_levels(),
        computational_levels=("0", "1"),
        transitions=_cs_ladder_transitions(),
        static_level_energies_rad_per_us={"e": -detuning, "r": 0.0},
        decays=decays,
    )
    channels = {
        "microwave": ChannelSpec(
            "microwave", "01", "local", TWOPI * 1.0, TWOPI * 10.0
        ),
        "rydberg_459": ChannelSpec(
            "rydberg_459", "1e", "local", 2.0 * leg_rabi, TWOPI * 100.0
        ),
        "rydberg_1040": ChannelSpec(
            "rydberg_1040", "er", "local", 2.0 * leg_rabi, TWOPI * 100.0
        ),
    }
    return MultilevelEnvironmentConfig(
        atom_positions_um=tuple((6.0 * atom, 0.0) for atom in range(n_atoms)),
        channels=channels,
        model=model,
        profile_name="graham-2019-Cs66S-intermediate-scattering-isolate",
        nominal_controls={
            "one_photon_detuning_rad_per_us": detuning,
            "effective_rabi_rad_per_us": effective_rabi,
            "omega_459_rad_per_us": leg_rabi,
            "omega_1040_rad_per_us": leg_rabi,
            "pi_duration_us": math.pi / effective_rabi,
            "intermediate_lifetime_us": lifetime_us,
        },
        provenance=(
            ParameterProvenance(
                "one_photon_detuning",
                680.0,
                "MHz",
                "reported",
                GRAHAM_2019_URL,
                "Supplementary Sec. SM-I.C",
            ),
            ParameterProvenance(
                "intermediate_lifetime",
                155.0,
                "ns",
                "reported",
                GRAHAM_2019_URL,
                "Supplementary Sec. SM-I.C",
            ),
            ParameterProvenance(
                "equal_single_photon_rabi",
                leg_rabi,
                "rad/us",
                "derived",
                GRAHAM_2019_URL,
                "Pse analytic-limit reconstruction",
                "sqrt(2*abs(Delta)*Omega_eff)",
            ),
            ParameterProvenance(
                "effective_two_photon_rabi",
                effective_rabi_mhz,
                "MHz",
                "chosen_validation",
                "S3A_EXPERIMENT_PLAN.md",
                "numerical validation setting",
                "The scattering formula is independent of this value in the "
                "adiabatic equal-leg limit.",
            ),
        ),
    )


def radnaev_2025_nominal_profile(
    *,
    n_atoms: int = 2,
    adiabatic_detuning_scale: float = 1.0,
    include_intermediate_decay: bool = True,
    include_rydberg_decay: bool = True,
) -> MultilevelEnvironmentConfig:
    """Primary Cs 69S nominal operating point with explicit optical legs.

    The decay branching is intentionally conservative: both 7P and 69S decay
    are routed to a generic loss/leakage sink until hyperfine-resolved branching
    is independently validated.
    """

    ladder = radnaev_single_intermediate_ladder_parameters(
        adiabatic_detuning_scale=adiabatic_detuning_scale
    )
    intermediate_energy = ladder.intermediate_energy_rad_per_us
    laser_detuning = -intermediate_energy
    effective_rabi = ladder.effective_rabi_rad_per_us
    blue_light_shift = ladder.lower_light_shift_rad_per_us
    omega_459 = ladder.omega_459_rad_per_us
    omega_1040 = ladder.omega_1040_rad_per_us
    differential_compensation = (
        ladder.two_photon_compensation_rad_per_us
    )
    intermediate_lifetime_us = 0.15436819436296377
    rydberg_lifetime_us_300k = 134.35079065904912
    blockade = TWOPI * 10.3
    model = MultilevelModelConfig(
        levels=_cs_ladder_levels(),
        computational_levels=("0", "1"),
        transitions=_cs_ladder_transitions(),
        static_level_energies_rad_per_us={
            "e": intermediate_energy,
            "r": differential_compensation,
        },
        decays=tuple(
            decay
            for enabled, decay in (
                (
                    include_intermediate_decay,
                    DecaySpec(
                        "e",
                        "loss",
                        1.0 / intermediate_lifetime_us,
                        "7P1/2 unresolved scattering",
                    ),
                ),
                (
                    include_rydberg_decay,
                    DecaySpec(
                        "r",
                        "loss",
                        1.0 / rydberg_lifetime_us_300k,
                        "69S room-temperature lifetime",
                    ),
                ),
            )
            if enabled
        ),
        pair_interactions=(
            PairInteractionSpec("r", "r", blockade, True, "measured blockade"),
        ),
    )
    channels = {
        "microwave": ChannelSpec(
            "microwave", "01", "global", TWOPI * 0.2, TWOPI * 1.0
        ),
        "rydberg_459": ChannelSpec(
            "rydberg_459", "1e", "local", 1.5 * omega_459, TWOPI * 100.0
        ),
        "rydberg_1040": ChannelSpec(
            "rydberg_1040", "er", "local", 1.5 * omega_1040, TWOPI * 100.0
        ),
    }
    default_variant = (
        math.isclose(
            adiabatic_detuning_scale, 1.0, rel_tol=0.0, abs_tol=0.0
        )
        and include_intermediate_decay
        and include_rydberg_decay
    )
    profile_name = (
        "radnaev-2025-Cs69S-nominal-S3A"
        if default_variant
        else (
            "radnaev-2025-Cs69S-single-intermediate"
            f"-s{adiabatic_detuning_scale:g}"
            f"-e{int(include_intermediate_decay)}"
            f"-r{int(include_rydberg_decay)}"
        )
    )
    return MultilevelEnvironmentConfig(
        atom_positions_um=tuple((6.0 * atom, 0.0) for atom in range(n_atoms)),
        channels=channels,
        model=model,
        profile_name=profile_name,
        nominal_controls={
            "laser_one_photon_detuning_rad_per_us": laser_detuning,
            "intermediate_energy_rad_per_us": intermediate_energy,
            "adiabatic_detuning_scale": adiabatic_detuning_scale,
            "effective_rabi_rad_per_us": effective_rabi,
            "omega_459_rad_per_us": omega_459,
            "omega_1040_rad_per_us": omega_1040,
            "blue_light_shift_rad_per_us": blue_light_shift,
            "upper_light_shift_rad_per_us": (
                ladder.upper_light_shift_rad_per_us
            ),
            "two_photon_compensation_rad_per_us": differential_compensation,
            "blockade_rad_per_us": blockade,
            "intermediate_lifetime_us": intermediate_lifetime_us,
            "rydberg_lifetime_us_300k": rydberg_lifetime_us_300k,
            "gate_duration_us": 0.416,
        },
        provenance=(
            ParameterProvenance(
                "laser_one_photon_detuning",
                -2100.0,
                "MHz",
                "reported",
                RADNAEV_2025_URL,
                "Fig. 3 / main text",
            ),
            ParameterProvenance(
                "effective_two_photon_rabi",
                3.0,
                "MHz",
                "reported",
                RADNAEV_2025_URL,
                "Fig. 3 / main text",
            ),
            ParameterProvenance(
                "blue_light_shift",
                2.0,
                "MHz",
                "reported",
                RADNAEV_2025_URL,
                "Fig. 3 / main text",
            ),
            ParameterProvenance(
                "blockade",
                10.3,
                "MHz",
                "reported",
                RADNAEV_2025_URL,
                "Fig. 3b",
            ),
            ParameterProvenance(
                "intermediate_lifetime",
                intermediate_lifetime_us,
                "us",
                "software",
                ARC_URL,
                "Caesium.getStateLifetime(7,1,0.5)",
                software_version="3.10.2",
            ),
            ParameterProvenance(
                "rydberg_lifetime_300K",
                rydberg_lifetime_us_300k,
                "us",
                "software",
                ARC_URL,
                "Caesium.getStateLifetime(69,0,0.5,300,100)",
                software_version="3.10.2",
            ),
            ParameterProvenance(
                "omega_459",
                omega_459,
                "rad/us",
                "derived",
                RADNAEV_2025_URL,
                "derived nominal profile",
                "sqrt(4*abs(Delta)*abs(blue_light_shift)); simple "
                "single-intermediate-state convention",
            ),
            ParameterProvenance(
                "omega_1040",
                omega_1040,
                "rad/us",
                "derived",
                RADNAEV_2025_URL,
                "derived nominal profile",
                "2*abs(Delta)*Omega_eff/Omega_459",
            ),
            ParameterProvenance(
                "two_photon_compensation",
                differential_compensation,
                "rad/us",
                "derived",
                RADNAEV_2025_URL,
                "derived nominal profile",
                "(Omega_1040^2-Omega_459^2)/(4*(-Delta)); excludes "
                "hyperfine and polarization corrections",
            ),
        ),
    )
