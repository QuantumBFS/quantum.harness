from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from spinglass3d.linear_bias import LinearFeatureBasis
from spinglass3d.model import EABonds
from spinglass3d.templates import TemplateEncoder
from spinglass3d.tensor_train import LocalTensorTrain, SymmetricLocalTT
from spinglass3d.vmcrg import (
    CheckpointContext,
    FrozenRouteBatch,
    InMemoryVMCRGBackend,
    VMCRGBatch,
    VMCRGProtocol,
    VMCRGSamplingBackend,
    VMCRGTrainer,
    classify_tt_improvement,
    compare_frozen_routes,
    estimate_gradient,
    evaluate_frozen_bias,
    evaluate_frozen_linear,
    exact_two_state_vmcrg,
    vmcrg_gradient,
)
from spinglass3d.bias import BiasRoute, OverlapBias


def test_vmcrg_batch_owns_immutable_whole_j_draws() -> None:
    target = np.array(
        [
            [[1, -1, 1], [1, 1, -1]],
            [[-1, 1, -1], [-1, -1, 1]],
        ],
        dtype=np.int8,
    )
    biased = -target
    batch = VMCRGBatch(
        target_tokens=target,
        biased_tokens=biased,
        j_ids=("J-0", "J-1"),
    )

    assert batch.target_tokens.shape == (2, 2, 3)
    assert batch.biased_tokens.shape == batch.target_tokens.shape
    assert batch.j_ids == ("J-0", "J-1")
    assert not batch.target_tokens.flags.writeable
    assert not batch.biased_tokens.flags.writeable
    target[0, 0, 0] = -1
    assert batch.target_tokens[0, 0, 0] == 1
    with pytest.raises(ValueError, match="read-only"):
        batch.target_tokens[0, 0, 0] = -1


