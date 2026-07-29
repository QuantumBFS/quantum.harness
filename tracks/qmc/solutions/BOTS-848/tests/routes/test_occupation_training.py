from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import warnings

import numpy as np
import pytest
from scipy.special import logsumexp

from scalable_v1.routes.occupation_autoregressive.constraints import (
    FeasibilityTable,
    occupation_m2,
)
from scalable_v1.routes.occupation_autoregressive.model import AutoregressiveNQS
from scalable_v1.routes.occupation_autoregressive.operators import (
    PreparedPairOperator,
)
from scalable_v1.routes.occupation_autoregressive import train
from scalable_v1.routes.occupation_autoregressive.train import (
    AdamState,
    FeatureStateError,
    ReducedTrainingConfig,
    adam_update,
    atomic_save_npz,
    clip_gradient,
    run_reduced_training,
    score_covariance,
    _sector_estimators,
)
from train_occupation_autoregressive import main as training_main


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


def test_cumulative_phase_overflow_is_rejected_without_runtime_warnings() -> None:
    model = _tiny_model()
    parameters = np.zeros(model.parameter_count, dtype=np.float64)
    parameters[model.parameter_slices["ground.phase_b"]] = (
        np.finfo(np.float64).max / 2.0,
        np.finfo(np.float64).max / 2.0,
    )
    model.set_flat_parameters(parameters)

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        with pytest.raises(FloatingPointError, match="non-finite.*cumulative"):
            model.logpsi((1 << 0) | (1 << 5), "ground")


def test_reverse_derivative_overflow_is_rejected_without_runtime_warnings() -> None:
    model = _tiny_model()
    parameters = np.zeros(model.parameter_count, dtype=np.float64)
    parameters[model.parameter_slices["ground.phase_W"]] = (
        np.finfo(np.float64).max / 2.0
    )
    model.set_flat_parameters(parameters)
    state = (1 << 0) | (1 << 5)

    forward = model.logpsi(state, "ground")
    assert np.isfinite(forward.real)
    assert np.isfinite(forward.imag)

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        with pytest.raises(FloatingPointError, match="non-finite.*log-derivative"):
            model.log_derivative(state, "ground")


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


def _tiny_training_config(*, updates: int = 16, batch_size: int = 4) -> ReducedTrainingConfig:
    return ReducedTrainingConfig(
        training_seed=848,
        updates=updates,
        batch_size_per_sector=batch_size,
        learning_rate=1.0e-3,
        beta1=0.9,
        beta2=0.999,
        epsilon=1.0e-8,
        gradient_clip_norm=10.0,
        checkpoint_interval=128,
        protocol_sha256=(
            "2435cd2e72ffae88117ee194f45b15451c8653dafa755b732005b6a199251d38"
        ),
        comparison_sha="5aa9219f4cd24bc2274f0514b621c2f9b47cead7",
    )


def _zero_pair_operator(two_q: int) -> PreparedPairOperator:
    return PreparedPairOperator.build(
        (),
        np.zeros((0, 0), dtype=np.complex128),
        two_q,
    )


def _jsonl_records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_score_covariance_matches_explicit_complex_vmc_expression() -> None:
    scores = np.array(
        [
            [1.0 + 0.5j, -0.25 + 0.75j],
            [-0.5 + 0.25j, 0.5 - 1.0j],
            [0.75 - 0.5j, 1.25 + 0.25j],
        ],
        dtype=np.complex128,
    )
    local_values = np.array(
        [1.25 - 0.5j, -0.75 + 0.25j, 0.5 + 1.0j],
        dtype=np.complex128,
    )
    conjugate_scores = scores.conj()
    expected = 2.0 * np.real(
        np.mean(conjugate_scores * local_values[:, None], axis=0)
        - np.mean(conjugate_scores, axis=0) * np.mean(local_values)
    )

    observed = score_covariance(scores, local_values)

    np.testing.assert_allclose(observed, expected, rtol=0.0, atol=1.0e-15)


def test_global_gradient_clipping_uses_the_l2_norm() -> None:
    clipped, before, after = clip_gradient(np.array([3.0, 4.0]), max_norm=2.0)

    np.testing.assert_allclose(clipped, np.array([1.2, 1.6]))
    assert before == pytest.approx(5.0)
    assert after == pytest.approx(2.0)


def test_sector_estimators_memoize_logpsi_only_within_one_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _tiny_model(width=3)
    state = (1 << 0) | (1 << 5)
    calls: Counter[int] = Counter()
    original_logpsi = model.logpsi

    def recording_logpsi(configuration: int, sector: str) -> complex:
        calls[configuration] += 1
        return original_logpsi(configuration, sector)

    monkeypatch.setattr(model, "logpsi", recording_logpsi)
    _sector_estimators(
        model,
        _zero_pair_operator(model.two_q),
        np.asarray([state, state, state], dtype=object),
        "ground",
    )

    assert calls
    assert set(calls.values()) == {1}


