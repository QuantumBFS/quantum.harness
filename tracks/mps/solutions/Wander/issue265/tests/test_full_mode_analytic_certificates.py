from __future__ import annotations

import math
import numpy as np
from scipy.linalg import expm

from src.full_mode_analytic_certificates import (
    cubic_diffusion_noise_tadpole_counterterms,
    cubic_velocity_tadpole_counterterm,
    exact_ou_covariance,
    full_fdt_noise_covariance,
    linear_ghd_generator,
    magnetic_local_gge_wall_tangent,
    matrix_free_multiplicative_noise_observable_contact_correction,
    mixed_quadratic_dynamics_observable_correction,
    multiplicative_noise_observable_contact_correction,
    normal_ordered_cubic_velocity_force_memory,
    one_loop_occupation_force_memory,
    one_loop_colored_memory_derivatives_at_zero,
    quadratic_observable_structure_correction,
    one_loop_physical_spin_corrections,
    projected_mori_kernel,
    perturbative_structure_from_memory,
    projected_two_time_structure,
    propagate_matrix_mori_volterra,
    propagate_low_rank_matrix_mori_actions,
    randomized_diffusion_wick_pair,
    randomized_noise_contact_trace,
    randomized_full_vector_velocity_diffusion_wick_pair,
    randomized_full_vector_multiplicative_noise_contact,
    randomized_symmetric_quadratic_wick_pair,
    randomized_velocity_diffusion_wick_pair,
    scalar_galerkin_coefficients,
    sharp_product_wall_mori_certificate,
    spin_flip_projection_certificate,
    static_metric_projection,
    symmetrized_occupation_vertex,
    zero_field_magnetic_wall_string_certificate,
)


def _small_operator():
    velocity = np.asarray([-0.4, 0.2, 0.7])
    diffusion = np.asarray(
        [[1.2, -0.2, 0.0], [-0.1, 0.9, -0.1], [0.0, -0.2, 1.1]]
    )
    covariance = np.diag([0.8, 1.1, 0.6])
    projection = np.asarray([1.0, -0.3, 0.5])
    return velocity, diffusion, covariance, projection


def test_randomized_matrix_free_diffusion_wick_matches_dense_contraction() -> None:
    covariance = np.diag([0.8, 1.1, 0.6])
    vertex = np.asarray(
        [[0.7, -0.2, 0.1], [0.3, -0.4, 0.2], [-0.1, 0.5, 0.6]]
    )
    generator_p = np.asarray(
        [[-0.12, 0.03, 0.0], [-0.01, -0.08, 0.02], [0.0, -0.02, -0.1]],
        dtype=complex,
    ) + 1j * np.diag([0.2, -0.1, 0.05])
    generator_q = np.asarray(
        [[-0.09, -0.01, 0.02], [0.02, -0.11, 0.0], [-0.01, 0.0, -0.07]],
        dtype=complex,
    ) + 1j * np.diag([-0.15, 0.08, 0.03])
    propagator_p = expm(0.7 * generator_p)
    propagator_q = expm(0.7 * generator_q)
    p_symbol = 0.31
    q_symbol = -0.22
    normalization = np.sqrt(8.0)
    gamma = -0.25 / normalization * (
        q_symbol**2 * vertex.T + p_symbol**2 * vertex
    )
    s_p = propagator_p @ covariance
    s_q = propagator_q @ covariance
    exact = 2.0 * np.sum(
        (s_p.T @ gamma) * (gamma.conj() @ s_q.T)
    )
    for distribution in ("gaussian", "rademacher"):
        result = randomized_diffusion_wick_pair(
            lambda vector: vertex @ vector,
            covariance,
            propagator_p,
            propagator_q,
            p_symbol,
            q_symbol,
            fourier_normalization=normalization,
            samples=50_000,
            seed=265,
            trace_distribution=distribution,
        )
        error = abs(result["estimate"] - exact)
        assert error <= 5.0 * result["standard_error_complex_norm"]
        assert error <= 0.03 * abs(exact)


def test_randomized_matrix_free_noise_contact_matches_dense_trace() -> None:
    covariance = np.asarray(
        [[0.8, 0.12, -0.04], [0.12, 1.1, 0.08], [-0.04, 0.08, 0.6]]
    )
    vertex = np.asarray(
        [[0.7, -0.2], [0.3, -0.4], [-0.1, 0.5]]
    )
    exact = float(np.trace(vertex.conj().T @ covariance @ vertex).real)
    for distribution in ("gaussian", "rademacher"):
        result = randomized_noise_contact_trace(
            lambda vector: vertex.T @ vector,
            covariance,
            samples=50_000,
            seed=265,
            trace_distribution=distribution,
        )
        error = abs(float(result["estimate"]) - exact)
        assert error <= 5.0 * float(result["standard_error"])
        assert error <= 0.03 * exact


def test_full_vector_noise_contact_projects_exactly_to_trace_estimator() -> None:
    rng = np.random.default_rng(265)
    modes = 4
    factor = rng.normal(size=(modes, modes))
    covariance = factor @ factor.T + 0.3 * np.eye(modes)
    root_vertex = rng.normal(size=(modes, modes, modes))
    projection = rng.normal(size=modes)

    def directional(vector: np.ndarray) -> np.ndarray:
        return np.einsum("l,lir->ir", vector, root_vertex)

    full = randomized_full_vector_multiplicative_noise_contact(
        directional,
        covariance,
        samples=4096,
        seed=265,
        trace_distribution="rademacher",
    )
    scalar = randomized_noise_contact_trace(
        lambda vector: directional(vector).T @ projection,
        covariance,
        samples=4096,
        seed=265,
        trace_distribution="rademacher",
    )
    projected = projection @ full["matrix_estimate"] @ projection
    assert np.allclose(projected, scalar["estimate"], rtol=2.0e-13, atol=2.0e-13)


