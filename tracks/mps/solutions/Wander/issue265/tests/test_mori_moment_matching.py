from __future__ import annotations

import math
import numpy as np

from src.heisenberg_burgers_bridge import (
    mori_kernel_from_lanczos_terminator,
    xxx_mori_long_wave_lanczos,
)
from src.mori_moment_matching import (
    density_structure_from_mori_kernels,
    embed_colored_memory_behind_exact_lanczos,
    exponential_jet_counterterm,
    match_kernels_to_exact_lanczos,
    mori_hierarchy_kernel_from_terminator,
    moment_preserving_jet_subtraction,
)


def test_colored_continuum_is_embedded_behind_exact_mu26_prefix() -> None:
    times = np.linspace(0.0, 40.0, 2001)
    memory = np.exp(-0.4 * times)
    z = np.asarray([0.1, 0.2, 0.4, 0.8])
    omega = np.concatenate(([0.0], np.geomspace(1.0e-3, 20.0, 255)))
    result = embed_colored_memory_behind_exact_lanczos(
        times,
        memory,
        z,
        spectral_frequencies=omega,
    )
    assert result["exact_recurrent_count_preserved"] == 13
    assert result["exact_moment_order_preserved"] == 26
    assert result["white_contact_input"] == 0.0
    assert np.min(result["spectral_weights"]) >= 0.0
    assert np.isclose(np.sum(result["spectral_weights"]), 1.0, atol=1.0e-10)
    assert result["spectral_fit"]["relative_residual"] < 0.02


def test_colored_continuum_can_preserve_exact_finite_k_mu16_prefix() -> None:
    times = np.linspace(0.0, 40.0, 2001)
    memory = np.exp(-0.4 * times) * np.cos(0.2 * times)
    z = np.asarray([0.1, 0.2, 0.4, 0.8])
    omega = np.concatenate(([0.0], np.geomspace(1.0e-3, 20.0, 255)))
    result = embed_colored_memory_behind_exact_lanczos(
        times,
        memory,
        z,
        spectral_frequencies=omega,
        wavenumber=0.17,
    )
    assert result["exact_prefix_kind"] == "momentum_dependent_mu16"
    assert result["exact_recurrent_count_preserved"] == 8
    assert result["exact_moment_order_preserved"] == 16
    assert result["wavenumber"] == 0.17
    assert np.all(np.asarray(result["exact_squared_recurrents"]) > 0.0)
    assert np.min(result["spectral_weights"]) >= 0.0


def test_time_domain_hierarchy_has_exact_contact_and_conserves_k_zero() -> None:
    times = np.linspace(0.0, 20.0, 2001)
    terminator = np.exp(-0.3 * times) * np.cos(0.15 * times)
    squared = np.asarray([0.5, 1.75, 3.1785714285714284])
    kernel = mori_hierarchy_kernel_from_terminator(
        times, terminator, mu0=0.5, squared_recurrents=squared
    )
    assert kernel[0] == 0.5
    structure = density_structure_from_mori_kernels(
        times,
        np.asarray([0.0, 0.1]),
        np.column_stack([kernel, kernel]),
    )
    assert np.allclose(structure[:, 0], 1.0)
    assert structure[0, 1] == 1.0
    assert np.all(np.isfinite(structure))
from scripts.derive_matched_full_mode_wall import derive_matched_wall


def _synthetic_kernel(z: np.ndarray, weight_shift: float = 0.0) -> np.ndarray:
    lanczos = xxx_mori_long_wave_lanczos()
    frequencies = np.asarray([0.0, 0.17, 0.55, 1.4])
    weights = np.asarray(
        [0.08, 0.31 + weight_shift, 0.42 - weight_shift, 0.19]
    )
    terminator = np.sum(
        weights[:, None]
        * z[None, :]
        / (z[None, :] ** 2 + frequencies[:, None] ** 2),
        axis=0,
    )
    return mori_kernel_from_lanczos_terminator(
        z,
        terminator,
        float(lanczos["mu0"]),
        np.asarray(lanczos["squared_recurrents"]),
    )


