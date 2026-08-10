from __future__ import annotations

import copy
import hashlib

import numpy as np
import pytest
from flax import serialization
import jax
import jax.numpy as jnp

import challenge15.production_vmc as production_vmc_module
from challenge15.production_vmc import (
    EvaluationContext,
    JaxCompileEventRecorder,
    ProductionVMCConfig,
    acceptance_diagnostics,
    compare_training_lifecycle_metrics,
    coordinate_diagnostics,
    coordinate_execution_document,
    coordinate_evaluation_documents,
    deterministic_microbatch_map,
    deterministic_microbatch_map_with_fallback,
    build_oom_retry_attempt,
    deterministic_execution_block_fallback,
    deserialize_verified_blob,
    pending_training_lifecycle_equivalence,
)
from challenge15.production_schema import TrainingAttempt, payload_sha256


def test_diagnostics_preserve_chain_grouping_instead_of_flattening_walkers():
    rng = np.random.default_rng(302)
    draws = 512
    chain_values = np.empty((4, draws))
    noise = rng.normal(size=chain_values.shape)
    chain_values[:, 0] = noise[:, 0]
    for draw in range(1, draws):
        chain_values[:, draw] = 0.7 * chain_values[:, draw - 1] + noise[:, draw]
    walker_values = np.repeat(chain_values[:, None, :], 3, axis=1)
    walker_values += 0.01 * rng.normal(size=walker_values.shape)

    diagnostics = coordinate_diagnostics(
        walker_values,
        local_acceptance=np.full(4, 0.5),
        rigid_acceptance=np.full(4, 0.4),
        local_width=np.full(4, 0.7),
        rigid_width=np.full(4, 0.6),
    )

    assert len(diagnostics["per_chain"]) == 4
    assert [item["chain"] for item in diagnostics["per_chain"]] == [0, 1, 2, 3]
    assert diagnostics["tau_int"] > 1.0
    assert diagnostics["effective_sample_size"] <= 4 * draws
    flattened = walker_values.reshape(12, draws)
    flattened_chain_means = np.mean(flattened, axis=1)
    assert diagnostics["estimate"] == pytest.approx(np.mean(chain_values), abs=2e-3)
    assert len(flattened_chain_means) == 12


def test_acceptance_uses_exact_total_counts_not_mean_of_rates():
    accepted = np.asarray([[9, 1], [1, 1]], dtype=np.int64)
    proposed = np.asarray([[10, 2], [2, 100]], dtype=np.int64)

    result = acceptance_diagnostics(accepted, proposed)

    assert result["accepted"] == 12
    assert result["proposed"] == 114
    assert result["rate"] == pytest.approx(12 / 114)


def test_evaluation_receipt_is_separate_from_canonical_scientific_shard():
    common = {
        "policy_sha256": "a" * 64,
        "source_manifest_sha256": "b" * 64,
        "runtime_attestations": {"coordinate": {"qdeshell": "c" * 64}},
        "base_configuration_sha256": "d" * 64,
        "particles": 4,
    }
    scientific = {
        **common,
        "seed": 1,
        "rank": 2,
        "generation_sha256": "e" * 64,
        "parameter_sha256": "f" * 64,
        "evaluation_prng_sha256": "1" * 64,
        "sampler_configuration": {},
        "sector_diagnostics": {},
        "paired_gap_diagnostics": {},
        "execution_validation": {
            "selected_layout": {
                "walker_microbatch": 2,
                "determinant_block": None,
                "carrier_block": 2,
                "quadrature_block": 2,
            },
            "metric_equivalence": {
                "canonical_completed": True,
                "bitwise_equal": True,
                "classification": "passed",
            },
        },
        "gate_metrics": {},
    }
    execution = {
        "started_at_utc": "2026-07-29T00:00:00Z",
        "finished_at_utc": "2026-07-29T00:00:01Z",
        "hostname": "node",
        "controller": "qdeshell",
        "device": "cpu",
        "peak_rss_mib": 10.0,
        "compile_seconds": 0.1,
        "compile_events": [
            {"name": "/jax/core/compile/backend_compile_duration", "seconds": 0.1}
        ],
        "compile_event_count": 1,
        "elapsed_seconds": 1.0,
        "cache_counters": {"hits": 2, "misses": 1},
        "selected_layout": {
            "walker_microbatch": 2,
            "determinant_block": None,
            "carrier_block": 2,
            "quadrature_block": 2,
        },
        "metric_equivalence": {
            "canonical_completed": True,
            "bitwise_equal": True,
            "classification": "passed",
        },
    }

    shard_sha = payload_sha256(scientific)
    execution["telemetry_invocation_sha256"] = payload_sha256(
        {
            "stage": "coordinate",
            "shard_sha256": shard_sha,
            "started_at_utc": execution["started_at_utc"],
        }
    )
    shard, receipt = coordinate_evaluation_documents(
        scientific, execution, shard_sha256=shard_sha
    )

    assert shard == scientific
    assert receipt["stage"] == "coordinate"
    assert receipt["identity"] == {"stage": "coordinate", "seed": 1, "rank": 2}
    assert receipt["shard_sha256"] == shard_sha
    for field in execution:
        assert field in receipt
        assert field not in shard
    for field in common:
        assert receipt[field] == common[field]
    with pytest.raises(ValueError, match="SHA256"):
        coordinate_evaluation_documents(
            scientific, execution, shard_sha256="2" * 64
        )


