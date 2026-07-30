from pathlib import Path

import pytest

from verify_pdf import extract_text, verify_pdf


@pytest.fixture(scope="module")
def compiled_pdf(paper_dir: Path) -> Path:
    path = paper_dir / "paper.pdf"
    if not path.is_file():
        pytest.skip("compile paper.pdf with `make manuscript`")
    return path


def test_pdf_is_prb_shaped_and_complete(compiled_pdf):
    result = verify_pdf(compiled_pdf)

    assert 8 <= result.page_count <= 22
    assert result.page_width_points == pytest.approx(612.0, abs=1.0)
    assert result.page_height_points == pytest.approx(792.0, abs=1.0)
    assert result.figure_xobjects >= 8
    assert result.has_embedded_fonts


def test_pdf_contains_required_scientific_language(compiled_pdf):
    text = " ".join(extract_text(compiled_pdf).split())

    for phrase in (
        "Effective Central Charges",
        "Xu Tian",
        "Huidan Tan",
        "Data Availability",
        "Author Contributions",
        "Exploratory learning-induced",
        "does not constitute a universal-central-charge estimate",
    ):
        assert phrase.lower() in text.lower()


def test_compilation_log_is_clean(paper_dir):
    log = (paper_dir / "paper.log").read_text(encoding="utf-8", errors="replace")

    for forbidden in (
        "LaTeX Warning: There were undefined references",
        "Package natbib Warning: Citation",
        "Overfull \\hbox",
        "Overfull \\vbox",
        "float is stuck",
    ):
        assert forbidden not in log
