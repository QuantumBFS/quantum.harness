from __future__ import annotations

import numpy as np

from vmcrg_ref.issue28_validation import (
    excess_patch_tv_components,
    scientific_round_gates_pass,
)


def test_excess_patch_tv_removes_independent_empirical_noise() -> None:
    uniform = np.full(512, 1.0 / 512.0)
    observed = uniform.copy()
    target = uniform.copy()
    observed[:16] = 0.0
    observed[16:32] *= 2.0
    target[32:48] = 0.0
    target[48:64] *= 2.0

    observed_tv, target_tv, excess = excess_patch_tv_components(observed, target)

    raw_two_sample = 0.5 * np.abs(observed - target).sum()
    assert raw_two_sample > 0.02
    assert observed_tv == target_tv
    assert abs(float(excess)) < 1e-15


def test_scientific_round_gate_requires_every_frozen_condition() -> None:
    passing = {
        "training": "CONVERGED",
        "validation": "PASS",
        "objective": "IDENTIFIABLE",
    }
    assert scientific_round_gates_pass(passing)
    assert not scientific_round_gates_pass({**passing, "validation": "FAIL"})
    assert not scientific_round_gates_pass(
        {**passing, "objective_improvement": "FAIL"}
    )
