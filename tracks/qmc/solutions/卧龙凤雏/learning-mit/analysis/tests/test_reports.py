from pathlib import Path

from pypdf import PdfReader

from analysis.html_renderer import render_html
from analysis.pdf_renderer import render_pdf
from analysis.plots import make_plots
from analysis.report_model import build_report
from analysis.verify_outputs import verify_report_pair
from summary_fixture import summary_fixture


def test_bilingual_models_share_numeric_facts_but_localize_all_reader_text(tmp_path: Path):
    summary = summary_fixture()
    english = build_report(summary, "en")
    chinese = build_report(summary, "zh")

    assert english.numeric_facts == chinese.numeric_facts
    assert english.status == chinese.status
    assert english.figure_data_hashes == chinese.figure_data_hashes
    assert english.title != chinese.title
    assert english.sections[0].title != chinese.sections[0].title

    make_plots(summary, "en", tmp_path / "plots/en")
    make_plots(summary, "zh", tmp_path / "plots/zh")
    render_html(english, tmp_path / "report.html")
    render_html(chinese, tmp_path / "report-zh.html")
    render_pdf(english, tmp_path / "report.pdf")
    render_pdf(chinese, tmp_path / "report-zh.pdf")

    chinese_html = (tmp_path / "report-zh.html").read_text(encoding="utf-8")
    for forbidden in ("Contents", "Figure", "Interpretation limit"):
        assert forbidden not in chinese_html
    assert "探索性" in chinese_html
    assert "exploratory" in (tmp_path / "report.html").read_text(encoding="utf-8")
    assert len(PdfReader(tmp_path / "report.pdf").pages) >= 8
    assert len(PdfReader(tmp_path / "report-zh.pdf").pages) >= 8

    verification = verify_report_pair(tmp_path)
    assert verification.passed, verification.errors
