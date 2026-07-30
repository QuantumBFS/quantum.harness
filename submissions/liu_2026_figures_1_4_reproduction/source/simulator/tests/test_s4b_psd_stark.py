"""S4-B tests for measured cross-PSD and scalar Stark-field sources."""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.signal import periodogram

from cs_tweezer_sim import (
    OneSidedCrossSpectralDensity,
    PolynomialLevelShiftSpec,
    ScalarFieldNoiseModel,
    SpectralLaserFrequencyNoiseModel,
    StochasticScopeEngine,
    arc_dc_polarizability_to_quadratic_shift_rad_per_us_per_vpcm2,
    cs_69s_dc_stark_level_shift_spec,
)


def _spectral_engine(model, seed: int) -> StochasticScopeEngine:
    engine = StochasticScopeEngine(model.blocks(1), seed=seed)
    engine.begin_iteration()
    engine.begin_shot()
    return engine


def test_cross_psd_rejects_nonhermitian_or_nonpositive_matrices() -> None:
    with pytest.raises(ValueError, match="Hermitian"):
        OneSidedCrossSpectralDensity(
            ("a", "b"),
            (0.0, 1.0),
            (
                ((1.0, 0.5j), (0.5j, 1.0)),
                ((1.0, 0.5j), (0.5j, 1.0)),
            ),
        )
    with pytest.raises(ValueError, match="positive semidefinite"):
        OneSidedCrossSpectralDensity(
            ("a", "b"),
            (0.0, 1.0),
            (
                ((1.0, 2.0), (2.0, 1.0)),
                ((1.0, 2.0), (2.0, 1.0)),
            ),
        )


def test_flat_cross_psd_reconstructs_power_and_correlation() -> None:
    target_psd = 10.0
    target_correlation = 0.6
    spectrum = OneSidedCrossSpectralDensity(
        ("blue", "infrared"),
        (0.0, 500_000.0),
        (
            (
                (target_psd, target_correlation * target_psd),
                (target_correlation * target_psd, target_psd),
            ),
            (
                (target_psd, target_correlation * target_psd),
                (target_correlation * target_psd, target_psd),
            ),
        ),
    )
    model = SpectralLaserFrequencyNoiseModel(spectrum, 1.0)
    psd_values = []
    variances = []
    correlations = []
    for seed in range(80):
        realization = model.realization(
            _spectral_engine(model, seed),
            1,
            2048.0,
        )
        blue = np.asarray(
            realization.frequency_traces_hz["blue"].values[:-1]
        )
        infrared = np.asarray(
            realization.frequency_traces_hz["infrared"].values[:-1]
        )
        _, estimated = periodogram(
            blue,
            fs=1e6,
            window="boxcar",
            detrend=False,
            scaling="density",
        )
        psd_values.append(float(np.mean(estimated[1:-1])))
        variances.append(float(np.var(blue)))
        correlations.append(float(np.corrcoef(blue, infrared)[0, 1]))

    expected_variance = target_psd * 500_000.0
    assert abs(np.mean(psd_values) / target_psd - 1.0) < 0.05
    assert abs(np.mean(variances) / expected_variance - 1.0) < 0.05
    assert abs(np.mean(correlations) - target_correlation) < 0.05
    assert spectrum.integrated_auto_variances_hz2() == (
        expected_variance,
        expected_variance,
    )


def test_spectral_frequency_integrates_to_phase_and_repeats_by_seed() -> None:
    spectrum = OneSidedCrossSpectralDensity(
        ("drive",),
        (0.0, 500_000.0),
        (((4.0,),), ((4.0,),)),
    )
    model = SpectralLaserFrequencyNoiseModel(spectrum, 1.0)
    first = model.realization(_spectral_engine(model, 91), 2, 128.0)
    second = model.realization(_spectral_engine(model, 91), 2, 128.0)
    frequency = np.asarray(
        first.frequency_traces_hz["drive"].values[:-1]
    )
    phase = np.asarray(first.phase_traces_rad["drive"].values)
    reconstructed = np.diff(phase) / (2.0 * math.pi * 1e-6)

    assert np.max(np.abs(reconstructed - frequency)) < 1e-9
    assert (
        first.phase_traces_rad["drive"].values
        == second.phase_traces_rad["drive"].values
    )
    assert (
        first.context.channel_phase_offset_traces_rad[("drive", 0)][0]
        is first.context.channel_phase_offset_traces_rad[("drive", 1)][0]
    )


def test_scalar_field_maps_bias_cross_term_and_scopes() -> None:
    shift = PolynomialLevelShiftSpec(
        "r",
        linear_rad_per_us_per_field=2.0,
        quadratic_rad_per_us_per_field2=3.0,
    )
    model = ScalarFieldNoiseModel(
        field_name="dc_electric_field",
        field_unit="V/cm",
        bias_field=0.4,
        level_shifts=(shift,),
        iteration_common_sigma=0.01,
        shot_common_sigma=0.02,
        shot_local_sigma=0.005,
        within_shot_common_sigma=0.003,
        within_shot_local_sigma=0.002,
        within_shot_correlation_time_us=0.2,
        sample_interval_us=0.01,
        block_prefix="test_dc_stark",
    )
    engine = StochasticScopeEngine(model.blocks(2), seed=44)
    engine.begin_iteration()
    iteration = engine.sample("test_dc_stark_iteration_common")["common"]
    engine.begin_shot()
    first = model.realization(engine, 2, 0.5)
    same_iteration = engine.sample("test_dc_stark_iteration_common")["common"]
    engine.begin_shot()
    second = model.realization(engine, 2, 0.5)
    engine.begin_iteration()
    engine.begin_shot()
    next_iteration = engine.sample("test_dc_stark_iteration_common")["common"]

    assert iteration == same_iteration
    assert iteration != next_iteration
    assert first.base_fields != second.base_fields
    assert np.std(first.field_traces[0].values) > 0
    base = first.base_fields[0]
    energy_trace = first.context.level_energy_offset_traces_rad_per_us[
        (0, "r")
    ][0]
    for field, offset in zip(
        first.field_traces[0].values,
        energy_trace.values,
    ):
        expected = shift.energy_rad_per_us(field) - shift.energy_rad_per_us(base)
        assert abs(offset - expected) < 1e-12


def test_arc_dc_polarizability_unit_conversion() -> None:
    alpha_mhz_cm2_per_v2 = -12.5
    coefficient = (
        arc_dc_polarizability_to_quadratic_shift_rad_per_us_per_vpcm2(
            alpha_mhz_cm2_per_v2
        )
    )
    field_v_per_cm = 0.03
    angular_shift = coefficient * field_v_per_cm**2
    expected = (
        -2.0
        * math.pi
        * 0.5
        * alpha_mhz_cm2_per_v2
        * field_v_per_cm**2
    )

    assert abs(angular_shift - expected) < 1e-12
    cs_spec = cs_69s_dc_stark_level_shift_spec()
    assert cs_spec.level == "r"
    assert cs_spec.quadratic_rad_per_us_per_field2 < 0
