from analysis.gates import evaluate_claim_gates


def valid_inputs():
    return {
        "xy_interval": (0.22, 0.26),
        "xy_reference": (0.20, 0.28),
        "diii_width_count": 7,
        "opposite_phase_evidence": True,
        "oracle_pass": True,
        "invariant_pass": True,
        "effective_sample_size": 80.0,
        "minimum_effective_sample_size": 40.0,
        "fit_stable": True,
        "alpha_stable": True,
        "casimir_amplitude": 0.41,
        "alpha": 1.25,
    }


def test_claim_gate_emits_exact_candidate_state_and_central_charge():
    decision = evaluate_claim_gates(**valid_inputs())
    assert decision.status == "xy_reproduced_diii_candidate"
    assert decision.publish_central_charge
    assert decision.central_charge == 0.41 / 1.25


def test_claim_gate_separates_inconclusive_from_failed_validation():
    inconclusive = valid_inputs()
    inconclusive["diii_width_count"] = 4
    decision = evaluate_claim_gates(**inconclusive)
    assert decision.status == "xy_reproduced_diii_inconclusive"
    assert not decision.publish_central_charge

    failed = valid_inputs()
    failed["oracle_pass"] = False
    decision = evaluate_claim_gates(**failed)
    assert decision.status == "validation_failed"
