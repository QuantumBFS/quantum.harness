"""S3-C tests for stochastic scopes and correlated Cs thermal/laser noise."""

from __future__ import annotations

import math

import numpy as np
import pytest

from cs_tweezer_sim import (
    ChannelSpec,
    ConstantPulse,
    Delay,
    EnvironmentConfig,
    ExperimentProgram,
    GaussianBeamCouplingSpec,
    GaussianBlockSpec,
    Measure,
    Play,
    Prepare,
    PulseEnergyNoiseModel,
    ReducedModelConfig,
    SimulationContext,
    StochasticExperimentRuntime,
    StochasticScopeEngine,
    TemporalScope,
    ThermalPositionNoiseModel,
    analytic_doppler_coherence,
    doppler_t2_us,
    harmonic_position_sigma_um,
)
from cs_tweezer_sim.oracle import TruthOracle
from cs_tweezer_sim.qutip_backend import QutipReducedBackend
from cs_tweezer_sim.stochastic import (
    BOLTZMANN_J_PER_K,
    CS133_MASS_KG,
    HBAR_J_S,
    thermal_velocity_sigma_m_per_s,
    two_photon_effective_wavevector_rad_per_m,
)


def _scalar_block(name: str, scope: TemporalScope) -> GaussianBlockSpec:
    return GaussianBlockSpec(
        name=name,
        keys=(name,),
        mean=(0.0,),
        covariance=((1.0,),),
        scope=scope,
    )


def test_scope_cache_reproducibility_and_covariance() -> None:
    blocks = (
        _scalar_block("fixed", TemporalScope.FIXED),
        _scalar_block("iteration", TemporalScope.ITERATION),
        _scalar_block("shot", TemporalScope.SHOT),
        _scalar_block("within", TemporalScope.WITHIN_SHOT),
    )
    first = StochasticScopeEngine(blocks, seed=101)
    second = StochasticScopeEngine(blocks, seed=101)
    sequences: list[tuple[float, ...]] = []
    for engine in (first, second):
        fixed_0 = engine.sample("fixed")["fixed"]
        fixed_1 = engine.sample("fixed")["fixed"]
        engine.begin_iteration()
        iteration_0 = engine.sample("iteration")["iteration"]
        engine.begin_shot()
        shot_0 = engine.sample("shot")["shot"]
        shot_0_repeat = engine.sample("shot")["shot"]
        within_0 = engine.sample("within", within_shot_token=0)["within"]
        within_0_repeat = engine.sample(
            "within", within_shot_token=0
        )["within"]
        within_1 = engine.sample("within", within_shot_token=1)["within"]
        engine.begin_shot()
        shot_1 = engine.sample("shot")["shot"]
        iteration_0_repeat = engine.sample("iteration")["iteration"]
        engine.begin_iteration()
        iteration_1 = engine.sample("iteration")["iteration"]
        sequences.append(
            (
                fixed_0,
                fixed_1,
                iteration_0,
                iteration_0_repeat,
                iteration_1,
                shot_0,
                shot_0_repeat,
                shot_1,
                within_0,
                within_0_repeat,
                within_1,
            )
        )
    assert sequences[0] == sequences[1]
    values = sequences[0]
    assert values[0] == values[1]
    assert values[2] == values[3]
    assert values[2] != values[4]
    assert values[5] == values[6]
    assert values[5] != values[7]
    assert values[8] == values[9]
    assert values[8] != values[10]

    correlated = GaussianBlockSpec(
        "correlated",
        ("x", "y"),
        (0.0, 0.0),
        ((1.0, 0.65), (0.65, 1.0)),
        TemporalScope.SHOT,
    )
    engine = StochasticScopeEngine((correlated,), seed=20260729)
    engine.begin_iteration()
    samples = np.empty((20_000, 2))
    for index in range(len(samples)):
        engine.begin_shot()
        draw = engine.sample("correlated")
        samples[index] = draw["x"], draw["y"]
    assert abs(float(np.corrcoef(samples.T)[0, 1]) - 0.65) < 0.02

    with pytest.raises(ValueError, match="positive semidefinite"):
        GaussianBlockSpec(
            "bad",
            ("x", "y"),
            (0.0, 0.0),
            ((1.0, 2.0), (2.0, 1.0)),
            TemporalScope.SHOT,
        )


