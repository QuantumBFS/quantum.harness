#!/usr/bin/env python3
"""Evaluate all currently derived physical-spin one-loop GHD vertices."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_full_tba_diffusion import (  # noqa: E402
    effective_velocity_second_frechet_derivative,
    full_diffusion_noise_frechet_derivatives,
    full_diffusion_noise_second_diagonal_frechet_derivatives,
    full_diffusion_operator_field,
    symmetric_noise_root_frechet_derivatives,
    symmetric_noise_root_second_diagonal_frechet_derivatives,
)
from src.full_mode_analytic_certificates import (  # noqa: E402
    cubic_diffusion_noise_tadpole_counterterms,
    cubic_velocity_tadpole_counterterm,
    mixed_quadratic_dynamics_observable_correction,
    multiplicative_noise_observable_contact_correction,
    one_loop_colored_memory_derivatives_at_zero,
    one_loop_physical_spin_corrections,
)


def _real_list(values: np.ndarray) -> list[float]:
    return np.real(np.asarray(values)).astype(float).tolist()


def derive(
    *,
    field: float,
    xi_cutoff: float,
    xi_buffer: float,
    u_extent: float,
    rapidity_points: int,
    wave_number: float,
    maximum_time: float,
    time_points: int,
    fourier_cutoffs: tuple[int, ...],
    moment_derivative_order: int = 20,
    brillouin_zone_lattice: bool = False,
) -> dict[str, object]:
    modes = full_diffusion_operator_field(
        field,
        string_xi_cutoff=xi_cutoff,
        string_xi_buffer=xi_buffer,
        rapidity_u_extent=u_extent,
        rapidity_points=rapidity_points,
        string_boundary="robin",
    )
    derivatives = full_diffusion_noise_frechet_derivatives(modes)
    velocity_second = effective_velocity_second_frechet_derivative(modes)
    second_derivatives = full_diffusion_noise_second_diagonal_frechet_derivatives(
        modes
    )
    root = symmetric_noise_root_second_diagonal_frechet_derivatives(
        modes["noise_covariance"],
        derivatives["noise_covariance_derivative"],
        second_derivatives["noise_covariance_second_diagonal_derivative"],
    )
    times = np.linspace(0.0, maximum_time, time_points)
    requested_mixed_times = np.asarray(
        [0.0, 1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 150.0, maximum_time]
    )
    requested_mixed_times = requested_mixed_times[
        requested_mixed_times <= maximum_time
    ]
    mixed_indices = np.unique(
        np.clip(np.rint(requested_mixed_times / times[1]).astype(int), 0, times.size - 1)
    )
    mixed_times = times[mixed_indices]
    rows = []
    for points in fourier_cutoffs:
        if brillouin_zone_lattice:
            # Unit lattice spacing fixes the entire Brillouin zone.  The
            # requested wave number selects the nearest nonzero lattice mode;
            # it does not set an adjustable hydrodynamic UV cutoff.
            waves = 2.0 * np.pi * np.fft.fftfreq(points)
            external_index = max(
                1,
                min(points // 2 - 1, int(np.rint(wave_number * points / (2.0 * np.pi)))),
            )
            cell_length = 1.0
        else:
            waves = wave_number * (np.fft.fftfreq(points) * points)
            external_index = 1
            cell_length = 2.0 * np.pi / (points * wave_number)
        lattice_symbol = (
            (lambda k: 2.0 * np.sin(k / 2.0))
            if brillouin_zone_lattice
            else None
        )
        result = one_loop_physical_spin_corrections(
            waves,
            external_index,
            modes["velocity"],
            modes["diffusion_operator"],
            modes["static_covariance"],
            modes["velocity_vertex"],
            derivatives["diffusion_derivative"],
            root["noise_root_derivative"],
            modes["spin_projection"],
            modes["spin_hessian"],
            times,
            noise_covariance=modes["noise_covariance"],
            spatial_cell_length=cell_length,
            lattice_wave_number=lattice_symbol,
        )
        zero_time_derivatives = one_loop_colored_memory_derivatives_at_zero(
            waves,
            external_index,
            modes["velocity"],
            modes["diffusion_operator"],
            modes["static_covariance"],
            modes["velocity_vertex"],
            derivatives["diffusion_derivative"],
            modes["spin_projection"],
            maximum_order=moment_derivative_order,
            spatial_cell_length=cell_length,
            lattice_wave_number=lattice_symbol,
        )
        mixed = mixed_quadratic_dynamics_observable_correction(
            waves,
            external_index,
            modes["velocity"],
            modes["diffusion_operator"],
            modes["static_covariance"],
            modes["velocity_vertex"],
            derivatives["diffusion_derivative"],
            modes["spin_projection"],
            modes["spin_hessian"],
            times,
            mixed_times,
            spatial_cell_length=cell_length,
            lattice_wave_number=lattice_symbol,
        )
        noise_observable_contact = (
            multiplicative_noise_observable_contact_correction(
                waves,
                external_index,
                modes["velocity"],
                modes["diffusion_operator"],
                modes["static_covariance"],
                root["noise_root"],
                root["noise_root_derivative"],
                modes["spin_projection"],
                modes["spin_hessian"],
                times,
                mixed_times,
                spatial_cell_length=cell_length,
                lattice_wave_number=lattice_symbol,
            )
        )
        cubic_tadpole = cubic_velocity_tadpole_counterterm(
            velocity_second["velocity_hessian"],
            modes["static_covariance"],
            spatial_cell_length=cell_length,
        )
        cubic_diffusion_noise = cubic_diffusion_noise_tadpole_counterterms(
            second_derivatives["diffusion_second_diagonal_derivative"],
            root["noise_root_second_diagonal_derivative"],
            modes["static_covariance"],
            spatial_cell_length=cell_length,
        )
        components = {}
        for name in [
            "velocity_continuity_memory",
            "diffusion_continuity_memory",
            "cross_continuity_memory",
            "total_colored_continuity_memory",
        ]:
            values = np.real(np.asarray(result[name]))
            components[name] = {
                "values": values.tolist(),
                "integral_to_maximum_time": float(np.trapezoid(values, times)),
                "final_value": float(values[-1]),
            }
        noise_delta = float(np.real(result["multiplicative_noise_delta_memory"]))
        rows.append(
            {
                "fourier_points": points,
                "external_index": external_index,
                "external_wave_number": float(waves[external_index]),
                "external_lattice_wave_number": float(
                    2.0 * np.sin(float(waves[external_index]) / 2.0)
                ),
                "spatial_cell_length": cell_length,
                "maximum_resolved_wave_number": float(np.max(np.abs(waves))),
                "colored_memory": components,
                "multiplicative_noise_delta_memory": noise_delta,
                "full_fdt_noise_covariance_retained": bool(
                    result["full_fdt_noise_covariance_retained"]
                ),
                "fdt_noise_covariance_relative_residual": float(
                    result["fdt_noise_covariance_relative_residual"]
                ),
                "internal_lattice_wave_number_retained": bool(
                    result["internal_lattice_wave_number_retained"]
                ),
                "colored_memory_zero_time_derivatives": {
                    "maximum_order": moment_derivative_order,
                    "real": _real_list(
                        zero_time_derivatives[
                            "total_colored_continuity_derivatives"
                        ]
                    ),
                    "maximum_absolute_imaginary_part": float(
                        np.max(
                            np.abs(
                                np.imag(
                                    zero_time_derivatives[
                                        "total_colored_continuity_derivatives"
                                    ]
                                )
                            )
                        )
                    ),
                    "analytic_matrix_power_evaluation": True,
                },
                "combined_markov_shift_half_delta_convention": float(
                    components["total_colored_continuity_memory"][
                        "integral_to_maximum_time"
                    ]
                    + 0.5 * noise_delta
                ),
                "combined_markov_shift_full_delta_convention": float(
                    components["total_colored_continuity_memory"][
                        "integral_to_maximum_time"
                    ]
                    + noise_delta
                ),
                "quadratic_observable_structure_correction": _real_list(
                    result["quadratic_observable_structure_correction"]
                ),
                "mixed_quadratic_dynamics_observable": {
                    "times": mixed_times.tolist(),
                    "initial_endpoint_velocity_H": _real_list(
                        mixed["initial_observable_endpoint_velocity_H"]
                    ),
                    "initial_endpoint_diffusion_H": _real_list(
                        mixed["initial_observable_endpoint_diffusion_H"]
                    ),
                    "final_endpoint_velocity_H": _real_list(
                        mixed["final_observable_endpoint_velocity_H"]
                    ),
                    "final_endpoint_diffusion_H": _real_list(
                        mixed["final_observable_endpoint_diffusion_H"]
                    ),
                    "total_Gamma_H_structure_correction": _real_list(
                        mixed["total_mixed_Gamma_H_structure_correction"]
                    ),
                    "normal_ordered_quadratic_force": True,
                    "multiplicative_noise_observable_contact_included": True,
                },
                "multiplicative_noise_observable_contact": {
                    "times": mixed_times.tolist(),
                    "right_observable_leg": _real_list(
                        noise_observable_contact["right_observable_leg_contact"]
                    ),
                    "left_observable_leg": _real_list(
                        noise_observable_contact["left_observable_leg_contact"]
                    ),
                    "total_Bprime_H_structure_correction": _real_list(
                        noise_observable_contact[
                            "total_multiplicative_noise_H_structure_correction"
                        ]
                    ),
                    "stochastic_convention": "Ito",
                },
                "cubic_velocity_tadpole": {
                    "bare_velocity_shift_l2": float(
                        np.linalg.norm(
                            cubic_tadpole["bare_cubic_tadpole_velocity_shift"]
                        )
                    ),
                    "bare_velocity_shift_maximum": float(
                        np.max(
                            np.abs(
                                cubic_tadpole[
                                    "bare_cubic_tadpole_velocity_shift"
                                ]
                            )
                        )
                    ),
                    "normal_ordering_counterterm_l2": float(
                        np.linalg.norm(
                            cubic_tadpole[
                                "equilibrium_normal_ordering_counterterm"
                            ]
                        )
                    ),
                    "maximum_cancellation_residual": float(
                        cubic_tadpole[
                            "maximum_absolute_cancellation_residual"
                        ]
                    ),
                    "one_vertex_two_point_correction_after_normal_ordering": 0.0,
                },
                "cubic_diffusion_noise_tadpoles": {
                    "bare_diffusion_shift_frobenius": float(
                        np.linalg.norm(
                            cubic_diffusion_noise["bare_cubic_diffusion_tadpole"]
                        )
                    ),
                    "bare_noise_root_shift_frobenius": float(
                        np.linalg.norm(
                            cubic_diffusion_noise["bare_cubic_noise_root_tadpole"]
                        )
                    ),
                    "maximum_diffusion_cancellation_residual": float(
                        cubic_diffusion_noise[
                            "maximum_diffusion_cancellation_residual"
                        ]
                    ),
                    "maximum_noise_root_cancellation_residual": float(
                        cubic_diffusion_noise[
                            "maximum_noise_root_cancellation_residual"
                        ]
                    ),
                    "multiplicative_Bprime_Bprime_contact_retained": True,
                },
            }
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
            "maximum_time": maximum_time,
            "time_points": time_points,
            "fourier_cutoffs": list(fourier_cutoffs),
            "moment_derivative_order": moment_derivative_order,
            "brillouin_zone_lattice": brillouin_zone_lattice,
            "trajectory_data_used": False,
            "target_coefficients_used": False,
        },
        "operator": {
            "dimension": int(np.asarray(modes["velocity"]).size),
            "active_strings": int(modes["active_strings"]),
            "noise_root_maximum_relative_residual": float(
                np.max(root["relative_nullspace_residual"])
            ),
            "velocity_vertex": True,
            "diffusion_vertex": True,
            "multiplicative_noise_vertex": True,
            "quadratic_spin_observable": True,
            "mixed_deterministic_Gamma_H": True,
            "analytic_second_velocity_frechet_derivative": True,
            "cubic_velocity_tadpole_counterterm": True,
            "analytic_second_diagonal_diffusion_noise_frechet_derivatives": True,
            "second_noise_root_sylvester_derivative": True,
            "second_noise_root_maximum_relative_residual": float(
                np.max(root["second_order_relative_nullspace_residual"])
            ),
            "velocity_hessian_raw_schwarz_relative_residual": float(
                velocity_second["raw_schwarz_relative_residual"]
            ),
        },
        "times": times.tolist(),
        "uv_rows": rows,
        "scope": {
            "complete_known_quadratic_vertices": True,
            "mixed_deterministic_dynamics_observable_evaluated": True,
            "multiplicative_noise_observable_contact_complete_at_finite_cutoff": True,
            "first_order_cubic_velocity_tadpole_normal_ordered": True,
            "first_order_cubic_diffusion_noise_tadpoles_normal_ordered": True,
            "microscopic_mori_uv_matching_complete": False,
            "zero_field_infinite_mode_limit_complete": False,
            "physical_F1_perp_claimed": False,
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
    parser.add_argument("--maximum-time", type=float, default=50.0)
    parser.add_argument("--time-points", type=int, default=101)
    parser.add_argument("--fourier-cutoffs", nargs="+", type=int, default=[8, 12, 16])
    parser.add_argument("--moment-derivative-order", type=int, default=20)
    parser.add_argument(
        "--brillouin-zone-lattice",
        action="store_true",
        help=(
            "use unit lattice spacing, the full Brillouin zone, and the "
            "signed 2 sin(k/2) symbol in propagators and vertices"
        ),
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
        maximum_time=args.maximum_time,
        time_points=args.time_points,
        fourier_cutoffs=tuple(args.fourier_cutoffs),
        moment_derivative_order=args.moment_derivative_order,
        brillouin_zone_lattice=args.brillouin_zone_lattice,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