@pytest.mark.parametrize(
    ("target", "biased", "j_ids", "message"),
    (
        (
            np.ones((2, 3), dtype=np.int8),
            np.ones((2, 3), dtype=np.int8),
            ("J-0", "J-1"),
            "shape",
        ),
        (
            np.ones((2, 0, 3), dtype=np.int8),
            np.ones((2, 0, 3), dtype=np.int8),
            ("J-0", "J-1"),
            "positive",
        ),
        (
            np.ones((2, 1, 3), dtype=np.int8),
            np.ones((2, 2, 3), dtype=np.int8),
            ("J-0", "J-1"),
            "shape",
        ),
        (
            np.zeros((2, 1, 3), dtype=np.int8),
            np.ones((2, 1, 3), dtype=np.int8),
            ("J-0", "J-1"),
            "binary",
        ),
        (
            np.ones((2, 1, 3), dtype=np.int8),
            np.ones((2, 1, 3), dtype=np.int8),
            ("J-0", "J-0"),
            "unique",
        ),
        (
            np.ones((2, 1, 3), dtype=np.int8),
            np.ones((2, 1, 3), dtype=np.int8),
            ("J-0", ""),
            "unique",
        ),
        (
            np.ones((2, 1, 3), dtype=np.int8),
            np.ones((2, 1, 3), dtype=np.int8),
            ("J-0", 1),
            "unique",
        ),
        (
            np.ones((2, 1, 3), dtype=np.int8),
            np.ones((2, 1, 3), dtype=np.int8),
            ("J-0",),
            "unique",
        ),
    ),
)
def test_vmcrg_batch_rejects_invalid_whole_j_contract(
    target: np.ndarray,
    biased: np.ndarray,
    j_ids: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        VMCRGBatch(
            target_tokens=target,
            biased_tokens=biased,
            j_ids=j_ids,
        )


@pytest.mark.parametrize("j_ids", ("AB", b"AB"))
def test_vmcrg_batch_rejects_bare_string_j_ids(j_ids: object) -> None:
    tokens = np.ones((2, 1, 3), dtype=np.int8)
    with pytest.raises(TypeError, match="str or bytes"):
        VMCRGBatch(
            target_tokens=tokens,
            biased_tokens=tokens,
            j_ids=j_ids,
        )


def test_estimate_gradient_uses_explicit_draw_then_j_axes() -> None:
    target = np.array(
        [
            [[3.0, 1.0], [3.0, 1.0], [3.0, 1.0]],
            [[-1.0, -1.0], [-1.0, -1.0], [1.0, -1.0]],
        ]
    )
    biased = np.array(
        [
            [[1.0, -1.0], [1.0, -1.0], [1.0, -1.0]],
            [[-3.0, 1.0], [-1.0, 1.0], [-1.0, 1.0]],
        ]
    )
    estimate = estimate_gradient(None, target, biased)
    target_by_j = np.array([[3.0, 1.0], [-1.0 / 3.0, -1.0]])
    biased_by_j = np.array([[1.0, -1.0], [-5.0 / 3.0, 1.0]])

    np.testing.assert_allclose(estimate.target, target_by_j.mean(axis=0))
    np.testing.assert_allclose(estimate.biased, biased_by_j.mean(axis=0))
    np.testing.assert_allclose(
        estimate.difference,
        target_by_j.mean(axis=0) - biased_by_j.mean(axis=0),
    )


def test_vmcrg_gradient_sign() -> None:
    target = np.array([0.25, -0.10, 0.40])
    biased = np.array([0.50, -0.30, 0.35])
    gradient = vmcrg_gradient(target, biased)
    np.testing.assert_allclose(
        gradient,
        target - biased,
        atol=0.0,
        rtol=0.0,
    )
    estimate = estimate_gradient(None, target[None, :], biased[None, :])
    np.testing.assert_array_equal(estimate.difference, gradient)


def test_uniform_optimum_recovers_negative_bias() -> None:
    exact = exact_two_state_vmcrg()
    np.testing.assert_allclose(
        exact.recovered_hamiltonian,
        -exact.optimal_bias_centered,
        atol=2e-12,
        rtol=0.0,
    )
    probability = np.exp(
        -exact.effective_hamiltonian_centered - exact.optimal_bias_centered
    )
    probability /= probability.sum()
    np.testing.assert_allclose(probability, (0.5, 0.5), atol=2e-14, rtol=0.0)
    assert np.mean(exact.optimal_bias_centered) == pytest.approx(
        0.0,
        abs=2e-15,
        rel=0.0,
    )


def _training_case() -> tuple[TemplateEncoder, SymmetricLocalTT, InMemoryVMCRGBackend]:
    rng = np.random.default_rng(2026072922)
    encoder = TemplateEncoder("cube", True, 1)
    q = rng.choice(np.array([-1, 1], dtype=np.int8), size=(3, 3, 3))
    bonds = EABonds.sample(9, rng)
    base = encoder.encode(q, bonds, (0, 0, 0))
    target_batches = []
    biased_batches = []
    for _ in range(4):
        target = np.repeat(base[None, :], 24, axis=0)
        biased = target.copy()
        q_indices = np.asarray(encoder.q_token_indices)
        target[:, q_indices] = rng.choice(
            np.array([-1, 1], dtype=np.int8),
            size=(24, encoder.q_token_count),
        )
        biased[:, q_indices] = rng.choice(
            np.array([-1, 1], dtype=np.int8),
            size=(24, encoder.q_token_count),
            p=(0.65, 0.35),
        )
        target_batches.append(target)
        biased_batches.append(biased)
    tt = SymmetricLocalTT(LocalTensorTrain.random(13, 2, seed=104), encoder)
    backend = InMemoryVMCRGBackend(
        target_batches=target_batches,
        biased_batches=biased_batches,
        j_ids=tuple(f"J-{index}" for index in range(24)),
        seed=105,
    )
    return encoder, tt, backend


def _small_training_case() -> tuple[
    TemplateEncoder,
    SymmetricLocalTT,
    InMemoryVMCRGBackend,
]:
    encoder, tt, source = _training_case()
    backend = InMemoryVMCRGBackend(
        target_batches=(source.target_batches[0][:2],),
        biased_batches=(source.biased_batches[0][:2],),
        j_ids=source.j_ids[:2],
        seed=2026072946,
    )
    return encoder, tt, backend


class _StructuralVMCRGBackend:
    def __init__(self, delegate: InMemoryVMCRGBackend) -> None:
        self.delegate = delegate
        self._j_ids = delegate.j_ids
        shape = delegate.target_batches[0].shape
        self._draw_count = shape[1]
        self._token_count = shape[2]

    @property
    def j_ids(self) -> tuple[str, ...]:
        return self._j_ids

    @property
    def draw_count(self) -> int:
        return self._draw_count

    @property
    def token_count(self) -> int:
        return self._token_count

    def next_batch(self) -> VMCRGBatch:
        return self.delegate.next_batch()

    def checkpoint_state(self) -> dict[str, object]:
        return {
            "j_ids": self.j_ids,
            "draw_count": self.draw_count,
            "token_count": self.token_count,
            "rng_state": self.training_rng_state(),
            "delegate_state": self.delegate.checkpoint_state(),
        }

    def restore_state(self, state: dict[str, object]) -> None:
        restored = copy.deepcopy(state)
        self.delegate.restore_state(restored["delegate_state"])
        self._j_ids = tuple(restored["j_ids"])
        self._draw_count = int(restored["draw_count"])
        self._token_count = int(restored["token_count"])

    def training_rng_state(self) -> dict[str, object]:
        return self.delegate.training_rng_state()


class _AdversarialVMCRGBackend(_StructuralVMCRGBackend):
    def __init__(self, delegate: InMemoryVMCRGBackend, behavior: str) -> None:
        super().__init__(delegate)
        self.behavior = behavior

    def next_batch(self) -> object:
        batch = super().next_batch()
        if self.behavior == "wrong_type":
            return (batch.target_tokens, batch.biased_tokens, batch.j_ids)
        if self.behavior == "reordered_j":
            return VMCRGBatch(
                target_tokens=batch.target_tokens[::-1],
                biased_tokens=batch.biased_tokens[::-1],
                j_ids=batch.j_ids[::-1],
            )
        if self.behavior == "changing_draw_batch":
            return VMCRGBatch(
                target_tokens=np.repeat(batch.target_tokens, 2, axis=1),
                biased_tokens=np.repeat(batch.biased_tokens, 2, axis=1),
                j_ids=batch.j_ids,
            )
        if self.behavior == "changing_token_batch":
            return VMCRGBatch(
                target_tokens=batch.target_tokens[..., :-1],
                biased_tokens=batch.biased_tokens[..., :-1],
                j_ids=batch.j_ids,
            )
        if self.behavior == "changing_draw_schema":
            self._draw_count += 1
        if self.behavior == "changing_token_schema":
            self._token_count += 1
        if self.behavior == "changing_j_schema":
            self._j_ids = self._j_ids[::-1]
        return batch


class _AliasedMutateThenRaiseBackend(_StructuralVMCRGBackend):
    def __init__(self, delegate: InMemoryVMCRGBackend) -> None:
        super().__init__(delegate)
        self._shared_state = super().checkpoint_state()

    def checkpoint_state(self) -> dict[str, object]:
        return self._shared_state

    def next_batch(self) -> VMCRGBatch:
        batch = super().next_batch()
        self._shared_state["delegate_state"] = self.delegate.checkpoint_state()
        raise RuntimeError("sampler advanced before failure")

    def restore_state(self, state: dict[str, object]) -> None:
        super().restore_state(state)
        self._shared_state = copy.deepcopy(state)


class _MalformedStateBackend(_StructuralVMCRGBackend):
    def __init__(self, delegate: InMemoryVMCRGBackend, malformed: str) -> None:
        super().__init__(delegate)
        self.malformed = malformed

    def checkpoint_state(self) -> object:
        if self.malformed == "checkpoint":
            return []
        if self.malformed == "incomplete":
            return {"j_ids": self.j_ids}
        state = super().checkpoint_state()
        if self.malformed == "rng_mismatch":
            state["rng_state"] = self.delegate.training_rng_state()
        return state

    def training_rng_state(self) -> object:
        if self.malformed == "rng":
            return []
        if self.malformed == "rng_mismatch":
            return {"corrupt": True}
        return super().training_rng_state()


def _one_step_protocol() -> VMCRGProtocol:
    return VMCRGProtocol(
        c1_steps=1,
        c2_steps=1,
        c3_steps=0,
        linear_learning_rate=0.02,
        tt_learning_rate=0.01,
        gradient_clip=0.05,
        canonicalize_every=2,
    )


def test_in_memory_backend_promotes_legacy_schedule_to_one_draw() -> None:
    target = np.array([[1, -1, 1], [-1, 1, -1]], dtype=np.int8)
    biased = -target
    backend = InMemoryVMCRGBackend(
        target_batches=(target,),
        biased_batches=(biased,),
        j_ids=("J-0", "J-1"),
        seed=2026072945,
    )

    assert isinstance(backend, VMCRGSamplingBackend)
    batch = backend.next_batch()
    assert isinstance(batch, VMCRGBatch)
    assert batch.target_tokens.shape == (2, 1, 3)
    assert batch.biased_tokens.shape == (2, 1, 3)
    np.testing.assert_array_equal(batch.target_tokens[:, 0, :], target)
    np.testing.assert_array_equal(batch.biased_tokens[:, 0, :], biased)
    assert backend.j_ids == ("J-0", "J-1")
    assert backend.draw_count == 1
    assert backend.token_count == 3
    with pytest.raises(AttributeError):
        backend.draw_count = 2


def test_in_memory_backend_rejects_unequal_draws_across_schedule() -> None:
    one_draw = np.ones((2, 1, 3), dtype=np.int8)
    two_draws = np.ones((2, 2, 3), dtype=np.int8)
    with pytest.raises(ValueError, match="scheduled VMCRG batch shapes"):
        InMemoryVMCRGBackend(
            target_batches=(one_draw, two_draws),
            biased_batches=(one_draw, two_draws),
            j_ids=("J-0", "J-1"),
            seed=2026072947,
        )


def test_trainer_accepts_structural_sampling_backend_and_rejects_missing_method() -> None:
    _, tt, in_memory = _training_case()
    backend = _StructuralVMCRGBackend(in_memory)
    assert isinstance(backend, VMCRGSamplingBackend)
    protocol = VMCRGProtocol(
        c1_steps=1,
        c2_steps=1,
        c3_steps=0,
        linear_learning_rate=0.02,
        tt_learning_rate=0.01,
        gradient_clip=0.05,
        canonicalize_every=2,
    )
    trainer = _trainer(protocol, tt, backend)
    assert trainer.backend is backend
    assert trainer.step().stage == "C1"

    class MissingRestore:
        j_ids = in_memory.j_ids

        def next_batch(self) -> VMCRGBatch:
            return in_memory.next_batch()

        def checkpoint_state(self) -> dict[str, object]:
            return in_memory.checkpoint_state()

        def training_rng_state(self) -> dict[str, object]:
            return in_memory.training_rng_state()

    assert not isinstance(MissingRestore(), VMCRGSamplingBackend)
    with pytest.raises(TypeError, match="VMCRGSamplingBackend"):
        _trainer(protocol, tt, MissingRestore())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("_j_ids", "AB", "str or bytes"),
        ("_draw_count", "1", "draw_count.*integer"),
        ("_draw_count", 0, "draw_count.*positive"),
        ("_token_count", 12, "token_count.*encoder"),
    ),
)
def test_trainer_rejects_invalid_backend_schema_at_construction(
    field: str,
    value: object,
    message: str,
) -> None:
    _, tt, delegate = _small_training_case()
    backend = _StructuralVMCRGBackend(delegate)
    setattr(backend, field, value)
    with pytest.raises((TypeError, ValueError), match=message):
        _trainer(_one_step_protocol(), tt, backend)


