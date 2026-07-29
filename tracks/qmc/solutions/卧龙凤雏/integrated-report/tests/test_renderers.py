import re
import time

from pypdf import PdfReader

from analysis.html_renderer import render_html
from analysis.pdf_renderer import render_pdf
from build_report import build


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


def test_pdf_does_not_orphan_major_chapter_headings(report, tmp_path):
    reader = PdfReader(render_pdf(report, tmp_path / "report.pdf"))

    for title in (
        "Clean Ising Model",
        "Nishimori Random-Bond Ising Model",
        "Weak Self-Dual Majorana Network",
        "Appendices",
    ):
        page_text = next(
            page.extract_text() or ""
            for page in reader.pages[1:]
            if title in (page.extract_text() or "")
        )
        following_text = page_text.split(title, 1)[1]
        assert len(following_text.split()) >= 20, title


def test_pdf_code_blocks_preserve_lines_without_html_artifacts(report, tmp_path):
    reader = PdfReader(render_pdf(report, tmp_path / "report.pdf"))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "<br/>" not in text
    assert "for site in 0..L:" in text
    assert "for replica in disorder_replicas:" in text
    assert "Gamma = vacuum_covariance(L)" in text


def test_pdf_rendering_is_byte_deterministic(report, tmp_path):
    first = render_pdf(report, tmp_path / "first.pdf")
    time.sleep(1.1)
    second = render_pdf(report, tmp_path / "second.pdf")

    assert first.read_bytes() == second.read_bytes()


def test_build_writes_stable_outputs(repo_root):
    result = build(repo_root)

    assert result.html == repo_root / "output/html/three-model-central-charge-report.html"
    assert result.pdf == repo_root / "output/pdf/three-model-central-charge-report.pdf"
    assert result.html.exists() and result.pdf.exists()
    assert result.html_verification.passed
    assert result.pdf_verification.passed
