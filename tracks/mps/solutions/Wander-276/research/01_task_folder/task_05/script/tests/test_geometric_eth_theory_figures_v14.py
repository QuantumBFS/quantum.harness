"""Contracts for the six source-backed Paper II figures."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from PIL import Image
import pytest


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from make_geometric_eth_theory_figures_v14 import make_all_figures


REPO = Path(__file__).resolve().parents[4]
FIGURE_DIR = REPO / "overleaf_sync/geometric_eth_theory/figures"
MANIFEST_PATH = (
    REPO
    / "01_task_folder/task_05/script/output/geometric_eth_theory_v14/"
    "figure_manifest_v14.json"
)
EXPECTED_STEMS = (
    "figure_1_eth_to_bundle_v14",
    "figure_2_response_algebra_v14",
    "figure_3_covariance_closure_v14",
    "figure_4_topology_statistics_v14",
    "figure_5_bps_comparison_v14",
    "figure_6_effective_channel_test_v14",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pdf_text(path: Path) -> str:
    return subprocess.run(
        ["pdftotext", str(path), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_make_all_figures_contract_and_manifest() -> None:
    manifest = make_all_figures(REPO)

    assert manifest["schema"] == "geometric_eth_theory_figure_manifest_v14"
    assert MANIFEST_PATH.is_file()
    assert json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) == manifest
    assert _sha256(REPO / manifest["generator"]) == manifest["generator_sha256"]
    assert tuple(manifest["figures"]) == EXPECTED_STEMS
    assert [manifest["figures"][stem]["kind"] for stem in EXPECTED_STEMS] == [
        "conceptual",
        "conceptual",
        "conceptual",
        "conceptual",
        "source_audited_comparison",
        "quantitative_data",
    ]
    assert stat.S_IMODE(MANIFEST_PATH.stat().st_mode) == 0o644

    for stem, record in manifest["figures"].items():
        assert record["canonical_width_inches"] == 7.0
        assert record["preview_dpi"] == 300
        assert record["panel_labels"]
        assert record["source_hashes"]
        for recorded, digest in record["source_hashes"].items():
            source = REPO / recorded
            assert source.is_file()
            assert _sha256(source) == digest
        for output_kind in ("pdf", "png"):
            output = REPO / record["outputs"][output_kind]["path"]
            assert output.is_file()
            assert _sha256(output) == record["outputs"][output_kind]["sha256"]
            assert stat.S_IMODE(output.stat().st_mode) == 0o644


def test_exact_width_preview_resolution_and_vector_fonts() -> None:
    assert shutil.which("pdfinfo")
    assert shutil.which("pdffonts")
    assert shutil.which("pdfimages")
    for stem in EXPECTED_STEMS:
        pdf = FIGURE_DIR / f"{stem}.pdf"
        png = FIGURE_DIR / f"{stem}.png"
        info = subprocess.run(
            ["pdfinfo", str(pdf)], check=True, capture_output=True, text=True
        ).stdout
        page_size = next(line for line in info.splitlines() if line.startswith("Page size:"))
        width_points = float(page_size.split()[2])
        assert width_points == 504.0

        fonts = subprocess.run(
            ["pdffonts", str(pdf)], check=True, capture_output=True, text=True
        ).stdout
        assert "Type 3" not in fonts
        font_rows = fonts.splitlines()[2:]
        assert font_rows
        assert all(" yes " in f" {row} " for row in font_rows)

        images = subprocess.run(
            ["pdfimages", "-list", str(pdf)], check=True, capture_output=True, text=True
        ).stdout
        assert len(images.splitlines()) == 2

        with Image.open(png) as preview:
            assert preview.width == 2100
            dpi = preview.info.get("dpi")
            assert dpi is not None
            assert dpi[0] == pytest.approx(300, abs=0.2)
            assert dpi[1] == pytest.approx(300, abs=0.2)


def test_panel_labels_and_scientific_claim_boundaries_are_visible() -> None:
    expected_tokens = {
        1: ("(a)", "(b)", "Spectral ETH", "Projector bundle", "exact degeneracy"),
        2: ("(a)", "(b)", "(c)", "commutant", "necessary, not sufficient"),
        3: ("(a)", "(b)", "(c)", "pseudocovariance", "three Wick pairings"),
        4: ("(a)", "(b)", "U(1)", "SU(D)", "Chern"),
        5: (
            "(a)",
            "chen2026berry",
            "calculation",
            "conjecture",
            "horizonless",
        ),
        6: (
            "(a)",
            "(b)",
            "sealed band",
            "random: FAILED",
            "local control",
            "structured control",
        ),
    }
    for index, stem in enumerate(EXPECTED_STEMS, start=1):
        text = _pdf_text(FIGURE_DIR / f"{stem}.pdf")
        for token in expected_tokens[index]:
            assert token in text


def test_figure_5_uses_only_verified_citation_keys_and_statuses() -> None:
    text = _pdf_text(FIGURE_DIR / "figure_5_bps_comparison_v14.pdf")
    for key in ("chen2026berry", "chen2024bps"):
        assert key in text
    for row in (
        "D1/D5 1/2-BPS",
        "N=4 SYM 1/4-BPS",
        "N=2 super-JT",
        "N=2 SYK",
        "broader black-hole",
        "interpretation",
    ):
        assert row in text
    assert "experiment" not in text.lower()


def test_figure_6_matches_frozen_inference_numbers() -> None:
    inference = json.loads(
        (
            REPO
            / "01_task_folder/task_05/script/output/geometric_eth_theory_v14/"
            "chiral_inference_v14.json"
        ).read_text(encoding="utf-8")
    )
    text = _pdf_text(FIGURE_DIR / "figure_6_effective_channel_test_v14.pdf")
    band = inference["random_primary"]["band"]
    assert f"{band['lower']:.3f}" in text
    assert f"{band['upper']:.3f}" in text
    assert inference["selected_branch"] == "random_channel_failure"
    assert "0/3 random point estimates inside" in text
    assert "95% base-bootstrap CI" in text


def test_generation_is_byte_deterministic() -> None:
    first = make_all_figures(REPO)
    first_hashes = {
        stem: {
            kind: record["outputs"][kind]["sha256"]
            for kind in ("pdf", "png")
        }
        for stem, record in first["figures"].items()
    }
    second = make_all_figures(REPO)
    second_hashes = {
        stem: {
            kind: record["outputs"][kind]["sha256"]
            for kind in ("pdf", "png")
        }
        for stem, record in second["figures"].items()
    }
    assert second_hashes == first_hashes
