from __future__ import annotations

from collections import Counter

import numpy as np
import pytest
from scipy.special import logsumexp

from scalable_v1.routes.occupation_autoregressive.constraints import (
    FeasibilityTable,
    occupation_m2,
)
from scalable_v1.routes.occupation_autoregressive.model import AutoregressiveNQS


def _tiny_model(*, seed: int = 848, width: int = 4) -> AutoregressiveNQS:
    return AutoregressiveNQS.initialize(
        n_electrons=2,
        two_q=5,
        target_m2=0,
        width=width,
        layers=2,
        seed=seed,
        max_trainable_parameters=262_144,
    )


@pytest.mark.parametrize("sector", ["ground", "excited"])
def test_model_log_probabilities_normalize_on_tiny_support(sector: str) -> None:
    model = _tiny_model()
    support = model.feasibility.enumerate_support()

    log_norm = logsumexp(
        [2.0 * model.logpsi(state, sector).real for state in support]
    )

    assert log_norm == pytest.approx(0.0, abs=1.0e-12)


def test_ground_and_excited_share_only_the_exact_trunk_arrays() -> None:
    model = _tiny_model()
    ground = model.sector_parameters("ground")
    excited = model.sector_parameters("excited")

    assert tuple(ground) == (
        "W1",
        "b1",
        "W2",
        "b2",
        "amplitude_W",
        "amplitude_b",
        "phase_W",
        "phase_b",
    )
    for name in ("W1", "b1", "W2", "b2"):
        assert ground[name] is excited[name]
    for name in ("amplitude_W", "amplitude_b", "phase_W", "phase_b"):
        assert ground[name] is not excited[name]


def test_seed_848_initialization_and_sampling_are_deterministic() -> None:
    first = _tiny_model(seed=848)
    second = _tiny_model(seed=848)

    assert tuple(first.parameter_slices) == tuple(second.parameter_slices)
    assert first.parameter_count == second.parameter_count
    np.testing.assert_array_equal(first.flat_parameters(), second.flat_parameters())
    np.testing.assert_array_equal(
        first.sample(size=256, sector="ground", seed=848),
        second.sample(size=256, sector="ground", seed=848),
    )


def test_infeasible_state_is_rejected() -> None:
    model = _tiny_model()

    with pytest.raises(ValueError, match="fixed-N fixed-M2 sector"):
        model.logpsi(0, "ground")
    with pytest.raises(ValueError, match="fixed-N fixed-M2 sector"):
        model.log_derivative((1 << 0) | (1 << 1), "excited")


def test_parameter_cap_and_non_two_layer_architectures_are_rejected() -> None:
    with pytest.raises(ValueError, match="parameter cap"):
        AutoregressiveNQS.initialize(
            n_electrons=2,
            two_q=5,
            target_m2=0,
            width=4,
            layers=2,
            seed=848,
            max_trainable_parameters=1,
        )
    with pytest.raises(ValueError, match="exactly two"):
        AutoregressiveNQS.initialize(
            n_electrons=2,
            two_q=5,
            target_m2=0,
            width=4,
            layers=1,
            seed=848,
            max_trainable_parameters=262_144,
        )


def _central_difference_all_parameters(
    model: AutoregressiveNQS,
    state: int,
    sector: str,
    *,
    step: float,
) -> np.ndarray:
    original = model.flat_parameters()
    numeric = np.empty(original.size, dtype=np.complex128)
    try:
        for index in range(original.size):
            plus = original.copy()
            minus = original.copy()
            plus[index] += step
            minus[index] -= step
            model.set_flat_parameters(plus)
            upper = model.logpsi(state, sector)
            model.set_flat_parameters(minus)
            lower = model.logpsi(state, sector)
            numeric[index] = (upper - lower) / (2.0 * step)
    finally:
        model.set_flat_parameters(original)
    return numeric


@pytest.mark.parametrize("sector", ["ground", "excited"])
def test_every_flat_analytic_log_derivative_matches_central_difference(
    sector: str,
) -> None:
    model = _tiny_model(width=3)
    state = (1 << 0) | (1 << 5)

    analytic = model.log_derivative(state, sector)
    numeric = _central_difference_all_parameters(
        model,
        state,
        sector,
        step=1.0e-6,
    )

    assert analytic.shape == (model.parameter_count,)
    np.testing.assert_allclose(analytic, numeric, rtol=2.0e-5, atol=2.0e-7)


@pytest.mark.parametrize("sector", ["ground", "excited"])
def test_sampling_matches_autoregressive_probabilities_without_enumeration(
    monkeypatch: pytest.MonkeyPatch,
    sector: str,
) -> None:
    model = _tiny_model()
    support = model.feasibility.enumerate_support()
    expected = {
        state: float(np.exp(2.0 * model.logpsi(state, sector).real))
        for state in support
    }

    def forbidden_enumeration(self: FeasibilityTable) -> tuple[int, ...]:
        raise AssertionError("sample must not enumerate support")

    monkeypatch.setattr(FeasibilityTable, "enumerate_support", forbidden_enumeration)
    draws = model.sample(size=12_000, sector=sector, seed=848)
    frequencies = Counter(draws.tolist())

    assert set(frequencies) == set(support)
    assert all(state.bit_count() == 2 for state in draws)
    assert all(occupation_m2(state, 5) == 0 for state in draws)
    for state, probability in expected.items():
        assert frequencies[state] / len(draws) == pytest.approx(
            probability,
            abs=0.03,
        )
