from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
import math

import numpy as np
import pytest

from spinglass3d.statistics import (
    BootstrapCrossingResult,
    FSSVariant,
    NonlinearBounds,
    RecordIdentity,
    DisorderSeries,
    bootstrap_pair_crossings,
    bootstrap_fss,
    bootstrap_success_adequate,
    fit_dimensionless_fss,
    pair_crossings,
    resample_disorder,
    select_headline_variant,
)


def _series(
    j_id: str,
    length: int,
    temperatures: Sequence[float],
    xi_over_l: Sequence[float],
    *,
    binder: Sequence[float] | None = None,
    source_hash: str = "a" * 64,
) -> DisorderSeries:
    xi = np.asarray(xi_over_l, dtype=np.float64)
    return DisorderSeries(
        j_id=j_id,
        length=length,
        temperatures=np.asarray(temperatures, dtype=np.float64),
        observables={
            "xi_over_l": xi,
            "binder": xi + 0.25 if binder is None else np.asarray(binder),
        },
        source_hash=source_hash,
    )


def test_disorder_series_owns_immutable_complete_temperature_record() -> None:
    temperatures = np.array([0.9, 1.0, 1.1])
    values = np.array([0.2, 0.3, 0.4])
    record = _series("J-7", 9, temperatures, values)
    temperatures[0] = 7.0
    values[0] = 8.0
    np.testing.assert_array_equal(record.temperatures, [0.9, 1.0, 1.1])
    np.testing.assert_array_equal(record.observables["xi_over_l"], [0.2, 0.3, 0.4])
    with pytest.raises(ValueError):
        record.temperatures[0] = 1.5
    with pytest.raises(ValueError):
        record.observables["xi_over_l"][0] = 1.5
    with pytest.raises(TypeError):
        record.observables["new"] = np.ones(3)


def test_resample_disorder_resamples_whole_j_records() -> None:
    records = tuple(
        _series(
            f"J-{index}",
            9,
            [0.9, 1.0, 1.1],
            [index, index + 10.0, index - 3.0],
        )
        for index in range(12)
    )
    sample = resample_disorder(records, np.array([1, 1, 5, 9]))
    assert sample[0] is sample[1] is records[1]
    assert sample[0].j_id == sample[1].j_id == records[1].j_id
    np.testing.assert_array_equal(sample[0].temperatures, records[1].temperatures)
    np.testing.assert_array_equal(
        sample[0].observables["xi_over_l"],
        records[1].observables["xi_over_l"],
    )
    with pytest.raises(ValueError, match="integer"):
        resample_disorder(records, np.array([0.0, 1.0]))
    with pytest.raises(IndexError, match="range"):
        resample_disorder(records, np.array([12]))


def test_pair_crossings_keep_all_roots_inside_common_support_and_failures() -> None:
    records = (
        _series("L6-J0", 6, [0.8, 0.9, 1.0, 1.1, 1.2], [0, 2, 0, 2, 0]),
        _series("L6-J1", 6, [0.8, 0.9, 1.0, 1.1, 1.2], [0, 2, 0, 2, 0]),
        _series("L9-J0", 9, [0.85, 0.9, 1.0, 1.1, 1.15], [1, 1, 1, 1, 1]),
        _series("L9-J1", 9, [0.85, 0.9, 1.0, 1.1, 1.15], [1, 1, 1, 1, 1]),
        _series("L12-J0", 12, [1.3, 1.4], [0.5, 0.6]),
        _series("L12-J1", 12, [1.3, 1.4], [0.5, 0.6]),
    )
    results = pair_crossings(records, observable="xi_over_l")
    assert tuple(result.sizes for result in results) == ((6, 9), (6, 12), (9, 12))
    crossing = results[0]
    assert crossing.failed is False
    assert crossing.common_temperature_window == (0.85, 1.15)
    np.testing.assert_allclose(
        crossing.temperatures,
        [0.85, 0.95, 1.05, 1.15],
        atol=2e-15,
        rtol=0.0,
    )
    for failure in results[1:]:
        assert failure.failed is True
        assert failure.temperatures == ()
        assert "common temperature" in failure.reason


