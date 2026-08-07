from __future__ import annotations

import numpy as np

from vmcrg_ref.mps_patch import PatchMPS
from vmcrg_ref.mps_vmcrg import residual_parameter_gradient
from vmcrg_ref.multi_optimizer import MultiOperatorOptimizer
from vmcrg_ref.operators import EVEN_SHAPES
from vmcrg_ref.patch_table import PatchLookupTable


def test_zero_alpha_has_zero_core_gradient() -> None:
    model = PatchMPS.random(chi=2, seed=20260870)
    histogram = np.arange(1, 513, dtype=np.float64)
    gradient_alpha, gradient_cores = residual_parameter_gradient(
        model, alpha=0.0, mean_histogram=histogram
    )
    assert np.isfinite(gradient_alpha)
    assert gradient_cores.norm() == 0.0


def test_mps_residual_gradient_finite_difference() -> None:
    rng = np.random.default_rng(20260871)
    model = PatchMPS.random(chi=2, seed=20260872)
    histogram = rng.multinomial(25, np.full(512, 1.0 / 512.0)).astype(float)
    alpha = 0.3
    gradient_alpha, gradient_cores = residual_parameter_gradient(
        model, alpha=alpha, mean_histogram=histogram
    )
    lookup = PatchLookupTable.from_model(model)
    expected_alpha = float(histogram @ lookup.values) / histogram.sum()
    assert abs(gradient_alpha - expected_alpha) < 1e-12

    core_index = 5
    index = (1, 1, 0)
    epsilon = 1e-6
    original = float(model.cores[core_index][index])
    model.cores[core_index][index] = original + epsilon
    plus = alpha * float(histogram @ PatchLookupTable.from_model(model).values)
    model.cores[core_index][index] = original - epsilon
    minus = alpha * float(histogram @ PatchLookupTable.from_model(model).values)
    model.cores[core_index][index] = original
    numeric = (plus - minus) / (2.0 * epsilon * histogram.sum())
    assert abs(float(gradient_cores.cores[core_index][index]) - numeric) < 2e-6


def test_traditional_optimizer_progress_callback() -> None:
    records = []
    optimizer = MultiOperatorOptimizer(
        length=9,
        couplings=np.array([0.2]),
        shapes=(EVEN_SHAPES[0],),
        walkers=2,
        seed=20260873,
        compiled=True,
        parallel_walkers=False,
    )
    result = optimizer.run(
        steps=2,
        sweeps_per_step=1,
        learning_rate=1e-3,
        callback=records.append,
    )
    assert records == result
