# PRB Four-Model Paper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a visually verified Physical Review B Regular Article PDF that unifies the three validated central-charge benchmarks and the exploratory learning-induced metal--insulator-transition result.

**Architecture:** A self-contained `prb-paper` package will validate the four frozen result sets, regenerate eight publication figures, render frozen values into a small generated TeX include, and compile a REVTeX 4.2 manuscript with BibTeX. Tests will bind every headline claim to source JSON/CSV and verify citations, cross-references, PDF structure, and the conservative learning-MIT claim boundary.

**Tech Stack:** Python 3.13, NumPy, Matplotlib, Pillow, pytest, pypdf, REVTeX 4.2, BibTeX, latexmk, Ghostscript.

## Global Constraints

- Write the manuscript in American English as a PRB Regular Article.
- Use the approved title: `Effective Central Charges across Clean, Disordered, and Monitored Criticality: Benchmarks and an Exploratory Learning-Induced Metal--Insulator Transition`.
- Authors are Xu Tian and Huidan Tan.
- Affiliation is `Department of Physics, School of Science, Westlake University, Hangzhou 310030, China`.
- Contact author is Xu Tian, `tianxu@westlake.edu.cn`.
- Read only frozen result artifacts; do not rerun Monte Carlo.
- Rust remains the sole source of sampled physics data; Python performs validation, plotting, manuscript generation, and PDF checks.
- Preserve the learning-MIT candidate at the pre-refinement value \(\phi/\pi=0.30\).
- Do not publish either learning-MIT effective-central-charge estimator as a universal central charge.
- The reader-facing deliverable is only `output/pdf/effective-central-charges-prb-paper.pdf`.
- Use REVTeX 4.2 with the `prb` option and include titles in all references.
- Use accessible colors plus markers and line styles so every plot works in grayscale.
- Do not leave unresolved citations, references, `TODO`, `TBD`, placeholder text, or invented DOI metadata.
- Render and inspect every final PDF page before completion.

---

## File Map

- Create `tracks/qmc/solutions/卧龙凤雏/prb-paper/Makefile`
  - Defines setup, test, figures, manuscript, verify, and clean targets.
- Create `tracks/qmc/solutions/卧龙凤雏/prb-paper/requirements.txt`
  - Pins the Python packages already used by the report workflows.
- Create `tracks/qmc/solutions/卧龙凤雏/prb-paper/paper_data.py`
  - Loads and validates all four frozen studies.
- Create `tracks/qmc/solutions/卧龙凤雏/prb-paper/build_values.py`
  - Writes deterministic TeX macros from validated numerical facts.
- Create `tracks/qmc/solutions/卧龙凤雏/prb-paper/build_figures.py`
  - Builds the eight publication multipanel figures from frozen data.
- Create `tracks/qmc/solutions/卧龙凤雏/prb-paper/paper.tex`
  - Contains the complete REVTeX manuscript.
- Create `tracks/qmc/solutions/卧龙凤雏/prb-paper/references.bib`
  - Contains verified APS-style bibliography metadata with titles.
- Create `tracks/qmc/solutions/卧龙凤雏/prb-paper/verify_pdf.py`
  - Checks page geometry, embedded fonts, text, figure count, and metadata.
- Create `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/conftest.py`
  - Supplies repository-root and frozen-data fixtures.
- Create `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_paper_data.py`
  - Verifies frozen values, hashes, gates, and claim boundaries.
- Create `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_figures.py`
  - Verifies deterministic figure production and readable dimensions.
- Create `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_bibliography.py`
  - Verifies citation keys and mandatory BibTeX fields.
- Create `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_manuscript.py`
  - Verifies structure, equations, author metadata, claims, and cross-references.
- Create `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_pdf.py`
  - Verifies the compiled PDF.
- Create `tracks/qmc/solutions/卧龙凤雏/prb-paper/generated/.gitkeep`
  - Retains the generated-asset directory without committing temporary TeX files.
- Create `tracks/qmc/solutions/卧龙凤雏/prb-paper/tmp/pdfs/.gitkeep`
  - Retains the PDF-rendering directory.
- Create `output/pdf/effective-central-charges-prb-paper.pdf`
  - Stable final artifact.