def test_randomized_combined_velocity_diffusion_wick_matches_dense() -> None:
    covariance = np.diag([0.8, 1.1, 0.6])
    velocity_action_matrix = np.asarray(
        [[0.4, -0.1, 0.2], [0.0, -0.3, 0.1], [0.2, 0.1, 0.5]]
    )
    diffusion_action_matrix = np.asarray(
        [[0.7, -0.2, 0.1], [0.3, -0.4, 0.2], [-0.1, 0.5, 0.6]]
    )
    generator_p = -0.1 * np.eye(3) + 1j * np.diag([0.2, -0.1, 0.05])
    generator_q = -0.08 * np.eye(3) + 1j * np.diag([-0.15, 0.08, 0.03])
    propagator_p = expm(0.7 * generator_p)
    propagator_q = expm(0.7 * generator_q)
    p_symbol, q_symbol = 0.31, -0.22
    normalization = np.sqrt(8.0)
    gamma_v = -0.5j / normalization * (
        q_symbol * velocity_action_matrix.T
        + p_symbol * velocity_action_matrix
    )
    gamma_d = -0.25 / normalization * (
        q_symbol**2 * diffusion_action_matrix.T
        + p_symbol**2 * diffusion_action_matrix
    )
    s_p = propagator_p @ covariance
    s_q = propagator_q @ covariance

    def wick(gamma: np.ndarray) -> complex:
        return complex(2.0 * np.sum((s_p.T @ gamma) * (gamma.conj() @ s_q.T)))

    exact = {
        "velocity": wick(gamma_v),
        "diffusion": wick(gamma_d),
        "cross": wick(gamma_v + gamma_d) - wick(gamma_v) - wick(gamma_d),
        "total": wick(gamma_v + gamma_d),
    }
    result = randomized_velocity_diffusion_wick_pair(
        lambda vector: velocity_action_matrix @ vector,
        lambda vector: diffusion_action_matrix @ vector,
        covariance,
        propagator_p,
        propagator_q,
        p_symbol,
        q_symbol,
        fourier_normalization=normalization,
        samples=80_000,
        seed=265,
        trace_distribution="rademacher",
    )
    for name, expected in exact.items():
        error = abs(result["estimates"][name] - expected)
        assert error <= 5.0 * result["standard_error_complex_norms"][name]
        assert error <= 0.04 * max(abs(expected), abs(exact["total"]))


def test_full_vector_wick_projects_exactly_to_scalar_estimator() -> None:
    rng = np.random.default_rng(265)
    modes = 4
    factor = rng.normal(size=(modes, modes))
    covariance = factor @ factor.T + 0.4 * np.eye(modes)
    velocity_vertex = rng.normal(size=(modes, modes))
    diffusion_tensor = rng.normal(size=(modes, modes, modes))
    projection = rng.normal(size=modes)
    generator_p = -0.13 * np.eye(modes) + 1j * np.diag(
        [0.21, -0.09, 0.04, -0.17]
    )
    generator_q = -0.08 * np.eye(modes) + 1j * np.diag(
        [-0.14, 0.07, 0.02, 0.11]
    )
    propagator_p = expm(0.6 * generator_p)
    propagator_q = expm(0.6 * generator_q)

    def directional(vector: np.ndarray) -> np.ndarray:
        return np.einsum("l,laj->aj", vector, diffusion_tensor)

    common = dict(
        covariance=covariance,
        propagator_p=propagator_p,
        propagator_q=propagator_q,
        p_symbol=0.29,
        q_symbol=-0.18,
        fourier_normalization=np.sqrt(12.0),
        samples=4096,
        seed=265,
        trace_distribution="rademacher",
    )
    vector_result = randomized_full_vector_velocity_diffusion_wick_pair(
        velocity_vertex,
        directional,
        return_low_rank_factors=True,
        **common,
    )
    scalar_result = randomized_velocity_diffusion_wick_pair(
        lambda vector: (projection[:, None] * velocity_vertex) @ vector,
        lambda vector: directional(vector).T @ projection,
        **common,
    )
    for name in ("velocity", "diffusion", "cross", "total"):
        projected = (
            projection
            @ vector_result["matrix_estimates"][name]
            @ projection
        )
        assert np.allclose(
            projected,
            scalar_result["estimates"][name],
            rtol=2.0e-13,
            atol=2.0e-13,
        )
    assert np.allclose(
        vector_result["total_low_rank_left_factor"]
        @ vector_result["total_low_rank_right_factor"].conj().T,
        vector_result["matrix_estimates"]["total"],
        rtol=2.0e-13,
        atol=2.0e-13,
    )


