import json
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.integrate import quad
from scipy.special import erf

from scripts.audit_full_tba_subleading import audit as audit_full_tba_subleading
from scripts.audit_theory_exact_weak_estimator import derive as derive_exact_weak
from scripts.derive_theory_only_hierarchy import derive as derive_hierarchy
from scripts.evaluate_full_tba_diffusion import (
    apply_symmetric_noise_root_frechet,
    _assemble_nodal_diffusion_noise,
    _assemble_nodal_diffusion_noise_weighted,
    _thermodynamic_fields_nodes,
    diagonal_diffusion_width_field,
    effective_velocity_second_frechet_derivative,
    evaluate as evaluate_full_tba,
    full_diffusion_noise_directional_frechet_derivative,
    full_diffusion_noise_frechet_derivatives,
    full_diffusion_noise_second_diagonal_frechet_derivatives,
    full_diffusion_operator_field,
    full_diffusion_operator_field_adaptive_rapidity,
    projected_diffusion_vertex_action,
    projected_noise_root_vertex_action,
    symmetric_noise_root_frechet_setup,
    symmetric_noise_root_frechet_derivatives,
    symmetric_noise_root_second_diagonal_frechet_derivatives,
)
from scripts.derive_xxx_mori_lanczos import (
    fourier_bond_current,
    kernel_moments,
    microscopic_bond_current_continuity_certificate,
    uniform_current_kernel_moments,
    translation_reduced_uniform_current_kernel_moments,
)
from scripts.derive_kpz_lanczos_terminator import (
    scale_correction_structure_laplace,
    scaled_structure_laplace,
)
from scripts.derive_xxx_slow_current_projector import (
    bond_current_bilinear_gram,
    bond_current_bilinear_operator,
    derive as derive_slow_current_projector,
    slow_bilinear_dynamical_matrices,
)
from scripts.derive_xxx_slow_current_dynamics import (
    derive as derive_slow_current_dynamics,
    projected_qlq_lanczos,
)
from scripts.derive_xxx_thermodynamic_qlq import (
    analytic_bandlimited_first_recurrent,
)

from src.heisenberg_burgers_bridge import (
    EXACT_D0_INFINITY_T,
    finite_rescaled_bare_scattering_kernel,
    giant_bare_scattering_first_field_fourier_kernel,
    giant_bare_scattering_first_field_correction,
    giant_bare_scattering_fourier_kernel,
    giant_bare_scattering_kernel,
    giant_density_velocity_first_field_data,
    giant_diagonal_diffusion_outer_factors,
    giant_diagonal_diffusion_outer_integrand_coefficients,
    giant_dressed_scattering_common_shift_derivative_fourier_kernel,
    giant_dressed_scattering_fourier_kernel,
    giant_dressed_scattering_first_field_fourier_quadrature,
    giant_dressed_scattering_first_field_real_kernel,
    giant_dressed_scattering_real_kernel,
    giant_infinite_temperature_first_field_data,
    zero_field_edge_dressed_momentum_green,
    zero_field_edge_dressed_scattering_fourier,
    zero_field_edge_thermodynamic_fields,
    EXACT_MOMENT_AMPLITUDE_INFINITY_T,
    KPZ_SCALING_FOURTH_CUMULANT,
    KPZ_BURGERS_MOMENT_SHAPE_FACTOR,
    SPECTRAL_REGULATOR_D1_INFINITY_T,
    finite_field_scale_correction,
    finite_field_spectral_regulator_diffusion,
    ghd_moment_amplitude,
    giant_string_diffusion_amplitude_quadrature,
    kpz_lambda_from_tba,
    kpz_mori_laplace_first_correction,
    kpz_mori_laplace_scaling,
    kpz_tcl_gradient_coefficients,
    mori_kernel_from_lanczos_terminator,
    mori_kernel_from_structure_laplace,
    mori_lanczos_stieltjes_bounds,
    mori_lanczos_terminator_from_kernel,
    physical_quadratic_current_kubo_vertex,
    theory_only_current_projection,
    theory_only_current_projection_diagnostics,
    theory_only_current_projection_from_scale,
    theory_only_running_current_projection,
    theory_only_scale_corrected_projection,
    theory_only_strong_scale_corrected_projection,
    theory_only_strong_projection,
    theory_only_strong_projection_from_scale,
    theory_only_width_rate_projection,
    xxx_mori_short_time_moments,
    xxx_mori_even_moments,
    xxx_mori_long_wave_lanczos,
    xxx_mori_lanczos_recurrents,
    xxx_structure_factor_short_time,
)


def test_infinite_temperature_tba_constants() -> None:
    assert np.isclose(EXACT_D0_INFINITY_T, 5.0 * np.pi / 27.0)
    assert np.isclose(
        ghd_moment_amplitude(), EXACT_MOMENT_AMPLITUDE_INFINITY_T
    )


def test_zero_field_edge_green_solves_exact_discrete_dressing_recurrence() -> None:
    for wave_number in (0.0, 0.3, 1.2):
        q = abs(wave_number) / 2.0
        for source in (1, 3, 7):
            strings = np.arange(1, 40)
            values = zero_field_edge_dressed_momentum_green(
                strings, source, wave_number
            )
            holes = 1.0 - 1.0 / (strings + 1.0) ** 2
            padded = np.r_[0.0, values, 0.0]
            left_holes = np.r_[0.0, holes[:-1]]
            right_holes = 1.0 - 1.0 / (strings + 2.0) ** 2
            residual = (
                2.0 * np.cosh(q) * values
                - left_holes * padded[:-2]
                - right_holes * padded[2:]
            )
            expected = (strings == source).astype(float)
            # The final row sees the artificial zero padding; all interior
            # rows satisfy the exact half-line recurrence.
            assert np.max(np.abs(residual[:-1] - expected[:-1])) < 2e-11


def test_zero_field_edge_scattering_is_neighbor_source_sum() -> None:
    left = np.arange(1, 8)[:, None]
    right = np.arange(1, 9)[None, :]
    wave_number = 0.7
    expected = zero_field_edge_dressed_momentum_green(
        left, right + 1, wave_number
    )
    expected += np.where(
        right > 1,
        zero_field_edge_dressed_momentum_green(
            left, np.maximum(right - 1, 1), wave_number
        ),
        0.0,
    )
    actual = zero_field_edge_dressed_scattering_fourier(
        left, right, wave_number
    )
    np.testing.assert_allclose(actual, expected, rtol=2e-13, atol=2e-13)


def test_zero_field_edge_thermodynamics_match_finite_field_limit() -> None:
    strings = np.asarray([1.0, 3.0, 8.0, 15.0])
    rapidities = np.asarray([0.2, -1.1, 3.0, -7.0])
    exact = zero_field_edge_thermodynamic_fields(strings, rapidities)
    for field in (2e-3, 1e-3, 5e-4):
        finite = _thermodynamic_fields_nodes(field, strings, rapidities)
        np.testing.assert_allclose(
            finite["filling"], exact["filling"], rtol=4e-4, atol=2e-8
        )
        np.testing.assert_allclose(
            finite["rho_total"], exact["rho_total"], rtol=3e-4, atol=2e-9
        )
        np.testing.assert_allclose(
            finite["velocity"], exact["velocity"], rtol=5e-4, atol=2e-9
        )
        np.testing.assert_allclose(
            finite["dressed_magnetization"] / field,
            exact["dressed_magnetization_per_field"],
            rtol=3e-4,
            atol=2e-8,
        )
    assert np.isclose(kpz_lambda_from_tba(), 1.9265241411877572)
    assert np.isclose(
        giant_string_diffusion_amplitude_quadrature(),
        EXACT_D0_INFINITY_T,
        rtol=2e-12,
    )


