from __future__ import annotations

import numpy as np

from scripts.propagate_full_mode_fluctuating_ghd import (
    _hermitian_gaussian,
    _compress_frechet_tensor,
    _nonlinear_rhs,
    _spin_observable_fourier,
    propagate,
)


def test_hermitian_noise_gives_real_dealiased_field() -> None:
    roots = np.repeat(np.eye(3)[None, :, :], 16, axis=0)
    sample = _hermitian_gaussian(roots, 4, np.random.default_rng(7))
    real_space = np.fft.ifft(sample, axis=-1, norm="ortho")
    assert np.max(np.abs(real_space.imag)) < 1.0e-14
    assert np.all(sample[:, :, 8] == 0.0)


def test_antithetic_noise_is_exactly_opposite() -> None:
    roots = np.repeat(np.eye(2)[None, :, :], 8, axis=0)
    sample = _hermitian_gaussian(
        roots, 6, np.random.default_rng(8), antithetic=True
    )
    assert np.allclose(sample[:3], -sample[3:], rtol=0.0, atol=0.0)


def test_frechet_tensor_svd_compression_reports_exact_full_rank() -> None:
    rng = np.random.default_rng(13)
    tensor = rng.normal(size=(4, 3, 3))
    left, matrices, report = _compress_frechet_tensor(tensor, 1.0)
    reconstructed = np.einsum("lr,rij->lij", left, matrices)
    assert np.allclose(reconstructed, tensor, rtol=1.0e-12, atol=1.0e-12)
    assert report["relative_discarded_frobenius_norm"] < 1.0e-7


def test_quadratic_vertex_rhs_is_dealiased_and_has_no_nyquist() -> None:
    rng = np.random.default_rng(9)
    real_field = rng.normal(size=(2, 4, 16))
    field = np.fft.fft(real_field, axis=-1, norm="ortho")
    k = 2.0 * np.pi * np.fft.fftfreq(16)
    indices = np.fft.fftfreq(16) * 16
    mask = np.abs(indices) <= 16 / 3
    vertex = rng.normal(size=(4, 4))
    rhs = _nonlinear_rhs(field, k, vertex, mask)
    assert np.all(rhs[:, :, ~mask] == 0.0)
    assert np.max(np.abs(np.fft.ifft(rhs, axis=-1).imag)) < 1.0e-14


def test_quadratic_spin_observable_matches_real_space_definition() -> None:
    rng = np.random.default_rng(12)
    occupation = rng.normal(size=(3, 4, 8))
    fourier = np.fft.fft(occupation, axis=-1, norm="ortho")
    spin = rng.normal(size=4)
    hessian = rng.normal(size=(4, 4))
    hessian = 0.5 * (hessian + hessian.T)
    measured = _spin_observable_fourier(fourier, spin, hessian)
    expected_real = (
        np.einsum("i,eix->ex", spin, occupation)
        + 0.5 * np.einsum("ij,eix,ejx->ex", hessian, occupation, occupation)
    )
    expected = np.fft.fft(expected_real, axis=-1, norm="ortho")
    assert np.allclose(measured, expected, rtol=1.0e-12, atol=1.0e-12)


def test_zero_time_full_mode_propagation_uses_no_target_data() -> None:
    result = propagate(
        field=0.25,
        xi_cutoff=0.25,
        xi_buffer=0.5,
        u_extent=1.5,
        rapidity_points=16,
        spatial_points=8,
        cell_length=512.0,
        time_step=0.02,
        output_times=np.asarray([0.0, 0.02]),
        ensembles=2,
        seed=11,
        paired_linear_control=True,
    )
    assert result["operator"]["dimension"] == 16
    assert result["operator"]["relative_fdt_identity_residual"] < 1.0e-13
    assert result["inputs"]["trajectory_data_used"] is False
    assert result["inputs"]["target_coefficients_used"] is False
    assert result["scope"]["infinite_mode_limit_converged"] is False
    delta = result["structure_factor"][0]["nonlinear_minus_linear_over_chi"]
    assert np.allclose(delta, 0.0, rtol=0.0, atol=0.0)