def test_cs_doppler_analytic_monte_carlo_and_backend_ramsey() -> None:
    wavelengths = (459.4459, 1040.03)
    hot_t2 = doppler_t2_us(15.0, wavelengths_nm=wavelengths)
    cold_t2 = doppler_t2_us(2.6, wavelengths_nm=wavelengths)
    assert 5.9 <= hot_t2 <= 6.2
    assert 14.0 <= cold_t2 <= 16.0

    rng = np.random.default_rng(20260729)
    velocities = rng.normal(
        0.0, thermal_velocity_sigma_m_per_s(15.0), size=200_000
    )
    wavevector = two_photon_effective_wavevector_rad_per_m(wavelengths)
    angular_offsets_rad_per_us = wavevector * velocities * 1e-6
    errors = []
    for ratio in (0.5, 1.0, 1.5):
        numerical = float(
            np.mean(np.cos(angular_offsets_rad_per_us * ratio * hot_t2))
        )
        analytic = analytic_doppler_coherence(ratio * hot_t2, hot_t2)
        errors.append(abs(numerical - analytic))
    assert max(errors) < 0.005

    # Use effectively instantaneous analysis pulses so the frozen comparison
    # isolates the free-evolution Gaussian envelope rather than pulse-time
    # Doppler response.
    omega = 2.0 * math.pi * 500.0
    pi_over_two_duration = math.pi / (2.0 * omega)
    config = EnvironmentConfig(
        atom_positions_um=((0.0, 0.0),),
        channels={
            "rydberg": ChannelSpec(
                "rydberg", "1r", "local", 1.1 * omega, 2.0 * math.pi * 10.0
            )
        },
        model=ReducedModelConfig(blockade_rad_per_us=0.0),
        profile_name="S3C-effective-ground-Rydberg-Ramsey",
    )
    program = (
        ExperimentProgram(name="doppler-ramsey")
        .then(Prepare("1"))
        .then(
            Play(
                "rydberg",
                (0,),
                ConstantPulse(pi_over_two_duration, omega),
            )
        )
        .then(Delay(hot_t2))
        .then(
            Play(
                "rydberg",
                (0,),
                ConstantPulse(pi_over_two_duration, omega),
            )
        )
        .then(Measure())
    )
    oracle = TruthOracle(QutipReducedBackend(config))
    nodes, weights = np.polynomial.hermite.hermgauss(32)
    sigma_v = thermal_velocity_sigma_m_per_s(15.0)
    averaged_p1 = 0.0
    for node, weight in zip(nodes, weights):
        velocity = math.sqrt(2.0) * sigma_v * float(node)
        offset = wavevector * velocity * 1e-6
        probabilities = oracle.outcome_probabilities(
            program,
            context=SimulationContext(
                level_energy_offsets_rad_per_us={(0, "r"): offset}
            ),
        )
        averaged_p1 += float(weight) / math.sqrt(math.pi) * probabilities["1"]
    backend_coherence = 1.0 - 2.0 * averaged_p1
    assert abs(backend_coherence - math.exp(-1.0)) < 2e-4


def _cold_thermal_position_model() -> ThermalPositionNoiseModel:
    radial_sigma = harmonic_position_sigma_um(2.6, 60.9)
    axial_sigma = harmonic_position_sigma_um(2.6, 11.5)
    nominal = ((0.0, 0.0, 0.0), (6.0, 0.0, 0.0))
    return ThermalPositionNoiseModel(
        nominal_positions_um=nominal,
        sigma_xyz_um=(
            (radial_sigma, radial_sigma, axial_sigma),
            (radial_sigma, radial_sigma, axial_sigma),
        ),
        beams=tuple(
            GaussianBeamCouplingSpec(channel, atom, waist, nominal[atom])
            for atom in range(2)
            for channel, waist in (
                ("rydberg_459", 2.8),
                ("rydberg_1040", 3.0),
            )
        ),
    )