def test_randomized_quadratic_observable_wick_matches_dense() -> None:
    covariance = np.diag([0.8, 1.1, 0.6])
    hessian = np.asarray(
        [[0.4, -0.1, 0.2], [-0.1, -0.3, 0.1], [0.2, 0.1, 0.5]]
    )
    propagator_p = expm(-0.07 * np.eye(3) + 1j * np.diag([0.2, -0.1, 0.05]))
    propagator_q = expm(-0.09 * np.eye(3) + 1j * np.diag([-0.15, 0.08, 0.03]))
    normalization = np.sqrt(8.0)
    gamma = 0.5 * hessian / normalization
    s_p = propagator_p @ covariance
    s_q = propagator_q @ covariance
    exact = complex(2.0 * np.sum((s_p.T @ gamma) * (gamma.conj() @ s_q.T)))
    result = randomized_symmetric_quadratic_wick_pair(
        lambda vector: hessian @ vector,
        covariance,
        propagator_p,
        propagator_q,
        fourier_normalization=normalization,
        samples=50_000,
        seed=265,
        trace_distribution="rademacher",
    )
    error = abs(result["estimate"] - exact)
    assert error <= 5.0 * result["standard_error_complex_norm"]
    assert error <= 0.03 * abs(exact)


def test_stationary_ou_covariance_is_preserved_without_sampling() -> None:
    velocity, diffusion, covariance, _ = _small_operator()
    generator = linear_ghd_generator(0.17, velocity, diffusion)
    result = exact_ou_covariance(
        generator, covariance, covariance, np.asarray([0.0, 0.4, 1.0])
    )
    assert np.allclose(result["covariances"], covariance[None, :, :], atol=2e-14)
    for innovation in result["accumulated_noise_covariances"]:
        assert np.min(np.linalg.eigvalsh(innovation)) >= -1e-12


def test_full_fdt_noise_keeps_off_diagonal_diffusion_and_closes_lyapunov() -> None:
    velocity, diffusion, covariance, _ = _small_operator()
    generator = linear_ghd_generator(0.31, velocity, diffusion)
    result = full_fdt_noise_covariance(generator, covariance)
    noise = result["noise_covariance"]
    assert np.linalg.norm(noise - np.diag(np.diag(noise))) > 1.0e-4
    assert result["positive_semidefinite_within_roundoff"]
    assert result["relative_lyapunov_residual"] < 1.0e-14


def test_matrix_mori_volterra_reduces_to_exact_linear_propagator() -> None:
    velocity, diffusion, covariance, _ = _small_operator()
    generator = linear_ghd_generator(0.17, velocity, diffusion)
    times = np.linspace(0.0, 1.0, 11)
    result = propagate_matrix_mori_volterra(
        generator,
        covariance,
        times,
        np.zeros((times.size, 3, 3), dtype=complex),
    )
    exact = np.asarray([expm(time * generator) for time in times])
    assert np.allclose(result["response"], exact, rtol=2.0e-14, atol=2.0e-14)
    assert np.allclose(result["two_time_covariance"], exact @ covariance)


def test_low_rank_matrix_mori_actions_equal_dense_volterra_columns() -> None:
    rng = np.random.default_rng(265)
    velocity, diffusion, covariance, _ = _small_operator()
    generator = linear_ghd_generator(0.17, velocity, diffusion)
    times = np.linspace(0.0, 0.5, 6)
    left = 0.02 * rng.normal(size=(times.size, 3, 2))
    right = 0.02 * rng.normal(size=(times.size, 3, 2))
    memory = np.einsum("tir,tjr->tij", left, right.conj())
    sources = rng.normal(size=(3, 4))
    dense = propagate_matrix_mori_volterra(
        generator, covariance, times, memory
    )
    low_rank = propagate_low_rank_matrix_mori_actions(
        generator, covariance, times, left, right, sources
    )
    assert np.allclose(
        low_rank["response_actions"],
        dense["response"] @ sources,
        rtol=2.0e-13,
        atol=2.0e-13,
    )


def test_cubic_velocity_tadpole_is_exactly_removed_by_wick_counterterm() -> None:
    hessian = np.zeros((2, 2, 2))
    hessian[0] = np.asarray([[0.4, -0.1], [-0.1, 0.2]])
    hessian[1] = np.asarray([[-0.3, 0.05], [0.05, 0.1]])
    covariance = np.asarray([[0.8, 0.2], [0.2, 0.5]])
    result = cubic_velocity_tadpole_counterterm(
        hessian, covariance, spatial_cell_length=2.0
    )
    expected = 0.25 * np.einsum("abc,bc->a", hessian, covariance)
    assert np.allclose(result["bare_cubic_tadpole_velocity_shift"], expected)
    assert np.allclose(
        result["equilibrium_normal_ordering_counterterm"], -expected
    )
    assert result["maximum_absolute_cancellation_residual"] == 0.0
    assert result["one_cubic_vertex_two_point_correction_after_normal_ordering"] == 0.0


def test_cubic_diffusion_noise_tadpoles_keep_Bprime_contact_separate() -> None:
    covariance = np.diag([0.8, 0.5])
    diffusion_second = np.arange(8, dtype=float).reshape(2, 2, 2) / 10.0
    noise_second = np.arange(12, dtype=float).reshape(2, 2, 3) / 7.0
    result = cubic_diffusion_noise_tadpole_counterterms(
        diffusion_second,
        noise_second,
        covariance,
        spatial_cell_length=2.0,
    )
    weights = np.diag(covariance) / 4.0
    assert np.allclose(
        result["bare_cubic_diffusion_tadpole"],
        np.einsum("c,cab->ab", weights, diffusion_second),
    )
    assert np.allclose(
        result["bare_cubic_noise_root_tadpole"],
        np.einsum("c,car->ar", weights, noise_second),
    )
    assert result["maximum_diffusion_cancellation_residual"] == 0.0
    assert result["maximum_noise_root_cancellation_residual"] == 0.0
    assert result["multiplicative_Bprime_Bprime_contact_removed"] is False