def test_statistics_inputs_fail_closed_on_bad_or_incomplete_temperature_data() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        _series("duplicate-T", 9, [0.9, 1.0, 1.0], [0.2, 0.3, 0.4])
    with pytest.raises(ValueError, match="finite"):
        _series("nonfinite", 9, [0.9, 1.0, 1.1], [0.2, np.nan, 0.4])

    records = (
        _series("L6-J0", 6, [0.9, 1.0, 1.1], [0.2, 0.3, 0.4]),
        _series("L6-J1", 6, [0.9, 1.1], [0.2, 0.4]),
        _series("L9-J0", 9, [0.9, 1.0, 1.1], [0.3, 0.4, 0.5]),
        _series("L9-J1", 9, [0.9, 1.0, 1.1], [0.3, 0.4, 0.5]),
    )
    with pytest.raises(ValueError, match="temperature grid"):
        pair_crossings(records, observable="xi_over_l")

    duplicate_j = (
        _series("same", 6, [0.9, 1.0], [0.2, 0.3]),
        _series("same", 6, [0.9, 1.0], [0.3, 0.4]),
        _series("L9-J0", 9, [0.9, 1.0], [0.4, 0.5]),
        _series("L9-J1", 9, [0.9, 1.0], [0.5, 0.6]),
    )
    with pytest.raises(ValueError, match="duplicate"):
        pair_crossings(duplicate_j, observable="xi_over_l")


def _bootstrap_fixture(
    *,
    tc: float = 1.11,
    nu: float = 2.45,
    omega: float = 1.0,
    seed: int = 71,
    sizes: tuple[int, ...] = (6, 9, 12, 15, 18, 24),
    disorder_samples: int = 18,
    temperatures: np.ndarray | None = None,
) -> tuple[DisorderSeries, ...]:
    rng = np.random.default_rng(seed)
    grid = (
        np.linspace(1.0, 1.2, 9, dtype=np.float64)
        if temperatures is None
        else np.asarray(temperatures, dtype=np.float64)
    )
    records: list[DisorderSeries] = []
    source_index = 1
    for length in sizes:
        x = (grid - tc) * length ** (1.0 / nu)
        parity = 1.0 if length % 2 == 0 else -1.0
        correction = length ** (-omega)
        xi_mean = (
            0.61
            + 0.23 * x
            - 0.035 * x**2
            + 0.009 * x**3
            + correction * (0.32 - 0.07 * x)
            + parity * correction * 0.025
        )
        binder_mean = (
            0.47
            + 0.17 * x
            + 0.021 * x**2
            - 0.006 * x**3
            + correction * (-0.24 + 0.05 * x)
            - parity * correction * 0.018
        )
        shared = rng.normal(0.0, 0.006, size=(disorder_samples, 1))
        slopes = rng.normal(0.0, 0.002, size=(disorder_samples, 1))
        smooth_noise = shared + slopes * x[None, :]
        xi_noise = smooth_noise + rng.normal(
            0.0,
            0.0015,
            size=(disorder_samples, grid.size),
        )
        binder_noise = 0.7 * smooth_noise + rng.normal(
            0.0,
            0.0015,
            size=(disorder_samples, grid.size),
        )
        xi_noise -= np.mean(xi_noise, axis=0, keepdims=True)
        binder_noise -= np.mean(binder_noise, axis=0, keepdims=True)
        for sample in range(disorder_samples):
            xi = xi_mean + xi_noise[sample]
            binder = binder_mean + binder_noise[sample]
            records.append(
                _series(
                    f"L{length}-J{sample}",
                    length,
                    grid,
                    xi,
                    binder=binder,
                    source_hash=f"{source_index:064x}",
                )
            )
            source_index += 1
    return tuple(records)