def test_first_field_correction_to_giant_bare_scattering_is_euler_maclaurin_limit() -> None:
    xi = 1.2
    zeta = 0.8
    rapidity_difference = 0.7
    leading = float(
        giant_bare_scattering_kernel(xi, zeta, rapidity_difference)
    )
    correction = float(
        giant_bare_scattering_first_field_correction(
            xi, zeta, rapidity_difference
        )
    )
    errors = []
    for denominator in (20, 40, 80, 160):
        h = 1.0 / denominator
        finite = finite_rescaled_bare_scattering_kernel(
            h,
            round(xi / h),
            round(zeta / h),
            rapidity_difference,
        )
        errors.append(abs((finite - leading) / h - correction))
    assert all(right < left for left, right in zip(errors, errors[1:]))
    assert errors[-1] < 7.0e-4


def test_giant_bare_fourier_kernels_match_direct_rapidity_quadrature() -> None:
    xi = 1.3
    zeta = 0.7
    wave_number = 1.4
    direct0 = 2.0 * quad(
        lambda u: giant_bare_scattering_kernel(xi, zeta, u),
        0.0,
        np.inf,
        weight="cos",
        wvar=wave_number,
        epsabs=2.0e-10,
        limlst=200,
    )[0]
    direct1 = 2.0 * quad(
        lambda u: giant_bare_scattering_first_field_correction(xi, zeta, u),
        0.0,
        np.inf,
        weight="cos",
        wvar=wave_number,
        epsabs=2.0e-10,
        limlst=200,
    )[0]
    assert np.isclose(
        direct0,
        giant_bare_scattering_fourier_kernel(xi, zeta, wave_number),
        rtol=2.0e-8,
        atol=2.0e-9,
    )
    assert np.isclose(
        direct1,
        giant_bare_scattering_first_field_fourier_kernel(
            xi, zeta, wave_number
        ),
        rtol=2.0e-8,
        atol=2.0e-9,
    )


def test_closed_giant_dressed_kernel_solves_continuum_dressing_equation() -> None:
    xi = 1.1
    zeta = 0.8
    for wave_number in (0.0, 0.8, 2.0, 3.4):
        dressed = float(
            giant_dressed_scattering_fourier_kernel(
                xi, zeta, wave_number
            )
        )
        convolution = quad(
            lambda q: float(
                giant_bare_scattering_fourier_kernel(
                    xi, q, wave_number
                )
                * giant_dressed_scattering_fourier_kernel(
                    q, zeta, wave_number
                )
                / np.sinh(q) ** 2
            ),
            0.0,
            30.0,
            epsabs=2.0e-10,
            limit=300,
        )[0]
        bare = float(
            giant_bare_scattering_fourier_kernel(
                xi, zeta, wave_number
            )
        )
        assert np.isclose(dressed, bare - convolution, rtol=2e-8, atol=2e-9)


def test_first_dressed_giant_kernel_quadrature_converges() -> None:
    coarse = giant_dressed_scattering_first_field_fourier_quadrature(
        1.1, 0.8, 2.0, xi_cutoff=12.0, order=320
    )
    fine = giant_dressed_scattering_first_field_fourier_quadrature(
        1.1, 0.8, 2.0, xi_cutoff=14.0, order=640
    )
    farther = giant_dressed_scattering_first_field_fourier_quadrature(
        1.1, 0.8, 2.0, xi_cutoff=16.0, order=720
    )
    assert np.isclose(coarse, fine, rtol=2.0e-3, atol=3.0e-4)
    assert np.isclose(fine, farther, rtol=1.0e-3, atol=2.0e-4)


def test_first_dressed_giant_kernel_is_common_shift_derivative() -> None:
    for xi, zeta, wave_number in (
        (1.1, 0.8, 0.0),
        (1.1, 0.8, 0.7),
        (1.1, 0.8, 2.0),
        (0.9, 0.9, 3.4),
    ):
        step = 2.0e-6
        finite_difference = (
            giant_dressed_scattering_fourier_kernel(
                xi + step, zeta + step, wave_number
            )
            - giant_dressed_scattering_fourier_kernel(
                xi - step, zeta - step, wave_number
            )
        ) / (2.0 * step)
        exact = giant_dressed_scattering_common_shift_derivative_fourier_kernel(
            xi, zeta, wave_number
        )
        assert np.isclose(exact, finite_difference, rtol=2.0e-7, atol=2.0e-8)
        assert np.isclose(
            giant_dressed_scattering_first_field_fourier_quadrature(
                xi, zeta, wave_number
            ),
            exact,
            rtol=1.0e-13,
            atol=1.0e-13,
        )


def test_inverse_fourier_giant_dressed_kernels_have_pointwise_plateau() -> None:
    leading = [
        giant_dressed_scattering_real_kernel(
            1.3,
            0.7,
            0.4,
            wave_number_cutoff=cutoff,
            wave_number_order=order,
        )
        for cutoff, order in ((32.0, 240), (48.0, 320), (64.0, 400))
    ]
    first = [
        giant_dressed_scattering_first_field_real_kernel(
            1.3,
            0.7,
            0.4,
            wave_number_cutoff=cutoff,
            wave_number_order=order,
            xi_cutoff=14.0,
            xi_order=180,
        )
        for cutoff, order in ((24.0, 80), (36.0, 120), (48.0, 160))
    ]
    assert abs(leading[-1] - leading[-2]) < abs(leading[1] - leading[0])
    assert np.isclose(leading[-1], leading[-2], rtol=4.0e-8, atol=8.0e-9)
    assert abs(first[-1] - first[-2]) < abs(first[1] - first[0])
    assert np.isclose(first[-1], first[-2], rtol=4.0e-5, atol=2.0e-5)


def test_outer_diagonal_diffusion_first_integrand_contains_all_product_terms() -> None:
    left = giant_diagonal_diffusion_outer_factors(1.1, 0.45)
    right = giant_diagonal_diffusion_outer_factors(0.8, -0.25)
    x0 = 0.37
    x1 = -0.11
    coefficients = giant_diagonal_diffusion_outer_integrand_coefficients(
        1.1, 0.45, 0.8, -0.25, x0, x1
    )
    errors = []
    cross_errors = []
    cross_leading = (
        4.0
        * left["cross_weight_leading"]
        * right["cross_weight_leading"]
        * abs(left["velocity_leading"] - right["velocity_leading"])
        * x0**2
    )
    cross_first = 4.0 * (
        (
            left["cross_weight_first"] * right["cross_weight_leading"]
            + left["cross_weight_leading"] * right["cross_weight_first"]
        )
        * abs(left["velocity_leading"] - right["velocity_leading"])
        * x0**2
        + left["cross_weight_leading"]
        * right["cross_weight_leading"]
        * np.sign(left["velocity_leading"] - right["velocity_leading"])
        * (left["velocity_first"] - right["velocity_first"])
        * x0**2
        + 2.0
        * left["cross_weight_leading"]
        * right["cross_weight_leading"]
        * abs(left["velocity_leading"] - right["velocity_leading"])
        * x0
        * x1
    )
    for h in (0.04, 0.02, 0.01, 0.005, 0.0025):
        a = h**-2 * (
            left["left_weight_leading"]
            + h * left["left_weight_first"]
        )
        b = h**4 * (
            right["partner_weight_leading"]
            + h * right["partner_weight_first"]
        )
        velocity_difference = h * (
            left["velocity_leading"]
            - right["velocity_leading"]
            + h
            * (left["velocity_first"] - right["velocity_first"])
        )
        # h^-4 is the two-string/two-rapidity measure and chi^-1=4.
        scaled_raw = (
            h
            * 4.0
            * h**-4
            * a
            * b
            * abs(velocity_difference)
            * (x0 + h * x1) ** 2
        )
        difference_quotient = (
            scaled_raw - coefficients["integrand_leading"]
        ) / h
        errors.append(abs(difference_quotient - coefficients["integrand_first"]))
        cross_left = h * (
            left["cross_weight_leading"]
            + h * left["cross_weight_first"]
        )
        cross_right = h * (
            right["cross_weight_leading"]
            + h * right["cross_weight_first"]
        )
        scaled_cross = (
            h
            * 4.0
            * h**-4
            * cross_left
            * cross_right
            * abs(velocity_difference)
            * (x0 + h * x1) ** 2
        )
        cross_errors.append(
            abs((scaled_cross - cross_leading) / h - cross_first)
        )
    assert all(right_error < left_error for left_error, right_error in zip(errors, errors[1:]))
    assert errors[-1] < 5.0e-3
    assert all(
        right_error < left_error
        for left_error, right_error in zip(cross_errors, cross_errors[1:])
    )
    assert cross_errors[-1] < 5.0e-3