---

### Task 1: Scaffold the Paper Package and Frozen-Data Contract

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/Makefile`
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/requirements.txt`
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/paper_data.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/conftest.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_paper_data.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/generated/.gitkeep`
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/tmp/pdfs/.gitkeep`

**Interfaces:**
- Consumes: the four frozen result directories and `learning-mit/FROZEN_RESULT`.
- Produces: `PaperData load_paper_data(repo_root: Path)` and immutable benchmark/open-result records used by every later task.

- [ ] **Step 1: Write the frozen-data tests**

```python
def test_headline_values_are_loaded_from_frozen_sources(repo_root):
    data = load_paper_data(repo_root)
    assert data.clean.mc_c == pytest.approx(0.4987390622675896)
    assert data.clean.exact_c == pytest.approx(0.49942440242816655)
    assert data.nishimori.c_eff == pytest.approx(0.45646940076821396)
    assert data.nishimori.ci95 == pytest.approx(
        (0.44006391478771134, 0.4723035402043263)
    )
    assert data.weak.c_eff == pytest.approx(0.44410663549565277)
    assert data.learning.candidate_phi_pi == pytest.approx(0.30)


def test_learning_result_remains_exploratory(repo_root):
    learning = load_paper_data(repo_root).learning
    assert learning.entanglement_c_eff == pytest.approx(3.060739513110786)
    assert learning.casimir_c_eff == pytest.approx(12.579932843147617)
    assert learning.alpha_stable is False
    assert learning.estimator_agrees is False
    assert learning.central_charge_published is False
    assert learning.claim_reasons == (
        "diii_transition_not_bracketed",
        "anisotropy_unstable",
        "estimator_disagreement",
    )


def test_learning_summary_matches_frozen_pointer(repo_root):
    data = load_paper_data(repo_root)
    assert data.learning.summary_sha256 == (
        "cc08a6e6d6d414046c744b4d29d48f112d44526dfc2145b867aae01f07d53c33"
    )
```

- [ ] **Step 2: Run the tests and verify that the package does not exist yet**

Run:

```bash
cd tracks/qmc/solutions/卧龙凤雏/prb-paper
python3 -m pytest tests/test_paper_data.py -q
```

Expected: collection fails because `paper_data` is not defined.

- [ ] **Step 3: Implement the immutable data contract**

Define focused dataclasses:

```python
@dataclass(frozen=True)
class Benchmark:
    slug: str
    c_eff: float
    standard_error: float
    ci95: tuple[float, float]
    target: float
    exact_c: float | None
    widths: tuple[int, ...]
    gates: tuple[str, ...]
    source_hashes: Mapping[str, str]


@dataclass(frozen=True)
class LearningResult:
    candidate_phi_pi: float
    entanglement_c_eff: float
    entanglement_standard_error: float
    entanglement_ci95: tuple[float, float]
    casimir_c_eff: float
    casimir_standard_error: float
    casimir_ci95: tuple[float, float]
    alpha: float
    alpha_stable: bool
    estimator_agrees: bool
    central_charge_published: bool
    claim_reasons: tuple[str, ...]
    summary_sha256: str
    source_hashes: Mapping[str, str]


@dataclass(frozen=True)
class PaperData:
    clean: Benchmark
    nishimori: Benchmark
    weak: Benchmark
    learning: LearningResult
```

Reuse the already tested loaders in
`integrated-report/analysis/sources.py`, but adapt their returned records into
the paper-specific dataclasses. Recompute the learning summary SHA-256 and
reject any mismatch with `FROZEN_RESULT`. Reject failed required gates for the
three benchmark models, but retain the declared failed claim gates for the
exploratory study.

- [ ] **Step 4: Add deterministic package commands**

Use this Makefile surface:

