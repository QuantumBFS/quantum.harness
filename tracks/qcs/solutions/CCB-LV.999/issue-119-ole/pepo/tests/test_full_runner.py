import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from ole_pepo.engine import ProgressRecord


OLE_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = OLE_ROOT.parents[4]
RUNNER_SCRIPT = OLE_ROOT / "scripts" / "run_pepo.py"
ARRAY_SCRIPT = OLE_ROOT / "scripts" / "run_pepo_array_cell.py"


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
    provenance = {
        "qasm_sha256": FULL_RUNNER.EXPECTED_QASM_SHA256,
        "quimb_commit": FULL_RUNNER.PINNED_QUIMB_COMMIT,
        "core_source_digest": FULL_RUNNER.core_source_digest(FULL_RUNNER.OLE_ROOT),
    }
    path = tmp_path / "small-oracle.json"
    path.write_text(
        json.dumps(
            {
                "status": "success",
                "provenance": provenance,
                "validation": {
                    "success": True,
                    "max_absolute_error": 0.0,
                    **provenance,
                },
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def confined_output(tmp_path: Path):
    run_root = (
        WORKSPACE_ROOT
        / "results"
        / f"issue119-pepo-pytest-{tmp_path.name}"
    )
    yield run_root / "manifest.json"
    shutil.rmtree(run_root, ignore_errors=True)


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


def test_missing_small_oracle_manifest_is_refused(
    tmp_path: Path, confined_output: Path
):
    """Breaks if a full-cell plan can proceed without its success certificate."""

    completed = subprocess.run(
        _direct_command(confined_output, tmp_path / "absent.json"),
        cwd=WORKSPACE_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "small-oracle" in completed.stderr
    assert not confined_output.exists()


@pytest.mark.parametrize(
    "field",
    [
        pytest.param("qasm_sha256", id="qasm"),
        pytest.param("quimb_commit", id="quimb"),
        pytest.param("core_source_digest", id="core-source"),
    ],
)
def test_stale_small_oracle_provenance_is_refused(
    valid_oracle: Path, confined_output: Path, field: str
):
    """Breaks if changed input, environment, or numerical core can reuse a stale oracle."""
    document = json.loads(valid_oracle.read_text(encoding="utf-8"))
    document["provenance"][field] = "stale"
    valid_oracle.write_text(json.dumps(document), encoding="utf-8")

    completed = subprocess.run(
        _direct_command(confined_output, valid_oracle),
        cwd=WORKSPACE_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert field in completed.stderr
    assert not confined_output.exists()


def test_dry_run_prints_one_token_without_writing_a_manifest(
    valid_oracle: Path, confined_output: Path
):
    """Breaks if inspection computes a PEPO cell or emits an ambiguous confirmation."""

    completed = subprocess.run(
        _direct_command(confined_output, valid_oracle),
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
    assert not confined_output.exists()
    assert not confined_output.with_suffix(".partial.json").exists()


def test_wrong_confirmation_preserves_existing_output(
    valid_oracle: Path, confined_output: Path
):
    """Breaks if an unconfirmed execute can replace an existing cell result."""
    confined_output.parent.mkdir(parents=True)
    confined_output.write_bytes(b'{"status":"success","sentinel":true}\n')

    completed = subprocess.run(
        [
            *_direct_command(confined_output, valid_oracle),
            "--execute",
            "--confirm",
            "0" * 16,
        ],
        cwd=WORKSPACE_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert confined_output.read_bytes() == b'{"status":"success","sentinel":true}\n'


def test_execute_revalidates_oracle_before_publishing_cell_state(
    valid_oracle: Path, confined_output: Path
):
    """Breaks if execution starts from a certificate that became stale after inspection."""
    args = FULL_RUNNER._parser().parse_args(
        _direct_command(confined_output, valid_oracle)[2:]
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

    assert not confined_output.exists()
    assert not confined_output.with_suffix(".partial.json").exists()


def test_successful_injected_run_writes_atomic_progress_and_result(
    valid_oracle: Path,
    confined_output: Path,
    capsys: pytest.CaptureFixture[str],
):
    """Breaks if a controlled full-cell result loses raw value, diagnostics, or atomic files."""
    output = confined_output.parent / "cell" / "manifest.json"
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
        FULL_RUNNER.core_source_digest(FULL_RUNNER.OLE_ROOT)
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
    valid_oracle: Path,
    confined_output: Path,
    capsys: pytest.CaptureFixture[str],
    raw_value: complex,
    message: str,
):
    """Breaks if an invalid complex contraction is published as a successful cell."""
    output = confined_output
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


@pytest.mark.parametrize(
    "output",
    [
        pytest.param(Path("/tmp/issue119-pepo-escape/manifest.json"), id="absolute"),
        pytest.param(
            Path("results/issue119-pepo-safe/../../escape/manifest.json"),
            id="traversal",
        ),
    ],
)
def test_direct_runner_refuses_output_outside_repo_results_before_writing(
    output: Path,
    valid_oracle: Path,
):
    """Breaks if a direct output path can escape the repo-root PEPO results tree."""
    with pytest.raises(SystemExit):
        FULL_RUNNER.main(_direct_command(output, valid_oracle)[2:])

    assert not output.exists()


@pytest.mark.parametrize(
    "bad_error",
    [
        pytest.param(-1.0e-12, id="negative"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="infinity"),
        pytest.param(True, id="bool"),
    ],
)
def test_direct_runner_refuses_invalid_oracle_error(
    bad_error: object,
    valid_oracle: Path,
    confined_output: Path,
):
    """Breaks if a non-error or non-finite oracle error can certify a full cell."""
    certificate = json.loads(valid_oracle.read_text(encoding="utf-8"))
    certificate["validation"]["max_absolute_error"] = bad_error
    valid_oracle.write_text(json.dumps(certificate), encoding="utf-8")

    with pytest.raises(SystemExit):
        FULL_RUNNER.main(
            _direct_command(confined_output, valid_oracle)[2:]
        )

    assert not confined_output.exists()


@pytest.mark.parametrize("source", ["progress", "final"])
def test_nonfinite_diagnostic_publishes_atomic_failure_manifest(
    source: str,
    valid_oracle: Path,
    confined_output: Path,
    capsys: pytest.CaptureFixture[str],
):
    """Breaks if strict JSON encoding prevents a terminal numerical failure record."""
    token = _inspect_token(FULL_RUNNER, confined_output, valid_oracle, capsys)

    def nonfinite_evolution(
        _protocol,
        *,
        progress_callback,
        **_settings,
    ):
        if source == "progress":
            progress_callback(ProgressRecord(1, 2, 3, 2, float("inf"), 0.01))
        diagnostics = SimpleNamespace(
            causal_gates=2,
            final_support=(52, 59, 72),
            max_realized_bond=2,
            max_retained_tail_ratio=float("nan"),
        )
        return complex(0.5, 0.0), diagnostics

    returncode = FULL_RUNNER.main(
        [
            *_direct_command(confined_output, valid_oracle)[2:],
            "--execute",
            "--confirm",
            token,
        ],
        evolution_function=nonfinite_evolution,
    )

    assert returncode == 1
    manifest = json.loads(confined_output.read_text(encoding="utf-8"))
    assert manifest["status"] == "failure"
    assert "non-finite" in manifest["failure"]["message"]
    assert not confined_output.with_suffix(".json.tmp").exists()


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


@pytest.mark.parametrize(
    "run_dir",
    [
        pytest.param("/tmp/issue119-pepo-escape", id="absolute"),
        pytest.param(
            "results/issue119-pepo-safe/../../escape",
            id="traversal",
        ),
        pytest.param("results/not-a-pepo-run", id="wrong-run-root"),
    ],
)
def test_adapter_refuses_unconfined_run_dir_before_writing(
    tmp_path: Path, run_dir: str
):
    """Breaks if a scan run directory can escape its workspace PEPO results tree."""
    run_spec = _run_spec()
    run_spec["run_dir"] = run_dir

    with pytest.raises(ValueError, match="run_dir"):
        ARRAY_RUNNER.selected_payload(run_spec, 1)

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "cell_id",
    [
        pytest.param("../cell-0001", id="traversal"),
        pytest.param("/tmp/cell-0001", id="absolute"),
        pytest.param("nested/cell-0001", id="nested"),
    ],
)
def test_adapter_refuses_unsafe_cell_id_before_writing(
    tmp_path: Path, cell_id: str
):
    """Breaks if a scan cell identifier is accepted as more than one safe component."""
    run_spec = _run_spec()
    run_spec["cells"][0]["cell_id"] = cell_id

    with pytest.raises(ValueError, match="cell_id"):
        ARRAY_RUNNER.selected_payload(run_spec, 1)

    assert list(tmp_path.iterdir()) == []


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


def _write_marker_runner(path: Path, marker: Path) -> None:
    path.write_text(
        f"""#!/usr/bin/env python3
from pathlib import Path

Path({str(marker)!r}).write_text("invoked", encoding="utf-8")
print("confirmation_token=0123456789abcdef")
""",
        encoding="utf-8",
    )


def test_array_run_rejects_run_root_symlink_before_subprocess(tmp_path: Path):
    """Breaks if a textual PEPO run root can resolve to a different results identity."""
    payload = ARRAY_RUNNER.selected_payload(_run_spec(), 1)
    results_root = tmp_path / "results"
    results_root.mkdir()
    redirected = results_root / "not-a-pepo-run"
    redirected.mkdir()
    (results_root / "issue119-pepo-test").symlink_to(
        redirected,
        target_is_directory=True,
    )
    marker = tmp_path / "runner-invoked"
    fake_runner = tmp_path / "fake-run-pepo.py"
    _write_marker_runner(fake_runner, marker)

    with pytest.raises(ValueError, match="run_dir"):
        ARRAY_RUNNER.run_cell(
            payload,
            workspace_root=tmp_path,
            python_bin=Path(sys.executable),
            runner=fake_runner,
        )

    assert not marker.exists()
    assert list(redirected.iterdir()) == []


def test_array_run_rejects_matching_sibling_run_root_symlink_before_subprocess(
    tmp_path: Path,
):
    """Breaks if one valid PEPO run identity can redirect into a sibling run."""
    run_spec = _run_spec()
    run_spec["run_dir"] = "results/issue119-pepo-A"
    payload = ARRAY_RUNNER.selected_payload(run_spec, 1)
    results_root = tmp_path / "results"
    results_root.mkdir()
    sibling = results_root / "issue119-pepo-B"
    sibling.mkdir()
    (results_root / "issue119-pepo-A").symlink_to(
        sibling,
        target_is_directory=True,
    )
    marker = tmp_path / "runner-invoked"
    fake_runner = tmp_path / "fake-run-pepo.py"
    _write_marker_runner(fake_runner, marker)

    with pytest.raises(ValueError, match="run_dir"):
        ARRAY_RUNNER.run_cell(
            payload,
            workspace_root=tmp_path,
            python_bin=Path(sys.executable),
            runner=fake_runner,
        )

    assert not marker.exists()
    assert list(sibling.iterdir()) == []


def test_array_run_rejects_cells_symlink_escape_before_subprocess(tmp_path: Path):
    """Breaks if a pre-existing cells symlink can redirect a selected cell outside its run."""
    payload = ARRAY_RUNNER.selected_payload(_run_spec(), 1)
    run_root = tmp_path / "results" / "issue119-pepo-test"
    run_root.mkdir(parents=True)
    escaped = tmp_path / "escaped-cells"
    escaped.mkdir()
    (run_root / "cells").symlink_to(escaped, target_is_directory=True)
    marker = tmp_path / "runner-invoked"
    fake_runner = tmp_path / "fake-run-pepo.py"
    _write_marker_runner(fake_runner, marker)

    with pytest.raises(ValueError, match="cell path"):
        ARRAY_RUNNER.run_cell(
            payload,
            workspace_root=tmp_path,
            python_bin=Path(sys.executable),
            runner=fake_runner,
        )

    assert not marker.exists()
    assert list(escaped.iterdir()) == []


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
