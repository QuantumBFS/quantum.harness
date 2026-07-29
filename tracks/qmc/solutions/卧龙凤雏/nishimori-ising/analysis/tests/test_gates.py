from analysis.gates import evaluate_gates


def test_all_nine_production_gates_pass_for_a_high_precision_target_result():
    gates = evaluate_gates(
        central_charge=0.463,
        standard_error=0.004,
        ci_low=0.455,
        ci_high=0.471,
        fit_window_ci_low=-0.012,
        fit_window_ci_high=0.008,
        half_stability_z=1.2,
        replica_stability_z=2.1,
        identity_error=0.001,
        negative_bond_z=0.7,
        runtime_s=412.0,
        required=True,
    )
    assert len(gates["gates"]) == 9
    assert gates["all_required_pass"]


def test_target_and_interval_fail_independently():
    gates = evaluate_gates(
        central_charge=0.49,
        standard_error=0.004,
        ci_low=0.48,
        ci_high=0.50,
        fit_window_ci_low=-0.01,
        fit_window_ci_high=0.01,
        half_stability_z=1.0,
        replica_stability_z=1.0,
        identity_error=0.001,
        negative_bond_z=0.0,
        runtime_s=100.0,
        required=True,
    )
    by_name = {gate["name"]: gate for gate in gates["gates"]}
    assert not by_name["target_agreement"]["passed"]
    assert not by_name["target_in_confidence_interval"]["passed"]
    assert not gates["all_required_pass"]


def test_fit_windows_agree_when_paired_bootstrap_interval_contains_zero():
    gates = evaluate_gates(
        central_charge=0.458,
        standard_error=0.009,
        ci_low=0.44,
        ci_high=0.476,
        fit_window_ci_low=-0.080,
        fit_window_ci_high=0.011,
        half_stability_z=1.0,
        replica_stability_z=1.0,
        identity_error=0.001,
        negative_bond_z=0.0,
        runtime_s=500.0,
        required=True,
    )
    by_name = {gate["name"]: gate for gate in gates["gates"]}
    assert by_name["fit_window_agreement"]["passed"]