def test_trainer_rejects_structurally_present_noncallable_method() -> None:
    _, tt, delegate = _small_training_case()

    class NonCallableBackend(_StructuralVMCRGBackend):
        next_batch = None

    with pytest.raises(TypeError, match="next_batch.*callable"):
        _trainer(_one_step_protocol(), tt, NonCallableBackend(delegate))


@pytest.mark.parametrize(
    ("malformed", "error", "message"),
    (
        ("checkpoint", TypeError, "Mapping"),
        ("rng", TypeError, "Mapping"),
        ("incomplete", ValueError, "incomplete"),
        ("rng_mismatch", ValueError, "RNG evidence"),
    ),
)
def test_step_rejects_malformed_backend_state_before_sampling(
    malformed: str,
    error: type[Exception],
    message: str,
) -> None:
    _, tt, delegate = _small_training_case()
    backend = _MalformedStateBackend(delegate, malformed)
    trainer = _trainer(_one_step_protocol(), tt, backend)
    before = copy.deepcopy(delegate.checkpoint_state())
    with pytest.raises(error, match=message):
        trainer.step()
    assert delegate.checkpoint_state() == before
    assert trainer.step_index == 0


@pytest.mark.parametrize(
    ("behavior", "error", "message"),
    (
        ("wrong_type", TypeError, "VMCRGBatch"),
        ("reordered_j", ValueError, "J inventory"),
        ("changing_draw_batch", ValueError, "batch shape"),
        ("changing_token_batch", ValueError, "token count"),
        ("changing_draw_schema", RuntimeError, "schema changed"),
        ("changing_token_schema", RuntimeError, "schema changed"),
        ("changing_j_schema", RuntimeError, "schema changed"),
    ),
)
def test_step_rejects_schema_and_batch_drift_with_full_rollback(
    behavior: str,
    error: type[Exception],
    message: str,
) -> None:
    _, tt, delegate = _small_training_case()
    backend = _AdversarialVMCRGBackend(delegate, behavior)
    trainer = _trainer(_one_step_protocol(), tt, backend)
    before = copy.deepcopy(backend.checkpoint_state())
    before_coefficients = trainer.coefficients.copy()
    with pytest.raises(error, match=message):
        trainer.step()
    assert backend.checkpoint_state() == before
    np.testing.assert_array_equal(trainer.coefficients, before_coefficients)
    assert trainer.step_index == 0


