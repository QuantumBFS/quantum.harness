"""Contract tests for the additive Paper-I REVTeX project."""

from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]


def test_prb_project_contract() -> None:
    root = REPO / "overleaf_sync/exactly_degenerate_quantum_chaos_prb"
    main = (root / "main.tex").read_text(encoding="utf-8")

    assert (
        r"\documentclass[aps,prb,reprint,superscriptaddress,longbibliography,floatfix]"
        r"{revtex4-2}"
    ) in main
    assert (
        r"\title{Exactly Degenerate Quantum Chaos: Non-Abelian Quantum Geometry "
        r"as a Probe}"
    ) in main
    assert main.count(r"\input{sections/") == 10
    assert main.count(r"\includegraphics") == 7
    assert (root / "supplement.tex").exists()


def test_main_inputs_and_figure_slots_are_frozen() -> None:
    root = REPO / "overleaf_sync/exactly_degenerate_quantum_chaos_prb"
    main = (root / "main.tex").read_text(encoding="utf-8")

    expected_sections = [
        "01_introduction",
        "02_protected_response",
        "03_statistics",
        "04_models",
        "05_laughlin_results",
        "06_topology",
        "07_cohomology",
        "08_stabilizer",
        "09_classification",
        "10_discussion",
    ]
    positions = []
    for section in expected_sections:
        token = rf"\input{{sections/{section}.tex}}"
        assert token in main
        positions.append(main.index(token))
        assert (root / "sections" / f"{section}.tex").is_file()
    assert positions == sorted(positions)

    expected_figures = [
        ("figure_1_protection_mixing_v13.pdf", "fig:protection"),
        ("figure_2_spectral_silence_v13.pdf", "fig:spectral"),
        ("figure_3_geometric_hierarchy_v13.pdf", "fig:hierarchy"),
        ("figure_4_independent_channels_v13.pdf", "fig:channels"),
        ("figure_5_wick_parent_dependence_v13.pdf", "fig:wick"),
        ("figure_6_fixed_chern_holonomy_v13.pdf", "fig:holonomy"),
        ("figure_7_cross_mechanism_v13.pdf", "fig:mechanisms"),
    ]
    for filename, label in expected_figures:
        assert rf"\includegraphics[width=\textwidth]{{figures/{filename}}}" in main
        assert rf"\label{{{label}}}" in main

    assert r"\input{generated/results_v13.tex}" in main
    assert r"\begin{acknowledgments}" in main
    assert r"\bibliography{references}" in main


def test_supplement_contract() -> None:
    root = REPO / "overleaf_sync/exactly_degenerate_quantum_chaos_prb"
    supplement = (root / "supplement.tex").read_text(encoding="utf-8")

    assert (
        r"\documentclass[aps,prb,preprint,onecolumn,superscriptaddress,"
        r"longbibliography,floatfix]{revtex4-2}"
    ) in supplement
    assert r"\input{generated/results_v13.tex}" in supplement
    assert r"\input{sections/supplement_methods.tex}" in supplement
    assert r"\input{sections/supplement_numerics.tex}" in supplement
    assert r"\bibliography{references}" in supplement
    assert (root / "sections/supplement_methods.tex").is_file()
    assert (root / "sections/supplement_numerics.tex").is_file()


def _formalism_text() -> tuple[str, str, str]:
    sections = (
        REPO
        / "overleaf_sync/exactly_degenerate_quantum_chaos_prb"
        / "sections"
    )
    protected = (sections / "02_protected_response.tex").read_text(encoding="utf-8")
    statistics = (sections / "03_statistics.tex").read_text(encoding="utf-8")
    supplement = (sections / "supplement_methods.tex").read_text(encoding="utf-8")
    return protected, statistics, supplement


