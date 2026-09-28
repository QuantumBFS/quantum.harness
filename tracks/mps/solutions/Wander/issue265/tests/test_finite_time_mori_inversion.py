import numpy as np
from scipy.special import erf

from src.finite_time_mori_inversion import (
    conditional_vertex_zero_amplitude_limit,
    even_amplitude_zero_limit,
    cross_validate_finite_time_structure,
    decompose_dilation_correction,
    finite_q_mori_k0_correction,
    finite_time_structure_correction,
    local_current_vertex,
    opposite_wall_linear_response,
    structure_factor_from_wall,
)


def test_conditional_vertex_amplitude_limit_removes_even_and_odd_biases() -> None:
    amplitudes = np.asarray([0.02, 0.05, 0.10, 0.20])
    mu = np.repeat(amplitudes, 2)
    orientation = np.tile(np.asarray([1, -1]), amplitudes.size)
    exact = 0.231
    coefficient = (
        exact
        + 0.7 * mu**2
        - 1.2 * mu**4
        + orientation * (0.4 * mu - 0.9 * mu**3)
    )
    result = conditional_vertex_zero_amplitude_limit(mu, orientation, coefficient)
    assert np.isclose(result["a0_one_sided"], exact, atol=2e-13)
    assert np.isclose(result["even_mu2"], 0.7, atol=2e-11)
    assert np.isclose(result["odd_mu1"], 0.4, atol=2e-11)
    assert result["n_amplitudes"] == 4


def test_even_amplitude_limit_extrapolates_entire_frequency_grid() -> None:
    mu = np.asarray([0.02, 0.05, 0.10, 0.20])
    limit = np.asarray([-0.25, -0.28, -0.31])
    values = limit + mu[:, None] ** 2 * np.asarray([0.4, -0.2, 0.1])
    values += mu[:, None] ** 4 * np.asarray([-0.7, 0.3, 0.6])
    result = even_amplitude_zero_limit(mu, values)
    assert np.allclose(result["zero_amplitude_limit"], limit, atol=2e-14)


def test_opposite_walls_cancel_orientation_even_contamination() -> None:
    linear = np.arange(12.0).reshape(3, 4)
    even = 0.03 * linear**2
    up = linear + even
    down = -linear + even
    assert np.allclose(opposite_wall_linear_response(up, down), linear)


def test_wall_deconvolution_recovers_heat_structure_factor() -> None:
    x = np.linspace(-128.0, 127.5, 512)
    t = np.array([1.0, 2.0, 4.0, 7.0])
    wall = np.stack([0.5 * erf(x / (2.0 * np.sqrt(value))) for value in t])
    modes = np.array([1, 2, 3, 4])
    k, structure = structure_factor_from_wall(x, t, wall, modes)
    expected = np.exp(-(t[:, None] - t[0]) * k[None, :] ** 2)
    assert np.allclose(structure, expected, rtol=2e-4, atol=2e-5)


def test_extract_and_decompose_known_dilation_F1() -> None:
    k = np.array([0.02, 0.04, 0.06])
    t = np.linspace(50.0, 200.0, 31)
    lam = 1.9
    q = k[None, :] * (lam * t[:, None]) ** (2.0 / 3.0)
    leading = lambda value: np.exp(-0.2 * value**2)
    derivative = lambda value: -0.4 * value * np.exp(-0.2 * value**2)
    b = -0.23
    structure = leading(q) + t[:, None] ** (-1.0 / 3.0) * b * q * derivative(q)
    finite = finite_time_structure_correction(
        k,
        t,
        structure,
        leading,
        lambda_kpz=lam,
        t_window=(50.0, 200.0),
    )
    decomposition = decompose_dilation_correction(
        finite.q, finite.correction, derivative
    )
    assert np.isclose(decomposition["dilation_coefficient"], b, atol=2e-14)
    assert decomposition["relative_perpendicular_norm"] < 2e-13


def test_local_current_vertex_recovers_quadratic_flux_and_diffusion() -> None:
    x = np.linspace(-40.0, 40.0, 161)
    t = np.linspace(50.0, 80.0, 16)
    field = np.stack(
        [0.5 * np.tanh(x / (3.0 + 0.02 * ti)) for ti in t], axis=0
    )
    bond_field = 0.5 * (field[:, :-1] + field[:, 1:])
    gradient = np.diff(field, axis=1) / np.diff(x)[None, :]
    a_exact, d_exact, mu = 0.23, 1.97, 0.05
    current = mu * (
        0.5 * a_exact * bond_field**2
        - d_exact * gradient
        + 0.001 * np.sin(t)[:, None]
    )
    result = local_current_vertex(
        x,
        t,
        field,
        current,
        mu=mu,
        orientation=1,
        t_window=(50.0, 80.0),
        x_crop=(-35.0, 35.0),
        smoothing_window=9,
        smoothing_order=3,
    )
    assert abs(result["a_current_vertex"] - a_exact) < 3e-4
    assert abs(result["D_instantaneous_local"] - d_exact) < 2e-3


def test_finite_q_mori_correction_matches_direct_quadrature() -> None:
    q = np.linspace(0.0, 7.0, 5001)
    f1 = q * np.exp(-q)
    leading = lambda value: np.exp(-0.3 * value**2)
    lam = 1.9
    s = np.array([0.75, 1.25, 2.0])
    result = finite_q_mori_k0_correction(
        q,
        f1,
        leading,
        lambda_kpz=lam,
        s_values=s,
        q_max=7.0,
        n_bins=500,
        n_grid=10001,
    )
    for index, laplace in enumerate(s):
        exponential = np.exp(-laplace * q**1.5)
        phi0 = 1.5 * np.trapezoid(q**0.5 * exponential * leading(q), q)
        phi1 = 1.5 * np.trapezoid(exponential * f1, q)
        expected = -(lam ** (4.0 / 3.0)) * phi1 / phi0**2
        assert np.isclose(result["delta_K1_truncated"][index], expected, rtol=2e-4)


def test_finite_time_correction_predicts_disjoint_late_times() -> None:
    k = np.linspace(0.015, 0.09, 12)
    t = np.linspace(50.0, 200.0, 301)
    lam = 1.9
    q = k[None, :] * (lam * t[:, None]) ** (2.0 / 3.0)
    leading = lambda value: np.exp(-0.2 * value**2)
    f1 = lambda value: -0.17 * value**2 * np.exp(-0.3 * value)
    structure = leading(q) + t[:, None] ** (-1.0 / 3.0) * f1(q)
    result = cross_validate_finite_time_structure(
        k,
        t,
        structure,
        leading,
        lambda_kpz=lam,
        train_window=(50.0, 120.0),
        test_window=(121.0, 200.0),
        q_max=5.0,
    )
    assert result["corrected_rms"] < 0.03 * result["leading_rms"]