def test_normal_ordered_scalar_cubic_memory_has_six_wick_pairings() -> None:
    waves = 0.2 * (np.fft.fftfreq(4) * 4)
    covariance = np.asarray([[0.7]])
    hessian = np.asarray([[[0.3]]])
    result = normal_ordered_cubic_velocity_force_memory(
        waves,
        1,
        np.asarray([0.0]),
        np.asarray([[0.0]]),
        covariance,
        hessian,
        np.asarray([1.0]),
        np.asarray([0.0, 1.0]),
        spatial_cell_length=2.0,
    )
    expected = (
        result["dealiased_ordered_momentum_triplets"]
        / waves.size**2
        * 0.3**2
        * 0.7**2
        / (6.0 * 2.0**2)
    )
    assert np.allclose(result["continuity_normalized_cubic_memory"], expected)
    assert result["wick_cross_pairings"] == 6
    assert result["first_order_cubic_correction_after_normal_ordering"] == 0.0
    assert result["zero_time_nonnegative"] is True


def test_projected_mori_identity_matches_resolvent_exactly() -> None:
    velocity, diffusion, covariance, projection = _small_operator()
    k = 0.11
    generator = linear_ghd_generator(k, velocity, diffusion)
    z = np.asarray([0.05, 0.2, 0.7])
    result = projected_mori_kernel(
        generator,
        covariance,
        projection,
        k,
        z,
        lattice_wave_number=lambda value: 2.0 * np.sin(value / 2.0),
    )
    assert result["maximum_resolvent_inversion_residual"] < 2e-15
    time_values = projected_two_time_structure(
        generator, covariance, projection, np.asarray([0.0])
    )
    assert np.allclose(time_values, 1.0)


def test_static_metric_projection_is_exactly_orthogonal() -> None:
    covariance = np.diag([0.5, 2.0, 1.5])
    tangent = np.asarray([1.0, 0.5, -0.2])
    perpendicular = np.asarray([0.2, -0.4, 0.1])
    perpendicular -= tangent * (
        tangent @ np.linalg.solve(covariance, perpendicular)
    ) / (tangent @ np.linalg.solve(covariance, tangent))
    result = static_metric_projection(
        1.7 * tangent + perpendicular, tangent, covariance
    )
    assert np.isclose(result["coefficient"], 1.7)
    assert abs(result["orthogonality_residual"]) < 1e-14
    assert np.allclose(result["perpendicular"], perpendicular)


def test_spin_flip_certificate_distinguishes_two_vertices() -> None:
    result = spin_flip_projection_certificate()
    assert result["physical_zero_field_quadratic_kubo_vertex"] == 0.0
    assert result["conditional_quadratic_basis_coordinate_may_be_nonzero"] is True
    assert result["objects_are_identical"] is False


def test_weak_local_gge_wall_is_parallel_to_spin_tangent() -> None:
    _, _, covariance, projection = _small_operator()
    profile = np.tanh(np.linspace(-2.0, 2.0, 17)) * 0.03
    result = magnetic_local_gge_wall_tangent(profile, covariance, projection)
    tangent = covariance @ projection
    assert np.allclose(
        result["mode_profile_linear_response"], tangent[:, None] * profile[None, :]
    )
    assert result["linear_order_orthogonal_fraction"] == 0.0
    assert result["non_local_gge_initial_slip_controlled"] is False


def test_symmetrized_vertex_exchanges_incoming_legs() -> None:
    vertex = np.asarray([[0.1, -0.3], [0.4, 0.2]])
    for output in range(2):
        gamma_pq = symmetrized_occupation_vertex(
            vertex, output, 0.7, -0.2, fourier_points=8
        )
        gamma_qp = symmetrized_occupation_vertex(
            vertex, output, -0.2, 0.7, fourier_points=8
        )
        assert np.allclose(gamma_pq, gamma_qp.T)


def test_one_loop_force_memory_is_positive_and_quadratic_in_vertex() -> None:
    velocity, diffusion, covariance, projection = _small_operator()
    waves = 2.0 * np.pi * np.fft.fftfreq(8, d=2.0)
    vertex = np.asarray(
        [[0.2, -0.1, 0.0], [0.05, 0.1, -0.03], [-0.08, 0.04, 0.12]]
    )
    base = one_loop_occupation_force_memory(
        waves,
        1,
        velocity,
        diffusion,
        covariance,
        vertex,
        projection,
        np.asarray([0.0, 0.2]),
    )
    doubled = one_loop_occupation_force_memory(
        waves,
        1,
        velocity,
        diffusion,
        covariance,
        2.0 * vertex,
        projection,
        np.asarray([0.0, 0.2]),
    )
    assert base["zero_time_minimum_eigenvalue"] >= -1e-12
    assert np.allclose(
        doubled["projected_force_memory"],
        4.0 * np.asarray(base["projected_force_memory"]),
    )
    assert base["first_order_two_point_correction"] == 0.0
    assert base["complete_physical_F1_perp"] is False
    assert base["running_markov_diffusion_correction"][0] == 0.0


