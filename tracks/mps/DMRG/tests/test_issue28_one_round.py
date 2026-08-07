from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

import vmcrg_ref.hybrid_neural as hybrid_neural_module
import vmcrg_ref.one_round as one_round_module
from scripts.issue28_one_round import (
    one_round_seed_bundle,
    run_one_round,
)
from vmcrg_ref.issue28_protocol import load_issue28_protocol
from vmcrg_ref.neural_checkpoint import CheckpointExpectations, load_neural_checkpoint
from vmcrg_ref.neural_energy import D4EvenLocalMLP


PROTOCOL_PATH = Path("config/issue28_easy_v1.json")


def test_one_round_monitor_does_not_build_operator_bases_in_callback(
    monkeypatch,
) -> None:
    bundle = one_round_seed_bundle("smoke")
    monitor = one_round_module._OneRoundMonitor(
        length=21,
        block_size=3,
        coupling=0.436,
        stream=bundle.streams["monitoring"],
        preset="smoke",
    )

    def fail_construction(*args, **kwargs):
        raise AssertionError("operator basis constructed after worker startup")

    monkeypatch.setattr(one_round_module, "OperatorBasis", fail_construction)
    monkeypatch.setattr(hybrid_neural_module, "OperatorBasis", fail_construction)
    model = D4EvenLocalMLP.random(3, 32, 23, feature_mode="multiscale")
    record = hybrid_neural_module.NeuralOptimizationRecord(
        step=0,
        gradient_norm=0.01,
        learning_rate=0.01,
        biased_energy_per_site=0.0,
        target_energy_per_site=0.0,
        biased_nn_per_site=0.0,
        target_nn_per_site=0.0,
        acceptance_rate=1.0,
        unclipped_gradient_norm=0.01,
        clipped_gradient_norm=0.01,
    )

    window = monitor(1, model, record, 0.0)

    assert np.isfinite(window.operator_equivalence)
    assert np.isfinite(window.patch_tv)


def test_one_round_checkpoint_has_exact_zero_linear_branch(tmp_path: Path) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    bundle = one_round_seed_bundle("smoke")
    output = tmp_path / "N2"
    report = run_one_round(protocol, bundle, "smoke", output, workers=2)

    assert report["stage"] == "N2"
    assert report["preset"] == "smoke"
    assert report["manifest"]["round"] == 1
    assert report["manifest"]["bundle_id"] == bundle.bundle_id
    assert report["fixed_linear_bias_linf"] == 0.0
    assert report["fixed_linear_bias"] == [0.0] * 13
    assert len(report["initial_state_sha256"]) == 64
    assert report["classification"] == "SCIENTIFIC_NEGATIVE"
    assert report["reason"] == "SMOKE_STATISTICALLY_INSUFFICIENT"
    assert report["stage_setup"] == {
        "length": 21,
        "coupling": 0.436,
        "block_size": 3,
        "coarse_length": 7,
        "boundary": "periodic",
        "rg_transform": "majority_rule",
    }
    assert report["model"] == {
        "architecture": "D4EvenLocalMLP",
        "radius": 3,
        "hidden": 32,
        "feature_mode": "multiscale",
    }
    assert report["objective"]["estimator"] == "stratified_BAR"
    assert report["objective"]["common_zero_bias_anchor"] is True
    assert report["objective"]["workers_per_bundle"] == 2
    assert report["validation"]["workers_per_bundle"] == 2
    monitoring = json.loads((output / "monitoring.json").read_text(encoding="ascii"))
    assert monitoring["windows"]
    assert all(
        window["patch_tv_statistic"]
        == "excess_vs_independent_uniform_baseline"
        for window in monitoring["windows"]
    )
    assert all("observed_patch_tv" in window for window in monitoring["windows"])
    assert all("target_patch_tv" in window for window in monitoring["windows"])
    assert len(set(report["objective"]["stream_hashes"])) == len(
        report["objective"]["stream_hashes"]
    )
    assert set(report["candidate_26"]) == {"axis5", "generic43"}
    assert report["handoff"]["relation"] == "U_next=-V_frozen"
    assert report["handoff"]["maximum_gauge_centered_residual"] <= 1e-10
    assert report["resources"]["elapsed_seconds"] > 0.0
    assert (output / "manifest.json").is_file()
    assert (output / "checkpoint" / "manifest.json").is_file()

    with np.load(output / "gauge_reference.npz", allow_pickle=False) as archive:
        gauge = archive["spins"]
    checkpoint = load_neural_checkpoint(
        output / "checkpoint",
        CheckpointExpectations(
            bundle_id=bundle.bundle_id,
            round_index=1,
            predecessor_manifest_sha256=None,
            protocol_sha256=protocol.protocol_sha256,
            code_sha256=report["code_sha256"],
            operator_basis_sha256=protocol.operator_basis_sha256,
            gauge_reference_sha256=report["gauge_reference_sha256"],
            seed_bundle_sha256=report["seed_bundle_sha256"],
            gauge_spins=gauge,
        ),
    )
    np.testing.assert_array_equal(checkpoint.fixed_linear_bias, np.zeros(13))


def test_one_round_seed_bundle_has_independent_required_streams() -> None:
    bundle = one_round_seed_bundle("pilot")
    records = [
        (stream.entropy, stream.spawn_key) for stream in bundle.streams.values()
    ]
    assert len(records) == 13
    assert len(records) == len(set(records))


def test_n2_certification_does_not_consume_a_formal_n4_seed() -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    bundle = one_round_seed_bundle("formal")
    assert bundle.bundle_id not in {
        formal_bundle.bundle_id for formal_bundle in protocol.formal_bundles
    }
    assert all(
        stream.entropy not in {
            formal_stream.entropy
            for formal_bundle in protocol.formal_bundles
            for formal_stream in formal_bundle.streams.values()
        }
        for stream in bundle.streams.values()
    )


def test_one_round_refuses_output_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "N2"
    output.mkdir()
    (output / "keep.txt").write_text("keep", encoding="ascii")
    with pytest.raises(FileExistsError, match="overwrite"):
        run_one_round(
            load_issue28_protocol(PROTOCOL_PATH),
            one_round_seed_bundle("smoke"),
            "smoke",
            output,
        )
    assert (output / "keep.txt").read_text(encoding="ascii") == "keep"


def test_one_round_manifest_hashes_every_declared_output(tmp_path: Path) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    output = tmp_path / "N2"
    run_one_round(protocol, one_round_seed_bundle("smoke"), "smoke", output)
    manifest = json.loads((output / "manifest.json").read_text(encoding="ascii"))
    assert manifest["pure_linear_bias"] == [0.0] * 13
    assert "one_round_report.json" in manifest["outputs"]
    assert "objective.json" in manifest["outputs"]
    assert "checkpoint/model.npz" in manifest["outputs"]


def test_one_round_cli_runs_from_fresh_checkout_without_pythonpath() -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "scripts/issue28_one_round.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "单轮纯神经" in result.stdout


def test_one_round_api_is_available_from_package_root() -> None:
    import vmcrg_ref

    assert vmcrg_ref.run_one_round is run_one_round