def test_first_field_giant_thermodynamic_data_match_exact_tba() -> None:
    xi = 1.0
    coefficients = giant_infinite_temperature_first_field_data(xi)
    filling_errors = []
    magnetization_errors = []
    for denominator in (20, 40, 80, 160):
        h = 1.0 / denominator
        s = round(xi / h)
        filling = (np.sinh(h) / np.sinh((s + 1) * h)) ** 2
        x = (s + 1) * h
        dressed_magnetization = np.sinh(x) * (
            (s + 1) * np.cosh(x) - np.cosh(h) / np.sinh(h) * np.sinh(x)
        ) / (np.sinh(x) ** 2 - np.sinh(h) ** 2)
        filling_first = (
            filling / h**2 - coefficients["scaled_filling_leading"]
        ) / h
        magnetization_first = (
            h * dressed_magnetization
            - coefficients["scaled_dressed_magnetization_leading"]
        ) / h
        filling_errors.append(
            abs(filling_first - coefficients["scaled_filling_first"])
        )
        magnetization_errors.append(
            abs(
                magnetization_first
                - coefficients["scaled_dressed_magnetization_first"]
            )
        )
    assert all(
        right < left for left, right in zip(filling_errors, filling_errors[1:])
    )
    assert all(
        right < left
        for left, right in zip(magnetization_errors, magnetization_errors[1:])
    )
    assert filling_errors[-1] < 0.03
    assert magnetization_errors[-1] < 0.01


def test_first_field_giant_density_and_velocity_match_exact_tba() -> None:
    xi = 1.0
    u = 0.7
    coefficients = giant_density_velocity_first_field_data(xi, u)
    density_errors = []
    velocity_errors = []
    for denominator in (20, 40, 80, 160):
        h = 1.0 / denominator
        s = xi / h
        theta = u / h
        prefactor = (
            2.0
            * np.sinh(h)
            * np.sinh(h * (s + 1.0))
            / (np.pi * np.sinh(2.0 * h))
        )
        first = s / ((4.0 * theta**2 + s**2) * np.sinh(h * s))
        second = (s + 2.0) / (
            (4.0 * theta**2 + (s + 2.0) ** 2)
            * np.sinh(h * (s + 2.0))
        )
        rho = prefactor * (first - second)
        first_energy = s / (
            (4.0 * theta**2 + s**2) ** 2 * np.sinh(h * s)
        )
        second_energy = (s + 2.0) / (
            (4.0 * theta**2 + (s + 2.0) ** 2) ** 2
            * np.sinh(h * (s + 2.0))
        )
        energy = (
            16.0
            * theta
            * np.sinh(h)
            * np.sinh(h * (s + 1.0))
            / np.sinh(2.0 * h)
            * (first_energy - second_energy)
        )
        velocity = energy / (2.0 * np.pi * rho)
        density_first = (
            rho / h**2 - coefficients["scaled_total_density_leading"]
        ) / h
        velocity_first = (
            velocity / h - coefficients["scaled_effective_velocity_leading"]
        ) / h
        density_errors.append(
            abs(density_first - coefficients["scaled_total_density_first"])
        )
        velocity_errors.append(
            abs(velocity_first - coefficients["scaled_effective_velocity_first"])
        )
    assert all(right < left for left, right in zip(density_errors, density_errors[1:]))
    assert all(right < left for left, right in zip(velocity_errors, velocity_errors[1:]))
    assert density_errors[-1] < 0.003
    assert velocity_errors[-1] < 0.004


def test_physical_quadratic_current_kubo_vertex_vanishes() -> None:
    assert physical_quadratic_current_kubo_vertex() == 0.0


def test_theory_only_window_projection_uses_no_trajectory() -> None:
    coefficient, diffusion = theory_only_current_projection(50.0, 200.0)
    assert np.isclose(coefficient, 0.24797804, rtol=2e-8)
    assert np.isclose(diffusion, 2.05820566, rtol=2e-8)


def test_theory_only_hierarchy_certificate_has_no_target_or_trajectory() -> None:
    result = derive_hierarchy(50.0, 200.0)
    assert result["inputs"]["trajectory_data_used"] is False
    assert result["inputs"]["target_coefficients_used"] is False
    estimate = result["scheme_variation_estimate"]
    assert np.isclose(estimate["a"], 0.23362593775)
    assert np.isclose(estimate["a_half_width"], 0.02005582066)
    assert np.isclose(estimate["D"], 2.02635531770)
    assert np.isclose(estimate["D_half_width"], 0.20249973129)
    assert "restricted" in estimate["interpretation"]


def test_exact_weak_estimator_audit_has_no_target_or_trajectory() -> None:
    # Analytic mock g with g'(y)=2 erf(y/sqrt(2)); no downloaded table or
    # Heisenberg trajectory is needed to test the audit invariants.
    y = np.linspace(0.0, 8.0, 1001)
    g = 2.0 * (
        y * erf(y / np.sqrt(2.0))
        + np.sqrt(2.0 / np.pi) * np.exp(-0.5 * y**2)
    )
    result = derive_exact_weak(
        length=64,
        dx=1.0,
        dt=0.2,
        profile_start=5.0,
        profile_stop=8.0,
        fit_start=5.4,
        fit_stop=7.6,
        x_crop=(-20.0, 20.0),
        spline=CubicSpline(y, g),
    )
    assert result["inputs"]["trajectory_data_used"] is False
    assert result["inputs"]["target_coefficients_used"] is False
    leading = result["frozen_weak_estimator"]["leading_kpz"]
    diagnostic = result["frozen_weak_estimator"]["spectral_scale_diagnostic"]
    assert np.isfinite([leading["a"], leading["D"]]).all()
    assert diagnostic["physical_subleading_coefficient_claimed"] is False