```make
PYTHON ?= .venv/bin/python
MPLCONFIGDIR ?= /private/tmp/prb-paper-matplotlib

.PHONY: setup test figures manuscript verify clean

setup:
	test -d .venv || python3 -m venv --system-site-packages .venv
	.venv/bin/pip install -r requirements.txt

test:
	MPLCONFIGDIR="$(MPLCONFIGDIR)" "$(PYTHON)" -m pytest -q

figures:
	MPLCONFIGDIR="$(MPLCONFIGDIR)" "$(PYTHON)" build_values.py
	MPLCONFIGDIR="$(MPLCONFIGDIR)" "$(PYTHON)" build_figures.py

manuscript: figures
	latexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex

verify: manuscript
	"$(PYTHON)" verify_pdf.py paper.pdf

clean:
	latexmk -C paper.tex
	rm -f generated/*.pdf generated/*.png generated/headline_values.tex
```

Pin `numpy==2.0.2`, `matplotlib==3.9.4`, `Pillow==11.3.0`,
`pypdf==5.9.0`, and `pytest==8.3.5`.

- [ ] **Step 5: Run the focused tests**

Run:

```bash
make setup
make test
```

Expected: all Task 1 tests pass.

- [ ] **Step 6: Commit the data contract**

```bash
git add tracks/qmc/solutions/卧龙凤雏/prb-paper
git commit -m "feat: add frozen data contract for PRB paper"
```

---

### Task 2: Generate TeX Values and Eight Publication Figures

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/build_values.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/build_figures.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_figures.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/Makefile`

**Interfaces:**
- Consumes: `PaperData` plus the frozen CSV/JSON tables and existing plot inputs.
- Produces: `generated/headline_values.tex` and `generated/fig01-workflow.pdf` through `generated/fig08-learning-diagnostics.pdf`.

- [ ] **Step 1: Write tests for generated macros and figures**

```python
EXPECTED_FIGURES = (
    "fig01-workflow.pdf",
    "fig02-clean.pdf",
    "fig03-nishimori.pdf",
    "fig04-weak-self-dual.pdf",
    "fig05-benchmark-comparison.pdf",
    "fig06-phase-scans.pdf",
    "fig07-entanglement.pdf",
    "fig08-learning-diagnostics.pdf",
)


def test_value_macros_are_source_derived(repo_root, paper_dir):
    build_values(repo_root, paper_dir / "generated/headline_values.tex")
    text = (paper_dir / "generated/headline_values.tex").read_text()
    assert r"\newcommand{\CleanMCCharge}{0.498739}" in text
    assert r"\newcommand{\NishimoriCharge}{0.456469}" in text
    assert r"\newcommand{\WeakCharge}{0.444107}" in text
    assert r"\newcommand{\LearningCandidate}{0.30}" in text
    assert r"\newcommand{\LearningPublished}{false}" in text


def test_all_figures_are_deterministic_and_print_readable(repo_root, paper_dir):
    first = build_all_figures(repo_root, paper_dir / "generated")
    first_hashes = {path.name: sha256(path.read_bytes()).hexdigest() for path in first}
    second = build_all_figures(repo_root, paper_dir / "generated")
    second_hashes = {path.name: sha256(path.read_bytes()).hexdigest() for path in second}
    assert tuple(path.name for path in first) == EXPECTED_FIGURES
    assert first_hashes == second_hashes
    assert all(path.stat().st_size > 10_000 for path in first)
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```bash
make test
```

Expected: failures because `build_values.py` and `build_figures.py` do not
exist.

- [ ] **Step 3: Implement deterministic TeX macro generation**

Write macros only through a fixed serializer:

```python
def tex_command(name: str, value: str) -> str:
    if not name.isascii() or not name.isalpha():
        raise ValueError(f"invalid TeX command name: {name}")
    if "\n" in value or "{" in value or "}" in value:
        raise ValueError(f"unsafe TeX command value: {name}")
    return rf"\newcommand{{\{name}}}{{{value}}}" + "\n"
```

Generate commands for all estimates, standard errors, confidence endpoints,
targets, candidate point, anisotropy, task count, runtime, summary hash, and
claim-reason labels. Write atomically so a failed build cannot leave a partial
include.

- [ ] **Step 4: Implement the shared journal plotting style**

Use a colorblind-safe palette:

```python
COLORS = {
    "blue": "#0072B2",
    "orange": "#E69F00",
    "green": "#009E73",
    "red": "#D55E00",
    "purple": "#CC79A7",
    "gray": "#5B5B5B",
}

plt.rcParams.update({
    "font.size": 8.0,
    "axes.labelsize": 8.0,
    "axes.titlesize": 8.5,
    "legend.fontsize": 7.0,
    "xtick.labelsize": 7.0,
    "ytick.labelsize": 7.0,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "savefig.bbox": "tight",
})
```

