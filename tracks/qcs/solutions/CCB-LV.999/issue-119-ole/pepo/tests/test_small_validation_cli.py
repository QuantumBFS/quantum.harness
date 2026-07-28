import json
from pathlib import Path
import re
import subprocess
import sys

import pytest


OLE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = OLE_ROOT / "scripts/validate_pepo_small.py"


def test_inspect_prints_confirmation_token_without_writing_default_manifest():
    """Breaks if inspection can create a certificate without explicit confirmation."""
    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=OLE_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert re.search(r"^confirmation_token=[0-9a-f]{16}$", completed.stdout, re.MULTILINE)
    workspace_root = OLE_ROOT.parents[4]
    assert not (
        workspace_root / "results/issue119-pepo-small-oracle/manifest.json"
    ).exists()


def test_execute_writes_a_successful_complete_small_oracle_manifest(tmp_path):
    """Breaks if the confirmed seven-site validation omits a measured gate result."""
    inspected = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=OLE_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    token = re.search(r"^confirmation_token=([0-9a-f]{16})$", inspected.stdout, re.MULTILINE)
    assert token is not None

    output_dir = tmp_path / "small-oracle"
    subprocess.run(
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
        capture_output=True,
        check=True,
    )

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
