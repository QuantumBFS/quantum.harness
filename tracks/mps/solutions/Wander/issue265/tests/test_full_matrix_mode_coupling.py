from __future__ import annotations

import argparse

from scripts.derive_full_matrix_mode_coupling import derive


def test_full_matrix_mode_coupling_smoke_keeps_fdt_and_projection() -> None:
    payload = derive(
        argparse.Namespace(
            field=0.25,
            string_xi_cutoff=0.5,
            string_xi_buffer=0.5,
            scaled_rapidity_extent=2.0,
            scaled_rapidity_map_alpha=2.0,
            nodes_per_string=8,
            kernel_theta_step=0.25,
            fourier_points=4,
            wave_step=0.1,
            times=[0.0, 0.25],
            samples=8,
            seed=265,
            trace_distribution="rademacher",
            lattice_wave_number=False,
        )
    )
    operator = payload["full_operator_certificates"]
    assert operator["diffusion_off_diagonal_frobenius_fraction"] > 0.1
    assert operator["noise_off_diagonal_frobenius_fraction"] > 0.01
    assert operator["fdt_noise_positive_semidefinite"]
    assert operator["fdt_operator_identity_residual"] < 1.0e-12
    assert operator["stationary_covariance_maximum_residual"] < 1.0e-13
    assert (
        payload["matrix_memory"][
            "matrix_to_scalar_projection_identity_maximum_residual"
        ]
        < 1.0e-13
    )
    assert (
        payload["multiplicative_noise_contact"][
            "matrix_to_scalar_projection_identity_residual"
        ]
        < 1.0e-13
    )
    assert not payload["scope"]["self_consistent_matrix_resummation_complete"]
    assert not payload["scope"]["physical_a_or_D_identified"]
