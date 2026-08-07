"""S4-A tests for dynamic magnetic and laser phase/frequency noise."""

from __future__ import annotations

import math

import numpy as np
import qutip as qt

from cs_tweezer_sim import (
    ConstantPulse,
    Delay,
    ExperimentProgram,
    LaserPhaseFrequencyNoiseModel,
    MagneticFieldNoiseModel,
    Measure,
    Play,
    SampledTimeTrace,
    SimulationContext,
    StochasticScopeEngine,
    ZeemanLevelShiftSpec,
)
from cs_tweezer_sim.profiles import reduced_validation_profile
from cs_tweezer_sim.qutip_backend import QutipReducedBackend


def _engine(model, n_atoms: int, seed: int = 1) -> StochasticScopeEngine:
    engine = StochasticScopeEngine(model.blocks(n_atoms), seed=seed)
    engine.begin_iteration()
    engine.begin_shot()
    return engine


def test_sampled_trace_interpolation_and_context_composition() -> None:
    first = SampledTimeTrace(1.0, (0.0, 2.0, 4.0))
    second = SampledTimeTrace(0.5, (1.0, 1.0, 1.0), interpolation="zoh")
    context = SimulationContext.combine(
        SimulationContext(
            channel_phase_offset_traces_rad={("drive", 0): first}
        ),
        SimulationContext(
            channel_phase_offset_traces_rad={("drive", 0): second}
        ),
    )

    assert first.value_at(0.5) == 1.0
    assert first.breakpoints(0.25, 1.75) == (1.0,)
    assert context.channel_phase_offset_rad("drive", 0, 0.5) == 2.0
    assert context.dynamic_breakpoints(0.25, 1.5) == (0.5, 1.0)


def test_long_play_matches_explicit_trace_interval_plays() -> None:
    config = reduced_validation_profile(n_atoms=1, blockade_rad_per_us=0.0)
    backend = QutipReducedBackend(config)
    trace = SampledTimeTrace(
        0.05,
        (0.0, 0.1, -0.2, 0.3, 0.0),
        interpolation="zoh",
    )
    context = SimulationContext(
        channel_phase_offset_traces_rad={("microwave", 0): trace}
    )
    long_program = ExperimentProgram(
        (
            Play(
                "microwave",
                (0,),
                ConstantPulse(0.2, 2.0 * math.pi),
            ),
        )
    )
    split_program = ExperimentProgram(
        tuple(
            Play(
                "microwave",
                (0,),
                ConstantPulse(0.05, 2.0 * math.pi),
            )
            for _ in range(4)
        )
    )

    long_state = backend.simulate(long_program, context=context).state
    split_state = backend.simulate(split_program, context=context).state

    assert qt.metrics.tracedist(qt.ket2dm(long_state), qt.ket2dm(split_state)) < 2e-9


def test_laser_phase_realization_is_reproducible_and_correlated() -> None:
    correlation = ((1.0, 0.7), (0.7, 1.0))
    model = LaserPhaseFrequencyNoiseModel(
        channels=("blue", "ir"),
        lorentzian_linewidth_fwhm_hz=(20_000.0, 30_000.0),
        quasistatic_frequency_covariance_hz2=((0.0, 0.0), (0.0, 0.0)),
        ou_frequency_sigma_hz=(0.0, 0.0),
        sample_interval_us=0.01,
        phase_diffusion_correlation=correlation,
    )
    first = model.realization(_engine(model, 2, 91), 2, 200.0)
    second = model.realization(_engine(model, 2, 91), 2, 200.0)
    blue = np.diff(first.phase_traces_rad["blue"].values)
    infrared = np.diff(first.phase_traces_rad["ir"].values)

    assert first.phase_traces_rad["blue"].values == second.phase_traces_rad[
        "blue"
    ].values
    assert abs(float(np.corrcoef(blue, infrared)[0, 1]) - 0.7) < 0.03
    assert (
        first.context.channel_phase_offset_traces_rad[("blue", 0)][0]
        is first.context.channel_phase_offset_traces_rad[("blue", 1)][0]
    )


def test_lorentzian_and_quasistatic_coherence_match_analytics() -> None:
    linewidth_hz = 80_000.0
    sigma_hz = 50_000.0
    duration_us = 1.5
    sample_count = 8_000
    models = (
        (
            LaserPhaseFrequencyNoiseModel(
                ("drive",),
                (linewidth_hz,),
                ((0.0,),),
                (0.0,),
                duration_us,
            ),
            math.exp(-math.pi * linewidth_hz * duration_us * 1e-6),
        ),
        (
            LaserPhaseFrequencyNoiseModel(
                ("drive",),
                (0.0,),
                ((sigma_hz**2,),),
                (0.0,),
                duration_us,
            ),
            math.exp(
                -2.0
                * math.pi**2
                * sigma_hz**2
                * (duration_us * 1e-6) ** 2
            ),
        ),
    )
    for model, expected in models:
        engine = StochasticScopeEngine(model.blocks(1), seed=17)
        engine.begin_iteration()
        phasors = []
        for _ in range(sample_count):
            engine.begin_shot()
            realization = model.realization(engine, 1, duration_us)
            phase = realization.phase_traces_rad["drive"].values[-1]
            phasors.append(np.exp(1j * phase))
        observed = abs(np.mean(phasors))
        assert abs(float(observed) - expected) < 0.025


