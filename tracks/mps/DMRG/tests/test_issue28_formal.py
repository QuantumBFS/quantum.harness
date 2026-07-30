from __future__ import annotations

import json
from pathlib import Path
import shutil

import numpy as np
import pytest

from scripts.issue28_formal import (
    build_formal_bundle_plan,
    classify_formal_root,
    run_formal_bundle,
)
from vmcrg_ref.formal_compute import (
    _atomic_compute_directory,
    execute_formal_bundle,
    finalize_formal_bundle,
    measure_paired_round1_objective,
    measure_three_arm_autocorrelation,
    prepare_formal_bundle_inputs,
    run_traditional_chain,
    train_linear_round,
)
from vmcrg_ref.neural_energy import D4EvenLocalMLP
from vmcrg_ref.issue28_protocol import SeedStream
from vmcrg_ref.artifacts import atomic_write_json, sha256_bytes
from vmcrg_ref.issue28_protocol import load_issue28_protocol
from vmcrg_ref.issue28_workflow import create_stage_manifest
from vmcrg_ref.one_round import _load_run_protocols


PROTOCOL_PATH = Path("config/issue28_easy_v1.json")


def _execution() -> dict:
    pilot = json.loads(Path("config/issue28_pilot_v1.json").read_text(encoding="ascii"))
    return {
        "formal_seed_count": 5,
        "formal_rounds": 5,
        "training": pilot["training"],
        "objective": {
            **pilot["objective"],
            "neural_lambda_ladder": pilot["objective"]["lambda_ladder"],
            "linear_lambda_ladder": pilot["objective"]["lambda_ladder"],
        },
        "resources": {
            "wall_seconds_per_round": 3600,
            "memory_mib": 4096,
            "cpus_per_task": 16,
            "hardware_class": "matched_slurm_partition",
        },
        "autocorrelation": {
            "chains": 8,
            "thermal_sweeps": 1000,
            "measurements": 5000,
            "spacing_sweeps": 1,
            "maximum_lag": 1000,
            "observable": "microscopic_nn_density_times_block_nn_density",
            "estimator": "initial_positive_sequence",
        },
        "postformal_seed_extension_allowed": False,
        "failed_seed_replacement_allowed": False,
    }


def test_formal_arms_share_initial_hash_but_not_rng_stream() -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    plan = build_formal_bundle_plan(protocol, "formal-1", _execution())
    assert len(plan["rounds"]) == 5
    for record in plan["rounds"]:
        arms = record["arms"]
        assert len(
            {
                arms["neural"]["initial_state_sha256"],
                arms["linear"]["initial_state_sha256"],
                arms["unbiased"]["initial_state_sha256"],
            }
        ) == 1
        assert len(
            {
                arms["neural"]["rng_stream_sha256"],
                arms["linear"]["rng_stream_sha256"],
                arms["unbiased"]["rng_stream_sha256"],
            }
        ) == 3
        assert len(
            {
                arms["neural"]["autocorrelation_rng_stream_sha256"],
                arms["linear"]["autocorrelation_rng_stream_sha256"],
                arms["unbiased"]["autocorrelation_rng_stream_sha256"],
            }
        ) == 3
        assert arms["neural"]["sampling_budget"] == arms["linear"][
            "sampling_budget"
        ]
        assert arms["neural"]["threads"] == arms["linear"]["threads"]
        assert arms["neural"]["hardware_class"] == arms["linear"][
            "hardware_class"
        ]
    assert plan["autocorrelation"] == _execution()["autocorrelation"]


def test_local_formal_bundle_requires_explicit_authorization(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="allow_large_local"):
        run_formal_bundle(
            load_issue28_protocol(PROTOCOL_PATH),
            "formal-1",
            tmp_path / "formal-1",
            backend="local",
            resume=False,
            formal_execution=_execution(),
            dry_run=True,
            workers=8,
        )
    assert not (tmp_path / "formal-1").exists()


def test_authorized_local_formal_dry_run_records_worker_budget(tmp_path: Path) -> None:
    output = tmp_path / "formal-1"
    plan = run_formal_bundle(
        load_issue28_protocol(PROTOCOL_PATH),
        "formal-1",
        output,
        backend="local",
        resume=False,
        formal_execution=_execution(),
        dry_run=True,
        allow_large_local=True,
        workers=8,
    )
    assert plan["dry_run"] is True
    assert plan["runtime"]["backend"] == "local"
    assert plan["runtime"]["workers_per_bundle"] == 8
    assert plan["runtime"]["execution_policy"] == "LOCAL_COMPUTE_DEVIATION"
    assert not output.exists()