def test_step_deepcopies_snapshot_and_rolls_back_sampler_that_mutates_then_raises() -> None:
    _, tt, delegate = _small_training_case()
    backend = _AliasedMutateThenRaiseBackend(delegate)
    trainer = _trainer(_one_step_protocol(), tt, backend)
    before = copy.deepcopy(backend.checkpoint_state())
    with pytest.raises(RuntimeError, match="advanced before failure"):
        trainer.step()
    assert backend.checkpoint_state() == before
    assert trainer.step_index == 0


def test_unexpected_training_exception_rolls_back_complete_backend_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, tt, backend = _small_training_case()
    trainer = _trainer(_one_step_protocol(), tt, backend)
    before = copy.deepcopy(backend.checkpoint_state())

    def unexpected(*args, **kwargs):
        raise RuntimeError("unexpected gradient failure")

    monkeypatch.setattr(trainer, "_active_gradients", unexpected)
    with pytest.raises(RuntimeError, match="unexpected gradient failure"):
        trainer.step()
    assert backend.checkpoint_state() == before
    assert trainer.step_index == 0


def _trainer(
    protocol: VMCRGProtocol,
    tt: SymmetricLocalTT,
    backend: VMCRGSamplingBackend,
    *,
    route: BiasRoute | str = BiasRoute.C_LINEAR_PLUS_TT,
) -> VMCRGTrainer:
    context = CheckpointContext(
        beta=0.9,
        hashes={"design": "test-design"},
        j_split={
            "train": backend.j_ids,
            "validation": ("validation-placeholder",),
            "test": ("test-placeholder",),
        },
        rg_level=1,
    )
    return VMCRGTrainer(
        protocol,
        LinearFeatureBasis.cube_v1(),
        tt,
        backend,
        route=route,
        checkpoint_context=context,
        failure_checkpoint_root=Path("/tmp") / f"hg3d-vmcrg-test-{id(backend)}",
    )


