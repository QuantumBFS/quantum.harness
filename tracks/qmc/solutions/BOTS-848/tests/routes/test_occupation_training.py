from __future__ import annotations

from collections import Counter
import warnings

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


def test_public_parameter_views_are_read_only_and_shared() -> None:
    model = _tiny_model()
    ground = model.sector_parameters("ground")
    excited = model.sector_parameters("excited")

    for name in ("W1", "b1", "W2", "b2"):
        assert ground[name] is excited[name] is getattr(model, name)
    for parameters in (ground, excited):
        for array in parameters.values():
            assert not array.flags.writeable
            with pytest.raises(ValueError, match="read-only"):
                array.flat[0] = 0.0


def test_parameter_view_identities_survive_flat_updates() -> None:
    model = _tiny_model()
    before = {
        sector: dict(model.sector_parameters(sector))
        for sector in ("ground", "excited")
    }
    updated = model.flat_parameters() + np.linspace(
        1.0e-4,
        2.0e-4,
        model.parameter_count,
    )

    model.set_flat_parameters(updated)

    np.testing.assert_array_equal(model.flat_parameters(), updated)
    for sector in ("ground", "excited"):
        after = model.sector_parameters(sector)
        for name, view in before[sector].items():
            assert after[name] is view
            tree_name = f"trunk.{name}" if name in ("W1", "b1", "W2", "b2") else f"{sector}.{name}"
            parameter_slice = model.parameter_slices[tree_name]
            np.testing.assert_array_equal(
                after[name].reshape(-1),
                updated[parameter_slice],
            )


def test_sector_head_parameters_use_one_authoritative_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _tiny_model()

    assert "_heads" not in vars(model)
    original = model._parameter
    accessed: list[str] = []

    def recording_parameter(name: str) -> np.ndarray:
        value = original(name)
        assert value is model._parameters[name]
        accessed.append(name)
        return value

    monkeypatch.setattr(model, "_parameter", recording_parameter)
    state = (1 << 0) | (1 << 5)

    model.logpsi(state, "ground")
    model.log_derivative(state, "ground")

    assert {
        "ground.amplitude_W",
        "ground.amplitude_b",
        "ground.phase_W",
        "ground.phase_b",
    }.issubset(accessed)


@pytest.mark.parametrize("name", ["W1", "b1", "W2", "b2"])
def test_shared_trunk_public_rebinding_is_rejected(name: str) -> None:
    model = _tiny_model()

    with pytest.raises(AttributeError):
        setattr(model, name, np.zeros_like(getattr(model, name)))


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


@pytest.mark.parametrize("operation", ["logpsi", "sample"])
def test_non_finite_conditionals_are_rejected_without_runtime_warnings(
    operation: str,
) -> None:
    model = _tiny_model()
    model.set_flat_parameters(
        np.full(model.parameter_count, np.finfo(np.float64).max)
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        with pytest.raises(FloatingPointError, match="non-finite.*conditional"):
            if operation == "logpsi":
                model.logpsi((1 << 0) | (1 << 5), "ground")
            else:
                model.sample(size=8, sector="ground", seed=848)


@pytest.mark.parametrize("operation", ["logpsi", "sample"])
def test_finite_extreme_logits_are_rejected_without_normalization_warnings(
    operation: str,
) -> None:
    model = _tiny_model()
    parameters = np.zeros(model.parameter_count, dtype=np.float64)
    parameters[model.parameter_slices["ground.amplitude_b"]] = (
        -np.finfo(np.float64).max,
        np.finfo(np.float64).max,
    )
    model.set_flat_parameters(parameters)

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        with pytest.raises(FloatingPointError, match="non-finite.*conditional"):
            if operation == "logpsi":
                model.logpsi((1 << 0) | (1 << 5), "ground")
            else:
                model.sample(size=8, sector="ground", seed=848)


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


def test_sampling_uses_one_batched_amplitude_call_per_orbital(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _tiny_model()
    sample_count = 17
    calls: list[tuple[int, tuple[int, ...]]] = []
    parameter_calls: list[str] = []
    original_batch = model._conditional_batch
    original_parameter = model._parameter

    def phase_poison(name: str) -> np.ndarray:
        parameter_calls.append(name)
        if name.startswith("ground.phase_"):
            raise AssertionError("sampling must not access phase heads")
        return original_parameter(name)

    def recording_batch(
        prefixes: np.ndarray,
        orbital: int,
        remaining: np.ndarray,
        remaining_m2: np.ndarray,
        sector: str,
    ) -> np.ndarray:
        calls.append((orbital, prefixes.shape))
        result = original_batch(prefixes, orbital, remaining, remaining_m2, sector)
        assert isinstance(result, np.ndarray)
        assert result.shape == (sample_count, 2)
        return result

    def forbidden_scalar_path(*args: object, **kwargs: object) -> object:
        raise AssertionError(
            "sample must not use scalar conditional evaluation or its derivative cache"
        )

    monkeypatch.setattr(model, "_parameter", phase_poison)
    monkeypatch.setattr(model, "_conditional_batch", recording_batch)
    monkeypatch.setattr(model, "_conditional", forbidden_scalar_path)

    draws = model.sample(size=sample_count, sector="ground", seed=848)

    assert calls == [
        (orbital, (sample_count, model.n_orbitals))
        for orbital in range(model.n_orbitals)
    ]
    assert parameter_calls == [
        name
        for _ in range(model.n_orbitals)
        for name in ("ground.amplitude_W", "ground.amplitude_b")
    ]
    assert all(state.bit_count() == model.n_electrons for state in draws)
    assert all(
        occupation_m2(state, model.two_q) == model.target_m2
        for state in draws
    )


@pytest.mark.parametrize("sector", ["ground", "excited"])
def test_production_shape_batched_sampling_is_deterministic_and_sector_valid(
    sector: str,
) -> None:
    model = AutoregressiveNQS.initialize(
        n_electrons=6,
        two_q=15,
        target_m2=0,
        width=128,
        layers=2,
        seed=848,
        max_trainable_parameters=262_144,
    )

    first = model.sample(size=32, sector=sector, seed=848)
    second = model.sample(size=32, sector=sector, seed=848)

    np.testing.assert_array_equal(first, second)
    assert all(state.bit_count() == 6 for state in first)
    assert all(occupation_m2(state, 15) == 0 for state in first)