def test_formal_dry_run_is_nonmutating_and_lists_five_rounds(tmp_path: Path) -> None:
    output = tmp_path / "formal-2"
    report = run_formal_bundle(
        load_issue28_protocol(PROTOCOL_PATH),
        "formal-2",
        output,
        backend="slurm",
        resume=False,
        formal_execution=_execution(),
        dry_run=True,
    )
    assert report["dry_run"] is True
    assert report["bundle_id"] == "formal-2"
    assert len(report["rounds"]) == 5
    assert not output.exists()


def _write_bundle(
    root: Path,
    bundle_id: str,
    classification: str = "EASY_GOAL_SUCCESS",
    objective_classification: str = "IDENTIFIABLE",
) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    bundle_root = root / bundle_id
    bundle_root.mkdir(parents=True)
    result = {
        "bundle_id": bundle_id,
        "rounds_completed": 5,
        "classification": classification,
        "objective_classification": objective_classification,
        "replacement_seed_allowed": False,
        "arms": ["neural", "linear", "unbiased"],
    }
    atomic_write_json(bundle_root / "bundle_result.json", result)
    manifest = create_stage_manifest(
        stage="N4",
        protocol=protocol,
        classification=classification,
        reason="TEST_FORMAL_BUNDLE",
        output_root=bundle_root,
        outputs=("bundle_result.json",),
        correctness_gates={"five_rounds": "PASS"},
        scientific_gates={"objective": objective_classification},
        resources={"backend": "slurm"},
        bundle_id=bundle_id,
        round_index=5,
    )
    manifest["scope"] = "N4_FORMAL_BUNDLE"
    atomic_write_json(bundle_root / "manifest.json", manifest)


def test_missing_formal_seed_is_not_replaced(tmp_path: Path) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    for bundle in protocol.formal_bundles:
        if bundle.bundle_id != "formal-3":
            _write_bundle(tmp_path, bundle.bundle_id)
    result = classify_formal_root(tmp_path, protocol)
    assert result["classification"] == "PROTOCOL_FAILURE"
    assert result["missing_bundles"] == ["formal-3"]
    assert result["replacement_seed_allowed"] is False


def test_unidentifiable_overlap_is_scientific_negative(tmp_path: Path) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    for bundle in protocol.formal_bundles:
        _write_bundle(
            tmp_path,
            bundle.bundle_id,
            classification=(
                "SCIENTIFIC_NEGATIVE"
                if bundle.bundle_id == "formal-4"
                else "EASY_GOAL_SUCCESS"
            ),
            objective_classification=(
                "UNIDENTIFIABLE_OVERLAP"
                if bundle.bundle_id == "formal-4"
                else "IDENTIFIABLE"
            ),
        )
    result = classify_formal_root(tmp_path, protocol)
    assert result["classification"] == "SCIENTIFIC_NEGATIVE"
    assert result["unidentifiable_bundles"] == ["formal-4"]


def test_formal_api_is_available_from_package_root() -> None:
    import vmcrg_ref

    assert vmcrg_ref.run_formal_bundle is run_formal_bundle
    assert vmcrg_ref.classify_formal_root is classify_formal_root


def test_linear_round_uses_paired_initial_state_and_negative_handoff(
    tmp_path: Path,
) -> None:
    initial = np.ones((2, 21, 21), dtype=np.int8)
    initial[1] *= -1
    report = train_linear_round(
        length=21,
        block_size=3,
        couplings=np.array([0.2, *([0.0] * 12)]),
        initial_spins=initial,
        steps=2,
        sweeps_per_step=1,
        learning_rate=1e-4,
        seed=31,
        output=tmp_path / "linear",
        workers=1,
    )
    assert report["steps"] == 2
    assert report["walkers"] == 2
    np.testing.assert_allclose(
        report["next_microscopic_couplings"],
        -np.asarray(report["final_bias"]),
    )
    assert len(report["initial_state_sha256"]) == 64
    np.testing.assert_allclose(
        report["microscopic_couplings"],
        np.array([0.2, *([0.0] * 12)]),
    )
    assert report["resources"]["elapsed_seconds"] > 0.0
    assert report["resources"]["proposals"] > 0
    assert report["resources"]["threads"] == 1
    assert (tmp_path / "linear" / "trajectory.npz").is_file()


