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
    compose_ladders,
)
from scalable_v1.routes.occupation_autoregressive import factory, train
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
from scalable_v1.routes.occupation_autoregressive.tower import (
    LadderComponent,
    LadderTower,
    MetropolisSampleBatch,
)
import train_occupation_autoregressive as training_cli
from train_occupation_autoregressive import main as training_main


N8_SMOKE_ARTIFACT_ENV = "BOTS848_N8_SMOKE_ARTIFACT"
PROTOCOL_SHA256 = (
    "2435cd2e72ffae88117ee194f45b15451c8653dafa755b732005b6a199251d38"
)


def _write_synthetic_reviewed_n8_smoke(path: Path) -> Path:
    """Write only the reviewed A05.1 fields consumed at the production boundary."""

    path.write_text(
        json.dumps(
            {
                "schema": "bots848-occupation-n8-smoke-v1",
                "status": "ok",
                "optimizer_updates": 0,
                "seed": 4848,
                "protocol_sha256": PROTOCOL_SHA256,
                "device_environment_fingerprint": {
                    "hostname": "synthetic-test-n8",
                    "slurm_job_id": "reviewed-fixture",
                },
                "n8_to_n6_time_ratio": 4.229112834613484,
                "n8_to_n6_memory_ratio": 2.3707141015725703,
                "finite_counters": {"finite": 20_800, "nan": 0, "inf": 0},
            },
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def _bind_synthetic_reviewed_n8_smoke(
    monkeypatch: pytest.MonkeyPatch,
    path: Path,
) -> Path:
    reviewed = _write_synthetic_reviewed_n8_smoke(path)
    monkeypatch.setattr(
        training_cli,
        "REVIEWED_N8_SMOKE_SHA256",
        hashlib.sha256(reviewed.read_bytes()).hexdigest(),
        raising=False,
    )
    return reviewed


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


def _install_fast_full_training_compute(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the production artifact path real while replacing expensive estimators."""

    def fake_ground_sample(
        self: AutoregressiveNQS,
        size: int,
        sector: str,
        *,
        seed: int,
    ) -> np.ndarray:
        assert sector == "ground"
        assert seed >= 0
        return np.zeros(size, dtype=object)

    monkeypatch.setattr(AutoregressiveNQS, "sample", fake_ground_sample)

    class FakeComponent:
        def __init__(self, m: int) -> None:
            self.m = m

    class FakeTower:
        def __init__(self) -> None:
            self.components = {
                m: FakeComponent(m) for m in (-2, -1, 0, 1, 2)
            }

        def __getitem__(self, m: int) -> FakeComponent:
            return self.components[m]

        def __iter__(self):
            return iter((-2, -1, 0, 1, 2))

    fake_tower = FakeTower()
    monkeypatch.setattr(
        train.LadderTower,
        "from_m0",
        lambda **_kwargs: fake_tower,
    )

    class FakeSampler:
        def __init__(self, tower: object, *, target_m: int) -> None:
            assert tower is fake_tower
            self.target_m = target_m

        def sample(
            self,
            *,
            n_samples: int,
            burn_in_steps: int,
            seed: int,
        ) -> MetropolisSampleBatch:
            return MetropolisSampleBatch(
                configs=np.zeros(n_samples, dtype=object),
                n_samples=n_samples,
                burn_in_steps=burn_in_steps,
                seed=seed,
                burn_in_proposals=burn_in_steps,
                burn_in_accepted_moves=0,
                sampling_proposals=n_samples,
                sampling_accepted_moves=0,
            )

    monkeypatch.setattr(train, "FixedMMetropolisSampler", FakeSampler)

    def zero_sector_estimators(
        model: AutoregressiveNQS,
        _operator: object,
        _states: np.ndarray,
        _sector: str,
        *,
        include_l4: bool = True,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, np.ndarray]:
        train_model_parameter_count[0] = model.parameter_count
        return (
            np.zeros(1, dtype=np.complex128),
            np.zeros(1, dtype=np.complex128),
            np.zeros(1, dtype=np.complex128) if include_l4 else None,
            np.zeros((1, model.parameter_count), dtype=np.complex128),
        )

    def zero_tower_estimators(
        _component: object,
        _operator: object,
        _states: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        parameter_count = train_model_parameter_count[0]
        return (
            np.zeros(1, dtype=np.complex128),
            np.zeros(1, dtype=np.complex128),
            np.zeros(1, dtype=np.complex128),
            np.zeros((1, parameter_count), dtype=np.complex128),
        )

    train_model_parameter_count = [0]
    monkeypatch.setattr(train, "_sector_estimators", zero_sector_estimators)
    monkeypatch.setattr(
        train,
        "_tower_component_estimators",
        zero_tower_estimators,
    )

    def zero_objective(
        **_kwargs: object,
    ) -> tuple[float, np.ndarray, dict[str, float]]:
        metrics = {
            "energy_ground": 0.0,
            "energy_excited": 0.0,
            "mean_l2_ground": 0.0,
            "mean_l2_excited": 6.0,
            "mean_l4_excited": 36.0,
            "variance_l2_excited": 0.0,
            **{f"energy_excited_m{m:+d}": 0.0 for m in (-2, -1, 0, 1, 2)},
        }
        return (
            0.0,
            np.zeros(train_model_parameter_count[0], dtype=np.float64),
            metrics,
        )

    def zero_adam_update(
        parameters: object,
        _gradient: object,
        state: AdamState,
        **_kwargs: object,
    ) -> tuple[np.ndarray, AdamState, float, float]:
        return (
            np.asarray(parameters, dtype=np.float64),
            AdamState(
                update=state.update + 1,
                first_moment=state.first_moment,
                second_moment=state.second_moment,
            ),
            0.0,
            0.0,
        )

    monkeypatch.setattr(train, "full_objective_and_gradient", zero_objective)
    monkeypatch.setattr(train, "adam_update", zero_adam_update)


def _tiny_l2_matrix(
    support: tuple[int, ...],
    two_q: int,
    target_m: float = 0.0,
) -> np.ndarray:
    """Build a dense tiny-support reference in test code only."""

    index = {state: position for position, state in enumerate(support)}
    matrix = np.zeros((len(support), len(support)), dtype=np.complex128)
    for column, state in enumerate(support):
        for target, coefficient in compose_ladders(state, two_q).items():
            matrix[index[target], column] += coefficient
        matrix[column, column] += target_m * (target_m + 1.0)
    return matrix


def _exact_logpsi(
    support: tuple[int, ...],
    amplitudes: np.ndarray,
):
    table = dict(zip(support, amplitudes, strict=True))

    def logpsi(state: int) -> complex:
        value = complex(table[state])
        if value == 0.0:
            return complex(-np.inf, 0.0)
        return complex(np.log(abs(value)), np.angle(value))

    return logpsi


def _exact_sector_arrays(
    model: AutoregressiveNQS,
    sector: str,
    support: tuple[int, ...],
    hamiltonian: np.ndarray,
    l2_matrix: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    log_values = np.asarray(
        [model.logpsi(state, sector) for state in support],
        dtype=np.complex128,
    )
    wavefunction = np.exp(log_values)
    probabilities = np.abs(wavefunction) ** 2
    probabilities /= np.sum(probabilities)
    scores = np.asarray(
        [model.log_derivative(state, sector) for state in support],
        dtype=np.complex128,
    )
    energy_local = hamiltonian @ wavefunction / wavefunction
    l2_local = l2_matrix @ wavefunction / wavefunction
    l4_local = l2_matrix @ (l2_matrix @ wavefunction) / wavefunction
    return energy_local, l2_local, l4_local, scores, probabilities


def _exact_reduced_objective(
    model: AutoregressiveNQS,
    support: tuple[int, ...],
    hamiltonian: np.ndarray,
    l2_matrix: np.ndarray,
) -> float:
    moments: dict[str, tuple[float, float, float]] = {}
    l4_matrix = l2_matrix @ l2_matrix
    for sector in ("ground", "excited"):
        wavefunction = np.asarray(
            [np.exp(model.logpsi(state, sector)) for state in support],
            dtype=np.complex128,
        )
        norm = float(np.vdot(wavefunction, wavefunction).real)
        moments[sector] = (
            float(np.vdot(wavefunction, hamiltonian @ wavefunction).real / norm),
            float(np.vdot(wavefunction, l2_matrix @ wavefunction).real / norm),
            float(np.vdot(wavefunction, l4_matrix @ wavefunction).real / norm),
        )
    energy_ground, l2_ground, _l4_ground = moments["ground"]
    energy_excited, l2_excited, l4_excited = moments["excited"]
    return (
        energy_ground
        + energy_excited
        + 0.25 * l2_ground**2
        + 0.25 * (l2_excited - 6.0) ** 2
        + 0.05 * (l4_excited - l2_excited**2)
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


@pytest.mark.parametrize(
    "weights",
    [
        np.asarray([0.5, -0.25, 0.75]),
        np.zeros(3),
        np.asarray([0.2 + 0.0j, 0.3 + 0.0j, 0.5 + 0.0j]),
        np.asarray([0.4, 0.6]),
        np.asarray([0.5, np.inf, 0.5]),
    ],
    ids=("negative", "zero-sum", "complex", "wrong-length", "nonfinite"),
)
def test_score_covariance_rejects_invalid_weights(weights: np.ndarray) -> None:
    scores = np.ones((3, 2), dtype=np.complex128)
    local_values = np.ones(3, dtype=np.complex128)

    with pytest.raises(ValueError, match="weights"):
        score_covariance(scores, local_values, weights=weights)


def test_weighted_score_covariance_is_stable_for_large_common_offsets() -> None:
    offset = float(2**40)
    scores = np.asarray(
        [
            [offset + 1.0 + 1.0j, -offset + 2.0 - 3.0j],
            [offset - 2.0 + 4.0j, -offset - 1.0 + 2.0j],
            [offset + 3.0 - 2.0j, -offset + 4.0 + 1.0j],
            [offset - 4.0 + 3.0j, -offset - 3.0 - 4.0j],
        ],
        dtype=np.complex128,
    )
    local_values = np.asarray(
        [
            offset + 2.0 - 1.0j,
            offset - 3.0 + 2.0j,
            offset + 5.0,
            offset - 1.0 - 3.0j,
        ],
        dtype=np.complex128,
    )
    weights = np.asarray([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
    normalized = weights / np.sum(weights)
    conjugate_scores = scores.conj()
    centered_scores = conjugate_scores - np.sum(
        normalized[:, None] * conjugate_scores,
        axis=0,
    )
    centered_values = local_values - np.sum(normalized * local_values)
    expected = 2.0 * np.real(
        np.sum(
            normalized[:, None] * centered_scores * centered_values[:, None],
            axis=0,
        )
    )

    observed = score_covariance(scores, local_values, weights=weights)

    np.testing.assert_allclose(observed, expected, rtol=0.0, atol=1.0e-12)


def test_physical_l2_variance_differs_from_real_local_value_variance() -> None:
    model = _tiny_model(width=2)
    support = tuple(model.feasibility.enumerate_support())
    l2_matrix = _tiny_l2_matrix(support, model.two_q)
    amplitudes = np.asarray(
        [1.0 + 0.2j, -0.7 + 0.9j, 0.4 - 0.3j],
        dtype=np.complex128,
    )
    probabilities = np.abs(amplitudes) ** 2
    probabilities /= np.sum(probabilities)
    l2_local = l2_matrix @ amplitudes / amplitudes
    l4_local = l2_matrix @ (l2_matrix @ amplitudes) / amplitudes
    mean_l2 = float(np.sum(probabilities * l2_local).real)
    physical_variance = float(np.sum(probabilities * l4_local).real - mean_l2**2)
    rejected_surrogate = float(
        np.sum(probabilities * (l2_local.real - mean_l2) ** 2)
    )

    assert physical_variance >= -1.0e-12
    assert physical_variance != pytest.approx(rejected_surrogate, abs=1.0e-8)
    assert train.physical_l2_variance(
        l2_local,
        l4_local,
        weights=probabilities,
    ) == pytest.approx(physical_variance, abs=1.0e-12)


def test_sparse_local_l4_matches_exact_two_hop_row_with_zero_intermediate() -> None:
    model = _tiny_model(width=2)
    support = tuple(model.feasibility.enumerate_support())
    l2_matrix = _tiny_l2_matrix(support, model.two_q)
    source_index = next(
        column
        for column in range(len(support))
        if np.any(
            (l2_matrix[:, column] != 0.0)
            & (np.arange(len(support)) != column)
        )
    )
    intermediate_index = next(
        row
        for row in range(len(support))
        if row != source_index and l2_matrix[row, source_index] != 0.0
    )
    amplitudes = np.asarray(
        [1.0 + 0.25j, -0.6 + 0.8j, 0.35 - 0.4j],
        dtype=np.complex128,
    )
    amplitudes[intermediate_index] = 0.0
    assert amplitudes[source_index] != 0.0
    expected = (l2_matrix @ (l2_matrix @ amplitudes))[source_index] / amplitudes[
        source_index
    ]

    observed = train.local_l4(
        support[source_index],
        two_q=model.two_q,
        target_m=0.0,
        logpsi=_exact_logpsi(support, amplitudes),
    )

    assert observed == pytest.approx(expected, abs=1.0e-12)


def test_sparse_local_l4_matches_exact_nonzero_m_two_hop_row() -> None:
    two_q = 6
    target_m = 1.0
    support = FeasibilityTable.build(
        n_electrons=3,
        two_q=two_q,
        target_m2=2,
    ).enumerate_support()
    l2_matrix = _tiny_l2_matrix(support, two_q, target_m)
    amplitudes = np.asarray(
        [
            complex(1.0 + 0.15 * index, (-1) ** index * (0.2 + 0.05 * index))
            for index in range(len(support))
        ],
        dtype=np.complex128,
    )
    source_index = next(
        column
        for column in range(len(support))
        if np.count_nonzero(l2_matrix[:, column]) > 1
    )
    expected = (l2_matrix @ (l2_matrix @ amplitudes))[source_index] / amplitudes[
        source_index
    ]

    observed = train.local_l4(
        support[source_index],
        two_q=two_q,
        target_m=target_m,
        logpsi=_exact_logpsi(support, amplitudes),
    )

    assert observed == pytest.approx(expected, abs=1.0e-12)


def test_local_l4_rejects_coercible_states_before_canonical_int() -> None:
    source = (1 << 0) | (1 << 5)

    for state in (True, source + 0.75, str(source)):
        with pytest.raises(TypeError, match="state must be an integer"):
            train.local_l4(
                state,
                two_q=5,
                target_m=0.0,
                logpsi=lambda _state: 0.0j,
            )


def test_local_l4_rejects_invalid_determinants_consistently() -> None:
    cases = (
        (-1, "non-negative"),
        (1 << 6, "outside the orbital range"),
        ((1 << 0) | (1 << 4), "requested target_m sector"),
    )

    for state, message in cases:
        with pytest.raises(ValueError, match=message):
            train.local_l4(
                state,
                two_q=5,
                target_m=0.0,
                logpsi=lambda _state: 0.0j,
            )


def test_exact_reduced_objective_gradient_matches_central_difference() -> None:
    model = _tiny_model(seed=848, width=2)
    support = tuple(model.feasibility.enumerate_support())
    l2_matrix = _tiny_l2_matrix(support, model.two_q)
    hamiltonian = np.diag(np.linspace(-0.4, 0.7, len(support))).astype(
        np.complex128
    )
    ground = _exact_sector_arrays(
        model,
        "ground",
        support,
        hamiltonian,
        l2_matrix,
    )
    excited = _exact_sector_arrays(
        model,
        "excited",
        support,
        hamiltonian,
        l2_matrix,
    )

    objective, analytic_gradient, metrics = train.reduced_objective_and_gradient(
        ground_energy=ground[0],
        ground_l2=ground[1],
        ground_l4=None,
        ground_scores=ground[3],
        excited_energy=excited[0],
        excited_l2=excited[1],
        excited_l4=excited[2],
        excited_scores=excited[3],
        ground_weights=ground[4],
        excited_weights=excited[4],
    )
    baseline = model.flat_parameters()
    step = 2.0e-6
    central = np.empty_like(baseline)
    try:
        for index in range(baseline.size):
            plus = baseline.copy()
            minus = baseline.copy()
            plus[index] += step
            minus[index] -= step
            model.set_flat_parameters(plus)
            upper = _exact_reduced_objective(
                model,
                support,
                hamiltonian,
                l2_matrix,
            )
            model.set_flat_parameters(minus)
            lower = _exact_reduced_objective(
                model,
                support,
                hamiltonian,
                l2_matrix,
            )
            central[index] = (upper - lower) / (2.0 * step)
    finally:
        model.set_flat_parameters(baseline)

    assert objective == pytest.approx(
        _exact_reduced_objective(model, support, hamiltonian, l2_matrix),
        abs=1.0e-12,
    )
    assert metrics["variance_l2_excited_m0"] == pytest.approx(
        metrics["mean_l4_excited_m0"] - metrics["mean_l2_excited_m0"] ** 2,
        abs=1.0e-12,
    )
    np.testing.assert_allclose(
        analytic_gradient,
        central,
        rtol=2.0e-5,
        atol=2.0e-6,
    )


def test_reduced_objective_rejects_score_parameter_width_mismatch() -> None:
    ground_values = np.asarray([0.25, -0.5], dtype=np.complex128)
    excited_values = np.asarray([0.75, 0.5], dtype=np.complex128)

    with pytest.raises(ValueError, match="same parameter count"):
        train.reduced_objective_and_gradient(
            ground_energy=ground_values,
            ground_l2=ground_values,
            ground_l4=ground_values,
            ground_scores=np.ones((2, 1), dtype=np.complex128),
            excited_energy=excited_values,
            excited_l2=excited_values,
            excited_l4=excited_values,
            excited_scores=np.ones((2, 2), dtype=np.complex128),
        )


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


@pytest.mark.parametrize("state", [True, 33.75, "33"])
def test_sector_estimators_reject_coercible_states_before_canonical_int(
    state: object,
) -> None:
    model = _tiny_model(width=3)

    with pytest.raises(TypeError, match="state must be an integer"):
        _sector_estimators(
            model,
            _zero_pair_operator(model.two_q),
            np.asarray([state], dtype=object),
            "ground",
        )


def test_sector_estimators_reuse_real_l2_rows_and_omit_ground_l4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _tiny_model(width=3)
    source = (1 << 0) | (1 << 5)
    states = np.asarray([source, source, source], dtype=object)
    original_l2_neighbors = train.l2_neighbors
    calls: Counter[int] = Counter()

    def recording_l2_neighbors(
        state: int,
        two_q: int,
        target_m: float,
    ) -> dict[int, complex]:
        calls[state] += 1
        return original_l2_neighbors(state, two_q, target_m)

    monkeypatch.setattr(train, "l2_neighbors", recording_l2_neighbors)

    _energy, _l2, ground_l4, _scores = _sector_estimators(
        model,
        _zero_pair_operator(model.two_q),
        states,
        "ground",
        include_l4=False,
    )

    assert ground_l4 is None
    assert calls == Counter({source: 1})

    calls.clear()
    source_row = original_l2_neighbors(source, model.two_q, 0.0)
    _sector_estimators(
        model,
        _zero_pair_operator(model.two_q),
        states,
        "excited",
        include_l4=True,
    )

    assert calls == Counter({state: 1 for state in {source, *source_row}})


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


def test_reduced_training_rejects_nonzero_model_target_m2_before_writing(
    tmp_path: Path,
) -> None:
    model = AutoregressiveNQS.initialize(
        n_electrons=2,
        two_q=5,
        target_m2=2,
        width=2,
        layers=2,
        seed=848,
        max_trainable_parameters=262_144,
    )
    run_dir = tmp_path / "wrong-sector"

    with pytest.raises(ValueError, match="target_m2 must be 0"):
        run_reduced_training(
            model=model,
            operator=_zero_pair_operator(model.two_q),
            config=_tiny_training_config(updates=1),
            run_dir=run_dir,
        )

    assert not run_dir.exists()


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


def test_full_objective_uses_arithmetic_tower_means_and_component_scores() -> None:
    ground_energy = np.asarray([1.0 + 0.5j, 3.0 - 0.5j])
    ground_l2 = np.asarray([0.5 + 0.25j, 1.5 - 0.25j])
    ground_scores = np.asarray(
        [[1.0 + 2.0j, -0.5j], [3.0 - 1.0j, 2.0 + 0.25j]]
    )
    energy_by_m: dict[int, np.ndarray] = {}
    l2_by_m: dict[int, np.ndarray] = {}
    l4_by_m: dict[int, np.ndarray] = {}
    scores_by_m: dict[int, np.ndarray] = {}
    for index, m in enumerate((-2, -1, 0, 1, 2), start=1):
        energy_by_m[m] = np.asarray(
            [index + 0.2j * m, index + 2.0 - 0.2j * m]
        )
        l2_by_m[m] = np.asarray(
            [4.0 + 0.1j * index, 6.0 - 0.1j * index]
        )
        l4_by_m[m] = np.asarray(
            [26.0 + 0.3j * m, 30.0 - 0.3j * m]
        )
        scores_by_m[m] = np.asarray(
            [
                [index + 1.0j * m, 0.25 * index - 0.5j],
                [-0.5 * index + 0.2j, index + 0.75j * m],
            ]
        )

    objective, gradient, metrics = train.full_objective_and_gradient(
        ground_energy=ground_energy,
        ground_l2=ground_l2,
        ground_scores=ground_scores,
        excited_energy_by_m=energy_by_m,
        excited_l2_by_m=l2_by_m,
        excited_l4_by_m=l4_by_m,
        excited_scores_by_m=scores_by_m,
    )

    energy_ground = float(np.mean(ground_energy).real)
    mean_l2_ground = float(np.mean(ground_l2).real)
    energy_means = {
        m: float(np.mean(values).real) for m, values in energy_by_m.items()
    }
    mean_l2_excited = float(
        np.mean([np.mean(values).real for values in l2_by_m.values()])
    )
    mean_l4_excited = float(
        np.mean([np.mean(values).real for values in l4_by_m.values()])
    )
    variance_l2_excited = mean_l4_excited - mean_l2_excited**2
    expected_objective = (
        energy_ground
        + float(np.mean(list(energy_means.values())))
        + 0.25 * mean_l2_ground**2
        + 0.25 * (mean_l2_excited - 6.0) ** 2
        + 0.05 * variance_l2_excited
    )
    mean_component_covariance = lambda values_by_m: np.mean(
        [
            score_covariance(scores_by_m[m], values_by_m[m])
            for m in (-2, -1, 0, 1, 2)
        ],
        axis=0,
    )
    ground_l2_gradient = score_covariance(ground_scores, ground_l2)
    excited_l2_gradient = mean_component_covariance(l2_by_m)
    expected_gradient = (
        score_covariance(ground_scores, ground_energy)
        + mean_component_covariance(energy_by_m)
        + 0.5 * mean_l2_ground * ground_l2_gradient
        + 0.5 * (mean_l2_excited - 6.0) * excited_l2_gradient
        + 0.05
        * (
            mean_component_covariance(l4_by_m)
            - 2.0 * mean_l2_excited * excited_l2_gradient
        )
    )

    assert objective == pytest.approx(expected_objective)
    np.testing.assert_allclose(gradient, expected_gradient)
    assert metrics["energy_excited"] == pytest.approx(
        np.mean(list(energy_means.values()))
    )
    assert metrics["variance_l2_excited"] == pytest.approx(
        variance_l2_excited
    )
    for m in (-2, -1, 0, 1, 2):
        assert metrics[f"energy_excited_m{m:+d}"] == pytest.approx(
            energy_means[m]
        )


def test_tower_estimators_pair_each_component_with_its_analytic_log_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _tiny_model(width=3)
    tower = LadderTower.from_m0(
        logpsi=lambda state: model.logpsi(state, "excited"),
        log_score=lambda state: model.log_derivative(state, "excited"),
        n_electrons=model.n_electrons,
        two_q=model.two_q,
        l=2,
    )
    selected: dict[int, int] = {}
    for m in (-2, -1, 0, 1, 2):
        support = FeasibilityTable.build(
            n_electrons=model.n_electrons,
            two_q=model.two_q,
            target_m2=2 * m,
        ).enumerate_support()
        selected[m] = next(
            state for state in support if tower[m].logpsi(state).real != -np.inf
        )
    original_log_score = LadderComponent.log_score
    calls: list[tuple[int, int]] = []

    def recording_log_score(self: LadderComponent, state: int) -> np.ndarray:
        calls.append((self.m, state))
        return original_log_score(self, state)

    monkeypatch.setattr(LadderComponent, "log_score", recording_log_score)
    observed: dict[int, np.ndarray] = {}
    for m in (-2, -1, 0, 1, 2):
        _energy, _l2, _l4, scores = train._tower_component_estimators(
            tower[m],
            _zero_pair_operator(model.two_q),
            np.asarray([selected[m]], dtype=object),
        )
        observed[m] = scores[0]

    assert calls == [(m, selected[m]) for m in (-2, -1, 0, 1, 2)]
    for m in (-2, -1, 0, 1, 2):
        np.testing.assert_allclose(
            observed[m],
            original_log_score(tower[m], selected[m]),
        )


def test_full_training_runs_frozen_2048_update_six_batch_tower_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _tiny_model(width=3)
    valid_state = model.feasibility.enumerate_support()[0]
    ground_calls: list[tuple[int, str, int]] = []
    tower_calls: list[tuple[int, int, int, int]] = []

    def fake_ground_sample(size: int, sector: str, *, seed: int) -> np.ndarray:
        ground_calls.append((size, sector, seed))
        return np.full(size, valid_state, dtype=object)

    monkeypatch.setattr(model, "sample", fake_ground_sample)

    class FakeComponent:
        def __init__(self, m: int) -> None:
            self.m = m

    class FakeTower:
        def __init__(self) -> None:
            self.components = {m: FakeComponent(m) for m in (-2, -1, 0, 1, 2)}

        def __getitem__(self, m: int) -> FakeComponent:
            return self.components[m]

        def __iter__(self):
            return iter((-2, -1, 0, 1, 2))

    fake_tower = FakeTower()
    monkeypatch.setattr(
        train.LadderTower,
        "from_m0",
        lambda **_kwargs: fake_tower,
    )

    class FakeSampler:
        def __init__(self, tower: object, *, target_m: int) -> None:
            assert tower is fake_tower
            self.target_m = target_m

        def sample(
            self,
            *,
            n_samples: int,
            burn_in_steps: int,
            seed: int,
        ) -> MetropolisSampleBatch:
            tower_calls.append(
                (self.target_m, n_samples, burn_in_steps, seed)
            )
            return MetropolisSampleBatch(
                configs=np.full(n_samples, valid_state, dtype=object),
                n_samples=n_samples,
                burn_in_steps=burn_in_steps,
                seed=seed,
                burn_in_proposals=burn_in_steps,
                burn_in_accepted_moves=0,
                sampling_proposals=n_samples,
                sampling_accepted_moves=0,
            )

    monkeypatch.setattr(train, "FixedMMetropolisSampler", FakeSampler)

    def zero_estimators(
        _model: object,
        _operator: object,
        states: np.ndarray,
        _sector: str,
        *,
        include_l4: bool = True,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, np.ndarray]:
        count = states.size
        return (
            np.zeros(count, dtype=np.complex128),
            np.zeros(count, dtype=np.complex128),
            np.zeros(count, dtype=np.complex128) if include_l4 else None,
            np.zeros((count, model.parameter_count), dtype=np.complex128),
        )

    def zero_tower_estimators(
        _component: object,
        _operator: object,
        states: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        count = states.size
        return (
            np.zeros(count, dtype=np.complex128),
            np.zeros(count, dtype=np.complex128),
            np.zeros(count, dtype=np.complex128),
            np.zeros((count, model.parameter_count), dtype=np.complex128),
        )

    monkeypatch.setattr(train, "_sector_estimators", zero_estimators)
    monkeypatch.setattr(
        train,
        "_tower_component_estimators",
        zero_tower_estimators,
    )
    config = train.FullTrainingConfig(
        training_seed=848,
        protocol_sha256="a" * 64,
        comparison_sha="b" * 40,
    )
    run_dir = tmp_path / "full"
    progress_pulses: list[dict[str, object]] = []

    artifacts = train.run_full_training(
        model=model,
        operator=_zero_pair_operator(model.two_q),
        config=config,
        run_dir=run_dir,
        progress_callback=progress_pulses.append,
    )

    assert config.updates == 2048
    assert config.batch_size_per_sector == 512
    assert config.checkpoint_interval == 128
    assert artifacts.selected_update == 2048
    assert len(ground_calls) == 2048
    assert {(size, sector) for size, sector, _seed in ground_calls} == {
        (512, "ground")
    }
    assert len(tower_calls) == 2048 * 5
    assert {
        (m, count, burn_in) for m, count, burn_in, _seed in tower_calls
    } == {(m, 512, 1024) for m in (-2, -1, 0, 1, 2)}
    seed_tuples = [
        (
            ground_calls[index][2],
            *(call[3] for call in tower_calls[5 * index : 5 * index + 5]),
        )
        for index in range(2048)
    ]
    assert seed_tuples[0] == (
        848_002_544,
        848_002_545,
        848_002_546,
        848_002_547,
        848_002_548,
        848_002_549,
    )
    assert seed_tuples[1] == (
        848_002_550,
        848_002_551,
        848_002_552,
        848_002_553,
        848_002_554,
        848_002_555,
    )
    assert seed_tuples[2047] == (
        848_014_826,
        848_014_827,
        848_014_828,
        848_014_829,
        848_014_830,
        848_014_831,
    )
    all_seeds = [seed for seeds in seed_tuples for seed in seeds]
    assert len(all_seeds) == len(set(all_seeds)) == 12_288
    records = _jsonl_records(run_dir / "training.jsonl")
    assert [record["update"] for record in records] == list(range(1, 2049))
    assert [record["selected"] for record in records] == [False] * 2047 + [True]
    assert all(record["ground_samples"] == 512 for record in records)
    assert all(record["total_samples"] == 3072 for record in records)
    assert all(
        record["excited_samples_by_m"]
        == {str(m): 512 for m in (-2, -1, 0, 1, 2)}
        for record in records
    )
    assert [pulse["update"] for pulse in progress_pulses] == list(
        range(128, 2049, 128)
    )
    assert [pulse["selected"] for pulse in progress_pulses] == [False] * 15 + [
        True
    ]
    assert all(pulse["total_samples"] == 3072 for pulse in progress_pulses)
    with np.load(run_dir / "checkpoint.npz", allow_pickle=False) as checkpoint:
        assert checkpoint["selected_update"].item() == 2048
        assert checkpoint["completed_update"].item() == 2048
        assert checkpoint["batch_size_per_sector"].item() == 512


def test_full_cli_has_only_frozen_seed_schedule_and_freezes_terminal_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}
    model = _tiny_model(width=3)
    operator = _zero_pair_operator(model.two_q)
    run_dir = tmp_path / "production"
    reviewed_n8 = _bind_synthetic_reviewed_n8_smoke(
        monkeypatch,
        tmp_path / "n8-smoke.json",
    )
    monkeypatch.setenv(N8_SMOKE_ARTIFACT_ENV, str(reviewed_n8))
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    clock = iter((10.0, 12.5))
    monkeypatch.setattr(training_cli.time, "perf_counter", lambda: next(clock))
    monkeypatch.setattr(training_cli, "peak_rss_bytes", lambda: 123_456)
    monkeypatch.setattr(
        training_cli,
        "_full_run_device_fingerprint",
        lambda: "pytest-full-runtime",
        raising=False,
    )

    monkeypatch.setattr(
        training_cli.AutoregressiveNQS,
        "initialize",
        lambda **kwargs: captured.setdefault("initialize", kwargs) and model,
    )
    monkeypatch.setattr(training_cli, "_prepared_operator", lambda _two_q: operator)

    def fake_run_full_training(**kwargs: object) -> object:
        captured["config"] = kwargs["config"]
        captured["progress_callback"] = kwargs["progress_callback"]
        output = Path(kwargs["run_dir"])
        output.mkdir(parents=True)
        paths = [
            output / "checkpoint.npz",
            output / "optimizer-state.npz",
            output / "training.jsonl",
        ]
        paths[0].write_bytes(b"checkpoint-fixture")
        paths[1].write_bytes(b"optimizer-fixture")
        paths[2].write_text(
            json.dumps(
                {
                    "update": 2048,
                    "selected": True,
                    "selection_rule": "final_update",
                    "training_seed": 1848,
                },
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return train.TrainingArtifacts(
            checkpoint=paths[0],
            optimizer_state=paths[1],
            training_log=paths[2],
            checkpoint_sha256="1" * 64,
            optimizer_state_sha256="2" * 64,
            training_log_sha256=hashlib.sha256(paths[2].read_bytes()).hexdigest(),
            selected_update=2048,
        )

    monkeypatch.setattr(
        training_cli,
        "run_full_training",
        fake_run_full_training,
        raising=False,
    )
    def fake_freeze(**kwargs: object) -> Path:
        captured["freeze"] = kwargs
        path = Path(kwargs["run_dir"]) / "training-manifest.json"
        path.write_text("{}\n", encoding="utf-8")
        return path

    monkeypatch.setattr(training_cli, "freeze_training_run", fake_freeze)

    assert training_cli.main(
        ["--training-seed", "1848", "--run-dir", str(run_dir)]
    ) == 0

    config = captured["config"]
    assert isinstance(config, train.FullTrainingConfig)
    assert config.training_seed == 1848
    assert config.updates == 2048
    assert config.batch_size_per_sector == 512
    assert config.checkpoint_interval == 128
    assert captured["freeze"]["training_seed"] == 1848
    assert callable(captured["progress_callback"])
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["mode"] == "a05.2-full-tower-training"
    assert emitted["selected_update"] == 2048
    record = json.loads((run_dir / "training.jsonl").read_text(encoding="utf-8"))
    assert record["resource_metrics"]["placement"] == "local"


def test_real_full_training_freeze_is_loadable_by_factory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reviewed_n8 = _bind_synthetic_reviewed_n8_smoke(
        monkeypatch,
        tmp_path / "n8-smoke.json",
    )
    run_dir = tmp_path / "production"
    monkeypatch.setenv(N8_SMOKE_ARTIFACT_ENV, str(reviewed_n8))
    monkeypatch.setenv("SLURM_JOB_ID", "pytest-slurm")
    _install_fast_full_training_compute(monkeypatch)
    monkeypatch.setattr(
        training_cli,
        "_prepared_operator",
        lambda two_q: _zero_pair_operator(two_q),
    )
    clock = iter((100.0, 102.5))
    monkeypatch.setattr(training_cli.time, "perf_counter", lambda: next(clock))
    monkeypatch.setattr(training_cli, "peak_rss_bytes", lambda: 123_456)
    monkeypatch.setattr(
        training_cli,
        "_full_run_device_fingerprint",
        lambda: "pytest-full-runtime",
        raising=False,
    )

    assert training_cli.main(
        ["--training-seed", "848", "--run-dir", str(run_dir)]
    ) == 0

    emitted = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(emitted) == 17
    summary = emitted[-1]
    training_log = run_dir / "training.jsonl"
    training_bytes = training_log.read_bytes()
    training_sha256 = hashlib.sha256(training_bytes).hexdigest()
    assert summary["training_log_sha256"] == training_sha256
    records = _jsonl_records(training_log)
    assert len(records) == 2048
    assert all("resource_metrics" not in record for record in records[:-1])
    assert [record["selected"] for record in records] == [False] * 2047 + [True]
    manifest = json.loads(
        (run_dir / "training-manifest.json").read_text(encoding="utf-8")
    )
    training_item = next(
        item for item in manifest["artifacts"] if item["role"] == "training_log"
    )
    assert training_item["sha256"] == training_sha256

    monkeypatch.setenv(factory.RUN_DIR_ENV, str(run_dir))
    monkeypatch.setattr(factory, "coulomb_integrals", lambda _two_q: None)
    monkeypatch.setattr(
        factory,
        "antisymmetrized_pair_matrix",
        lambda _integrals: ((), np.zeros((0, 0), dtype=np.complex128)),
    )
    candidate = factory.load_candidate()
    resources = candidate.resource_metrics()
    assert records[-1]["resource_metrics"] == {
        "placement": "remote",
        "wall_seconds": 2.5,
        "peak_rss_bytes": 123_456,
        "peak_vram_bytes": None,
        "estimator_evaluations": 6_291_456,
        "effective_sample_size": 0.0,
        "n8_smoke_complete": True,
        "n8_to_n6_time_ratio": 4.229112834613484,
        "n8_to_n6_memory_ratio": 2.3707141015725703,
        "device_fingerprint": "pytest-full-runtime",
    }
    assert resources.placement == "remote"
    assert resources.wall_seconds == 2.5
    assert resources.estimator_evaluations == 6_291_456
    assert resources.effective_sample_size == 0.0
    assert resources.n8_smoke_complete is True
    assert resources.n8_to_n6_time_ratio == 4.229112834613484
    assert resources.n8_to_n6_memory_ratio == 2.3707141015725703


def test_full_cli_parser_accepts_explicit_reviewed_n8_smoke_path(
    tmp_path: Path,
) -> None:
    reviewed_n8 = tmp_path / "n8-smoke.json"
    arguments = training_cli._parser().parse_args(
        [
            "--training-seed",
            "848",
            "--run-dir",
            str(tmp_path / "run"),
            "--n8-smoke-artifact",
            str(reviewed_n8),
        ]
    )

    assert arguments.n8_smoke_artifact == reviewed_n8


def test_full_cli_requires_reviewed_n8_smoke_before_training(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(N8_SMOKE_ARTIFACT_ENV, raising=False)
    monkeypatch.setattr(
        training_cli.AutoregressiveNQS,
        "initialize",
        lambda **_kwargs: pytest.fail("training started before N=8 input validation"),
    )

    with pytest.raises(ValueError, match="reviewed N=8 smoke artifact is required"):
        training_cli.main(
            ["--training-seed", "848", "--run-dir", str(tmp_path / "run")]
        )


def test_full_cli_rejects_wrong_reviewed_n8_smoke_sha_before_training(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewed_n8 = _write_synthetic_reviewed_n8_smoke(tmp_path / "n8-smoke.json")
    monkeypatch.setenv(N8_SMOKE_ARTIFACT_ENV, str(reviewed_n8))
    monkeypatch.setattr(
        training_cli,
        "REVIEWED_N8_SMOKE_SHA256",
        "0" * 64,
        raising=False,
    )
    monkeypatch.setattr(
        training_cli.AutoregressiveNQS,
        "initialize",
        lambda **_kwargs: pytest.fail("training started before N=8 SHA validation"),
    )

    with pytest.raises(ValueError, match="reviewed N=8 smoke SHA-256 mismatch"):
        training_cli.main(
            ["--training-seed", "848", "--run-dir", str(tmp_path / "run")]
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema", "wrong-schema", "schema"),
        ("status", "failed", "status"),
        ("optimizer_updates", 1, "optimizer_updates"),
        ("protocol_sha256", "0" * 64, "protocol"),
        ("seed", 848, "seed"),
        ("n8_to_n6_time_ratio", -1.0, "time ratio"),
        ("n8_to_n6_memory_ratio", None, "memory ratio"),
        ("finite_counters", {"finite": 20_800, "nan": 1, "inf": 0}, "finite"),
    ],
)
def test_full_cli_rejects_unreviewed_n8_smoke_before_training(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    reviewed_n8 = _write_synthetic_reviewed_n8_smoke(tmp_path / "n8-smoke.json")
    payload = json.loads(reviewed_n8.read_text(encoding="utf-8"))
    payload[field] = value
    reviewed_n8.write_text(
        json.dumps(payload, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.setattr(
        training_cli,
        "REVIEWED_N8_SMOKE_SHA256",
        hashlib.sha256(reviewed_n8.read_bytes()).hexdigest(),
        raising=False,
    )
    monkeypatch.setenv(N8_SMOKE_ARTIFACT_ENV, str(reviewed_n8))
    monkeypatch.setattr(
        training_cli.AutoregressiveNQS,
        "initialize",
        lambda **_kwargs: pytest.fail("training started before N=8 input validation"),
    )

    with pytest.raises(ValueError, match=message):
        training_cli.main(
            ["--training-seed", "848", "--run-dir", str(tmp_path / "run")]
        )


def test_full_cli_rejects_existing_manifest_before_training_starts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _tiny_model(width=3)
    run_dir = tmp_path / "protected-run"
    run_dir.mkdir()
    reviewed_n8 = _bind_synthetic_reviewed_n8_smoke(
        monkeypatch,
        tmp_path / "n8-smoke.json",
    )
    monkeypatch.setenv(N8_SMOKE_ARTIFACT_ENV, str(reviewed_n8))
    manifest = run_dir / "training-manifest.json"
    sentinel = b"preexisting-provenance\n"
    manifest.write_bytes(sentinel)

    def forbidden_sample(
        _size: int,
        _sector: str,
        *,
        seed: int,
    ) -> np.ndarray:
        raise AssertionError(f"training started with seed {seed}")

    monkeypatch.setattr(model, "sample", forbidden_sample)
    monkeypatch.setattr(
        training_cli.AutoregressiveNQS,
        "initialize",
        lambda **_kwargs: model,
    )
    monkeypatch.setattr(
        training_cli,
        "_prepared_operator",
        lambda _two_q: _zero_pair_operator(model.two_q),
    )

    with pytest.raises(FileExistsError, match="training artifacts"):
        training_cli.main(
            ["--training-seed", "848", "--run-dir", str(run_dir)]
        )

    assert manifest.read_bytes() == sentinel
    assert {path.name for path in run_dir.iterdir()} == {
        "training-manifest.json"
    }


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            ["--n8-smoke", "--training-seed", "848", "--run-dir", "unused"],
            "N=8 smoke.*A05",
        ),
    ],
)
def test_cli_modes_fail_closed_until_later_capabilities_are_installed(
    arguments: list[str],
    message: str,
) -> None:
    with pytest.raises(FeatureStateError, match=message):
        training_main(arguments)
