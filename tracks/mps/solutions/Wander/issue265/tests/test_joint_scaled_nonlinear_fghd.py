from __future__ import annotations

import numpy as np

from scripts.audit_joint_scaled_nonlinear_fghd import audit
from scripts.audit_joint_scaled_one_loop_breakdown import audit as audit_breakdown
from scripts.derive_self_consistent_joint_scaled_mode_coupling import (
    _internal_damped_memory,
)


def _payload(field: float) -> dict[str, object]:
    # Exact joint scaling: colored K_h(t)=h^2(1+tau), contact=h^-1/3.
    rows = []
    for tau in (0.0, 0.2):
        value = field**2 * (1.0 + tau)
        rows.append(
            {
                "standard_error_complex_norms": {
                    name: 0.0
                    for name in ("velocity", "diffusion", "cross", "total")
                },
                "dense_checks": {
                    name: [value, 0.0]
                    for name in ("velocity", "diffusion", "cross", "total")
                }
            }
        )
    return {
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "regulator": {"field": field, "mode_count": 8},
        "hydrodynamic_coordinates": {
            "joint_scaled_input": True,
            "scaled_wave_step_q_equals_k_over_h2": 0.4,
            "scaled_times_tau_equals_t_h3": [0.0, 0.2],
        },
        "static_susceptibility_captured_fraction": 1.0,
        "fdt_residual": 0.0,
        "multiplicative_noise_delta_memory": {
            "estimate": 1.0 / (3.0 * field),
            "standard_error": 0.0,
        },
        "rows": rows,
    }


def test_joint_scaled_nonlinear_audit_uses_resolvent_dimensions() -> None:
    result = audit([_payload(0.25), _payload(0.2)], tolerance=1.0e-12)
    convergence = result["last_field_step_convergence"]
    assert convergence["bare_vertex_sequence_converged"]
    assert convergence["maximum_relative_change"] < 1.0e-12
    assert result["scaled_variables"]["colored_kernel_scaling"] == "K_h(t)/h^2"
    assert result["scaled_variables"]["delta_contact_scaling"] == "h*K_delta,h"
    assert not result["scope"]["physical_F1_certified"]


def test_one_loop_breakdown_audit_recovers_two_thirds_power() -> None:
    fields = (0.25, 0.2, 1.0 / 6.0, 0.125)
    rows = []
    for field in fields:
        rows.append(
            {
                "field": field,
                "frequency_rows": [
                    {"scaled_colored_hDeltaK": scale * field ** (-2.0 / 3.0)}
                    for scale in (1.0, 0.8, 0.6)
                ],
            }
        )
    payload = {
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "scaled_variables": {
            "q_equals_k_over_h2": 0.4,
            "p_equals_z_over_h3": [1.0, 2.0, 4.0],
        },
        "rows": rows,
    }
    result = audit_breakdown([payload])
    assert result["gates"]["two_thirds_growth_consistent_but_not_proved"]
    assert not result["gates"]["finite_one_loop_zero_field_limit"]
    for row in result["frequency_rows"]:
        assert abs(row["pure_power_effective_exponent"] - 2.0 / 3.0) < 1.0e-12


def test_internal_line_dressing_is_identity_at_zero_gamma() -> None:
    h = 0.25
    wave_step = 0.025
    points = 4
    cell_length = 2.0 * 3.141592653589793 / (points * wave_step)
    fourier_chi = (1.0 / (4.0 * np.cosh(h) ** 2)) / cell_length
    normalization = fourier_chi * (2.0 * np.sin(wave_step / 2.0)) ** 2
    payload = {
        "regulator": {"field": h, "fourier_points": points},
        "hydrodynamic_coordinates": {"physical_wave_step": wave_step},
        "static_susceptibility_captured_fraction": 1.0,
        "rows": [
            {
                "time": 3.0,
                "internal_wave_rows": [
                    {
                        "p_wave": 0.0,
                        "q_wave": wave_step,
                        "estimates": {"total": [2.5 * normalization, 0.0]},
                    }
                ],
            }
        ],
    }
    value = _internal_damped_memory(payload, gamma=0.0)
    assert abs(value[0] - 2.5) < 1.0e-12
