from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.freeze_issue28_formal_protocol import freeze_formal_protocol
from vmcrg_ref.artifacts import atomic_write_json, sha256_file
from vmcrg_ref.formal_protocol import load_formal_execution_protocol
from vmcrg_ref.issue28_protocol import load_issue28_protocol
from vmcrg_ref.issue28_workflow import create_stage_manifest, current_code_sha256


UMBRELLA = Path("config/issue28_easy_v1.json")


def _pilot_fixture(
    root: Path,
    classification: str,
    *,
    backend: str = "slurm",
    failed_round: int | None = None,
    forge_top_success: bool = False,
) -> Path:
    protocol = load_issue28_protocol(UMBRELLA)
    root.mkdir()
    chain_report = {
        "schema_version": 1,
        "stage": "N3",
        "preset": "pilot",
        "requested_rounds": 5,
        "classification": classification,
        "reason": "TEST_PILOT",
        "rounds_passing_scientific_gates": (
            5 if forge_top_success or failed_round is None else 4
        ),
        "all_round_scientific_gates_pass": (
            forge_top_success or failed_round is None
        ),
        "rounds": [
            {
                "round": index,
                "scientific_gates": {
                    "training": "CONVERGED",
                    "validation": "FAIL" if index == failed_round else "PASS",
                    "objective": "IDENTIFIABLE",
                },
                "resources": {
                    "elapsed_seconds": 120.0 + index,
                    "peak_rss_kib": 524288,
                    "threads": 8,
                },
            }
            for index in range(1, 6)
        ],
        "power": {
            "formal_seed_count": 5,
            "expected_ci_width": 0.03,
            "probability_ci_below_zero": 0.72,
            "postformal_seed_extension_allowed": False,
            "valid_negative_outcome": (
                "direction_correct_but_confidence_interval_misses_frozen_gate"
            ),
        },
        "resources": {
            "total_wall_seconds": 615.0,
            "peak_rss_kib": 524288,
            "output_bytes": 4_000_000,
            "backend": backend,
            "execution_policy": (
                "LOCAL_COMPUTE_DEVIATION" if backend == "local" else "SLURM"
            ),
            "workers_per_bundle": 8,
            "max_parallel_bundles": 2 if backend == "local" else 1,
            "host": (
                {
                    "node": "test-local-host",
                    "logical_cpus": 32,
                    "memory_total_bytes": 32 * 1024**3,
                    "memory_available_bytes": 24 * 1024**3,
                    "workers_per_bundle": 8,
                    "max_parallel_bundles": 2,
                }
                if backend == "local"
                else None
            ),
        },
        "postformal_seed_extension_allowed": False,
    }
    atomic_write_json(root / "chain_report.json", chain_report)
    manifest = create_stage_manifest(
        stage="N3",
        protocol=protocol,
        classification=classification,
        reason="TEST_PILOT",
        output_root=root,
        outputs=("chain_report.json",),
        correctness_gates={"five_rounds": "PASS"},
        scientific_gates={
            "pilot_depth": "PASS",
            "round_science": (
                "PASS" if forge_top_success or failed_round is None else "FAIL"
            ),
            "rounds_passing": (
                5 if forge_top_success or failed_round is None else 4
            ),
            "power": "PASS",
        },
        resources=chain_report["resources"],
        bundle_id="n3-five-round-pilot",
        round_index=5,
        code_sha256=current_code_sha256(),
    )
    manifest["scope"] = "N3_STAGE_ONLY"
    atomic_write_json(root / "manifest.json", manifest)
    return root / "manifest.json"


def test_formal_protocol_cannot_be_frozen_without_passing_pilot(
    tmp_path: Path,
) -> None:
    manifest = _pilot_fixture(tmp_path / "pilot", "SCIENTIFIC_NEGATIVE")
    with pytest.raises(ValueError, match="N3 pilot"):
        freeze_formal_protocol(UMBRELLA, manifest, tmp_path / "formal.json")


