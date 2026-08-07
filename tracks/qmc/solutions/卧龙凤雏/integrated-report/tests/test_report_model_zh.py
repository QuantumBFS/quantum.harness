from analysis.locale import ZH_SECTION_TITLES
from analysis.report_model import CodeBlock, Figure
from analysis.report_model_zh import build_report_zh


def test_chinese_report_has_complete_structure(models, learning_mit):
    report = build_report_zh(models, learning_mit)

    assert tuple(section.title for section in report.sections) == ZH_SECTION_TITLES
    assert report.title == "中心荷的三条验证路径"
    assert "纯净 Ising、Nishimori 无序与弱自对偶 Majorana 动力学" in report.subtitle


def test_chinese_report_preserves_frozen_science(models, learning_mit):
    text = build_report_zh(models, learning_mit).plain_text()

    for value in ("0.498739", "0.499424", "0.456469", "0.444107"):
        assert value in text
    assert "0.522" in text
    assert "0.464" in text
    assert "L = 4, 6, 8, 10, 12, 14" in text
    assert "已完成 L = 16" not in text


def test_chinese_report_is_detailed_and_has_no_placeholders(models, learning_mit):
    text = build_report_zh(models, learning_mit).plain_text()

    assert len(text) >= 18000
    for placeholder in ("TBD", "TODO", "FIXME", "lorem ipsum", "待补充"):
        assert placeholder.lower() not in text.lower()


def test_chinese_report_uses_all_localized_figures(models, learning_mit):
    report = build_report_zh(models, learning_mit)
    figures = [
        block
        for section in report.sections
        for block in section.blocks
        if isinstance(block, Figure)
    ]

    assert len(figures) == 27
    assert all(
        str(figure.source).startswith("generated/zh/")
        or "/plots/zh/" in str(figure.source)
        for figure in figures
    )


def test_code_remains_traceable_to_original_sources(models, learning_mit):
    report = build_report_zh(models, learning_mit)
    code = "\n".join(
        block.code
        for section in report.sections
        for block in section.blocks
        if isinstance(block, CodeBlock)
    )

    assert "for site in 0..L:" in code
    assert "for replica in disorder_replicas:" in code
    assert "Gamma = vacuum_covariance(L)" in code


def test_each_model_chapter_has_full_technical_block_types(models, learning_mit):
    report = build_report_zh(models, learning_mit)

    for slug in ("clean-ising", "nishimori-ising", "weak-self-dual"):
        kinds = {block.kind for block in report.section_for_slug(slug).blocks}
        assert {"equation", "table", "figure", "code", "callout"} <= kinds


def test_chinese_open_research_chapter_is_explicitly_exploratory(
    models, learning_mit
):
    section = build_report_zh(models, learning_mit).section_for_slug(
        "learning-induced-mit"
    )
    text = "\n".join(
        block.text if hasattr(block, "text") else getattr(block, "note", "")
        for block in section.blocks
    )

    assert "探索性" in text
    assert "不发布" in text
    assert "0.24" in build_report_zh(models, learning_mit).plain_text()


def test_chinese_open_research_reports_both_effective_central_charge_estimators(
    models, learning_mit
):
    report = build_report_zh(models, learning_mit)
    section = report.section_for_slug("learning-induced-mit")
    text = report.plain_text()
    figures = [block for block in section.blocks if isinstance(block, Figure)]

    for value in (
        "3.060740",
        "1.571634",
        "4.549845",
        "12.579933",
        "10.727804",
        "14.610337",
    ):
        assert value in text
    assert "纠缠有效中心荷" in text
    assert "Casimir–各向异性有效中心荷" in text
    assert "各向异性不稳定" in text
    assert "估计器不一致" in text
    assert len(figures) == 6
