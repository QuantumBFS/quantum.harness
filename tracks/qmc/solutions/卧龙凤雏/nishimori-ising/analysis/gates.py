TARGET_CENTRAL_CHARGE = 0.464


def _gate(name: str, value, criterion: str, passed: bool, required: bool) -> dict:
    return {
        "name": name,
        "value": value,
        "criterion": criterion,
        "passed": bool(passed),
        "required": bool(required),
    }


def evaluate_gates(
    *,
    central_charge: float,
    standard_error: float,
    ci_low: float,
    ci_high: float,
    fit_window_ci_low: float,
    fit_window_ci_high: float,
    half_stability_z: float,
    replica_stability_z: float,
    identity_error: float,
    negative_bond_z: float,
    runtime_s: float,
    required: bool,
) -> dict:
    gates = [
        _gate(
            "target_agreement",
            abs(central_charge - TARGET_CENTRAL_CHARGE),
            "|c_eff - 0.464| <= 0.020",
            abs(central_charge - TARGET_CENTRAL_CHARGE) <= 0.020,
            required,
        ),
        _gate(
            "target_in_confidence_interval",
            [ci_low, ci_high],
            "95% CI contains 0.464",
            ci_low <= TARGET_CENTRAL_CHARGE <= ci_high,
            required,
        ),
        _gate(
            "standard_error",
            standard_error,
            "SE(c_eff) <= 0.010",
            standard_error <= 0.010,
            required,
        ),
        _gate(
            "fit_window_agreement",
            [fit_window_ci_low, fit_window_ci_high],
            "paired-bootstrap 95% CI for c(Lmin=4)-c(Lmin=6) contains zero",
            fit_window_ci_low <= 0.0 <= fit_window_ci_high,
            required,
        ),
        _gate(
            "half_run_stability",
            half_stability_z,
            "first/second-half discrepancy < 4 sigma",
            half_stability_z < 4.0,
            required,
        ),
        _gate(
            "replica_stability",
            replica_stability_z,
            "maximum leave-one-replica-out discrepancy < 4 sigma",
            replica_stability_z < 4.0,
            required,
        ),
        _gate(
            "nishimori_energy_identity",
            identity_error,
            "|d phi/dK - 2 tanh(K_N)| <= 0.005",
            identity_error <= 0.005,
            required,
        ),
        _gate(
            "negative_bond_frequency",
            negative_bond_z,
            "|bond-frequency z| < 4",
            abs(negative_bond_z) < 4.0,
            required,
        ),
        _gate(
            "runtime",
            runtime_s,
            "end-to-end runtime < 600 s",
            runtime_s < 600.0,
            required,
        ),
    ]
    return {
        "target_central_charge": TARGET_CENTRAL_CHARGE,
        "gates": gates,
        "all_required_pass": all(
            gate["passed"] for gate in gates if gate["required"]
        ),
    }
