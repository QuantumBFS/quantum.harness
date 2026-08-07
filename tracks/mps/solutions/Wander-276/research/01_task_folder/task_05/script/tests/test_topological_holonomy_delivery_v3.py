"""Publication and fail-closed tests for fixed-Chern holonomy."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from run_topological_holonomy_v3 import OUTPUT_JSON, OUTPUT_NPZ
from verify_topological_holonomy_v3 import (
    AUDIT_JSON,
    FIGURE_MANIFEST,
    FIGURE_PDF,
    FIGURE_PNG,
    audit_topology_payload,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_figure_7_has_registered_dimensions_and_source_hashes() -> None:
    manifest = json.loads(FIGURE_MANIFEST.read_text(encoding="utf-8"))
    figure = manifest["figure_7_topological_holonomy_v3"]
    assert figure["width_inches"] == 7.0
    assert figure["png_width_pixels"] == 2100
    assert figure["source_json_sha256"] == _sha256(OUTPUT_JSON)
    assert figure["source_npz_sha256"] == _sha256(OUTPUT_NPZ)
    assert figure["pdf_sha256"] == _sha256(FIGURE_PDF)
    assert figure["png_sha256"] == _sha256(FIGURE_PNG)
    assert figure["panels"] == [
        "fixed_chern_and_gap",
        "determinant_winding",
        "wilson_gap_ratio",
        "wilson_form_factor",
    ]
    with Image.open(FIGURE_PNG) as image:
        assert image.width == 2100
        assert image.height >= 1450


def test_topology_delivery_audit_passes_all_gates() -> None:
    audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    assert audit["passed"] is True
    assert all(audit["checks"].values())
    assert audit["result_branch"] == "fixed_chern_deformed_holonomy"
    assert audit["registered_sizes"] == [[3, 8, 16], [4, 10, 25]]
    assert audit["registered_meshes"] == [16, 20]


def test_topology_audit_rejects_changed_chern() -> None:
    payload = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
    corrupted = copy.deepcopy(payload)
    corrupted["sizes"][0]["primary_chern_range"][-1] += 1.0
    with pytest.raises(AssertionError):
        audit_topology_payload(corrupted)


def test_topology_audit_rejects_false_cue_branch() -> None:
    payload = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
    corrupted = copy.deepcopy(payload)
    corrupted["result_branch"] = "fixed_chern_chaotic_holonomy"
    with pytest.raises(AssertionError):
        audit_topology_payload(corrupted)
