import numpy as np

from scripts.evaluate_full_tba_diffusion import (
    _dressed_kernel_rows_fourier,
    _zero_field_edge_kernel_rows_fourier,
    fixed_string_inner_weights_field,
    full_diffusion_operator_field_adaptive_rapidity,
    zero_field_edge_weights,
)
from src.infinite_mode_fluctuating_ghd import (
    complement_invariants,
    direct_full_noise_spin_covariance,
    exact_spin_mori_resolvent,
    krylov_spin_mori_resolvent,
    krylov_spin_structure_factor,
    joint_scaled_spin_structure_grid,
    physical_spin_basis,
    physical_spin_invariants,
    stationary_spin_structure_factor,
)
from src.heisenberg_burgers_bridge import (
    giant_dressed_scattering_common_shift_derivative_fourier_kernel,
    giant_dressed_scattering_fourier_kernel,
)


def test_physical_spin_rotation_retains_full_fdt_operator():
    covariance = np.diag([2.0, 3.0, 5.0])
    diffusion = np.array(
        [[2.0, 0.4, -0.2], [0.1, 1.5, 0.3], [-0.5, 0.2, 1.0]]
    )
    noise = 0.5 * (diffusion @ covariance + covariance @ diffusion.T)
    projection = np.array([1.0, -0.5, 0.25])
    result = physical_spin_basis(
        diffusion,
        covariance,
        noise,
        projection,
        velocity=np.array([-1.0, 0.2, 0.7]),
    )
    assert np.allclose(result["rotation"].T @ result["rotation"], np.eye(3))
    assert np.isclose(result["susceptibility"], projection @ covariance @ projection)
    assert result["fdt_residual"] < 1.0e-13
    assert result["diffusion"].shape == (3, 3)
    assert result["noise_covariance"].shape == (3, 3)
    # The first whitened block is exactly the physical Kubo contraction,
    # not a bare occupation-space diagonal entry.
    expected_spin_diffusion = (
        projection @ diffusion @ covariance @ projection
        / (projection @ covariance @ projection)
    )
    assert np.isclose(result["spin_diffusion"], expected_spin_diffusion)
    invariants = physical_spin_invariants(
        diffusion,
        covariance,
        noise,
        projection,
        velocity=np.array([-1.0, 0.2, 0.7]),
    )
    for key in (
        "susceptibility",
        "fdt_residual",
        "spin_diffusion",
        "spin_noise",
        "spin_to_orthogonal_diffusion_norm",
        "orthogonal_to_spin_diffusion_norm",
        "spin_orthogonal_noise_norm",
        "spin_velocity",
        "spin_orthogonal_velocity_norm",
    ):
        assert np.isclose(invariants[key], result[key])


def test_stationary_propagation_uses_cross_blocks_and_noise_identity():
    velocity = np.array([[0.0, 0.3], [0.3, 0.1]])
    diffusion = np.array([[2.0, 0.5], [0.1, 1.0]])
    noise = 0.5 * (diffusion + diffusion.T)
    propagated = stationary_spin_structure_factor(
        velocity, diffusion, noise, 0.2, np.array([0.0, 1.0, 2.0])
    )
    structure = propagated["structure_factor_over_susceptibility"]
    assert propagated["stationarity_residual"] < 1.0e-13
    assert np.isclose(structure[0], 1.0)
    assert not np.isclose(structure[-1], np.exp(-0.5 * 2.0 * 0.2**2 * 2.0))


def test_complement_diagnostics_are_basis_independent_norms():
    operator = np.array([[1.0, 2.0, 0.0], [3.0, 4.0, 0.0], [0.0, 0.0, 5.0]])
    result = complement_invariants(operator)
    assert np.isclose(result["spin_to_complement_norm"], 3.0)
    assert np.isclose(result["complement_to_spin_norm"], 2.0)
    assert np.isclose(result["round_trip_scalar"], 6.0)


