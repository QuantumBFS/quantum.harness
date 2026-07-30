"""Literature-anchored Rb-87 reference profiles for backend validation.

These profiles are not the default Cs experiment model.  They exercise the
same generic multilevel interfaces against the eight-level structure reported
by Evered et al., Nature 622, 268 (2023).
"""

from __future__ import annotations

import math
from typing import Mapping

from .config import (
    ChannelLevelShiftSpec,
    ChannelSpec,
    TransitionCouplingSpec,
)
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
EVERED_2023_DOI = "https://doi.org/10.1038/s41586-023-06481-y"
STECK_RB87_URL = "https://steck.us/alkalidata/rubidium87numbers.pdf"
NIST_RB_REFERENCE_DOI = "https://doi.org/10.1063/1.2035727"


def _relative(
    values: Mapping[str, complex] | None,
    defaults: Mapping[str, complex],
) -> dict[str, complex]:
    result = dict(defaults if values is None else values)
    if set(result) != set(defaults):
        raise ValueError(
            f"relative-coupling keys must be {sorted(defaults)}"
        )
    converted = {key: complex(value) for key, value in result.items()}
    if any(value == 0 for value in converted.values()):
        raise ValueError("relative Rabi couplings must be non-zero")
    return converted


def evered_2023_rb87_eight_level_profile(
    *,
    n_atoms: int = 2,
    intermediate_relative_rabi: Mapping[str, complex] | None = None,
    target_rydberg_relative_rabi: Mapping[str, complex] | None = None,
    unwanted_rydberg_relative_factor: complex = 1.0 / 3.0,
    include_intermediate_decay: bool = True,
    include_rydberg_decay: bool = True,
    include_1013_differential_light_shift: bool = True,
) -> MultilevelEnvironmentConfig:
    """Return the reported Evered Rb-87 eight-level model structure.

    The paper reports the level count, three intermediate-state spacings,
    principal Rabi frequencies, detuning, lifetimes, branching ratios, the
    24 MHz unwanted-Rydberg splitting and its factor-three suppressed
    coupling.  It does not tabulate every intermediate-state complex
    Clebsch--Gordan coefficient.  The two mapping arguments expose those
    coefficients rather than hiding them.  Unit defaults are a structural
    reference only and must be replaced by polarization-resolved values before
    claiming reproduction of the published error budget.

    Frequencies are angular frequencies in rad/us.  The 20 MHz 1013-nm
    differential light shift is represented, up to a diagonal gauge choice, as
    a quadratic shift of both Rydberg levels at the reported nominal Rabi
    frequency.
    """

    if n_atoms <= 0:
        raise ValueError("n_atoms must be positive")
    unwanted_factor = complex(unwanted_rydberg_relative_factor)
    if unwanted_factor == 0:
        raise ValueError("unwanted Rydberg coupling factor must be non-zero")

    intermediate = _relative(
        intermediate_relative_rabi,
        {"e1": 1.0, "e2": 1.0, "e3": 1.0},
    )
    target = _relative(
        target_rydberg_relative_rabi,
        {"e1": 1.0, "e2": 1.0, "e3": 1.0},
    )

    levels = (
        LevelSpec("0", "0"),
        LevelSpec("1", "1"),
        LevelSpec("loss", "L"),
        LevelSpec("e1", "E1"),
        LevelSpec("e2", "E2"),
        LevelSpec("e3", "E3"),
        LevelSpec("r_plus", "R+"),
        LevelSpec("r_minus", "R-"),
    )
    transitions: dict[str, TransitionSpec] = {
        "01": TransitionSpec("01", "0", "1", {"1": -1.0}),
    }
    for excited in ("e1", "e2", "e3"):
        transitions[f"1_{excited}"] = TransitionSpec(
            f"1_{excited}",
            "1",
            excited,
            {excited: -1.0},
        )
        for rydberg in ("r_plus", "r_minus"):
            transitions[f"{excited}_{rydberg}"] = TransitionSpec(
                f"{excited}_{rydberg}",
                excited,
                rydberg,
                {rydberg: -1.0},
            )

    omega_420 = TWOPI * 237.0
    omega_1013 = TWOPI * 303.0
    differential_light_shift = TWOPI * 20.0
    light_shift_coefficient = (
        differential_light_shift / omega_1013**2
    )
    channels = {
        "microwave": ChannelSpec(
            "microwave",
            "01",
            "global",
            TWOPI * 20.0,
            TWOPI * 100.0,
        ),
        "rydberg_420": ChannelSpec(
            "rydberg_420",
            "1_e3",
            "global",
            omega_420,
            TWOPI * 1000.0,
            additional_transition_couplings=(
                TransitionCouplingSpec(
                    "1_e1", intermediate["e1"] / intermediate["e3"]
                ),
                TransitionCouplingSpec(
                    "1_e2", intermediate["e2"] / intermediate["e3"]
                ),
            ),
        ),
        "rydberg_1013": ChannelSpec(
            "rydberg_1013",
            "e3_r_plus",
            "global",
            omega_1013,
            TWOPI * 1000.0,
            additional_transition_couplings=(
                TransitionCouplingSpec(
                    "e1_r_plus", target["e1"] / target["e3"]
                ),
                TransitionCouplingSpec(
                    "e2_r_plus", target["e2"] / target["e3"]
                ),
                TransitionCouplingSpec(
                    "e1_r_minus",
                    unwanted_factor * target["e1"] / target["e3"],
                ),
                TransitionCouplingSpec(
                    "e2_r_minus",
                    unwanted_factor * target["e2"] / target["e3"],
                ),
                TransitionCouplingSpec(
                    "e3_r_minus", unwanted_factor
                ),
            ),
            level_shifts=(
                (
                    ChannelLevelShiftSpec(
                        "r_plus", light_shift_coefficient
                    ),
                    ChannelLevelShiftSpec(
                        "r_minus", light_shift_coefficient
                    ),
                )
                if include_1013_differential_light_shift
                else ()
            ),
        ),
    }

    intermediate_lifetime_us = 0.110
    rydberg_lifetime_us = 88.0
    decays: list[DecaySpec] = []
    if include_intermediate_decay:
        for excited in ("e1", "e2", "e3"):
            for target_level, branching in (
                ("loss", 0.6142),
                ("1", 0.2504),
                ("0", 0.1354),
            ):
                decays.append(
                    DecaySpec(
                        excited,
                        target_level,
                        branching / intermediate_lifetime_us,
                        f"{excited}->{target_level}",
                    )
                )
    if include_rydberg_decay:
        for rydberg in ("r_plus", "r_minus"):
            for target_level, branching in (
                ("loss", 0.894),
                ("1", 0.053),
                ("0", 0.053),
            ):
                decays.append(
                    DecaySpec(
                        rydberg,
                        target_level,
                        branching / rydberg_lifetime_us,
                        f"{rydberg}->{target_level}",
                    )
                )

    one_photon_detuning = TWOPI * 7800.0
    model = MultilevelModelConfig(
        levels=levels,
        computational_levels=("0", "1"),
        transitions=transitions,
        static_level_energies_rad_per_us={
            "e1": one_photon_detuning,
            "e2": one_photon_detuning + TWOPI * 51.0,
            "e3": one_photon_detuning + TWOPI * (51.0 + 87.0),
            "r_plus": 0.0,
            "r_minus": -TWOPI * 24.0,
        },
        decays=tuple(decays),
        pair_interactions=(
            PairInteractionSpec(
                "r_plus",
                "r_plus",
                TWOPI * 450.0,
                label="evered_target_blockade",
            ),
        ),
    )
    controls = {
        "omega_420_rad_per_us": omega_420,
        "omega_1013_rad_per_us": omega_1013,
        "one_photon_detuning_rad_per_us": one_photon_detuning,
        "unwanted_rydberg_splitting_rad_per_us": TWOPI * 24.0,
        "target_blockade_rad_per_us": TWOPI * 450.0,
        "intermediate_lifetime_us": intermediate_lifetime_us,
        "rydberg_lifetime_us": rydberg_lifetime_us,
        "differential_1013_light_shift_rad_per_us": (
            differential_light_shift
        ),
    }
    provenance = tuple(
        ParameterProvenance(
            parameter,
            value,
            unit,
            kind,
            source,
            locator,
            derivation,
        )
        for parameter, value, unit, kind, source, locator, derivation in (
            (
                "omega_420",
                omega_420,
                "rad/us",
                "reported",
                EVERED_2023_DOI,
                "Extended Data Fig. 3a",
                "2*pi*237 MHz",
            ),
            (
                "omega_1013",
                omega_1013,
                "rad/us",
                "reported",
                EVERED_2023_DOI,
                "Extended Data Fig. 3a",
                "2*pi*303 MHz",
            ),
            (
                "one_photon_detuning",
                one_photon_detuning,
                "rad/us",
                "reported",
                EVERED_2023_DOI,
                "Extended Data Fig. 3a / Table 1",
                "2*pi*7.8 GHz",
            ),
            (
                "unwanted_rydberg_splitting",
                TWOPI * 24.0,
                "rad/us",
                "reported",
                EVERED_2023_DOI,
                "Methods / Extended Data Fig. 3a",
                "2*pi*24 MHz",
            ),
            (
                "target_blockade",
                TWOPI * 450.0,
                "rad/us",
                "reported",
                EVERED_2023_DOI,
                "Methods: Rydberg-state selection",
                "2*pi*450 MHz at 2 um",
            ),
            (
                "intermediate_hyperfine_sources",
                1.0,
                "reference",
                "reference",
                STECK_RB87_URL,
                "6P3/2 hyperfine structure",
                "profile offsets follow the 51 and 87 MHz values reported "
                "in Evered Fig. 3a",
            ),
            (
                "Rb_spectral_reference",
                1.0,
                "reference",
                "reference",
                NIST_RB_REFERENCE_DOI,
                "NIST Rb spectral compilation",
                "",
            ),
            (
                "unspecified_intermediate_CG_defaults",
                1.0,
                "relative",
                "assumption",
                EVERED_2023_DOI,
                "not tabulated in paper",
                "unit structural defaults; override mapping arguments for "
                "polarization-resolved fidelity work",
            ),
        )
    )
    return MultilevelEnvironmentConfig(
        atom_positions_um=tuple(
            (2.0 * atom, 0.0) for atom in range(n_atoms)
        ),
        channels=channels,
        model=model,
        profile_name="evered-2023-rb87-eight-level-reference",
        nominal_controls=controls,
        provenance=provenance,
    )
