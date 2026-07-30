"""Publication-figure contract for the v2 article."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
from pypdf import PdfReader
import pytest

from make_spectral_silence_figures_v2 import run


EXTERNAL_SPECTRAL = (
    Path(__file__).resolve().parents[1]
    / "output"
    / "spectral_silence_v2.npz"
)


def _audit_manifest(manifest_path: Path) -> None:
    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )
    assert len(manifest["figures"]) == 5
    assert manifest["scientific_annotations"] == {
        "energy_raw": 50.0,
        "energy_connected": 0.0,
        "local_g": 0.2,
        "ramp_g": 0.4,
        "number_extent": 1.0,
        "D800_atom_each": 120,
        "D800_connected_plateau": 0.7,
    }
    for figure in manifest["figures"].values():
        pdf = Path(figure["pdf"])
        png = Path(figure["png"])
        assert pdf.is_file() and png.is_file()
        width = (
            float(PdfReader(str(pdf)).pages[0].mediabox.width)
            / 72.0
        )
        assert abs(width - 7.0) < 0.01
        with Image.open(png) as image:
            assert image.width >= 2100
            assert image.info["dpi"][0] >= 299.0
        assert len(figure["pdf_sha256"]) == 64
        assert len(figure["png_sha256"]) == 64


@pytest.mark.skipif(
    not EXTERNAL_SPECTRAL.exists(),
    reason=(
        "activates with production arrays listed in release_manifest_v1.json"
    ),
)
def test_reduced_figure_build(tmp_path):
    result = run(tmp_path)
    assert result["all_checks_pass"]
    _audit_manifest(tmp_path / "figure_manifest_v2.json")
    numbers = (tmp_path / "generated_numbers_v2.tex").read_text(
        encoding="utf-8"
    )
    assert r"\newcommand{\EnergyRawSFF}{50}" in numbers
    assert r"\newcommand{\GeometricLocalOnset}{0.20}" in numbers
    assert r"\newcommand{\GeometricRampOnset}{0.40}" in numbers


def test_registered_figure_package():
    output = Path(__file__).resolve().parents[1] / "output"
    _audit_manifest(output / "figure_manifest_v2.json")
