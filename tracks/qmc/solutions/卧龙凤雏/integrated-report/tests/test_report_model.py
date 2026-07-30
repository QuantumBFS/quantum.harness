from analysis.report_model import build_report
from analysis.report_model import Figure


REQUIRED_TITLES = [
    "Executive Summary",
    "Conceptual Foundation",
    "Shared Computational Architecture",
    "Clean Ising Model",
    "Nishimori Random-Bond Ising Model",
    "Weak Self-Dual Majorana Network",
    "Cross-Model Comparison",
    "Error and Sensitivity Analysis",
    "Implementation and Reproducibility",
    "Open Research: Learning-Induced Metal-Insulator Transition",
    "Conclusions",
    "Appendices",
]


def test_report_has_required_sections(models, learning_mit):
    report = build_report(models, learning_mit)

    assert [section.title for section in report.sections] == REQUIRED_TITLES


def test_every_model_has_parameters_equations_errors_figures_and_code(models, learning_mit):
    report = build_report(models, learning_mit)

    for slug in ("clean-ising", "nishimori-ising", "weak-self-dual"):
        section = report.section_for_slug(slug)
        kinds = {block.kind for block in section.blocks}
        assert {"equation", "table", "figure", "code", "callout"} <= kinds


def test_report_contains_source_backed_headline_values(models, learning_mit):
    text = build_report(models, learning_mit).plain_text()

    for value in ("0.498739", "0.499424", "0.456469", "0.444107"):
        assert value in text
    assert "0.522" in text
    assert "ordinary quenched" in text


def test_report_is_detailed_and_has_no_placeholders(models, learning_mit):
    text = build_report(models, learning_mit).plain_text()

    assert len(text.split()) >= 6500
    for placeholder in ("TBD", "TODO", "FIXME", "lorem ipsum"):
        assert placeholder.lower() not in text.lower()


def test_open_research_numbers_are_separate_and_exploratory(models, learning_mit):
    report = build_report(models, learning_mit)
    section = report.section_for_slug("learning-induced-mit")
    text = "\n".join(
        block.text if hasattr(block, "text") else getattr(block, "note", "")
        for block in section.blocks
    )

    assert "exploratory" in text.lower()
    assert "0.24" in report.plain_text()
    assert "0.25" in report.plain_text()
    assert "not publish" in text.lower()
    headline = report.section_for_slug("executive-summary").blocks[2]
    assert len(headline.rows) == 3


def test_open_research_reports_both_effective_central_charge_estimators(
    models, learning_mit
):
    report = build_report(models, learning_mit)
    section = report.section_for_slug("learning-induced-mit")
    text = report.plain_text()
    figures = [block for block in section.blocks if isinstance(block, Figure)]

    for value in (
        "3.259733",
        "0.085659",
        "6.433808",
        "11.251995",
        "6.480240",
        "15.865840",
    ):
        assert value in text
    assert "c_eff^S(L)" in text
    assert "c_eff^C = 6 A alpha / pi" in text
    assert "anisotropy_unstable" in text
    assert "estimator_disagreement" in text
    assert len(figures) == 6
