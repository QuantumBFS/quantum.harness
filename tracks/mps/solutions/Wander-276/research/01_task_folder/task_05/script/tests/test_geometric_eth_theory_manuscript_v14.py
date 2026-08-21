"""Literature-audit contract for the Geometric ETH manuscript."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
AUDIT = ROOT / "docs/literature/2026-08-17-geometric-eth-bps-black-hole-audit.md"
BIB = ROOT / "overleaf_sync/geometric_eth_theory/references.bib"
MANUSCRIPT = ROOT / "overleaf_sync/geometric_eth_theory"
GATE = ROOT / "01_task_folder/task_05/script/output/geometric_eth_theory_v14/theory_gate_v14.json"


def test_black_hole_audit_contract() -> None:
    text = AUDIT.read_text(encoding="utf-8")
    lowered = text.lower()
    for field in [
        "citation_key",
        "exact title",
        "authors",
        "primary claim",
        "section role",
        "verified date",
    ]:
        assert field in lowered
    for author in ["Lingxin Kong", "Hao Geng", "Yikun Jiang"]:
        assert author in text
    assert "to be verified" not in lowered


def test_literature_audit_has_at_least_35_records_and_unique_identifiers() -> None:
    text = AUDIT.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith("|")]
    assert len(rows) >= 37  # header, separator, and at least 35 records

    identifiers: list[str] = []
    for line in rows[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        identifier = cells[4]
        identifiers.extend(
            re.findall(r"(?:10\.\d{4,9}/[^)\s]+|arXiv:[A-Za-z0-9./-]+)", identifier)
        )
    assert identifiers
    assert len(identifiers) == len(set(identifiers))


def test_theory_bibliography_is_present_and_uses_audit_keys() -> None:
    audit = AUDIT.read_text(encoding="utf-8")
    bibliography = BIB.read_text(encoding="utf-8")
    audit_keys = set(re.findall(r"`([A-Za-z0-9:_-]+)`", audit))
    bib_keys = set(re.findall(r"^@\w+\{([^,]+),", bibliography, flags=re.MULTILINE))
    assert len(bib_keys) >= 35
    assert audit_keys.intersection(bib_keys)
    assert "huijse2010cohomology" not in bib_keys


def test_high_risk_claim_map_has_direct_primary_links() -> None:
    text = AUDIT.read_text(encoding="utf-8")
    lowered = text.lower()
    row = next(line for line in text.splitlines() if "`chen2026berry`" in line)
    required = [
        "d1/d5 1/2-bps",
        "1/4-bps n=4 sym",
        "n=2 super-jt",
        "n=2 syk",
        "exponentially large chern numbers",
    ]
    for phrase in required:
        assert phrase in row.lower() or phrase in lowered

    map_text = text.split("## Claim-to-source map", 1)[1]
    map_labels = [
        "D1/D5 1/2-BPS",
        "1/4-BPS states in N=4 SYM",
        "N=2 super-JT",
        "Explicit N=2 SYK numerics",
        "N=2 SYK has exponentially large Chern numbers",
    ]
    primary_link = "[arXiv:2604.23287](https://arxiv.org/abs/2604.23287)"
    for label in map_labels:
        line = next(line for line in map_text.splitlines() if label.lower() in line.lower())
        assert primary_link in line


def _manuscript_text() -> str:
    paths = [MANUSCRIPT / "main.tex", MANUSCRIPT / "supplement.tex"]
    paths.extend(sorted((MANUSCRIPT / "sections").glob("*.tex")))
    paths.extend(sorted((MANUSCRIPT / "supplement_sections").glob("*.tex")))
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def test_title_is_selected_only_by_the_machine_readable_gate() -> None:
    gate = json.loads(GATE.read_text(encoding="utf-8"))
    main = (MANUSCRIPT / "main.tex").read_text(encoding="utf-8")
    generated = (MANUSCRIPT / "generated/results_v14.tex").read_text(encoding="utf-8")

    assert gate["passed"] is False
    assert gate["selected_title"] == (
        "Geometric Response of Exactly Degenerate Quantum State Bundles"
    )
    assert "\\title{\\PaperIITitle}" in main
    assert gate["selected_title"] in generated
    assert "The Geometric ETH: Statistical Closure" not in generated


def test_modular_manuscript_contains_ten_sections_and_six_figures() -> None:
    main = (MANUSCRIPT / "main.tex").read_text(encoding="utf-8")
    for index, stem in enumerate(
        (
            "eth_failure",
            "bundle_geometry",
            "geometric_eth_ansatz",
            "channel_theorem",
            "protection_classes",
            "chiral_test",
            "bps_black_holes",
            "topology",
            "predictions",
            "discussion",
        ),
        start=1,
    ):
        assert f"\\input{{sections/{index:02d}_{stem}.tex}}" in main
    for index, stem in enumerate(
        (
            "eth_to_bundle",
            "response_algebra",
            "covariance_closure",
            "topology_statistics",
            "bps_comparison",
            "effective_channel_test",
        ),
        start=1,
    ):
        assert f"figures/figure_{index}_{stem}_v14.pdf" in main


def test_semantic_spine_and_negative_claim_boundary_are_explicit() -> None:
    text = _manuscript_text()
    lowered = text.lower()
    required = (
        "n_{\\rm eff}",
        "pseudocovariance",
        "three wick",
        "commutant",
        "random-channel prediction",
        "chiral",
        "d1/d5",
        "super-jt",
        "chern",
        "it from eth",
    )
    for token in required:
        assert token.lower() in lowered
    forbidden = (
        "we establish geometric eth",
        "black holes satisfy geometric eth",
        "proves the horizon",
        "thermalization of bps states",
        "we establish a universal geometric eth",
    )
    for phrase in forbidden:
        assert phrase not in lowered


def test_chiral_result_reports_all_frozen_values_without_refit() -> None:
    section = (MANUSCRIPT / "sections/06_chiral_test.tex").read_text(encoding="utf-8")
    for macro in (
        "\\ChiralBandLower",
        "\\ChiralBandUpper",
        "\\ChiralRandomOnePoint",
        "\\ChiralRandomTwoPoint",
        "\\ChiralRandomThreePoint",
        "\\PaperIIBranch",
    ):
        assert macro in section
    lowered = section.lower()
    assert "all three validation sizes" in lowered
    assert "we do not fit" in lowered
    assert "does not contradict weighted cumulant additivity" in lowered


def test_chiral_statistic_and_failure_attribution_are_unambiguous() -> None:
    main = (MANUSCRIPT / "main.tex").read_text(encoding="utf-8")
    section = (MANUSCRIPT / "sections/06_chiral_test.tex").read_text(
        encoding="utf-8"
    )
    appendix = (
        MANUSCRIPT / "supplement_sections/appendix_channel_theorem.tex"
    ).read_text(encoding="utf-8")
    protocol = (MANUSCRIPT / "supplement_sections/chiral_protocol.tex").read_text(
        encoding="utf-8"
    )

    assert r"N_{\rm eff}R_4^{\mathrm{full}}" in main
    assert r"\mu_z=\langle z\rangle" in section
    assert r"z-\bar z" not in section
    assert r"R_4^{\mathrm{full}}" in section
    assert r"\widehat R_4^{\mathrm{full}}" in appendix
    assert "identifies the missing assumption" not in section
    assert "9,216 tangent observations" in protocol
    assert "27,648" not in protocol


def test_author_identity_and_pdf_metadata_are_not_placeholder_like() -> None:
    main = (MANUSCRIPT / "main.tex").read_text(encoding="utf-8")
    supplement = (MANUSCRIPT / "supplement.tex").read_text(encoding="utf-8")

    for text in (main, supplement):
        assert r"\author{OkongOyangO}" in text
        assert "OKongOYangO" not in text
    assert "pdftitle={Supplemental Material for" in supplement
    assert "pdfauthor={Thomas J. Wang; OkongOyangO}" in supplement


def test_literature_count_and_taxonomy_scope_match_the_audit() -> None:
    audit = AUDIT.read_text(encoding="utf-8")
    scope = (MANUSCRIPT / "supplement_sections/literature_scope.tex").read_text(
        encoding="utf-8"
    )
    protection = (MANUSCRIPT / "sections/05_protection_classes.tex").read_text(
        encoding="utf-8"
    )

    assert "table contains 49 source records" in audit
    assert "source audit contains 49 records" in scope
    assert "not an exhaustive literature classification" in protection
    assert "random-coupling protected model" in protection
    assert "wang2026exactdegenerate" in audit
    assert r"\cite{wang2026exactdegenerate}" in protection


def test_subsystem_eth_record_uses_the_official_article_title() -> None:
    audit = AUDIT.read_text(encoding="utf-8")
    bibliography = BIB.read_text(encoding="utf-8")

    official_title = "Subsystem eigenstate thermalization hypothesis"
    assert official_title in audit
    assert f"title = {{{official_title}}}" in bibliography
    assert "title = {Subsystem ETH}" not in bibliography


def test_empirical_values_are_consumed_only_through_generated_macros() -> None:
    main = (MANUSCRIPT / "main.tex").read_text(encoding="utf-8")
    theorem = (MANUSCRIPT / "sections/04_channel_theorem.tex").read_text(
        encoding="utf-8"
    )
    predictions = (MANUSCRIPT / "sections/09_predictions.tex").read_text(
        encoding="utf-8"
    )
    appendix = (
        MANUSCRIPT / "supplement_sections/appendix_channel_theorem.tex"
    ).read_text(encoding="utf-8")

    for macro in (
        r"\ChiralBandLower",
        r"\ChiralBandUpper",
        r"\ChiralRandomOnePoint",
        r"\ChiralRandomTwoPoint",
        r"\ChiralRandomThreePoint",
    ):
        assert macro in main + predictions
    assert r"\ChannelTheoryMaximumRelativeError" in theorem
    assert r"\ChannelTheoryMaximumRelativeError" in appendix
    prose = "\n".join((main, theorem, predictions, appendix))
    for manual_value in (
        "1.2903355",
        "1.3649631",
        "1.4814450",
        "0.4476289",
        "1.2352060",
        "0.04433547544",
        "$1.290$",
        "$1.365$",
        "$1.481$",
        "$[0.448,1.235]$",
    ):
        assert manual_value not in prose