def test_staged_trainer_clips_gradients_and_freezes_evaluation() -> None:
    _, tt, backend = _training_case()
    protocol = VMCRGProtocol(
        c1_steps=1,
        c2_steps=2,
        c3_steps=0,
        linear_learning_rate=0.02,
        tt_learning_rate=0.01,
        gradient_clip=0.05,
        canonicalize_every=1,
    )
    trainer = _trainer(protocol, tt, backend)
    records = trainer.run(3)
    assert [record.stage for record in records] == ["C1", "C2", "C2"]
    assert all(record.clipped_gradient_norm <= 0.05 + 1e-15 for record in records)
    assert all(record.finite for record in records)
    frozen = trainer.freeze(_heldout_batch(tt.encoder, budget="proposal"))
    assert np.isfinite(frozen.objective_estimate)
    assert np.isfinite(frozen.total_variation)
    assert np.isfinite(frozen.jensen_shannon)
    assert np.isfinite(frozen.mmd)
    assert frozen.projection.coefficients.shape == (5,)
    assert all(len(record.core_norms) == 13 for record in records)


def _heldout_batch(
    encoder: TemplateEncoder,
    *,
    budget: str,
    seed: int = 108,
    j_ids: tuple[str, ...] = ("heldout-0", "heldout-1", "heldout-2"),
) -> FrozenRouteBatch:
    rng = np.random.default_rng(seed)
    shape = (len(j_ids), 5, encoder.token_count)
    target = rng.choice(np.array([-1, 1], dtype=np.int8), size=shape)
    biased = rng.choice(np.array([-1, 1], dtype=np.int8), size=shape)
    return FrozenRouteBatch(
        target=target,
        biased=biased,
        j_ids=j_ids,
        split="validation",
        budget_kind=budget,
        proposal_count=500,
        wall_seconds=2.5,
        acceptance=0.42,
        iat=3.0,
        ess=250.0,
    )


def test_vmcrg_linear_and_tt_gradients_match_finite_differences() -> None:
    encoder, tt, backend = _training_case()
    batch = backend.next_batch()
    target = batch.target_tokens.reshape(-1, batch.target_tokens.shape[-1])
    biased = batch.biased_tokens.reshape(-1, batch.biased_tokens.shape[-1])
    basis = LinearFeatureBasis.cube_v1()
    target_features = np.asarray([basis.local_features(row, encoder) for row in target])
    biased_features = np.asarray([basis.local_features(row, encoder) for row in biased])
    analytic_linear = vmcrg_gradient(target_features.mean(0), biased_features.mean(0))
    direction = np.array([0.3, -0.2, 0.1, 0.05, -0.15])
    epsilon = 1.0e-6
    numeric_linear = (
        np.mean(target_features @ (epsilon * direction))
        - np.mean(biased_features @ (epsilon * direction))
        - np.mean(target_features @ (-epsilon * direction))
        + np.mean(biased_features @ (-epsilon * direction))
    ) / (2.0 * epsilon)
    assert float(analytic_linear @ direction) == pytest.approx(
        numeric_linear,
        abs=2e-10,
        rel=0.0,
    )

    weights = np.full(target.shape[0], 1.0 / target.shape[0])
    analytic_tt = tt.gradient(target, weights).add(
        tt.gradient(biased, weights).scale(-1.0)
    )
    core_index, core_entry = 4, (1, 0, 1)
    plus = LocalTensorTrain.from_arrays(tt.model.save_arrays())
    minus = LocalTensorTrain.from_arrays(tt.model.save_arrays())
    plus.cores[core_index][core_entry] += epsilon
    minus.cores[core_index][core_entry] -= epsilon
    plus_tt = SymmetricLocalTT(plus, encoder)
    minus_tt = SymmetricLocalTT(minus, encoder)
    numeric_tt = (
        np.mean(plus_tt.values(target))
        - np.mean(plus_tt.values(biased))
        - np.mean(minus_tt.values(target))
        + np.mean(minus_tt.values(biased))
    ) / (2.0 * epsilon)
    assert analytic_tt.cores[core_index][core_entry] == pytest.approx(
        numeric_tt,
        abs=2e-6,
        rel=0.0,
    )


def test_trainer_gradients_use_explicit_draw_then_j_means() -> None:
    _, tt, backend = _training_case()
    single_draw = backend.next_batch()
    target = np.concatenate(
        (single_draw.target_tokens, single_draw.biased_tokens),
        axis=1,
    )
    biased = np.concatenate(
        (single_draw.biased_tokens, single_draw.biased_tokens),
        axis=1,
    )
    batch = VMCRGBatch(
        target_tokens=target,
        biased_tokens=biased,
        j_ids=single_draw.j_ids,
    )
    trainer = _trainer(
        VMCRGProtocol(
            c1_steps=1,
            c2_steps=1,
            c3_steps=0,
            linear_learning_rate=0.02,
            tt_learning_rate=0.01,
            gradient_clip=0.05,
            canonicalize_every=2,
        ),
        tt,
        backend,
    )

    linear, tensor = trainer._active_gradients("C3", batch)
    target_features = trainer._features(target.reshape(-1, target.shape[-1])).reshape(
        target.shape[0], target.shape[1], -1
    )
    biased_features = trainer._features(biased.reshape(-1, biased.shape[-1])).reshape(
        biased.shape[0], biased.shape[1], -1
    )
    expected_linear = target_features.mean(axis=1).mean(axis=0) - biased_features.mean(
        axis=1
    ).mean(axis=0)
    np.testing.assert_allclose(linear, expected_linear, atol=0.0, rtol=0.0)

    def mean_whole_j_tt(tokens: np.ndarray):
        per_j = [
            trainer.tt.gradient(
                row,
                np.full(row.shape[0], 1.0 / row.shape[0]),
            )
            for row in tokens
        ]
        result = per_j[0].scale(1.0 / len(per_j))
        for gradient in per_j[1:]:
            result = result.add(gradient.scale(1.0 / len(per_j)))
        return result

    expected_tensor = mean_whole_j_tt(target).add(
        mean_whole_j_tt(biased).scale(-1.0)
    )
    assert tensor is not None
    for actual, expected in zip(tensor.cores, expected_tensor.cores, strict=True):
        np.testing.assert_allclose(actual, expected, atol=2e-15, rtol=0.0)