def test_full_quadratic_wick_contraction_reduces_to_velocity_one_loop() -> None:
    velocity, diffusion, covariance, projection = _small_operator()
    waves = 2.0 * np.pi * np.fft.fftfreq(8, d=2.0)
    vertex = np.asarray(
        [[0.2, -0.1, 0.0], [0.05, 0.1, -0.03], [-0.08, 0.04, 0.12]]
    )
    times = np.asarray([0.0, 0.2])
    base = one_loop_occupation_force_memory(
        waves, 1, velocity, diffusion, covariance, vertex, projection, times
    )
    zeros = np.zeros((3, 3, 3))
    full = one_loop_physical_spin_corrections(
        waves,
        1,
        velocity,
        diffusion,
        covariance,
        vertex,
        zeros,
        zeros,
        projection,
        np.zeros((3, 3)),
        times,
        noise_covariance=0.5 * (
            diffusion @ covariance + covariance @ diffusion.T
        ),
    )
    assert np.allclose(
        full["velocity_force_memory"],
        base["projected_force_memory"],
        rtol=1.0e-12,
        atol=1.0e-12,
    )
    assert np.allclose(full["diffusion_force_memory"], 0.0)
    assert np.allclose(full["quadratic_observable_structure_correction"], 0.0)
    assert full["full_off_diagonal_diffusion_retained"] is True
    assert full["full_fdt_noise_covariance_retained"] is True
    assert np.allclose(
        full["total_colored_force_memory"],
        np.asarray(full["velocity_force_memory"])
        + np.asarray(full["diffusion_force_memory"])
        + np.asarray(full["velocity_diffusion_cross_memory"]),
    )


def test_colored_memory_zero_time_derivatives_reconstruct_short_time_kernel() -> None:
    velocity, diffusion, covariance, projection = _small_operator()
    waves = 2.0 * np.pi * np.fft.fftfreq(8, d=2.0)
    vertex = np.asarray(
        [[0.2, -0.1, 0.0], [0.05, 0.1, -0.03], [-0.08, 0.04, 0.12]]
    )
    derivative = np.zeros((3, 3, 3))
    derivative[0, 0, 1] = 0.07
    derivative[1, 2, 0] = -0.04
    zeros = np.zeros((3, 3, 3))
    h = 1.0e-3
    direct = one_loop_physical_spin_corrections(
        waves,
        1,
        velocity,
        diffusion,
        covariance,
        vertex,
        derivative,
        zeros,
        projection,
        np.zeros((3, 3)),
        np.asarray([0.0, h]),
    )
    expansion = one_loop_colored_memory_derivatives_at_zero(
        waves,
        1,
        velocity,
        diffusion,
        covariance,
        vertex,
        derivative,
        projection,
        maximum_order=6,
    )
    coefficients = np.asarray(expansion["total_colored_continuity_derivatives"])
    reconstructed = sum(
        coefficients[n] * h**n / math.factorial(n)
        for n in range(coefficients.size)
    )
    assert np.allclose(
        reconstructed,
        np.asarray(direct["total_colored_continuity_memory"])[1],
        rtol=1.0e-11,
        atol=1.0e-11,
    )
    assert np.allclose(
        coefficients[0],
        np.asarray(direct["total_colored_continuity_memory"])[0],
    )


def test_lattice_symbol_is_used_inside_propagators_and_vertices() -> None:
    velocity, diffusion, covariance, projection = _small_operator()
    waves = 2.0 * np.pi * np.fft.fftfreq(8)
    vertex = np.asarray(
        [[0.2, -0.1, 0.0], [0.05, 0.1, -0.03], [-0.08, 0.04, 0.12]]
    )
    derivative = np.zeros((3, 3, 3))
    derivative[0, 0, 1] = 0.07
    derivative[1, 2, 0] = -0.04
    zeros = np.zeros((3, 3, 3))
    symbol = lambda wave: 2.0 * np.sin(wave / 2.0)
    h = 2.0e-4
    direct = one_loop_physical_spin_corrections(
        waves,
        1,
        velocity,
        diffusion,
        covariance,
        vertex,
        derivative,
        zeros,
        projection,
        np.zeros((3, 3)),
        np.asarray([0.0, h]),
        spatial_cell_length=1.0,
        lattice_wave_number=symbol,
    )
    expansion = one_loop_colored_memory_derivatives_at_zero(
        waves,
        1,
        velocity,
        diffusion,
        covariance,
        vertex,
        derivative,
        projection,
        maximum_order=6,
        spatial_cell_length=1.0,
        lattice_wave_number=symbol,
    )
    coefficients = np.asarray(expansion["total_colored_continuity_derivatives"])
    reconstructed = sum(
        coefficients[n] * h**n / math.factorial(n)
        for n in range(coefficients.size)
    )
    assert np.allclose(
        reconstructed,
        np.asarray(direct["total_colored_continuity_memory"])[1],
        rtol=1.0e-11,
        atol=1.0e-11,
    )
    assert direct["internal_lattice_wave_number_retained"] is True
    assert expansion["internal_lattice_wave_number_retained"] is True

    external_only = one_loop_physical_spin_corrections(
        waves,
        1,
        velocity,
        diffusion,
        covariance,
        vertex,
        derivative,
        zeros,
        projection,
        np.zeros((3, 3)),
        np.asarray([0.0, h]),
        spatial_cell_length=1.0,
    )
    assert not np.allclose(
        np.asarray(direct["total_colored_continuity_memory"]),
        np.asarray(external_only["total_colored_continuity_memory"]),
    )


