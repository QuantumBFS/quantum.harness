from analysis.gates import evaluate_gates


def passing_inputs():
    return {
        "oracle_pass": True,
        "max_invariant_error": 1e-12,
        "invariant_tolerance": 1e-9,
        "self_duality_z": 0.0,
        "minimum_ess": 200.0,
        "maximum_fit_shift_z": 0.5,
        "systematic_spread": 0.002,
        "maximum_studentized_residual": 1.0,
        "residual_trend": 0.0,
        "required": True,
    }


def test_target_gate_requires_containment_and_precision():
    result = evaluate_gates(ci_low=0.440, ci_high=0.454, **passing_inputs())
    assert result["by_name"]["target_interval"]["passed"]
    assert result["by_name"]["precision"]["passed"]
    result = evaluate_gates(ci_low=0.430, ci_high=0.466, **passing_inputs())
    assert result["by_name"]["target_interval"]["passed"]
    assert not result["by_name"]["precision"]["passed"]


def test_self_duality_boundary_is_inclusive():
    values = passing_inputs()
    values["self_duality_z"] = 1.96
    assert evaluate_gates(ci_low=0.44, ci_high=0.454, **values)["by_name"]["self_duality"]["passed"]
    values["self_duality_z"] = 1.961
    assert not evaluate_gates(ci_low=0.44, ci_high=0.454, **values)["by_name"]["self_duality"]["passed"]
