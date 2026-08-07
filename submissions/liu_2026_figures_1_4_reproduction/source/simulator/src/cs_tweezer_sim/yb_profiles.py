"""Literature-anchored Yb profiles assembled from generic platform objects.

This module contains data adapters only.  The multilevel backend, Doppler
model, waveform compiler and observation boundary contain no Yb-specific
branches.
"""

from __future__ import annotations

import math

from .config import ChannelSpec, TransitionCouplingSpec
from .multilevel_config import (
    DecaySpec,
    LevelSpec,
    MultilevelEnvironmentConfig,
    MultilevelModelConfig,
    PairInteractionSpec,
    ParameterProvenance,
    TransitionSpec,
)
from .stochastic import (
    ATOMIC_MASS_KG,
    DopplerNoiseModel,
    single_photon_effective_wavevector_rad_per_m,
)


TWOPI = 2.0 * math.pi

LIU_2026_ARXIV_URL = "https://arxiv.org/abs/2606.05060"
LIU_2026_ARXIV_PDF_URL = "https://arxiv.org/pdf/2606.05060"
PEPER_2025_DOI_URL = "https://doi.org/10.1103/PhysRevX.15.011009"
PEPER_2025_ARXIV_URL = "https://arxiv.org/abs/2406.01482"
NIST_YB_ATOMIC_DATA_URL = (
    "https://physics.nist.gov/PhysRefData/Handbook/Tables/"
    "ytterbiumtable1_a.htm"
)
CIAAW_YB_ISOTOPE_URL = "https://ciaaw.org/ytterbium.htm"

YB171_ATOMIC_MASS_U = 170.93633152
YB171_MASS_KG = YB171_ATOMIC_MASS_U * ATOMIC_MASS_KG
LIU_2026_RYDBERG_WAVELENGTH_NM = 302.0
LIU_2026_RYDBERG_RABI_RAD_PER_US = TWOPI * 6.0
LIU_2026_RYDBERG_SPLITTING_RAD_PER_US = TWOPI * 16.1
LIU_2026_RYDBERG_LIFETIME_US = 42.0
LIU_2026_TEMPERATURE_UK = 2.7
LIU_2026_DIMER_SPACING_UM = 2.0
LIU_2026_BEAM_WAIST_UM = 12.0
LIU_2026_OUT_OF_COMPUTATIONAL_DECAY_FRACTION = 0.90
LIU_2026_SHARED_RYDBERG_RELATIVE_RABI = 1.0

# These are simulator command-range guards, not measured Liu parameters.
YB171_PROFILE_RF_MAX_RABI_RAD_PER_US = TWOPI * 0.01
YB171_PROFILE_RF_MAX_ABS_DETUNING_RAD_PER_US = TWOPI * 1.0
YB171_PROFILE_RYDBERG_MAX_RABI_RAD_PER_US = TWOPI * 20.0
YB171_PROFILE_RYDBERG_MAX_ABS_DETUNING_RAD_PER_US = TWOPI * 100.0


def _effective_rydberg_decays(
    *,
    lifetime_us: float,
    out_of_computational_fraction: float,
) -> tuple[DecaySpec, ...]:
    """Return an explicitly effective decay partition for ``r`` and ``r'``.

    Liu et al. report the measured lifetime and that about 90 percent of
    lifetime-induced errors leave the qubit subspace.  They do not publish a
    complete microscopic branching table.  The remaining effective rate is
    divided equally between the two computational states only to close a
    trace-preserving minimal model; provenance marks this as an assumption.
    """

    if lifetime_us <= 0 or not 0.0 <= out_of_computational_fraction <= 1.0:
        raise ValueError("effective Rydberg decay parameters are invalid")
    rate = 1.0 / lifetime_us
    in_subspace_each = 0.5 * (1.0 - out_of_computational_fraction)
    decays: list[DecaySpec] = []
    for source in ("r", "r_prime"):
        decays.extend(
            (
                DecaySpec(
                    source,
                    "erasure",
                    out_of_computational_fraction * rate,
                    f"{source}->outside-computational-effective",
                ),
                DecaySpec(
                    source,
                    "0",
                    in_subspace_each * rate,
                    f"{source}->0-effective",
                ),
                DecaySpec(
                    source,
                    "1",
                    in_subspace_each * rate,
                    f"{source}->1-effective",
                ),
            )
        )
    return tuple(decays)