def test_coordinate_execution_uses_precomputed_telemetry_invocation_sha():
    invocation = "a" * 64
    execution = coordinate_execution_document(
        started_at_utc="2026-07-29T00:00:00Z",
        finished_at_utc="2026-07-29T00:00:01Z",
        hostname="node",
        controller="qdeshell",
        device="cpu",
        peak_rss_mib=1.0,
        telemetry={
            "compile_seconds": 0.0,
            "compile_events": [],
            "compile_event_count": 0,
            "elapsed_seconds": 1.0,
            "cache_counters": {"hits": 0, "misses": 0},
        },
        telemetry_invocation_sha256=invocation,
        execution_validation={
            "selected_layout": {
                "walker_microbatch": 2,
                "determinant_block": None,
                "carrier_block": 2,
                "quadrature_block": 2,
            },
            "metric_equivalence": {
                "canonical_completed": True,
                "bitwise_equal": True,
                "classification": "passed",
            },
        },
    )

    assert execution["telemetry_invocation_sha256"] == invocation


def test_microbatch_layout_changes_only_execution_not_order_or_metrics():
    values = np.arange(35, dtype=np.float64).reshape(7, 5)

    def kernel(batch):
        return batch * batch + 3.0 * batch

    whole = deterministic_microbatch_map(values, 7, kernel)
    blocked = deterministic_microbatch_map(values, 2, kernel)
    singleton = deterministic_microbatch_map(values, 1, kernel)

    np.testing.assert_array_equal(blocked, whole)
    np.testing.assert_array_equal(singleton, whole)
    original = copy.deepcopy(values)
    with pytest.raises(MemoryError):
        deterministic_microbatch_map(
            values,
            7,
            lambda _batch: (_ for _ in ()).throw(MemoryError("oom")),
        )
    np.testing.assert_array_equal(values, original)


def test_microbatch_kernel_cannot_mutate_the_fixed_sample_stream():
    values = np.arange(12, dtype=np.float64).reshape(4, 3)
    original = values.copy()

    def mutating_kernel(batch):
        batch[0, 0] = -1
        return batch

    with pytest.raises(ValueError, match="read-only"):
        deterministic_microbatch_map(values, 2, mutating_kernel)
    np.testing.assert_array_equal(values, original)


def test_microbatch_oom_fallback_preserves_order_and_exact_metrics():
    values = np.arange(48, dtype=np.float64).reshape(8, 6)
    attempted = []

    def constrained_kernel(batch):
        attempted.append(len(batch))
        if len(batch) > 2:
            raise MemoryError("synthetic device OOM")
        return batch * batch - batch

    result, used_microbatch = deterministic_microbatch_map_with_fallback(
        values, 8, constrained_kernel
    )

    np.testing.assert_array_equal(result, values * values - values)
    assert attempted[:3] == [8, 4, 2]
    assert used_microbatch == 2


def test_all_execution_blocks_retry_without_changing_identity_or_metric():
    config = ProductionVMCConfig()
    attempts = []

    def constrained(layout):
        attempts.append(
            (layout.walker_microbatch, layout.carrier_block, layout.quadrature_block)
        )
        if max(attempts[-1]) > 8:
            raise MemoryError("synthetic OOM")
        return np.asarray([1.0, 2.0, 3.0])

    result, used, immutable_attempts = deterministic_execution_block_fallback(
        config, constrained
    )

    np.testing.assert_array_equal(result, [1.0, 2.0, 3.0])
    assert used.base_configuration_sha256 == config.base_configuration_sha256
    assert all(
        candidate.base_configuration_sha256 == config.base_configuration_sha256
        for candidate in immutable_attempts
    )
    assert attempts[-1] == (8, 8, 8)


def test_evaluation_oom_requires_full_prng_restart_and_records_layout():
    config = ProductionVMCConfig()
    context = EvaluationContext(config, [], JaxCompileEventRecorder())

    def independent_evaluation(layout):
        stream = np.random.default_rng(42).integers(0, 2**31, size=8)
        if layout.walker_microbatch > 32:
            raise MemoryError("synthetic OOM")
        return stream

    with pytest.raises(RuntimeError, match="initial independent PRNG"):
        deterministic_execution_block_fallback(
            config,
            independent_evaluation,
            evaluation_context=context,
        )
    result, selected, _ = deterministic_execution_block_fallback(
        context.layout,
        independent_evaluation,
        evaluation_context=EvaluationContext(
            context.layout, [], JaxCompileEventRecorder()
        ),
    )

    np.testing.assert_array_equal(
        result, np.random.default_rng(42).integers(0, 2**31, size=8)
    )
    assert selected.walker_microbatch == 32
    assert context.oom_occurred is True
    assert context.attempted_layouts == [config]
    assert not hasattr(production_vmc_module, "_ACTIVE_TRAINING_ATTEMPT")


