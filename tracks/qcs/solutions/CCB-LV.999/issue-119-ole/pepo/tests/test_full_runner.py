import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace

import pytest

from ole_pepo.engine import ProgressRecord


OLE_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = OLE_ROOT.parents[4]
RUNNER_SCRIPT = OLE_ROOT / "scripts" / "run_pepo.py"
ARRAY_SCRIPT = OLE_ROOT / "scripts" / "run_pepo_array_cell.py"
ORACLE_MANIFEST = (
    WORKSPACE_ROOT / "results" / "issue119-pepo-small-oracle" / "manifest.json"
)


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


FULL_RUNNER = _load_script("run_pepo_test", RUNNER_SCRIPT)
ARRAY_RUNNER = _load_script("run_pepo_array_cell_test", ARRAY_SCRIPT)


@pytest.fixture
def valid_oracle(tmp_path: Path) -> Path:
    path = tmp_path / "small-oracle.json"
    path.write_bytes(ORACLE_MANIFEST.read_bytes())
    return path


def _direct_command(output: Path, oracle: Path) -> list[str]:
    return [
        sys.executable,
        str(RUNNER_SCRIPT),
        "--dop",
        "2",
        "--chi-env",
        "16",
        "--delta",
        "0.15",
        "--output",
        str(output),
        "--oracle-manifest",
        str(oracle),
    ]


def _inspect_token(
    module, output: Path, oracle: Path, capsys: pytest.CaptureFixture[str]
) -> str:
    assert module.main(_direct_command(output, oracle)[2:]) == 0
    captured = capsys.readouterr()
    matches = re.findall(
        r"^confirmation_token=([0-9a-f]{16})$", captured.out, re.MULTILINE
    )
    assert len(matches) == 1
    return matches[0]


