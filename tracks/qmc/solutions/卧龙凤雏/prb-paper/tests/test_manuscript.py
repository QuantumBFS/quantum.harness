import re


def _paper(paper_dir):
    return (paper_dir / "paper.tex").read_text(encoding="utf-8")


def test_prb_front_matter_is_exact(paper_dir):
    text = _paper(paper_dir)

    assert (
        r"\documentclass[aps,prb,reprint,superscriptaddress,longbibliography]"
        r"{revtex4-2}"
    ) in text
    assert r"\author{Xu Tian}" in text
    assert r"\author{Huidan Tan}" in text
    assert "Department of Physics, School of Science, Westlake University" in text
    assert r"\email{tianxu@westlake.edu.cn}" in text
    assert r"\input{generated/headline_values.tex}" in text


def test_required_sections_and_equations_exist(paper_dir):
    text = _paper(paper_dir)

    for label in (
        "sec:introduction",
        "sec:models",
        "sec:methods",
        "sec:benchmarks",
        "sec:learning",
        "sec:discussion",
        "sec:conclusion",
        "app:mappings",
        "app:bootstrap",
        "app:gates",
    ):
        assert rf"\label{{{label}}}" in text
    compact = re.sub(r"\s+", "", text)
    assert r"f(L)=f_\infty-\frac{\pic_{\mathrm{eff}}}{6L^2}" in compact


def test_abstract_states_benchmark_and_exploratory_outcomes(paper_dir):
    text = _paper(paper_dir)
    abstract = re.search(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}", text, flags=re.DOTALL
    )

    assert abstract
    body = abstract.group(1)
    assert r"\CleanMCCharge" in body
    assert r"\NishimoriCharge" in body
    assert r"\WeakCharge" in body
    assert r"\LearningEntanglementCharge" in body
    assert r"\LearningCasimirCharge" in body
    assert "inconclusive" in body.lower()
    assert len(re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)?", body)) <= 250


def test_methods_name_rust_python_rng_and_resampling_units(paper_dir):
    text = _paper(paper_dir)

    for phrase in (
        "Xoshiro256++",
        "Wolff",
        "Rao--Blackwell",
        "paired bootstrap",
        "common-disorder",
        "Rust",
        "Python",
    ):
        assert phrase in text


def test_results_include_all_figures_and_tables(paper_dir):
    text = _paper(paper_dir)

    for number in range(1, 9):
        assert rf"\label{{fig:{number:02d}-" in text
    for number in range(1, 5):
        assert rf"\label{{tab:{number:02d}-" in text
    assert text.count(r"\includegraphics") == 8


def test_learning_claim_is_explicitly_conservative(paper_dir):
    text = re.sub(r"\s+", " ", _paper(paper_dir).lower())

    for phrase in (
        "does not constitute a universal-central-charge estimate",
        "transition is not bracketed",
        "anisotropy calibration is unstable",
        "estimators disagree",
    ):
        assert phrase in text
    assert r"\learningpublished" in text


def test_nishimori_replica_conventions_are_distinguished(paper_dir):
    text = _paper(paper_dir)

    assert "ordinary quenched" in text
    assert "0.522" in text
    assert "higher-replica" in text
