import numpy as np
import pytest

from ceffflow.clean_ising import (
    critical_ground_energy,
    fit_clean_ising,
)
from ceffflow.fits import (
    casimir_gls,
    covariance_weighted_casimir_samples,
    monotonicity_test,
)


def test_clean_ising_exact_formula_requires_even_lengths():
    with pytest.raises(ValueError, match="even"):
        critical_ground_energy([4, 5, 6])


def test_clean_ising_recovers_half():
    lengths = np.arange(8, 42, 2)
    fit = fit_clean_ising(lengths, velocity=2.0)
    assert abs(fit.central_charge - 0.5) < 2e-5


def test_gls_recovers_injected_casimir_with_l3_term():
    lengths = np.array([6, 8, 10, 12, 14, 16], dtype=float)
    values = (
        -1.7 * lengths
        - np.pi * 0.447 / (6 * lengths)
        + 0.3 / lengths**3
    )
    covariance = np.eye(lengths.size) * 1e-10
    fit = casimir_gls(
        lengths,
        values,
        covariance,
        alpha=1.0,
        include_l3=True,
    )
    assert abs(fit.central_charge - 0.447) < 1e-6
    assert fit.dof == 3
    assert len(fit.leave_one_out) == lengths.size


def test_covariance_weighted_block_samples_reproduce_gls():
    rng = np.random.default_rng(122)
    lengths = np.asarray([6, 8, 10, 12, 14, 16], dtype=float)
    curve = -1.2 * lengths - np.pi * 0.447 / (6 * lengths) + 0.3 / lengths**3
    mixing = np.asarray(
        [
            [2.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.7, 1.0, 0.0, 0.0, 0.0, 0.0],
            [0.3, 0.2, 1.5, 0.0, 0.0, 0.0],
            [0.2, 0.1, 0.4, 0.8, 0.0, 0.0],
            [0.1, 0.3, 0.2, 0.1, 1.2, 0.0],
            [0.2, 0.1, 0.0, 0.2, 0.4, 0.7],
        ]
    )
    blocks = curve + 1e-4 * (rng.normal(size=(80, 6)) @ mixing.T)
    covariance_of_mean = np.cov(blocks, rowvar=False, ddof=1) / blocks.shape[0]
    expected = casimir_gls(
        lengths,
        blocks.mean(axis=0),
        covariance_of_mean,
        alpha=1.0,
        include_l3=True,
        compute_leave_one_out=False,
    )
    samples = covariance_weighted_casimir_samples(lengths, blocks)
    assert np.isclose(samples.mean(), expected.central_charge, atol=1e-12)
    assert np.isclose(
        samples.std(ddof=1) / np.sqrt(samples.size),
        expected.standard_error,
        atol=1e-12,
    )


def test_casimir_fit_rejects_nonpositive_anisotropy():
    lengths = np.array([4, 6, 8, 10], dtype=float)
    with pytest.raises(ValueError, match="alpha"):
        casimir_gls(
            lengths,
            -lengths,
            np.eye(lengths.size),
            alpha=0.0,
        )


def test_casimir_fit_rejects_singular_covariance():
    lengths = np.array([4, 6, 8, 10], dtype=float)
    covariance = np.ones((4, 4))
    with pytest.raises(ValueError, match="positive definite"):
        casimir_gls(lengths, -lengths, covariance, alpha=1.0)


def test_monotonicity_test_accepts_a_decreasing_curve():
    result = monotonicity_test(
        [0.5, 0.4, 0.3],
        np.eye(3) * 0.01,
        bootstrap_draws=100,
        seed=2,
    )
    assert result.statistic < 1e-10
    assert result.bootstrap_p_value > 0.5


def test_monotonicity_test_detects_a_precise_reversal():
    result = monotonicity_test(
        [0.5, 0.8, 0.3],
        np.eye(3) * 1e-4,
        bootstrap_draws=200,
        seed=3,
    )
    assert result.statistic > 100.0
    assert result.bootstrap_p_value < 0.02


def test_monotonicity_test_keeps_a_nearly_exact_endpoint_weight():
    result = monotonicity_test(
        [0.4, -0.52, -0.5],
        np.diag([0.1**2, 0.04**2, 1e-10**2]),
        bootstrap_draws=100,
        seed=4,
    )
    assert np.isclose(result.constrained_curve[-1], -0.5, atol=1e-9)
    assert np.isclose(result.constrained_curve[-2], -0.5, atol=1e-7)
    assert np.isclose(result.statistic, 0.25, rtol=1e-5)
