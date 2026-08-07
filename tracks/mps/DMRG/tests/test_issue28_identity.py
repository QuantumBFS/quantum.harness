from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from scripts.issue28_identity import (
    classify_identity_results,
    identity_seed_records,
    run_identity_certification,
)
from vmcrg_ref.issue28_protocol import load_issue28_protocol
from vmcrg_ref.neural_checkpoint import CheckpointExpectations, load_neural_checkpoint
from vmcrg_ref.neural_energy import D4EvenLocalMLP


PROTOCOL_PATH = Path("config/issue28_easy_v1.json")


def test_identity_formal_has_three_locked_independent_seed_bundles() -> None:
    records = identity_seed_records("formal")
    assert [item["bundle_id"] for item in records] == [
        "identity-formal-1",
        "identity-formal-2",
        "identity-formal-3",
    ]
    streams = [
        (stream["entropy"], tuple(stream["spawn_key"]))
        for record in records
        for stream in record["streams"].values()
    ]
    assert len(streams) == len(set(streams))


def test_identity_gradient_estimator_mismatch_is_correctness_failure() -> None:
    classification, reason = classify_identity_results(
        "formal",
        [
            {
                "scientific_pass": False,
                "gradient_diagnostic": {
                    "diagnosis": "SAMPLER_OR_GRADIENT_ESTIMATOR_MISMATCH"
                },
            }
        ],
    )
    assert classification == "CORRECTNESS_FAILURE"
    assert reason == "N1_GRADIENT_ESTIMATOR_MISMATCH"


def test_identity_smoke_starts_random_and_writes_fail_closed_artifacts(
    tmp_path: Path,
) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    output = tmp_path / "N1"
    report = run_identity_certification(protocol, "smoke", output)

    assert report["stage"] == "N1"
    assert report["initialization"] == "random"
    assert report["supervised_checkpoint"] is None
    assert report["stage_setup"]["block_size"] == 1
    assert report["stage_setup"]["rg_transform"] == "identity"
    assert report["exact_relation"] == "U_next=-V_frozen_and_H_prime_equals_H"
    assert report["formal_seed_count"] == 0
    assert report["classification"] == "SCIENTIFIC_NEGATIVE"
    assert report["reason"] == "SMOKE_STATISTICALLY_INSUFFICIENT"
    assert report["fixed_linear_bias_linf"] == 0.0
    assert report["seed_results"][0]["fixed_linear_bias"] == [0.0] * 13
    assert report["seed_results"][0]["model"] == {
        "architecture": "D4EvenLocalMLP",
        "radius": 3,
        "hidden": 32,
        "feature_mode": "multiscale",
    }
    assert (output / "manifest.json").is_file()
    assert (output / "identity_report.json").is_file()
    assert (output / "identity-smoke" / "checkpoint" / "manifest.json").is_file()

    result = report["seed_results"][0]
    gauge = np.load(output / "identity-smoke" / "gauge_reference.npz")["spins"]
    expected = CheckpointExpectations(
        bundle_id="identity-smoke",
        round_index=1,
        predecessor_manifest_sha256=None,
        protocol_sha256=protocol.protocol_sha256,
        code_sha256=result["code_sha256"],
        operator_basis_sha256=protocol.operator_basis_sha256,
        gauge_reference_sha256=result["gauge_reference_sha256"],
        seed_bundle_sha256=result["seed_bundle_sha256"],
        gauge_spins=gauge,
    )
    checkpoint = load_neural_checkpoint(
        output / "identity-smoke" / "checkpoint",
        expected,
    )
    assert checkpoint.metadata["initialization"] == "random"
    assert checkpoint.model.feature_mode == "multiscale"
    np.testing.assert_array_equal(checkpoint.fixed_linear_bias, np.zeros(13))


def test_identity_output_is_not_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "N1"
    output.mkdir()
    (output / "keep.txt").write_text("keep", encoding="ascii")
    with pytest.raises(FileExistsError, match="overwrite"):
        run_identity_certification(
            load_issue28_protocol(PROTOCOL_PATH),
            "smoke",
            output,
        )
    assert (output / "keep.txt").read_text(encoding="ascii") == "keep"


def test_identity_cli_runs_from_fresh_checkout_without_pythonpath() -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "scripts/issue28_identity.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "随机初始化" in result.stdout


def test_identity_runner_is_available_from_package_root() -> None:
    import vmcrg_ref

    assert vmcrg_ref.run_identity_certification is run_identity_certification
    model = D4EvenLocalMLP.random(3, 32, 1, feature_mode="multiscale")
    assert model.radius == 3
