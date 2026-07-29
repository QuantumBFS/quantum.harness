import re
import time

from pypdf import PdfReader

from analysis.html_renderer import render_html
from analysis.locale import ZH_LOCALE
from analysis.pdf_renderer import render_pdf
from analysis.report_model import Figure, Paragraph, ReportDocument, Section, Table
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


def test_html_localizes_all_renderer_chrome(repo_root, tmp_path):
    output = render_html(
        _chinese_report(repo_root), tmp_path / "report-zh.html", ZH_LOCALE
    )
    html = output.read_text(encoding="utf-8")

    assert '<html lang="zh-CN">' in html
    assert '<div class="toc-title">目录</div>' in html
    assert "第 01 节" in html
    assert "<strong>图 1.</strong>" in html
    assert "<strong>表 1.</strong>" in html
    assert "解读边界" in html
    assert "Contents" not in html
    assert "Interpretation limit" not in html


def test_pdf_uses_extractable_chinese_text(repo_root, tmp_path):
    output = render_pdf(
        _chinese_report(repo_root), tmp_path / "report-zh.pdf", ZH_LOCALE
    )
    text = "\n".join(page.extract_text() or "" for page in PdfReader(output).pages)

    assert "摘要" in text
    assert "目录" in text
    assert "中文段落用于检查字体和文本提取" in text
    assert "Figure" not in text
    assert "Table" not in text


def _chinese_report(repo_root):
    return ReportDocument(
        title="中心荷的三条验证路径",
        subtitle="中文版渲染测试",
        author="卧龙凤雏团队",
        abstract="本摘要用于检查中文 PDF 字体。",
        sections=(
            Section(
                "执行摘要",
                "executive-summary",
                (
                    Paragraph("中文段落用于检查字体和文本提取。"),
                    Table(
                        "测试参数",
                        ("参数", "含义"),
                        (("L", "圆柱宽度"),),
                        "数据来自冻结结果。",
                    ),
                    Figure(
                        repo_root
                        / "tracks/qmc/results/clean-ising-20260729-120302"
                        / "figures/free_energy_scaling.png",
                        "测试图",
                        "用于检查中文图注。",
                        "本图只检查排版。",
                    ),
                ),
            ),
        ),
    )