def test_continuum_terminator_matching_preserves_exact_recurrents() -> None:
    z = np.geomspace(0.03, 3.0, 40)
    kernel = _synthetic_kernel(z)
    result = match_kernels_to_exact_lanczos(
        z,
        np.vstack([_synthetic_kernel(z, 2.0e-5), kernel]),
        spectral_frequencies=np.concatenate(
            ([0.0], np.geomspace(0.01, 4.0, 160))
        ),
        spectral_relative_tolerance=2.0e-3,
        cutoff_relative_tolerance=1.0e-3,
    )
    assert result["matching_complete"] is True
    assert result["exact_moment_order_preserved"] == 26
    assert result["finite_pole_count_assumed"] is False
    assert result["all_spectral_weights_nonnegative"] is True
    assert result["all_candidates_inside_stieltjes_bounds"] is True
    assert result["maximum_spectral_relative_residual"] < 2.0e-3


def test_matching_fails_closed_for_cutoff_drift() -> None:
    z = np.geomspace(0.03, 3.0, 40)
    kernel = _synthetic_kernel(z)
    result = match_kernels_to_exact_lanczos(
        z,
        np.vstack([kernel, 1.03 * kernel, 0.97 * kernel]),
        spectral_frequencies=np.concatenate(
            ([0.0], np.geomspace(0.01, 4.0, 160))
        ),
        spectral_relative_tolerance=3.0e-3,
        cutoff_relative_tolerance=1.0e-2,
    )
    assert result["matching_complete"] is False
    assert result["cutoff_stability_pass"] is False


def test_matching_rejects_kernel_outside_exact_moment_interval() -> None:
    z = np.geomspace(0.03, 3.0, 40)
    kernel = _synthetic_kernel(z)
    result = match_kernels_to_exact_lanczos(
        z,
        np.vstack([kernel, 100.0 * kernel]),
        spectral_frequencies=np.concatenate(
            ([0.0], np.geomspace(0.01, 4.0, 160))
        ),
    )
    assert result["matching_complete"] is False
    assert result["all_candidates_inside_stieltjes_bounds"] is False


def test_wall_projection_is_blocked_when_matching_is_incomplete() -> None:
    result = derive_matched_wall(
        {
            "inputs": {
                "trajectory_data_used": False,
                "target_coefficients_used": False,
            },
            "gates": {
                "continuum_terminator_matching_complete": False,
                "physical_F1_perp_certified": False,
            },
        },
        t_start=50.0,
        t_stop=200.0,
    )
    assert result["status"] == "blocked"
    assert result["physical_F1_perp_certified"] is False
    assert "a" not in result
    assert "D" not in result


def test_exponential_jet_counterterm_matches_all_declared_derivatives() -> None:
    derivatives = np.asarray([1.3, -0.7, 2.1, -4.2, 8.0])
    rate = 0.6
    result = exponential_jet_counterterm(derivatives, matching_rate=rate)
    coefficients = np.asarray(result["polynomial_derivatives_at_zero"])
    reconstructed = []
    for order in range(derivatives.size):
        reconstructed.append(
            sum(
                math.comb(order, m)
                * coefficients[m]
                * (-rate) ** (order - m)
                for m in range(order + 1)
            )
        )
    assert np.allclose(reconstructed, derivatives)


def test_moment_preserving_subtraction_cancels_contact_and_known_uv_jet() -> None:
    z = np.asarray([2.0e2, 4.0e2, 8.0e2])
    decay = 0.37
    derivatives = np.asarray([1.0, -decay, decay**2])
    raw_colored = 1.0 / (z + decay)
    result = moment_preserving_jet_subtraction(
        z,
        raw_colored,
        derivatives,
        white_contact=7.5,
        matching_rate=0.9,
    )
    renormalized = np.asarray(result["renormalized_colored_laplace"])
    # Three matched derivatives imply O(z^-4), rather than a constant contact
    # or any of the z^-1,z^-2,z^-3 microscopic moments.
    scaled = renormalized * z**4
    assert np.max(np.abs(np.diff(scaled) / scaled[:-1])) < 0.02
    assert result["white_contact_counterterm"] == -7.5
    assert result["preserved_large_z_orders"] == 3
