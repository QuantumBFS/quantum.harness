from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence

import numpy as np
import pytest

from spinglass3d.backend import BackendCase
from spinglass3d.bias import BiasRoute, OverlapBias
from spinglass3d.jax_biased_backend import JaxBiasedPairBackend
from spinglass3d.jax_vmcrg_backend import (
    JaxVMCRGSamplingBackend,
    build_uniform_target_tokens,
    decode_token_codes,
    select_equal_per_j_rows,
)
from spinglass3d.linear_bias import LinearFeatureBasis
from spinglass3d.model import EABonds
from spinglass3d.templates import TemplateEncoder
from spinglass3d.tensor_train import LocalTensorTrain, SymmetricLocalTT
from spinglass3d.vmcrg import (
    CheckpointContext,
    VMCRGBatch,
    VMCRGProtocol,
    VMCRGSamplingBackend,
    VMCRGTrainer,
)


def _bias(
    seed: int,
    *,
    route: BiasRoute = BiasRoute.B_CONDITIONED_TT,
    chi: int = 2,
) -> OverlapBias:
    encoder = TemplateEncoder("cube", conditioned=True, rg_level=1)
    tt = SymmetricLocalTT(
        LocalTensorTrain.random(encoder.token_count, chi, seed=seed),
        encoder,
    )
    if route is BiasRoute.C_LINEAR_PLUS_TT:
        return OverlapBias(
            route,
            LinearFeatureBasis.cube_v1(),
            np.array([0.11, -0.07, 0.05, 0.03, -0.02]),
            tt,
        )
    return OverlapBias(route, None, np.empty(0), tt)


def _case(
    seed: int,
    *,
    betas: Sequence[float] = (0.2, 0.9),
    pairs: int = 1,
    distinguish_temperatures: bool = False,
) -> BackendCase:
    source = BackendCase.random(
        length=3,
        temperatures=2,
        samples=1,
        walkers=2 * pairs,
        seed=seed,
    )
    spins = source.spins.copy()
    if distinguish_temperatures:
        spins[0, 0, 0::2] = 1
        spins[0, 0, 1::2] = 1
        spins[0, 1, 0::2] = 1
        spins[0, 1, 1::2] = -1
    return BackendCase(
        spins=spins,
        bonds=source.bonds,
        betas=np.asarray(betas, dtype=np.float64),
        seed=seed,
    )


def _raw(
    case: BackendCase,
    biases: OverlapBias | Sequence[OverlapBias],
) -> JaxBiasedPairBackend:
    jax = pytest.importorskip("jax")
    if jax.default_backend() != "cpu":
        pytest.skip("adapter correctness tests require the CPU JAX backend")
    return JaxBiasedPairBackend(case, biases, required_platform="cpu")


def _adapter(
    seed: int,
    *,
    sweeps_per_batch: int,
    distinguish_temperatures: bool = False,
) -> tuple[JaxVMCRGSamplingBackend, tuple[JaxBiasedPairBackend, ...]]:
    bias = _bias(2026073501)
    raw = tuple(
        _raw(
            _case(
                seed + index,
                distinguish_temperatures=distinguish_temperatures,
            ),
            bias,
        )
        for index in range(2)
    )
    adapter = JaxVMCRGSamplingBackend(
        j_ids=("J-0", "J-1"),
        backends=raw,
        draw_count=1,
        target_temperature_index=1,
        sweeps_per_batch=sweeps_per_batch,
        seed=seed + 1000,
    )
    return adapter, raw


