from __future__ import annotations

import math

import numpy as np
import pytest

from challenge148.statistics import (
    _integrated_time_from_autocorrelation,
    agreement_z_score,
    integrated_autocorrelation_time,
    jackknife_binder,
    summarize_bin_records,
    summarize_chain,
)


def _ar1(seed: int, *, phi: float, count: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    innovations = rng.normal(scale=math.sqrt(1.0 - phi**2), size=count)
    values = np.empty(count)
    values[0] = innovations[0]
    for index in range(1, count):
        values[index] = phi * values[index - 1] + innovations[index]
    return values


def test_iid_iat_has_seeded_coverage_not_brittle_exact_equality():
    estimates = [
        integrated_autocorrelation_time(np.random.default_rng(seed).normal(size=16_384))
        for seed in range(8)
    ]
    assert 0.45 <= float(np.median(estimates)) <= 0.65
    assert max(estimates) < 0.9


def test_ar1_iat_has_seeded_coverage_around_analytic_value():
    phi = 0.8
    expected = 0.5 + phi / (1.0 - phi)
    estimates = [
        integrated_autocorrelation_time(_ar1(seed, phi=phi, count=65_536))
        for seed in range(6)
    ]
    assert abs(float(np.median(estimates)) - expected) / expected < 0.18
    assert all(0.65 * expected < estimate < 1.35 * expected for estimate in estimates)


def test_iat_documents_hybrid_positive_pairs_and_window_estimator():
    documentation = integrated_autocorrelation_time.__doc__
    assert documentation is not None
    normalized = " ".join(documentation.split())
    assert "actual Geyer IPS" in normalized
    assert "ρ(0)+ρ(1)" in normalized
    assert "self-consistent window" in normalized


def test_geyer_ips_pairs_begin_with_rho_zero_and_rho_one():
    rho = np.array([1.0, 0.2, -0.1, -0.2, 0.9])
    assert _integrated_time_from_autocorrelation(rho) == pytest.approx(0.7)
    old_lag_one_pairing = 0.5 + rho[1] + rho[2]
    assert old_lag_one_pairing == pytest.approx(0.6)


def test_geyer_ips_supports_negative_correlation_but_rejects_invalid_sequences():
    assert _integrated_time_from_autocorrelation(
        np.array([1.0, -0.25, -0.1, -0.1])
    ) == pytest.approx(0.25)
    with pytest.raises(ValueError):
        _integrated_time_from_autocorrelation(np.array([1.0]))
    with pytest.raises(ValueError):
        _integrated_time_from_autocorrelation(np.array([1.0, -1.0, 0.0]))


def test_known_chain_uses_rho_zero_pair_not_lag_one_pair():
    chain = np.array([0.0, 0.1, 0.2, 0.3, 1.0, 1.1, 1.2, 1.3])
    centered = chain - chain.mean()
    rho = np.correlate(centered, centered, mode="full")[len(chain) - 1 :]
    rho = rho / np.arange(len(chain), 0, -1)
    rho = rho / rho[0]
    expected = _integrated_time_from_autocorrelation(rho)
    assert integrated_autocorrelation_time(chain) == pytest.approx(expected)
    old = 0.5
    for lag in range(1, len(rho) - 1, 2):
        pair = rho[lag] + rho[lag + 1]
        if pair <= 0:
            break
        old += pair
        if lag + 1 >= 5 * old:
            break
    assert expected != pytest.approx(old)


@pytest.mark.parametrize(
    "samples",
    [
        np.ones(100),
        np.array([1.0, 2.0, np.nan]),
        np.arange(7, dtype=float),
        np.ones((8, 1)),
    ],
)
def test_iat_rejects_constant_nonfinite_short_and_non_1d_chains(samples):
    with pytest.raises(ValueError):
        integrated_autocorrelation_time(samples)


def test_chain_summary_uses_iat_effective_count_and_enforces_bin_length():
    samples = _ar1(148, phi=0.6, count=16_384)
    summary = summarize_chain(samples, bin_length=100)
    assert summary["effective_sample_count"] == pytest.approx(
        len(samples) / (2.0 * summary["tau_int"])
    )
    assert summary["standard_error"] == pytest.approx(
        samples.std(ddof=1) / math.sqrt(summary["effective_sample_count"])
    )
    with pytest.raises(ValueError, match="10"):
        summarize_chain(samples, bin_length=1)
    with pytest.raises(ValueError, match="25"):
        summarize_chain(samples, bin_length=25, minimum_bin_tau=25)


def test_half_and_independent_chain_agreement_use_combined_errors():
    assert agreement_z_score(1.0, 0.2, 1.3, 0.4) == pytest.approx(
        0.3 / math.hypot(0.2, 0.4)
    )
    with pytest.raises(ValueError):
        agreement_z_score(1.0, 0.0, 1.0, 0.0)


def test_binder_jackknife_uses_aggregate_m2_m4_and_covariance():
    m2 = np.array([0.20, 0.24, 0.18, 0.23, 0.21, 0.19, 0.22, 0.17])
    m4 = np.array([0.08, 0.10, 0.07, 0.095, 0.085, 0.075, 0.09, 0.065])
    result = jackknife_binder(m2, m4)
    direct = m2.mean() ** 2 / m4.mean()
    leave = ((m2.sum() - m2) / 7) ** 2 / ((m4.sum() - m4) / 7)
    expected_bias_corrected = np.mean(8 * direct - 7 * leave)
    assert result["raw_plugin_mean"] == pytest.approx(direct)
    assert result["mean"] == pytest.approx(expected_bias_corrected)
    assert result["mean"] != pytest.approx(direct, abs=1e-12)
    assert result["standard_error"] > 0.0


def test_bin_summary_estimates_tau_from_serial_retained_samples_not_bin_means():
    serial = {
        name: _ar1(seed, phi=0.8, count=1600)
        for seed, name in enumerate(("energy", "transverse_magnetization", "m2", "m4"), 40)
    }
    serial["m2"] = 0.5 + 0.05 * serial["m2"]
    serial["m4"] = 0.3 + 0.03 * serial["m4"]
    records = []
    for index in range(16):
        start, stop = index * 100, (index + 1) * 100
        observations = {
            name: values[start:stop].tolist() for name, values in serial.items()
        }
        records.append(
            {
                "bin_index": index,
                "sample_count": 100,
                "serial_measurement_stride_samples": 1,
                "serial_observations": observations,
                **{
                    f"{name}_sum": float(np.sum(values[start:stop]))
                    for name, values in serial.items()
                },
            }
        )
    summary = summarize_bin_records(
        records,
        analysis_bin_length_samples=100,
        serial_measurement_stride_samples=1,
        minimum_analysis_bin_tau_ratio=10,
    )
    energy = summary["observables"]["energy"]
    assert energy["tau_int_samples"] > 2.0
    assert energy["analysis_bin_length_samples"] == 100
    assert energy["serial_measurement_stride_samples"] == 1
    assert energy["serial_sample_count"] == 1600
    assert "tau_int" not in energy
