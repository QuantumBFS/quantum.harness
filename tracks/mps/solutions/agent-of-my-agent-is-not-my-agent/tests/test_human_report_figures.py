from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "build_human_report_figures.py"
PHASE8_ANALYSIS = (
    PROJECT_ROOT
    / "results"
    / "phase8-scaling"
    / "sigma-1.75"
    / "sensitivity-Gamma-ST"
    / "analysis"
    / "analysis.json"
)
PHASE9_ANALYSIS = (
    PROJECT_ROOT
    / "results"
    / "phase9-validation"
    / "sigma1.8-z"
    / "report"
    / "analysis.json"
)


def _load_builder():
    spec = importlib.util.spec_from_file_location("human_report_figures", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_figure3_has_only_panels_a_and_b():
    builder = _load_builder()
    figure = builder.build_figure_3(PHASE8_ANALYSIS)
    try:
        assert len(figure.axes) == 2
        panel_labels = {
            text.get_text()
            for axis in figure.axes
            for text in axis.texts
            if text.get_fontweight() == "bold"
        }
        assert panel_labels == {"A", "B"}
    finally:
        plt.close(figure)


def test_figure4_uses_power_correction_of_z_eff_against_l_eff():
    builder = _load_builder()
    figure = builder.build_figure_4(PHASE9_ANALYSIS)
    try:
        assert len(figure.axes) == 1
        axis = figure.axes[0]
        assert "Effective size" in axis.get_xlabel()
        assert "Effective exponent" in axis.get_ylabel()

        analysis = json.loads(PHASE9_ANALYSIS.read_text())
        power = analysis["gap_scaling"]["correction_sensitivity"]["power"]
        fit_line = next(
            line for line in axis.lines if line.get_label() == "power correction"
        )
        x_values = np.asarray(fit_line.get_xdata(), dtype=float)
        y_values = np.asarray(fit_line.get_ydata(), dtype=float)
        assert np.allclose(
            y_values,
            power["estimate"] + power["coefficient"] / x_values,
        )
        legend_labels = axis.get_legend_handles_labels()[1]
        assert "Shiratani–Todo QMC z=0.93(2)" in legend_labels
        assert not axis.patches
    finally:
        plt.close(figure)


def test_table3_uses_published_sigma18_uncertainties():
    report = (PROJECT_ROOT / "report_Human" / "main.md").read_text()
    assert "0.93(2) / 1.00(3)" in report


def test_human_report_uses_feasibility_title_and_no_figure5():
    report = (PROJECT_ROOT / "report_Human" / "main.md").read_text()
    expected_title = (
        "# Feasibility Validation of Exploring Universality-Class Crossover "
        "in the Long-Range Transverse-Field Ising Model Using DMRG"
    )
    assert expected_title in " ".join(report.split())
    assert "Figure 5" not in report
    assert "figure-05-numerical-uncertainty.png" not in report
    assert not (
        PROJECT_ROOT
        / "report_Human"
        / "figures"
        / "figure-05-numerical-uncertainty.png"
    ).exists()


def test_table4_is_compact_and_uses_largest_l_mps_shift():
    report = (PROJECT_ROOT / "report_Human" / "main.md").read_text()
    table4 = report.split("| Source | Controlled comparison", maxsplit=1)[1]
    table4 = table4.split("**Table 4.**", maxsplit=1)[0]
    assert "MPS truncation" in table4
    assert "L=128" in table4
    assert "4.53×10⁻⁷" in table4
    assert "Local MPS truncation" not in table4
    assert "Large-L excited-state refinement" not in table4
    assert "Finite-size correction coordinate" not in table4


def test_human_report_records_local_resource_evidence():
    report = (PROJECT_ROOT / "report_Human" / "main.md").read_text()
    normalized = " ".join(report.split())
    assert "32 GB personal computer" in normalized
    assert "normally below 16 GB" in normalized
    assert "1.3 GiB" in normalized
    assert "2.66 GiB" in normalized
    assert "1.76 h" in normalized
    assert "6,325 s" in normalized
    assert "remains to be tested" in normalized


def test_human_report_states_time_limited_gamma_over_nu_scope_concisely():
    report = (PROJECT_ROOT / "report_Human" / "main.md").read_text()
    limitations = report.split("## 4. Limitations", maxsplit=1)[1]
    limitations = limitations.split("## 5. Conclusion", maxsplit=1)[0]
    normalized = " ".join(limitations.split())
    assert "submission timeline" in normalized
    assert "S(0,0)" not in normalized
    assert "S_eq(0)" not in normalized


def test_human_report_is_final_narrative_not_an_outline():
    report = (PROJECT_ROOT / "report_Human" / "main.md").read_text()
    assert "proposed structure" not in report
    assert "annotated outline" not in report
    for placeholder in (
        "- State ",
        "- Summarize ",
        "- Report ",
        "- Define ",
        "- Explain ",
        "- Briefly summarize ",
    ):
        assert placeholder not in report
    assert "## Abstract" in report
    assert "## 1. Model and method" in report
    assert "## 2. Numerical validation" in report
    assert "## 3. Long-range critical scaling" in report
    assert "## 4. Limitations" in report
    assert "## 5. Conclusion" in report
    assert "J_L(r)" in report
    assert "z_power=0.903245" in report
    assert "z_power=0.918948" in report


def test_human_report_includes_crossover_scan_and_second_gamma_benchmark():
    report = (PROJECT_ROOT / "report_Human" / "main.md").read_text()
    assert "σ=1.50–2.00" in report
    assert "Γ_x(32,64)=1.428411" in report
    assert "1.4208(2)" in report
    assert "210" in report
    assert "84.3 min" in report


def test_model_and_method_uses_rendered_latex_equations():
    report = (PROJECT_ROOT / "report_Human" / "main.md").read_text()
    method = report.split("## 1. Model and method", maxsplit=1)[1]
    method = method.split("## 2. Numerical validation", maxsplit=1)[0]
    assert "```text" not in method
    assert "$$" in method
    assert r"\sum_{i<j}" in method
    assert r"\zeta" in method
    assert r"\frac" in method