def liu_2026_yb171_four_level_profile(
    *,
    n_atoms: int = 2,
    rydberg_splitting_rad_per_us: float = (
        LIU_2026_RYDBERG_SPLITTING_RAD_PER_US
    ),
    include_effective_rydberg_decay: bool = True,
    effective_out_of_computational_decay_fraction: float = (
        LIU_2026_OUT_OF_COMPUTATIONAL_DECAY_FRACTION
    ),
    nominal_rr_interaction_rad_per_us: float | None = None,
) -> MultilevelEnvironmentConfig:
    """Return the minimal Liu-2026 metastable Yb-171 four-level profile.

    The physical 302 nm actuator drives both ``1<->r`` and
    ``0<->r_prime`` with the same complex waveform and nominal unit relative
    Rabi coefficient.  The sign convention places ``r_prime`` below ``r`` by
    ``rydberg_splitting_rad_per_us`` in the rotating frame.

    ``nominal_rr_interaction_rad_per_us`` is optional because Liu et al. use an
    MQDT pair-state calculation rather than publishing a single transferable
    blockade number.  Supplying a value enables a reduced diagonal
    ``|rr>`` interaction, but the default does not invent one.
    """

    if n_atoms <= 0:
        raise ValueError("n_atoms must be positive")
    if (
        not math.isfinite(rydberg_splitting_rad_per_us)
        or rydberg_splitting_rad_per_us < 0
    ):
        raise ValueError("Rydberg splitting must be finite and non-negative")
    if (
        not math.isfinite(effective_out_of_computational_decay_fraction)
        or not 0.0
        <= effective_out_of_computational_decay_fraction
        <= 1.0
    ):
        raise ValueError(
            "effective out-of-computational decay fraction must be in [0, 1]"
        )
    if nominal_rr_interaction_rad_per_us is not None and (
        not math.isfinite(nominal_rr_interaction_rad_per_us)
        or nominal_rr_interaction_rad_per_us < 0
    ):
        raise ValueError("nominal rr interaction must be finite and non-negative")

    levels = (
        LevelSpec("0", "0"),
        LevelSpec("1", "1"),
        LevelSpec("r", "R"),
        LevelSpec("r_prime", "R'"),
        LevelSpec("erasure", "L"),
    )
    transitions = {
        "01": TransitionSpec("01", "0", "1", {"1": -1.0}),
        "1_r": TransitionSpec("1_r", "1", "r", {"r": -1.0}),
        "0_r_prime": TransitionSpec(
            "0_r_prime",
            "0",
            "r_prime",
            {"r_prime": -1.0},
        ),
    }
    channels = {
        "rf_qubit": ChannelSpec(
            "rf_qubit",
            "01",
            "global",
            YB171_PROFILE_RF_MAX_RABI_RAD_PER_US,
            YB171_PROFILE_RF_MAX_ABS_DETUNING_RAD_PER_US,
        ),
        "rydberg_302": ChannelSpec(
            "rydberg_302",
            "1_r",
            "global",
            YB171_PROFILE_RYDBERG_MAX_RABI_RAD_PER_US,
            YB171_PROFILE_RYDBERG_MAX_ABS_DETUNING_RAD_PER_US,
            additional_transition_couplings=(
                TransitionCouplingSpec(
                    "0_r_prime",
                    complex(LIU_2026_SHARED_RYDBERG_RELATIVE_RABI),
                ),
            ),
        ),
    }
    pair_interactions = (
        (
            PairInteractionSpec(
                "r",
                "r",
                nominal_rr_interaction_rad_per_us,
                label="liu-yb171-reduced-rr",
            ),
        )
        if nominal_rr_interaction_rad_per_us is not None
        else ()
    )
    decays = (
        _effective_rydberg_decays(
            lifetime_us=LIU_2026_RYDBERG_LIFETIME_US,
            out_of_computational_fraction=(
                effective_out_of_computational_decay_fraction
            ),
        )
        if include_effective_rydberg_decay
        else ()
    )
    model = MultilevelModelConfig(
        levels=levels,
        computational_levels=("0", "1"),
        transitions=transitions,
        static_level_energies_rad_per_us={
            "r": 0.0,
            "r_prime": -rydberg_splitting_rad_per_us,
        },
        decays=decays,
        pair_interactions=pair_interactions,
    )
    controls = {
        "atomic_mass_u": YB171_ATOMIC_MASS_U,
        "atomic_mass_kg": YB171_MASS_KG,
        "nuclear_spin": 0.5,
        "rydberg_wavelength_nm": LIU_2026_RYDBERG_WAVELENGTH_NM,
        "rydberg_rabi_rad_per_us": LIU_2026_RYDBERG_RABI_RAD_PER_US,
        "rydberg_splitting_rad_per_us": rydberg_splitting_rad_per_us,
        "rydberg_lifetime_us": LIU_2026_RYDBERG_LIFETIME_US,
        "temperature_uk": LIU_2026_TEMPERATURE_UK,
        "dimer_spacing_um": LIU_2026_DIMER_SPACING_UM,
        "beam_waist_um": LIU_2026_BEAM_WAIST_UM,
        "shared_rydberg_relative_rabi": (
            LIU_2026_SHARED_RYDBERG_RELATIVE_RABI
        ),
        "effective_out_of_computational_decay_fraction": (
            effective_out_of_computational_decay_fraction
        ),
        "rf_max_rabi_rad_per_us": YB171_PROFILE_RF_MAX_RABI_RAD_PER_US,
        "rf_max_abs_detuning_rad_per_us": (
            YB171_PROFILE_RF_MAX_ABS_DETUNING_RAD_PER_US
        ),
        "rydberg_max_rabi_rad_per_us": (
            YB171_PROFILE_RYDBERG_MAX_RABI_RAD_PER_US
        ),
        "rydberg_max_abs_detuning_rad_per_us": (
            YB171_PROFILE_RYDBERG_MAX_ABS_DETUNING_RAD_PER_US
        ),
    }
    if nominal_rr_interaction_rad_per_us is not None:
        controls["nominal_rr_interaction_rad_per_us"] = (
            nominal_rr_interaction_rad_per_us
        )

    provenance = (
        ParameterProvenance(
            "atomic_mass",
            YB171_ATOMIC_MASS_U,
            "u",
            "reference",
            CIAAW_YB_ISOTOPE_URL,
            "Ytterbium isotope table, 171Yb row",
            "Converted to kg with the project atomic-mass constant",
        ),
        ParameterProvenance(
            "nuclear_spin",
            0.5,
            "hbar",
            "reference",
            NIST_YB_ATOMIC_DATA_URL,
            "171Yb isotope row",
        ),
        ParameterProvenance(
            "rydberg_wavelength",
            LIU_2026_RYDBERG_WAVELENGTH_NM,
            "nm",
            "reported",
            LIU_2026_ARXIV_URL,
            "main text Sec. II and Appendix A",
        ),
        ParameterProvenance(
            "rydberg_rabi",
            LIU_2026_RYDBERG_RABI_RAD_PER_US,
            "rad/us",
            "reported",
            LIU_2026_ARXIV_URL,
            "main text Sec. II",
            "2*pi*6.0 MHz",
        ),
        ParameterProvenance(
            "rydberg_splitting",
            rydberg_splitting_rad_per_us,
            "rad/us",
            (
                "reported"
                if math.isclose(
                    rydberg_splitting_rad_per_us,
                    LIU_2026_RYDBERG_SPLITTING_RAD_PER_US,
                    rel_tol=0.0,
                    abs_tol=1e-15,
                )
                else "configured"
            ),
            LIU_2026_ARXIV_URL,
            "main text Sec. II",
            (
                "2*pi*16.1 MHz"
                if math.isclose(
                    rydberg_splitting_rad_per_us,
                    LIU_2026_RYDBERG_SPLITTING_RAD_PER_US,
                    rel_tol=0.0,
                    abs_tol=1e-15,
                )
                else "caller override for a parameter scan"
            ),
        ),
        ParameterProvenance(
            "shared_rydberg_relative_rabi",
            LIU_2026_SHARED_RYDBERG_RELATIVE_RABI,
            "dimensionless complex-amplitude ratio",
            "reported",
            LIU_2026_ARXIV_URL,
            "main text Sec. II, equal sigma-minus/sigma-plus components",
            "linear polarization perpendicular to B gives equal drive strength",
        ),
        ParameterProvenance(
            "rydberg_lifetime",
            LIU_2026_RYDBERG_LIFETIME_US,
            "us",
            "reported",
            LIU_2026_ARXIV_URL,
            "Appendix E",
        ),
        ParameterProvenance(
            "temperature",
            LIU_2026_TEMPERATURE_UK,
            "uK",
            "reported",
            LIU_2026_ARXIV_URL,
            "Appendix E",
        ),
        ParameterProvenance(
            "dimer_spacing",
            LIU_2026_DIMER_SPACING_UM,
            "um",
            "reported",
            LIU_2026_ARXIV_URL,
            "Appendix A/E",
        ),
        ParameterProvenance(
            "beam_waist",
            LIU_2026_BEAM_WAIST_UM,
            "um",
            "reported",
            LIU_2026_ARXIV_URL,
            "main text Sec. II and Appendix A",
            "1/e^2 intensity radius",
        ),
        ParameterProvenance(
            "out_of_computational_lifetime_error_fraction",
            effective_out_of_computational_decay_fraction,
            "fraction",
            (
                "reported"
                if math.isclose(
                    effective_out_of_computational_decay_fraction,
                    LIU_2026_OUT_OF_COMPUTATIONAL_DECAY_FRACTION,
                    rel_tol=0.0,
                    abs_tol=1e-15,
                )
                else "configured"
            ),
            LIU_2026_ARXIV_URL,
            "Appendix E",
            (
                "paper states about 90 percent of lifetime-induced errors "
                "leave the qubit subspace"
                if math.isclose(
                    effective_out_of_computational_decay_fraction,
                    LIU_2026_OUT_OF_COMPUTATIONAL_DECAY_FRACTION,
                    rel_tol=0.0,
                    abs_tol=1e-15,
                )
                else "caller override of the reported effective fraction"
            ),
        ),
        ParameterProvenance(
            "effective_in_subspace_decay_partition",
            0.5,
            "fraction of residual rate per qubit state",
            "assumption",
            LIU_2026_ARXIV_URL,
            "microscopic branching ratios not published",
            "remaining effective decay rate divided equally between 0 and 1",
        ),
        ParameterProvenance(
            "Yb_Rydberg_MQDT_reference",
            1.0,
            "reference",
            "reference",
            PEPER_2025_DOI_URL,
            "PRX 15, 011009 and supplemental material",
            "profile does not claim to implement the MQDT pair model",
        ),
        ParameterProvenance(
            "profile_channel_command_limits",
            1.0,
            "configuration record",
            "configured",
            "src/cs_tweezer_sim/yb_profiles.py",
            "YB171_PROFILE_*_MAX_* constants",
            "software safety bounds, not measured atomic parameters; exact "
            "values are copied into nominal_controls",
        ),
    )
    return MultilevelEnvironmentConfig(
        atom_positions_um=tuple(
            (LIU_2026_DIMER_SPACING_UM * atom, 0.0)
            for atom in range(n_atoms)
        ),
        channels=channels,
        model=model,
        profile_name="liu-2026-yb171-four-level-effective",
        nominal_controls=controls,
        provenance=provenance,
    )


def liu_2026_yb171_doppler_model() -> DopplerNoiseModel:
    """Return the single-photon 302 nm Doppler model for the Liu profile."""

    return DopplerNoiseModel(
        temperature_uk=LIU_2026_TEMPERATURE_UK,
        rydberg_level="r",
        block_name="liu_yb171_302nm_doppler_velocity",
        mass_kg=YB171_MASS_KG,
        effective_wavevector_rad_per_m=(
            single_photon_effective_wavevector_rad_per_m(
                LIU_2026_RYDBERG_WAVELENGTH_NM
            )
        ),
        additional_shifted_levels=("r_prime",),
    )
