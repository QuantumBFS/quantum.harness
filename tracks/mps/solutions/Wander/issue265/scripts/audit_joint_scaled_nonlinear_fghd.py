#!/usr/bin/env python3
"""Audit nonlinear fluctuating-GHD vertices in the giant-string limit.

Inputs are certificates from ``derive_matrix_free_adaptive_diffusion_memory``
created with its joint-scaled interface.  At fixed ``q=k/h^2`` and
``tau=t*h^3``, the continuity resolvent requires

    K_h(t) = h^2 K(q,tau),       K_delta,h = h^-1 K_delta(q).

The program therefore compares ``K_h(t)/h^2`` for every colored velocity,
diffusion, and cross contribution, and ``h*K_delta,h`` for multiplicative
noise.  It does not select a finite-pole closure or read wall data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


COMPONENTS = ("velocity", "diffusion", "cross", "total")


def _complex(pair: list[float]) -> complex:
    return complex(float(pair[0]), float(pair[1]))


def _row_value(row: dict[str, object], component: str) -> complex:
    dense = row.get("dense_checks")
    if dense is not None:
        return _complex(dense[component])
    return _complex(row["continuity_memory_estimates"][component])


def audit(payloads: list[dict[str, object]], tolerance: float) -> dict[str, object]:
    if len(payloads) < 2:
        raise ValueError("at least two field regulators are required")
    ordered = sorted(payloads, key=lambda item: item["regulator"]["field"], reverse=True)
    reference_q = None
    reference_tau = None
    per_field = []
    scaled_by_component: dict[str, list[np.ndarray]] = {
        name: [] for name in COMPONENTS
    }
    errors_by_component: dict[str, list[np.ndarray]] = {
        name: [] for name in COMPONENTS
    }
    scaled_contacts = []
    scaled_contact_errors = []
    for payload in ordered:
        if payload.get("uses_target_trajectory") or payload.get("uses_target_a_or_D"):
            raise RuntimeError("target-contaminated nonlinear certificate")
        coordinates = payload["hydrodynamic_coordinates"]
        if not coordinates.get("joint_scaled_input"):
            raise ValueError("all inputs must use the joint-scaled interface")
        h = float(payload["regulator"]["field"])
        q = float(coordinates["scaled_wave_step_q_equals_k_over_h2"])
        tau = np.asarray(coordinates["scaled_times_tau_equals_t_h3"], dtype=float)
        if reference_q is None:
            reference_q = q
            reference_tau = tau
        elif not np.isclose(q, reference_q) or not np.allclose(tau, reference_tau):
            raise ValueError("fixed q and tau grids are required across fields")
        component_rows = {}
        for component in COMPONENTS:
            values = np.asarray(
                [_row_value(row, component) for row in payload["rows"]],
                dtype=complex,
            ) / h**2
            scaled_by_component[component].append(values)
            errors = np.asarray(
                [
                    float(row["standard_error_complex_norms"][component])
                    for row in payload["rows"]
                ],
                dtype=float,
            ) / h**2
            if payload["rows"][0].get("dense_checks") is not None:
                errors = np.zeros_like(errors)
            errors_by_component[component].append(errors)
            component_rows[component] = [[value.real, value.imag] for value in values]
        contact = h * float(payload["multiplicative_noise_delta_memory"]["estimate"])
        contact_error = h * float(
            payload["multiplicative_noise_delta_memory"]["standard_error"]
        )
        scaled_contacts.append(contact)
        scaled_contact_errors.append(contact_error)
        per_field.append(
            {
                "field": h,
                "mode_count": int(payload["regulator"]["mode_count"]),
                "static_susceptibility_captured_fraction": float(
                    payload["static_susceptibility_captured_fraction"]
                ),
                "scaled_colored_memory_K_over_h2": component_rows,
                "scaled_multiplicative_noise_contact_hKdelta": contact,
                "scaled_multiplicative_noise_contact_standard_error": contact_error,
                "fdt_residual": float(payload["fdt_residual"]),
                "dense_contractions_used": bool(
                    payload["rows"][0].get("dense_checks") is not None
                ),
            }
        )

    convergence = {}
    maximum_change = 0.0
    for component, rows in scaled_by_component.items():
        array = np.asarray(rows)
        errors = np.asarray(errors_by_component[component])
        absolute = np.abs(array[-1] - array[-2])
        scale = np.maximum.reduce(
            (np.abs(array[-1]), np.abs(array[-2]), np.full_like(absolute, 1.0e-14))
        )
        relative = absolute / scale
        pooled_error = np.sqrt(errors[-1] ** 2 + errors[-2] ** 2)
        z_score = absolute / np.maximum(pooled_error, 1.0e-300)
        maximum_change = max(maximum_change, float(np.max(relative)))
        convergence[component] = {
            "last_field_step_relative_change_by_tau": relative.tolist(),
            "maximum_last_field_step_relative_change": float(np.max(relative)),
            "last_field_step_change_in_pooled_standard_errors_by_tau": (
                z_score.tolist()
            ),
            "maximum_change_in_pooled_standard_errors": float(np.max(z_score)),
        }
    contact_change = abs(scaled_contacts[-1] - scaled_contacts[-2]) / max(
        abs(scaled_contacts[-1]), abs(scaled_contacts[-2]), 1.0e-14
    )
    contact_pooled_error = np.hypot(
        scaled_contact_errors[-1], scaled_contact_errors[-2]
    )
    contact_z_score = abs(scaled_contacts[-1] - scaled_contacts[-2]) / max(
        contact_pooled_error, 1.0e-300
    )
    maximum_change = max(maximum_change, contact_change)
    return {
        "schema": 1,
        "method": "target_free_joint_scaled_full_nonlinear_fghd_vertex_audit",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "scaled_variables": {
            "q_equals_k_over_h2": reference_q,
            "tau_equals_t_h3": reference_tau.tolist(),
            "colored_kernel_scaling": "K_h(t)/h^2",
            "delta_contact_scaling": "h*K_delta,h",
        },
        "per_field": per_field,
        "last_field_step_convergence": {
            "colored_components": convergence,
            "multiplicative_noise_contact_relative_change": contact_change,
            "multiplicative_noise_contact_change_in_pooled_standard_errors": (
                contact_z_score
            ),
            "maximum_relative_change": maximum_change,
            "declared_relative_tolerance": tolerance,
            "bare_vertex_sequence_converged": bool(maximum_change < tolerance),
        },
        "scope": {
            "complete_velocity_diffusion_cross_vertices": True,
            "complete_non_diagonal_diffusion_operator": True,
            "multiplicative_noise_covariance_derivative": True,
            "finite_pole_closure_assumed": False,
            "microscopic_mori_contact_matched": False,
            "physical_F1_certified": False,
            "reason": (
                "a converged bare hydrodynamic loop would still require the exact "
                "lattice Mori contact subtraction before defining a physical kernel"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--relative-tolerance", type=float, default=0.05)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(
        [json.loads(path.read_text(encoding="utf-8")) for path in args.inputs],
        args.relative_tolerance,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