def test_traditional_chain_uses_negative_bias_handoff_and_manifest_link(
    tmp_path: Path,
) -> None:
    first = np.random.default_rng(100).choice(
        np.asarray([-1, 1], dtype=np.int8), size=(2, 21, 21)
    )
    second = np.random.default_rng(101).choice(
        np.asarray([-1, 1], dtype=np.int8), size=(2, 21, 21)
    )
    report = run_traditional_chain(
        length=21,
        block_size=3,
        initial_couplings=np.array([0.2, *([0.0] * 12)]),
        initial_spins_by_round={1: first, 2: second},
        updates_by_round={1: 2, 2: 2},
        sweeps_per_update=1,
        learning_rate=1e-4,
        stream=SeedStream(1003, (0,)),
        output=tmp_path / "traditional",
        resume=False,
    )
    assert len(report["rounds"]) == 2
    np.testing.assert_allclose(
        report["rounds"][1]["microscopic_couplings"],
        report["rounds"][0]["next_microscopic_couplings"],
    )
    assert report["rounds"][1]["predecessor_manifest_sha256"] == report[
        "rounds"
    ][0]["manifest_sha256"]
    assert (tmp_path / "traditional" / "round-02" / "round_manifest.json").is_file()


def test_paired_round1_objective_reuses_actual_anchor_configurations(
    tmp_path: Path,
) -> None:
    model = D4EvenLocalMLP.random(1, 3, 40, feature_mode="patch")
    model.weight_out[:] = np.array([0.02, -0.01, 0.005])
    objective = {
        "estimator": "stratified_BAR",
        "neural_lambda_ladder": [0.0, 1.0],
        "linear_lambda_ladder": [0.0, 1.0],
        "chains_per_bridge": 2,
        "thermal_sweeps": 1,
        "measurements": 3,
        "spacing_sweeps": 1,
        "root_tolerance": 1e-12,
        "minimum_bar_overlap": 0.03,
        "minimum_kish_ess_fraction": 0.10,
        "maximum_closure_z": 3.0,
        "jackknife_unit": "independent_chain",
        "common_zero_bias_anchor": True,
        "independent_nonzero_streams": True,
        "unidentifiable_classification": "UNIDENTIFIABLE_OVERLAP",
        "bootstrap_hierarchy": ["seed_bundle", "independent_chain"],
    }
    report = measure_paired_round1_objective(
        length=21,
        block_size=3,
        coupling=0.2,
        neural_model=model,
        linear_bias=np.array([0.03, *([0.0] * 12)]),
        objective=objective,
        anchor_stream=SeedStream(1001, (0,)),
        neural_stream=SeedStream(1001, (1,)),
        linear_stream=SeedStream(1001, (2,)),
        target_stream=SeedStream(1001, (3,)),
        output=tmp_path / "objective",
        workers=1,
    )
    assert report["neural"]["anchor_hash"] == report["linear"]["anchor_hash"]
    assert report["neural"]["anchor_stream_hash"] == report["linear"][
        "anchor_stream_hash"
    ]
    assert set(report["neural"]["nonzero_stream_hashes"]).isdisjoint(
        report["linear"]["nonzero_stream_hashes"]
    )
    assert report["workers_per_bundle"] == 1
    assert (tmp_path / "objective" / "paired_objective.json").is_file()
    parallel = measure_paired_round1_objective(
        length=21,
        block_size=3,
        coupling=0.2,
        neural_model=model,
        linear_bias=np.array([0.03, *([0.0] * 12)]),
        objective=objective,
        anchor_stream=SeedStream(1001, (0,)),
        neural_stream=SeedStream(1001, (1,)),
        linear_stream=SeedStream(1001, (2,)),
        target_stream=SeedStream(1001, (3,)),
        output=tmp_path / "objective-parallel",
        workers=2,
    )
    assert parallel["workers_per_bundle"] == 2
    assert parallel["neural"] == report["neural"]
    assert parallel["linear"] == report["linear"]
    assert parallel["paired"] == report["paired"]
    with np.load(
        tmp_path / "objective" / "paired_objective_samples.npz",
        allow_pickle=False,
    ) as serial_samples, np.load(
        tmp_path / "objective-parallel" / "paired_objective_samples.npz",
        allow_pickle=False,
    ) as parallel_samples:
        assert serial_samples.files == parallel_samples.files
        for name in serial_samples.files:
            np.testing.assert_array_equal(serial_samples[name], parallel_samples[name])


