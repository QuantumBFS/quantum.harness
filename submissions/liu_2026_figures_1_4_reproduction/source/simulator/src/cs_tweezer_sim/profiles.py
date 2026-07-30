"""Named environment profiles.

The initial profile is intentionally reduced and uses generous actuator limits.
It is an API-validation fixture, not a calibrated Cs experiment.
"""

from __future__ import annotations

from .config import ChannelSpec, EnvironmentConfig, ReducedModelConfig


def reduced_validation_profile(
    *,
    n_atoms: int,
    blockade_rad_per_us: float,
) -> EnvironmentConfig:
    """Return a deterministic three-level validation profile."""

    positions = tuple((float(index) * 5.0, 0.0) for index in range(n_atoms))
    channels = {
        "microwave": ChannelSpec(
            name="microwave",
            transition="01",
            addressing="local",
            max_amplitude_rad_per_us=100.0,
            max_abs_detuning_rad_per_us=100.0,
        ),
        "rydberg": ChannelSpec(
            name="rydberg",
            transition="1r",
            addressing="local",
            max_amplitude_rad_per_us=100.0,
            max_abs_detuning_rad_per_us=100.0,
        ),
    }
    return EnvironmentConfig(
        atom_positions_um=positions,
        channels=channels,
        model=ReducedModelConfig(blockade_rad_per_us=blockade_rad_per_us),
        profile_name="reduced-validation-v1",
    )
