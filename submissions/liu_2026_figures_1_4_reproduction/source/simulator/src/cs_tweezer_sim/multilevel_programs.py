"""User-level programs for multilevel optical ladders."""

from __future__ import annotations

import math

from .contracts import (
    ConstantPulse,
    ExperimentProgram,
    Measure,
    ParallelPlay,
    Play,
    Prepare,
)


def two_photon_constant_program(
    *,
    n_atoms: int,
    atom: int,
    duration_us: float,
    omega_lower_rad_per_us: float,
    omega_upper_rad_per_us: float,
    lower_channel: str = "rydberg_459",
    upper_channel: str = "rydberg_1040",
    lower_phase_rad: float = 0.0,
    upper_phase_rad: float = 0.0,
    lower_detuning_rad_per_us: float = 0.0,
    upper_detuning_rad_per_us: float = 0.0,
    initial_bitstring: str | None = None,
    measure: bool = True,
    name: str = "two-photon-constant",
) -> ExperimentProgram:
    """Apply two simultaneous constant optical fields to one atom."""

    if atom < 0 or atom >= n_atoms:
        raise ValueError("atom is outside the configured register")
    program = ExperimentProgram(name=name)
    if initial_bitstring is not None:
        if len(initial_bitstring) != n_atoms:
            raise ValueError("initial bitstring length must equal n_atoms")
        program = program.then(Prepare(initial_bitstring))
    program = program.then(
        ParallelPlay(
            (
                Play(
                    lower_channel,
                    (atom,),
                    ConstantPulse(
                        duration_us,
                        omega_lower_rad_per_us,
                        lower_phase_rad,
                        lower_detuning_rad_per_us,
                    ),
                ),
                Play(
                    upper_channel,
                    (atom,),
                    ConstantPulse(
                        duration_us,
                        omega_upper_rad_per_us,
                        upper_phase_rad,
                        upper_detuning_rad_per_us,
                    ),
                ),
            )
        )
    )
    if measure:
        program = program.then(Measure())
    return program


def two_photon_sin2_pi_program(
    *,
    n_atoms: int,
    atom: int,
    peak_omega_lower_rad_per_us: float,
    peak_omega_upper_rad_per_us: float,
    one_photon_detuning_rad_per_us: float,
    segments: int = 64,
    lower_channel: str = "rydberg_459",
    upper_channel: str = "rydberg_1040",
    initial_bitstring: str | None = None,
    measure: bool = True,
    name: str = "two-photon-sin2-pi",
) -> ExperimentProgram:
    """Construct a smooth two-photon pi pulse from public constant segments.

    Both single-photon Rabi amplitudes use a ``sin^2`` envelope, so the
    adiabatically eliminated two-photon Rabi rate follows ``sin^4``.  The total
    duration is selected from the analytic area
    ``integral_0^T sin^4(pi t/T) dt = 3T/8``.

    This deliberately lives above the platform: sampled/AWG waveforms are
    represented by ordinary concurrent laboratory segments.
    """

    if segments < 4:
        raise ValueError("at least four segments are required")
    if one_photon_detuning_rad_per_us == 0:
        raise ValueError("one-photon detuning must be non-zero")
    effective_peak = (
        peak_omega_lower_rad_per_us
        * peak_omega_upper_rad_per_us
        / (2.0 * abs(one_photon_detuning_rad_per_us))
    )
    if effective_peak <= 0:
        raise ValueError("peak optical Rabi frequencies must be positive")
    total_duration_us = 8.0 * math.pi / (3.0 * effective_peak)
    segment_duration_us = total_duration_us / segments

    program = ExperimentProgram(name=name)
    if initial_bitstring is not None:
        if len(initial_bitstring) != n_atoms:
            raise ValueError("initial bitstring length must equal n_atoms")
        program = program.then(Prepare(initial_bitstring))
    for index in range(segments):
        midpoint = (index + 0.5) / segments
        scale = math.sin(math.pi * midpoint) ** 2
        program = program.then(
            ParallelPlay(
                (
                    Play(
                        lower_channel,
                        (atom,),
                        ConstantPulse(
                            segment_duration_us,
                            scale * peak_omega_lower_rad_per_us,
                        ),
                    ),
                    Play(
                        upper_channel,
                        (atom,),
                        ConstantPulse(
                            segment_duration_us,
                            scale * peak_omega_upper_rad_per_us,
                        ),
                    ),
                )
            )
        )
    if measure:
        program = program.then(Measure())
    return program