def test_exact_mori_resolvent_reduces_to_scalar_diffusion():
    velocity = np.zeros((2, 2))
    diffusion = np.diag([4.0, 7.0])
    result = exact_spin_mori_resolvent(velocity, diffusion, 0.1, 0.02)
    assert np.isclose(result["continuity_memory"], 2.0)
    assert np.isclose(result["orthogonal_memory_correction"], 0.0)


def test_exact_mori_resolvent_keeps_non_pole_complement():
    velocity = np.zeros((3, 3))
    diffusion = np.array([[2.0, 0.3, 0.1], [0.4, 1.0, 0.2], [0.2, 0.1, 3.0]])
    low = exact_spin_mori_resolvent(velocity, diffusion, 0.2, 0.01)
    high = exact_spin_mori_resolvent(velocity, diffusion, 0.2, 0.1)
    assert not np.isclose(
        low["orthogonal_memory_correction"],
        high["orthogonal_memory_correction"],
    )


def test_complement_free_krylov_equals_explicit_full_rotation():
    covariance = np.diag([0.7, 1.3, 2.1])
    diffusion = np.array(
        [[2.0, 0.4, -0.1], [0.2, 1.5, 0.3], [-0.2, 0.1, 0.9]]
    )
    noise = 0.5 * (diffusion @ covariance + covariance @ diffusion.T)
    projection = np.array([1.0, -0.4, 0.2])
    velocity_diagonal = np.array([-0.7, 0.2, 0.9])
    basis = physical_spin_basis(
        diffusion,
        covariance,
        noise,
        projection,
        velocity=velocity_diagonal,
    )
    times = np.array([0.0, 0.7, 1.4])
    dense = stationary_spin_structure_factor(
        basis["velocity"],
        basis["diffusion"],
        basis["noise_covariance"],
        0.13,
        times,
    )
    krylov = krylov_spin_structure_factor(
        velocity_diagonal,
        diffusion,
        covariance,
        noise,
        projection,
        0.13,
        times,
    )
    assert np.allclose(
        krylov["structure_factor_over_susceptibility"],
        dense["structure_factor_over_susceptibility"],
        rtol=1.0e-11,
        atol=1.0e-12,
    )
    assert krylov["stationarity_residual"] < 1.0e-12
    assert np.allclose(krylov["total_equal_time_covariance"], 1.0)
    assert np.all(
        krylov["equal_time_covariance_from_accumulated_full_noise"] >= -1.0e-12
    )

    dense_mori = exact_spin_mori_resolvent(
        basis["velocity"], basis["diffusion"], 0.13, 0.04
    )
    krylov_mori = krylov_spin_mori_resolvent(
        velocity_diagonal,
        diffusion,
        covariance,
        noise,
        projection,
        0.13,
        0.04,
    )
    assert krylov_mori["gmres_info"] == 0
    assert krylov_mori["linear_solve_relative_residual"] < 1.0e-9
    for key in (
        "spin_structure_resolvent",
        "continuity_memory",
        "bare_spin_memory",
        "orthogonal_memory_correction",
    ):
        assert np.isclose(krylov_mori[key], dense_mori[key], rtol=1.0e-9)