def test_running_projection_has_kpz_powers_and_smaller_residual() -> None:
    times = np.array([50.0, 200.0])
    result = theory_only_running_current_projection(times)
    assert np.isclose(result["alpha"], 0.70761403, rtol=2e-8)
    assert np.isclose(result["delta"], 0.36793598, rtol=2e-8)
    assert np.allclose(result["coefficient"], [0.19825835, 0.12489493])
    assert np.allclose(result["diffusion"], [2.16622525, 3.43866824])
    assert np.isclose(
        result["coefficient"][1] / result["coefficient"][0],
        (200.0 / 50.0) ** (-1.0 / 3.0),
    )
    assert np.isclose(
        result["diffusion"][1] / result["diffusion"][0],
        (200.0 / 50.0) ** (1.0 / 3.0),
    )
    assert np.isclose(result["relative_current_residual"], 0.0023228292)
    assert result["relative_current_residual"] < 0.11 * 0.0218048626


def test_exact_mori_inversion_and_kpz_scaling() -> None:
    k = np.array([0.08, 0.16])
    z = np.array([0.03, 0.07])
    s0 = np.array([0.25, 0.25])
    stilde = np.array([2.0, 1.2])
    expected = (s0 / stilde - z) / k**2
    assert np.allclose(
        mori_kernel_from_structure_laplace(k, z, s0, stilde), expected
    )

    lam = kpz_lambda_from_tba()
    rate = lam * np.abs(k) ** 1.5
    scaled_frequency = z / rate
    # Use a positive mock Phi(s).  The test checks the exact scaling algebra,
    # not a numerical quadrature of the public KPZ table.
    phi = 1.0 / (1.0 + 0.4 * scaled_frequency)
    kernel = kpz_mori_laplace_scaling(k, z, phi, lambda_kpz=lam)
    assert np.allclose(
        kernel,
        lam * np.abs(k) ** (-0.5) * (1.0 / phi - scaled_frequency),
    )


def test_exact_xxx_mori_short_time_moments() -> None:
    k = np.array([0.0, np.pi / 2.0, np.pi])
    result = xxx_mori_short_time_moments(k)
    assert np.allclose(result["kernel_at_zero"], 0.5)
    assert np.allclose(result["second_moment"], [0.25, 0.5, 0.75])
    assert np.allclose(result["quadratic_coefficient"], [-0.125, -0.25, -0.375])
    scaled = xxx_mori_short_time_moments(k, exchange=2.0)
    assert np.allclose(scaled["kernel_at_zero"], 2.0)
    assert np.allclose(scaled["second_moment"], 16.0 * result["second_moment"])


def test_xxx_structure_factor_short_time_series() -> None:
    k = np.pi / 2.0
    t = np.array([0.0, 0.1])
    q = (2.0 * np.sin(k / 2.0)) ** 2
    k0 = 0.5
    mu2 = 0.5
    expected = 1.0 - q * k0 * t**2 / 2.0 + (q * mu2 + q**2 * k0**2) * t**4 / 24.0
    assert np.allclose(xxx_structure_factor_short_time(k, t), expected)


def test_exact_higher_mori_moments_and_lanczos_recurrents() -> None:
    moments = xxx_mori_even_moments(np.asarray(0.0))
    assert np.isclose(moments[0], 1.0 / 2.0)
    assert np.isclose(moments[2], 1.0 / 4.0)
    assert np.isclose(moments[4], 9.0 / 16.0)
    assert np.isclose(moments[6], 85.0 / 32.0)
    assert np.isclose(moments[8], 1237.0 / 64.0)
    assert np.isclose(moments[10], 186431.0 / 1024.0)
    assert np.isclose(moments[12], 4169963.0 / 2048.0)
    assert np.isclose(moments[14], 211707499.0 / 8192.0)
    assert np.isclose(moments[16], 11888860255.0 / 32768.0)
    lanczos = xxx_mori_long_wave_lanczos()
    assert np.allclose(
        lanczos["squared_recurrents"],
        [
            1.0 / 2.0,
            7.0 / 4.0,
            89.0 / 28.0,
            5199.0 / 1246.0,
            16362745.0 / 3701688.0,
            533174919181.0 / 97222755720.0,
            155669008835604501.0 / 28007079431635030.0,
            4880178544612122657668885.0 / 717500221130768922597084.0,
            1661338264320398559685770311237065.0
            / 250046006650855968625336278366756.0,
            8947223295590546232590956669440969508183131.0
            / 1157939709161061360332266823095747081714670.0,
            4998855168101323939519657338176816790733704038061133749.0
            / 662940090391383920022207046600208806645584336263399720.0,
            50132156701168705499901888783939441335625086510164717309097902703635.0
            / 5723858454419032516985810177548916159600312473930368972463971550968.0,
            3830599597503707351550130770645203489092745851543132140176839142618275372045569703.0
            / 432843590440934458009633813168074175889453230158717769172869909448364119630832969.0,
        ],
    )
    assert np.isclose(lanczos["mu18"], 726837552981.0 / 131072.0)
    assert np.isclose(lanczos["mu20"], 23930343808959.0 / 262144.0)
    assert np.isclose(lanczos["mu22"], 6735689494485335.0 / 4194304.0)
    assert np.isclose(lanczos["mu24"], 503357997961442429.0 / 16777216.0)
    assert np.isclose(lanczos["mu26"], 9934914094146058465.0 / 16777216.0)
    assert np.allclose(
        xxx_mori_lanczos_recurrents(np.asarray(0.0)),
        lanczos["squared_recurrents"][:8],
        rtol=2e-12,
    )


def test_uniform_current_chain_is_exact_long_wave_density_force() -> None:
    exact = uniform_current_kernel_moments(10, 6)
    expected = [0.5, 0.25, 9.0 / 16.0, 85.0 / 32.0]
    assert np.allclose(exact["moments"], expected, atol=2e-12)
    assert exact["finite_momentum_extrapolation_used"] is False


def test_microscopic_bond_current_has_exact_half_bond_fourier_phase() -> None:
    for length, momentum_index in [(8, 1), (12, 2), (16, 3)]:
        result = microscopic_bond_current_continuity_certificate(
            length, momentum_index
        )
        assert result["relative_operator_residual"] == 0.0
        assert result["bond_center_phase_retained"] is True
        assert result["internal_ghd_momentum_replacement_implied"] is False
        assert np.isclose(
            result["density_commutator_norm"],
            result["khat"] ** 2 * result["bond_current_norm"],
            rtol=0.0,
            atol=1.0e-14,
        )


def test_exact_slow_bilinear_projector_is_positive_bounded_and_complete() -> None:
    gram = bond_current_bilinear_gram(12, 1)
    assert np.min(np.linalg.eigvalsh(gram)) >= -1.0e-14
    assert np.isclose(np.ones(12) @ gram @ np.ones(12), 0.125)
    result = derive_slow_current_projector(12, 1, (1, 2, 3, 5))
    assert all(result["gates"].values())
    fractions = [
        row["projected_fraction_of_full_current"] for row in result["rows"]
    ]
    assert np.all(np.diff(fractions) >= -1.0e-12)
    assert fractions[-1] < 1.0
    assert np.isclose(result["exact_kernel_mu0"], 0.5)
    for row in result["rows"]:
        assert row["projected_slow_kernel_mu0"] >= 0.0
        assert row["orthogonal_kernel_mu0"] >= 0.0
        assert row["kernel_mu0_sum_residual"] <= 1.0e-14
        assert np.isclose(
            row["projected_slow_kernel_mu0"]
            + row["orthogonal_kernel_mu0"],
            result["exact_kernel_mu0"],
        )