def test_corrected_fss_recovers_synthetic_tc_and_records_diagnostics() -> None:
    data = _correlated_nonself_fss()
    fit = fit_dimensionless_fss(
        data,
        observable="xi_over_l",
        l_min=9,
        temperature_window=(1.0, 1.2),
        polynomial_order=3,
        parity=True,
        parity_order=1,
    )
    assert fit.tc == pytest.approx(1.11, abs=0.025)
    assert fit.nu == pytest.approx(2.3, abs=0.45)
    assert fit.omega == pytest.approx(0.9, abs=0.45)
    assert fit.omega_p == pytest.approx(1.45, abs=0.7)
    assert fit.success is True
    assert fit.l_min == 9
    assert fit.temperature_window == (1.0, 1.2)
    assert fit.parity_model == "p(L)*L^-omega_p*Fp_order_1(x)"
    assert fit.polynomial_order == 3
    assert fit.dof > 0
    assert 0.1 < fit.whitened_rss_per_dof < 2.0
    assert fit.residual_diagnostic == "regularized_covariance_whitened_rss"
    assert fit.covariance_diagnostic == "gauss_newton_working_covariance"
    assert fit.multistart_attempts >= 4
    assert fit.multistart_successes >= 1
    assert fit.covariance.ndim == 2
    assert fit.covariance.shape[0] == fit.covariance.shape[1]
    assert tuple(fit.coefficients) == ("xi_over_l",)
    assert fit.failed_resamples == ()
    assert len(fit.selected_records) < len(data)
    assert {identity.length for identity in fit.excluded_records} == {6}


def test_noisy_nonself_bootstrap_has_bounded_bias_and_repeated_coverage() -> None:
    generating_values = {
        "tc": 1.11,
        "nu": 2.3,
        "omega": 0.9,
        "omega_p": 1.45,
    }
    coverage = {name: 0 for name in generating_values}
    medians = {name: [] for name in generating_values}
    for offset, data_seed in enumerate(range(2026073226, 2026073230)):
        result = bootstrap_fss(
            _correlated_nonself_fss(seed=data_seed),
            "xi_over_l",
            variants=(FSSVariant(9, (1.0, 1.2), 3, True, parity_order=1),),
            n_resamples=8,
            seed=2307 + offset,
            minimum_success_count=4,
            minimum_success_fraction=0.5,
        )
        assert result.bootstrap_success_counts[0] >= result.required_success_count
        for name, expected in generating_values.items():
            interval = result.statistical_intervals[name]
            coverage[name] += int(interval.lower < expected < interval.upper)
            medians[name].append(interval.median)

    assert all(count >= 3 for count in coverage.values())
    bias_tolerances = {"tc": 0.02, "nu": 0.15, "omega": 0.25, "omega_p": 0.3}
    for name, expected in generating_values.items():
        assert float(np.mean(medians[name])) == pytest.approx(
            expected,
            abs=bias_tolerances[name],
        )


def test_joint_fss_shares_critical_parameters_but_keeps_coefficients_separate() -> None:
    data = _bootstrap_fixture(disorder_samples=12)
    fit = fit_dimensionless_fss(
        data,
        observable=("xi_over_l", "binder"),
        l_min=9,
        temperature_window=(1.0, 1.2),
        polynomial_order=2,
        parity=True,
        fixed_omega=1.0,
    )
    assert fit.tc == pytest.approx(1.11, abs=0.02)
    assert fit.observable_names == ("xi_over_l", "binder")
    assert tuple(fit.coefficients) == ("xi_over_l", "binder")
    assert fit.omega_treatment == "fixed"


def test_fss_refuses_two_size_claims_and_duplicate_records() -> None:
    two_sizes = _bootstrap_fixture(sizes=(9, 12), disorder_samples=8)
    with pytest.raises(ValueError, match="at least three"):
        fit_dimensionless_fss(
            two_sizes,
            observable="xi_over_l",
            l_min=9,
            temperature_window=(1.0, 1.2),
            polynomial_order=2,
            parity=True,
        )
    duplicate = _bootstrap_fixture(sizes=(9, 12, 15), disorder_samples=8)
    with pytest.raises(ValueError, match="duplicate"):
        fit_dimensionless_fss(
            duplicate + (duplicate[0],),
            observable="xi_over_l",
            l_min=9,
            temperature_window=(1.0, 1.2),
            polynomial_order=2,
            parity=True,
        )