def test_mixed_gamma_h_correction_has_the_expected_multilinear_scaling() -> None:
    velocity, diffusion, covariance, projection = _small_operator()
    waves = 2.0 * np.pi * np.fft.fftfreq(4, d=2.0)
    vertex = np.asarray(
        [[0.2, -0.1, 0.0], [0.05, 0.1, -0.03], [-0.08, 0.04, 0.12]]
    )
    derivative = np.zeros((3, 3, 3))
    derivative[0] = np.asarray(
        [[0.03, -0.01, 0.0], [0.0, 0.02, -0.01], [0.01, 0.0, -0.02]]
    )
    derivative[1] = -0.4 * derivative[0]
    derivative[2] = 0.2 * derivative[0]
    hessian = np.asarray(
        [[0.2, -0.03, 0.0], [-0.03, 0.1, 0.02], [0.0, 0.02, -0.08]]
    )
    times = np.linspace(0.0, 0.2, 5)
    kwargs = dict(
        wave_numbers=waves,
        external_index=1,
        velocity=velocity,
        diffusion=diffusion,
        covariance=covariance,
        spin_projection=projection,
        integration_times=times,
        output_times=np.asarray([0.0, 0.1, 0.2]),
    )
    base = mixed_quadratic_dynamics_observable_correction(
        velocity_vertex=vertex,
        diffusion_derivative=derivative,
        spin_hessian=hessian,
        **kwargs,
    )
    doubled_hessian = mixed_quadratic_dynamics_observable_correction(
        velocity_vertex=vertex,
        diffusion_derivative=derivative,
        spin_hessian=2.0 * hessian,
        **kwargs,
    )
    doubled_vertices = mixed_quadratic_dynamics_observable_correction(
        velocity_vertex=2.0 * vertex,
        diffusion_derivative=2.0 * derivative,
        spin_hessian=hessian,
        **kwargs,
    )
    total = np.asarray(base["total_mixed_Gamma_H_structure_correction"])
    assert total[0] == 0.0
    assert np.any(np.abs(total[1:]) > 1.0e-12)
    assert np.allclose(
        doubled_hessian["total_mixed_Gamma_H_structure_correction"],
        2.0 * total,
        rtol=1.0e-12,
        atol=1.0e-12,
    )
    assert np.allclose(
        doubled_vertices["total_mixed_Gamma_H_structure_correction"],
        2.0 * total,
        rtol=1.0e-12,
        atol=1.0e-12,
    )
    assert base["normal_ordered_quadratic_force"] is True
    assert base["complete_physical_F1_perp"] is False


def test_mixed_gamma_h_matrix_contractions_match_explicit_vertex_tensors() -> None:
    velocity, diffusion, covariance, projection = _small_operator()
    waves = 2.0 * np.pi * np.fft.fftfreq(4, d=2.0)
    vertex = np.asarray(
        [[0.2, -0.1, 0.0], [0.05, 0.1, -0.03], [-0.08, 0.04, 0.12]]
    )
    derivative = np.arange(27, dtype=float).reshape(3, 3, 3) / 700.0
    hessian = np.asarray(
        [[0.2, -0.03, 0.0], [-0.03, 0.1, 0.02], [0.0, 0.02, -0.08]]
    )
    times = np.asarray([0.0, 0.05, 0.1])
    result = mixed_quadratic_dynamics_observable_correction(
        waves,
        1,
        velocity,
        diffusion,
        covariance,
        vertex,
        derivative,
        projection,
        hessian,
        times,
        np.asarray([0.1]),
    )
    generators = [
        linear_ghd_generator(wave, velocity, diffusion) for wave in waves
    ]
    transitions = np.asarray(
        [[expm(time * generator) for generator in generators] for time in times]
    )
    cross = transitions @ covariance
    grid = waves.size
    root_grid = np.sqrt(float(grid))
    susceptibility = projection @ covariance @ projection

    def full_gamma(p_wave: float, q_wave: float) -> tuple[np.ndarray, np.ndarray]:
        velocity_tensor = np.asarray(
            [
                symmetrized_occupation_vertex(
                    vertex, output, p_wave, q_wave, fourier_points=grid
                )
                for output in range(3)
            ]
        )
        diffusion_tensor = np.zeros((3, 3, 3), dtype=complex)
        for output in range(3):
            for first in range(3):
                for second in range(3):
                    diffusion_tensor[output, first, second] = (
                        -0.25
                        / root_grid
                        * (
                            q_wave**2 * derivative[first, output, second]
                            + p_wave**2 * derivative[second, output, first]
                        )
                    )
        return velocity_tensor, diffusion_tensor

    explicit = np.zeros((4, times.size), dtype=complex)
    output_index = times.size - 1
    external = 1
    for s_index in range(times.size):
        delay = output_index - s_index
        output_row = projection @ transitions[delay, external]
        external_source = cross[s_index, external] @ projection
        for p_index, p_wave in enumerate(waves):
            q_index = (external - p_index) % grid
            q_wave = waves[q_index]
            gamma_v, gamma_d = full_gamma(p_wave, q_wave)
            wick = cross[s_index, p_index] @ hessian @ cross[s_index, q_index].T
            explicit[0, s_index] += (
                np.einsum("a,abc,bc->", output_row, gamma_v, wick)
                / root_grid
            )
            explicit[1, s_index] += (
                np.einsum("a,abc,bc->", output_row, gamma_d, wick)
                / root_grid
            )
            propagated_hessian = hessian @ transitions[delay, q_index]
            first_cross = cross[delay, p_index]
            minus_p = (-p_index) % grid
            for swapped, component in [(False, 2), (True, 2)]:
                first_wave, second_wave = (
                    (waves[minus_p], waves[external])
                    if not swapped
                    else (waves[external], waves[minus_p])
                )
                gamma_v_endpoint, _ = full_gamma(first_wave, second_wave)
                explicit[component, s_index] += (
                    np.einsum(
                        "aB,Bcd,ac,d->",
                        propagated_hessian,
                        gamma_v_endpoint,
                        first_cross,
                        external_source,
                        optimize=True,
                    )
                    / root_grid
                )
                _, gamma_d_endpoint = full_gamma(first_wave, second_wave)
                explicit[3, s_index] += (
                    np.einsum(
                        "aB,Bcd,ac,d->",
                        propagated_hessian,
                        gamma_d_endpoint,
                        first_cross,
                        external_source,
                        optimize=True,
                    )
                    / root_grid
                )
    expected = np.trapezoid(explicit, x=times, axis=1) / susceptibility
    observed = np.asarray(
        [
            result["initial_observable_endpoint_velocity_H"][0],
            result["initial_observable_endpoint_diffusion_H"][0],
            result["final_observable_endpoint_velocity_H"][0],
            result["final_observable_endpoint_diffusion_H"][0],
        ]
    )
    assert np.allclose(observed, expected, rtol=1.0e-12, atol=1.0e-12)