def test_direct_full_nondiagonal_noise_propagation_matches_fdt_identity():
    covariance = np.diag([0.7, 1.3, 2.1])
    diffusion = np.array(
        [[2.0, 0.4, -0.1], [0.2, 1.5, 0.3], [-0.2, 0.1, 0.9]]
    )
    noise = 0.5 * (diffusion @ covariance + covariance @ diffusion.T)
    projection = np.array([1.0, -0.4, 0.2])
    velocity = np.array([-0.7, 0.2, 0.9])
    result = direct_full_noise_spin_covariance(
        velocity,
        diffusion,
        covariance,
        noise,
        projection,
        0.23,
        np.array([0.0, 0.7, 1.4, 2.1]),
        quadrature_order=12,
    )
    assert result["method"] == "direct_full_dense_nondiagonal_noise_quadrature"
    assert np.allclose(
        result["equal_time_covariance_from_direct_full_noise"],
        result["equal_time_covariance_from_fdt_identity"],
        rtol=2.0e-11,
        atol=2.0e-13,
    )
    assert np.allclose(
        result["equal_time_covariance_from_diagonal_noise_only"]
        + result["equal_time_covariance_from_offdiagonal_noise"],
        result["equal_time_covariance_from_direct_full_noise"],
    )
    assert not np.allclose(
        result["equal_time_covariance_from_diagonal_noise_only"],
        result["equal_time_covariance_from_direct_full_noise"],
    )
    assert np.allclose(result["total_equal_time_covariance_direct"], 1.0)


def test_joint_scaled_grid_reduces_to_field_independent_scalar_diffusion():
    field = 0.2
    d0 = 0.7
    diffusion = np.asarray([[d0 / field]])
    covariance = np.asarray([[1.3]])
    noise = diffusion @ covariance
    q = np.asarray([0.0, 0.5, 1.0, 2.0])
    tau = 0.8
    result = joint_scaled_spin_structure_grid(
        np.asarray([0.0]),
        diffusion,
        covariance,
        noise,
        np.asarray([1.0]),
        field,
        q,
        tau,
        lattice_wave_number=False,
    )
    expected = np.exp(-0.5 * d0 * tau * q**2)
    assert np.allclose(
        result["structure_factor_over_susceptibility"], expected, atol=1.0e-12
    )


def test_string_adaptive_quadrature_resolves_static_spin_and_fdt():
    raw = full_diffusion_operator_field_adaptive_rapidity(
        0.25,
        string_xi_cutoff=4.0,
        string_xi_buffer=2.0,
        scaled_rapidity_extent=10.0,
        scaled_rapidity_map_alpha=3.0,
        nodes_per_string=32,
        kernel_theta_step=0.25,
    )
    basis = physical_spin_basis(
        raw["diffusion_operator"],
        raw["static_covariance"],
        raw["noise_covariance"],
        raw["spin_projection"],
        velocity=raw["velocity"],
    )
    exact = 1.0 / (4.0 * np.cosh(0.25) ** 2)
    assert 0.90 < basis["susceptibility"] / exact < 1.0
    assert basis["fdt_residual"] < 1.0e-12


def test_selected_fixed_string_rows_reproduce_full_contractions():
    field = 0.2
    cutoff = 2.0
    nodes = 8
    selected = np.arange(1, int(np.ceil(cutoff / field)) + 1)
    rows = fixed_string_inner_weights_field(
        field,
        selected,
        partner_xi_cutoff=cutoff,
        partner_xi_buffer=3.0,
        rapidity_ratio_extent=6.0,
        nodes_per_string=nodes,
        kernel_theta_step=0.25,
    )
    full = full_diffusion_operator_field_adaptive_rapidity(
        field,
        string_xi_cutoff=cutoff,
        string_xi_buffer=3.0,
        scaled_rapidity_extent=6.0,
        nodes_per_string=nodes,
        kernel_theta_step=0.25,
    )
    covariance = full["static_covariance"]
    projection = full["spin_projection"]
    cutoff_chi = float(projection @ covariance @ projection)
    contracted_full = float(
        projection
        @ full["diffusion_operator"]
        @ covariance
        @ projection
        / cutoff_chi
    )
    contracted_diagonal = float(
        projection
        @ (2.0 * np.diag(full["collision_rate"]))
        @ covariance
        @ projection
        / cutoff_chi
    )
    row_diagonal = sum(row["diagonal_weight"] for row in rows["rows"])
    row_cross = sum(row["cross_weight"] for row in rows["rows"])
    normalization = 0.25 / cutoff_chi
    # The selected-row path uses float32 Fourier storage and a separately
    # reconstructed symmetric row, so agreement is limited by interpolation.
    assert np.isclose(
        row_diagonal * normalization, contracted_diagonal, rtol=3.0e-3
    )
    assert np.isclose(
        row_cross * normalization,
        contracted_diagonal - contracted_full,
        rtol=3.0e-3,
    )