def test_three_arm_autocorrelation_pairs_states_but_separates_rng(
    tmp_path: Path,
) -> None:
    initial = np.random.default_rng(19).choice(
        np.asarray([-1, 1], dtype=np.int8), size=(2, 21, 21)
    )
    model = D4EvenLocalMLP.random(1, 3, 41, feature_mode="patch")
    model.weight_out[:] = np.array([0.01, -0.005, 0.002])
    report = measure_three_arm_autocorrelation(
        length=21,
        block_size=3,
        coupling=0.2,
        neural_model=model,
        linear_bias=np.array([0.02, *([0.0] * 12)]),
        initial_spins=initial,
        stream=SeedStream(1002, (0,)),
        protocol={
            "chains": 2,
            "thermal_sweeps": 1,
            "measurements": 32,
            "spacing_sweeps": 1,
            "maximum_lag": 8,
            "observable": "microscopic_nn_density_times_block_nn_density",
            "estimator": "initial_positive_sequence",
        },
        output=tmp_path / "autocorrelation",
        workers=1,
    )
    assert report["common_initial_state"] is True
    assert len({report[arm]["initial_state_sha256"] for arm in report["arms"]}) == 1
    assert len({report[arm]["rng_stream_sha256"] for arm in report["arms"]}) == 3
    assert all(report[arm]["tau_int_mean"] >= 0.5 for arm in report["arms"])
    assert all(report[arm]["ess_per_second_mean"] > 0.0 for arm in report["arms"])
    assert report["workers_per_bundle"] == 1
    assert (tmp_path / "autocorrelation" / "series.npz").is_file()


def test_formal_resume_rejects_changed_plan_before_compute(tmp_path: Path) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    bundle = protocol.formal_bundles[0]
    plan = build_formal_bundle_plan(protocol, bundle.bundle_id, _execution())
    output = tmp_path / bundle.bundle_id
    output.mkdir()
    atomic_write_json(output / "formal_plan.json", {**plan, "plan_sha256": "0" * 64})
    with pytest.raises(ValueError, match="plan"):
        execute_formal_bundle(
            protocol,
            bundle,
            output,
            _execution(),
            plan,
            resume=True,
        )


def test_finalize_formal_bundle_writes_three_arm_data_and_n4_manifest(
    tmp_path: Path,
) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    bundle = protocol.formal_bundles[0]
    plan = build_formal_bundle_plan(
        protocol,
        bundle.bundle_id,
        _execution(),
        backend="local",
        workers=8,
    )
    root = tmp_path / bundle.bundle_id
    root.mkdir(parents=True)
    atomic_write_json(root / "formal_plan.json", plan)
    for name in ("neural", "linear", "objective", "autocorrelation"):
        (root / name).mkdir()
    neural_rounds = [
        {
            "round": item["round"],
            "initial_state_sha256": item["initial_state_sha256"],
            "fixed_linear_bias_linf": 0.0,
            "classification": "SCIENTIFIC_NEGATIVE",
            "resources": {"elapsed_seconds": 1.0, "peak_rss_kib": 100},
        }
        for item in plan["rounds"]
    ]
    linear_rounds = [
        {
            "round": item["round"],
            "initial_state_sha256": item["initial_state_sha256"],
            "resources": {"elapsed_seconds": 1.0, "peak_rss_kib": 100},
        }
        for item in plan["rounds"]
    ]
    atomic_write_json(
        root / "neural" / "chain_report.json",
        {"requested_rounds": 5, "rounds": neural_rounds},
    )
    atomic_write_json(
        root / "linear" / "chain_report.json",
        {"rounds_completed": 5, "rounds": linear_rounds},
    )
    atomic_write_json(
        root / "objective" / "paired_objective.json",
        {
            "paired": {"classification": "IDENTIFIABLE"},
            "neural": {"anchor_hash": "a" * 64},
            "linear": {"anchor_hash": "a" * 64},
        },
    )
    atomic_write_json(
        root / "autocorrelation" / "autocorrelation.json",
        {
            "arms": ["neural", "linear", "unbiased"],
            "neural": {"tau_int_mean": 2.0, "ess_per_second_mean": 4.0},
            "linear": {"tau_int_mean": 2.1, "ess_per_second_mean": 4.1},
            "unbiased": {"tau_int_mean": 4.0, "ess_per_second_mean": 2.0},
        },
    )
    result = finalize_formal_bundle(
        protocol,
        bundle,
        root,
        plan,
        backend="local",
        workers=8,
    )
    assert result["classification"] == "EASY_GOAL_SUCCESS"
    assert result["rounds_completed"] == 5
    assert result["three_arm"]["tau_neural_over_linear"] < 1.10
    assert result["three_arm"]["ess_neural_over_linear"] > 0.90
    assert result["resources"]["backend"] == "local"
    assert result["resources"]["execution_policy"] == "LOCAL_COMPUTE_DEVIATION"
    assert result["resources"]["workers_per_bundle"] == 8
    assert result["resources"]["host"]["node"]
    assert (root / "three_arm_comparison.json").is_file()
    assert (root / "manifest.json").is_file()
    with pytest.raises(ValueError, match="completed formal dependencies"):
        execute_formal_bundle(
            protocol,
            bundle,
            root,
            _execution(),
            plan,
            resume=True,
        )