Use circles, squares, triangles, and diamonds plus solid, dashed, dotted, and
dash-dot lines. Export vector PDF figures at single-column width 3.35 in or
double-column width 7.0 in.

- [ ] **Step 5: Build the eight specified multipanel figures**

Implement one `PaperData -> matplotlib.figure.Figure` function per figure:
`figure_workflow`, `figure_clean`, `figure_nishimori`,
`figure_weak_self_dual`, `figure_benchmark_comparison`,
`figure_phase_scans`, `figure_entanglement`, and
`figure_learning_diagnostics`. `build_all_figures` calls them in this fixed
order and writes the filenames declared by `EXPECTED_FIGURES`.

Figure 1 is a Matplotlib-native diagram, not a raster screenshot. Figures
2--4 combine the corresponding frozen fit, residual, stability, and oracle
data. Figure 5 plots all three benchmark estimates with 95% intervals and
literature targets. Figures 6--8 use only the hash-selected production-v2
learning data and visually mark the result as exploratory.

- [ ] **Step 6: Run figure tests and visually inspect every panel**

Run:

```bash
make figures
make test
mkdir -p tmp/pdfs/figures
for f in generated/fig*.pdf; do
  /usr/local/bin/gs -q -dSAFER -dBATCH -dNOPAUSE \
    -sDEVICE=png16m -r180 -sOutputFile="tmp/pdfs/figures/$(basename "${f%.pdf}").png" "$f"
done
```

Inspect all eight PNGs for tiny labels, clipped legends, ambiguous color-only
encoding, and inconsistent panel lettering.

- [ ] **Step 7: Commit the generated-data pipeline**

```bash
git add tracks/qmc/solutions/卧龙凤雏/prb-paper
git commit -m "feat: generate PRB paper figures and values"
```

---

### Task 3: Build and Verify the Primary-Source Bibliography

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/references.bib`
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_bibliography.py`

**Interfaces:**
- Consumes: publisher, DOI, and arXiv metadata.
- Produces: a title-complete BibTeX database whose keys are used by `paper.tex`.

- [ ] **Step 1: Write bibliography validation tests**

```python
REQUIRED_KEYS = {
    "Onsager1944",
    "BloeteCardyNightingale1986",
    "Affleck1986",
    "Wolff1989",
    "Nishimori1981",
    "HoneckerJacobsenPiccoPujol2001",
    "EfronTibshirani1993",
    "Bravyi2005",
    "SkinnerRuhmanNahum2019",
    "LiChenFisher2018",
    "WangVasseurTrebstLudwigZhu2025",
    "BlackmanVigna2021",
}


def test_references_have_prb_required_titles(paper_dir):
    entries = parse_bibtex(paper_dir / "references.bib")
    assert REQUIRED_KEYS <= set(entries)
    for key, entry in entries.items():
        assert entry["author"].strip()
        assert entry["title"].strip()
        assert entry["year"].isdigit()
        assert "doi" in entry or "eprint" in entry or "isbn" in entry
```

Add a DOI-format check and a manuscript-to-bibliography consistency test that
compares every `\cite{...}` key with the parsed entries.

- [ ] **Step 2: Run the bibliography tests and verify failure**

Run:

```bash
make test
```

Expected: bibliography tests fail because `references.bib` is absent.

- [ ] **Step 3: Verify and enter the core references**

Populate complete entries for:

- L. Onsager, *Crystal Statistics. I. A Two-Dimensional Model with an
  Order-Disorder Transition*, Phys. Rev. **65**, 117 (1944),
  DOI `10.1103/PhysRev.65.117`.
- H. W. J. Blöte, J. L. Cardy, and M. P. Nightingale, *Conformal Invariance,
  the Central Charge, and Universal Finite-Size Amplitudes at Criticality*,
  Phys. Rev. Lett. **56**, 742 (1986),
  DOI `10.1103/PhysRevLett.56.742`.