def test_protected_response_defines_the_canonical_geometry() -> None:
    protected, _, supplement = _formalism_text()
    combined = protected + "\n" + supplement

    for label in (
        "eq:splitting",
        "eq:response",
        "eq:qgt",
        "eq:curvature",
    ):
        assert rf"\label{{{label}}}" in combined

    assert r"Q=1-P" in protected
    assert r"X_a=Q(\partial_aP)P=-R_QV_a" in protected
    aligned = protected.replace("&", "")
    assert r"F_{ab}=\partial_aA_b-\partial_bA_a-i[A_a,A_b]" in aligned
    assert r"=i(\mathcal Q_{ab}-\mathcal Q_{ba})" in aligned
    assert "constant rank" in protected
    assert "spectral gap" in protected
    assert "reduced resolvent" in protected
    assert "gauge covariant" in protected
    assert "gauge invariant" in protected
    assert "not primary observables" in " ".join(protected.split())


def test_statistics_defines_complete_wick_subtraction_and_units() -> None:
    _, statistics, supplement = _formalism_text()
    combined = statistics + "\n" + supplement

    assert r"\label{eq:fourpoint}" in statistics
    assert r"\label{eq:wickresidual}" in statistics
    assert "pseudocovariance" in combined
    assert r"\Pi_{ab}" in combined
    assert "three Wick pairings" in combined
    assert r"C_{ab}C_{cd}" in combined
    assert r"\Pi_{ac}^{*}\Pi_{bd}" in combined
    assert r"C_{ad}C_{cb}" in combined
    assert r"R_4^{\mathrm{full}}" in statistics
    assert "finite-sample point estimate alone does not" in statistics
    assert "declared statistical unit" in statistics
    assert "treated as exchangeable" in combined
    assert r"(X_a)_{\alpha i}(X_b)_{\beta j}^{*}" in supplement
    assert "are not independent samples" in statistics
    assert "disorder realization" in statistics
    assert "fixed-Hamiltonian tangent panel" in statistics
    assert "delete-one" in combined
    assert "pseudovalues" in combined


def _model_text() -> tuple[str, str, str]:
    root = REPO / "overleaf_sync/exactly_degenerate_quantum_chaos_prb"
    models = (root / "sections/04_models.tex").read_text(encoding="utf-8")
    numerics = (root / "sections/supplement_numerics.tex").read_text(
        encoding="utf-8"
    )
    bibliography = (root / "references.bib").read_text(encoding="utf-8")
    return models, numerics, bibliography


def test_model_section_covers_each_exactness_mechanism() -> None:
    models, numerics, _ = _model_text()
    combined = models + "\n" + numerics
    compact = "".join(combined.split())
    normalized = " ".join(combined.split())

    equations = (
        r"H_{\mathrm{par}}=C^\dagger C",
        r"H_{\mathrm L}=V_0\sum_R A_R^\dagger A_R",
        r"H_{\mathrm{MR}}=\sum_x C_x^\dagger C_x",
        r"C_x=\frac{1}{\sqrt{3!}}\left(\sum_j\phi_{xj}b_j\right)^3",
        r"H_{\mathrm{SUSY}}=\{Q,Q^\dagger\}",
        r"H_{\mathrm{XC}}=-\sum_cJ_cA_c-\sum_{v,\mu\nu}K_v^{\mu\nu}B_v^{\mu\nu}",
    )
    for equation in equations:
        assert "".join(equation.split()) in compact

    for mechanism in (
        "two-body clustering",
        "three-body clustering",
        "random-supercharge cohomology",
        "independence-complex cohomology",
        "commuting stabilizers",
    ):
        assert mechanism in normalized.lower()

    for boundary in (
        "breaks Laughlin exactness",
        "breaks Moore--Read exactness",
        "breaks random-supercharge exactness",
        "breaks lattice-SUSY exactness",
        "breaks X-cube exactness",
    ):
        assert boundary in normalized

    normalized_models = " ".join(models.split())
    assert "quasi-degenerate replication" in normalized_models
    assert "not an exact-zero-mode mechanism" in normalized_models
    assert r"\input{generated/model_table_v13.tex}" in models