def test_training_step_objective_uses_draw_then_j_reducer() -> None:
    _, tt, source = _small_training_case()
    single = source.next_batch()
    target = np.concatenate(
        (single.target_tokens, single.biased_tokens),
        axis=1,
    )
    biased = np.concatenate(
        (single.biased_tokens, single.biased_tokens),
        axis=1,
    )
    backend = InMemoryVMCRGBackend(
        target_batches=(target,),
        biased_batches=(biased,),
        j_ids=single.j_ids,
        seed=2026072948,
    )
    trainer = _trainer(_one_step_protocol(), tt, backend)

    record = trainer.step()
    target_output = trainer._output_values(
        "C1", trainer.tt, trainer.coefficients, target
    )
    biased_output = trainer._output_values(
        "C1", trainer.tt, trainer.coefficients, biased
    )
    expected = target_output.mean(axis=1).mean(axis=0) - biased_output.mean(
        axis=1
    ).mean(axis=0)
    assert expected != pytest.approx(0.0, abs=2e-15, rel=0.0)
    assert record.objective_estimate == pytest.approx(expected, abs=2e-15, rel=0.0)


def test_route_b_omits_linear_branch_and_stage_lengths_are_enforced() -> None:
    _, tt, backend = _training_case()
    protocol = VMCRGProtocol(
        c1_steps=1,
        c2_steps=2,
        c3_steps=1,
        linear_learning_rate=0.02,
        tt_learning_rate=0.01,
        gradient_clip=0.05,
        canonicalize_every=2,
    )
    trainer = _trainer(protocol, tt, backend, route=BiasRoute.B_CONDITIONED_TT)
    records = trainer.run(2)
    assert [record.stage for record in records] == ["B", "B"]
    assert trainer.coefficients.size == 0
    with pytest.raises(RuntimeError, match="exhausted"):
        trainer.step()


def test_route_c_sampling_bias_disables_tt_until_c1_is_complete() -> None:
    _, tt, backend = _training_case()
    trainer = _trainer(
        VMCRGProtocol(
            c1_steps=1,
            c2_steps=1,
            c3_steps=0,
            linear_learning_rate=0.02,
            tt_learning_rate=0.01,
            gradient_clip=0.05,
            canonicalize_every=4,
        ),
        tt,
        backend,
    )
    tokens = backend.target_batches[0][0, 0]
    full_before = trainer.current_bias().local_value(tokens)
    sampling_before = trainer.sampling_bias().local_value(tokens)
    assert sampling_before == pytest.approx(0.0, abs=0.0, rel=0.0)
    assert abs(full_before) > 1e-14

    assert trainer.step().stage == "C1"

    sampling_after = trainer.sampling_bias().local_value(tokens)
    assert sampling_after != pytest.approx(
        float(trainer.coefficients @ trainer.basis.local_features(tokens, tt.encoder)),
        abs=1e-14,
        rel=0.0,
    )


def test_c3_requires_immutable_heldout_evidence() -> None:
    _, tt, backend = _training_case()
    protocol = VMCRGProtocol(
        c1_steps=1,
        c2_steps=1,
        c3_steps=1,
        linear_learning_rate=0.02,
        tt_learning_rate=0.01,
        gradient_clip=0.05,
        canonicalize_every=2,
    )
    trainer = _trainer(protocol, tt, backend)
    trainer.run(2)
    with pytest.raises(RuntimeError, match="evidence"):
        trainer.step()
    evaluation = trainer.freeze(_heldout_batch(tt.encoder, budget="proposal"))
    baseline = replace(
        evaluation,
        route_name="linear",
        initialization_hash=None,
        primary_metric_by_j=evaluation.primary_metric_by_j + 0.1,
    )
    trainer.authorize_joint_tuning(
        baseline_evaluation=baseline,
        evaluation=evaluation,
        seed=2026072931,
        bootstrap_replicates=500,
    )
    assert trainer.step().stage == "C3"
    with pytest.raises(RuntimeError, match="exhausted"):
        trainer.step()


def test_c3_authorization_recomputes_assessment_from_bound_evaluations() -> None:
    _, tt, backend = _training_case()
    protocol = VMCRGProtocol(
        c1_steps=1,
        c2_steps=1,
        c3_steps=1,
        linear_learning_rate=0.02,
        tt_learning_rate=0.01,
        gradient_clip=0.05,
        canonicalize_every=2,
    )
    trainer = _trainer(protocol, tt, backend)
    trainer.run(2)
    candidate = trainer.freeze(_heldout_batch(tt.encoder, budget="proposal"))
    baseline = replace(
        candidate,
        route_name="linear",
        initialization_hash=None,
        primary_metric_by_j=candidate.primary_metric_by_j + 0.1,
    )

    assessment = trainer.authorize_joint_tuning(
        baseline_evaluation=baseline,
        evaluation=candidate,
        seed=2026072941,
        bootstrap_replicates=500,
    )
    assert assessment.classification == "PASS"
    assert assessment.confidence_interval[0] > 0.0
    assert trainer.step().stage == "C3"