def test_multiplicative_noise_h_contact_matches_scalar_ito_contraction() -> None:
    waves = 0.2 * (np.fft.fftfreq(4) * 4)
    times = np.asarray([0.0, 0.05, 0.1])
    diffusion_value = 0.7
    covariance_value = 1.3
    noise_value = 0.8
    derivative_value = -0.4
    hessian_value = 0.6
    result = multiplicative_noise_observable_contact_correction(
        waves,
        1,
        np.asarray([0.0]),
        np.asarray([[diffusion_value]]),
        np.asarray([[covariance_value]]),
        np.asarray([[noise_value]]),
        np.asarray([[[derivative_value]]]),
        np.asarray([1.0]),
        np.asarray([[hessian_value]]),
        times,
        np.asarray([0.0, 0.1]),
    )
    external_wave = waves[1]
    integrand = []
    for time in times:
        delay = times[-1] - time
        value = 0.0
        for q_index, q_wave in enumerate(waves):
            r_wave = waves[(1 - q_index) % waves.size]
            value += q_wave * r_wave * np.exp(
                -0.5
                * diffusion_value
                * ((q_wave**2 + r_wave**2) * delay + external_wave**2 * time)
            )
        integrand.append(value)
    expected = (
        -hessian_value
        * noise_value
        * derivative_value
        / waves.size
        * np.trapezoid(integrand, x=times)
    )
    observed = np.asarray(
        result["total_multiplicative_noise_H_structure_correction"]
    )
    assert observed[0] == 0.0
    assert np.isclose(observed[1], expected, rtol=1.0e-12, atol=1.0e-12)
    assert np.allclose(
        result["left_observable_leg_contact"],
        result["right_observable_leg_contact"],
        rtol=1.0e-12,
        atol=1.0e-12,
    )


def test_multiplicative_noise_h_contact_is_bilinear_in_h_and_bprime() -> None:
    velocity, diffusion, covariance, projection = _small_operator()
    waves = 0.1 * (np.fft.fftfreq(4) * 4)
    noise = np.asarray(
        [[0.8, 0.1, 0.0], [0.1, 0.7, 0.05], [0.0, 0.05, 0.6]]
    )
    derivative = np.arange(27, dtype=float).reshape(3, 3, 3) / 500.0
    hessian = np.asarray(
        [[0.2, -0.03, 0.0], [-0.03, 0.1, 0.02], [0.0, 0.02, -0.08]]
    )
    kwargs = dict(
        wave_numbers=waves,
        external_index=1,
        velocity=velocity,
        diffusion=diffusion,
        covariance=covariance,
        noise_root=noise,
        spin_projection=projection,
        integration_times=np.asarray([0.0, 0.05, 0.1]),
        output_times=np.asarray([0.1]),
    )
    base = multiplicative_noise_observable_contact_correction(
        noise_root_derivative=derivative,
        spin_hessian=hessian,
        **kwargs,
    )
    doubled = multiplicative_noise_observable_contact_correction(
        noise_root_derivative=2.0 * derivative,
        spin_hessian=3.0 * hessian,
        **kwargs,
    )
    assert np.allclose(
        doubled["total_multiplicative_noise_H_structure_correction"],
        6.0 * np.asarray(
            base["total_multiplicative_noise_H_structure_correction"]
        ),
        rtol=1.0e-12,
        atol=1.0e-12,
    )