def test_bilinear_current_operators_reconstruct_current_and_dynamic_gram() -> None:
    length = 8
    external_mode = 1
    _, current = fourier_bond_current(length, external_mode)
    reconstructed = {}
    for mode in range(length):
        for string, coefficient in bond_current_bilinear_operator(
            length, external_mode, mode
        ).items():
            reconstructed[string] = reconstructed.get(string, 0.0j) + coefficient
    keys = set(current) | set(reconstructed)
    assert max(
        abs(current.get(key, 0.0j) - reconstructed.get(key, 0.0j))
        for key in keys
    ) <= 1.0e-13
    dynamics = slow_bilinear_dynamical_matrices(length, external_mode, (0, 1, 7))
    assert dynamics["maximum_g0_analytic_residual"] <= 1.0e-13
    for key in ("gram", "liouvillian_gram", "liouvillian_norm_gram"):
        matrix = dynamics[key]
        assert np.allclose(matrix, matrix.conj().T, atol=1.0e-13)
    assert np.min(np.linalg.eigvalsh(dynamics["liouvillian_norm_gram"])) >= -1.0e-13
    split = derive_slow_current_dynamics(length, external_mode, (1, 3))
    assert split["gates"]["exact_full_current_norm"]
    assert split["gates"]["all_qlp_leakage_norms_nonnegative"]
    assert all(row["qlp_leakage_norm"] >= -1.0e-12 for row in split["rows"])
    assert any(
        row["qlp_fraction_of_projected_liouvillian_norm"] > 0.5
        for row in split["rows"]
    )
    qlq = projected_qlq_lanczos(length, external_mode, 1, 2)
    assert qlq["qlp_force_norm"] > 0.0
    assert np.allclose(qlq["alphas"], 0.0, atol=1.0e-12)
    assert all(value > 0.0 for value in qlq["squared_betas"])
    assert qlq["maximum_q_orthogonality_residual"] <= 1.0e-12
    continuum = analytic_bandlimited_first_recurrent(np.pi / 4.0)
    assert np.isclose(
        continuum["projected_current_norm"],
        (np.pi - 2.0) / (32.0 * np.pi),
        atol=1.0e-14,
    )
    assert continuum["qlp_force_norm"] > 0.0
    assert continuum["ql2_projected_current_norm"] > 0.0
    assert np.isclose(
        continuum["squared_first_qlq_recurrent"],
        1.2544032716229014,
        atol=1.0e-12,
    )


def test_translation_reduced_uniform_current_chain_matches_full_ring() -> None:
    full = uniform_current_kernel_moments(10, 6)
    reduced = translation_reduced_uniform_current_kernel_moments(6)
    assert np.allclose(reduced["moments"], full["moments"], atol=2e-12)
    assert reduced["translation_orbits_used"] is True
    assert reduced["finite_ring_used"] is False


def test_translation_reduced_chain_reproduces_mu22() -> None:
    reduced = translation_reduced_uniform_current_kernel_moments(22)
    assert np.isclose(
        reduced["moments"][-1],
        6735689494485335.0 / 4194304.0,
        rtol=3e-15,
    )
    assert reduced["exact_moments"][-1] == "6735689494485335/4194304"


def test_sparse_pauli_commutators_reproduce_closed_mori_moments() -> None:
    exact = kernel_moments(14, 3, 8)
    closed = xxx_mori_even_moments(np.asarray(exact["k"]))
    assert np.allclose(
        exact["moments"], [closed[order] for order in exact["orders"]], atol=2e-12
    )


def test_node_resolved_ghd_width_contracts_to_diagonal_diffusion() -> None:
    node = diagonal_diffusion_width_field(
        0.25,
        string_xi_cutoff=2.0,
        string_xi_buffer=2.0,
        rapidity_u_extent=10.0,
        rapidity_step=0.8,
        velocity_series_terms=50,
    )
    dc = float(node["rapidity_step"]) * np.sum(
        node["filling"][:, None]
        * node["holes"][:, None]
        * node["rho_total"]
        * node["dressed_magnetization"][:, None] ** 2
        * node["width"]
    )
    scalar = evaluate_full_tba(
        0.25,
        string_xi_cutoff=2.0,
        string_xi_buffer=2.0,
        rapidity_u_extent=10.0,
        rapidity_step=0.8,
        velocity_series_terms=50,
        velocity_group_ratio=1.3,
        string_boundary="robin",
        compute_cross_diagnostic=False,
    )
    chi = 1.0 / (4.0 * np.cosh(0.25) ** 2)
    assert np.isclose(dc / chi, scalar["diagonal_diffusion"], rtol=2e-12)
    assert np.all(node["width"] >= 0.0)


def test_full_diffusion_operator_retains_fdt_covariance() -> None:
    result = full_diffusion_operator_field(
        0.25,
        string_xi_cutoff=0.75,
        string_xi_buffer=0.75,
        rapidity_u_extent=1.5,
        rapidity_points=16,
    )
    diffusion = np.asarray(result["diffusion_operator"])
    covariance = np.asarray(result["static_covariance"])
    noise = np.asarray(result["noise_covariance"])
    vertex = np.asarray(result["velocity_vertex"])
    spin_hessian = np.asarray(result["spin_hessian"])
    assert diffusion.shape == (48, 48)
    assert np.allclose(
        noise,
        0.5 * (diffusion @ covariance + covariance @ diffusion.T),
        rtol=1.0e-12,
        atol=1.0e-12,
    )
    assert np.allclose(noise, noise.T, rtol=0.0, atol=1.0e-12)
    assert np.linalg.eigvalsh(noise)[0] >= -1.0e-9
    assert vertex.shape == diffusion.shape
    assert np.all(np.isfinite(vertex))
    # A node cannot change its own velocity: the exact dressing derivative
    # contains v_j-v_i and hence has a vanishing diagonal.
    assert np.allclose(np.diag(vertex), 0.0, rtol=0.0, atol=1.0e-14)
    assert spin_hessian.shape == diffusion.shape
    assert np.allclose(spin_hessian, spin_hessian.T, rtol=0.0, atol=1.0e-13)


def test_full_diffusion_noise_frechet_derivative_matches_directional_difference() -> None:
    modes = full_diffusion_operator_field(
        0.25,
        string_xi_cutoff=0.25,
        string_xi_buffer=0.5,
        rapidity_u_extent=1.5,
        rapidity_points=16,
    )
    derivatives = full_diffusion_noise_frechet_derivatives(modes)
    rng = np.random.default_rng(265)
    direction = rng.normal(size=16)
    direction /= np.linalg.norm(direction)
    d_rho = np.einsum(
        "l,li->i", direction, derivatives["rho_total_derivative"]
    )
    d_scattering = np.einsum(
        "l,lij->ij", direction, derivatives["dressed_scattering_derivative"]
    )
    d_velocity = np.asarray(modes["velocity_vertex"]) @ direction
    expected = {
        "diffusion_operator": np.einsum(
            "l,lij->ij", direction, derivatives["diffusion_derivative"]
        ),
        "static_covariance": np.einsum(
            "l,lij->ij", direction, derivatives["static_covariance_derivative"]
        ),
        "noise_covariance": np.einsum(
            "l,lij->ij", direction, derivatives["noise_covariance_derivative"]
        ),
    }
    epsilon = 1.0e-6
    scattering = np.asarray(modes["dressed_scattering"]) + epsilon * d_scattering
    perturbed = _assemble_nodal_diffusion_noise(
        np.asarray(modes["filling"]) + epsilon * direction,
        np.asarray(modes["rho_total"]) + epsilon * d_rho,
        np.asarray(modes["velocity"]) + epsilon * d_velocity,
        scattering,
        scattering.T,
        float(modes["rapidity_step"]),
    )
    for key in expected:
        finite_difference = (
            np.asarray(perturbed[key]) - np.asarray(modes[key])
        ) / epsilon
        assert np.allclose(
            finite_difference, expected[key], rtol=3.0e-5, atol=3.0e-5
        )

    root_data = symmetric_noise_root_frechet_derivatives(
        modes["noise_covariance"], derivatives["noise_covariance_derivative"]
    )
    root = np.asarray(root_data["noise_root"])
    assert np.allclose(
        root @ root.T,
        modes["noise_covariance"],
        rtol=2.0e-11,
        atol=2.0e-11,
    )
    assert np.max(root_data["relative_nullspace_residual"]) < 1.0e-11