def _state_equal(left: object, right: object) -> bool:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return set(left) == set(right) and all(
            _state_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, np.ndarray) or isinstance(right, np.ndarray):
        return np.array_equal(np.asarray(left), np.asarray(right))
    if (
        isinstance(left, Sequence)
        and not isinstance(left, (str, bytes))
        and isinstance(right, Sequence)
        and not isinstance(right, (str, bytes))
    ):
        return len(left) == len(right) and all(
            _state_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def test_equal_per_j_selection_accepts_unequal_raw_pools_without_ragged_batch() -> None:
    first = np.array([[1, -1, 1], [-1, 1, -1]], dtype=np.int8)
    second = np.array(
        [[1, 1, -1], [-1, -1, 1], [1, -1, -1], [-1, 1, 1]],
        dtype=np.int8,
    )
    indices = (np.array([0, 1]), np.array([3, 1]))

    selected = select_equal_per_j_rows((first, second), indices)
    duplicated = select_equal_per_j_rows(
        (np.concatenate((first, first), axis=0), second),
        indices,
    )

    assert selected.shape == (2, 2, 3)
    np.testing.assert_array_equal(duplicated, selected)
    np.testing.assert_array_equal(selected[0], first[indices[0]])
    np.testing.assert_array_equal(selected[1], second[indices[1]])
    assert selected.mean(axis=1).mean(axis=0) == pytest.approx(
        np.mean(selected.mean(axis=1), axis=0)
    )


def test_uniform_target_builder_preserves_disorder_and_samples_independent_q() -> None:
    biased = np.ones((2, 4096, 5), dtype=np.int8)
    biased[..., 1] = -1
    biased[..., 3] = -1
    rng = np.random.default_rng(2026073502)

    target = build_uniform_target_tokens(biased, (0, 2, 4), rng)

    np.testing.assert_array_equal(target[..., (1, 3)], biased[..., (1, 3)])
    assert np.all((target[..., (0, 2, 4)] == -1) | (target[..., (0, 2, 4)] == 1))
    assert np.max(np.abs(target[..., (0, 2, 4)].mean(axis=(0, 1)))) < 0.04
    assert not np.shares_memory(target, biased)


def test_adapter_uses_only_target_temperature_and_matches_direct_encoder() -> None:
    adapter, raw = _adapter(
        2026073503,
        sweeps_per_batch=0,
        distinguish_temperatures=True,
    )
    expected_rows = []
    auxiliary_rows = []
    for backend in raw:
        target_code = backend.token_codes[0, 1, 0]
        auxiliary_code = backend.token_codes[0, 0, 0]
        expected = decode_token_codes(np.asarray([target_code]), backend.token_count)[0]
        auxiliary = decode_token_codes(
            np.asarray([auxiliary_code]), backend.token_count
        )[0]
        direct = backend.encoder.encode(
            backend.q_prime[0, 1],
            EABonds(backend.case.bonds[0]),
            (0, 0, 0),
        )
        np.testing.assert_array_equal(expected, direct)
        expected_rows.append(expected)
        auxiliary_rows.append(auxiliary)

    batch = adapter.next_batch()

    assert isinstance(batch, VMCRGBatch)
    assert batch.target_tokens.shape == (2, 1, adapter.token_count)
    np.testing.assert_array_equal(batch.biased_tokens[:, 0], expected_rows)
    q_indices = np.asarray(adapter.encoder.q_token_indices)
    disorder_indices = np.asarray(
        [index for index in range(adapter.token_count) if index not in set(q_indices)]
    )
    np.testing.assert_array_equal(
        batch.target_tokens[..., disorder_indices],
        batch.biased_tokens[..., disorder_indices],
    )
    assert any(
        not np.array_equal(expected[q_indices], auxiliary[q_indices])
        for expected, auxiliary in zip(expected_rows, auxiliary_rows, strict=True)
    )


def test_constructor_rejects_nonshared_bias_and_incompatible_raw_schema() -> None:
    shared = _bias(2026073504)
    first = _raw(_case(2026073505), shared)
    second = _raw(_case(2026073506), shared)
    adapter = JaxVMCRGSamplingBackend(
        j_ids=("J-0", "J-1"),
        backends=(first, second),
        draw_count=1,
        target_temperature_index=1,
        sweeps_per_batch=0,
        seed=2026073507,
    )
    assert isinstance(adapter, VMCRGSamplingBackend)
    assert not isinstance(first, VMCRGSamplingBackend)

    mixed_temperature = _raw(
        _case(2026073508),
        (_bias(2026073509), _bias(2026073510)),
    )
    with pytest.raises(ValueError, match="temperature.*bias signature"):
        JaxVMCRGSamplingBackend(
            j_ids=("J-mixed",),
            backends=(mixed_temperature,),
            draw_count=1,
            target_temperature_index=1,
            sweeps_per_batch=0,
            seed=2026073511,
        )

    different_bias = _raw(_case(2026073512), _bias(2026073513))
    with pytest.raises(ValueError, match="shared bias signature"):
        JaxVMCRGSamplingBackend(
            j_ids=("J-0", "J-1"),
            backends=(first, different_bias),
            draw_count=1,
            target_temperature_index=1,
            sweeps_per_batch=0,
            seed=2026073514,
        )

    different_beta = _raw(_case(2026073515, betas=(0.3, 0.9)), shared)
    with pytest.raises(ValueError, match="beta ladder"):
        JaxVMCRGSamplingBackend(
            j_ids=("J-0", "J-1"),
            backends=(first, different_beta),
            draw_count=1,
            target_temperature_index=1,
            sweeps_per_batch=0,
            seed=2026073516,
        )


@pytest.mark.parametrize("bad_j_ids", ["J", b"J"])
def test_constructor_rejects_bare_string_j_id_sequences(bad_j_ids: object) -> None:
    backend = _raw(_case(2026073522), _bias(2026073523))

    with pytest.raises(TypeError, match="J IDs.*sequence"):
        JaxVMCRGSamplingBackend(
            j_ids=bad_j_ids,
            backends=(backend,),
            draw_count=1,
            target_temperature_index=1,
            sweeps_per_batch=0,
            seed=2026073524,
        )


def test_live_bias_drift_fails_all_surfaces_before_any_sampler_advances() -> None:
    adapter, raw = _adapter(2026073525, sweeps_per_batch=1)
    frozen = adapter.checkpoint_state()
    raw[1].refresh_biases(_bias(2026073526))
    drifted_raw = tuple(backend.checkpoint_state() for backend in raw)
    frozen_rng = copy.deepcopy(adapter._rng.bit_generator.state)
    frozen_counters = (adapter._batches_emitted, adapter._draws_emitted)

    actions = (
        adapter.checkpoint_state,
        adapter.next_batch,
        lambda: adapter.restore_state(frozen),
        adapter.training_rng_state,
        adapter.resource_snapshot,
    )
    for action in actions:
        with pytest.raises(RuntimeError, match="live contract"):
            action()
        assert all(
            _state_equal(backend.checkpoint_state(), expected)
            for backend, expected in zip(raw, drifted_raw, strict=True)
        )
        assert _state_equal(adapter._rng.bit_generator.state, frozen_rng)
        assert (adapter._batches_emitted, adapter._draws_emitted) == frozen_counters


def test_restore_binds_ordered_j_ids_to_immutable_disorder_context() -> None:
    source, _ = _adapter(2026073527, sweeps_per_batch=0)
    checkpoint = source.checkpoint_state()
    target, _ = _adapter(2026073529, sweeps_per_batch=0)
    before = target.checkpoint_state()

    with pytest.raises(ValueError, match="context"):
        target.restore_state(checkpoint)
    assert _state_equal(target.checkpoint_state(), before)

    contexts = tuple(
        entry.get("context_signature") for entry in checkpoint["per_j_states"]
    )
    assert all(isinstance(value, str) and value for value in contexts)
    assert len(set(contexts)) == len(contexts)
    swapped = copy.deepcopy(checkpoint)
    swapped["per_j_states"][0]["context_signature"] = contexts[1]
    swapped["per_j_states"][1]["context_signature"] = contexts[0]
    before = source.checkpoint_state()
    with pytest.raises(ValueError, match="context"):
        source.restore_state(swapped)
    assert _state_equal(source.checkpoint_state(), before)


def test_checkpoint_restore_reproduces_next_complete_batch_trajectory() -> None:
    source, _ = _adapter(2026073517, sweeps_per_batch=1)
    source.next_batch()
    checkpoint = source.checkpoint_state()
    resumed, _ = _adapter(2026073517, sweeps_per_batch=1)
    resumed.restore_state(checkpoint)

    expected = source.next_batch()
    actual = resumed.next_batch()

    np.testing.assert_array_equal(actual.target_tokens, expected.target_tokens)
    np.testing.assert_array_equal(actual.biased_tokens, expected.biased_tokens)
    assert _state_equal(resumed.checkpoint_state(), source.checkpoint_state())


def test_one_j_failure_rolls_back_all_jax_states_and_adapter_rng(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, raw = _adapter(2026073518, sweeps_per_batch=1)
    before = adapter.checkpoint_state()
    original = raw[1].run_sweeps

    def mutate_then_fail(sweeps: int, progress_every=None) -> None:
        original(sweeps, progress_every)
        raise RuntimeError("forced second-J failure")

    monkeypatch.setattr(raw[1], "run_sweeps", mutate_then_fail)
    with pytest.raises(RuntimeError, match="forced second-J failure"):
        adapter.next_batch()
    assert _state_equal(adapter.checkpoint_state(), before)


def test_restore_rejects_corrupt_inventory_rng_signature_and_cache_transactionally() -> None:
    adapter, _ = _adapter(2026073519, sweeps_per_batch=0)
    checkpoint = adapter.checkpoint_state()

    corruptions = []
    missing_j = copy.deepcopy(checkpoint)
    missing_j["per_j_states"] = missing_j["per_j_states"][:-1]
    corruptions.append(missing_j)
    wrong_order = copy.deepcopy(checkpoint)
    wrong_order["per_j_states"] = tuple(reversed(wrong_order["per_j_states"]))
    corruptions.append(wrong_order)
    wrong_target = copy.deepcopy(checkpoint)
    wrong_target["target_temperature_index"] = 0
    corruptions.append(wrong_target)
    wrong_beta = copy.deepcopy(checkpoint)
    wrong_beta["target_beta"] += 0.1
    corruptions.append(wrong_beta)
    wrong_signature = copy.deepcopy(checkpoint)
    wrong_signature["bias_signature"] = "wrong"
    corruptions.append(wrong_signature)
    bad_rng = copy.deepcopy(checkpoint)
    bad_rng["rng_state"]["adapter_rng"] = {"invalid": True}
    corruptions.append(bad_rng)
    stale_cache = copy.deepcopy(checkpoint)
    stale_cache["per_j_states"][0]["state"]["token_codes"][0, 0, 0] ^= 1
    corruptions.append(stale_cache)

    for corrupt in corruptions:
        before = adapter.checkpoint_state()
        with pytest.raises((TypeError, ValueError, RuntimeError)):
            adapter.restore_state(corrupt)
        assert _state_equal(adapter.checkpoint_state(), before)


def test_late_j_restore_failure_does_not_rewind_an_earlier_j() -> None:
    adapter, _ = _adapter(2026073521, sweeps_per_batch=1)
    older = adapter.checkpoint_state()
    adapter.next_batch()
    before = adapter.checkpoint_state()
    corrupt = copy.deepcopy(older)
    corrupt["per_j_states"][1]["state"]["token_codes"][0, 0, 0] ^= 1

    with pytest.raises(RuntimeError, match="stale cache"):
        adapter.restore_state(corrupt)

    assert _state_equal(adapter.checkpoint_state(), before)


def test_per_j_audit_counters_checkpoint_restore_and_resource_are_equal() -> None:
    adapter, raw = _adapter(2026073535, sweeps_per_batch=1)
    adapter.next_batch()
    checkpoint = adapter.checkpoint_state()
    expected = {
        "adapter_sweep_count": 1,
        "retained_biased_draws": 1,
        "generated_target_draws": 1,
    }

    assert tuple(
        entry.get("adapter_counters") for entry in checkpoint["per_j_states"]
    ) == (expected, expected)
    resumed, resumed_raw = _adapter(2026073535, sweeps_per_batch=1)
    resumed.restore_state(checkpoint)
    resources = resumed.resource_snapshot()
    for j_id, backend in zip(resumed.j_ids, resumed_raw, strict=True):
        record = resources["per_j"][j_id]
        assert record["adapter_sweep_count"] == 1
        assert record["retained_biased_draws"] == 1
        assert record["generated_target_draws"] == 1
        assert record["sweep_count"] == backend.sweep_count
        assert record["generation"] == backend.checkpoint_state()["generation"]
        assert record["context_signature"] == backend.context_signature
    assert resources["aggregate_sweeps"] == 2
    assert resources["aggregate_retained_biased_draws"] == 2
    assert resources["aggregate_generated_target_draws"] == 2
    assert resources["aggregate_raw_lifetime_sweeps"] == sum(
        backend.sweep_count for backend in resumed_raw
    )

    resumed.next_batch()
    replayed = resumed.resource_snapshot()
    assert all(
        replayed["per_j"][j_id]["adapter_sweep_count"] == 2
        and replayed["per_j"][j_id]["retained_biased_draws"] == 2
        and replayed["per_j"][j_id]["generated_target_draws"] == 2
        for j_id in resumed.j_ids
    )
    assert all(backend.sweep_count == 2 for backend in resumed_raw)
    assert all(backend.sweep_count == 1 for backend in raw)


def test_resource_snapshot_records_per_j_and_aggregate_training_cost() -> None:
    adapter, raw = _adapter(2026073520, sweeps_per_batch=1)
    adapter.next_batch()

    resources = adapter.resource_snapshot()

    assert resources["backend"] == "jax-vmcrg-sampling-adapter"
    assert resources["target_temperature_index"] == 1
    assert resources["target_beta"] == pytest.approx(0.9)
    assert resources["draw_count"] == 1
    assert resources["draws_emitted"] == 2
    assert resources["aggregate_proposals"] == sum(
        backend.proposed_changes for backend in raw
    )
    assert resources["aggregate_accepted"] == sum(
        backend.accepted_changes for backend in raw
    )
    assert resources["aggregate_sweeps"] == 2
    assert resources["aggregate_retained_biased_draws"] == 2
    assert resources["aggregate_generated_target_draws"] == 2
    assert resources["host_peak_bytes"] > 0
    assert resources["device_peak_bytes"] >= 0
    assert resources["compile_seconds"] >= 0.0
    assert resources["lookup_build_seconds"] >= 0.0
    assert resources["bias_signature"] == adapter.bias_signature
    assert tuple(resources["per_j"]) == adapter.j_ids
    assert all(
        resources["per_j"][j_id]["retained_biased_draws"] == 1
        and resources["per_j"][j_id]["generated_target_draws"] == 1
        for j_id in adapter.j_ids
    )
    assert resources["backend_provenance"] == "JaxBiasedPairBackend"


def test_real_jax_sampling_adapter_tracks_two_successive_trainer_updates(
    tmp_path,
) -> None:
    encoder = TemplateEncoder("cube", conditioned=True, rg_level=1)
    initial = LocalTensorTrain.random(encoder.token_count, 2, seed=2026073540)
    raw_tt = SymmetricLocalTT(
        LocalTensorTrain.from_arrays(initial.save_arrays()),
        encoder,
    )
    trainer_tt = SymmetricLocalTT(
        LocalTensorTrain.from_arrays(initial.save_arrays()),
        encoder,
    )
    raw_bias = OverlapBias(
        BiasRoute.B_CONDITIONED_TT,
        None,
        np.empty(0),
        raw_tt,
    )
    raw = _raw(_case(2026073541), raw_bias)
    adapter = JaxVMCRGSamplingBackend(
        j_ids=("J-0",),
        backends=(raw,),
        draw_count=1,
        target_temperature_index=1,
        sweeps_per_batch=0,
        seed=2026073542,
    )
    context = CheckpointContext(
        beta=adapter.target_beta,
        hashes={"test": "a" * 64},
        j_split={"train": ("J-0",), "validation": (), "test": ()},
        rg_level=1,
    )
    trainer = VMCRGTrainer(
        VMCRGProtocol(
            c1_steps=0,
            c2_steps=2,
            c3_steps=0,
            linear_learning_rate=0.01,
            tt_learning_rate=0.01,
            gradient_clip=0.1,
            canonicalize_every=8,
            momentum=0.0,
        ),
        LinearFeatureBasis.cube_v1(),
        trainer_tt,
        adapter,
        route=BiasRoute.B_CONDITIONED_TT,
        checkpoint_context=context,
        failure_checkpoint_root=tmp_path / "failures",
    )
    initial_signature = adapter.bias_signature

    first = trainer.step()
    first_signature = adapter.bias_signature
    second = trainer.step()

    assert first.stage == second.stage == "B"
    assert first_signature != initial_signature
    assert adapter.bias_signature != first_signature
    assert set(raw.bias_signatures) == {adapter.bias_signature}
    raw.assert_cache_consistent()


def _physical_trainer(tmp_path, seed: int):
    encoder = TemplateEncoder("cube", conditioned=True, rg_level=1)
    initial = LocalTensorTrain.random(encoder.token_count, 2, seed=seed)
    raw_tt = SymmetricLocalTT(
        LocalTensorTrain.from_arrays(initial.save_arrays()),
        encoder,
    )
    trainer_tt = SymmetricLocalTT(
        LocalTensorTrain.from_arrays(initial.save_arrays()),
        encoder,
    )
    raw = _raw(
        _case(seed + 1),
        OverlapBias(
            BiasRoute.B_CONDITIONED_TT,
            None,
            np.empty(0),
            raw_tt,
        ),
    )
    adapter = JaxVMCRGSamplingBackend(
        j_ids=("J-0",),
        backends=(raw,),
        draw_count=1,
        target_temperature_index=1,
        sweeps_per_batch=0,
        seed=seed + 2,
    )
    context = CheckpointContext(
        beta=adapter.target_beta,
        hashes={"test": "b" * 64},
        j_split={"train": ("J-0",), "validation": (), "test": ()},
        rg_level=1,
    )
    trainer = VMCRGTrainer(
        VMCRGProtocol(
            c1_steps=0,
            c2_steps=2,
            c3_steps=0,
            linear_learning_rate=0.01,
            tt_learning_rate=0.01,
            gradient_clip=0.1,
            canonicalize_every=8,
            momentum=0.0,
        ),
        LinearFeatureBasis.cube_v1(),
        trainer_tt,
        adapter,
        route=BiasRoute.B_CONDITIONED_TT,
        checkpoint_context=context,
        failure_checkpoint_root=tmp_path / f"failures-{seed}",
    )
    return trainer, adapter, context


def test_real_jax_trainer_checkpoint_restores_bias_then_next_trajectory(
    tmp_path,
) -> None:
    source, source_adapter, context = _physical_trainer(tmp_path, 2026073550)
    source.step()
    checkpoint = source.checkpoint_from_context()
    resumed, resumed_adapter, resumed_context = _physical_trainer(
        tmp_path,
        2026073550,
    )

    resumed.restore(checkpoint, context=resumed_context)
    expected = source.step()
    actual = resumed.step()

    assert actual.stage == expected.stage == "B"
    assert actual.objective_estimate == pytest.approx(
        expected.objective_estimate,
        abs=0.0,
        rel=0.0,
    )
    assert resumed_adapter.bias_signature == source_adapter.bias_signature
    resumed_state = resumed_adapter.checkpoint_state()
    source_state = source_adapter.checkpoint_state()
    assert _state_equal(resumed_state, source_state)