def test_model_section_states_auditable_inputs_and_uses_verified_keys() -> None:
    models, numerics, bibliography = _model_text()
    combined = models + "\n" + numerics

    for phrase in (
        "Hilbert space",
        "boundary conditions",
        "protected rank",
        "positive gap",
        "tangent class",
        "role in the comparison",
    ):
        assert phrase in combined

    required_keys = (
        "laughlin1983",
        "bernevighaldane2008",
        "chenseidel2015",
        "kapitmueller2010",
        "mooreread1991",
        "zhang2023parent",
        "fu2017susy",
        "fendley2003lattice",
        "huijse2010cohomology",
        "vijay2016xcube",
        "sun:2011:flat",
        "regnault:2011:fci",
    )
    for key in required_keys:
        assert f"{{{key}," in bibliography
        assert rf"\cite{{{key}}}" in combined

    assert "experimental" not in combined.lower()


def test_task7_sources_have_no_forbidden_c0_controls() -> None:
    root = REPO / "overleaf_sync/exactly_degenerate_quantum_chaos_prb"
    paths = (
        root / "sections/04_models.tex",
        root / "sections/supplement_numerics.tex",
        root / "references.bib",
    )
    allowed = {0x09, 0x0A, 0x0D}

    for path in paths:
        forbidden = [byte for byte in path.read_bytes() if byte < 0x20 and byte not in allowed]
        assert not forbidden, f"{path}: forbidden C0 bytes {forbidden}"


def test_model_section_separates_exact_transport_from_fixed_parent_probes() -> None:
    models, numerics, _ = _model_text()
    normalized = " ".join((models + "\n" + numerics).split())

    assert "exactness-preserving constraint/generator transport" in normalized
    assert r"$S_a=0$ along the path" in normalized
    assert "v2/v3 Laughlin fixed-parent local-potential panels" in normalized
    assert "v6 protected-generator results belong to exact transport" in normalized
    assert (
        "v9 Moore--Read guiding-center panels are exactness-preserving "
        "generator transports"
        in normalized
    )
    assert r"$(\partial_aH)P=-H\Gamma_N(G_a)P$" in normalized
    assert r"$X_a=Q\Gamma_N(G_a)P$" in normalized
    assert r"$\widetilde X_a=-Q\Gamma_N(G_a)P=-X_a$" in normalized
    assert "invertible transport of the three-body constraint map" in normalized
    assert "unitary transport of the three-body constraint map" not in normalized
    assert (
        "generally do not preserve exact degeneracy away from the base point"
        in normalized
    )
    assert (
        r"linear response of the isolated rank-$D$ cluster at the exact parent"
        in normalized
    )
    assert "finite exact path" in normalized
    assert "Moore--Read" in normalized
    assert "not generic splitting probes" in normalized
    assert "These are fixed-parent operator probes" not in normalized


def _article_level_text() -> tuple[str, str, str]:
    root = REPO / "overleaf_sync/exactly_degenerate_quantum_chaos_prb"
    introduction = (root / "sections/01_introduction.tex").read_text(
        encoding="utf-8"
    )
    discussion = (root / "sections/10_discussion.tex").read_text(encoding="utf-8")
    bibliography = (root / "references.bib").read_text(encoding="utf-8")
    return introduction, discussion, bibliography


def test_article_level_prose_states_the_geometric_argument_and_scope() -> None:
    introduction, discussion, _ = _article_level_text()
    combined = introduction + "\n" + discussion
    normalized = " ".join(combined.split())

    assert len(introduction.split()) >= 900
    assert len(discussion.split()) >= 1100
    for phrase in (
        "spectral form factor is silent",
        "off-fiber projector response",
        "exactness-preserving transport",
        "fixed-parent base-point probes",
        "Jacobi-like local eigenvalue repulsion",
        "global covariance memory",
        "finite-rank, cross-mechanism evidence",
        "not an asymptotic Geometric ETH theorem",
        "not a universal Geometric ETH theorem",
        "do not demonstrate thermalization",
        "independent model/operator class has not been established",
    ):
        assert phrase in normalized

    assert r"\subsection{Conclusion}" in discussion
    assert r"\label{sec:conclusion}" in discussion
    assert "X-cube" in combined
    assert "connected variance vanishes" in normalized
    assert "under reanalysis" not in normalized
    assert "final evidence registry" in normalized