def _c3_authorization_case(
    budget: str,
) -> tuple[VMCRGTrainer, FrozenEvaluation, FrozenEvaluation]:
    _, tt, backend = _training_case()
    protocol = VMCRGProtocol(
        c1_steps=1,
        c2_steps=1,
        c3_steps=1,
        linear_learning_rate=0.02,
        tt_learning_rate=0.01,
        gradient_clip=0.05,
        canonicalize_every=2,
    )
    trainer = _trainer(protocol, tt, backend)
    trainer.run(2)
    candidate = trainer.freeze(_heldout_batch(tt.encoder, budget=budget))
    baseline = replace(
        candidate,
        route_name="linear",
        initialization_hash=None,
        primary_metric_by_j=candidate.primary_metric_by_j + 0.1,
    )
    return trainer, baseline, candidate


def test_c3_proposal_budget_accepts_unequal_wall_times() -> None:
    trainer, baseline, candidate = _c3_authorization_case("proposal")
    with pytest.raises(ValueError, match="matched immutable"):
        trainer.authorize_joint_tuning(
            baseline_evaluation=replace(
                baseline,
                proposal_count=baseline.proposal_count + 1,
            ),
            evaluation=candidate,
            seed=2026072943,
            bootstrap_replicates=500,
        )

    assessment = trainer.authorize_joint_tuning(
        baseline_evaluation=replace(
            baseline,
            wall_seconds=baseline.wall_seconds + 1.0,
        ),
        evaluation=candidate,
        seed=2026072943,
        bootstrap_replicates=500,
    )
    assert assessment.classification == "PASS"


def test_c3_wall_budget_accepts_unequal_proposal_counts() -> None:
    trainer, baseline, candidate = _c3_authorization_case("wall")
    with pytest.raises(ValueError, match="matched immutable"):
        trainer.authorize_joint_tuning(
            baseline_evaluation=replace(
                baseline,
                wall_seconds=baseline.wall_seconds + 1.0,
            ),
            evaluation=candidate,
            seed=2026072944,
            bootstrap_replicates=500,
        )

    assessment = trainer.authorize_joint_tuning(
        baseline_evaluation=replace(
            baseline,
            proposal_count=baseline.proposal_count + 1,
        ),
        evaluation=candidate,
        seed=2026072944,
        bootstrap_replicates=500,
    )
    assert assessment.classification == "PASS"


def test_c3_rejects_evaluation_from_another_initialization() -> None:
    _, tt, backend = _training_case()
    protocol = VMCRGProtocol(
        c1_steps=1,
        c2_steps=1,
        c3_steps=1,
        linear_learning_rate=0.02,
        tt_learning_rate=0.01,
        gradient_clip=0.05,
        canonicalize_every=2,
    )
    trainer = _trainer(protocol, tt, backend)
    trainer.run(2)
    candidate = trainer.freeze(_heldout_batch(tt.encoder, budget="proposal"))
    baseline = replace(
        candidate,
        route_name="linear",
        initialization_hash=None,
        primary_metric_by_j=candidate.primary_metric_by_j + 0.1,
    )
    foreign = replace(candidate, initialization_hash="f" * 64)
    with pytest.raises(ValueError, match="initialization"):
        trainer.authorize_joint_tuning(
            baseline_evaluation=baseline,
            evaluation=foreign,
            seed=2026072942,
            bootstrap_replicates=500,
        )


def test_c3_clip_norm_includes_linear_and_every_tt_core() -> None:
    _, tt, backend = _training_case()
    protocol = VMCRGProtocol(
        c1_steps=1,
        c2_steps=1,
        c3_steps=1,
        linear_learning_rate=0.02,
        tt_learning_rate=0.01,
        gradient_clip=0.01,
        canonicalize_every=4,
        momentum=0.0,
    )
    trainer = _trainer(protocol, tt, backend)
    trainer.run(2)
    evaluation = trainer.freeze(_heldout_batch(tt.encoder, budget="proposal"))
    baseline = replace(
        evaluation,
        route_name="linear",
        initialization_hash=None,
        primary_metric_by_j=evaluation.primary_metric_by_j + 0.1,
    )
    trainer.authorize_joint_tuning(
        baseline_evaluation=baseline,
        evaluation=evaluation,
        seed=2026072932,
        bootstrap_replicates=500,
    )
    target_batch = backend.target_batches[
        backend.index % len(backend.target_batches)
    ]
    biased_batch = backend.biased_batches[
        backend.index % len(backend.biased_batches)
    ]
    target = target_batch.reshape(-1, target_batch.shape[-1])
    biased = biased_batch.reshape(-1, biased_batch.shape[-1])
    target_features = np.asarray(
        [trainer.basis.local_features(row, tt.encoder) for row in target]
    )
    biased_features = np.asarray(
        [trainer.basis.local_features(row, tt.encoder) for row in biased]
    )
    linear = vmcrg_gradient(target_features.mean(0), biased_features.mean(0))
    weights = np.full(target.shape[0], 1.0 / target.shape[0])
    tensor = trainer.tt.gradient(target, weights).add(
        trainer.tt.gradient(biased, weights).scale(-1.0)
    )
    expected_joint_norm = np.sqrt(float(linear @ linear) + tensor.norm() ** 2)

    record = trainer.step()
    assert record.unclipped_gradient_norm == pytest.approx(
        expected_joint_norm,
        abs=2e-12,
        rel=0.0,
    )
    assert record.clipped_gradient_norm == pytest.approx(0.01, abs=2e-15, rel=0.0)