def test_adaptive_weighted_diffusion_noise_frechet_derivative_matches_difference() -> None:
    modes = full_diffusion_operator_field_adaptive_rapidity(
        0.25,
        string_xi_cutoff=0.25,
        string_xi_buffer=0.5,
        scaled_rapidity_extent=2.0,
        scaled_rapidity_map_alpha=2.0,
        nodes_per_string=12,
        kernel_theta_step=0.25,
    )
    derivatives = full_diffusion_noise_frechet_derivatives(modes)
    rng = np.random.default_rng(1265)
    direction = rng.normal(size=12)
    direction /= np.linalg.norm(direction)
    d_rho = np.einsum(
        "l,li->i", direction, derivatives["rho_total_derivative"]
    )
    d_scattering = np.einsum(
        "l,lij->ij", direction, derivatives["dressed_scattering_derivative"]
    )
    weights = np.asarray(modes["quadrature_weights"])
    reverse = np.asarray(modes["reverse_dressed_scattering"])
    d_reverse = np.einsum(
        "l,l,il,lj->ij", direction, weights, reverse, reverse
    )
    d_velocity = np.asarray(modes["velocity_vertex"]) @ direction
    expected = {
        "diffusion_operator": np.einsum(
            "l,lij->ij", direction, derivatives["diffusion_derivative"]
        ),
        "static_covariance": np.einsum(
            "l,lij->ij", direction, derivatives["static_covariance_derivative"]
        ),
        "noise_covariance": np.einsum(
            "l,lij->ij", direction, derivatives["noise_covariance_derivative"]
        ),
    }
    directional = full_diffusion_noise_directional_frechet_derivative(
        modes, direction
    )
    assert np.allclose(
        directional["diffusion_directional_derivative"],
        expected["diffusion_operator"],
        rtol=2.0e-12,
        atol=2.0e-12,
    )
    assert np.allclose(
        directional["static_covariance_directional_derivative"],
        expected["static_covariance"],
        rtol=2.0e-12,
        atol=2.0e-12,
    )
    assert np.allclose(
        directional["noise_covariance_directional_derivative"],
        expected["noise_covariance"],
        rtol=2.0e-12,
        atol=2.0e-12,
    )
    projected_tensor = np.einsum(
        "a,laj->jl",
        np.asarray(modes["spin_projection"]),
        derivatives["diffusion_derivative"],
    )
    assert np.allclose(
        projected_diffusion_vertex_action(
            modes, np.asarray(modes["spin_projection"]), direction
        ),
        projected_tensor @ direction,
        rtol=2.0e-12,
        atol=2.0e-12,
    )
    complex_direction = direction + 0.3j * np.roll(direction, 1)
    root_tensor = symmetric_noise_root_frechet_derivatives(
        np.asarray(modes["noise_covariance"]),
        derivatives["noise_covariance_derivative"],
    )
    projected_root_tensor = np.einsum(
        "a,lar->lr",
        np.asarray(modes["spin_projection"]),
        root_tensor["noise_root_derivative"],
    )
    root_setup = symmetric_noise_root_frechet_setup(
        np.asarray(modes["noise_covariance"])
    )
    projected_root_action = projected_noise_root_vertex_action(
        modes,
        np.asarray(modes["spin_projection"]),
        complex_direction,
        root_setup,
    )
    assert np.allclose(
        projected_root_action["projected_noise_root_vertex_action"],
        projected_root_tensor.T @ complex_direction,
        rtol=3.0e-10,
        atol=3.0e-11,
    )
    direct_root_action = apply_symmetric_noise_root_frechet(
        root_setup,
        directional["noise_covariance_directional_derivative"],
    )
    assert direct_root_action["relative_nullspace_residual"] < 1.0e-10
    assert np.allclose(
        projected_diffusion_vertex_action(
            modes, np.asarray(modes["spin_projection"]), complex_direction
        ),
        projected_tensor @ complex_direction,
        rtol=2.0e-12,
        atol=2.0e-12,
    )
    epsilon = 1.0e-6
    perturbed = _assemble_nodal_diffusion_noise_weighted(
        np.asarray(modes["filling"]) + epsilon * direction,
        np.asarray(modes["rho_total"]) + epsilon * d_rho,
        np.asarray(modes["velocity"]) + epsilon * d_velocity,
        np.asarray(modes["dressed_scattering"]) + epsilon * d_scattering,
        reverse + epsilon * d_reverse,
        weights,
    )
    for key in expected:
        finite_difference = (
            np.asarray(perturbed[key]) - np.asarray(modes[key])
        ) / epsilon
        assert np.allclose(
            finite_difference, expected[key], rtol=4.0e-5, atol=4.0e-5
        )


def test_effective_velocity_hessian_matches_vertex_directional_difference() -> None:
    modes = full_diffusion_operator_field(
        0.25,
        string_xi_cutoff=0.25,
        string_xi_buffer=0.5,
        rapidity_u_extent=1.5,
        rapidity_points=16,
    )
    result = effective_velocity_second_frechet_derivative(modes)
    hessian = np.asarray(result["velocity_hessian"])
    scattering = np.asarray(modes["dressed_scattering"])
    rho = np.asarray(modes["rho_total"])
    velocity = np.asarray(modes["velocity"])
    vertex = np.asarray(modes["velocity_vertex"])
    step = float(modes["rapidity_step"])
    # The dressed formula contains cancellations between individually large
    # density/scattering terms.  A centered difference at 1e-3 removes the
    # quadratic perturbation error without amplifying double-precision noise.
    epsilon = 1.0e-3
    for node in (0, 7, 15):
        d_scattering = step * scattering[:, node, None] * scattering[node, None, :]
        d_rho = step * scattering[:, node] * rho[node]
        d_velocity = vertex[:, node]
        vertices = []
        for sign in (1.0, -1.0):
            scattering_eps = scattering + sign * epsilon * d_scattering
            rho_eps = rho + sign * epsilon * d_rho
            velocity_eps = velocity + sign * epsilon * d_velocity
            vertices.append(
                step
                * scattering_eps
                * rho_eps[None, :]
                / rho_eps[:, None]
                * (velocity_eps[None, :] - velocity_eps[:, None])
            )
        finite_difference = (vertices[0] - vertices[1]) / (2.0 * epsilon)
        assert np.allclose(
            finite_difference, hessian[:, :, node], rtol=2.0e-3, atol=8.0e-5
        )
    assert result["raw_schwarz_relative_residual"] < 3.0e-8