def test_one_adam_step_matches_hand_calculated_fixture() -> None:
    parameters = np.array([1.0, -2.0], dtype=np.float64)
    gradient = np.array([0.5, -0.25], dtype=np.float64)
    initial = AdamState.zeros(parameters.size)

    updated, state, before, after = adam_update(
        parameters,
        gradient,
        initial,
        learning_rate=1.0e-3,
        beta1=0.9,
        beta2=0.999,
        epsilon=1.0e-8,
        clip_norm=10.0,
    )

    first_moment = 0.1 * gradient
    second_moment = 0.001 * gradient**2
    first_unbiased = first_moment / (1.0 - 0.9)
    second_unbiased = second_moment / (1.0 - 0.999)
    expected = parameters - 1.0e-3 * first_unbiased / (
        np.sqrt(second_unbiased) + 1.0e-8
    )
    np.testing.assert_allclose(updated, expected, rtol=0.0, atol=1.0e-15)
    np.testing.assert_allclose(state.first_moment, first_moment)
    np.testing.assert_allclose(state.second_moment, second_moment)
    assert state.update == 1
    assert before == pytest.approx(np.linalg.norm(gradient))
    assert after == pytest.approx(np.linalg.norm(gradient))


def test_each_update_draws_the_exact_ground_and_excited_m0_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _tiny_model(width=3)
    calls: list[tuple[int, str, int]] = []
    original_sample = model.sample

    def recording_sample(size: int, sector: str, *, seed: int) -> np.ndarray:
        calls.append((size, sector, seed))
        return original_sample(size, sector, seed=seed)

    monkeypatch.setattr(model, "sample", recording_sample)
    run_reduced_training(
        model=model,
        operator=_zero_pair_operator(model.two_q),
        config=_tiny_training_config(updates=3, batch_size=5),
        run_dir=tmp_path / "budget",
    )

    assert [(size, sector) for size, sector, _seed in calls] == [
        (5, sector)
        for _update in range(3)
        for sector in ("ground", "excited")
    ]
    records = _jsonl_records(tmp_path / "budget" / "training.jsonl")
    assert [record["ground_m0_samples"] for record in records] == [5, 5, 5]
    assert [record["excited_m0_samples"] for record in records] == [5, 5, 5]
    assert [record["total_samples"] for record in records] == [10, 10, 10]


def test_seed_848_smoke_writes_updates_1_through_16_and_selects_only_final(
    tmp_path: Path,
) -> None:
    model = _tiny_model(width=3)
    run_dir = tmp_path / "smoke"

    run_reduced_training(
        model=model,
        operator=_zero_pair_operator(model.two_q),
        config=_tiny_training_config(),
        run_dir=run_dir,
    )

    records = _jsonl_records(run_dir / "training.jsonl")
    assert [record["update"] for record in records] == list(range(1, 17))
    assert all(record["selection_rule"] == "final_update" for record in records)
    assert [record["selected"] for record in records] == [False] * 15 + [True]
    with np.load(run_dir / "checkpoint.npz", allow_pickle=False) as checkpoint:
        assert checkpoint["selected_update"].item() == 16
        assert checkpoint["training_seed"].item() == 848
        assert checkpoint["selection_rule"].item() == "final_update"


def test_atomic_checkpoint_preserves_old_target_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpoint = tmp_path / "checkpoint.npz"
    checkpoint.write_bytes(b"old-checkpoint")
    original_entries = {path.name for path in tmp_path.iterdir()}

    def fail_replace(source: object, target: object) -> None:
        raise OSError("simulated checkpoint replace failure")

    monkeypatch.setattr(train.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated checkpoint replace failure"):
        atomic_save_npz(checkpoint, parameters=np.array([1.0, 2.0]))

    assert checkpoint.read_bytes() == b"old-checkpoint"
    assert {path.name for path in tmp_path.iterdir()} == original_entries


def test_two_seed_848_smokes_are_byte_identical_and_finite(tmp_path: Path) -> None:
    run_directories = [tmp_path / "first", tmp_path / "second"]
    for run_dir in run_directories:
        model = _tiny_model(seed=848, width=3)
        run_reduced_training(
            model=model,
            operator=_zero_pair_operator(model.two_q),
            config=_tiny_training_config(),
            run_dir=run_dir,
        )

    for artifact in ("checkpoint.npz", "optimizer-state.npz", "training.jsonl"):
        first = (run_directories[0] / artifact).read_bytes()
        second = (run_directories[1] / artifact).read_bytes()
        assert hashlib.sha256(first).digest() == hashlib.sha256(second).digest()
        assert first == second

    records = _jsonl_records(run_directories[0] / "training.jsonl")
    finite_fields = (
        "objective",
        "energy_ground",
        "energy_excited_m0",
        "mean_l2_ground",
        "mean_l2_excited_m0",
        "variance_l2_excited_m0",
        "gradient_norm_before_clip",
        "gradient_norm_after_clip",
    )
    assert all(
        np.isfinite(float(record[field]))
        for record in records
        for field in finite_fields
    )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            ["--n8-smoke", "--training-seed", "848", "--run-dir", "unused"],
            "N=8 smoke.*A05",
        ),
        (
            ["--training-seed", "848", "--run-dir", "unused"],
            "full tower-aware training.*A05",
        ),
    ],
)
def test_cli_modes_fail_closed_until_later_capabilities_are_installed(
    arguments: list[str],
    message: str,
) -> None:
    with pytest.raises(FeatureStateError, match=message):
        training_main(arguments)
