"""Named, parameter-exposed Cs stochastic environment profiles."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .stochastic import (
    CompositeShotNoiseModel,
    DopplerNoiseModel,
    GaussianBeamCouplingSpec,
    LaserPhaseFrequencyNoiseModel,
    MagneticFieldNoiseModel,
    PolynomialLevelShiftSpec,
    PulseEnergyNoiseModel,
    ThermalPositionNoiseModel,
    ZeemanLevelShiftSpec,
    arc_dc_polarizability_to_quadratic_shift_rad_per_us_per_vpcm2,
    harmonic_position_sigma_um,
)

CS_CLOCK_QUADRATIC_ZEEMAN_HZ_PER_G2 = 427.45
CS_69S_DC_POLARIZABILITY_MHZ_CM2_PER_V2_ARC_3_10_2 = 534.7973202077148


def cs_clock_quadratic_zeeman_rad_per_us_per_g2() -> float:
    """Return the Cs |F=3,mF=0> to |F=4,mF=0> quadratic coefficient."""

    return (
        2.0
        * math.pi
        * CS_CLOCK_QUADRATIC_ZEEMAN_HZ_PER_G2
        * 1e-6
    )


def cs_69s_dc_stark_level_shift_spec() -> PolynomialLevelShiftSpec:
    """Return the ARC-3.10.2 small-field scalar Cs 69S Stark coefficient."""

    return PolynomialLevelShiftSpec(
        "r",
        quadratic_rad_per_us_per_field2=(
            arc_dc_polarizability_to_quadratic_shift_rad_per_us_per_vpcm2(
                CS_69S_DC_POLARIZABILITY_MHZ_CM2_PER_V2_ARC_3_10_2
            )
        ),
    )


@dataclass(frozen=True)
class CsColdGateNoiseProfile:
    """Components of one explicit cold-Cs gate environment."""

    doppler: DopplerNoiseModel
    thermal_position: ThermalPositionNoiseModel
    pulse_energy: PulseEnergyNoiseModel
    laser_phase_frequency: LaserPhaseFrequencyNoiseModel
    magnetic_field: MagneticFieldNoiseModel

    @property
    def joint(self) -> CompositeShotNoiseModel:
        return CompositeShotNoiseModel(
            (
                self.doppler,
                self.thermal_position,
                self.pulse_energy,
                self.laser_phase_frequency,
                self.magnetic_field,
            )
        )


def radnaev_2025_cold_gate_noise_profile(
    *,
    temperature_uk: float = 2.6,
    wavelengths_nm: tuple[float, float] = (459.4459, 1040.03),
    radial_trap_frequency_khz: float = 60.9,
    axial_trap_frequency_khz: float = 11.5,
    atom_spacing_um: float = 6.0,
    waist_459_um: float = 2.8,
    waist_1040_um: float = 3.0,
    pulse_energy_fractional_sigma: float = 0.016,
    pulse_energy_channel: str = "rydberg_1040",
    laser_lorentzian_linewidth_fwhm_hz: tuple[float, float, float] = (
        0.0,
        0.0,
        0.0,
    ),
    laser_quasistatic_frequency_sigma_hz: tuple[float, float, float] = (
        0.0,
        0.0,
        0.0,
    ),
    laser_ou_frequency_sigma_hz: tuple[float, float, float] = (
        0.0,
        0.0,
        0.0,
    ),
    laser_ou_correlation_time_us: float = 1.0,
    phase_frequency_sample_interval_us: float = 0.004,
    magnetic_bias_field_g: float = 0.0,
    magnetic_iteration_common_sigma_g: float = 0.0,
    magnetic_shot_common_sigma_g: float = 0.0,
    magnetic_shot_local_sigma_g: float = 0.0,
    magnetic_within_shot_common_sigma_g: float = 0.0,
    magnetic_within_shot_local_sigma_g: float = 0.0,
    magnetic_correlation_time_us: float = 1.0,
    magnetic_sample_interval_us: float = 0.004,
    zeeman_level_shifts: tuple[ZeemanLevelShiftSpec, ...] | None = None,
) -> CsColdGateNoiseProfile:
    """Construct the parameter-exposed cold-Cs noise profile.

    Temperature, wavelengths, trap frequencies, spacing and waists are exposed
    rather than hidden in the backend.  The default pulse-energy sigma is a
    chosen validation value inherited from S3-C, not a claimed measurement of
    the Radnaev apparatus.  Laser linewidth/OU and magnetic-noise defaults are
    deliberately zero because the source does not publish enough information
    to reconstruct apparatus PSDs.  The default Zeeman map includes only the
    measured Cs clock-state quadratic coefficient; users must provide the
    selected 7P and 69S sublevel coefficients for a polarization-resolved
    model.
    """

    radial_sigma = harmonic_position_sigma_um(
        temperature_uk, radial_trap_frequency_khz
    )
    axial_sigma = harmonic_position_sigma_um(
        temperature_uk, axial_trap_frequency_khz
    )
    nominal = (
        (0.0, 0.0, 0.0),
        (atom_spacing_um, 0.0, 0.0),
    )
    thermal_position = ThermalPositionNoiseModel(
        nominal_positions_um=nominal,
        sigma_xyz_um=(
            (radial_sigma, radial_sigma, axial_sigma),
            (radial_sigma, radial_sigma, axial_sigma),
        ),
        beams=tuple(
            GaussianBeamCouplingSpec(channel, atom, waist, nominal[atom])
            for atom in range(2)
            for channel, waist in (
                ("rydberg_459", waist_459_um),
                ("rydberg_1040", waist_1040_um),
            )
        ),
    )
    return CsColdGateNoiseProfile(
        doppler=DopplerNoiseModel(
            temperature_uk=temperature_uk,
            wavelengths_nm=wavelengths_nm,
        ),
        thermal_position=thermal_position,
        pulse_energy=PulseEnergyNoiseModel(
            channels=(pulse_energy_channel,),
            energy_covariance=((pulse_energy_fractional_sigma**2,),),
        ),
        laser_phase_frequency=LaserPhaseFrequencyNoiseModel(
            channels=("microwave", "rydberg_459", "rydberg_1040"),
            lorentzian_linewidth_fwhm_hz=(
                laser_lorentzian_linewidth_fwhm_hz
            ),
            quasistatic_frequency_covariance_hz2=tuple(
                tuple(
                    (
                        laser_quasistatic_frequency_sigma_hz[row] ** 2
                        if row == column
                        else 0.0
                    )
                    for column in range(3)
                )
                for row in range(3)
            ),
            ou_frequency_sigma_hz=laser_ou_frequency_sigma_hz,
            sample_interval_us=phase_frequency_sample_interval_us,
            ou_correlation_time_us=laser_ou_correlation_time_us,
        ),
        magnetic_field=MagneticFieldNoiseModel(
            bias_field_g=magnetic_bias_field_g,
            level_shifts=(
                zeeman_level_shifts
                if zeeman_level_shifts is not None
                else (
                    ZeemanLevelShiftSpec(
                        "1",
                        quadratic_rad_per_us_per_g2=(
                            cs_clock_quadratic_zeeman_rad_per_us_per_g2()
                        ),
                    ),
                )
            ),
            iteration_common_sigma_g=magnetic_iteration_common_sigma_g,
            shot_common_sigma_g=magnetic_shot_common_sigma_g,
            shot_local_sigma_g=magnetic_shot_local_sigma_g,
            within_shot_common_sigma_g=(
                magnetic_within_shot_common_sigma_g
            ),
            within_shot_local_sigma_g=magnetic_within_shot_local_sigma_g,
            within_shot_correlation_time_us=magnetic_correlation_time_us,
            sample_interval_us=magnetic_sample_interval_us,
        ),
    )
