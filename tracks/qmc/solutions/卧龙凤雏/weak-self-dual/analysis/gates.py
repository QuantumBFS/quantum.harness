TARGET_CENTRAL_CHARGE = 0.447


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
    ci_low: float,
    ci_high: float,
    oracle_pass: bool,
    max_invariant_error: float,
    invariant_tolerance: float,
    self_duality_z: float,
    minimum_ess: float,
    maximum_fit_shift_z: float,
    systematic_spread: float,
    maximum_studentized_residual: float,
    residual_trend: float,
    required: bool,
) -> dict:
    half_width = 0.5 * (ci_high - ci_low)
    gates = [
        _gate("exact_oracles", oracle_pass, "all exact oracle tolerances pass", oracle_pass, required),
        _gate(
            "gaussian_invariants",
            max_invariant_error,
            f"maximum invariant error <= {invariant_tolerance}",
            max_invariant_error <= invariant_tolerance,
            required,
        ),
        _gate(
            "self_duality",
            self_duality_z,
            "|electric-minus-magnetic z| <= 1.96",
            abs(self_duality_z) <= 1.96,
            required,
        ),
        _gate("effective_sample_size", minimum_ess, "minimum ESS >= 100", minimum_ess >= 100, required),
        _gate(
            "target_interval",
            [ci_low, ci_high],
            "95% CI contains 0.447",
            ci_low <= TARGET_CENTRAL_CHARGE <= ci_high,
            required,
        ),
        _gate("precision", half_width, "95% half-width <= 0.01", half_width <= 0.01, required),
        _gate(
            "fit_stability",
            maximum_fit_shift_z,
            "maximum paired fit shift < 2 sigma",
            maximum_fit_shift_z < 2.0,
            required,
        ),
        _gate(
            "systematic_spread",
            systematic_spread,
            "required fit centers span <= 0.01",
            systematic_spread <= 0.01,
            required,
        ),
        _gate(
            "residuals",
            maximum_studentized_residual,
            "maximum |studentized residual| < 3",
            maximum_studentized_residual < 3.0,
            required,
        ),
        _gate(
            "residual_trend",
            residual_trend,
            "|corr(residual,1/L)| < 0.8",
            abs(residual_trend) < 0.8,
            required,
        ),
    ]
    return {
        "target_central_charge": TARGET_CENTRAL_CHARGE,
        "gates": gates,
        "by_name": {gate["name"]: gate for gate in gates},
        "all_required_pass": all(gate["passed"] for gate in gates if gate["required"]),
    }
