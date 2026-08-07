"""Public calibration circuits and finite-shot estimators."""

from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np
from scipy.optimize import curve_fit

from .contracts import (
    ConstantPulse,
    ExperimentProgram,
    ExperimentResult,
    Measure,
    Play,
    Prepare,
)
from .programs import ramsey_phase_program


def rabi_scan_programs(
    durations_us: Iterable[float],
    *,
    rabi_command_rad_per_us: float,
    atom: int = 0,
    n_atoms: int = 1,
) -> tuple[ExperimentProgram, ...]:
    """Build an ordinary pulse-duration Rabi scan."""

    if rabi_command_rad_per_us <= 0:
        raise ValueError("Rabi command must be positive")
    programs = []
    for index, duration in enumerate(durations_us):
        if duration <= 0:
            raise ValueError("Rabi scan durations must be positive")
        programs.append(
            ExperimentProgram(name=f"rabi-scan-{index:03d}")
            .then(Prepare("0" * n_atoms))
            .then(
                Play(
                    "microwave",
                    (atom,),
                    ConstantPulse(float(duration), rabi_command_rad_per_us),
                )
            )
            .then(Measure())
        )
    return tuple(programs)


def ramsey_phase_scan_programs(
    phases_rad: Iterable[float],
    *,
    rabi_rad_per_us: float,
    delay_us: float = 0.0,
) -> tuple[ExperimentProgram, ...]:
    """Build a phase scan using the generic Ramsey program."""

    return tuple(
        ramsey_phase_program(
            phase_rad=float(phase),
            rabi_rad_per_us=rabi_rad_per_us,
            delay_us=delay_us,
            measure=True,
        )
        for phase in phases_rad
    )


def public_success_probability(
    result: ExperimentResult, expected_outcome: str
) -> float:
    """Compute a binomial objective from public counts only."""

    if result.resources.shots <= 0:
        raise ValueError("result has no shots")
    return result.counts.get(expected_outcome, 0) / result.resources.shots


def fit_rabi_rate_rad_per_us(
    durations_us: Sequence[float],
    results: Sequence[ExperimentResult],
    *,
    initial_rate_rad_per_us: float,
    excited_outcome: str = "1",
) -> float:
    """Fit ``offset + contrast*sin(omega*t/2)^2`` to public counts."""

    if (
        len(durations_us) != len(results)
        or len(results) < 5
        or initial_rate_rad_per_us <= 0
    ):
        raise ValueError("Rabi fit inputs are invalid")
    times = np.asarray(durations_us, dtype=float)
    probabilities = np.asarray(
        [
            public_success_probability(result, excited_outcome)
            for result in results
        ]
    )

    def model(time, offset, contrast, omega):
        return offset + contrast * np.sin(0.5 * omega * time) ** 2

    fitted, _ = curve_fit(
        model,
        times,
        probabilities,
        p0=(0.0, 1.0, initial_rate_rad_per_us),
        bounds=(
            (-0.2, 0.0, 0.25 * initial_rate_rad_per_us),
            (0.2, 1.2, 2.0 * initial_rate_rad_per_us),
        ),
        maxfev=10000,
    )
    return float(fitted[2])


def fit_ramsey_phase_offset_rad(
    scanned_phases_rad: Sequence[float],
    results: Sequence[ExperimentResult],
    *,
    excited_outcome: str = "1",
) -> float:
    """Fit a Ramsey fringe phase from public counts only."""

    if len(scanned_phases_rad) != len(results) or len(results) < 5:
        raise ValueError("Ramsey fit inputs are invalid")
    phases = np.asarray(scanned_phases_rad, dtype=float)
    probabilities = np.asarray(
        [
            public_success_probability(result, excited_outcome)
            for result in results
        ]
    )

    def model(phase, offset, cosine, sine):
        return offset + cosine * np.cos(phase) + sine * np.sin(phase)

    fitted, _ = curve_fit(
        model,
        phases,
        probabilities,
        p0=(0.5, 0.5, 0.0),
        maxfev=10000,
    )
    return float(math.atan2(-fitted[2], fitted[1]))
