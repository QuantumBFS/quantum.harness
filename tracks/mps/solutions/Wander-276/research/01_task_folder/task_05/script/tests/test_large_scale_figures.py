from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


def test_registered_figure_package() -> None:
    output = Path(__file__).resolve().parents[1] / "output"
    manifest = json.loads(
        (output / "figure_manifest_v1.json").read_text(encoding="utf-8")
    )
    assert manifest["atom_annotations"] == {
        "D546_each_boundary": 6,
        "D800_each_boundary": 120,
        "D800_total_weight": 0.30,
    }
    assert len(manifest["inputs"]) == 7
    for figure in manifest["figures"].values():
        pdf = Path(figure["pdf"])
        png = Path(figure["png"])
        reader = PdfReader(str(pdf))
        width = float(reader.pages[0].mediabox.width) / 72.0
        assert abs(width - 7.0) < 0.01
        with Image.open(png) as image:
            assert image.width >= 2100
            assert image.info["dpi"][0] >= 299.0
    numbers = (output / "generated_numbers_v1.tex").read_text(
        encoding="utf-8"
    )
    assert r"\newcommand{\LargestRank}{800}" in numbers
    assert r"\newcommand{\LargestAtomMultiplicity}{120}" in numbers
    assert r"\newcommand{\BootstrapReplicates}{10000}" in numbers
