"""Generated TeX inputs for the result-gated Paper-II manuscript."""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from make_geometric_eth_theory_inputs_v14 import build_inputs


REPO = Path(__file__).resolve().parents[4]


def test_generated_inputs_follow_the_failed_title_gate(tmp_path: Path) -> None:
    results = tmp_path / "results.tex"
    classes = tmp_path / "classes.tex"
    payload = build_inputs(REPO, results_path=results, classes_path=classes)
    text = results.read_text(encoding="utf-8")

    assert payload["gate_passed"] is False
    assert payload["selected_branch"] == "random_channel_failure"
    assert "Geometric Response of Exactly Degenerate Quantum State Bundles" in text
    assert "The Geometric ETH: Statistical Closure" not in text
    assert "\\newcommand{\\ChiralRandomOnePoint}{1.29034}" in text
    assert "\\newcommand{\\ChiralBandUpper}{1.23521}" in text
    assert "\\newcommand{\\PaperIIMappedArchivalCases}{0}" in text


def test_protection_table_contains_six_distinct_mechanisms(tmp_path: Path) -> None:
    results = tmp_path / "results.tex"
    classes = tmp_path / "classes.tex"
    build_inputs(REPO, results_path=results, classes_path=classes)
    text = classes.read_text(encoding="utf-8")

    for token in (
        "Common kernel / parent",
        "Cohomological",
        "Stabilizer",
        "Chiral / index",
        "Symmetry multiplet",
        "Integrable / spectrum-generating algebra",
    ):
        assert token in text
    assert "does not determine statistics" in text
    assert r"\begin{tabular}{@{}lllll@{}}" in text
    assert r"\newcommand{\pcell}" in text
    assert "p{1.00in}" not in text
