import json
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import time

import pytest


OLE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = OLE_ROOT / "scripts/validate_pepo_small.py"


def _inspect() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=OLE_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def _validator_module():
    spec = importlib.util.spec_from_file_location("validate_pepo_small_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inspect_is_repeatable_without_altering_default_manifest():
    """Breaks if inspection changes an existing small-oracle certificate."""
    workspace_root = OLE_ROOT.parents[4]
    manifest_path = workspace_root / "results/issue119-pepo-small-oracle/manifest.json"
    before = manifest_path.read_bytes() if manifest_path.exists() else None

    completed = _inspect()
    repeated = _inspect()

    assert re.search(r"^confirmation_token=[0-9a-f]{16}$", completed.stdout, re.MULTILINE)
    assert repeated.stdout == completed.stdout
    if before is None:
        assert not manifest_path.exists()
    else:
        assert manifest_path.read_bytes() == before


def test_execute_publishes_running_progress_and_isolated_success_artifacts(tmp_path):
    """Breaks if a real oracle run leaves stale success or writes its report outside output_dir."""
    inspected = _inspect()
    token = re.search(r"^confirmation_token=([0-9a-f]{16})$", inspected.stdout, re.MULTILINE)
    assert token is not None

    output_dir = tmp_path / "small-oracle"
    root_report = OLE_ROOT / "PEPO_SMALL_VALIDATION.md"
    root_report_before = root_report.read_bytes() if root_report.exists() else None
    process = subprocess.Popen(
        [
            sys.executable,
            str(SCRIPT),
            "--execute",
            "--confirm",
            token.group(1),
            "--output-dir",
            str(output_dir),
        ],
        cwd=OLE_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    manifest_path = output_dir / "manifest.json"
    observed_running = False
    observed_progress = False
    deadline = time.monotonic() + 60
    while process.poll() is None and time.monotonic() < deadline:
        if manifest_path.exists():
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
            observed_running |= document["status"] == "running"
            observed_progress |= (
                document["status"] == "running"
                and "processed_causal_gates" in document.get("progress", {})
            )
        time.sleep(0.02)
    stdout, stderr = process.communicate(timeout=10)
    assert process.returncode == 0, stderr
    assert "status=success" in stdout
    assert observed_running
    assert observed_progress

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "success"
    assert manifest["validation"]["dense_delta_zero"] == pytest.approx(1.0, abs=1e-10)
    assert manifest["validation"]["pepo_delta_zero"] == pytest.approx(1.0, abs=1e-10)
    assert manifest["validation"]["dense_delta_015"] == pytest.approx(
        manifest["validation"]["pepo_delta_015"], abs=1e-10
    )
    assert set(manifest["validation"]["exact_errors"]) == {"delta_zero", "delta_015"}
    assert manifest["validation"]["max_absolute_error"] <= 1e-10
    assert set(manifest["validation"]["truncated_delta_015"]) == {"1", "2", "4"}
    assert manifest["timings"]["wall_seconds"] > 0
    assert manifest["resources"]["peak_rss_bytes"] > 0
    assert (output_dir / "PEPO_SMALL_VALIDATION.md").exists()
    if root_report_before is None:
        assert not root_report.exists()
    else:
        assert root_report.read_bytes() == root_report_before


def test_wrong_confirmation_preserves_existing_certificate(tmp_path):
    """Breaks if a rejected confirmation can replace a valid certificate."""
    output_dir = tmp_path / "small-oracle"
    output_dir.mkdir()
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_bytes(b'{"status":"success","sentinel":true}\n')

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--execute",
            "--confirm",
            "0" * 16,
            "--output-dir",
            str(output_dir),
        ],
        cwd=OLE_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert manifest_path.read_bytes() == b'{"status":"success","sentinel":true}\n'


def test_validation_failure_is_atomically_published_before_nonzero_exit(tmp_path, monkeypatch):
    """Breaks if a failed validation leaves a stale success certificate available."""
    validator = _validator_module()
    token = validator.confirmation_token(validator._confirmation_document())
    output_dir = tmp_path / "small-oracle"

    def failing_parse(*_args, **_kwargs):
        raise RuntimeError("injected parse failure")

    monkeypatch.setattr(validator, "read_validated_qasm", failing_parse)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--execute",
            "--confirm",
            token,
            "--output-dir",
            str(output_dir),
        ],
    )

    assert validator.main() == 1
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failure"
    assert manifest["failure"]["message"] == "injected parse failure"
    assert manifest["provenance"]["qasm_sha256"] == validator.QASM_SHA256
