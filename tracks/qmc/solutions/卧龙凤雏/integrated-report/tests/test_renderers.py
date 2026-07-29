import re

from pypdf import PdfReader

from analysis.html_renderer import render_html
from analysis.pdf_renderer import render_pdf


REQUIRED_SECTION_TITLES = (
    "Executive Summary",
    "Conceptual Foundation",
    "Shared Computational Architecture",
    "Clean Ising Model",
    "Nishimori Random-Bond Ising Model",
    "Weak Self-Dual Majorana Network",
    "Cross-Model Comparison",
    "Error and Sensitivity Analysis",
    "Implementation and Reproducibility",
    "Conclusions",
    "Appendices",
)


def test_html_is_offline_self_contained(report, tmp_path):
    output = render_html(report, tmp_path / "report.html")
    html = output.read_text(encoding="utf-8")

    assert "<!doctype html>" in html.lower()
    assert html.count("data:image/png;base64,") >= 20
    assert "http://" not in html and "https://" not in html
    assert all(title in html for title in REQUIRED_SECTION_TITLES)
    assert "0.499424" in html
    assert "0.456469" in html
    assert "0.444107" in html
    assert "<nav" in html
    assert 'class="equation"' in html


def test_html_has_no_local_image_dependencies(report, tmp_path):
    html = render_html(report, tmp_path / "report.html").read_text(encoding="utf-8")
    visible_markup = re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+", "", html)

    assert 'src="figures/' not in html
    assert 'src="generated/' not in html
    assert "TBD" not in visible_markup


def test_pdf_has_expected_length_and_content(report, tmp_path):
    output = render_pdf(report, tmp_path / "report.pdf")
    reader = PdfReader(output)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert 25 <= len(reader.pages) <= 35
    assert all(title in text for title in REQUIRED_SECTION_TITLES)
    assert "0.499424" in text
    assert "0.456469" in text
    assert "0.444107" in text
    assert "TBD" not in text
    assert all(page.mediabox.width > 590 for page in reader.pages)
    assert all(page.mediabox.height > 840 for page in reader.pages)