def test_formal_protocol_rejects_top_level_success_with_failed_round(
    tmp_path: Path,
) -> None:
    manifest = _pilot_fixture(
        tmp_path / "pilot",
        "EASY_GOAL_SUCCESS",
        failed_round=4,
        forge_top_success=True,
    )
    with pytest.raises(ValueError, match="round 4 scientific gates"):
        freeze_formal_protocol(UMBRELLA, manifest, tmp_path / "formal.json")


def test_formal_protocol_contains_literal_training_objective_resources_and_seeds(
    tmp_path: Path,
) -> None:
    manifest = _pilot_fixture(tmp_path / "pilot", "EASY_GOAL_SUCCESS")
    output = tmp_path / "formal.json"
    value = freeze_formal_protocol(UMBRELLA, manifest, output)
    execution = value["formal_execution"]
    assert execution["locked"] is True
    assert execution["training"]["eta_0"] > 0.0
    assert execution["training"]["maximum_updates"] == 1000
    assert execution["objective"]["neural_lambda_ladder"][0] == 0.0
    assert execution["objective"]["neural_lambda_ladder"][-1] == 1.0
    assert execution["objective"]["common_zero_bias_anchor"] is True
    assert execution["resources"]["wall_seconds_per_round"] >= 60
    assert execution["resources"]["memory_mib"] >= 512
    assert execution["autocorrelation"] == {
        "chains": 8,
        "thermal_sweeps": 1000,
        "measurements": 5000,
        "spacing_sweeps": 1,
        "maximum_lag": 1000,
        "observable": "microscopic_nn_density_times_block_nn_density",
        "estimator": "initial_positive_sequence",
    }
    assert len(value["formal_seed_bundles"]) == 5
    assert execution["postformal_seed_extension_allowed"] is False
    protocol, loaded = load_formal_execution_protocol(output)
    assert protocol.formal_rounds == 5
    assert loaded["pilot_manifest_sha256"] == sha256_file(manifest)


def test_formal_freeze_is_byte_stable_and_refuses_overwrite(tmp_path: Path) -> None:
    manifest = _pilot_fixture(tmp_path / "pilot", "EASY_GOAL_SUCCESS")
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    freeze_formal_protocol(UMBRELLA, manifest, first)
    freeze_formal_protocol(UMBRELLA, manifest, second)
    assert first.read_bytes() == second.read_bytes()
    assert sha256_file(first) == sha256_file(second)
    with pytest.raises(FileExistsError, match="overwrite"):
        freeze_formal_protocol(UMBRELLA, manifest, first)


def test_formal_loader_rejects_changed_pilot_hash(tmp_path: Path) -> None:
    manifest = _pilot_fixture(tmp_path / "pilot", "EASY_GOAL_SUCCESS")
    output = tmp_path / "formal.json"
    freeze_formal_protocol(UMBRELLA, manifest, output)
    value = json.loads(output.read_text(encoding="ascii"))
    value["formal_execution"]["pilot_manifest_sha256"] = "0" * 64
    changed = tmp_path / "changed.json"
    atomic_write_json(changed, value)
    with pytest.raises(ValueError, match="pilot manifest hash"):
        load_formal_execution_protocol(changed)


def test_formal_freeze_preserves_local_deviation_and_concurrency(tmp_path: Path) -> None:
    manifest = _pilot_fixture(
        tmp_path / "pilot",
        "EASY_GOAL_SUCCESS",
        backend="local",
    )
    value = freeze_formal_protocol(UMBRELLA, manifest, tmp_path / "formal.json")
    resources = value["formal_execution"]["resources"]
    assert resources["backend"] == "local"
    assert resources["execution_policy"] == "LOCAL_COMPUTE_DEVIATION"
    assert resources["workers_per_bundle"] == 8
    assert resources["max_parallel_bundles"] == 2
    assert resources["host"]["node"] == "test-local-host"
