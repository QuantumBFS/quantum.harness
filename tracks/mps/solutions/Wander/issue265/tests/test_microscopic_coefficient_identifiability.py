from scripts.audit_microscopic_coefficient_identifiability import audit


def _record(start: float, stop: float, a: float, diffusion: float) -> dict:
    return {
        "inputs": {
            "t_window": [start, stop],
            "target_coefficients_used": False,
        },
        "microscopic_current_vertex": {"orientation_average_a": a},
        "frozen_weak_projection": {"a": a - 0.01, "D": diffusion},
        "mori_k0_correction": {
            "s": [0.5, 1.0, 2.0],
            "delta_K1_total_truncated": [-0.25, -0.28, -0.30],
        },
    }


def test_audit_never_promotes_projected_pair_to_physical_identity() -> None:
    result = audit(
        {
            "coarse": _record(50.0, 200.0, 0.231, 1.95),
            "medium": _record(50.0, 200.0, 0.228, 2.01),
            "fine": _record(50.0, 200.0, 0.229, 1.99),
        },
        {"convergence_accepted": True},
    )
    assert result["gate_audit"]["finite_time_kernel_frozen"] is True
    assert result["exact_microscopic_result"][
        "physical_zero_field_quadratic_current_vertex"
    ] == 0.0
    assert result["exact_microscopic_result"]["highest_even_mori_moment_order"] == 26
    assert result["exact_microscopic_result"]["highest_finite_momentum_closed_form_order"] == 16
    assert result["exact_microscopic_result"]["exact_lanczos_recurrent_count"] == 13
    assert result["identifiability_verdict"][
        "unique_physical_scalar_burgers_pair_proven"
    ] is False


def test_partial_checkpoint_does_not_pass_full_window_gate() -> None:
    result = audit(
        {
            "coarse": _record(50.0, 200.0, 0.231, 1.95),
            "medium": _record(50.0, 116.0, 0.228, 2.01),
            "fine": _record(20.0, 36.0, 0.41, 1.1),
        },
        {"convergence_accepted": False},
    )
    assert result["gate_audit"]["full_window_resolution_count"] == 1
    assert result["gate_audit"]["finite_time_kernel_frozen"] is False
    assert result["identifiability_verdict"]["constant_long_time_coefficients_proven"] is False