- I. Affleck, *Universal Term in the Free Energy at a Critical Point and the
  Conformal Anomaly*, Phys. Rev. Lett. **56**, 746 (1986),
  DOI `10.1103/PhysRevLett.56.746`.
- U. Wolff, *Collective Monte Carlo Updating for Spin Systems*, Phys. Rev.
  Lett. **62**, 361 (1989), DOI `10.1103/PhysRevLett.62.361`.
- H. Nishimori, *Internal Energy, Specific Heat and Correlation Function of
  the Bond-Random Ising Model*, Prog. Theor. Phys. **66**, 1169 (1981),
  DOI `10.1143/PTP.66.1169`.
- A. Honecker, J. L. Jacobsen, M. Picco, and P. Pujol, *Nishimori Point in
  Random-Bond Ising and Potts Models in Two Dimensions*, Phys. Rev. Lett.
  **87**, 047201 (2001), DOI `10.1103/PhysRevLett.87.047201`.
- S. Bravyi, *Lagrangian Representation for Fermionic Linear Optics*,
  Quantum Inf. Comput. **5**, 216 (2005), arXiv `quant-ph/0404180`.
- B. Skinner, J. Ruhman, and A. Nahum, *Measurement-Induced Phase
  Transitions in the Dynamics of Entanglement*, Phys. Rev. X **9**, 031009
  (2019), DOI `10.1103/PhysRevX.9.031009`.
- Y. Li, X. Chen, and M. P. A. Fisher, *Quantum Zeno Effect and the
  Many-Body Entanglement Transition*, Phys. Rev. B **98**, 205136 (2018),
  DOI `10.1103/PhysRevB.98.205136`.
- Q. Wang, R. Vasseur, S. Trebst, A. W. W. Ludwig, and G.-Y. Zhu,
  *Decoherence-Induced Self-Dual Criticality in Topological States of
  Matter*, arXiv:2502.14034v4 (2025).
- D. Blackman and S. Vigna, *Scrambled Linear Pseudorandom Number
  Generators*, ACM Trans. Math. Softw. **47**, 36 (2021),
  DOI `10.1145/3460772`.

Add verified references for bootstrap methodology, transfer matrices,
Nishimori-point numerical estimates, monitored free-fermion trajectories,
class-D/DIII network models, and entanglement finite-size scaling as required
by the final text. Use the current arXiv v4 metadata for the 2025 challenge
reference.

- [ ] **Step 4: Run the bibliography tests and BibTeX parser**

Run:

```bash
make test
bibtex --version
```

Expected: all bibliography tests pass and BibTeX is available.

- [ ] **Step 5: Commit the bibliography**

```bash
git add tracks/qmc/solutions/卧龙凤雏/prb-paper/references.bib \
  tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_bibliography.py
git commit -m "docs: add verified bibliography for PRB paper"
```

---

### Task 4: Write the Front Matter, Theory, and Numerical Methods

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/paper.tex`
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_manuscript.py`

**Interfaces:**
- Consumes: `generated/headline_values.tex`, Figures 1--8, and `references.bib`.
- Produces: the first complete manuscript draft with all section labels,
  equations, citations, and figure/table references.

- [ ] **Step 1: Write manuscript-structure tests**

```python
def test_prb_front_matter_is_exact(paper_text):
    assert r"\documentclass[aps,prb,reprint,superscriptaddress,longbibliography]{revtex4-2}" in paper_text
    assert r"\author{Xu Tian}" in paper_text
    assert r"\author{Huidan Tan}" in paper_text
    assert "Department of Physics, School of Science, Westlake University" in paper_text
    assert r"\email{tianxu@westlake.edu.cn}" in paper_text


def test_required_sections_and_equations_exist(paper_text):
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
        assert rf"\label{{{label}}}" in paper_text
    assert r"f(L)=f_\infty-\frac{\pi c_{\mathrm{eff}}}{6L^2}" in paper_text
    assert r"\input{generated/headline_values.tex}" in paper_text
```

- [ ] **Step 2: Run the manuscript tests and verify failure**

Run:

```bash
make test
```

Expected: manuscript tests fail because `paper.tex` is absent.

- [ ] **Step 3: Write the REVTeX front matter and abstract**

Use:

```tex
\documentclass[aps,prb,reprint,superscriptaddress,longbibliography]{revtex4-2}
\usepackage{amsmath,amssymb,bm,booktabs,graphicx,microtype,xcolor}
\graphicspath{{generated/}}
\input{generated/headline_values.tex}

\begin{document}
\title{Effective Central Charges across Clean, Disordered, and Monitored
Criticality: Benchmarks and an Exploratory Learning-Induced
Metal--Insulator Transition}
\author{Xu Tian}
\email{tianxu@westlake.edu.cn}
\author{Huidan Tan}
\affiliation{Department of Physics, School of Science, Westlake University,
Hangzhou 310030, China}
```

The abstract must state the three benchmark estimates with uncertainties,
describe the frozen learning candidate, and conclude that estimator
disagreement prevents a universal-central-charge claim. Keep it below 250
words and avoid implementation jargon not needed by a broad PRB readership.

- [ ] **Step 4: Write Sections I and II**

Section I establishes central charge as a universal finite-size amplitude,
explains why nonunitary or disordered systems use \(c_{\mathrm{eff}}\), and
frames the three benchmarks as calibration for the open problem.

Section II defines:

```tex
f(L)=f_\infty-\frac{\pi c_{\mathrm{eff}}}{6L^2}
     +\frac{a}{L^4}+O(L^{-6}),
```

the square-lattice Ising Hamiltonian, the \(\pm J\) Nishimori distribution,
the Majorana covariance matrix \(\Gamma_{ij}=\frac{i}{2}
\langle[\gamma_i,\gamma_j]\rangle\), conditional Born probabilities, and the
XY and generic-DIII angle cuts. Explicitly distinguish ordinary quenched
\(c_{\mathrm{eff}}\simeq0.464\) from the different Born/higher-replica
quantity near \(0.522\).

- [ ] **Step 5: Write Section III**

Describe:

- exact transfer-matrix and Wolff thermodynamic-integration routes;
- common-disorder transfer products and the Nishimori energy identity;
- Gaussian covariance updates and Rao--Blackwellized conditional entropy;
- Xoshiro256++ stream derivation;
- model-specific blocks, paired bootstrap, effective sample size, and
  predeclared validation gates.

Include Figure 1 and Table I. State that more Monte Carlo samples reduce
sampling variance but do not correct finite-size bias, unstable anisotropy, or
an unbracketed transition.

- [ ] **Step 6: Run text and structure tests**

Run:

```bash
make figures
make test
```

Expected: all current tests pass.

- [ ] **Step 7: Commit the theory and methods draft**

```bash
git add tracks/qmc/solutions/卧龙凤雏/prb-paper
git commit -m "docs: write PRB theory and numerical methods"
```

---

### Task 5: Write Benchmark Results and the Exploratory MIT Analysis

**Files:**
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/paper.tex`
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_manuscript.py`

**Interfaces:**
- Consumes: generated macros and Figures 2--8.
- Produces: complete Results, Discussion, Conclusion, tables, and end matter.

- [ ] **Step 1: Add claim-boundary regression tests**

```python
def test_learning_claim_is_conservative(paper_text):
    required = (
        r"\LearningEntanglementCharge",
        r"\LearningCasimirCharge",
        "does not constitute a universal-central-charge estimate",
        "transition is not bracketed",
        "anisotropy calibration is unstable",
        "estimators disagree",
    )
    assert all(item in paper_text for item in required)
    forbidden = (
        "we determine the DIII central charge",
        "confirmed DIII critical point",
        "universal value is 12.58",
    )
    assert all(item not in paper_text for item in forbidden)


def test_all_eight_figures_and_four_tables_are_referenced(paper_text):
    for number in range(1, 9):
        assert rf"\label{{fig:{number:02d}" in paper_text
    for number in range(1, 5):
        assert rf"\label{{tab:{number:02d}" in paper_text
```

- [ ] **Step 2: Run the new tests and verify failure**

Run:

```bash
make test
```

Expected: failures because the result sections and their figures/tables are
not present.

- [ ] **Step 3: Write the three benchmark subsections**

For each benchmark, explain the observable, fit model, sampling unit, result,
uncertainty, target comparison, and strongest validation oracle.

