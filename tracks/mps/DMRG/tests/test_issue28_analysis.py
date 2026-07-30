from __future__ import annotations

import numpy as np

from vmcrg_ref.power import estimate_five_seed_power


def test_power_report_never_recommends_postformal_seed_addition() -> None:
    report = estimate_five_seed_power(
        np.array([-1.0, -0.5]),
        np.array([1.0, 1.2]),
        7,
    )
    assert report["formal_seed_count"] == 5
    assert report["postformal_seed_extension_allowed"] is False
    assert report["valid_negative_outcome"] == (
        "direction_correct_but_confidence_interval_misses_frozen_gate"
    )


def test_power_estimate_is_deterministic_and_uses_five_seed_means() -> None:
    effects = np.array([-0.4, -0.2, -0.1])
    variances = np.array([0.09, 0.04, 0.16])
    first = estimate_five_seed_power(effects, variances, 19)
    second = estimate_five_seed_power(effects, variances, 19)
    assert first == second
    assert 0.0 <= first["probability_ci_below_zero"] <= 1.0
    assert first["simulation_replicates"] >= 1000