def test_frontmatter_and_discussion_close_on_corrected_v13_claims() -> None:
    root = REPO / "overleaf_sync/exactly_degenerate_quantum_chaos_prb"
    main = (root / "main.tex").read_text(encoding="utf-8")
    supplement = (root / "supplement.tex").read_text(encoding="utf-8")
    introduction, discussion, _ = _article_level_text()
    combined = " ".join((main + "\n" + introduction + "\n" + discussion).split())

    assert r"\pdftrailerid{}" in main
    assert r"\pdftrailerid{}" in supplement

    abstract_match = re.search(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}", main, flags=re.DOTALL
    )
    assert abstract_match is not None
    abstract = " ".join(abstract_match.group(1).split())
    abstract_words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*", abstract)
    assert 170 <= len(abstract_words) <= 260

    for phrase in (
        "spectrally silent",
        "protection and mixing",
        "Jacobi-like",
        "parent- and covariance-dependent memory",
        "Moore--Read $N=6$",
        "Student-$t_{11}$",
        "Bonferroni",
        "Moore--Read $N=4$",
        "lattice-SUSY",
        "X-cube",
        "not an asymptotic or universal Geometric ETH",
    ):
        assert phrase in combined

    caption_match = re.search(
        r"\\caption\{\\label\{fig:protection\}(.*?)\}\s*\\end\{figure\*\}",
        main,
        flags=re.DOTALL,
    )
    assert caption_match is not None
    caption = " ".join(caption_match.group(1).split())
    for phrase in (
        "(a)",
        "(b)",
        "(c)",
        r"$S_a=0$ does not imply $X_a=0$",
        r"$s_a=D^{-1}\Tr[P(\partial_aH)P]$",
        "frozen, scalar, structured/reducible, and stochastic",
    ):
        assert phrase in caption

    acknowledgments_match = re.search(
        r"\\begin\{acknowledgments\}(.*?)\\end\{acknowledgments\}",
        main,
        flags=re.DOTALL,
    )
    assert acknowledgments_match is not None
    acknowledgments = " ".join(acknowledgments_match.group(1).split())
    assert "reproducibility package" in acknowledgments
    assert "Quantum Harness community" in acknowledgments

    assert "under reanalysis" not in combined
    assert "only the registered finite-rank Moore--Read $N=6$ case" in combined
    assert "No positive complete-cumulant statement is made" in combined


def test_article_level_claim_boundary_and_citations() -> None:
    introduction, discussion, bibliography = _article_level_text()
    combined = introduction + "\n" + discussion
    lowered = combined.lower()

    forbidden = (
        "we establish universal geometric eth",
        "thermalization is demonstrated",
        "novel framework",
        "comprehensive",
        "robust evidence",
        "opens new avenues",
        "state-of-the-art",
        "groundbreaking",
    )
    for phrase in forbidden:
        assert phrase not in lowered

    required_keys = (
        "berry1984",
        "wilczekzee1984",
        "provostvallee1980",
        "kato1950",
        "chen2026",
        "pandey2020",
        "chenludwig2018",
        "srednicki1994",
        "dalessio2016",
        "hastingswen2005",
        "collins2005",
    )
    cited_keys = {
        key.strip()
        for group in re.findall(r"\\cite\{([^}]+)\}", combined)
        for key in group.split(",")
    }
    for key in required_keys:
        assert f"{{{key}," in bibliography
        assert key in cited_keys


def _laughlin_result_text() -> tuple[str, str, str, str]:
    root = REPO / "overleaf_sync/exactly_degenerate_quantum_chaos_prb"
    results = (root / "sections/05_laughlin_results.tex").read_text(
        encoding="utf-8"
    )
    topology = (root / "sections/06_topology.tex").read_text(encoding="utf-8")
    main = (root / "main.tex").read_text(encoding="utf-8")
    macros = (root / "generated/results_v13.tex").read_text(encoding="utf-8")
    return results, topology, main, macros