Use Figures 2--5 and Table II. Report values through generated macros rather
than duplicated decimal literals. State that confidence-interval agreement is
evidence of consistency, not proof of the target value.

- [ ] **Step 4: Write the learning-induced-transition section**

Use Figures 6--8 and Table III. The logical order is:

1. reproduce the XY bracket \([0.24,0.25]\);
2. show that the generic-DIII evidence does not create an adjacent
   metal/insulator bracket;
3. explain why candidate selection is frozen before adaptive refinement;
4. present the entanglement chord-length estimate and its smallest-width
   stability;
5. present the Casimir amplitude and anisotropy conversion;
6. quantify the estimator disagreement;
7. conclude that the result is exploratory and inconclusive.

Do not average the two central-charge estimators or select one after seeing
their values.

- [ ] **Step 5: Write the cross-model discussion and conclusion**

Use Table IV to separate:

- sampling variance;
- autocorrelation;
- quenched-disorder covariance;
- floating-point Gaussian-invariant error;
- finite-size correction uncertainty;
- anisotropy uncertainty;
- critical-point selection uncertainty.

Conclude that the framework validates three benchmarks but diagnoses the open
problem as underdetermined. Recommend larger widths, an independent
anisotropy observable, and a predeclared bracketed scan.

- [ ] **Step 6: Write end matter and appendixes**

Use these exact declarations:

```tex
\section*{Data Availability}
All numerical data, configurations, analysis code, and provenance manifests
used in this work are contained in the accompanying Quantum Harness
repository. The manuscript reads only the frozen result directories identified
in the data manifest and does not rerun the Monte Carlo calculations.

\section*{Author Contributions}
Xu Tian and Huidan Tan jointly designed the study, developed and validated the
numerical workflows, analyzed the data, and wrote the manuscript.

\section*{Acknowledgments}
The authors thank Guo-Yi Zhu for formulating Quantum Harness Challenge
\#122, which motivated the benchmark-to-frontier study.
```

Appendixes contain explicit coupling maps, Gaussian update/oracle equations,
bootstrap resampling units, fit variants, and the complete gate table.

- [ ] **Step 7: Run manuscript tests**

Run:

```bash
make test
```

Expected: all manuscript and data tests pass.

- [ ] **Step 8: Commit the complete scientific draft**

```bash
git add tracks/qmc/solutions/卧龙凤雏/prb-paper/paper.tex \
  tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_manuscript.py
git commit -m "docs: complete PRB four-model manuscript"
```

---

### Task 6: Compile and Automatically Verify the PRB PDF

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/verify_pdf.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_pdf.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/Makefile`

**Interfaces:**
- Consumes: `paper.tex`, `references.bib`, generated macros, and eight figures.
- Produces: a checked `paper.pdf` and stable output copy.

- [ ] **Step 1: Write PDF validation tests**

```python
def test_pdf_is_prb_shaped_and_complete(compiled_pdf):
    result = verify_pdf(compiled_pdf)
    assert 14 <= result.page_count <= 22
    assert result.page_width_points == pytest.approx(612.0, abs=1.0)
    assert result.page_height_points == pytest.approx(792.0, abs=1.0)
    assert result.figure_xobjects >= 8
    assert result.has_embedded_fonts


def test_pdf_contains_required_scientific_language(compiled_pdf):
    text = extract_text(compiled_pdf)
    for phrase in (
        "PHYSICAL REVIEW B",
        "Xu Tian",
        "Huidan Tan",
        "Data Availability",
        "Author Contributions",
        "Exploratory Learning-Induced",
        "does not constitute a universal-central-charge estimate",
    ):
        assert phrase in text
```

- [ ] **Step 2: Run the PDF tests and verify failure**

Run:

```bash
make test
```

Expected: PDF tests fail because no compiled PDF exists.

- [ ] **Step 3: Implement `verify_pdf.py`**

Return a structured result:

```python
@dataclass(frozen=True)
class PdfVerification:
    page_count: int
    page_width_points: float
    page_height_points: float
    figure_xobjects: int
    has_embedded_fonts: bool
    text_sha256: str
