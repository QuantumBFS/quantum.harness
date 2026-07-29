from analysis.gates import evaluate_gates


def test_all_nine_production_gates_pass_for_a_high_precision_target_result():
    gates = evaluate_gates(
        central_charge=0.463,
        standard_error=0.004,
        ci_low=0.455,
        ci_high=0.471,
        diagnostic_central_charge=0.469,
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
        diagnostic_central_charge=0.49,
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