def test_prepare_formal_inputs_materializes_every_planned_initial_hash(
    tmp_path: Path,
) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    bundle = protocol.formal_bundles[1]
    execution = _execution()
    plan = build_formal_bundle_plan(protocol, bundle.bundle_id, execution)
    root = tmp_path / bundle.bundle_id
    root.mkdir()
    prepared = prepare_formal_bundle_inputs(
        protocol,
        bundle,
        execution,
        plan,
        root,
        resume=False,
    )
    with np.load(root / "paired_initial_states.npz", allow_pickle=False) as archive:
        for item in plan["rounds"]:
            values = archive[f"round_{item['round']:02d}"]
            assert sha256_bytes(
                np.ascontiguousarray(values).tobytes(order="C")
            ) == item["initial_state_sha256"]
    assert prepared["rounds"] == 5
    runtime = json.loads(
        (root / "formal_runtime_config.json").read_text(encoding="ascii")
    )
    assert runtime["training"] == execution["training"]
    assert runtime["objective"]["lambda_ladder"] == execution["objective"][
        "neural_lambda_ladder"
    ]
    training, objective, objective_protocol = _load_run_protocols(
        "formal",
        root / "formal_runtime_config.json",
        coarse_sites=225,
    )
    assert training.maximum_updates == execution["training"]["maximum_updates"]
    assert objective["lambda_ladder"] == execution["objective"][
        "neural_lambda_ladder"
    ]
    assert objective_protocol.lambda_ladder == tuple(
        execution["objective"]["neural_lambda_ladder"]
    )


def test_prepare_formal_inputs_recovers_from_atomic_prefix(
    tmp_path: Path,
) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    bundle = protocol.formal_bundles[2]
    execution = _execution()
    plan = build_formal_bundle_plan(protocol, bundle.bundle_id, execution)
    source = tmp_path / "source"
    source.mkdir()
    prepare_formal_bundle_inputs(
        protocol, bundle, execution, plan, source, resume=False
    )
    recovered = tmp_path / "recovered"
    recovered.mkdir()
    shutil.copy2(
        source / "paired_initial_states.npz",
        recovered / "paired_initial_states.npz",
    )
    report = prepare_formal_bundle_inputs(
        protocol, bundle, execution, plan, recovered, resume=True
    )
    assert report["rounds"] == 5
    assert (recovered / "formal_runtime_config.json").is_file()
    assert (recovered / "formal_inputs.json").is_file()


def test_atomic_compute_directory_never_publishes_partial_output(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "measurement"

    def fail(staging: Path) -> None:
        (staging / "partial.txt").write_text("partial", encoding="ascii")
        raise RuntimeError("injected interruption")

    with pytest.raises(RuntimeError, match="injected"):
        _atomic_compute_directory(destination, fail)
    assert not destination.exists()
    assert not list(tmp_path.glob(".measurement.staging-*"))
