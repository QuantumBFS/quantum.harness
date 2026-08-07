"""Provenance-aware loaders and generic program mappings for published pulses.

Published pulse data remain ordinary sampled controls.  This module does not
add a privileged ``CZ`` operation to the backend: it translates upstream
amplitude/phase samples into the same public ``Play`` primitives available to
any benchmarked controller.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .contracts import ExperimentProgram
from .waveform_compiler import compile_sampled_fields
from .waveforms import SampledWaveform


@dataclass(frozen=True)
class DimensionlessPublishedPulse:
    """Zero-order-hold pulse tabulated in units of ``1/Omega_max``.

    ``sample_times_over_omega`` contains interval start times and
    ``terminal_time_over_omega`` is the exclusive end time.  The physical
    interval duration is obtained by dividing by ``Omega_max`` in rad/time,
    exactly as in the source paper.
    """

    source_name: str
    sample_times_over_omega: tuple[float, ...]
    amplitude_fraction: tuple[float, ...]
    phase_rad: tuple[float, ...]
    terminal_time_over_omega: float

    def __post_init__(self) -> None:
        count = len(self.sample_times_over_omega)
        if count == 0:
            raise ValueError("published pulse requires at least one interval")
        if len(self.amplitude_fraction) != count or len(self.phase_rad) != count:
            raise ValueError("published pulse arrays must have matching lengths")
        if not math.isclose(
            self.sample_times_over_omega[0], 0.0, abs_tol=1e-14
        ):
            raise ValueError("published pulse must start at zero")
        boundaries = self.sample_times_over_omega + (
            self.terminal_time_over_omega,
        )
        steps = tuple(
            boundaries[index + 1] - boundaries[index]
            for index in range(count)
        )
        if any(step <= 0 or not math.isfinite(step) for step in steps):
            raise ValueError("published pulse times must increase")
        if not all(
            math.isclose(step, steps[0], rel_tol=0.0, abs_tol=2e-12)
            for step in steps
        ):
            raise ValueError("published pulse must use a uniform time grid")
        if any(
            amplitude < 0 or not math.isfinite(amplitude)
            for amplitude in self.amplitude_fraction
        ):
            raise ValueError("published amplitudes must be finite and non-negative")
        if not all(math.isfinite(phase) for phase in self.phase_rad):
            raise ValueError("published phases must be finite")

    @property
    def n_intervals(self) -> int:
        return len(self.amplitude_fraction)

    @property
    def interval_duration_over_omega(self) -> float:
        return self.terminal_time_over_omega / self.n_intervals

    def subdivide(self, factor: int) -> "DimensionlessPublishedPulse":
        """Split every ZOH interval without changing its physical field."""

        if factor < 1:
            raise ValueError("subdivision factor must be positive")
        if factor == 1:
            return self
        step = self.interval_duration_over_omega / factor
        times = tuple(
            index * step for index in range(self.n_intervals * factor)
        )
        return DimensionlessPublishedPulse(
            source_name=f"{self.source_name}:subdivide-{factor}",
            sample_times_over_omega=times,
            amplitude_fraction=tuple(
                amplitude
                for amplitude in self.amplitude_fraction
                for _ in range(factor)
            ),
            phase_rad=tuple(
                phase for phase in self.phase_rad for _ in range(factor)
            ),
            terminal_time_over_omega=self.terminal_time_over_omega,
        )

    def to_waveform(
        self,
        *,
        omega_max_rad_per_us: float,
        phase_convention: Literal[
            "source", "backend_effective", "backend_upper_ladder"
        ] = "source",
        amplitude_scale_rad_per_us: float | None = None,
    ) -> SampledWaveform:
        """Convert dimensionless source samples to one physical waveform.

        ``backend_effective`` maps the source coefficient
        ``Omega exp(+i phi)|1><r|/2`` to the backend convention
        ``exp(-i phase)|1><r|/2``.

        ``backend_upper_ladder`` additionally accounts for the minus sign from
        eliminating a positive-energy intermediate state when the lower-leg
        phase is fixed to zero.
        """

        if omega_max_rad_per_us <= 0 or not math.isfinite(
            omega_max_rad_per_us
        ):
            raise ValueError("omega_max_rad_per_us must be finite and positive")
        amplitude_scale = (
            omega_max_rad_per_us
            if amplitude_scale_rad_per_us is None
            else amplitude_scale_rad_per_us
        )
        if amplitude_scale <= 0 or not math.isfinite(amplitude_scale):
            raise ValueError("amplitude scale must be finite and positive")
        if phase_convention == "source":
            phases = self.phase_rad
        elif phase_convention == "backend_effective":
            phases = tuple(-phase for phase in self.phase_rad)
        elif phase_convention == "backend_upper_ladder":
            phases = tuple(math.pi - phase for phase in self.phase_rad)
        else:  # pragma: no cover - Literal protects typed callers.
            raise ValueError(f"unknown phase convention: {phase_convention}")
        return SampledWaveform(
            dt_us=self.interval_duration_over_omega / omega_max_rad_per_us,
            amplitude_rad_per_us=tuple(
                amplitude_scale * fraction
                for fraction in self.amplitude_fraction
            ),
            phase_rad=phases,
            detuning_rad_per_us=(0.0,) * self.n_intervals,
        )


def load_jandura_pulse_csv(path: str | Path) -> DimensionlessPublishedPulse:
    """Load one unmodified Jandura--Pupillo Figshare CSV.

    The published files contain one final terminal-time row with empty
    amplitude and phase fields.  It is a boundary, not a 100th control sample.
    """

    source = Path(path)
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) < 2:
        raise ValueError("published CSV must contain controls and a terminal row")
    required = {"t", "|Omega|", "arg(Omega)"}
    if set(rows[0]) != required:
        raise ValueError(f"unexpected published CSV columns: {tuple(rows[0])}")
    terminal = rows[-1]
    if terminal["|Omega|"].strip() or terminal["arg(Omega)"].strip():
        raise ValueError("final published CSV row must be an empty terminal row")
    control_rows = rows[:-1]
    if any(
        not row["|Omega|"].strip() or not row["arg(Omega)"].strip()
        for row in control_rows
    ):
        raise ValueError("only the terminal row may have empty controls")
    return DimensionlessPublishedPulse(
        source_name=source.name,
        sample_times_over_omega=tuple(
            float(row["t"]) for row in control_rows
        ),
        amplitude_fraction=tuple(
            float(row["|Omega|"]) for row in control_rows
        ),
        phase_rad=tuple(
            float(row["arg(Omega)"]) for row in control_rows
        ),
        terminal_time_over_omega=float(terminal["t"]),
    )

def effective_global_program(
    pulse: DimensionlessPublishedPulse,
    *,
    omega_max_rad_per_us: float,
    n_atoms: int = 2,
    channel: str = "rydberg",
    measure: bool = False,
    name: str | None = None,
) -> ExperimentProgram:
    """Map a published effective ``|1>-|r>`` pulse to public primitives."""

    waveform = pulse.to_waveform(
        omega_max_rad_per_us=omega_max_rad_per_us,
        phase_convention="backend_effective",
    )
    return compile_sampled_fields(
        n_atoms=n_atoms,
        fields={channel: waveform},
        targets={channel: tuple(range(n_atoms))},
        measure=measure,
        name=name or f"effective-global:{pulse.source_name}",
    )


def explicit_ladder_global_program(
    pulse: DimensionlessPublishedPulse,
    *,
    effective_omega_max_rad_per_us: float,
    omega_lower_rad_per_us: float,
    omega_upper_rad_per_us: float,
    n_atoms: int = 2,
    lower_channel: str = "rydberg_459",
    upper_channel: str = "rydberg_1040",
    measure: bool = False,
    name: str | None = None,
) -> ExperimentProgram:
    """Map an effective pulse to simultaneous explicit optical ladder fields.

    The lower-leg magnitude stays fixed and the source normalized amplitude is
    applied to the upper leg.  For the time-optimal CZ source used in S3-D the
    magnitude is identically one, matching a phase-only modulation.  Other
    source files remain executable, but this upper-only amplitude mapping must
    then be treated as an explicit modelling choice rather than source truth.
    """

    lower = SampledWaveform(
        dt_us=(
            pulse.interval_duration_over_omega
            / effective_omega_max_rad_per_us
        ),
        amplitude_rad_per_us=(omega_lower_rad_per_us,) * pulse.n_intervals,
        phase_rad=(0.0,) * pulse.n_intervals,
        detuning_rad_per_us=(0.0,) * pulse.n_intervals,
    )
    upper = pulse.to_waveform(
        omega_max_rad_per_us=effective_omega_max_rad_per_us,
        amplitude_scale_rad_per_us=omega_upper_rad_per_us,
        phase_convention="backend_upper_ladder",
    )
    return compile_sampled_fields(
        n_atoms=n_atoms,
        fields={lower_channel: lower, upper_channel: upper},
        targets={
            lower_channel: tuple(range(n_atoms)),
            upper_channel: tuple(range(n_atoms)),
        },
        measure=measure,
        name=name or f"explicit-ladder-global:{pulse.source_name}",
    )
