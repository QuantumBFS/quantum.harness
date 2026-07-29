from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from qcontrol.config import SystemConfig
from qcontrol.device import Observation
from qcontrol.offline import (
    classify_solver_termination,
    compute_geometry_diagnostics,
    cumulative_best_exact_infidelity,
    effective_ranks,
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
    ("result", "max_iterations", "max_evaluations", "expected"),
    (
        (
            SimpleNamespace(
                success=True,
                status=0,
                message="CONVERGENCE",
                nit=3,
                nfev=7,
                fun=0.1,
                x=np.zeros(1),
                jac=np.zeros(1),
            ),
            10,
            20,
            "converged",
        ),
        (
            SimpleNamespace(
                success=False,
                status=1,
                message="TOTAL NO. OF ITERATIONS REACHED LIMIT",
                nit=10,
                nfev=12,
                fun=0.1,
                x=np.zeros(1),
                jac=np.zeros(1),
            ),
            10,
            20,
            "iteration_limit",
        ),
        (
            SimpleNamespace(
                success=False,
                status=1,
                message="TOTAL NO. OF F AND G EVALUATIONS EXCEEDS LIMIT",
                nit=4,
                nfev=20,
                fun=0.1,
                x=np.zeros(1),
                jac=np.zeros(1),
            ),
            10,
            20,
            "evaluation_limit",
        ),
        (
            SimpleNamespace(
                success=False,
                status=2,
                message="ABNORMAL_TERMINATION_IN_LNSRCH",
                nit=4,
                nfev=12,
                fun=0.1,
                x=np.zeros(1),
                jac=np.zeros(1),
            ),
            10,
            20,
            "line_search_failure",
        ),
        (
            SimpleNamespace(
                success=False,
                status=2,
                message="NAN RESULT",
                nit=1,
                nfev=2,
                fun=np.nan,
                x=np.zeros(1),
                jac=np.zeros(1),
            ),
            10,
            20,
            "numerical_failure",
        ),
        (
            SimpleNamespace(
                success=False,
                status=3,
                message="CALLBACK HALT",
                nit=1,
                nfev=2,
                fun=0.1,
                x=np.zeros(1),
                jac=np.zeros(1),
            ),
            10,
            20,
            "solver_failure",
        ),
        (
            SimpleNamespace(
                success=False,
                status=1,
                message="TOTAL NO. OF ITERATIONS REACHED LIMIT",
                nit=0,
                nfev=1,
                fun=0.1,
                x=np.zeros(1),
                jac=np.zeros(1),
            ),
            10,
            20,
            "solver_failure",
        ),
    ),
)
def test_solver_termination_categories_use_status_message_and_counters(
    result,
    max_iterations,
    max_evaluations,
    expected,
) -> None:
    assert (
        classify_solver_termination(
            result,
            max_iterations=max_iterations,
            max_evaluations=max_evaluations,
        )
        == expected
    )
