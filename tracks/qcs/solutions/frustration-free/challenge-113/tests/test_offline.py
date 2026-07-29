from __future__ import annotations

import numpy as np

from qcontrol.device import Observation
from qcontrol.offline import cumulative_best_exact_infidelity


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
