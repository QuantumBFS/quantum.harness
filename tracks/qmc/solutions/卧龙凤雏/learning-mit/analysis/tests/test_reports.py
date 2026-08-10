from pathlib import Path

from pypdf import PdfReader
from reportlab.platypus import KeepTogether

from analysis.html_renderer import render_html
from analysis.locale import get_locale
from analysis.pdf_renderer import (
    _figure,
    _register_cjk_font,
    _styles,
    render_pdf,
)
from analysis.plots import make_plots
from analysis.report_model import Figure, build_report
from analysis.verify_outputs import verify_report_pair, verify_summary_claim
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
    assert english.numeric_facts["entanglement_c_eff"] == 0.34
    assert english.numeric_facts["casimir_c_eff"] == 0.328
    assert english.numeric_facts["claim_status"] == "candidate"
    assert any(section.slug == "effective-central-charge" for section in english.sections)
    assert any(section.slug == "effective-central-charge" for section in chinese.sections)

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


def test_pdf_keeps_each_figure_with_its_caption_and_interpretation(tmp_path: Path):
    summary = summary_fixture()
    document = build_report(summary, "en")
    make_plots(summary, "en", tmp_path / "plots/en")
    figure = next(
        block
        for section in document.sections
        for block in section.blocks
        if isinstance(block, Figure)
    )

    flowables = _figure(
        figure,
        1,
        tmp_path,
        _styles(_register_cjk_font()),
        get_locale("en").labels,
    )

    assert any(isinstance(flowable, KeepTogether) for flowable in flowables)


def test_inconclusive_report_describes_null_estimates_without_python_none():
    summary = summary_fixture()
    summary["status"] = "xy_reproduced_diii_inconclusive"
    summary["casimir"]["amplitude"] = None
    summary["anisotropy"]["alpha"] = None
    summary["anisotropy"]["alpha_stable"] = False
    summary["central_charge"] = {
        "published": False,
        "value": None,
        "interval": None,
    }

    english = build_report(summary, "en").sections[0].blocks[0].text
    chinese = build_report(summary, "zh").sections[0].blocks[0].text

    assert "None" not in english
    assert "unavailable" in english
    assert "not a universal-constant claim" in english
    assert "不能作为普适常数结论" in chinese
    assert "None" not in chinese


def test_summary_verifier_enforces_candidate_and_exploratory_claim_contracts():
    candidate = summary_fixture()
    assert verify_summary_claim(candidate) == ()

    candidate["entanglement_c_eff"]["widths"] = [8, 12, 16, 24]
    assert "candidate requires at least five widths" in verify_summary_claim(candidate)

    exploratory = summary_fixture()
    exploratory["claim"] = {
        "status": "exploratory",
        "published": False,
        "value": 0.34,
        "interval": [0.30, 0.38],
        "reasons": [],
    }
    assert "exploratory claim requires failed-gate reasons" in verify_summary_claim(
        exploratory
    )