def test_second_diagonal_diffusion_noise_jets_and_root_sylvester_identity() -> None:
    modes = full_diffusion_operator_field(
        0.25,
        string_xi_cutoff=0.25,
        string_xi_buffer=0.5,
        rapidity_u_extent=1.5,
        rapidity_points=16,
    )
    first = full_diffusion_noise_frechet_derivatives(modes)
    second = full_diffusion_noise_second_diagonal_frechet_derivatives(modes)
    root = symmetric_noise_root_second_diagonal_frechet_derivatives(
        modes["noise_covariance"],
        first["noise_covariance_derivative"],
        second["noise_covariance_second_diagonal_derivative"],
    )
    assert second["diffusion_second_diagonal_derivative"].shape == (16, 16, 16)
    assert second["static_covariance_second_diagonal_derivative"].shape == (16, 16, 16)
    assert second["noise_covariance_second_diagonal_derivative"].shape == (16, 16, 16)
    assert np.max(root["second_order_relative_nullspace_residual"]) < 1.0e-11

    # Independent centered second directional check at a non-boundary node.
    node = 7
    epsilon = 2.0e-3
    count = 16
    delta = np.eye(count)[node]
    n = np.asarray(modes["filling"])
    rho = np.asarray(modes["rho_total"])
    velocity = np.asarray(modes["velocity"])
    scattering = np.asarray(modes["dressed_scattering"])
    reverse = np.asarray(modes["reverse_dressed_scattering"])
    vertex = np.asarray(modes["velocity_vertex"])
    step = float(modes["rapidity_step"])
    velocity_hessian = np.asarray(
        effective_velocity_second_frechet_derivative(modes)["velocity_hessian"]
    )
    d_scattering = step * scattering[:, node, None] * scattering[node, None, :]
    d2_scattering = (
        2.0
        * step**2
        * scattering[node, node]
        * scattering[:, node, None]
        * scattering[node, None, :]
    )
    d_reverse = step * reverse[:, node, None] * reverse[node, None, :]
    d2_reverse = (
        2.0
        * step**2
        * reverse[node, node]
        * reverse[:, node, None]
        * reverse[node, None, :]
    )
    d_rho = step * scattering[:, node] * rho[node]
    d2_rho = (
        2.0
        * step**2
        * scattering[:, node]
        * scattering[node, node]
        * rho[node]
    )
    d_velocity = vertex[:, node]
    d2_velocity = velocity_hessian[:, node, node]
    perturbed = []
    for sign in (1.0, -1.0):
        perturbed.append(
            _assemble_nodal_diffusion_noise(
                n + sign * epsilon * delta,
                rho + sign * epsilon * d_rho + 0.5 * epsilon**2 * d2_rho,
                velocity
                + sign * epsilon * d_velocity
                + 0.5 * epsilon**2 * d2_velocity,
                scattering
                + sign * epsilon * d_scattering
                + 0.5 * epsilon**2 * d2_scattering,
                reverse
                + sign * epsilon * d_reverse
                + 0.5 * epsilon**2 * d2_reverse,
                step,
            )
        )
    for key, result_key, tolerance in (
        ("diffusion_operator", "diffusion_second_diagonal_derivative", 1.2e-2),
        ("static_covariance", "static_covariance_second_diagonal_derivative", 1.0e-4),
        ("noise_covariance", "noise_covariance_second_diagonal_derivative", 2.0e-3),
    ):
        finite_difference = (
            np.asarray(perturbed[0][key])
            - 2.0 * np.asarray(modes[key])
            + np.asarray(perturbed[1][key])
        ) / epsilon**2
        exact = np.asarray(second[result_key][node])
        relative = np.linalg.norm(finite_difference - exact) / np.linalg.norm(exact)
        assert relative < tolerance


def test_sparse_pauli_commutators_reproduce_fourteenth_mori_moment() -> None:
    exact = kernel_moments(18, 3, 14)
    closed = xxx_mori_even_moments(np.asarray(exact["k"]))
    assert np.isclose(exact["moments"][-1], closed[14], rtol=8e-13, atol=2e-8)


def test_sparse_pauli_commutators_reproduce_sixteenth_mori_moment() -> None:
    exact = kernel_moments(22, 3, 16)
    closed = xxx_mori_even_moments(np.asarray(exact["k"]))
    assert np.isclose(exact["moments"][-1], closed[16], rtol=8e-13, atol=6e-7)


def test_mori_lanczos_terminator_round_trip() -> None:
    z = np.array([0.02, 0.1, 0.7, 3.0])
    b2 = xxx_mori_long_wave_lanczos()["squared_recurrents"]
    terminator = 1.0 / np.sqrt(z**2 + 6.0)
    kernel = mori_kernel_from_lanczos_terminator(z, terminator, 0.5, b2)
    recovered = mori_lanczos_terminator_from_kernel(z, kernel, 0.5, b2)
    # Thirteen inverse continued-fraction steps amplify roundoff at the largest
    # Laplace frequency; the observed relative residual is below 9e-9.
    assert np.allclose(recovered, terminator, rtol=1e-8, atol=1e-8)


def test_nine_moment_stieltjes_bounds_contain_positive_terminator_kernel() -> None:
    z = np.asarray([0.005, 0.01, 0.02])
    b2 = xxx_mori_long_wave_lanczos()["squared_recurrents"]
    terminator = 1.0 / (z + 0.7)
    kernel = mori_kernel_from_lanczos_terminator(z, terminator, 0.5, b2)
    bounds = mori_lanczos_stieltjes_bounds(z, 0.5, b2)
    assert np.all(bounds["lower"] <= kernel)
    assert np.all(kernel <= bounds["upper"])
    assert np.all(bounds["upper"] / bounds["lower"] > 100.0)


def test_scaled_structure_laplace_quadrature_on_gaussian() -> None:
    y = np.linspace(0.0, 8.0, 2049)
    g = 2.0 * y * erf(y) + 2.0 / np.sqrt(np.pi) * np.exp(-y**2)
    table = np.column_stack((y, g))
    s = np.array([0.4, 1.0, 2.5])
    actual = scaled_structure_laplace(
        table, s, quadrature_order=500, fourier_cutoff=14.0
    )
    expected = np.array(
        [
            quad(
                lambda q: 1.5
                * np.sqrt(q)
                * np.exp(-value * q**1.5 - q**2 / 4.0),
                0.0,
                np.inf,
            )[0]
            for value in s
        ]
    )
    assert np.allclose(actual, expected, rtol=3e-6, atol=2e-7)
    b = -0.2
    actual_phi1 = scale_correction_structure_laplace(
        table, s, b, quadrature_order=500, fourier_cutoff=14.0
    )
    expected_phi1 = np.array(
        [
            quad(
                lambda q: -0.75
                * b
                * q**2
                * np.exp(-value * q**1.5 - q**2 / 4.0),
                0.0,
                np.inf,
            )[0]
            for value in s
        ]
    )
    assert np.allclose(actual_phi1, expected_phi1, rtol=5e-6, atol=3e-7)


def test_first_finite_time_structure_correction_maps_exactly_to_mori() -> None:
    k = np.array([0.04, 0.09])
    phi0 = np.array([0.8, 0.6])
    phi1 = np.array([0.03, -0.02])
    lam = kpz_lambda_from_tba()
    correction = kpz_mori_laplace_first_correction(
        k, phi0, phi1, lambda_kpz=lam
    )
    assert np.allclose(correction, -(lam ** (4.0 / 3.0)) * phi1 / phi0**2)


def test_original_strong_loss_projection_uses_no_trajectory() -> None:
    coefficient, diffusion = theory_only_strong_projection(50.0, 200.0)
    assert np.isclose(coefficient, 0.21357012, rtol=2e-8)
    assert np.isclose(diffusion, 2.22885505, rtol=2e-8)