def test_bootstrap_saves_whole_j_indices_failures_and_separate_uncertainties() -> None:
    data = _bootstrap_fixture(
        sizes=(9, 12, 15, 18),
        disorder_samples=2,
        temperatures=np.linspace(1.02, 1.2, 7),
    )
    variants = (
        FSSVariant(9, (1.02, 1.2), 2, True, fixed_omega=1.0),
        FSSVariant(15, (1.04, 1.18), 2, True, fixed_omega=1.0),
    )
    result = bootstrap_fss(
        data,
        observable="xi_over_l",
        variants=variants,
        n_resamples=96,
        seed=991,
        minimum_success_count=2,
        minimum_success_fraction=0.02,
    )
    assert result.seed == 991
    assert tuple(result.resample_indices) == (9, 12, 15, 18)
    assert all(indices.shape == (96, 2) for indices in result.resample_indices.values())
    assert all(not indices.flags.writeable for indices in result.resample_indices.values())
    assert result.failed_resamples
    failed_indices = tuple(
        failure.resample_index
        for failure in result.failed_resamples
        if failure.variant_index == 0
    )
    assert result.fit.failed_resamples == failed_indices
    statistical = result.statistical_intervals["tc"]
    assert statistical.lower <= statistical.median <= statistical.upper
    assert tuple(result.bootstrap_intervals_by_variant) == (0,)
    assert result.bootstrap_intervals_by_variant[0]["tc"] == statistical
    assert set(result.bootstrap_success_counts) == {0, 1}
    assert result.bootstrap_success_counts[0] >= result.required_success_count
    assert result.bootstrap_success_counts[1] == 0
    assert any(failure.variant_index == 1 for failure in result.failed_resamples)
    systematic = result.finite_size_systematic["tc"]
    assert systematic.minimum <= systematic.maximum
    assert systematic.half_range == pytest.approx(
        0.5 * (systematic.maximum - systematic.minimum),
        abs=0.0,
        rel=0.0,
    )
    assert result.statistical_intervals is not result.finite_size_systematic
    assert result.declared_variants == variants
    assert {fit.temperature_window for fit in result.variant_fits} == {(1.02, 1.2)}
    assert any(
        failure.variant_index == 1 and "at least three" in failure.reason
        for failure in result.variant_failures
    )


def _correlated_nonself_fss(
    *,
    tc: float = 1.11,
    nu: float = 2.3,
    omega: float = 0.9,
    omega_p: float = 1.45,
    seed: int = 2026073226,
) -> tuple[DisorderSeries, ...]:
    rng = np.random.default_rng(seed)
    grid = np.linspace(1.0, 1.2, 13, dtype=np.float64)
    records: list[DisorderSeries] = []
    source_index = 20_000
    for length in (6, 9, 12, 15, 18, 21, 24, 27, 30):
        x = (grid - tc) * length ** (1.0 / nu)
        parity = 1.0 if length % 2 == 0 else -1.0
        mean = (
            0.61
            + 0.21 * np.tanh(x)
            + 0.018 * x**2
            + length ** (-omega) * (0.31 - 0.065 * x + 0.012 * x**2)
            + parity * length ** (-omega_p) * (0.08 - 0.018 * x)
            + 0.0025 * x**4
        )
        for sample in range(40):
            common, slope, curvature = rng.normal(
                0.0,
                (0.0045, 0.0018, 0.0007),
            )
            correlated = common + slope * x + curvature * (x**2 - np.mean(x**2))
            noise = correlated + rng.normal(0.0, 0.0012, size=grid.size)
            records.append(
                _series(
                    f"L{length}-J{sample}",
                    length,
                    grid,
                    mean + noise,
                    source_hash=f"{source_index:064x}",
                )
            )
            source_index += 1
    return tuple(records)


