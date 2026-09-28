#!/usr/bin/env python3
"""Derive an analytic finite-cutoff OU, Mori, symmetry, and projection certificate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_full_tba_diffusion import full_diffusion_operator_field  # noqa: E402
from src.heisenberg_burgers_bridge import (  # noqa: E402
    mori_lanczos_stieltjes_bounds,
    xxx_mori_long_wave_lanczos,
)
from src.full_mode_analytic_certificates import (  # noqa: E402
    exact_ou_covariance,
    linear_ghd_generator,
    magnetic_local_gge_wall_tangent,
    one_loop_occupation_force_memory,
    perturbative_structure_from_memory,
    projected_mori_kernel,
    projected_two_time_structure,
    quadratic_observable_structure_correction,
    scalar_galerkin_coefficients,
    sharp_product_wall_mori_certificate,
    spin_flip_projection_certificate,
    static_metric_projection,
    zero_field_magnetic_wall_string_certificate,
)


def _serializable(value):
    if isinstance(value, np.ndarray):
        if np.iscomplexobj(value):
            return {
                "real": np.real(value).tolist(),
                "imag": np.imag(value).tolist(),
            }
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: _serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(item) for item in value]
    return value


def derive(
    *,
    field: float,
    xi_cutoff: float,
    xi_buffer: float,
    u_extent: float,
    rapidity_points: int,
    wave_number: float,
    times: np.ndarray,
    laplace_values: np.ndarray,
    one_loop_fourier_points: int,
    one_loop_time_points: int,
    one_loop_cutoff_audit: tuple[int, ...],
    one_loop_volume_audit: tuple[int, ...],
) -> dict[str, object]:
    modes = full_diffusion_operator_field(
        field,
        string_xi_cutoff=xi_cutoff,
        string_xi_buffer=xi_buffer,
        rapidity_u_extent=u_extent,
        rapidity_points=rapidity_points,
        string_boundary="robin",
    )
    velocity = np.asarray(modes["velocity"])
    diffusion = np.asarray(modes["diffusion_operator"])
    covariance = np.asarray(modes["static_covariance"])
    spin = np.asarray(modes["spin_projection"])
    generator = linear_ghd_generator(wave_number, velocity, diffusion)
    ou = exact_ou_covariance(generator, covariance, covariance, times)
    structure = projected_two_time_structure(
        generator, covariance, spin, times
    )
    mori = projected_mori_kernel(
        generator,
        covariance,
        spin,
        wave_number,
        laplace_values,
        lattice_wave_number=lambda k: 2.0 * np.sin(k / 2.0),
    )
    one_loop_waves = wave_number * (
        np.fft.fftfreq(one_loop_fourier_points) * one_loop_fourier_points
    )
    one_loop_cell_length = 2.0 * np.pi / (
        one_loop_fourier_points * wave_number
    )
    one_loop_times = np.linspace(0.0, float(np.max(times)), one_loop_time_points)
    one_loop = one_loop_occupation_force_memory(
        one_loop_waves,
        1,
        velocity,
        diffusion,
        covariance,
        np.asarray(modes["velocity_vertex"]),
        spin,
        one_loop_times,
        lattice_wave_number=lambda k: 2.0 * np.sin(k / 2.0),
        spatial_cell_length=one_loop_cell_length,
    )
    # The full mode-by-mode force covariance is used to certify positivity,
    # but the public artifact only needs the projected memory and would be
    # needlessly large if all dense matrices were serialized.
    one_loop.pop("force_covariances")
    cutoff_audit = []
    for cutoff_points in one_loop_cutoff_audit:
        cutoff_waves = wave_number * (
            np.fft.fftfreq(cutoff_points) * cutoff_points
        )
        cutoff_cell_length = 2.0 * np.pi / (cutoff_points * wave_number)
        cutoff_result = one_loop_occupation_force_memory(
            cutoff_waves,
            1,
            velocity,
            diffusion,
            covariance,
            np.asarray(modes["velocity_vertex"]),
            spin,
            one_loop_times,
            lattice_wave_number=lambda k: 2.0 * np.sin(k / 2.0),
            spatial_cell_length=cutoff_cell_length,
        )
        cutoff_audit.append(
            {
                "fourier_points": cutoff_points,
                "spatial_cell_length": cutoff_cell_length,
                "maximum_resolved_wave_number": float(
                    np.max(np.abs(cutoff_waves))
                ),
                "final_running_diffusion_correction_real": float(
                    np.real(cutoff_result["running_markov_diffusion_correction"][-1])
                ),
                "final_memory_real": float(
                    np.real(cutoff_result["continuity_normalized_memory"][-1])
                ),
            }
        )
    volume_audit = []
    fixed_cell_length = one_loop_cell_length
    for volume_points in one_loop_volume_audit:
        volume_waves = 2.0 * np.pi * np.fft.fftfreq(
            volume_points, d=fixed_cell_length
        )
        external_volume_index = int(
            np.argmin(np.abs(volume_waves - wave_number))
        )
        if not np.isclose(volume_waves[external_volume_index], wave_number):
            raise ValueError(
                "volume audit grid does not contain the external wave number"
            )
        volume_result = one_loop_occupation_force_memory(
            volume_waves,
            external_volume_index,
            velocity,
            diffusion,
            covariance,
            np.asarray(modes["velocity_vertex"]),
            spin,
            one_loop_times,
            lattice_wave_number=lambda k: 2.0 * np.sin(k / 2.0),
            spatial_cell_length=fixed_cell_length,
        )
        volume_audit.append(
            {
                "fourier_points": volume_points,
                "external_index": external_volume_index,
                "wave_spacing": float(2.0 * np.pi / (volume_points * fixed_cell_length)),
                "maximum_resolved_wave_number": float(
                    np.max(np.abs(volume_waves))
                ),
                "final_running_diffusion_correction_real": float(
                    np.real(volume_result["running_markov_diffusion_correction"][-1])
                ),
                "final_memory_real": float(
                    np.real(volume_result["continuity_normalized_memory"][-1])
                ),
            }
        )
    volume_spacing = np.asarray([row["wave_spacing"] for row in volume_audit])
    volume_diffusion = np.asarray(
        [row["final_running_diffusion_correction_real"] for row in volume_audit]
    )
    volume_memory = np.asarray([row["final_memory_real"] for row in volume_audit])
    volume_diffusion_limit = float(np.polyfit(volume_spacing, volume_diffusion, 1)[1])
    volume_memory_limit = float(np.polyfit(volume_spacing, volume_memory, 1)[1])
    scalar_projection = scalar_galerkin_coefficients(
        velocity,
        diffusion,
        covariance,
        np.asarray(modes["velocity_vertex"]),
        spin,
    )
    observable_correction = quadratic_observable_structure_correction(
        one_loop_waves,
        1,
        velocity,
        diffusion,
        covariance,
        np.asarray(modes["spin_hessian"]),
        spin,
        one_loop_times,
        spatial_cell_length=one_loop_cell_length,
    )
    dense_linear_structure = projected_two_time_structure(
        generator, covariance, spin, one_loop_times
    )
    h2_values = np.asarray(
        observable_correction["normalized_H2_structure_correction"]
    )
    h2_normalized_structure = (dense_linear_structure + h2_values) / (
        1.0 + h2_values[0]
    )
    observable_correction["linear_structure"] = dense_linear_structure
    observable_correction["static_renormalized_linear_plus_H2_structure"] = (
        h2_normalized_structure
    )
    observable_correction["static_renormalized_shape_shift"] = (
        h2_normalized_structure - dense_linear_structure
    )
    velocity_structure_correction = perturbative_structure_from_memory(
        one_loop_times,
        dense_linear_structure,
        np.asarray(one_loop["continuity_normalized_memory"]),
        wave_number,
        lattice_wave_number=lambda k: 2.0 * np.sin(k / 2.0),
    )
    lanczos = xxx_mori_long_wave_lanczos()
    moment_bounds = mori_lanczos_stieltjes_bounds(
        laplace_values,
        float(lanczos["mu0"]),
        np.asarray(lanczos["squared_recurrents"]),
    )
    mori_real = np.real(np.asarray(mori["mori_kernel"]))
    mori_imaginary = np.imag(np.asarray(mori["mori_kernel"]))
    inside_moment_interval = (
        (mori_real >= np.asarray(moment_bounds["lower"]))
        & (mori_real <= np.asarray(moment_bounds["upper"]))
    )
    # This is a synthetic algebraic audit of the initial-state projector, not
    # a claim about a particular wall preparation.  The physical tangent is
    # the covariance-weighted spin source; adding a known orthogonal vector
    # verifies that the certificate measures exactly the discarded fraction.
    tangent = covariance @ spin
    trial = np.zeros_like(tangent)
    trial[0] = 1.0
    trial -= tangent * (tangent @ np.linalg.solve(covariance, trial)) / (
        tangent @ np.linalg.solve(covariance, tangent)
    )
    initial_projection_audit = static_metric_projection(
        tangent + 0.1 * trial, tangent, covariance
    )
    wall_coordinate = np.linspace(-4.0, 4.0, 65)
    magnetic_wall = magnetic_local_gge_wall_tangent(
        0.05 * np.tanh(wall_coordinate), covariance, spin
    )
    registered_wall_amplitudes = (0.02, 0.05, 0.10, 0.20)
    zero_field_walls = [
        zero_field_magnetic_wall_string_certificate(np.arange(1, 65), amplitude)
        for amplitude in registered_wall_amplitudes
    ]
    sharp_wall = sharp_product_wall_mori_certificate(
        np.asarray(registered_wall_amplitudes)
    )
    final_covariance = np.asarray(ou["covariances"])[-1]
    stationarity = np.linalg.norm(final_covariance - covariance) / max(
        np.linalg.norm(covariance), np.finfo(float).tiny
    )
    return {
        "schema_version": 1,
        "inputs": {
            "field": field,
            "string_xi_cutoff": xi_cutoff,
            "string_xi_buffer": xi_buffer,
            "rapidity_u_extent": u_extent,
            "rapidity_points": rapidity_points,
            "wave_number": wave_number,
            "times": times.tolist(),
            "laplace_values": laplace_values.tolist(),
            "one_loop_fourier_points": one_loop_fourier_points,
            "one_loop_time_points": one_loop_time_points,
            "one_loop_cutoff_audit": list(one_loop_cutoff_audit),
            "one_loop_volume_audit": list(one_loop_volume_audit),
            "trajectory_data_used": False,
            "target_coefficients_used": False,
        },
        "operator": {
            "dimension": int(velocity.size),
            "active_strings": int(modes["active_strings"]),
            "off_diagonal_diffusion_retained": True,
            "analytic_velocity_vertex_available": True,
        },
        "ou_covariance": {
            "stationary_initial_covariance_relative_residual": float(stationarity),
            "maximum_hermiticity_residual": float(
                ou["maximum_hermiticity_residual"]
            ),
            "accumulated_noise_minimum_eigenvalues": [
                float(np.min(np.linalg.eigvalsh(matrix)))
                for matrix in np.asarray(ou["accumulated_noise_covariances"])
            ],
        },
        "projected_structure_factor": {
            "real": np.real(structure).tolist(),
            "imag": np.imag(structure).tolist(),
        },
        "projected_mori": _serializable(mori),
        "nonlinear_velocity_one_loop_mori": _serializable(one_loop),
        "nonlinear_one_loop_uv_audit": {
            "cutoffs": cutoff_audit,
            "converged": False,
            "interpretation": (
                "the bare one-loop correction is coarse-graining dependent; "
                "a physical D shift requires matching to the microscopic Mori "
                "kernel and the omitted state-dependent vertices"
            ),
        },
        "nonlinear_one_loop_fixed_uv_volume_audit": {
            "fixed_spatial_cell_length": fixed_cell_length,
            "rows": volume_audit,
            "linear_spacing_extrapolated_final_diffusion_correction": volume_diffusion_limit,
            "linear_spacing_extrapolated_final_memory": volume_memory_limit,
            "last_to_extrapolated_diffusion_relative_difference": float(
                abs(volume_diffusion[-1] / volume_diffusion_limit - 1.0)
            ),
            "interpretation": (
                "at fixed hydrodynamic UV cutoff, increasing volume/refining "
                "the loop momentum grid approaches a stable finite result"
            ),
        },
        "weak_magnetic_tangent_scalar_projection": _serializable(
            scalar_projection
        ),
        "quadratic_spin_observable_correction": _serializable(
            observable_correction
        ),
        "velocity_one_loop_structure_correction": _serializable(
            velocity_structure_correction
        ),
        "zero_field_microscopic_moment_comparison": {
            "exact_recurrent_count": int(
                np.asarray(lanczos["squared_recurrents"]).size
            ),
            "lower": np.asarray(moment_bounds["lower"]).tolist(),
            "upper": np.asarray(moment_bounds["upper"]).tolist(),
            "finite_field_real_part_inside_interval": inside_moment_interval.tolist(),
            "finite_field_imaginary_to_real_ratio": np.divide(
                np.abs(mori_imaginary),
                np.maximum(np.abs(mori_real), np.finfo(float).tiny),
            ).tolist(),
            "interpretation": (
                "agreement is required only in the joint low-frequency and "
                "zero-field limit; failure at large z is expected because GHD "
                "does not reproduce microscopic short-time moments"
            ),
        },
        "spin_flip_certificate": spin_flip_projection_certificate(),
        "weak_local_gge_wall_mapping": _serializable(magnetic_wall),
        "zero_field_wall_giant_string_certificates": _serializable(
            {
                "registered_amplitudes": list(registered_wall_amplitudes),
                "rows": zero_field_walls,
                "minimum_required_crossover_strings": [
                    int(np.ceil(1.0 / amplitude))
                    for amplitude in registered_wall_amplitudes
                ],
            }
        ),
        "sharp_product_wall_mori_certificate": _serializable(sharp_wall),
        "initial_projection_algebra_audit": _serializable(initial_projection_audit),
        "scope": {
            "finite_cutoff_analytic_certificate": True,
            "monte_carlo_used": False,
            "zero_field_infinite_mode_limit_converged": False,
            "physical_wall_initial_projection_evaluated": False,
            "physical_F1_perp_claimed": False,
            "analytic_O_velocity_vertex_squared_memory_evaluated": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--field", type=float, default=0.25)
    parser.add_argument("--xi-cutoff", type=float, default=0.75)
    parser.add_argument("--xi-buffer", type=float, default=0.75)
    parser.add_argument("--u-extent", type=float, default=1.5)
    parser.add_argument("--rapidity-points", type=int, default=16)
    parser.add_argument("--wave-number", type=float, default=0.04)
    parser.add_argument("--times", nargs="+", type=float, default=[0.0, 10.0, 25.0, 50.0])
    parser.add_argument("--laplace-values", nargs="+", type=float, default=[0.02, 0.05, 0.1, 0.5, 1.0])
    parser.add_argument("--one-loop-fourier-points", type=int, default=8)
    parser.add_argument("--one-loop-time-points", type=int, default=101)
    parser.add_argument(
        "--one-loop-cutoff-audit", nargs="+", type=int, default=[8, 12, 16]
    )
    parser.add_argument(
        "--one-loop-volume-audit", nargs="+", type=int, default=[8, 16, 32, 64]
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(
        field=args.field,
        xi_cutoff=args.xi_cutoff,
        xi_buffer=args.xi_buffer,
        u_extent=args.u_extent,
        rapidity_points=args.rapidity_points,
        wave_number=args.wave_number,
        times=np.asarray(args.times),
        laplace_values=np.asarray(args.laplace_values),
        one_loop_fourier_points=args.one_loop_fourier_points,
        one_loop_time_points=args.one_loop_time_points,
        one_loop_cutoff_audit=tuple(args.one_loop_cutoff_audit),
        one_loop_volume_audit=tuple(args.one_loop_volume_audit),
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