def test_ou_frequency_has_stationary_variance_and_correlation() -> None:
    sigma_hz = 12_000.0
    correlation_time_us = 0.5
    dt_us = 0.01
    model = LaserPhaseFrequencyNoiseModel(
        ("drive",),
        (0.0,),
        ((0.0,),),
        (sigma_hz,),
        dt_us,
        ou_correlation_time_us=correlation_time_us,
    )
    realization = model.realization(
        _engine(model, 1, 13),
        1,
        500.0,
    )
    values = np.asarray(
        realization.frequency_traces_hz["drive"].values,
        dtype=float,
    )
    lag = round(correlation_time_us / dt_us)
    observed_sigma = float(np.std(values))
    observed_correlation = float(np.corrcoef(values[:-lag], values[lag:])[0, 1])

    assert abs(observed_sigma / sigma_hz - 1.0) < 0.03
    assert abs(observed_correlation - math.exp(-1.0)) < 0.03


def test_zeeman_maps_field_before_energy_and_preserves_scopes() -> None:
    level = ZeemanLevelShiftSpec(
        "1",
        linear_rad_per_us_per_g=2.0,
        quadratic_rad_per_us_per_g2=3.0,
    )
    assert level.energy_rad_per_us(0.4) == 2.0 * 0.4 + 3.0 * 0.4**2

    model = MagneticFieldNoiseModel(
        bias_field_g=0.2,
        level_shifts=(level,),
        iteration_common_sigma_g=0.01,
        shot_common_sigma_g=0.02,
        shot_local_sigma_g=0.005,
        within_shot_common_sigma_g=0.003,
        within_shot_local_sigma_g=0.002,
        within_shot_correlation_time_us=0.2,
        sample_interval_us=0.01,
    )
    engine = StochasticScopeEngine(model.blocks(2), seed=55)
    engine.begin_iteration()
    iteration_draw = engine.sample("magnetic_field_iteration_common_g")["common"]
    engine.begin_shot()
    first = model.realization(engine, 2, 0.5)
    same_iteration_draw = engine.sample("magnetic_field_iteration_common_g")[
        "common"
    ]
    engine.begin_shot()
    second = model.realization(engine, 2, 0.5)
    engine.begin_iteration()
    engine.begin_shot()
    next_iteration_draw = engine.sample("magnetic_field_iteration_common_g")[
        "common"
    ]

    assert iteration_draw == same_iteration_draw
    assert iteration_draw != next_iteration_draw
    assert first.base_fields_g != second.base_fields_g
    assert np.std(first.field_traces_g[0].values) > 0
    atom = 0
    base = first.base_fields_g[atom]
    energy_trace = first.context.level_energy_offset_traces_rad_per_us[
        (atom, "1")
    ][0]
    for field, offset in zip(
        first.field_traces_g[atom].values,
        energy_trace.values,
    ):
        expected = level.energy_rad_per_us(field) - level.energy_rad_per_us(base)
        assert abs(offset - expected) < 1e-12


def test_dynamic_zeeman_delay_accumulates_full_trace_phase() -> None:
    config = reduced_validation_profile(n_atoms=1, blockade_rad_per_us=0.0)
    backend = QutipReducedBackend(config)
    energy = SampledTimeTrace(0.1, (0.0, 1.0, -0.5, 0.25))
    context = SimulationContext(
        level_energy_offset_traces_rad_per_us={(0, "1"): energy}
    )
    duration_us = 0.3
    program = ExperimentProgram((Delay(duration_us), Measure()))
    initial = (backend.computational_basis_state("0") + backend.computational_basis_state("1")).unit()
    final = backend.simulate(
        program,
        initial_state=initial,
        ignore_prepare=True,
        context=context,
    ).state
    integral = sum(
        0.5 * (energy.values[index] + energy.values[index + 1]) * 0.1
        for index in range(3)
    )
    expected = (
        backend.computational_basis_state("0")
        + np.exp(-1j * integral) * backend.computational_basis_state("1")
    ).unit()

    assert qt.metrics.tracedist(qt.ket2dm(final), qt.ket2dm(expected)) < 2e-9