```

Use pypdf to extract text, inspect every media box, count image XObjects, and
Form XObjects, and check that font descriptors contain embedded font files.
Fail on missing sections, malformed pages, fewer than eight combined figure
objects, or visible placeholder markers.

- [ ] **Step 4: Compile with strict LaTeX settings**

Run:

```bash
make figures
latexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex
```

Then fail the build if `paper.log` contains:

```text
LaTeX Warning: There were undefined references
LaTeX Warning: Citation
```

Parse every overfull `\hbox` or `\vbox` warning and fail when the reported
overflow exceeds 1.0 pt. Allow underfull boxes only when visual inspection
shows no defect.

- [ ] **Step 5: Run automatic verification and publish the stable PDF**

Run:

```bash
make verify
mkdir -p ../../../../../output/pdf
cp paper.pdf ../../../../../output/pdf/effective-central-charges-prb-paper.pdf
make test
```

Expected: compilation, verification, and all tests pass.

- [ ] **Step 6: Commit the build and PDF**

```bash
git add tracks/qmc/solutions/卧龙凤雏/prb-paper \
  output/pdf/effective-central-charges-prb-paper.pdf
git commit -m "docs: build and verify PRB four-model paper"
```

---

### Task 7: Page-by-Page Visual QA and Final Scientific Audit

**Files:**
- Modify as needed: `tracks/qmc/solutions/卧龙凤雏/prb-paper/paper.tex`
- Modify as needed: `tracks/qmc/solutions/卧龙凤雏/prb-paper/build_figures.py`
- Modify: `output/pdf/effective-central-charges-prb-paper.pdf`

**Interfaces:**
- Consumes: the latest compiled PDF and all frozen source artifacts.
- Produces: final visually clean PDF and a clean, verified Git worktree.

- [ ] **Step 1: Render every page at inspection resolution**

Run:

```bash
mkdir -p tmp/pdfs/pages
/usr/local/bin/gs -q -dSAFER -dBATCH -dNOPAUSE \
  -sDEVICE=png16m -r144 \
  -sOutputFile=tmp/pdfs/pages/page-%03d.png paper.pdf
```

- [ ] **Step 2: Build contact sheets for global layout inspection**

Use Pillow to make contact sheets of no more than 12 pages each. Inspect title
page balance, section transitions, figure placement, appendix density, and
reference flow.

- [ ] **Step 3: Inspect every page at high resolution**

Check:

- no clipped text or figure panels;
- no overlapping equations, captions, or footnotes;
- no black boxes or missing glyphs;
- readable axis labels at 100% zoom;
- consistent panel letters and caption order;
- tables fit within one or two columns;
- references contain titles and do not overflow;
- page numbers and running headers are present;
- learning-MIT figures and captions visibly say `exploratory`.

- [ ] **Step 4: Correct defects and repeat compilation plus inspection**

For every correction:

```bash
make verify
cp paper.pdf ../../../../../output/pdf/effective-central-charges-prb-paper.pdf
/usr/local/bin/gs -q -dSAFER -dBATCH -dNOPAUSE \
  -sDEVICE=png16m -r144 \
  -sOutputFile=tmp/pdfs/pages/page-%03d.png paper.pdf
```

Repeat until the newest page renders contain zero observed layout defects.

- [ ] **Step 5: Run the final source and claim audit**

Run:

```bash
make test
make verify
rg -n "TODO|TBD|PLACEHOLDER|undefined citation" paper.tex references.bib generated
git diff --check -- . ':(exclude)output/pdf/*.pdf'
git status --short
```

Expected:

- all tests pass;
- all PDF verification checks pass;
- the placeholder scan returns no matches;
- non-PDF diffs contain no whitespace errors;
- only intentional final changes remain.

- [ ] **Step 6: Commit any visual-QA corrections**

```bash
git add tracks/qmc/solutions/卧龙凤雏/prb-paper \
  output/pdf/effective-central-charges-prb-paper.pdf
git commit -m "fix: polish PRB paper layout and claim boundaries"
```

- [ ] **Step 7: Perform completion verification**

Run the complete suite one final time from the paper directory:

```bash
make test
make verify
git status --short
```

Record the exact test count, PDF page count, current commit, and stable PDF
path before offering branch-integration choices.
