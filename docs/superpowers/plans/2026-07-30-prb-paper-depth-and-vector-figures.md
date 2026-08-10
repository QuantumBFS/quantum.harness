# PRB Paper Depth and Vector-Figure Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every raster-wrapped scientific panel with a data-native vector figure and expand the PRB manuscript into a detailed, accessible, and academically rigorous treatment of all four models.

**Architecture:** Preserve `paper_data.py` as the hash-gated source of headline claims and add `vector_data.py` as a plot-oriented adapter for processed CSV/JSON artifacts. Rebuild all eight figures exclusively from Matplotlib vector artists, then expand the bibliography and manuscript while retaining frozen values and conservative claim gates. Compile, structurally verify, render, and visually inspect the final PDF before replacing the stable artifact.

**Tech Stack:** Python 3.9+, NumPy 2.0.2, Matplotlib 3.9.4, pypdf 5.9.0, pytest 8.3.5, REVTeX 4.2, BibTeX, Ghostscript.

## Global Constraints

- Do not rerun Monte Carlo or alter any frozen result artifact.
- Do not change the four reported numerical results or their confidence intervals.
- Keep the learning-induced MIT central charge unpublished and exploratory.
- Generate all scientific panels from numeric CSV/JSON/bootstrap data; do not read PNG files.
- Generated figure PDFs must contain no `/Image` XObjects.
- Use American English and the existing PRB Regular Article format.
- Use title-complete primary or authoritative references with DOI, ISBN, or arXiv identifiers.
- Keep the stable final artifact at `output/pdf/effective-central-charges-prb-paper.pdf`.
- The stable PDF must be byte-identical to the latest verified package build.

---

### Task 1: Add a Validated Vector-Plot Data Layer

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/vector_data.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_vector_data.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/conftest.py`

**Interfaces:**
- Consumes: the repository root and the existing processed CSV/JSON artifacts selected by `paper_data.py`.
- Produces: `VectorPlotData load_vector_plot_data(repo_root: Path)`.

- [ ] **Step 1: Write immutable record types in the failing tests**

Add tests that import:

```python
from vector_data import load_vector_plot_data
```

The returned object must expose:

```python
data.clean.free_energy
data.clean.charge_fits
data.clean.diagnostics
data.nishimori.free_energy
data.nishimori.bootstrap
data.weak.finite_size
data.weak.fit_variants
data.weak.diagnostics
data.learning.xy_evidence
data.learning.diii_evidence
data.learning.entanglement
data.learning.casimir
data.learning.anisotropy
data.learning.estimator_comparison
data.learning.claim_reasons
```

Assert exact sentinels:

```python
assert data.clean.free_energy[0].width == 4
assert data.clean.free_energy[-1].width == 20
assert data.clean.charge_fits[3].estimate == pytest.approx(0.4987390622675896)
assert len(data.nishimori.bootstrap) == 4000
assert data.nishimori.free_energy[-1].width == 14
assert data.weak.finite_size[-1].width == 32
assert len(data.learning.xy_evidence) == 6
assert len(data.learning.diii_evidence) == 10
assert data.learning.claim_reasons == (
    "diii_transition_not_bracketed",
    "anisotropy_unstable",
    "estimator_disagreement",
)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
cd tracks/qmc/solutions/卧龙凤雏/prb-paper
.venv/bin/python -m pytest tests/test_vector_data.py -q
```

Expected: collection fails because `vector_data` does not exist.

- [ ] **Step 3: Implement typed scalar records**

Use frozen dataclasses with tuples of scalars rather than mutable NumPy arrays:

```python
@dataclass(frozen=True)
class FreeEnergyPoint:
    width: int
    value: float
    standard_error: float
    fitted: float
    residual: float


@dataclass(frozen=True)
class BootstrapPoint:
    sample: int
    primary: float
    alternate: float


@dataclass(frozen=True)
class EvidencePoint:
    phi_pi: float
    score: float
