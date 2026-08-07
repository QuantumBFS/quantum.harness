from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from spinglass3d.checkpoint import TrainingCheckpoint
from spinglass3d.linear_bias import LinearFeatureBasis
from spinglass3d.model import EABonds
from spinglass3d.templates import TemplateEncoder
from spinglass3d.tensor_train import LocalTensorTrain
from spinglass3d.tensor_train import SymmetricLocalTT
from spinglass3d.vmcrg import (
    CheckpointContext,
    InMemoryVMCRGBackend,
    VMCRGProtocol,
    VMCRGTrainer,
)


def test_training_checkpoint_round_trip_and_rng_trajectory(tmp_path) -> None:
    model = LocalTensorTrain.random(13, 2, seed=101)
    rng = np.random.default_rng(102)
    rng.random(11)
    state = copy.deepcopy(rng.bit_generator.state)
    checkpoint = TrainingCheckpoint(
        cores=model.save_arrays(),
        coefficients=np.arange(5, dtype=np.float64),
        optimizer_state={"moment": [0.1, 0.2], "step": 7},
        rng_state=state,
        pt_state={"replica_ids": [2, 0, 1]},
        hashes={"design": "abc123"},
        step=7,
        beta=0.9,
        j_split={"train": ["J-1"], "validation": ["J-2"], "test": ["J-3"]},
        rg_level=1,
    )
    destination = tmp_path / "checkpoint-step-7"
    checkpoint.save(destination)
    loaded = TrainingCheckpoint.load(destination)
    for left, right in zip(loaded.cores, model.cores, strict=True):
        np.testing.assert_array_equal(left, right)
    np.testing.assert_array_equal(loaded.coefficients, checkpoint.coefficients)
    restored_rng = np.random.default_rng()
    restored_rng.bit_generator.state = loaded.rng_state
    expected_rng = np.random.default_rng()
    expected_rng.bit_generator.state = state
    np.testing.assert_array_equal(restored_rng.random(32), expected_rng.random(32))
    with pytest.raises(FileExistsError, match="checkpoint"):
        checkpoint.save(destination)


def test_training_checkpoint_stores_nested_sampler_arrays_in_npz(tmp_path) -> None:
    model = LocalTensorTrain.random(13, 2, seed=2026073570)
    spins = np.ones((2, 3, 4, 5), dtype=np.int8)
    keys = np.arange(8, dtype=np.uint32).reshape(4, 2)
    checkpoint = TrainingCheckpoint(
        cores=model.save_arrays(),
        coefficients=np.zeros(5),
        optimizer_state={"moments": [np.arange(3, dtype=np.float64)]},
        rng_state={"per_j": [{"key": keys}]},
        pt_state={"per_j_states": [{"state": {"spins": spins}}]},
        hashes={"test": "a" * 64},
        step=1,
        beta=0.9,
        j_split={"train": ["J-0"], "validation": [], "test": []},
        rg_level=1,
    )
    destination = tmp_path / "physical-checkpoint"

    checkpoint.save(destination)
    loaded = TrainingCheckpoint.load(destination)

    assert (destination / "state.npz").is_file()
    metadata = (destination / "metadata.json").read_text(encoding="ascii")
    assert "state_sha256" in metadata
    assert "[[[[1" not in metadata
    restored_spins = loaded.pt_state["per_j_states"][0]["state"]["spins"]
    restored_key = loaded.rng_state["per_j"][0]["key"]
    np.testing.assert_array_equal(restored_spins, spins)
    np.testing.assert_array_equal(restored_key, keys)
    assert restored_spins.dtype == np.int8
    assert restored_key.dtype == np.uint32


