from __future__ import annotations

import numpy as np
import pytest

from spinglass3d.equilibration import (
    EquilibrationRecord,
    EquilibrationThresholds,
    RoundTripTracker,
    assess_equilibration,
    completion_eligibility,
    log_bin_estimates,
    observable_iat_ess,
    split_rhat,
)


def _thresholds() -> EquilibrationThresholds:
    return EquilibrationThresholds(
        swap_bottleneck=0.15,
        swap_target_min=0.20,
        swap_target_max=0.50,
        min_round_trips=10,
        max_rhat=1.05,
        min_ess=200.0,
        bin_sigma=2.0,
        max_thermal_error_fraction=0.25,
        min_chains=4,
    )


def _stationary_record(
    *,
    j_id: str = "J-1",
    edge_acceptance: tuple[float, ...] = (0.28, 0.31, 0.29),
    drift: float = 0.0,
    repeat: int = 1,
    tmax_forgetting_passed: bool = True,
) -> EquilibrationRecord:
    rng = np.random.default_rng(2026072921)
    observables = {}
    for index, name in enumerate(
        ("energy", "q2", "q4", "chi0", "chik_x", "chik_y", "chik_z")
    ):
        values = rng.normal(loc=0.1 * index, scale=1.0, size=(4, 2400))
        values[3, 1200:] += drift
        if repeat > 1:
            values = np.repeat(values[:, :100], repeat, axis=1)
        observables[name] = values
    return EquilibrationRecord(
        j_id=j_id,
        edge_acceptance=edge_acceptance,
        round_trips=(12, 13, 14, 12),
        observables=observables,
        elapsed_seconds=4.0,
        thermal_error_fraction=0.1,
        extension_count=0,
        tmax_forgetting_passed=tmax_forgetting_passed,
    )


def test_round_trip_tracker_counts_low_high_low_cycles() -> None:
    tracker = RoundTripTracker(n_temperatures=4, n_replicas=2)
    for positions in (
        (0, 1),
        (1, 0),
        (3, 2),
        (2, 3),
        (0, 2),
        (1, 0),
    ):
        tracker.update(np.asarray(positions))
    assert tracker.round_trips == (1, 1)
    assert all(value >= 0 for value in tracker.time_since_endpoint)


def test_synthetic_stationary_record_passes() -> None:
    report = assess_equilibration(_stationary_record(), _thresholds())
    assert report.passed is True
    assert report.failed_gates == ()
    assert report.disorder_count == 1
    assert report.components["thermal_error_fraction"] == pytest.approx(0.1)


def test_swap_bottleneck_fails() -> None:
    report = assess_equilibration(
        _stationary_record(edge_acceptance=(0.3, 0.08, 0.31)),
        _thresholds(),
    )
    assert report.passed is False
    assert "swap_bottleneck" in report.failed_gates


def test_drift_and_low_effective_sample_size_fail() -> None:
    drifted = assess_equilibration(_stationary_record(drift=1.0), _thresholds())
    assert any("rhat" in gate or "half" in gate for gate in drifted.failed_gates)
    repeated = assess_equilibration(_stationary_record(repeat=20), _thresholds())
    assert any("ess" in gate for gate in repeated.failed_gates)


def test_measurement_duplication_does_not_change_disorder_count() -> None:
    base = assess_equilibration(_stationary_record(), _thresholds())
    repeated = assess_equilibration(_stationary_record(repeat=20), _thresholds())
    assert base.disorder_count == repeated.disorder_count == 1


def test_split_rhat_log_bins_and_iat_are_explicit() -> None:
    record = _stationary_record()
    chains = record.observables["energy"]
    assert split_rhat(chains) < 1.05
    bins = log_bin_estimates(chains.ravel())
    assert len(bins) >= 3
    assert all(bin_.block_size > 0 and bin_.block_count >= 2 for bin_ in bins)
    summary = observable_iat_ess(chains[0], elapsed_seconds=1.0)
    assert summary["ess"] > 200
    assert summary["window_rule"]


def test_log_bins_are_doubling_run_lengths_not_reblocking_the_full_series() -> None:
    values = np.concatenate((np.zeros(1024), np.ones(1024)))
    bins = log_bin_estimates(values)
    assert bins[-2].block_size == 1024
    assert bins[-2].mean == pytest.approx(0.0, abs=0.0, rel=0.0)
    assert bins[-1].block_size == 2048
    assert bins[-1].mean == pytest.approx(0.5, abs=0.0, rel=0.0)


def test_log_bins_include_the_complete_non_power_of_two_history() -> None:
    values = np.concatenate((np.zeros(2048), np.ones(952)))
    bins = log_bin_estimates(values)
    assert bins[-1].block_size == 3000
    assert bins[-1].mean == pytest.approx(952.0 / 3000.0, abs=0.0, rel=0.0)


def test_tmax_memory_failure_is_explicit_and_extension_count_is_preserved() -> None:
    record = _stationary_record(tmax_forgetting_passed=False)
    report = assess_equilibration(record, _thresholds())
    assert "tmax_forgetting" in report.failed_gates
    assert report.components["extension_count"] == 0


def test_completion_policy_never_substitutes_j_ids() -> None:
    thresholds = _thresholds()
    reports = [
        assess_equilibration(_stationary_record(j_id=f"J-{index}"), thresholds)
        for index in range(20)
    ]
    reports[-1] = reports[-1].with_failure("forced_test_failure")
    eligibility = completion_eligibility(
        reports,
        preregistered_ids=tuple(f"J-{index}" for index in range(20)),
        hardness={f"J-{index}": float(index) for index in range(20)},
    )
    assert eligibility.completion_fraction == pytest.approx(0.95, rel=0.0)
    assert eligibility.eligible is True
    with pytest.raises(ValueError, match="preregistered"):
        completion_eligibility(
            reports + [assess_equilibration(_stationary_record(j_id="replacement"), thresholds)],
            preregistered_ids=tuple(f"J-{index}" for index in range(20)),
            hardness={},
        )
    with pytest.raises(ValueError, match="hardness"):
        completion_eligibility(
            reports,
            preregistered_ids=tuple(f"J-{index}" for index in range(20)),
            hardness={"J-0": 0.0},
        )
    with pytest.raises(ValueError, match="minimum fraction"):
        completion_eligibility(
            reports,
            preregistered_ids=tuple(f"J-{index}" for index in range(20)),
            hardness={f"J-{index}": float(index) for index in range(20)},
            minimum_fraction=1.1,
        )