```

Define focused frozen containers `CleanVectorData`, `NishimoriVectorData`,
`WeakVectorData`, `LearningVectorData`, and `VectorPlotData`.

- [ ] **Step 4: Implement strict CSV and JSON readers**

Implement:

```python
def _csv_rows(path: Path, required: tuple[str, ...]) -> tuple[dict[str, str], ...]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        missing = tuple(name for name in required if name not in fieldnames)
        if missing:
            raise ValueError(f"{path}: missing columns: {', '.join(missing)}")
        rows = tuple(dict(row) for row in reader)
    if not rows:
        raise ValueError(f"{path}: table is empty")
    return rows


def _finite(value: str, source: Path, column: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{source}: nonfinite {column}: {value}")
    return number


def load_vector_plot_data(repo_root: Path) -> VectorPlotData:
    root = Path(repo_root).resolve()
    headline = load_paper_data(root)
    return VectorPlotData(
        clean=_load_clean(root, headline.clean),
        nishimori=_load_nishimori(root, headline.nishimori),
        weak=_load_weak(root, headline.weak),
        learning=_load_learning(root, headline.learning),
    )
```

Reject missing columns, empty tables, nonfinite values, duplicate widths,
bootstrap samples other than 4000, and a learning summary hash other than:

```text
cc08a6e6d6d414046c744b4d29d48f112d44526dfc2145b867aae01f07d53c33
```

For learning data, parse `summary.json` directly only after
`load_paper_data(repo_root)` has validated the frozen source selection.

- [ ] **Step 5: Run the focused and complete tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_vector_data.py -q
make test
```

Expected: all tests pass.

- [ ] **Step 6: Commit the vector-data contract**

```bash
git add tracks/qmc/solutions/卧龙凤雏/prb-paper/vector_data.py \
  tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_vector_data.py
git commit -m "feat: add validated vector plot data"
```

---

### Task 2: Rebuild Benchmark Figures as Native Vector Graphics

**Files:**
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/build_figures.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_figures.py`

**Interfaces:**
- Consumes: `VectorPlotData` from Task 1.
- Produces: vector-native `fig01` through `fig05` with the existing filenames.

- [ ] **Step 1: Add a PDF-vector regression test**

Use pypdf to inspect every generated figure:

```python
def _xobject_subtypes(path):
    reader = PdfReader(path)
    return {
        str(obj.get_object().get("/Subtype"))
        for page in reader.pages
        for obj in page.get("/Resources", {}).get("/XObject", {}).values()
    }


def test_generated_figures_do_not_embed_raster_images(repo_root, tmp_path):
    paths = build_all_figures(repo_root, tmp_path)
    for path in paths:
        assert "/Image" not in _xobject_subtypes(path), path.name
```

Also assert:

```python
source = (paper_dir / "build_figures.py").read_text()
assert "matplotlib.image" not in source
assert "mpimg" not in source
assert "_image_grid" not in source
```

- [ ] **Step 2: Run the figure tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_figures.py -q
```

Expected: the source assertion fails because the current implementation reads
PNG files through `matplotlib.image`.

- [ ] **Step 3: Establish the publication style**

Set:

```python
plt.rcParams.update({
    "font.size": 9.0,
    "axes.labelsize": 9.0,
    "axes.titlesize": 9.5,
    "legend.fontsize": 8.5,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "lines.linewidth": 1.4,
    "lines.markersize": 5.0,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})
```

Add helpers:

```python
def _panel_label(axis, label: str) -> None:
    axis.text(-0.14, 1.08, label, transform=axis.transAxes,
              fontweight="bold", va="top")


def _finish_axis(axis) -> None:
    axis.grid(alpha=0.22, linewidth=0.6)
    axis.tick_params(direction="out")
```

- [ ] **Step 4: Redraw Figure 1**

Keep the validation-ladder concept but enlarge all text, align boxes to a
common grid, and show the sequence:

```text
exact oracle -> sampling validation -> finite-size stability -> claim gates
```

Use patches, arrows, and text only.

- [ ] **Step 5: Redraw Figure 2**

Build three panels from clean CSV data:

- `(a)` `g(L)/L` versus `1/L^2`, exact and MC with uncertainty;
- `(b)` residuals of exact and MC values relative to the primary fit;
- `(c)` central-charge estimates for `L_min = 4, 6, 8`, separating exact and
  Monte Carlo and marking `c = 1/2`.

Use circles/solid lines for MC, squares/dashed lines for exact values, and a
horizontal reference line for `1/2`.

- [ ] **Step 6: Redraw Figure 3**

Build three panels:

- `(a)` Nishimori quenched free energy and `L^-2 + L^-4` fit;
- `(b)` density-normalized histogram of 4000 `c_lmin4` bootstrap values with
  estimate and reference lines;
- `(c)` paired `L_min=4` and `L_min=6` estimates with 95% intervals and a
  line connecting their centers.

State “ordinary quenched” in the figure subtitle or caption.

- [ ] **Step 7: Redraw Figure 4**

Build four panels:

- `(a)` `gamma_1(L)` and the fitted curve;
- `(b)` studentized residuals with `+/-3` limits;
- `(c)` the electric-magnetic self-duality statistic with a `+/-1.96` band;
- `(d)` effective sample size by width with an ESS=100 threshold.

Load the self-duality and ESS arrays from the validated weak-model diagnostics
stored in the summary/oracle and block artifacts.

- [ ] **Step 8: Redraw Figure 5**

Use two panels:

- `(a)` estimates and 95% intervals against their reference values;
- `(b)` standardized deviations `(estimate-reference)/SE` with `+/-1` and
  `+/-2` guide bands.

- [ ] **Step 9: Run tests and render Figures 1--5**

Run:

```bash
make figures
.venv/bin/python -m pytest tests/test_figures.py -q
mkdir -p tmp/pdfs/vector-review
for f in generated/fig0{1,2,3,4,5}-*.pdf; do
  /usr/local/bin/gs -q -dSAFER -dBATCH -dNOPAUSE \
    -sDEVICE=png16m -r200 \
    -sOutputFile="tmp/pdfs/vector-review/$(basename "${f%.pdf}").png" "$f"
done
```

Inspect axis labels, marker distinction, legends, and panel order at full
resolution.

- [ ] **Step 10: Commit the vector benchmark figures**

```bash
git add tracks/qmc/solutions/卧龙凤雏/prb-paper/build_figures.py \
  tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_figures.py
git commit -m "feat: redraw benchmark figures as vectors"
```

---

### Task 3: Rebuild Learning-Induced MIT Figures as Native Vectors

**Files:**
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/build_figures.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_figures.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/vector_data.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_vector_data.py`

**Interfaces:**
- Consumes: the production-v2 learning summary, block records, and validated
  plot records.
- Produces: vector-native `fig06`, `fig07`, and `fig08`.

- [ ] **Step 1: Add exact panel-content tests**

Assert the plot data contain:

```python
assert data.learning.xy_bracket == pytest.approx((0.24, 0.25))
assert data.learning.candidate_phi_pi == pytest.approx(0.30)
assert data.learning.diii_bracket is None
assert data.learning.entanglement.value == pytest.approx(3.060739513110786)
assert data.learning.casimir.value == pytest.approx(12.579932843147617)
assert data.learning.anisotropy.stable is False
assert data.learning.estimator_comparison.agrees is False
```

Add a PDF text test confirming that Figures 6--8 contain the words
`bracketed`, `unbracketed`, and `exploratory`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_vector_data.py tests/test_figures.py -q
```

Expected: the new fields and embedded PDF text are absent.

- [ ] **Step 3: Extend the learning plot records**

Parse:

- XY and DIII evidence arrays;
- entanglement chord coordinates, entropy, uncertainties, and fitted values;
- per-width effective coefficients, standard errors, extrapolated values, and
  model weights;
- Casimir widths, observed values, errors, fitted values, and residuals;
- spatial and temporal anisotropy sequences and window estimates;
- estimator values, intervals, difference, and compatibility threshold;
- claim reasons and Boolean publication flag.

Validate matching vector lengths and finite values.

- [ ] **Step 4: Redraw Figure 6**

Use two panels with shared styling:

- `(a)` XY scan, shaded reference window, highlighted bracket
  `[0.24, 0.25]`, and text `bracketed`;
- `(b)` DIII scan, candidate line at `0.30`, scan boundary at `0.32`, and text
  `unbracketed / exploratory`.

Do not draw an inferred crossing for DIII.

- [ ] **Step 5: Redraw Figure 7**

Use three panels:

- `(a)` entropy versus chord logarithm at width 32 with uncertainties and fit;
- `(b)` per-width effective coefficients and large-width extrapolation;
- `(c)` horizontal model-weight bars for the five candidate extrapolation
  models.

Make the large covariance condition number visible in the caption, not as a
decorative plot annotation.

- [ ] **Step 6: Redraw Figure 8**

Use four panels:

- `(a)` Casimir observable and fitted curve;
- `(b)` spatial and temporal anisotropy sequences versus width;
- `(c)` entanglement and nominal Casimir `c_eff` values with 95% intervals;
- `(d)` three claim gates shown as pass/fail categorical markers.

Place a visible `EXPLORATORY - NO UNIVERSAL c_eff CLAIM` banner above the
panels.

- [ ] **Step 7: Verify vector structure and visual readability**

Run:

```bash
make figures
.venv/bin/python -m pytest \
  tests/test_vector_data.py tests/test_figures.py -q
for f in generated/fig0{6,7,8}-*.pdf; do
  /usr/local/bin/gs -q -dSAFER -dBATCH -dNOPAUSE \
    -sDEVICE=png16m -r200 \
    -sOutputFile="tmp/pdfs/vector-review/$(basename "${f%.pdf}").png" "$f"
done
```

Inspect every panel at original rendered resolution. Reject any axis label
that cannot be read without zooming beyond 100%.

- [ ] **Step 8: Commit the vector learning figures**

```bash
git add tracks/qmc/solutions/卧龙凤雏/prb-paper/build_figures.py \
  tracks/qmc/solutions/卧龙凤雏/prb-paper/vector_data.py \
  tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_figures.py \
  tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_vector_data.py
git commit -m "feat: redraw exploratory MIT figures as vectors"
```

---

### Task 4: Expand and Verify the Scientific Bibliography

**Files:**
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/references.bib`
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_bibliography.py`

**Interfaces:**
- Consumes: publisher, Crossref, arXiv, and DOI metadata from primary sources.
- Produces: a title-complete bibliography used by the expanded manuscript.

- [ ] **Step 1: Add required-key tests**

Extend the required bibliography set with:

```text
WilsonKogut1974
Cardy1984
BelavinPolyakovZamolodchikov1984
DiFrancescoMathieuSenechal1997
Harris1974
Ludwig1987
GruzbergReadLudwig2001
NishimoriNemoto2002
MerzChalker2002
ChalkerCoddington1988
EversMirlin2008
SchnyderRyuFurusakiLudwig2008
RyuSchnyderFurusakiLudwig2010
Kitaev2009
GullansHuse2020
BaoChoiAltman2020
JianYouVasseurLudwig2020
ZabaloGullansWilsonGopalakrishnanHusePixley2020
LuntSzyniszewskiPal2019
AlbertonBuchholdDiehl2021
```

Keep the title, author, year, and identifier checks for every entry.

- [ ] **Step 2: Run bibliography tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_bibliography.py -q
```

Expected: required keys are missing.

- [ ] **Step 3: Verify exact metadata from primary sources**

Use official publisher pages, DOI landing pages, Crossref, or arXiv. Record the
following canonical works:

- Wilson and Kogut, *The renormalization group and the epsilon expansion*,
  Phys. Rep. 12, 75 (1974), DOI
  `10.1016/0370-1573(74)90023-4`.
- Cardy, *Conformal invariance and universality in finite-size scaling*,
  J. Phys. A 17, L385 (1984), DOI `10.1088/0305-4470/17/7/003`.
- Belavin, Polyakov, and Zamolodchikov, *Infinite conformal symmetry in
  two-dimensional quantum field theory*, Nucl. Phys. B 241, 333 (1984), DOI
  `10.1016/0550-3213(84)90052-X`.
- Di Francesco, Mathieu, and Senechal, *Conformal Field Theory*, ISBN
  `978-0-387-94785-3`.
- Harris, *Effect of random defects on the critical behaviour of Ising
  models*, J. Phys. C 7, 1671 (1974), DOI
  `10.1088/0022-3719/7/9/009`.
- Ludwig, *Critical behavior of the two-dimensional random q-state Potts
  model by expansion in (q-2)*, Nucl. Phys. B 285, 97 (1987), DOI
  `10.1016/0550-3213(87)90412-1`.
- Gruzberg, Read, and Ludwig, *Random-bond Ising model in two dimensions: The
  Nishimori line and supersymmetry*, Phys. Rev. B 63, 104422 (2001), DOI
  `10.1103/PhysRevB.63.104422`.
- Nishimori and Nemoto, *Duality and multicritical point of two-dimensional
  spin glasses*, J. Phys. Soc. Jpn. 71, 1198 (2002), DOI
  `10.1143/JPSJ.71.1198`.
- Merz and Chalker, *Two-dimensional random-bond Ising model, free fermions,
  and the network model*, Phys. Rev. B 65, 054425 (2002), DOI
  `10.1103/PhysRevB.65.054425`.
- Chalker and Coddington, *Percolation, quantum tunnelling and the integer Hall
  effect*, J. Phys. C 21, 2665 (1988), DOI
  `10.1088/0022-3719/21/14/008`.
- Evers and Mirlin, *Anderson transitions*, Rev. Mod. Phys. 80, 1355 (2008),
  DOI `10.1103/RevModPhys.80.1355`.
- Schnyder, Ryu, Furusaki, and Ludwig, *Classification of topological
  insulators and superconductors in three spatial dimensions*, Phys. Rev. B
  78, 195125 (2008), DOI `10.1103/PhysRevB.78.195125`.
- Ryu, Schnyder, Furusaki, and Ludwig, *Topological insulators and
  superconductors: tenfold way and dimensional hierarchy*, New J. Phys. 12,
  065010 (2010), DOI `10.1088/1367-2630/12/6/065010`.
- Kitaev, *Periodic table for topological insulators and superconductors*,
  AIP Conf. Proc. 1134, 22 (2009), DOI `10.1063/1.3149495`.
- Gullans and Huse, *Dynamical purification phase transition induced by
  quantum measurements*, Phys. Rev. X 10, 041020 (2020), DOI
  `10.1103/PhysRevX.10.041020`.
- Bao, Choi, and Altman, *Theory of the phase transition in random unitary
  circuits with measurements*, Phys. Rev. B 101, 104301 (2020), DOI
  `10.1103/PhysRevB.101.104301`.
- Jian, You, Vasseur, and Ludwig, *Measurement-induced criticality in random
  quantum circuits*, Phys. Rev. B 101, 104302 (2020), DOI
  `10.1103/PhysRevB.101.104302`.
- Zabalo et al., *Critical properties of the measurement-induced transition
  in random quantum circuits*, Phys. Rev. B 101, 060301(R) (2020), DOI
  `10.1103/PhysRevB.101.060301`.
- Lunt, Szyniszewski, and Pal, *Measurement-induced criticality and
  entanglement clusters: A study of one-dimensional and two-dimensional
  Clifford circuits*, Phys. Rev. B 100, 224303 (2019), DOI
  `10.1103/PhysRevB.100.224303`.
- Alberton, Buchhold, and Diehl, *Entanglement transition in a monitored
  free-fermion chain: From extended criticality to area law*, Phys. Rev. Lett.
  126, 170602 (2021), DOI `10.1103/PhysRevLett.126.170602`.

- [ ] **Step 4: Add the verified BibTeX entries**

Use braces to preserve acronyms and proper names. For articles, include
`author`, `title`, `journal`, `volume`, `pages` or article number, `year`, and
`doi`. For the textbook, include publisher, address, year, and ISBN.

- [ ] **Step 5: Run bibliography tests and BibTeX**

Run:

```bash
.venv/bin/python -m pytest tests/test_bibliography.py -q
latexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex
```

Expected: bibliography metadata tests and BibTeX complete without missing-field
errors.

- [ ] **Step 6: Commit the expanded bibliography**

```bash
git add tracks/qmc/solutions/卧龙凤雏/prb-paper/references.bib \
  tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_bibliography.py
git commit -m "docs: expand PRB scientific bibliography"
```

---

### Task 5: Rewrite the Introduction with Breadth and Depth

**Files:**
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/paper.tex`
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_manuscript.py`

**Interfaces:**
- Consumes: the expanded bibliography and the approved eight-layer narrative.
- Produces: a self-contained Introduction of approximately 2200--3200 words.

- [ ] **Step 1: Add narrative-coverage tests**

Extract the Introduction between `sec:introduction` and `sec:models`. Assert:

```python
assert 2200 <= english_word_count(introduction) <= 3200
```

Require the terms:

```text
renormalization group
correlation length
relevant perturbation
universality class
Virasoro
conformal anomaly
Casimir
quenched
annealed
replica
Nishimori line
gauge
self-duality
Born
measurement-induced
Altland--Zirnbauer
DIII
metal--insulator transition
anisotropy
claim gate
```

Require citations from every conceptual group:

```text
WilsonKogut1974
BelavinPolyakovZamolodchikov1984
Harris1974
GruzbergReadLudwig2001
EversMirlin2008
SchnyderRyuFurusakiLudwig2008
GullansHuse2020
JianYouVasseurLudwig2020
```

- [ ] **Step 2: Run manuscript tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_manuscript.py -q
```

Expected: the current short Introduction fails length, terminology, and
citation coverage.

- [ ] **Step 3: Write the critical-phenomena foundation**

Explain:

- the correlation length `xi ~ |t|^-nu`;
- scale invariance at `xi -> infinity`;
- coarse graining and renormalization-group flow;
- fixed points, relevant/irrelevant perturbations, and universality;
- finite-size scaling as replacing the divergent correlation length by `L`.

Keep equations minimal and define every symbol immediately.

- [ ] **Step 4: Write the CFT and central-charge foundation**

Explain:

- local conformal symmetry in two dimensions;
- the Virasoro central extension;
- conformal anomaly on a cylinder;
- `f(L) = f_inf - pi c/(6L^2) + O(L^-4)`;
- entanglement chord scaling;
- why agreement of independent observables is stronger than a single good
  regression.

- [ ] **Step 5: Write the disorder and Nishimori context**

Explain annealed versus quenched free energies, the replica derivative
interpretation, effective central charge, the Harris criterion, Nishimori
gauge identities, and the multicritical point. State explicitly that `0.464`
and `0.522` refer to different disorder/replica observables.

- [ ] **Step 6: Write the monitored and topological context**

Explain trajectory ensembles, measurement-induced entanglement transitions,
Born weighting, Gaussian fermions, network models, tenfold-way class DIII,
localized topological phases, and a possible intervening two-dimensional
metal.

- [ ] **Step 7: Write the validation problem and contributions**

Explain why finite-size bias, correlated disorder, anisotropy, and estimator
definition can invalidate a precise-looking number. Present the four models as
a validation ladder and state the accepted claims without overstating the
learning-induced result.

- [ ] **Step 8: Run tests and compile the Introduction**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_manuscript.py tests/test_bibliography.py -q
latexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex
```

Inspect the first four pages for readable paragraph length, equation placement,
and citation density.

- [ ] **Step 9: Commit the expanded Introduction**

```bash
git add tracks/qmc/solutions/卧龙凤雏/prb-paper/paper.tex \
  tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_manuscript.py
git commit -m "docs: expand PRB introduction and physical context"
```

---

### Task 6: Deepen Models, Methods, Results, Discussion, and Appendices

**Files:**
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/paper.tex`
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_manuscript.py`

**Interfaces:**
- Consumes: frozen numerical values, vector figures, and the expanded
  bibliography.
- Produces: a detailed manuscript whose prose explains each calculation,
  parameter, result, limitation, and error mechanism.

- [ ] **Step 1: Add detailed-content tests**

Require a notation table and labels:

```text
tab:notation
sec:statistical-estimators
sec:systematic-errors
app:fit-models
```

Require exact explanatory phrases or equivalent stable sentences covering:

```text
independent sampling unit
thermal uncertainty
quenched-disorder uncertainty
finite-size truncation
transition-location uncertainty
anisotropy uncertainty
more Monte Carlo steps
larger system sizes
does not constitute a universal-central-charge estimate
```

Assert each main figure is referenced before or in the paragraph that
interprets it.

- [ ] **Step 2: Run manuscript tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_manuscript.py -q
```

Expected: new labels and expanded explanations are absent.

- [ ] **Step 3: Expand Models and universal observables**

Add:

- a notation table defining `L`, `M`, `K`, `p`, `phi`, `alpha`, `f`,
  `gamma_1`, `S`, `c`, `c_eff`, and confidence intervals;
- the clean and random-bond partition functions;
- the Nishimori condition and quenched averaging order;
- the Gaussian covariance and Born probability;
- the monitored DIII network interpretation;
- derivations connecting each stored observable to a finite-size coefficient.

- [ ] **Step 4: Expand Numerical methods**

Explain the implementation principle and controlled error for:

- Xoshiro256++ stream assignment;
- Wolff clusters and thermalization;
- Rao--Blackwell conditional expectations;
- nested-grid thermodynamic integration;
- matrix-free transfer products and per-row normalization;
- Gaussian covariance invariants;
- independent sampling units;
- hierarchical and paired bootstrap;
- common-disorder comparisons;
- fit corrections and predeclared windows.

Create subsections `Statistical estimators` and `Systematic errors` with the
required labels.

- [ ] **Step 5: Expand all benchmark Results**

For Clean Ising, Nishimori, and Weak self-dual, explain each figure using:

1. observable and axes;
2. reason for the calculation;
3. numerical outcome and uncertainty;
4. implementation or physics gate;
5. limitation of the result.

Retain all frozen values verbatim through generated macros.

- [ ] **Step 6: Expand the learning-induced MIT Results**

Explain:

- why XY is a positive-control bracket;
- why monotone DIII evidence is not a bracket;
- why `phi/pi = 0.30` is an exploratory boundary candidate;
- the chord-fit and extrapolation stages;
- the covariance condition number;
- the Casimir amplitude and the role of `alpha`;
- the estimator difference and combined compatibility threshold;
- why all three claim gates fail.

- [ ] **Step 7: Expand the cross-model Discussion**

Compare:

- exact versus stochastic validation;
- thermal versus quenched uncertainty;
- ordinary quenched versus Born/higher-replica effective charges;
- additional steps versus additional independent streams;
- additional steps versus larger widths;
- regression uncertainty versus model/observable uncertainty.

Give a staged next calculation: extend the DIII scan, calibrate aspect ratios,
increase widths, then repeat paired estimator comparison.

- [ ] **Step 8: Expand Appendices**

Add `Appendix: Fit models and window selection` with label `app:fit-models`.
Document:

- leading and correction terms for all four models;
- why the chosen powers are used;
- the diagnostic `L_min` variants;
- percentile bootstrap construction;
- common-disorder difference intervals;
- machine-readable claim-gate logic.

- [ ] **Step 9: Run tests and compile**

Run:

```bash
make test
make verify
rg -n "FIXME|XXX|undefined citation" \
  paper.tex references.bib generated
```

Expected: all tests and PDF checks pass; the scan returns no matches.

- [ ] **Step 10: Commit the detailed full manuscript**

```bash
git add tracks/qmc/solutions/卧龙凤雏/prb-paper/paper.tex \
  tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_manuscript.py
git commit -m "docs: deepen PRB analysis and error discussion"
```

---

### Task 7: Verify Vector Purity and Perform Final PDF QA

**Files:**
- Modify as needed: `tracks/qmc/solutions/卧龙凤雏/prb-paper/build_figures.py`
- Modify as needed: `tracks/qmc/solutions/卧龙凤雏/prb-paper/paper.tex`
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/verify_pdf.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/prb-paper/tests/test_pdf.py`
- Replace: `output/pdf/effective-central-charges-prb-paper.pdf`

**Interfaces:**
- Consumes: the expanded manuscript, bibliography, vector figures, and
  generated macros.
- Produces: the final verified, visually inspected stable PDF.

- [ ] **Step 1: Strengthen compiled-PDF vector checks**

Recursively inspect every page Form XObject. Distinguish the eight imported
figure forms from font resources and assert that no nested resource contains
an `/Image` subtype:

```python
def image_xobject_count(resources, seen=None) -> int:
    visited = set() if seen is None else seen
    total = 0
    for reference in resources.get("/XObject", {}).values():
        identity = getattr(reference, "idnum", id(reference))
        if identity in visited:
            continue
        visited.add(identity)
        obj = reference.get_object()
        subtype = obj.get("/Subtype")
        if subtype == "/Image":
            total += 1
        elif subtype == "/Form":
            total += image_xobject_count(obj.get("/Resources", {}), visited)
    return total


assert result.figure_xobjects >= 8
assert result.image_xobjects == 0
```

Require the final PDF to contain the expanded section headings and all eight
figure captions.

- [ ] **Step 2: Run PDF tests and verify RED if raster content remains**

Run:

```bash
make manuscript
.venv/bin/python -m pytest tests/test_pdf.py -q
```

Expected before the final vector conversion is complete: the nested
Image-XObject assertion fails. Expected after Tasks 2 and 3: it passes.

- [ ] **Step 3: Perform a clean rebuild**

Run:

```bash
make clean
make figures
latexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex
.venv/bin/python verify_pdf.py paper.pdf
```

Reject the build if `paper.log` contains undefined references, natbib citation
warnings, stuck floats, or overfull boxes above 1 pt.

- [ ] **Step 4: Render every page at 200 dpi**

Run:

```bash
mkdir -p tmp/pdfs/final-pages
/usr/local/bin/gs -q -dSAFER -dBATCH -dNOPAUSE \
  -sDEVICE=png16m -r200 \
  -sOutputFile=tmp/pdfs/final-pages/page-%03d.png paper.pdf
```

Create contact sheets with no more than ten pages each and inspect every page
individually at original rendered resolution.

- [ ] **Step 5: Apply the visual acceptance checklist**

Confirm:

- every axis label and legend is readable at 100%;
- curves, markers, and error bars remain sharp under magnification;
- no panel is a screenshot;
- no caption is detached from its figure;
- no equation, table, or citation is clipped;
- paragraph density is readable;
- the Introduction has a clear progression rather than a literature list;
- `0.464` and `0.522` are visibly distinguished;
- learning-MIT figures and prose say exploratory;
- references are title-complete and fit within the columns.

Correct any defect and repeat Steps 3--5.

- [ ] **Step 6: Publish the stable PDF**

Run:

```bash
cp paper.pdf ../../../../../output/pdf/effective-central-charges-prb-paper.pdf
cmp -s paper.pdf ../../../../../output/pdf/effective-central-charges-prb-paper.pdf
shasum -a 256 ../../../../../output/pdf/effective-central-charges-prb-paper.pdf
```

- [ ] **Step 7: Run the final completion gate**

Run:

```bash
make test
make verify
git diff --check
git status --short
```

Record the test count, page count, vector figure count, image-XObject count,
PDF SHA-256, current commit, and stable path.

- [ ] **Step 8: Commit the final verified artifact**

```bash
git add tracks/qmc/solutions/卧龙凤雏/prb-paper \
  output/pdf/effective-central-charges-prb-paper.pdf
git commit -m "docs: publish expanded vector PRB paper"
```
