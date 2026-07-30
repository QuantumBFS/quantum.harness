"""Compile actual sampled field waveforms into public experiment primitives."""

from __future__ import annotations

from typing import Mapping, Tuple

from .contracts import (
    ConstantPulse,
    Delay,
    ExperimentProgram,
    Measure,
    ParallelPlay,
    Play,
    Prepare,
)
from .waveforms import SampledWaveform


def compile_sampled_fields(
    *,
    n_atoms: int,
    fields: Mapping[str, SampledWaveform],
    targets: Mapping[str, Tuple[int, ...]],
    initial_bitstring: str | None = None,
    measure: bool = True,
    amplitude_epsilon: float = 1e-14,
    name: str = "compiled-sampled-fields",
) -> ExperimentProgram:
    """Compile synchronized zero-order-hold field samples into a program.

    This compiler consumes *actual field* waveforms after hardware transfer,
    not controller command waveforms.  Empty intervals become ``Delay``;
    one active channel becomes ``Play``; concurrent channels become
    ``ParallelPlay``.
    """

    if not fields:
        raise ValueError("at least one sampled field is required")
    if set(fields) != set(targets):
        raise ValueError("fields and targets must have identical channel keys")
    dt_values = {waveform.dt_us for waveform in fields.values()}
    sample_counts = {waveform.n_samples for waveform in fields.values()}
    if len(dt_values) != 1 or len(sample_counts) != 1:
        raise ValueError("sampled fields must be aligned in dt and length")
    dt_us = next(iter(dt_values))
    n_samples = next(iter(sample_counts))
    program = ExperimentProgram(name=name)
    if initial_bitstring is not None:
        if len(initial_bitstring) != n_atoms:
            raise ValueError("initial bitstring length must equal n_atoms")
        program = program.then(Prepare(initial_bitstring))

    channel_order = tuple(sorted(fields))
    for index in range(n_samples):
        plays = []
        for channel in channel_order:
            waveform = fields[channel]
            amplitude = waveform.amplitude_rad_per_us[index]
            if amplitude <= amplitude_epsilon:
                continue
            plays.append(
                Play(
                    channel,
                    targets[channel],
                    ConstantPulse(
                        dt_us,
                        amplitude,
                        waveform.phase_rad[index],
                        waveform.detuning_rad_per_us[index],
                    ),
                )
            )
        if not plays:
            program = program.then(Delay(dt_us))
        elif len(plays) == 1:
            program = program.then(plays[0])
        else:
            program = program.then(ParallelPlay(tuple(plays)))
    if measure:
        program = program.then(Measure())
    return program