def test_laughlin_results_state_the_finite_rank_hierarchy_and_wick_boundary() -> None:
    results, topology, _, macros = _laughlin_result_text()
    normalized = " ".join((results + "\n" + topology).split())

    assert len(results.split()) >= 1400
    assert len(topology.split()) >= 800
    for phrase in (
        "connected energy spectral form factor vanishes",
        "finite-$D$ Jacobi",
        "complete physical panel is the statistical unit",
        "intrafiber spectral scrambling",
        "off-fiber projector motion",
        "independent response channels",
        "historical two-pairing residual",
        "not the corrected complete cumulant",
        "zero of nine registered predictions",
        "does not imply the absence of finite-size decay",
        "Kapit--Mueller and continuum LLL parents",
        "parent dependence",
        "fixed first Chern number does not fix the non-Abelian holonomy",
        "not CUE-compatible",
    ):
        assert phrase in normalized

    required_macros = (
        "SpectralKernelBandwidth",
        "SpectralExternalGap",
        "SpectralFiberRank",
        "LaughlinNThreeRank",
        "LaughlinNFourRank",
        "LaughlinNFiveRank",
        "ContinuumLaughlinNThreeConnectedExcess",
        "ContinuumLaughlinNFourConnectedExcess",
        "ContinuumLaughlinNFiveConnectedExcess",
        "HolonomyNThreeRank",
        "HolonomyNThreeChernNumber",
        "HolonomyNThreeMinimumGap",
        "HolonomyNFourRank",
        "HolonomyNFourChernNumber",
        "HolonomyNFourMinimumGap",
    )
    for macro in required_macros:
        assert rf"\newcommand{{\{macro}}}" in macros
        assert rf"\{macro}" in results + topology

    assert r"\MooreRead" not in results + topology
    assert r"\LatticeSusy" not in results + topology
    assert "universal law" not in normalized.lower()
    assert "asymptotic" in normalized.lower()


def test_figures_two_through_six_have_self_contained_captions() -> None:
    _, _, main, _ = _laughlin_result_text()
    normalized_main = " ".join(main.split())

    for label in ("fig:spectral", "fig:hierarchy", "fig:channels", "fig:wick", "fig:holonomy"):
        match = re.search(
            rf"\\caption\{{\\label\{{{re.escape(label)}\}}(.*?)\n  \}}\n",
            main,
            flags=re.DOTALL,
        )
        assert match is not None
        caption = " ".join(match.group(1).split())
        assert len(caption.split()) >= 65
        for panel in ("(a)", "(b)", "(c)", "(d)"):
            assert panel in caption

    assert "historical two-pairing" in normalized_main
    assert "not the corrected complete cumulant" in normalized_main
    assert "registered point coverage" in normalized_main
    assert "CUE" in normalized_main
    assert "uncertainty" in normalized_main.lower()


def _cross_mechanism_text() -> tuple[str, str, str, str, str]:
    root = REPO / "overleaf_sync/exactly_degenerate_quantum_chaos_prb"
    cohomology = (root / "sections/07_cohomology.tex").read_text(
        encoding="utf-8"
    )
    stabilizer = (root / "sections/08_stabilizer.tex").read_text(
        encoding="utf-8"
    )
    classification = (root / "sections/09_classification.tex").read_text(
        encoding="utf-8"
    )
    main = (root / "main.tex").read_text(encoding="utf-8")
    macros = (root / "generated/results_v13.tex").read_text(encoding="utf-8")
    return cohomology, stabilizer, classification, main, macros


