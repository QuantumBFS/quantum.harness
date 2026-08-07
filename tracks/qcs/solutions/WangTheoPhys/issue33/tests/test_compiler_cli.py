import json
import os
import subprocess
import sys

import jax
import jax.numpy as jnp

from vqetape.compiler import compile_vqe
from vqetape.spec import CompileRequest, TFIMVQESpec


def test_compile_vqe_selects_valid_executable():
    request = CompileRequest(
        spec=TFIMVQESpec(nqubits=3, depth=2),
        memory_budget_bytes=1024**3,
        expected_vqe_steps=5,
        warm_repeats=1,
    )
    compiled = compile_vqe(request)
    theta = jnp.zeros(request.spec.parameter_shape)
    energy, gradient = compiled.executable(theta)
    jax.block_until_ready((energy, gradient))
    assert energy.shape == ()
    assert gradient.shape == request.spec.parameter_shape
    assert compiled.selected.valid
    assert compiled.selected in compiled.pareto
    assert all(
        candidate.valid
        for candidate in compiled.candidates
        if candidate.failure is None
    )


def test_cli_writes_machine_readable_report(tmp_path):
    report = tmp_path / "report.json"
    environment = dict(os.environ)
    environment["JAX_ENABLE_X64"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "vqetape.cli",
            "--nqubits",
            "3",
            "--depth",
            "2",
            "--memory-budget-gib",
            "1",
            "--expected-steps",
            "5",
            "--warm-repeats",
            "1",
            "--output",
            str(report),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(report.read_text())
    assert payload["selected"]["valid"] is True
    assert (
        payload["measurement_notes"]["peak_rss"]
        == "process peak RSS, not GPU peak memory"
    )


def test_spatial_cli_writes_joint_representation_report(tmp_path):
    report = tmp_path / "spatial-report.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "vqetape.cli",
            "--mode",
            "spatial-transfer",
            "--nqubits",
            "3",
            "--depth",
            "1",
            "--memory-budget-gib",
            "1",
            "--expected-steps",
            "5",
            "--warm-repeats",
            "1",
            "--timeout-seconds",
            "180",
            "--output",
            str(report),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(report.read_text())
    assert payload["reference"]["valid"]
    assert payload["selected"]["config"]["representation"] in {
        "direct_tn",
        "spatial_transfer",
    }
    assert all(item["valid"] for item in payload["candidates"])
    representations = {
        item["config"]["representation"]
        for item in payload["candidates"]
    }
    assert representations == {"direct_tn", "spatial_transfer"}