def test_closed_edge_kernel_matches_small_field_discrete_dressing():
    selected = np.asarray([1, 3, 7])
    momenta = np.asarray([0.2, 0.7, 1.4])
    exact = _zero_field_edge_kernel_rows_fourier(
        momenta, left_strings=selected, partner_strings=10
    )
    finite = _dressed_kernel_rows_fourier(
        1.0e-4,
        momenta,
        left_strings=selected,
        active_strings=10,
        solve_strings=160,
        boundary="robin",
    )
    np.testing.assert_allclose(finite, exact, rtol=3.0e-5, atol=2.0e-6)


def test_natural_giant_coordinate_removes_dressed_kernel_linear_field_term():
    x = 1.2
    y = 0.8
    scaled_wave_number = 0.7
    leading = float(
        giant_dressed_scattering_fourier_kernel(x, y, scaled_wave_number)
    )
    old_coordinate_first = float(
        giant_dressed_scattering_common_shift_derivative_fourier_kernel(
            x, y, scaled_wave_number
        )
    )
    natural_first_differences = []
    old_first_differences = []
    natural_second_differences = []
    for field in (0.04, 0.02, 0.01):
        active_strings = int(np.ceil(2.5 / field))
        solve_strings = active_strings + int(np.ceil(4.0 / field)) + 2
        natural_left = int(round(x / field - 1.0))
        natural_right = int(round(y / field - 1.0))
        old_left = int(round(x / field))
        old_right = int(round(y / field))
        natural = _dressed_kernel_rows_fourier(
            field,
            np.asarray([field * scaled_wave_number]),
            left_strings=np.asarray([natural_left]),
            active_strings=active_strings,
            solve_strings=solve_strings,
        )[0, 0, natural_right - 1]
        old = _dressed_kernel_rows_fourier(
            field,
            np.asarray([field * scaled_wave_number]),
            left_strings=np.asarray([old_left]),
            active_strings=active_strings,
            solve_strings=solve_strings,
        )[0, 0, old_right - 1]
        natural_first_differences.append((field * natural - leading) / field)
        natural_second_differences.append(
            (field * natural - leading) / field**2
        )
        old_first_differences.append((field * old - leading) / field)

    assert abs(natural_first_differences[-1]) < 1.0e-3
    assert abs(natural_first_differences[-1]) < 0.3 * abs(
        natural_first_differences[0]
    )
    assert np.ptp(natural_second_differences) < 8.0e-4
    assert abs(old_first_differences[-1] - old_coordinate_first) < 3.0e-3


def test_edge_weights_match_fixed_string_small_field_limit():
    selected = np.asarray([1, 2, 4])
    cutoff = 32
    edge = zero_field_edge_weights(
        selected,
        partner_string_cutoff=cutoff,
        rapidity_ratio_extent=6.0,
        nodes_per_string=12,
        kernel_theta_step=0.5,
    )
    field = 0.002
    finite = fixed_string_inner_weights_field(
        field,
        selected,
        partner_xi_cutoff=field * cutoff,
        partner_xi_buffer=0.25,
        rapidity_ratio_extent=6.0,
        nodes_per_string=12,
        kernel_theta_step=0.5,
    )
    for edge_row, finite_row in zip(edge["rows"], finite["rows"]):
        assert edge_row["string"] == finite_row["string"]
        assert np.isclose(
            finite_row["diagonal_weight"] / field**2,
            edge_row["diagonal_per_field_squared"],
            rtol=1.5e-2,
        )
        assert np.isclose(
            finite_row["cross_weight"] / field**2,
            edge_row["cross_per_field_squared"],
            rtol=1.5e-2,
        )