def test_sampled_scale_projections_recover_closed_power_law() -> None:
    time = np.linspace(50.0, 200.0, 20001)
    length = (kpz_lambda_from_tba() * time) ** (2.0 / 3.0)
    length_rate = (
        (2.0 / 3.0)
        * kpz_lambda_from_tba() ** (2.0 / 3.0)
        * time ** (-1.0 / 3.0)
    )
    assert np.allclose(
        theory_only_strong_projection_from_scale(
            time, length, length_rate
        ),
        theory_only_strong_projection(50.0, 200.0),
        rtol=2e-9,
    )
    assert np.allclose(
        theory_only_current_projection_from_scale(
            time, length, length_rate
        ),
        theory_only_current_projection(50.0, 200.0),
        rtol=2e-9,
    )


def test_sampled_scale_projections_reject_nonphysical_history() -> None:
    time = np.array([50.0, 100.0, 200.0])
    length = np.array([10.0, 20.0, 30.0])
    bad_rate = np.array([1.0, 0.0, 1.0])
    for function in (
        theory_only_strong_projection_from_scale,
        theory_only_current_projection_from_scale,
    ):
        try:
            function(time, length, bad_rate)
        except ValueError:
            pass
        else:
            raise AssertionError("non-positive scale rate must be rejected")


def test_full_tba_subleading_audit_rejects_unconverged_D1() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = json.loads(
        (root / "docs" / "full_tba_finite_field_runs.json").read_text()
    )
    result = audit_full_tba_subleading(payload)
    assert result["inputs"]["trajectory_data_used"] is False
    assert result["inputs"]["target_coefficients_used"] is False
    subleading = result["subleading_constant_audit"]
    assert subleading["physical_D1_determined"] is False
    assert subleading["leading_benchmark_improves_toward_zero"] is False
    assert subleading["putative_D1_max"] > 10.0 * subleading["putative_D1_min"]
    forbidden = result["forbidden_uniform_field_substitution"]
    assert forbidden["mapping_authorized_beyond_leading_singularity"] is False
    assert forbidden["finite_field_substitution_strong"][0] > 0.34
    assert forbidden["finite_field_substitution_current"][0] > 0.38


def test_full_tba_quadrature_labels_exact_cross_but_not_cutoff_as_converged() -> None:
    result = evaluate_full_tba(
        0.2,
        string_xi_cutoff=3.0,
        string_xi_buffer=2.0,
        rapidity_u_extent=8.0,
        rapidity_step=0.5,
        velocity_series_terms=50,
        velocity_group_ratio=2.0,
        string_boundary="robin",
    )
    assert result["uses_heisenberg_trajectory"] is False
    assert result["cross_is_exact_physical_off_diagonal_dc_term"] is True
    assert result["full_finite_cutoff_is_converged_physical_diffusion"] is False
    assert result["off_diagonal_cross_contraction_dc"] > 0.0
    assert np.isclose(
        result["full_dc_finite_cutoff"],
        result["diagonal_dc"] - result["off_diagonal_cross_contraction_dc"],
    )
    assert result["velocity_group_count"] >= 2
    assert result["diagonal_diffusion"] > 0.0
    assert np.isfinite(result["rho_total_relative_l2_error"])


def test_width_rate_projection_is_analytic_and_uses_no_trajectory() -> None:
    result = theory_only_width_rate_projection(50.0, 200.0)
    assert np.isclose(result["diffusion"], 1.8899924783, rtol=2e-10)
    assert np.isclose(result["speed"], 0.07818682690, rtol=2e-10)
    assert np.isclose(result["coefficient"], 0.2760216073, rtol=2e-9)
    assert result["relative_rate_residual"] < 0.011
    assert np.isclose(KPZ_BURGERS_MOMENT_SHAPE_FACTOR, 2.26610743)


def test_theory_only_window_projection_validates_window() -> None:
    for window in ((0.0, 200.0), (200.0, 50.0), (50.0, 50.0)):
        try:
            theory_only_current_projection(*window)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid time window must be rejected")
        try:
            theory_only_strong_projection(*window)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid time window must be rejected")


def test_theory_only_projection_residual_and_conditioning() -> None:
    diagnostics = theory_only_current_projection_diagnostics(50.0, 200.0)
    assert np.isclose(
        diagnostics["relative_current_residual"], 0.0218048626, rtol=2e-8
    )
    assert np.isclose(
        diagnostics["spatial_basis_correlation"], 0.99570192, rtol=2e-8
    )
    assert np.isclose(
        diagnostics["window_basis_correlation"], 0.96409353, rtol=2e-8
    )
    assert np.isclose(
        diagnostics["gram_condition_number"], 918.8067, rtol=2e-6
    )
    assert np.isclose(
        diagnostics["normalized_condition_number"], 54.7003, rtol=2e-6
    )


def test_scale_only_correction_cannot_match_both_reported_coefficients() -> None:
    coefficient, diffusion = theory_only_scale_corrected_projection(
        0.688887022
    )
    assert np.isclose(coefficient, 0.2301488, rtol=2e-8)
    assert np.isclose(diffusion, 2.8443957, rtol=2e-7)

    coefficient, diffusion = theory_only_scale_corrected_projection(
        -0.085319264
    )
    assert np.isclose(coefficient, 0.25010145, rtol=2e-8)
    assert np.isclose(diffusion, 1.97, rtol=2e-8)


def test_spectral_regulator_small_field_asymptotics() -> None:
    h = 0.001
    diffusion = finite_field_spectral_regulator_diffusion(h)
    assert np.isclose(h * diffusion, EXACT_D0_INFINITY_T, rtol=4e-4)
    remainder = diffusion - EXACT_D0_INFINITY_T / h
    assert np.isclose(
        remainder, SPECTRAL_REGULATOR_D1_INFINITY_T, rtol=7e-4
    )


def test_spectral_regulator_scale_correction_is_not_target_pair() -> None:
    correction = finite_field_scale_correction()
    assert np.isclose(correction, -0.2311973, rtol=2e-7)
    coefficient, diffusion = theory_only_scale_corrected_projection(correction)
    assert np.isclose(coefficient, 0.25368176, rtol=2e-7)
    assert np.isclose(diffusion, 1.82385559, rtol=2e-7)

    coefficient, diffusion = theory_only_strong_scale_corrected_projection(
        correction
    )
    assert np.isclose(coefficient, 0.21783469, rtol=2e-7)
    assert np.isclose(diffusion, 1.98557551, rtol=2e-7)


def test_zero_scale_correction_recovers_strong_projection() -> None:
    corrected = theory_only_strong_scale_corrected_projection(0.0)
    leading = theory_only_strong_projection()
    assert np.allclose(corrected, leading, rtol=2e-10, atol=1e-12)


def test_kpz_tcl_generator_runs_and_has_negative_fourth_order_term() -> None:
    times = np.array([50.0, 200.0])
    coefficients = kpz_tcl_gradient_coefficients(times)
    assert np.allclose(coefficients["diffusion"], [3.00570869, 4.77126514])
    assert np.all(coefficients["hyperdiffusion"] < 0.0)
    assert np.isclose(KPZ_SCALING_FOURTH_CUMULANT, -0.04895974316)
    assert np.isclose(
        coefficients["diffusion"][1] / coefficients["diffusion"][0],
        (200.0 / 50.0) ** (1.0 / 3.0),
    )