def test_cross_mechanism_results_preserve_the_inference_contract() -> None:
    cohomology, _, _, _, macros = _cross_mechanism_text()
    normalized = " ".join(cohomology.split())

    assert len(cohomology.split()) >= 1800
    for phrase in (
        "exactness-preserving generator transport",
        "fixed-base tangent panel",
        "exact population mean",
        "frozen 12/12 split",
        "training half alone",
        "three Wick pairings",
        "Student-$t$",
        "Bonferroni",
        "five registered primary cases",
        "reverse split is descriptive",
        "failure of the positive-direction gate does not prove Gaussianity",
        "separable proper-complex Gaussian null",
        "not the complete entrywise covariance",
        "independent disorder realization",
    ):
        assert phrase in normalized

    required_macros = (
        "MooreReadNFourRank",
        "MooreReadNSixRank",
        "MooreReadNFourFullRFourDirectionalEstimate",
        "MooreReadNFourFullRFourFamilywiseLower",
        "MooreReadNSixFullRFourDirectionalEstimate",
        "MooreReadNSixFullRFourFamilywiseLower",
        "LatticeSusyMOneRank",
        "LatticeSusyMTwoRank",
        "LatticeSusyMThreeRank",
        "SusySykNFourteenMedianOne",
        "SusySykNFourteenMedianTwo",
        "FullRFourTrainingCount",
        "FullRFourInferenceCount",
        "FullRFourPrimaryFamilySize",
        "FullRFourStudentTDegreesOfFreedom",
    )
    for macro in required_macros:
        assert rf"\newcommand{{\{macro}}}" in macros
        assert rf"\{macro}" in cohomology

    assert r"$N=4$" in cohomology and r"$N=6$" in cohomology
    assert r"$D=\MooreReadNFourRank$" in cohomology
    assert r"$D=\MooreReadNSixRank$" in cohomology
    assert "finite-rank $N=6$ result" in normalized
    assert "not an asymptotic statement" in normalized
    assert "v12 raw, uncentered" in normalized
    assert "historical two-pairing" in normalized

    assert r"X_a=Q\Gamma_N(G_a)P" in cohomology
    assert r"H_r=Q_{r+3}Q_{r+3}^{\dagger}+Q_r^{\dagger}Q_r" in cohomology
    assert r"X_a^-=\Pi_-X_a" in cohomology
    assert r"X_a^+=\Pi_+X_a" in cohomology


def test_stabilizer_results_include_both_exact_controls() -> None:
    _, stabilizer, _, _, macros = _cross_mechanism_text()
    normalized = " ".join(stabilizer.split())

    assert len(stabilizer.split()) >= 700
    for phrase in (
        "coefficient reweighting",
        "projector is parameter independent",
        "unitary transport",
        "exactly isospectral",
        "scalar curvature",
        "connected variance",
        "large exact degeneracy is not sufficient",
    ):
        assert phrase in normalized
    for macro in (
        "XCubeCoefficientCurvature",
        "XCubeTransportCurvatureEigenvalue",
        "XCubeTransportConnectedVariance",
    ):
        assert rf"\newcommand{{\{macro}}}" in macros
        assert rf"\{macro}" in stabilizer
    assert r"2^{6L-3}" in stabilizer
    assert "complete-covariance gate is not applicable" in normalized


def test_classification_separates_protection_mixing_and_sampling() -> None:
    _, _, classification, _, _ = _cross_mechanism_text()
    normalized = " ".join(classification.split())

    assert len(classification.split()) >= 900
    for phrase in (
        "protection class",
        "mixing class",
        "statistical class",
        "response rank",
        "commutant",
        "branch structure",
        "higher-order status",
        "fixed projector",
        "central curvature",
        "structured or reducible response",
        "finite-size stochastic response",
        "independent model/operator ensemble has not been established",
    ):
        assert phrase in normalized
    assert r"\mathfrak A_X" in classification
    assert r"\mathfrak C_X" in classification
    assert "protection does not determine mixing" in normalized


def test_figure_seven_caption_is_self_contained_and_finite_rank() -> None:
    _, _, _, main, _ = _cross_mechanism_text()
    match = re.search(
        r"\\caption\{\\label\{fig:mechanisms\}(.*?)\n  \}\n",
        main,
        flags=re.DOTALL,
    )
    assert match is not None
    caption = " ".join(match.group(1).split())
    assert len(caption.split()) >= 105
    for panel in ("(a)", "(b)", "(c)", "(d)"):
        assert panel in caption
    for phrase in (
        "historical two-pairing residual",
        "exact-population-centered complete cumulant",
        "frozen 12/12 split",
        "finite-rank",
        "reverse split",
        "not pooled",
        "zero connected variance",
    ):
        assert phrase in caption
