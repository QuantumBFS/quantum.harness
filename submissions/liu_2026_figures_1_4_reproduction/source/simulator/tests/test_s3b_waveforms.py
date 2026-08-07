"""S3-B tests for hardware transfer and Rydberg lifetime semantics."""

from __future__ import annotations

import math

from cs_tweezer_sim import Delay, ExperimentProgram
from cs_tweezer_sim.contracts import Prepare
from cs_tweezer_sim.cs_profiles import (
    graham_2019_scattering_profile,
    radnaev_2025_nominal_profile,
)
from cs_tweezer_sim.factory import create_multilevel_platform
from cs_tweezer_sim.waveform_compiler import compile_sampled_fields
from cs_tweezer_sim.waveforms import (
    AnalyticWaveform,
    CompositeTransfer,
    FirstOrderLowPassTransfer,
    GainOffsetTransfer,
    HardwareTransferGraph,
    PureDelayTransfer,
    SampledWaveform,
)


def test_analytic_sampling_and_integer_delay_are_exact() -> None:
    analytic = AnalyticWaveform(
        duration_us=0.01,
        amplitude=lambda time: 2.0 + math.sin(2.0 * math.pi * time),
        phase=lambda time: 3.0 * time,
        detuning=lambda time: -4.0 * time,
    )
    waveform = analytic.sample(dt_us=0.001)

    for index in range(waveform.n_samples):
        midpoint = (index + 0.5) * waveform.dt_us
        assert abs(
            waveform.amplitude_rad_per_us[index]
            - (2.0 + math.sin(2.0 * math.pi * midpoint))
        ) < 1e-14
        assert abs(waveform.phase_rad[index] - 3.0 * midpoint) < 1e-14
        assert (
            abs(waveform.detuning_rad_per_us[index] + 4.0 * midpoint)
            < 1e-14
        )

    delayed = PureDelayTransfer(0.003).apply(waveform)
    assert delayed.amplitude_rad_per_us[:3] == (0.0, 0.0, 0.0)
    assert delayed.amplitude_rad_per_us[3:] == waveform.amplitude_rad_per_us
    assert delayed.phase_rad[3:] == waveform.phase_rad
    assert delayed.detuning_rad_per_us[3:] == waveform.detuning_rad_per_us


def test_first_order_low_pass_matches_zoh_step_and_rise_time() -> None:
    bandwidth_mhz = 5.0
    transfer = FirstOrderLowPassTransfer(bandwidth_mhz)
    tau = transfer.time_constant_us
    dt_us = tau / 100.0
    step = SampledWaveform.from_amplitude(
        dt_us=dt_us,
        amplitude_rad_per_us=(1.0,) * 500,
    )
    output = transfer.apply(step)
    alpha = math.exp(-dt_us / tau)
    expected = tuple(1.0 - alpha ** (index + 1) for index in range(500))

    assert max(
        abs(actual - target)
        for actual, target in zip(output.amplitude_rad_per_us, expected)
    ) < 1e-12

    first_10 = next(
        index
        for index, value in enumerate(output.amplitude_rad_per_us)
        if value >= 0.1
    )
    first_90 = next(
        index
        for index, value in enumerate(output.amplitude_rad_per_us)
        if value >= 0.9
    )
    numerical_rise = (first_90 - first_10) * dt_us
    assert (
        abs(numerical_rise - transfer.rise_time_10_90_us)
        / transfer.rise_time_10_90_us
        < 0.05
    )


def test_transfer_composition_and_compiler_preserve_timing() -> None:
    command = SampledWaveform.from_amplitude(
        dt_us=0.01,
        amplitude_rad_per_us=(1.0, 1.0, 0.0, 0.0),
    )
    stages = (
        GainOffsetTransfer(amplitude_gain=2.0),
        PureDelayTransfer(0.01),
        FirstOrderLowPassTransfer(4.0, ringdown_time_constants=2.0),
    )
    manual = command
    for stage in stages:
        manual = stage.apply(manual)
    composed = CompositeTransfer(stages).apply(command)
    assert composed == manual

    graph = HardwareTransferGraph(
        {
            "rydberg_459": CompositeTransfer(stages),
            "rydberg_1040": CompositeTransfer(stages),
        }
    )
    fields = graph.apply(
        {"rydberg_459": command, "rydberg_1040": command}
    )
    program = compile_sampled_fields(
        n_atoms=1,
        fields=fields,
        targets={"rydberg_459": (0,), "rydberg_1040": (0,)},
        initial_bitstring="1",
    )
    result = create_multilevel_platform(
        graham_2019_scattering_profile()
    ).public.execute(program, shots=1)
    duration = next(iter(fields.values())).duration_us

    assert math.isclose(
        result.resources.sequence_time_per_shot_us,
        duration,
        abs_tol=1e-12,
    )
    assert math.isclose(
        result.resources.channel_time_per_shot_us["rydberg_459"],
        result.resources.channel_time_per_shot_us["rydberg_1040"],
        abs_tol=1e-12,
    )


def test_69s_lifetime_is_exponential_and_preparation_stays_privileged() -> None:
    config = radnaev_2025_nominal_profile(n_atoms=1)
    oracle = create_multilevel_platform(config).oracle
    tau = config.nominal_controls["rydberg_lifetime_us_300k"]

    for ratio in (0.5, 1.0, 2.0):
        program = ExperimentProgram(name="69S-lifetime").then(
            Delay(ratio * tau)
        )
        probabilities = oracle.outcome_probabilities_from_local_levels(
            program,
            ("r",),
        )
        assert abs(probabilities["R"] - math.exp(-ratio)) < 2e-7
        assert abs(probabilities["R"] + probabilities["L"] - 1.0) < 1e-10

    assert "physical" not in Prepare.__name__.lower()
    import cs_tweezer_sim.contracts as contracts

    assert "PreparePhysical" not in vars(contracts)


def test_filtered_square_reduces_nonadiabatic_scattering() -> None:
    config = graham_2019_scattering_profile()
    controls = config.nominal_controls
    dt_us = 0.0005
    n_on = round(controls["pi_duration_us"] / dt_us)
    command = SampledWaveform.from_amplitude(
        dt_us=dt_us,
        amplitude_rad_per_us=(
            controls["omega_459_rad_per_us"],
        )
        * n_on,
    )
    low_pass = CompositeTransfer(
        (FirstOrderLowPassTransfer(10.0, ringdown_time_constants=8.0),)
    )
    graph = HardwareTransferGraph(
        {"rydberg_459": low_pass, "rydberg_1040": low_pass}
    )
    preliminary = graph.apply(
        {"rydberg_459": command, "rydberg_1040": command}
    )
    effective_area = (
        sum(
            lower * upper
            for lower, upper in zip(
                preliminary["rydberg_459"].amplitude_rad_per_us,
                preliminary["rydberg_1040"].amplitude_rad_per_us,
            )
        )
        * dt_us
        / (2.0 * controls["one_photon_detuning_rad_per_us"])
    )
    command_gain = math.sqrt(math.pi / effective_area)
    calibrated = command.scale_amplitude(command_gain)
    fields = graph.apply(
        {"rydberg_459": calibrated, "rydberg_1040": calibrated}
    )
    program = compile_sampled_fields(
        n_atoms=1,
        fields=fields,
        targets={"rydberg_459": (0,), "rydberg_1040": (0,)},
        initial_bitstring="1",
    )
    probabilities = create_multilevel_platform(
        config
    ).oracle.outcome_probabilities(program)
    abrupt_loss = 0.003960287036913625

    assert 1.0 - probabilities["L"] / abrupt_loss > 0.15
    assert probabilities["E"] < 1e-4
