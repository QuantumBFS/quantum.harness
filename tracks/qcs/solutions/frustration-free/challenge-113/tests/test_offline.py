from __future__ import annotations

import numpy as np
import pytest

from qcontrol.config import SystemConfig
from qcontrol.device import Observation
from qcontrol.offline import (
    ExactInfidelityTrajectory,
    RestrictedOptimizationResult,
    canonical_solver_message_code,
    classify_solver_termination,
    compute_geometry_diagnostics,
    cumulative_best_exact_infidelity,
    effective_ranks,
    finalize_restricted_attained_bound,
)
from qcontrol.pulses import PulseSpace
from qcontrol.systems import make_system


def test_exact_trajectory_aligns_failed_queries_with_carry_forward() -> None:
    fidelities = {
        (0.0,): 0.5,
        (0.2,): 0.8,
        (0.9,): 0.99,
        (0.4,): 0.9,
    }

    def evaluate(pulse: object) -> float:
        return fidelities[tuple(np.asarray(pulse, dtype=np.float64))]

    successful_one = Observation(0.7, 1_000, 1, False, 1)
    successful_three = Observation(0.8, 1_000, 3, False, 3)

    result = cumulative_best_exact_infidelity(
        evaluate,
        initial_pulse=np.asarray([0.0]),
        audited_queries=(
            (np.asarray([0.2]), successful_one),
            (np.asarray([0.9]), None),
            (np.asarray([0.4]), successful_three),
        ),
    )

    assert result.initial_infidelity == 0.5
    np.testing.assert_allclose(
        result.cumulative_best_by_optimizer_query,
        (0.2, 0.2, 0.1),
        rtol=0.0,
        atol=1e-15,
    )


def test_effective_ranks_are_relative_and_rescaling_invariant() -> None:
    spectrum = np.asarray([100.0, -1e-5, 0.0])
    thresholds = (1e-6, 1e-8, 1e-10)

    assert effective_ranks(spectrum, thresholds) == (1, 2, 2)
    assert effective_ranks(1e-12 * spectrum, thresholds) == (1, 2, 2)
    assert effective_ranks(np.zeros(4), thresholds) == (0, 0, 0)
    with pytest.raises(ValueError, match="finite"):
        effective_ranks(np.asarray([1.0, np.nan]), thresholds)


@pytest.mark.parametrize(
    ("system_config", "expected_dimension"),
    (
        (SystemConfig("one_qubit", 1, 4.0), 2),
        (SystemConfig("two_qubit", 2, 4.0), 4),
    ),
)
def test_zero_gap_geometry_fixtures_cover_d2_and_d4(
    system_config,
    expected_dimension,
) -> None:
    model = make_system(system_config)
    assert model.dimension == expected_dimension
    pulse_space = PulseSpace.from_system(model, system_config.segments)
    geometry = compute_geometry_diagnostics(
        model,
        model,
        pulse_space,
        np.zeros(pulse_space.parameter_count),
    )

    assert len(geometry.model_eigenvalues) == pulse_space.parameter_count
    assert geometry.model_effective_ranks == geometry.truth_effective_ranks
    assert max(map(abs, geometry.signed_eigenvalue_gaps)) == 0.0
    assert max(geometry.principal_angles_radians) < 1e-7


@pytest.mark.parametrize(
    ("facts", "expected"),
    (
        (
            {
                "success": True,
                "status": 0,
                "message_code": "convergence",
                "output_finite": True,
                "nit": 3,
                "nfev": 7,
                "max_iterations": 10,
                "max_evaluations": 20,
            },
            "converged",
        ),
        (
            {
                "success": False,
                "status": 1,
                "message_code": "iteration_limit",
                "output_finite": True,
                "nit": 10,
                "nfev": 12,
                "max_iterations": 10,
                "max_evaluations": 20,
            },
            "iteration_limit",
        ),
        (
            {
                "success": False,
                "status": 1,
                "message_code": "evaluation_limit",
                "output_finite": True,
                "nit": 4,
                "nfev": 20,
                "max_iterations": 10,
                "max_evaluations": 20,
            },
            "evaluation_limit",
        ),
        (
            {
                "success": False,
                "status": 2,
                "message_code": "line_search_failure",
                "output_finite": True,
                "nit": 4,
                "nfev": 12,
                "max_iterations": 10,
                "max_evaluations": 20,
            },
            "line_search_failure",
        ),
        (
            {
                "success": False,
                "status": 2,
                "message_code": "numerical_failure",
                "output_finite": False,
                "nit": 1,
                "nfev": 2,
                "max_iterations": 10,
                "max_evaluations": 20,
            },
            "numerical_failure",
        ),
        (
            {
                "success": False,
                "status": 3,
                "message_code": "solver_failure",
                "output_finite": True,
                "nit": 1,
                "nfev": 2,
                "max_iterations": 10,
                "max_evaluations": 20,
            },
            "solver_failure",
        ),
    ),
)
def test_solver_termination_categories_use_only_raw_facts(facts, expected) -> None:
    assert classify_solver_termination(**facts) == expected


@pytest.mark.parametrize(
    "mutation",
    (
        {"success": False, "status": 0},
        {"success": True, "status": 1},
        {"message_code": "numerical_failure", "output_finite": True},
        {"message_code": "iteration_limit", "nit": 0},
        {"message_code": "evaluation_limit", "nfev": 0},
    ),
)
def test_solver_termination_rejects_contradictory_raw_facts(mutation) -> None:
    facts = {
        "success": False,
        "status": 2,
        "message_code": "line_search_failure",
        "output_finite": True,
        "nit": 2,
        "nfev": 4,
        "max_iterations": 10,
        "max_evaluations": 20,
    }
    facts.update(mutation)
    with pytest.raises(ValueError, match="solver"):
        classify_solver_termination(**facts)


@pytest.mark.parametrize(
    ("message", "code"),
    (
        ("CONVERGENCE: NORM_OF_PROJECTED_GRADIENT_<=_PGTOL", "convergence"),
        ("STOP: TOTAL NO. of ITERATIONS REACHED LIMIT", "iteration_limit"),
        ("TOTAL NO. OF F AND G EVALUATIONS EXCEEDS LIMIT", "evaluation_limit"),
        ("ABNORMAL_TERMINATION_IN_LNSRCH", "line_search_failure"),
        ("NaN result", "numerical_failure"),
        ("callback halt", "solver_failure"),
    ),
)
def test_solver_message_codes_are_canonical(message, code) -> None:
    assert canonical_solver_message_code(message) == code


def test_audited_candidate_can_supply_final_restricted_upper_bound() -> None:
    cached = RestrictedOptimizationResult(
        attained_infidelity_upper_bound=0.4,
        starting_infidelity_upper_bound=0.6,
        max_iterations=100,
        max_evaluations=1_000,
        gradient_tolerance=1e-9,
        consistency_tolerance=1e-10,
        nfev=5,
        nit=2,
        solver_success=True,
        solver_status=0,
        solver_message_code="convergence",
        solver_output_finite=True,
        termination="converged",
    )
    exact = ExactInfidelityTrajectory(
        initial_infidelity=0.6,
        cumulative_best_by_optimizer_query=(0.6, 0.1),
        best_successful_audited_infidelity=0.1,
    )

    payload = finalize_restricted_attained_bound(cached, exact)

    assert payload["cached_solver_attained_infidelity_upper_bound"] == 0.4
    assert payload["attained_infidelity_upper_bound"] == 0.1
    assert payload["attained_infidelity_source"] == "audited_candidate"