def test_matrix_free_noise_observable_contact_matches_dense_tensor() -> None:
    velocity, diffusion, covariance, projection = _small_operator()
    waves = 2.0 * np.pi * np.fft.fftfreq(4, d=2.0)
    noise_root = np.asarray(
        [[0.7, 0.1, 0.0], [0.1, 0.6, 0.05], [0.0, 0.05, 0.5]]
    )
    derivative = np.arange(27, dtype=float).reshape(3, 3, 3) / 200.0
    derivative = 0.5 * (derivative + derivative.transpose(0, 2, 1))
    hessian = np.asarray(
        [[0.2, -0.03, 0.01], [-0.03, 0.1, 0.02], [0.01, 0.02, -0.08]]
    )
    integration_times = np.linspace(0.0, 0.4, 5)
    output_times = np.asarray([0.0, 0.2, 0.4])
    dense = multiplicative_noise_observable_contact_correction(
        waves,
        1,
        velocity,
        diffusion,
        covariance,
        noise_root,
        derivative,
        projection,
        hessian,
        integration_times,
        output_times,
        spatial_cell_length=2.0,
    )
    matrix_free = matrix_free_multiplicative_noise_observable_contact_correction(
        waves,
        1,
        velocity,
        diffusion,
        covariance,
        noise_root,
        lambda direction: np.einsum("l,lij->ij", direction, derivative),
        projection,
        hessian,
        integration_times,
        output_times,
        spatial_cell_length=2.0,
    )
    for key in (
        "right_observable_leg_contact",
        "left_observable_leg_contact",
        "total_multiplicative_noise_H_structure_correction",
    ):
        assert np.allclose(matrix_free[key], dense[key], rtol=1e-12, atol=1e-12)
    assert matrix_free["rank_three_noise_root_derivative_stored"] is False


def test_scalar_galerkin_coefficients_are_exact_for_invariant_tangent() -> None:
    covariance = np.diag([2.0, 3.0])
    spin = np.asarray([1.0, 0.0])
    velocity = np.asarray([0.4, -0.7])
    diffusion = np.diag([1.2, 2.0])
    vertex = np.asarray([[0.5, 0.0], [0.0, -0.2]])
    result = scalar_galerkin_coefficients(
        velocity, diffusion, covariance, vertex, spin
    )
    assert np.isclose(result["background_advection_c"], 0.4)
    assert np.isclose(result["diffusion_D"], 0.6)
    assert np.isclose(result["burgers_A_physical_galerkin"], 0.5)
    assert result["advective_orthogonal_fraction"] == 0.0
    assert result["diffusive_orthogonal_fraction"] == 0.0
    assert result["nonlinear_orthogonal_fraction"] == 0.0
    assert result["scalar_closure_controlled_by_projection_alone"] is True


def test_zero_field_wall_sign_escapes_every_fixed_string_cutoff() -> None:
    result = zero_field_magnetic_wall_string_certificate(
        np.arange(1, 9), 0.03
    )
    assert np.allclose(result["opposite_wall_filling_difference"], 0.0)
    assert np.allclose(result["fixed_string_linear_derivative_at_zero"], 0.0)
    assert result["physical_susceptibility"] > 0.0
    assert result["finite_string_linear_response_matches_physical_spin"] is False
    assert result["missing_linear_spin_weight_fraction"] == 1.0
    assert result["augmented_mapping_linear_orthogonal_fraction"] == 0.0
    assert result["limits_commute"] is False


def test_quadratic_observable_correction_is_positive_and_scales_as_hessian_squared() -> None:
    velocity, diffusion, covariance, projection = _small_operator()
    waves = 2.0 * np.pi * np.fft.fftfreq(8, d=2.0)
    hessian = np.asarray(
        [[0.2, -0.03, 0.0], [-0.03, 0.1, 0.02], [0.0, 0.02, -0.08]]
    )
    base = quadratic_observable_structure_correction(
        waves,
        1,
        velocity,
        diffusion,
        covariance,
        hessian,
        projection,
        np.asarray([0.0, 0.2]),
    )
    doubled = quadratic_observable_structure_correction(
        waves,
        1,
        velocity,
        diffusion,
        covariance,
        2.0 * hessian,
        projection,
        np.asarray([0.0, 0.2]),
    )
    assert base["zero_time_correction"] >= 0.0
    assert np.allclose(
        doubled["normalized_H2_structure_correction"],
        4.0 * np.asarray(base["normalized_H2_structure_correction"]),
    )
    assert base["linear_quadratic_cross_correction"] == 0.0


def test_memory_dyson_correction_starts_at_zero_and_scales_linearly() -> None:
    times = np.linspace(0.0, 2.0, 101)
    leading = np.exp(-0.3 * times)
    memory = 0.2 * np.exp(-0.7 * times)
    base = perturbative_structure_from_memory(times, leading, memory, 0.1)
    doubled = perturbative_structure_from_memory(
        times, leading, 2.0 * memory, 0.1
    )
    assert base["initial_value_residual"] == 0.0
    assert np.allclose(
        doubled["structure_correction"],
        2.0 * np.asarray(base["structure_correction"]),
    )
    assert np.real(base["structure_correction"][-1]) < 0.0


def test_sharp_product_wall_has_no_linear_mori_initial_slip() -> None:
    result = sharp_product_wall_mori_certificate(
        np.asarray([0.02, 0.05, 0.10, 0.20])
    )
    assert result["linear_operator_inside_spin_density_mori_subspace"] is True
    assert result["linear_mori_initial_slip"] == 0.0
    assert result["profile_smoothness_required_for_linear_mori_statement"] is False
    assert np.isclose(result["maximum_bare_power_mu6"], 0.2**6)
