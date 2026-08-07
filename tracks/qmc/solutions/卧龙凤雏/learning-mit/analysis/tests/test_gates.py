from analysis.gates import evaluate_claim_gates


def valid_inputs():
    return {
        "xy_interval": (0.22, 0.26),
        "xy_reference": (0.20, 0.28),
        "diii_width_count": 7,
        "opposite_phase_evidence": True,
        "streams_per_width": 8,
        "complete_blocks": 64,
        "oracle_pass": True,
        "invariant_pass": True,
        "casimir_fit_stable": True,
        "alpha_stable": True,
        "entanglement_c_eff": 0.34,
        "entanglement_standard_error": 0.02,
        "casimir_c_eff": 0.328,
        "casimir_standard_error": 0.025,
        "bootstrap_failure_fraction": 0.01,
    }


def test_claim_gate_emits_exact_candidate_state_and_central_charge():
    decision = evaluate_claim_gates(**valid_inputs())
    assert decision.status == "candidate"
    assert decision.publish_central_charge
    assert decision.central_charge == 0.328
    assert decision.reasons == ()


def test_claim_gate_retains_exploratory_value_and_lists_every_failed_gate():
    exploratory = valid_inputs()
    exploratory.update(
        {
            "diii_width_count": 4,
            "opposite_phase_evidence": False,
            "streams_per_width": 3,
            "complete_blocks": 31,
            "casimir_fit_stable": False,
            "alpha_stable": False,
            "casimir_c_eff": 0.50,
            "casimir_standard_error": 0.01,
        }
    )
    decision = evaluate_claim_gates(**exploratory)
    assert decision.status == "exploratory"
    assert not decision.publish_central_charge
    assert decision.central_charge == 0.50
    assert decision.reasons == (
        "diii_transition_not_bracketed",
        "fewer_than_five_diii_widths",
        "fewer_than_four_streams_per_width",
        "fewer_than_32_complete_blocks",
        "casimir_fit_unstable",
        "anisotropy_unstable",
        "estimator_disagreement",
    )


def test_claim_gate_marks_unidentifiable_or_invalid_results_unavailable():
    invalid = valid_inputs()
    invalid["oracle_pass"] = False
    assert evaluate_claim_gates(**invalid).status == "unavailable"

    too_small = valid_inputs()
    too_small["diii_width_count"] = 3
    assert evaluate_claim_gates(**too_small).status == "unavailable"

    failed_bootstrap = valid_inputs()
    failed_bootstrap["bootstrap_failure_fraction"] = 0.051
    decision = evaluate_claim_gates(**failed_bootstrap)
    assert decision.status == "unavailable"
    assert decision.reasons == ("bootstrap_failure_rate_exceeds_5_percent",)


def test_claim_gate_keeps_entanglement_only_estimate_exploratory():
    inputs = valid_inputs()
    inputs.update(
        {
            "opposite_phase_evidence": False,
            "casimir_fit_stable": False,
            "alpha_stable": False,
            "casimir_c_eff": None,
            "casimir_standard_error": None,
        }
    )
    decision = evaluate_claim_gates(**inputs)
    assert decision.status == "exploratory"
    assert decision.central_charge == 0.34
    assert "casimir_estimate_unavailable" in decision.reasons
