from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from make_release_manifest_v1 import build_manifest
from verify_release_contract_v1 import verify_manifest


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = SCRIPT_ROOT / "output"
REPO_ROOT = SCRIPT_ROOT.parents[2]
RELEASE_MANIFEST = OUTPUT / "release_manifest_v1.json"


def _production_manifest() -> dict:
    return json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))


def test_release_manifest_captures_public_contract() -> None:
    manifest = build_manifest(
        repo_root=REPO_ROOT,
        bulk_output=OUTPUT,
        generated_utc="2026-07-30T00:00:00+00:00",
    )

    assert manifest["schema_version"] == 1
    assert manifest["release_id"] == "task05-geometric-chaos-v1"
    assert manifest["result_branches"] == {
        "matrix_element": "deformed_geometric_eth",
        "topology": "fixed_chern_deformed_holonomy",
    }
    assert manifest["paper"]["page_count"] == 17
    assert len(manifest["paper"]["sha256"]) == 64
    assert len(manifest["figures"]) == 7
    assert all(len(item["sha256"]) == 64 for item in manifest["figures"])
    assert manifest["verification"]["quick"] == "bash run_quick_verify_v1.sh"
    assert manifest["verification"]["full"] == "bash run_full_recompute_v1.sh"

    report = verify_manifest(RELEASE_MANIFEST, repo_root=REPO_ROOT)
    assert report["passed"]
    assert all(report["checks"].values())


def test_release_verifier_detects_changed_result_label(
    tmp_path: Path,
) -> None:
    manifest = copy.deepcopy(_production_manifest())
    manifest["result_branches"]["matrix_element"] = "full_haar"
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    report = verify_manifest(path, repo_root=REPO_ROOT)
    assert report["passed"] is False
    assert report["checks"]["registered_result_branches"] is False


def test_release_verifier_detects_blob_above_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(_production_manifest()),
        encoding="utf-8",
    )

    monkeypatch.setenv("TASK05_RELEASE_MAX_TRACKED_BYTES", "1")
    report = verify_manifest(path, repo_root=REPO_ROOT)
    assert report["passed"] is False
    assert report["checks"]["tracked_blob_limit"] is False