def test_missing_small_oracle_manifest_is_refused(tmp_path: Path):
    """Breaks if a full-cell plan can proceed without its success certificate."""
    output = tmp_path / "manifest.json"

    completed = subprocess.run(
        _direct_command(output, tmp_path / "absent.json"),
        cwd=WORKSPACE_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "small-oracle" in completed.stderr
    assert not output.exists()


@pytest.mark.parametrize(
    "field",
    [
        pytest.param("qasm_sha256", id="qasm"),
        pytest.param("quimb_commit", id="quimb"),
        pytest.param("core_source_digest", id="core-source"),
    ],
)
def test_stale_small_oracle_provenance_is_refused(
    tmp_path: Path, valid_oracle: Path, field: str
):
    """Breaks if changed input, environment, or numerical core can reuse a stale oracle."""
    document = json.loads(valid_oracle.read_text(encoding="utf-8"))
    document["provenance"][field] = "stale"
    valid_oracle.write_text(json.dumps(document), encoding="utf-8")
    output = tmp_path / "manifest.json"

    completed = subprocess.run(
        _direct_command(output, valid_oracle),
        cwd=WORKSPACE_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert field in completed.stderr
    assert not output.exists()


def test_dry_run_prints_one_token_without_writing_a_manifest(
    tmp_path: Path, valid_oracle: Path
):
    """Breaks if inspection computes a PEPO cell or emits an ambiguous confirmation."""
    output = tmp_path / "manifest.json"

    completed = subprocess.run(
        _direct_command(output, valid_oracle),
        cwd=WORKSPACE_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert len(
        re.findall(
            r"^confirmation_token=[0-9a-f]{16}$",
            completed.stdout,
            re.MULTILINE,
        )
    ) == 1
    assert "dry_run=true" in completed.stdout
    assert not output.exists()
    assert not output.with_suffix(".partial.json").exists()


def test_wrong_confirmation_preserves_existing_output(
    tmp_path: Path, valid_oracle: Path
):
    """Breaks if an unconfirmed execute can replace an existing cell result."""
    output = tmp_path / "manifest.json"
    output.write_bytes(b'{"status":"success","sentinel":true}\n')

    completed = subprocess.run(
        [
            *_direct_command(output, valid_oracle),
            "--execute",
            "--confirm",
            "0" * 16,
        ],
        cwd=WORKSPACE_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert output.read_bytes() == b'{"status":"success","sentinel":true}\n'


def test_execute_revalidates_oracle_before_publishing_cell_state(
    tmp_path: Path, valid_oracle: Path
):
    """Breaks if execution starts from a certificate that became stale after inspection."""
    output = tmp_path / "manifest.json"
    args = FULL_RUNNER._parser().parse_args(
        _direct_command(output, valid_oracle)[2:]
    )
    certificate = json.loads(valid_oracle.read_text(encoding="utf-8"))
    certificate["provenance"]["core_source_digest"] = "stale-after-inspection"
    valid_oracle.write_text(json.dumps(certificate), encoding="utf-8")

    with pytest.raises(ValueError, match="core_source_digest"):
        FULL_RUNNER.execute(
            args,
            "0123456789abcdef",
            lambda *_args, **_kwargs: pytest.fail(
                "numerical boundary reached before oracle revalidation"
            ),
        )

    assert not output.exists()
    assert not output.with_suffix(".partial.json").exists()


def test_successful_injected_run_writes_atomic_progress_and_result(
    tmp_path: Path,
    valid_oracle: Path,
    capsys: pytest.CaptureFixture[str],
):
    """Breaks if a controlled full-cell result loses raw value, diagnostics, or atomic files."""
    output = tmp_path / "cell" / "manifest.json"
    token = _inspect_token(FULL_RUNNER, output, valid_oracle, capsys)

    def controlled_evolution(
        _protocol,
        *,
        progress_callback,
        **_settings,
    ):
        progress_callback(ProgressRecord(1, 201, 3, 2, 1.0e-4, 0.01))
        progress_callback(ProgressRecord(100, 201, 17, 4, 2.0e-4, 0.02))
        progress_callback(ProgressRecord(200, 201, 31, 8, 3.0e-4, 0.03))
        progress_callback(ProgressRecord(201, 201, 32, 8, 4.0e-4, 0.04))
        diagnostics = SimpleNamespace(
            causal_gates=201,
            final_support=tuple(range(32)),
            max_realized_bond=8,
            max_retained_tail_ratio=4.0e-4,
        )
        return complex(0.625, 2.0e-10), diagnostics

    returncode = FULL_RUNNER.main(
        [
            *_direct_command(output, valid_oracle)[2:],
            "--execute",
            "--confirm",
            token,
        ],
        evolution_function=controlled_evolution,
    )

    assert returncode == 0
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["status"] == "success"
    assert manifest["result"]["value_real"] == 0.625
    assert manifest["result"]["value_imag"] == 2.0e-10
    assert manifest["result"]["wall_seconds"] >= 0
    assert manifest["result"]["peak_rss_bytes"] > 0
    assert manifest["diagnostics"] == {
        "causal_gates": 201,
        "final_support_size": 32,
        "max_realized_bond": 8,
        "max_retained_tail_ratio": 4.0e-4,
    }
    assert manifest["provenance"]["qasm_sha256"] == (
        "1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455"
    )
    assert manifest["provenance"]["core_source_digest"] == (
        "4b07886e968661b20424523deb9fb2a3d5deae062392016f6922c74f1ac1e300"
    )
    partial = json.loads(
        output.with_suffix(".partial.json").read_text(encoding="utf-8")
    )
    assert partial["progress"]["processed_causal_gates"] == 201
    assert not output.with_suffix(".json.tmp").exists()
    assert not output.with_suffix(".partial.json.tmp").exists()


@pytest.mark.parametrize(
    ("raw_value", "message"),
    [
        pytest.param(complex(0.5, 1.1e-8), "imaginary", id="imaginary"),
        pytest.param(complex(1.0 + 1.1e-8, 0.0), "physical range", id="range"),
        pytest.param(complex(float("nan"), 0.0), "non-finite", id="finite"),
    ],
)
def test_invalid_raw_result_writes_failure_manifest(
    tmp_path: Path,
    valid_oracle: Path,
    capsys: pytest.CaptureFixture[str],
    raw_value: complex,
    message: str,
):
    """Breaks if an invalid complex contraction is published as a successful cell."""
    output = tmp_path / "manifest.json"
    token = _inspect_token(FULL_RUNNER, output, valid_oracle, capsys)

    def invalid_evolution(_protocol, **_settings):
        diagnostics = SimpleNamespace(
            causal_gates=3,
            final_support=(52, 59, 72),
            max_realized_bond=2,
            max_retained_tail_ratio=None,
        )
        return raw_value, diagnostics

    returncode = FULL_RUNNER.main(
        [
            *_direct_command(output, valid_oracle)[2:],
            "--execute",
            "--confirm",
            token,
        ],
        evolution_function=invalid_evolution,
    )

    assert returncode == 1
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["status"] == "failure"
    assert message in manifest["failure"]["message"]
    assert not output.with_suffix(".json.tmp").exists()


def _run_spec() -> dict:
    return {
        "run_id": "pepo-test",
        "run_dir": "results/issue119-pepo-test",
        "settings": {
            "delta": 0.15,
            "evolution_cutoff": 1.0e-9,
            "contraction_cutoff": 2.0e-9,
            "owner": "run",
        },
        "provenance": {"qasm_sha256": "abc", "campaign": "test"},
        "cells": [
            {
                "cell_id": "cell-0001",
                "params": {"dop": 2, "chi_env": 16},
            },
            {
                "cell_id": "cell-0002",
                "params": {"dop": 4, "chi_env": 32, "delta": 0},
                "settings": {"owner": "cell"},
            },
        ],
    }


def test_inspect_selects_one_based_cell_and_merges_cell_settings(tmp_path: Path):
    """Breaks if selector indexing or per-cell setting precedence changes."""
    spec_path = tmp_path / "run-spec.json"
    spec_path.write_text(json.dumps(_run_spec()), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(ARRAY_SCRIPT),
            "--run-spec",
            str(spec_path),
            "--selector",
            "2",
            "--inspect-only",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert json.loads(completed.stdout) == {
        "cell_id": "cell-0002",
        "params": {"dop": 4, "chi_env": 32, "delta": 0},
        "settings": {
            "delta": 0.15,
            "evolution_cutoff": 1.0e-9,
            "contraction_cutoff": 2.0e-9,
            "owner": "cell",
        },
        "provenance": {"qasm_sha256": "abc", "campaign": "test"},
        "run_dir": "results/issue119-pepo-test",
    }


def test_inspect_uses_run_spec_and_selector_environment_fallbacks(tmp_path: Path):
    """Breaks if a Slurm array cannot select a cell through its environment."""
    spec_path = tmp_path / "run-spec.json"
    spec_path.write_text(json.dumps(_run_spec()), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(ARRAY_SCRIPT), "--inspect-only"],
        env={
            **os.environ,
            "HARNESS_RUN_SPEC": str(spec_path),
            "SLURM_ARRAY_TASK_ID": "1",
        },
        text=True,
        capture_output=True,
        check=True,
    )

    assert json.loads(completed.stdout)["cell_id"] == "cell-0001"


@pytest.mark.parametrize("selector", ["0", "3"])
def test_inspect_refuses_out_of_range_selector(tmp_path: Path, selector: str):
    """Breaks if zero or an absent array cell can be selected."""
    spec_path = tmp_path / "run-spec.json"
    spec_path.write_text(json.dumps(_run_spec()), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(ARRAY_SCRIPT),
            "--run-spec",
            str(spec_path),
            "--selector",
            selector,
            "--inspect-only",
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "outside 1:2" in completed.stderr


def _write_fake_direct_runner(path: Path, *, mismatched: bool = False) -> None:
    mismatch_line = "dop += 1" if mismatched else ""
    path.write_text(
        f"""#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--dop", type=int, required=True)
parser.add_argument("--chi-env", type=int, required=True)
parser.add_argument("--delta", type=float, required=True)
parser.add_argument("--evolution-cutoff", type=float, required=True)
parser.add_argument("--contraction-cutoff", type=float, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--execute", action="store_true")
parser.add_argument("--confirm")
args = parser.parse_args()
if not args.execute:
    print("confirmation_token=0123456789abcdef")
    raise SystemExit(0)
if args.confirm != "0123456789abcdef":
    raise SystemExit(3)
dop = args.dop
{mismatch_line}
document = {{
    "status": "success",
    "protocol": {{
        "dop": dop,
        "chi_env": args.chi_env,
        "delta": args.delta,
        "evolution_cutoff": args.evolution_cutoff,
        "contraction_cutoff": args.contraction_cutoff,
    }},
    "provenance": {{"qasm_sha256": "core-qasm"}},
    "result": {{
        "value_real": 0.75,
        "value_imag": 0.0,
        "wall_seconds": 1.25,
        "peak_rss_bytes": 4096,
    }},
    "diagnostics": {{
        "causal_gates": 123,
        "final_support_size": 17,
        "max_realized_bond": args.dop,
        "max_retained_tail_ratio": 1.0e-6,
    }},
}}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(document), encoding="utf-8")
""",
        encoding="utf-8",
    )


def test_array_run_stores_direct_document_and_atomic_scan_manifest(tmp_path: Path):
    """Breaks if the adapter loses the direct document, output path, or declared payload."""
    payload = ARRAY_RUNNER.selected_payload(_run_spec(), 2)
    fake_runner = tmp_path / "fake-run-pepo.py"
    _write_fake_direct_runner(fake_runner)

    manifest_path = ARRAY_RUNNER.run_cell(
        payload,
        workspace_root=tmp_path,
        python_bin=Path(sys.executable),
        runner=fake_runner,
    )

    cell_dir = (
        tmp_path
        / "results"
        / "issue119-pepo-test"
        / "cells"
        / "cell-0002"
    )
    assert manifest_path == cell_dir / "manifest.json"
    assert (cell_dir / "pepo-result.json").exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "success"
    assert manifest["params"] == payload["params"]
    assert manifest["settings"] == payload["settings"]
    assert manifest["provenance"] == payload["provenance"]
    assert manifest["source_result"] == str(cell_dir / "pepo-result.json")
    assert manifest["result"]["value_real"] == 0.75
    assert not manifest_path.with_suffix(".json.tmp").exists()


def test_array_run_rejects_result_for_a_different_selected_cell(tmp_path: Path):
    """Breaks if the scan manifest accepts direct output for different Dop settings."""
    payload = ARRAY_RUNNER.selected_payload(_run_spec(), 1)
    fake_runner = tmp_path / "fake-run-pepo.py"
    _write_fake_direct_runner(fake_runner, mismatched=True)

    with pytest.raises(ValueError, match="dop"):
        ARRAY_RUNNER.run_cell(
            payload,
            workspace_root=tmp_path,
            python_bin=Path(sys.executable),
            runner=fake_runner,
        )

    manifest_path = (
        tmp_path
        / "results"
        / "issue119-pepo-test"
        / "cells"
        / "cell-0001"
        / "manifest.json"
    )
    assert not manifest_path.exists()
