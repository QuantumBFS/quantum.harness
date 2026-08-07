from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Hard gate before a formal Table-I Jacobian measurement"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-coupling-drift", type=float, required=True)
    parser.add_argument("--expected-operators", type=int, default=13)
    parser.add_argument("--minimum-validation-runs", type=int, default=16)
    parser.add_argument("--minimum-validation-measurements", type=int, default=1000)
    parser.add_argument("--expected-family-alpha", type=float, default=0.05)
    return parser.parse_args()


def assess_gate(
    input_directory: Path,
    *,
    max_coupling_drift: float,
    expected_operators: int,
    minimum_validation_runs: int,
    minimum_validation_measurements: int,
    expected_family_alpha: float,
) -> dict[str, object]:
    if max_coupling_drift <= 0.0:
        raise ValueError("max coupling drift must be positive")
    if expected_operators <= 0:
        raise ValueError("expected operators must be positive")
    summary = json.loads(
        (input_directory / "summary.json").read_text(encoding="utf-8")
    )
    convergence = json.loads(
        (input_directory / "convergence.json").read_text(encoding="utf-8")
    )
    validation = json.loads(
        (input_directory / "frozen_validation.json").read_text(encoding="utf-8")
    )

    names = summary.get("operator_names")
    couplings = summary.get("final_renormalized_couplings")
    drift = convergence.get("coupling_drift_90_to_100_percent")
    z_scores = validation.get("z_scores_against_uniform_target")
    complete_vectors = (
        isinstance(names, list)
        and isinstance(couplings, list)
        and isinstance(drift, list)
        and isinstance(z_scores, list)
        and len(names) == expected_operators
        and len(couplings) == expected_operators
        and len(drift) == expected_operators
        and len(z_scores) == expected_operators
    )
    finite_vectors = complete_vectors and all(
        math.isfinite(float(value))
        for vector in (couplings, drift, z_scores)
        for value in vector
    )

    reported_drift = convergence.get(
        "max_abs_coupling_drift_90_to_100_percent"
    )
    computed_drift = (
        max(abs(float(value)) for value in drift) if finite_vectors else math.inf
    )
    drift_consistent = (
        reported_drift is not None
        and math.isfinite(float(reported_drift))
        and math.isclose(
            float(reported_drift), computed_drift, rel_tol=1.0e-12, abs_tol=1.0e-15
        )
    )

    max_abs_z = validation.get("max_abs_z")
    critical_abs_z = validation.get("bonferroni_critical_abs_z")
    alpha = validation.get("family_alpha")
    familywise_numeric_pass = (
        max_abs_z is not None
        and critical_abs_z is not None
        and math.isfinite(float(max_abs_z))
        and math.isfinite(float(critical_abs_z))
        and float(max_abs_z) <= float(critical_abs_z)
    )
    gates = {
        "complete_13_component_vectors": complete_vectors,
        "all_vector_values_finite": bool(finite_vectors),
        "late_window_statistics_available": (
            convergence.get("late_statistics_status")
            == "ESTIMATED_FROM_LATE_WINDOW_CHUNKS"
        ),
        "late_covariance_positive_definite": (
            convergence.get("covariance_status") == "POSITIVE_DEFINITE"
        ),
        "coupling_drift_report_consistent": drift_consistent,
        "complete_coupling_vector_stable": (
            drift_consistent and computed_drift <= max_coupling_drift
        ),
        "validation_run_count_sufficient": (
            int(validation.get("independent_runs", 0)) >= minimum_validation_runs
        ),
        "validation_measurements_sufficient": (
            int(validation.get("measurement_sweeps_per_run", 0))
            >= minimum_validation_measurements
        ),
        "family_alpha_matches_protocol": (
            alpha is not None
            and math.isclose(
                float(alpha), expected_family_alpha, rel_tol=0.0, abs_tol=1.0e-15
            )
        ),
        "all_13_frozen_moments_pass_bonferroni": (
            validation.get("familywise_status") == "PASS"
            and familywise_numeric_pass
        ),
    }
    status = "PASS" if all(gates.values()) else "FAIL"
    return {
        "status": status,
        "scope": "formal_RG2_pre_Jacobian_hard_gate",
        "input": str(input_directory.resolve()),
        "criteria_source": "preregistered_implementation_criteria_not_paper_published",
        "thresholds": {
            "maximum_absolute_component_drift_90_to_100_percent": max_coupling_drift,
            "expected_operator_count": expected_operators,
            "minimum_validation_runs": minimum_validation_runs,
            "minimum_validation_measurements_per_run": minimum_validation_measurements,
            "family_alpha": expected_family_alpha,
            "multiple_testing_method": "two_sided_bonferroni",
        },
        "observed": {
            "component_drift_90_to_100_percent": drift,
            "maximum_absolute_component_drift": (
                computed_drift if math.isfinite(computed_drift) else None
            ),
            "frozen_moment_z_scores": z_scores,
            "maximum_absolute_frozen_moment_z": max_abs_z,
            "bonferroni_critical_absolute_z": critical_abs_z,
        },
        "gates": gates,
        "failed_gates": [name for name, passed in gates.items() if not passed],
    }


def main() -> None:
    args = parse_args()
    input_directory = args.input.resolve()
    output = (args.output or input_directory / "gate_report.json").resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite RG gate report: {output}")
    report = assess_gate(
        input_directory,
        max_coupling_drift=args.max_coupling_drift,
        expected_operators=args.expected_operators,
        minimum_validation_runs=args.minimum_validation_runs,
        minimum_validation_measurements=args.minimum_validation_measurements,
        expected_family_alpha=args.expected_family_alpha,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
