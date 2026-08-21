"""Contract tests for the Paper-I v13 figure package."""

from __future__ import annotations

import subprocess
import sys
import hashlib
from pathlib import Path

import matplotlib.image as mpimg
import pytest

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from make_paper1_evidence_figures_v13 import (
    COPY_SOURCES,
    SOURCE_HASHES,
    _outline_fonts,
    assemble_figures,
)
from make_paper1_protection_mixing_figure_v13 import make_figure


REPO = Path(__file__).resolve().parents[4]


def _pdf_text(path: Path) -> str:
    return subprocess.run(
        ["pdftotext", str(path), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


REGISTRY = {
    "models": {
        "laughlin": {"role": "finite_size_stochastic_geometry"},
        "moore_read": {
            "role": "finite_size_stochastic_geometry",
            "production_complete": False,
        },
        "lattice_susy": {
            "role": "structured_reducible_geometry",
            "production_complete": False,
        },
        "xcube": {"role": "exact_structured_control"},
    },
    "claims": {"asymptotic_geometric_eth": False},
    "source_hashes": {"synthetic_fixture.json": "a" * 64},
}


def test_protection_mixing_figure_contract(tmp_path: Path) -> None:
    pdf = tmp_path / "figure.pdf"
    png = tmp_path / "figure.png"
    manifest = make_figure(REGISTRY, pdf, png)

    assert manifest["panel_labels"] == ["a", "b", "c"]
    assert manifest["dimensions_inches"] == [7.0, 5.6]
    assert manifest["dpi"] == 300
    assert len(manifest["source_hash"]) == 64
    assert manifest["classification"] == {
        "frozen": "xcube_coefficient_reweighting",
        "scalar": "xcube_unitary_transport",
        "structured_reducible": "lattice_susy",
        "stochastic_finite_size": ["moore_read", "laughlin"],
    }
    assert pdf.stat().st_size > 20_000
    assert png.stat().st_size > 100_000

    image = mpimg.imread(png)
    assert image.shape[:2] == (1680, 2100)


def test_positive_asymptotic_claim_is_rejected(tmp_path: Path) -> None:
    registry = {
        **REGISTRY,
        "claims": {"asymptotic_geometric_eth": True},
    }
    try:
        make_figure(registry, tmp_path / "figure.pdf", tmp_path / "figure.png")
    except ValueError as error:
        assert "asymptotic" in str(error).lower()
    else:
        raise AssertionError("a positive asymptotic claim must fail closed")


def test_evidence_figure_assembly_contract(tmp_path: Path) -> None:
    manifest_path = tmp_path / "figure_manifest_v13.json"
    payload = assemble_figures(
        REPO,
        figure_root=tmp_path / "figures",
        preview_root=tmp_path / "previews",
        manifest_path=manifest_path,
    )

    assert list(payload["figures"]) == [str(index) for index in range(1, 8)]
    assert manifest_path.is_file()
    assert payload["figures"]["2"]["mode"] == "vector_text_correction"
    assert payload["figures"]["5"]["mode"] == "recomposed"
    assert payload["figures"]["7"]["mode"] == "recomposed"
    for number, record in payload["figures"].items():
        pdf = REPO / record["outputs"]["pdf"]["path"]
        png = REPO / record["outputs"]["png"]["path"]
        if not pdf.is_file():
            pdf = Path(record["outputs"]["pdf"]["path"])
        if not png.is_file():
            png = Path(record["outputs"]["png"]["path"])
        assert pdf.is_file(), number
        assert png.is_file(), number
        assert record["outputs"]["pdf"]["sha256"]
        assert record["outputs"]["png"]["sha256"]
        assert record["source_hashes"]
        assert record["dimensions_inches"][0] == 7.0
        assert record["dpi"] == 300
        assert record["vector_pdf"] is True
        assert record["caption_data"]
        source_paths = set(record["source_hashes"])
        output_paths = {
            record["outputs"]["pdf"]["path"],
            record["outputs"]["png"]["path"],
        }
        assert source_paths.isdisjoint(output_paths)
        image = mpimg.imread(png)
        assert image.shape[1] == 2100

    figure_2_text = _pdf_text(tmp_path / "figures" / "figure_2_spectral_silence_v13.pdf")
    assert "Ramp universal" not in figure_2_text
    assert "Finite-D ramp agreement, long-range excess" in figure_2_text

    for number, stem in (
        (2, "figure_2_spectral_silence_v13.pdf"),
        (3, "figure_3_geometric_hierarchy_v13.pdf"),
        (4, "figure_4_independent_channels_v13.pdf"),
    ):
        font_report = subprocess.run(
            ["pdffonts", str(tmp_path / "figures" / stem)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert "Type 3" not in font_report, number
        assert not any(
            len(line.split()) >= 5 and line.split()[-5] == "no"
            for line in font_report.splitlines()[2:]
        ), number

    figure_5_text = _pdf_text(tmp_path / "figures" / "figure_5_wick_parent_dependence_v13.pdf")
    figure_5_contract = str(payload["figures"]["5"]["caption_data"])
    assert "complete covariance" not in (figure_5_text + figure_5_contract).lower()
    assert "separable proper-complex" in figure_5_text
    assert "two-pairing" in figure_5_text

    figure_7_text = _pdf_text(tmp_path / "figures" / "figure_7_cross_mechanism_v13.pdf")
    figure_7_contract = str(payload["figures"]["7"]["caption_data"])
    figure_7_audit = figure_7_text + figure_7_contract
    assert "historical two-pairing residual" in figure_7_audit
    assert "reanalysis pending" not in figure_7_audit
    assert "raw three-pairing moment residual (uncentered)" not in figure_7_audit
    assert "finite-rank N6-only" in figure_7_audit
    assert "not resolved" in figure_7_audit
    assert "exact population centering" in figure_7_audit
    assert "centered-whitened complete cumulant" in figure_7_audit
    assert "reverse split is descriptive and not pooled" in figure_7_audit
    assert "Bonferroni family alpha = 0.05; per-case alpha = 0.01" in figure_7_audit
    assert "familywise lower = 0.03916" in figure_7_audit
    assert "asymptotic" not in figure_7_audit.lower()
    assert (
        "01_task_folder/task_05/script/output/paper1_prb_v13/"
        "centered_complete_covariance_v13.json"
        in payload["figures"]["7"]["source_hashes"]
    )


def test_changed_source_hash_is_rejected_before_writes(tmp_path: Path) -> None:
    source = next(iter(SOURCE_HASHES))
    manifest_path = tmp_path / "figure_manifest_v13.json"
    with pytest.raises(RuntimeError, match="source hash mismatch"):
        assemble_figures(
            REPO,
            figure_root=tmp_path / "figures",
            preview_root=tmp_path / "previews",
            manifest_path=manifest_path,
            expected_source_hashes={source: "0" * 64},
        )
    assert not manifest_path.exists()


def test_font_outline_pdf_is_byte_deterministic(tmp_path: Path) -> None:
    source = REPO / COPY_SOURCES["3"]
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"

    _outline_fonts(source, first)
    _outline_fonts(source, second)

    assert _sha256(first) == _sha256(second)