def test_bootstrap_crossings_keep_every_resample_root_and_failure() -> None:
    records = (
        _series("L6-J0", 6, [0.9, 1.0, 1.1], [0.1, 0.5, 0.9], source_hash="1" * 64),
        _series("L6-J1", 6, [0.9, 1.0, 1.1], [0.2, 0.4, 1.0], source_hash="2" * 64),
        _series("L9-J0", 9, [0.9, 1.0, 1.1], [0.8, 0.5, 0.2], source_hash="3" * 64),
        _series("L9-J1", 9, [0.9, 1.0, 1.1], [0.9, 0.6, 0.1], source_hash="4" * 64),
    )
    matrices = {
        6: np.array([[0, 0], [1, 1], [0, 1]], dtype=np.int64),
        9: np.array([[0, 0], [1, 1], [0, 1]], dtype=np.int64),
    }
    axes = {
        6: (
            RecordIdentity(6, "L6-J0", "1" * 64),
            RecordIdentity(6, "L6-J1", "2" * 64),
        ),
        9: (
            RecordIdentity(9, "L9-J0", "3" * 64),
            RecordIdentity(9, "L9-J1", "4" * 64),
        ),
    }
    result = bootstrap_pair_crossings(
        records,
        "xi_over_l",
        n_resamples=3,
        seed=7,
        resample_indices=matrices,
        record_axes=axes,
    )
    assert isinstance(result, BootstrapCrossingResult)
    assert tuple(result.samples_by_pair) == ((6, 9),)
    samples = result.samples_by_pair[(6, 9)]
    assert tuple(sample.resample_index for sample in samples) == (0, 1, 2)
    assert all(sample.temperatures or sample.failed for sample in samples)
    assert result.record_axes[6] == (
        RecordIdentity(6, "L6-J0", "1" * 64),
        RecordIdentity(6, "L6-J1", "2" * 64),
    )
    assert result.resample_mode == "supplied_replay"


def test_bootstrap_indices_are_axis_bound_and_exactly_replayable() -> None:
    data = _bootstrap_fixture(
        sizes=(8, 12, 16, 20),
        disorder_samples=4,
        temperatures=np.linspace(1.02, 1.2, 7),
    )
    variant = FSSVariant(8, (1.02, 1.2), 3, False, fixed_omega=1.0)
    first = bootstrap_fss(
        data,
        "xi_over_l",
        variants=(variant,),
        n_resamples=8,
        seed=44,
        minimum_success_count=2,
        minimum_success_fraction=0.25,
    )
    replay = bootstrap_fss(
        tuple(reversed(data)),
        "xi_over_l",
        variants=(variant,),
        n_resamples=8,
        seed=first.seed,
        resample_indices=first.resample_indices,
        record_axes=first.record_axes,
        minimum_success_count=2,
        minimum_success_fraction=0.25,
    )
    assert replay.fit.tc == pytest.approx(first.fit.tc, abs=2e-12, rel=0.0)
    assert first.resample_mode == "generated_from_seed"
    assert replay.resample_mode == "supplied_replay"
    assert replay.seed == first.seed
    assert replay.statistical_intervals == first.statistical_intervals
    assert replay.bootstrap_intervals_by_variant == first.bootstrap_intervals_by_variant
    assert replay.bootstrap_success_counts == first.bootstrap_success_counts
    assert replay.failed_resamples == first.failed_resamples
    for length in first.resample_indices:
        np.testing.assert_array_equal(
            replay.resample_indices[length],
            first.resample_indices[length],
        )


def test_covariance_whitening_responds_to_temperature_correlations() -> None:
    base = _bootstrap_fixture(sizes=(9, 12, 15, 18), disorder_samples=10)
    transformed: list[DisorderSeries] = []
    for length in (9, 12, 15, 18):
        group = [record for record in base if record.length == length]
        matrix = np.asarray([record.observables["xi_over_l"] for record in group])
        mean = np.mean(matrix, axis=0)
        centered = matrix - mean
        signs = np.where(np.arange(centered.shape[1]) % 2 == 0, 1.0, -1.0)
        changed = mean + centered * signs[None, :]
        for index, record in enumerate(group):
            transformed.append(
                _series(
                    record.j_id,
                    record.length,
                    record.temperatures,
                    changed[index],
                    source_hash=record.source_hash,
                )
            )
    kwargs = dict(
        observable="xi_over_l",
        l_min=9,
        temperature_window=(1.0, 1.2),
        polynomial_order=2,
        parity=False,
        fixed_omega=1.0,
    )
    left = fit_dimensionless_fss(base, **kwargs)
    right = fit_dimensionless_fss(tuple(transformed), **kwargs)
    assert left.covariance_condition_max != pytest.approx(
        right.covariance_condition_max,
        rel=1e-4,
    )
    assert left.whitened_rss != pytest.approx(right.whitened_rss, rel=1e-4)