def test_checkpoint_rejects_nonfinite_arrays() -> None:
    model = LocalTensorTrain.random(13, 2, seed=103)
    cores = list(model.save_arrays())
    cores[0][0, 0, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        TrainingCheckpoint(
            cores=tuple(cores),
            coefficients=np.zeros(5),
            optimizer_state={},
            rng_state={},
            pt_state={},
            hashes={},
            step=0,
            beta=0.8,
            j_split={},
            rg_level=1,
        )


_DEFAULT_CHECKPOINT_ROOT = object()


def _trainer(seed: int, checkpoint_root=_DEFAULT_CHECKPOINT_ROOT) -> VMCRGTrainer:
    rng = np.random.default_rng(seed)
    encoder = TemplateEncoder("cube", True, 1)
    q = rng.choice(np.array([-1, 1], dtype=np.int8), size=(3, 3, 3))
    bonds = EABonds.sample(9, rng)
    base = encoder.encode(q, bonds, (0, 0, 0))
    target = np.repeat(base[None, :], 8, axis=0)
    biased = target.copy()
    biased[:, encoder.q_token_indices[:2]] *= -1
    backend = InMemoryVMCRGBackend(
        target_batches=(target, target[::-1].copy()),
        biased_batches=(biased, biased[::-1].copy()),
        j_ids=tuple(f"J-{index}" for index in range(8)),
        seed=seed + 1,
    )
    context = CheckpointContext(
        beta=0.9,
        hashes={"design": "abc123"},
        j_split={
            "train": tuple(f"J-{index}" for index in range(8)),
            "validation": ("V-0",),
            "test": ("T-0",),
        },
        rg_level=1,
    )
    selected_root = (
        Path("/tmp") / f"hg3d-checkpoint-test-{seed}"
        if checkpoint_root is _DEFAULT_CHECKPOINT_ROOT
        else checkpoint_root
    )
    return VMCRGTrainer(
        VMCRGProtocol(
            c1_steps=1,
            c2_steps=3,
            c3_steps=0,
            linear_learning_rate=0.02,
            tt_learning_rate=0.01,
            gradient_clip=0.1,
            canonicalize_every=2,
        ),
        LinearFeatureBasis.cube_v1(),
        SymmetricLocalTT(LocalTensorTrain.random(13, 2, seed=seed + 2), encoder),
        backend,
        checkpoint_context=context,
        failure_checkpoint_root=selected_root,
    )


def test_trainer_restore_reproduces_uniforms_decisions_and_next_update(tmp_path) -> None:
    source = _trainer(120)
    source.run(2)
    checkpoint = source.checkpoint_from_context()
    destination = tmp_path / "resume"
    checkpoint.save(destination)
    loaded = TrainingCheckpoint.load(destination)

    resumed = _trainer(120)
    resumed.restore(loaded, context=source.checkpoint_context)
    source_uniforms, source_decisions = source.backend.draw_decisions(32)
    resumed_uniforms, resumed_decisions = resumed.backend.draw_decisions(32)
    np.testing.assert_array_equal(resumed_uniforms, source_uniforms)
    np.testing.assert_array_equal(resumed_decisions, source_decisions)
    source_step = source.step()
    resumed_step = resumed.step()
    assert resumed_step == source_step
    np.testing.assert_array_equal(resumed.coefficients, source.coefficients)
    for left, right in zip(resumed.tt.model.cores, source.tt.model.cores, strict=True):
        np.testing.assert_array_equal(left, right)


def test_nonfinite_step_rolls_back_and_saves_last_finite_checkpoint(tmp_path) -> None:
    trainer = _trainer(130, checkpoint_root=tmp_path / "failures")
    trainer.protocol = VMCRGProtocol(
        c1_steps=1,
        c2_steps=1,
        c3_steps=0,
        linear_learning_rate=1.0e308,
        tt_learning_rate=0.01,
        gradient_clip=1.0e308,
        canonicalize_every=2,
    )
    before_coefficients = trainer.coefficients.copy()
    before_cores = trainer.tt.model.save_arrays()
    before_backend = trainer.backend.checkpoint_state()
    with pytest.raises(FloatingPointError, match="NaN/Inf"):
        trainer.step()
    np.testing.assert_array_equal(trainer.coefficients, before_coefficients)
    for left, right in zip(trainer.tt.model.cores, before_cores, strict=True):
        np.testing.assert_array_equal(left, right)
    assert trainer.backend.checkpoint_state() == before_backend
    assert trainer.last_failure.classification == "CORRECTNESS_FAILURE"
    assert trainer.last_failure.failure_kind == "NUMERICAL_FAILURE"
    saved = TrainingCheckpoint.load(trainer.last_failure.checkpoint_path)
    np.testing.assert_array_equal(saved.coefficients, before_coefficients)


def test_training_refuses_to_start_without_failure_checkpoint_root() -> None:
    trainer = _trainer(131, checkpoint_root=None)
    before_backend = trainer.backend.checkpoint_state()
    with pytest.raises(RuntimeError, match="failure checkpoint"):
        trainer.step()
    assert trainer.backend.checkpoint_state() == before_backend


def test_nonfinite_value_error_path_rolls_back_and_saves_checkpoint(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trainer = _trainer(132, checkpoint_root=tmp_path / "failures")
    before_backend = trainer.backend.checkpoint_state()

    def nonfinite_gradient(*args, **kwargs):
        raise ValueError("gradient cores must be finite rank-three arrays")

    monkeypatch.setattr(trainer, "_active_gradients", nonfinite_gradient)
    with pytest.raises(FloatingPointError, match="NaN/Inf"):
        trainer.step()
    assert trainer.backend.checkpoint_state() == before_backend
    saved = TrainingCheckpoint.load(trainer.last_failure.checkpoint_path)
    assert saved.step == 0


def _context_with_train(
    context: CheckpointContext,
    train: tuple[str, ...],
) -> CheckpointContext:
    return CheckpointContext(
        beta=context.beta,
        hashes=context.hashes,
        j_split={
            "train": train,
            "validation": context.j_split["validation"],
            "test": context.j_split["test"],
        },
        rg_level=context.rg_level,
    )


def _trainer_snapshot(trainer: VMCRGTrainer) -> dict[str, object]:
    return {
        "backend": copy.deepcopy(trainer.backend.checkpoint_state()),
        "coefficients": trainer.coefficients.copy(),
        "cores": tuple(core.copy() for core in trainer.tt.model.cores),
        "step": trainer.step_index,
        "context": trainer.checkpoint_context,
    }


def _assert_trainer_snapshot(
    trainer: VMCRGTrainer,
    expected: dict[str, object],
) -> None:
    assert trainer.backend.checkpoint_state() == expected["backend"]
    np.testing.assert_array_equal(trainer.coefficients, expected["coefficients"])
    for actual, saved in zip(
        trainer.tt.model.cores,
        expected["cores"],
        strict=True,
    ):
        np.testing.assert_array_equal(actual, saved)
    assert trainer.step_index == expected["step"]
    assert trainer.checkpoint_context is expected["context"]


def test_in_memory_checkpoint_is_detached_complete_and_bound_to_ordered_j() -> None:
    trainer = _trainer(140)
    backend = trainer.backend
    state = backend.checkpoint_state()

    assert state["j_ids"] == backend.j_ids
    assert state["draw_count"] == backend.draw_count
    assert state["token_count"] == backend.token_count
    assert state["rng_state"] == backend.training_rng_state()
    checkpoint = trainer.checkpoint_from_context()
    assert checkpoint.pt_state["j_ids"] == backend.j_ids
    assert checkpoint.pt_state["draw_count"] == backend.draw_count
    assert checkpoint.pt_state["token_count"] == backend.token_count
    assert checkpoint.pt_state["rng_state"] == checkpoint.rng_state
    before = copy.deepcopy(backend.checkpoint_state())
    state["batch_index"] = 999
    state["rng_state"]["state"]["state"] = 0
    assert backend.checkpoint_state() == before


def test_in_memory_restore_rejects_permuted_j_before_mutation() -> None:
    trainer = _trainer(141)
    backend = trainer.backend
    before = copy.deepcopy(backend.checkpoint_state())
    corrupt = copy.deepcopy(before)
    corrupt["j_ids"] = tuple(reversed(backend.j_ids))

    with pytest.raises(ValueError, match="ordered J"):
        backend.restore_state(corrupt)
    assert backend.checkpoint_state() == before


def test_trainer_constructor_requires_exact_ordered_context_j_ids() -> None:
    trainer = _trainer(142)
    context = _context_with_train(
        trainer.checkpoint_context,
        tuple(reversed(trainer.backend.j_ids)),
    )

    with pytest.raises(ValueError, match="ordered backend J IDs"):
        VMCRGTrainer(
            trainer.protocol,
            trainer.basis,
            trainer.tt,
            trainer.backend,
            checkpoint_context=context,
            failure_checkpoint_root=Path("/tmp") / "hg3d-permuted-constructor",
        )


def test_checkpoint_creation_requires_exact_ordered_backend_j_ids() -> None:
    trainer = _trainer(143)
    split = dict(trainer.checkpoint_context.j_split)
    split["train"] = tuple(reversed(trainer.backend.j_ids))
    before = _trainer_snapshot(trainer)

    with pytest.raises(ValueError, match="ordered backend J IDs"):
        trainer.checkpoint(
            beta=trainer.checkpoint_context.beta,
            hashes=trainer.checkpoint_context.hashes,
            j_split=split,
            rg_level=trainer.checkpoint_context.rg_level,
        )
    _assert_trainer_snapshot(trainer, before)


@pytest.mark.parametrize("inventory", ("permuted", "foreign"))
def test_restore_rejects_context_inventory_before_any_mutation(
    inventory: str,
) -> None:
    source = _trainer(144)
    source.run(1)
    checkpoint = source.checkpoint_from_context()
    if inventory == "permuted":
        train = tuple(reversed(source.backend.j_ids))
    else:
        train = tuple(f"foreign-{index}" for index in range(len(source.backend.j_ids)))
    context = _context_with_train(source.checkpoint_context, train)
    split = dict(checkpoint.j_split)
    split["train"] = train
    incompatible = replace(checkpoint, j_split=split)
    resumed = _trainer(144)
    before = _trainer_snapshot(resumed)

    with pytest.raises(ValueError, match="ordered backend J IDs"):
        resumed.restore(incompatible, context=context)
    _assert_trainer_snapshot(resumed, before)


def test_restore_rejects_rng_evidence_mismatch_before_any_mutation() -> None:
    source = _trainer(145)
    source.run(1)
    checkpoint = source.checkpoint_from_context()
    corrupt = replace(checkpoint, rng_state={"corrupt": True})
    resumed = _trainer(145)
    before = _trainer_snapshot(resumed)

    with pytest.raises(ValueError, match="RNG"):
        resumed.restore(corrupt, context=source.checkpoint_context)
    _assert_trainer_snapshot(resumed, before)


def test_restore_rejects_malformed_sampler_state_before_any_mutation() -> None:
    source = _trainer(146)
    source.run(1)
    checkpoint = source.checkpoint_from_context()
    malformed_state = copy.deepcopy(checkpoint.pt_state)
    malformed_state.pop("decision_count")
    corrupt = replace(checkpoint, pt_state=malformed_state)
    resumed = _trainer(146)
    before = _trainer_snapshot(resumed)

    with pytest.raises(ValueError, match="incomplete"):
        resumed.restore(corrupt, context=source.checkpoint_context)
    _assert_trainer_snapshot(resumed, before)