def test_coordinate_retry_preserves_invocation_timestamp_from_before_recorder(
    monkeypatch,
):
    events = []
    timestamps = []
    result = object()

    class Recorder:
        def __enter__(self):
            events.append("recorder-enter")
            return self

        def __exit__(self, *_exc):
            events.append("recorder-exit")

    def now():
        events.append("timestamp")
        return "2026-07-30T00:00:00Z"

    def attempt(_config, _generation, _destination, *, context):
        timestamps.append(context.started_at_utc)
        if len(timestamps) == 1:
            raise production_vmc_module._EvaluationOomRetry
        return result

    monkeypatch.setattr(production_vmc_module, "JaxCompileEventRecorder", Recorder)
    monkeypatch.setattr(production_vmc_module, "_utc_now", now)
    monkeypatch.setattr(
        production_vmc_module, "_evaluate_coordinates_attempt", attempt
    )

    actual = production_vmc_module.evaluate_coordinates(
        ProductionVMCConfig(), object(), object()
    )

    assert actual is result
    assert events == ["timestamp", "recorder-enter", "recorder-exit"]
    assert timestamps == [
        "2026-07-30T00:00:00Z",
        "2026-07-30T00:00:00Z",
    ]


def test_precheckpoint_oom_retry_preserves_deterministic_root_identity():
    running = TrainingAttempt(
        seed=0,
        rank=1,
        attempt_id="a" * 64,
        owner_sha256="b" * 64,
        extension_sha256="c" * 64,
        started_from_snapshot_sha256=None,
        resource_override=None,
        terminal_snapshot_sha256=None,
        status="running",
    )

    retry = build_oom_retry_attempt(
        running,
        override_path="/approved/override.json",
        override_sha256="d" * 64,
        persisted_snapshot_sha256=None,
    )

    assert retry.started_from_snapshot_sha256 is None
    assert retry.resource_override["payload_sha256"] == "d" * 64


def test_training_lifecycle_equivalence_compares_every_scientific_metric_bitwise():
    config = ProductionVMCConfig()
    retry = ProductionVMCConfig(
        walker_microbatch=32,
        carrier_block=4,
        quadrature_block=32,
    )

    def lifecycle(layout):
        return {
            "prng_stream": b"same-prng",
            "sample_stream": b"same-samples",
            "accumulation": b"same-order",
            "scientific_metrics": {
                "loss": 1.0,
                "energy": [2.0, 3.0],
            },
        }

    equivalent = compare_training_lifecycle_metrics(config, retry, lifecycle)
    assert equivalent["classification"] == "passed"
    assert equivalent["bitwise_equal"] is True

    def changed(layout):
        value = lifecycle(layout)
        if layout == retry:
            value["scientific_metrics"]["energy"][1] = np.nextafter(3.0, 4.0)
        return value

    pending = compare_training_lifecycle_metrics(config, retry, changed)
    assert pending["classification"] == "pending"
    assert pending["bitwise_equal"] is False


def test_training_oom_equivalence_stays_pending_until_canonical_lifecycle_completes():
    canonical = ProductionVMCConfig()
    retry = ProductionVMCConfig(
        walker_microbatch=32,
        carrier_block=4,
        quadrature_block=32,
    )

    equivalence = pending_training_lifecycle_equivalence(canonical, retry)

    assert equivalence["classification"] == "pending"
    assert equivalence["bitwise_equal"] is None
    assert equivalence["canonical_layout"]["walker_microbatch"] == 64
    assert equivalence["selected_layout"]["walker_microbatch"] == 32
    assert equivalence["reference_metrics_sha256"] is None


def test_jax_compile_recorder_sums_actual_compile_events():
    with JaxCompileEventRecorder() as recorder:
        jax.jit(lambda value: value + 1)(jnp.ones(2)).block_until_ready()
    telemetry = recorder.telemetry()

    assert telemetry["compile_seconds"] > 0
    assert telemetry["compile_event_count"] > 0
    assert telemetry["elapsed_seconds"] >= telemetry["compile_seconds"]


def test_verified_blob_rejects_symlink_and_checks_roundtrip_digest(tmp_path):
    value = {"x": np.asarray([1.0, 2.0])}
    encoded = serialization.to_bytes(value)
    digest = hashlib.sha256(encoded).hexdigest()
    blobs = tmp_path / "blobs"
    blobs.mkdir()
    (blobs / digest).write_bytes(encoded)

    restored = deserialize_verified_blob(value, tmp_path, digest)
    np.testing.assert_array_equal(restored["x"], value["x"])

    (blobs / digest).unlink()
    target = tmp_path / "target"
    target.write_bytes(encoded)
    (blobs / digest).symlink_to(target)
    with pytest.raises(ValueError, match="blob"):
        deserialize_verified_blob(value, tmp_path, digest)
