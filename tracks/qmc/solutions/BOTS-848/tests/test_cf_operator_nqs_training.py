from __future__ import annotations

from collections.abc import Callable

import numpy as np

from scalable_v1.routes.cf_operator_nqs.model import CFOperatorNQS


def _configs(seed: int = 848, *, batch: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    values = rng.normal(size=(batch, 2, 2)) + 1j * rng.normal(
        size=(batch, 2, 2)
    )
    return values / np.linalg.norm(values, axis=-1, keepdims=True)


def _fake_action() -> Callable[[object], tuple[np.ndarray, np.ndarray]]:
    def action(configs: object) -> tuple[np.ndarray, np.ndarray]:
        values = np.asarray(configs, dtype=np.complex128)
        batch = values.shape[0]
        coordinate = np.sum(values.real, axis=(1, 2))
        seeds = np.empty((batch, 6), dtype=np.complex128)
        actions = np.empty((batch, 6, 3), dtype=np.complex128)
        for sector in range(6):
            seeds[:, sector] = 1.0 + 0.1 * sector + 0.01j * coordinate
            for rank in range(3):
                actions[:, sector, rank] = (
                    (rank + 1) * (0.02 + 0.003j * sector) * (1.0 + coordinate)
                )
        return seeds, actions

    return action


def test_model_identity_initialization_and_shared_excited_head() -> None:
    action = _fake_action()
    configs = _configs()
    model = CFOperatorNQS.initialize(
        n_electrons=2,
        two_q=3,
        hidden_width=64,
        seed=848,
        action_kernel=action,
    )

    seeds, _actions = action(configs)
    np.testing.assert_allclose(model.amplitudes(configs), seeds)
    assert model.head_for_sector(0) == "ground"
    assert {model.head_for_sector(index) for index in range(1, 6)} == {
        "excited"
    }
    assert model.parameter_count <= 262_144


def test_model_analytic_log_derivative_matches_central_difference() -> None:
    model = CFOperatorNQS.initialize(
        n_electrons=2,
        two_q=3,
        hidden_width=3,
        seed=1848,
        action_kernel=_fake_action(),
    )
    parameters = np.linspace(-0.03, 0.04, model.parameter_count)
    model.set_flat_parameters(parameters)
    config = _configs(1848, batch=1)
    analytic = model.log_derivative(config, sector_index=3)[0]
    finite = np.empty(model.parameter_count, dtype=np.complex128)
    step = 1.0e-6
    for index in range(model.parameter_count):
        plus = parameters.copy()
        minus = parameters.copy()
        plus[index] += step
        minus[index] -= step
        model.set_flat_parameters(plus)
        plus_log = model.log_amplitudes(config)[0, 3]
        model.set_flat_parameters(minus)
        minus_log = model.log_amplitudes(config)[0, 3]
        finite[index] = (plus_log - minus_log) / (2.0 * step)
    model.set_flat_parameters(parameters)

    np.testing.assert_allclose(analytic, finite, rtol=3.0e-4, atol=3.0e-6)


def test_model_flat_parameters_are_copy_safe() -> None:
    model = CFOperatorNQS.initialize(
        n_electrons=2,
        two_q=3,
        hidden_width=3,
        seed=2848,
        action_kernel=_fake_action(),
    )
    expected = model.flat_parameters()
    mutated = model.flat_parameters()
    mutated[:] = 123.0
    np.testing.assert_array_equal(model.flat_parameters(), expected)