def test_freeze_rejects_training_ids_and_uses_complete_route_c_output() -> None:
    _, tt, backend = _training_case()
    protocol = VMCRGProtocol(
        c1_steps=1,
        c2_steps=1,
        c3_steps=0,
        linear_learning_rate=0.02,
        tt_learning_rate=0.01,
        gradient_clip=0.05,
        canonicalize_every=2,
    )
    trainer = _trainer(protocol, tt, backend)
    trainer.run(2)
    overlapping = _heldout_batch(
        tt.encoder,
        budget="proposal",
        j_ids=("J-0", "heldout-1", "heldout-2"),
    )
    with pytest.raises(ValueError, match="held-out"):
        trainer.freeze(overlapping)
    batch = _heldout_batch(tt.encoder, budget="proposal")
    frozen = trainer.freeze(batch)
    bias = OverlapBias(
        BiasRoute.C_LINEAR_PLUS_TT,
        trainer.basis,
        trainer.coefficients,
        trainer.tt,
    )
    target = batch.target.reshape(-1, batch.target.shape[-1])
    biased = batch.biased.reshape(-1, batch.biased.shape[-1])
    expected = np.mean([bias.local_value(row) for row in target]) - np.mean(
        [bias.local_value(row) for row in biased]
    )
    assert frozen.objective_estimate == pytest.approx(expected, abs=2e-12, rel=0.0)


def test_four_route_comparison_requires_both_fair_budget_groups() -> None:
    encoder, tt, _ = _training_case()
    basis = LinearFeatureBasis.cube_v1()
    coefficients = np.array([0.1, -0.04, 0.03, 0.02, -0.01])
    route_c = OverlapBias(BiasRoute.C_LINEAR_PLUS_TT, basis, coefficients, tt)
    route_b = OverlapBias(
        BiasRoute.B_CONDITIONED_TT,
        None,
        np.empty(0),
        SymmetricLocalTT(LocalTensorTrain.from_arrays(tt.model.save_arrays()), encoder),
    )
    q_encoder = TemplateEncoder("cube", False, 1)
    route_a = OverlapBias(
        BiasRoute.A_Q_ONLY,
        None,
        np.empty(0),
        SymmetricLocalTT(LocalTensorTrain.random(8, 2, seed=109), q_encoder),
    )
    evaluations = []
    for budget, seed in (("proposal", 110), ("wall", 111)):
        conditioned = _heldout_batch(encoder, budget=budget, seed=seed)
        q_only = FrozenRouteBatch(
            target=conditioned.target[..., encoder.q_token_indices],
            biased=conditioned.biased[..., encoder.q_token_indices],
            j_ids=conditioned.j_ids,
            split=conditioned.split,
            budget_kind=budget,
            proposal_count=conditioned.proposal_count,
            wall_seconds=conditioned.wall_seconds,
            acceptance=conditioned.acceptance,
            iat=conditioned.iat,
            ess=conditioned.ess,
        )
        evaluations.extend(
            (
                evaluate_frozen_linear(basis, coefficients, encoder, conditioned),
                evaluate_frozen_bias(route_c, conditioned, initialization_hash="same"),
                evaluate_frozen_bias(route_b, conditioned, initialization_hash="same"),
                evaluate_frozen_bias(route_a, q_only, initialization_hash="ablation"),
            )
        )
    comparison = compare_frozen_routes(
        evaluations,
        seed=112,
        bootstrap_replicates=500,
    )
    assert comparison.route_names == ("linear", "C", "B", "A")
    assert comparison.budget_kinds == ("proposal", "wall")
    assert set(comparison.assessments) == {"C", "B", "A"}


def test_tt_improvement_requires_whole_j_interval_excluding_zero() -> None:
    positive = classify_tt_improvement(
        np.linspace(0.05, 0.15, 24),
        other_metric_regression=np.zeros(24),
        seed=106,
        bootstrap_replicates=1000,
    )
    assert positive.classification == "PASS"
    negative = classify_tt_improvement(
        np.linspace(-0.05, 0.05, 24),
        other_metric_regression=np.zeros(24),
        seed=107,
        bootstrap_replicates=1000,
    )
    assert negative.classification == "SCIENTIFIC_NEGATIVE"
    with pytest.raises(ValueError, match="finite"):
        classify_tt_improvement(
            np.array([0.1, np.nan]),
            other_metric_regression=np.zeros(2),
            seed=113,
            bootstrap_replicates=100,
        )
