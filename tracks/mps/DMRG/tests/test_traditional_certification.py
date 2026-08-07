from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from vmcrg_ref.baseline_certification import (
    certify_traditional_baseline,
    traditional_handoff_energy,
    traditional_handoff_from_values,
)
from vmcrg_ref.issue28_protocol import load_issue28_protocol
from vmcrg_ref.multi_optimizer import MultiOperatorOptimizer
from vmcrg_ref.operators import EVEN_SHAPES, OperatorBasis


PROTOCOL = Path("config/issue28_easy_v1.json")


def test_traditional_handoff_uses_negative_frozen_bias() -> None:
    bias = np.array([0.2, -0.1])
    values = np.array([[3.0, 4.0], [-2.0, 5.0]])
    np.testing.assert_allclose(
        traditional_handoff_from_values(bias, values),
        -(values @ bias),
    )


def test_traditional_handoff_energy_matches_explicit_operator_values() -> None:
    basis = OperatorBasis(5, EVEN_SHAPES[:2])
    spins = np.ones((2, 5, 5), dtype=np.int8)
    spins[1, 1, 2] = -1
    bias = np.array([0.2, -0.1])
    expected = -np.array([basis.values(state) @ bias for state in spins])
    np.testing.assert_allclose(
        traditional_handoff_energy(bias, spins, basis),
        expected,
    )


def test_optimizer_record_exports_callback_safe_diagnostics() -> None:
    optimizer = MultiOperatorOptimizer(
        length=9,
        couplings=np.array([0.2, 0.0]),
        shapes=EVEN_SHAPES[:2],
        walkers=4,
        seed=17,
        block_size=3,
        compiled=False,
        parallel_walkers=False,
    )
    callbacks = []
    records = optimizer.run(
        steps=2,
        sweeps_per_step=1,
        learning_rate=1e-4,
        callback=callbacks.append,
    )
    assert callbacks == records
    payload = records[-1].to_dict()
    assert payload["step"] == 1
    assert payload["gradient_norm"] == pytest.approx(
        np.linalg.norm(records[-1].gradient)
    )
    assert payload["elapsed_seconds"] > 0.0
    assert len(payload["acceptance_rates"]) == 4
    assert payload["covariance_condition_number"] >= 1.0
    payload["running_bias"][0] = 99.0
    assert optimizer.running_bias[0] != 99.0


def test_traditional_optimizer_uses_supplied_paired_initial_states() -> None:
    initial = np.ones((2, 9, 9), dtype=np.int8)
    initial[1] *= -1
    optimizer = MultiOperatorOptimizer(
        length=9,
        couplings=np.array([0.2, 0.0]),
        shapes=EVEN_SHAPES[:2],
        walkers=2,
        seed=21,
        block_size=3,
        compiled=False,
        parallel_walkers=False,
        initial_spins=initial,
    )
    np.testing.assert_array_equal(optimizer.samplers[0].lattice.spins, initial[0])
    np.testing.assert_array_equal(optimizer.samplers[1].lattice.spins, initial[1])


def test_b0_rejects_wrong_basis_hash_before_writing(tmp_path: Path) -> None:
    protocol = replace(
        load_issue28_protocol(PROTOCOL),
        operator_basis_sha256="0" * 64,
    )
    output = tmp_path / "b0"
    with pytest.raises(ValueError, match="operator basis hash"):
        certify_traditional_baseline(protocol, output, preset="smoke")
    assert not output.exists()


def test_b0_smoke_writes_complete_fail_closed_artifacts(tmp_path: Path) -> None:
    protocol = load_issue28_protocol(PROTOCOL)
    output = tmp_path / "b0"
    report = certify_traditional_baseline(protocol, output, preset="smoke")
    assert report["classification"] == "SCIENTIFIC_NEGATIVE"
    assert report["reason"] == "SMOKE_STATISTICALLY_INSUFFICIENT"
    assert report["basis_sha256"] == protocol.operator_basis_sha256
    assert len(report["b0_config_sha256"]) == 64
    assert report["local_energy_delta"]["maximum_absolute_error"] <= 1e-10
    assert report["handoff"]["maximum_gauge_centered_residual"] <= 1e-10
    for name in (
        "basis.json",
        "trajectory.npz",
        "convergence.json",
        "frozen_validation.json",
        "local_energy_delta.json",
        "principal_couplings.json",
        "handoff.json",
        "autocorrelation.json",
        "resources.json",
        "manifest.json",
    ):
        assert (output / name).is_file()


def test_b0_refuses_to_overwrite_nonempty_output(tmp_path: Path) -> None:
    output = tmp_path / "b0"
    output.mkdir()
    (output / "keep.txt").write_text("user data", encoding="utf-8")
    with pytest.raises(FileExistsError, match="nonempty"):
        certify_traditional_baseline(
            load_issue28_protocol(PROTOCOL),
            output,
            preset="smoke",
        )
    assert (output / "keep.txt").read_text(encoding="utf-8") == "user data"


def test_b0_rejects_unverified_principal_coupling_anchor(tmp_path: Path) -> None:
    value = json.loads(Path("config/issue28_b0_v1.json").read_text(encoding="ascii"))
    value["principal_coupling_anchor"]["anchor_record_sha256"] = "0" * 64
    changed = tmp_path / "b0.json"
    changed.write_text(json.dumps(value), encoding="ascii")
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="anchor hash"):
        certify_traditional_baseline(
            load_issue28_protocol(PROTOCOL),
            output,
            preset="smoke",
            config_path=changed,
        )
    assert not output.exists()


def test_b0_cli_exposes_frozen_protocol_and_smoke_preset() -> None:
    from scripts.issue28_baseline import build_parser

    args = build_parser().parse_args(
        [
            "--protocol",
            "config/issue28_easy_v1.json",
            "--preset",
            "smoke",
            "--output",
            "/tmp/b0",
        ]
    )
    assert args.preset == "smoke"
    assert args.protocol == Path("config/issue28_easy_v1.json")


def test_b0_cli_runs_from_fresh_checkout_without_pythonpath() -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "scripts/issue28_baseline.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "传统 13 算符" in result.stdout


def test_b0_api_is_available_from_package_root() -> None:
    import vmcrg_ref

    assert vmcrg_ref.certify_traditional_baseline is certify_traditional_baseline
