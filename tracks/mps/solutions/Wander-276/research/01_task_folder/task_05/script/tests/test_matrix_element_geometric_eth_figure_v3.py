"""Publication-asset tests for the matrix-element Geometric-ETH figure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = SCRIPT_ROOT / "output"
ARTIFACT_JSON = OUTPUT / "matrix_element_geometric_eth_v3.json"
MANIFEST = OUTPUT / "figure_manifest_v3.json"
FIGURE_PNG = OUTPUT / "figure_6_wick_factorization_v3.png"
FIGURE_PDF = OUTPUT / "figure_6_wick_factorization_v3.pdf"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_figure_6_has_registered_dimensions_and_source_hash() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    figure = manifest["figure_6_wick_factorization_v3"]
    assert figure["width_inches"] == 7.0
    assert figure["png_width_pixels"] == 2100
    assert figure["source_sha256"] == _sha256(ARTIFACT_JSON)
    assert figure["pdf_sha256"] == _sha256(FIGURE_PDF)
    assert figure["png_sha256"] == _sha256(FIGURE_PNG)
    with Image.open(FIGURE_PNG) as image:
        assert image.width == 2100
        assert image.height >= 1450


def test_figure_6_manifest_records_result_branch() -> None:
    artifact = json.loads(ARTIFACT_JSON.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    figure = manifest["figure_6_wick_factorization_v3"]
    assert figure["result_branch"] == artifact["result_branch"]
    assert figure["panels"] == [
        "genuine_manybody_sequence",
        "four_channel_residual",
        "non_gaussian_excess",
        "covariance_geometry",
    ]