def test_thermal_position_jointly_controls_beams_and_blockade() -> None:
    temperature_uk = 1000.0
    frequency_khz = 60.9
    quantum_sigma = harmonic_position_sigma_um(
        temperature_uk, frequency_khz
    )
    omega = 2.0 * math.pi * frequency_khz * 1e3
    classical_sigma = (
        math.sqrt(
            BOLTZMANN_J_PER_K
            * temperature_uk
            * 1e-6
            / (CS133_MASS_KG * omega**2)
        )
        * 1e6
    )
    assert quantum_sigma > 0
    assert abs(quantum_sigma / classical_sigma - 1.0) < 0.01

    model = _cold_thermal_position_model()
    engine = StochasticScopeEngine(model.blocks(2), seed=303)
    engine.begin_iteration()
    engine.begin_shot()
    realization = model.realization(engine, 2)
    for beam in model.beams:
        position = realization.positions_um[beam.atom]
        rho2 = (
            (position[0] - beam.center_um[0]) ** 2
            + (position[1] - beam.center_um[1]) ** 2
        )
        expected = math.exp(-rho2 / beam.waist_um**2)
        assert abs(
            realization.context.channel_amplitude_scales[
                (beam.channel, beam.atom)
            ]
            - expected
        ) < 1e-14
    distance = math.dist(*realization.positions_um)
    expected_blockade_scale = (6.0 / distance) ** 6
    assert abs(
        realization.context.pair_interaction_scales[
            (0, 1, "measured blockade")
        ]
        - expected_blockade_scale
    ) < 1e-14

    engine = StochasticScopeEngine(model.blocks(2), seed=404)
    engine.begin_iteration()
    leg_scales = np.empty((20_000, 2))
    for index in range(len(leg_scales)):
        engine.begin_shot()
        context = model.context(engine, 2)
        leg_scales[index] = (
            context.channel_amplitude_scales[("rydberg_459", 0)],
            context.channel_amplitude_scales[("rydberg_1040", 0)],
        )
    assert float(np.corrcoef(leg_scales.T)[0, 1]) > 0.95


def test_pulse_energy_common_and_local_correlations() -> None:
    energy_sigma = 0.016
    common = PulseEnergyNoiseModel(
        channels=("rydberg",),
        energy_covariance=((energy_sigma**2,),),
    )
    common_engine = StochasticScopeEngine(common.blocks(2), seed=505)
    common_engine.begin_iteration()
    common_scales = np.empty((20_000, 2))
    for index in range(len(common_scales)):
        common_engine.begin_shot()
        context = common.context(common_engine, 2)
        common_scales[index] = (
            context.channel_amplitude_scales[("rydberg", 0)],
            context.channel_amplitude_scales[("rydberg", 1)],
        )
    assert float(np.corrcoef(common_scales.T)[0, 1]) > 0.99
    assert (
        abs(float(np.std(common_scales[:, 0], ddof=1)) / 0.008 - 1.0)
        < 0.05
    )

    independent = PulseEnergyNoiseModel(
        channels=("rydberg",),
        energy_covariance=((0.0,),),
        local_rabi_fractional_sigma=0.008,
    )
    independent_engine = StochasticScopeEngine(
        independent.blocks(2), seed=606
    )
    independent_engine.begin_iteration()
    independent_scales = np.empty((20_000, 2))
    for index in range(len(independent_scales)):
        independent_engine.begin_shot()
        context = independent.context(independent_engine, 2)
        independent_scales[index] = (
            context.channel_amplitude_scales[("rydberg", 0)],
            context.channel_amplitude_scales[("rydberg", 1)],
        )
    assert abs(float(np.corrcoef(independent_scales.T)[0, 1])) < 0.05


def test_stochastic_public_runtime_reproducible_and_hides_truth() -> None:
    omega = 2.0 * math.pi
    config = EnvironmentConfig(
        atom_positions_um=((0.0, 0.0),),
        channels={
            "rydberg": ChannelSpec(
                "rydberg", "1r", "local", 2.0 * omega, 2.0 * math.pi
            )
        },
        model=ReducedModelConfig(blockade_rad_per_us=0.0),
        profile_name="S3C-public-boundary-test",
    )
    program = (
        ExperimentProgram(name="stochastic-rabi")
        .then(Prepare("1"))
        .then(
            Play(
                "rydberg",
                (0,),
                ConstantPulse(math.pi / omega, omega),
            )
        )
        .then(Measure())
    )
    noise = PulseEnergyNoiseModel(
        channels=("rydberg",),
        energy_covariance=((0.02**2,),),
    )
    first = StochasticExperimentRuntime(
        QutipReducedBackend(config), noise, seed=20260729
    ).execute(program, shots=32)
    second = StochasticExperimentRuntime(
        QutipReducedBackend(config), noise, seed=20260729
    ).execute(program, shots=32)
    assert first == second

    forbidden = (
        "seed",
        "context",
        "velocity",
        "position",
        "noise",
        "state",
        "fidelity",
        "gradient",
        "hessian",
    )
    visible = " ".join(
        (
            repr(first),
            " ".join(first.__dataclass_fields__),
            " ".join(first.metadata),
        )
    ).lower()
    assert all(word not in visible for word in forbidden)