def test_parity_fit_rejects_single_parity_and_identifiability_failure() -> None:
    all_even = _bootstrap_fixture(sizes=(6, 12, 18, 24), disorder_samples=8)
    with pytest.raises(ValueError, match="both even and odd"):
        fit_dimensionless_fss(
            all_even,
            "xi_over_l",
            l_min=6,
            temperature_window=(1.0, 1.2),
            polynomial_order=2,
            parity=True,
        )


def test_near_singular_jacobian_is_rejected_before_covariance_inversion() -> None:
    temperatures = np.linspace(1.1095, 1.1105, 9)
    data = _bootstrap_fixture(
        sizes=(8, 12, 16, 20, 24, 28),
        disorder_samples=8,
        temperatures=temperatures,
    )
    with pytest.raises(RuntimeError, match="ill-conditioned"):
        fit_dimensionless_fss(
            data,
            "xi_over_l",
            l_min=8,
            temperature_window=(float(temperatures[0]), float(temperatures[-1])),
            polynomial_order=3,
            parity=False,
            fixed_omega=1.0,
        )
    sparse = _bootstrap_fixture(
        sizes=(9, 12, 15),
        disorder_samples=4,
        temperatures=np.array([1.08, 1.1, 1.12]),
    )
    with pytest.raises((ValueError, RuntimeError), match="rank|condition|degrees"):
        fit_dimensionless_fss(
            sparse,
            "xi_over_l",
            l_min=9,
            temperature_window=(1.08, 1.12),
            polynomial_order=3,
            parity=True,
            parity_order=2,
        )


def test_success_gate_and_bound_hit_primary_use_preregistered_fallback() -> None:
    assert bootstrap_success_adequate(800, 1000, minimum_count=200, minimum_fraction=0.8)
    assert not bootstrap_success_adequate(799, 1000, minimum_count=200, minimum_fraction=0.8)
    fit = fit_dimensionless_fss(
        _bootstrap_fixture(sizes=(9, 12, 15, 18), disorder_samples=8),
        "xi_over_l",
        l_min=9,
        temperature_window=(1.0, 1.2),
        polynomial_order=2,
        parity=False,
        fixed_omega=1.0,
    )
    central = {0: replace(fit, bound_hits=("tc",)), 1: fit}
    assert select_headline_variant(
        central,
        {0: 1000, 1: 850},
        n_resamples=1000,
        minimum_success_count=200,
        minimum_success_fraction=0.8,
    ) == 1
    with pytest.raises(RuntimeError, match="adequate"):
        select_headline_variant(
            central,
            {0: 1000, 1: 799},
            n_resamples=1000,
            minimum_success_count=200,
            minimum_success_fraction=0.8,
        )


def test_nonlinear_bounds_are_explicit_and_enforced() -> None:
    bounds = NonlinearBounds(
        tc=(1.05, 1.16),
        nu=(1.0, 4.0),
        omega=(0.2, 2.0),
        omega_p=(0.2, 2.5),
    )
    fit = fit_dimensionless_fss(
        _bootstrap_fixture(sizes=(9, 12, 15, 18), disorder_samples=8),
        "xi_over_l",
        l_min=9,
        temperature_window=(1.0, 1.2),
        polynomial_order=2,
        parity=False,
        fixed_omega=1.0,
        nonlinear_bounds=bounds,
    )
    assert bounds.tc[0] <= fit.tc <= bounds.tc[1]
