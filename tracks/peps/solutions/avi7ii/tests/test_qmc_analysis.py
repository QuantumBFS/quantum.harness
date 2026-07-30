import numpy as np
import pytest

from qh147.qmc_analysis import (
    analyze_trotter_point,
    bootstrap_thermodynamics,
    integrate_free_energy,
    specific_heat_from_u,
    trotter_extrapolate,
)


def test_trotter_fit_recovers_zero_step_limit():
    beta = 0.8
    m = np.array([32, 64, 128])
    u = -1.25 + 3.0 * (beta / m) ** 2
    fit = trotter_extrapolate(beta, m, u, np.full(3, 1e-4))

    assert np.isclose(fit.value, -1.25, atol=1e-10)
    assert np.isclose(fit.slope, 3.0, atol=1e-8)


def test_free_energy_uses_exact_beta_zero_anchor():
    beta = np.arange(0.0, 1.0001, 0.025)
    u = -2.0 * beta
    f = integrate_free_energy(beta, u)

    assert np.isnan(f[0])
    assert np.isclose(f[-1], -np.log(2.0) - 1.0, atol=1e-12)


def test_specific_heat_differentiates_a_polynomial_energy_curve():
    beta = np.arange(0.0, 1.0001, 0.025)
    u = -2.0 * beta + 0.5 * beta**2

    actual = specific_heat_from_u(beta, u)
    expected = -(beta**2) * (-2.0 + beta)

    assert np.allclose(actual, expected, atol=1e-11)


def _bins(values, *, spread=1e-3):
    offsets = np.linspace(-spread, spread, 32)
    return np.asarray([[value + offset for offset in offsets] for value in values])


def test_point_requires_three_m_values_four_chains_and_32_bins():
    beta = 0.8
    m = np.array([32, 64, 128])
    central = -1.25 + 3.0 * (beta / m) ** 2
    chain_bins = np.stack([_bins(np.repeat(value, 4)) for value in central])

    result = analyze_trotter_point(beta, m, chain_bins)

    assert result.status == "success"
    assert result.value == pytest.approx(-1.25, abs=1e-10)
    with pytest.raises(ValueError, match="four chains"):
        analyze_trotter_point(beta, m, chain_bins[:, :3])
    with pytest.raises(ValueError, match="32 bins"):
        analyze_trotter_point(beta, m, chain_bins[:, :, :31])


def test_curved_trotter_fixture_is_unconverged():
    beta = 0.8
    m = np.array([32, 64, 128])
    x = (beta / m) ** 2
    central = -1.25 + 3.0 * x + 2e6 * x**2
    chain_bins = np.stack([_bins(np.repeat(value, 4), spread=1e-6) for value in central])

    result = analyze_trotter_point(beta, m, chain_bins)

    assert result.status == "unconverged"
    assert result.reduced_chi2 >= 4.0


def test_bootstrap_propagates_through_u_f_and_c():
    beta = np.arange(0.0, 0.1501, 0.025)[1:]
    m = np.array([32, 64, 128])
    curves = []
    for point in beta:
        finite_m = -2.0 * point + 0.2 * (point / m) ** 2
        curves.append(
            np.stack([_bins(np.repeat(value, 4), spread=2e-3) for value in finite_m])
        )
    chain_bins = np.stack(curves)

    result = bootstrap_thermodynamics(
        beta, m, chain_bins, bootstrap_samples=64, seed=147
    )

    assert result.u.shape == beta.shape
    assert np.all(np.isfinite(result.u_error))
    assert np.all(np.isfinite(result.f))
    assert np.all(np.isfinite(result.c))
    assert set(result.status) == {"success"}
