from analysis.report_model import build_report


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
    "Conclusions",
    "Appendices",
]


def test_report_has_required_sections(models):
    report = build_report(models)

    assert [section.title for section in report.sections] == REQUIRED_TITLES


def test_every_model_has_parameters_equations_errors_figures_and_code(models):
    report = build_report(models)

    for slug in ("clean-ising", "nishimori-ising", "weak-self-dual"):
        section = report.section_for_slug(slug)
        kinds = {block.kind for block in section.blocks}
        assert {"equation", "table", "figure", "code", "callout"} <= kinds


def test_report_contains_source_backed_headline_values(models):
    text = build_report(models).plain_text()

    for value in ("0.498739", "0.499424", "0.456469", "0.444107"):
        assert value in text
    assert "0.522" in text
    assert "ordinary quenched" in text


def test_report_is_detailed_and_has_no_placeholders(models):
    text = build_report(models).plain_text()

    assert len(text.split()) >= 6500
    for placeholder in ("TBD", "TODO", "FIXME", "lorem ipsum"):
        assert placeholder.lower() not in text.lower()
