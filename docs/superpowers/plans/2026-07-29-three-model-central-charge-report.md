# Three-Model Central-Charge Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a detailed, data-backed English report for university students that integrates the clean Ising, Nishimori Ising, and weak self-dual central-charge studies in matching HTML and PDF formats.

**Architecture:** A Python package validates the three frozen result directories and converts their JSON, CSV, configuration, and figure artifacts into a format-independent report model. Separate HTML and ReportLab renderers consume that same model, while a comparison-plot module produces only cross-model synthesis charts. A build command writes stable artifacts under `output/` and a verification command checks content, provenance, and rendered layout without rerunning any simulation.

**Tech Stack:** Python 3.9+, standard library, NumPy, Matplotlib, Pillow, ReportLab, pypdf, pytest, Poppler (`pdfinfo`, `pdftoppm`)

## Global Constraints

- Report language: English.
- Primary audience: university students.
- PDF length: 25-35 A4 pages.
- Use only the frozen result directories named in the approved design.
- Do not rerun Monte Carlo or modify any frozen source artifact.
- Load headline numbers, confidence intervals, gates, and parameters from source JSON/CSV files.
- Use Xoshiro256++ only as an explained simulation detail; the report generator itself performs no stochastic simulation.
- HTML must be self-contained and work offline.
- HTML and PDF must make the same scientific claims and display the same headline values.
- Final files are `output/html/three-model-central-charge-report.html` and `output/pdf/three-model-central-charge-report.pdf`.
- Stop generation when required input, consistency, gate, or image checks fail.

## File Structure

- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/Makefile`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/requirements.txt`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/pytest.ini`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/__init__.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/sources.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/report_model.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/comparison_plots.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/html_renderer.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/pdf_renderer.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/verify_outputs.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/build_report.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_sources.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_report_model.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_comparison_plots.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_renderers.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/conftest.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/README.md`

---

### Task 1: Scaffold and Frozen-Source Validation

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/requirements.txt`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/pytest.ini`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/__init__.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/sources.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/conftest.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_sources.py`

**Interfaces:**
- Produces: `SourceSpec`, `ModelResult`, `source_specs(repo_root)`, `load_model(spec)`, and `load_all_models(repo_root)`.
- `ModelResult` contains `slug`, `name`, `result_dir`, `target`, `estimate`, `standard_error`, `ci95`, `runtime_s`, `parameters`, `gates`, `figures`, `tables`, and `provenance`.

- [ ] **Step 1: Write source-loader tests**

Create shared fixtures in `tests/conftest.py`. Resolve `repo_root` as six parent
directories above `conftest.py`, and define `models` by calling
`load_all_models(repo_root)`.

```python
from analysis.sources import load_all_models


def test_loads_three_frozen_models(repo_root):
    models = load_all_models(repo_root)
    assert [model.slug for model in models] == [
        "clean-ising", "nishimori-ising", "weak-self-dual"
    ]
    assert models[0].target == 0.5
    assert models[1].target == 0.464
    assert models[2].target == 0.447


def test_intervals_contain_estimates_and_all_required_gates_pass(repo_root):
    for model in load_all_models(repo_root):
        assert model.ci95[0] <= model.estimate <= model.ci95[1]
        assert all(not gate.required or gate.passed for gate in model.gates)
```

- [ ] **Step 2: Run the tests and confirm the missing-module failure**

Run: `.venv/bin/python -m pytest tests/test_sources.py -q`

Expected: FAIL because `analysis.sources` does not exist.

- [ ] **Step 3: Pin the report-only dependencies**

Write exactly:

```text
numpy==2.0.2
matplotlib==3.9.4
Pillow==11.3.0
reportlab==4.4.3
pypdf==5.9.0
pytest==8.3.5
```

These dependencies process existing artifacts only.

- [ ] **Step 4: Implement immutable source declarations and typed records**

Define frozen dataclasses:

```python
@dataclass(frozen=True)
class Gate:
    name: str
    criterion: str
    value: object
    passed: bool
    required: bool


@dataclass(frozen=True)
class ModelResult:
    slug: str
    name: str
    result_dir: Path
    target: float
    estimate: float
    standard_error: float
    ci95: tuple[float, float]
    runtime_s: float
    parameters: tuple[tuple[str, str, str, str], ...]
    gates: tuple[Gate, ...]
    figures: tuple[Path, ...]
    tables: Mapping[str, tuple[Mapping[str, str], ...]]
    provenance: Mapping[str, str]
```

Declare exact source directories from the design. Implement specialized clean,
Nishimori, and weak-self-dual adapters because their schemas differ. For clean
Ising, read the `L_min=6` rows from `central_charge_fits.csv`, use the
transfer-matrix estimate as an exact comparator, derive runtime from the
manifest, and convert `analysis_metadata.json` gates to required `Gate` records.
For the other models, read `processed/summary.json` and `processed/gates.json`.

Validate finite numbers, ordered intervals, target consistency, required gate
success, expected figures, and SHA-256 hashes. Do not read or rewrite raw stream
payloads; provenance hashes cover the processed inputs, manifests, and figures
used by the report.

- [ ] **Step 5: Run loader tests**

Run: `.venv/bin/python -m pytest tests/test_sources.py -q`

Expected: PASS.

- [ ] **Step 6: Commit source loading**

```bash
git add tracks/qmc/solutions/卧龙凤雏/integrated-report
git commit -m "feat: load frozen three-model report data"
```

---

### Task 2: Build the Shared Scientific Report Model

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/report_model.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_report_model.py`

**Interfaces:**
- Consumes: `tuple[ModelResult, ...]`.
- Produces: `ReportDocument`, `Section`, and block dataclasses plus `build_report(models) -> ReportDocument`.
- Blocks are `Paragraph`, `Equation`, `Figure`, `Table`, `Callout`, `CodeBlock`, and `PageBreak`.

- [ ] **Step 1: Write report-coverage tests**

```python
def test_report_has_required_sections(models):
    report = build_report(models)
    titles = [section.title for section in report.sections]
    assert titles == [
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


def test_every_model_has_parameters_equations_errors_and_code(models):
    report = build_report(models)
    for slug in ("clean-ising", "nishimori-ising", "weak-self-dual"):
        section = report.section_for_slug(slug)
        kinds = {block.kind for block in section.blocks}
        assert {"equation", "table", "figure", "code", "callout"} <= kinds
```

- [ ] **Step 2: Run tests and confirm the report-model failure**

Run: `.venv/bin/python -m pytest tests/test_report_model.py -q`

Expected: FAIL because the report model is absent.

- [ ] **Step 3: Implement small immutable report-block types**

Each type has one rendering-independent responsibility. `Figure` stores a source
path, alt text, caption, and inference limit. `Table` stores column definitions
and rows. `Equation` stores display text plus an equation number. `Callout`
stores a semantic level such as `result`, `principle`, `warning`, or `oracle`.

- [ ] **Step 4: Write the complete university-level scientific narrative**

Construct all eleven sections required by the design. Include these core
equations and explain every symbol before use:

```text
f(L) = f_infinity - pi*c/(6*L^2) + a/L^4
F(K_c) = -N*log(2) + integral_0^Kc <H>_K dK
K_N = (1/2)*log((1-p)/p)
phi_L = phi_infinity + pi*c_eff/(6*L^2) + a/L^4
P(s|Gamma) = [1 + s*tanh(beta)<i gamma_a gamma_b>_Gamma]/2
gamma_1(L) = f_infinity*L - pi*c_eff/(6*L) + a/L^3
H_2(q) = -q*log(q) - (1-q)*log(1-q)
```

For each model, include physical setup, computational path, why the estimator is
used, production parameters with meanings and sensitivity, numerical result,
oracles, failure modes, and compact pseudocode. Explicitly distinguish the
ordinary quenched Nishimori value near 0.464 from the different Born/higher
replica quantity near 0.522.

- [ ] **Step 5: Add provenance and glossary appendices**

The provenance table lists every consumed relative path and SHA-256 value. The
glossary defines \(L\), \(M\), \(K\), \(K_c\), \(p\), \(K_N\), \(\phi_L\),
\(\gamma_1\), \(c\), \(c_{\mathrm{eff}}\), SE, CI, ESS, and each correction
coefficient.

- [ ] **Step 6: Run report-model tests**

Run: `.venv/bin/python -m pytest tests/test_report_model.py -q`

Expected: PASS with no placeholder strings.

- [ ] **Step 7: Commit the shared content model**

```bash
git add tracks/qmc/solutions/卧龙凤雏/integrated-report
git commit -m "feat: define integrated scientific report content"
```

---

### Task 3: Generate Cross-Model Comparison Figures

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/comparison_plots.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_comparison_plots.py`

**Interfaces:**
- Consumes: `tuple[ModelResult, ...]` and output `Path`.
- Produces: `Mapping[str, Path]` from `build_comparison_plots(models, output_dir)`.

- [ ] **Step 1: Write plot-contract tests**

```python
def test_builds_four_nonempty_pngs(models, tmp_path):
    paths = build_comparison_plots(models, tmp_path)
    assert set(paths) == {
        "central-charge-intervals",
        "target-deviation",
        "precision-runtime",
        "validation-gates",
    }
    for path in paths.values():
        with Image.open(path) as image:
            assert image.width >= 1200
            assert image.height >= 700
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `.venv/bin/python -m pytest tests/test_comparison_plots.py -q`

Expected: FAIL because plot generation is absent.

- [ ] **Step 3: Implement the four plots**

Use a color-blind-safe palette and 180 DPI or greater. Plot measured estimates
with 95% intervals and separate target markers. Plot target deviation as
\((\hat c-c_\mathrm{target})/\mathrm{SE}\), showing zero and +/-1.96 reference
lines. Plot interval half-width and runtime on clearly separated panels rather
than using a misleading dual axis. Plot required gates as passed/failed/not
applicable and annotate the model-specific denominator.

- [ ] **Step 4: Test and inspect plot metadata**

Run: `MPLCONFIGDIR=/tmp/integrated-report-mpl .venv/bin/python -m pytest tests/test_comparison_plots.py -q`

Expected: PASS and four readable PNG files.

- [ ] **Step 5: Commit comparison figures**

```bash
git add tracks/qmc/solutions/卧龙凤雏/integrated-report
git commit -m "feat: add three-model comparison plots"
```

---

### Task 4: Render a Self-Contained HTML Report

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/html_renderer.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_renderers.py`

**Interfaces:**
- Consumes: `ReportDocument` and destination `Path`.
- Produces: `render_html(report, destination) -> Path`.

- [ ] **Step 1: Write HTML rendering tests**

```python
def test_html_is_offline_self_contained(report, tmp_path):
    output = render_html(report, tmp_path / "report.html")
    html = output.read_text(encoding="utf-8")
    assert "<!doctype html>" in html.lower()
    assert "data:image/png;base64," in html
    assert "http://" not in html and "https://" not in html
    assert all(title in html for title in REQUIRED_SECTION_TITLES)
    assert "0.499424" in html
    assert "0.456469" in html
    assert "0.444107" in html
```

- [ ] **Step 2: Run the test and confirm the missing-renderer failure**

Run: `.venv/bin/python -m pytest tests/test_renderers.py::test_html_is_offline_self_contained -q`

Expected: FAIL because `render_html` is absent.

- [ ] **Step 3: Implement semantic HTML and embedded styling**

Render a title/abstract block, sticky table of contents, result cards, numbered
sections, equation panels, striped parameter tables, figure grids, gate badges,
code blocks, footnotes, and provenance. Convert each PNG to a base64 data URI.
Use system-font fallbacks and CSS print rules. Give every figure meaningful alt
text and every section a stable anchor.

- [ ] **Step 4: Run HTML tests**

Run: `.venv/bin/python -m pytest tests/test_renderers.py::test_html_is_offline_self_contained -q`

Expected: PASS.

- [ ] **Step 5: Commit the HTML renderer**

```bash
git add tracks/qmc/solutions/卧龙凤雏/integrated-report
git commit -m "feat: render self-contained integrated HTML report"
```

---

### Task 5: Render the A4 PDF from the Shared Model

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/pdf_renderer.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_renderers.py`

**Interfaces:**
- Consumes: `ReportDocument` and destination `Path`.
- Produces: `render_pdf(report, destination) -> Path`.

- [ ] **Step 1: Write PDF contract tests**

```python
def test_pdf_has_expected_length_and_content(report, tmp_path):
    output = render_pdf(report, tmp_path / "report.pdf")
    reader = PdfReader(output)
    assert 25 <= len(reader.pages) <= 35
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    for title in REQUIRED_SECTION_TITLES:
        assert title in text
    for value in ("0.499424", "0.456469", "0.444107"):
        assert value in text
```

- [ ] **Step 2: Run the PDF test and confirm failure**

Run: `.venv/bin/python -m pytest tests/test_renderers.py::test_pdf_has_expected_length_and_content -q`

Expected: FAIL because `render_pdf` is absent.

- [ ] **Step 3: Implement ReportLab document primitives**

Use `BaseDocTemplate`, A4 page size, 18-20 mm margins, separate title and body
page templates, numbered headings, page numbers, running headers, `KeepTogether`
for figures/captions, and repeated table headers. Register a Unicode-capable local
font if available; otherwise keep PDF-visible prose and notation within the
verified font repertoire. Render equations as high-resolution transparent PNGs
through Matplotlib mathtext so symbols remain legible.

- [ ] **Step 4: Control pagination**

Assign explicit section page breaks at the three model chapters and appendices.
Scale figures to at most 165 mm wide and 105 mm tall. Keep captions under their
figures. Use compact tables for gates and split long parameter/provenance tables
with repeated headers. Adjust paragraph spacing until the result remains within
25-35 pages without shrinking body text below 9.5 pt.

- [ ] **Step 5: Run renderer tests**

Run: `.venv/bin/python -m pytest tests/test_renderers.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the PDF renderer**

```bash
git add tracks/qmc/solutions/卧龙凤雏/integrated-report
git commit -m "feat: render integrated A4 PDF report"
```

---

### Task 6: Build Command, Output Verification, and Documentation

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/verify_outputs.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/build_report.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/Makefile`
- Create: `tracks/qmc/solutions/卧龙凤雏/integrated-report/README.md`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_renderers.py`

**Interfaces:**
- Produces: CLI `python build_report.py --repo-root PATH`.
- Produces: `verify_html(path) -> VerificationResult` and `verify_pdf(path) -> VerificationResult`.

- [ ] **Step 1: Write end-to-end build tests**

```python
def test_build_writes_stable_outputs(repo_root):
    result = build(repo_root)
    assert result.html == repo_root / "output/html/three-model-central-charge-report.html"
    assert result.pdf == repo_root / "output/pdf/three-model-central-charge-report.pdf"
    assert result.html.exists() and result.pdf.exists()
```

- [ ] **Step 2: Run the end-to-end test and confirm failure**

Run: `.venv/bin/python -m pytest tests/test_renderers.py::test_build_writes_stable_outputs -q`

Expected: FAIL because the build orchestration is absent.

- [ ] **Step 3: Implement atomic orchestration and output checks**

Build into temporary sibling files, verify them, then replace stable outputs.
HTML checks cover doctype, required anchors, embedded images, absent network
dependencies, and headline values. PDF checks cover magic bytes, page count,
extractable section titles, headline values, and a nonempty image count.

- [ ] **Step 4: Add setup, test, build, and clean targets**

```make
setup:
	python3 -m venv --system-site-packages .venv
	.venv/bin/pip install -r requirements.txt

test:
	MPLCONFIGDIR=/tmp/integrated-report-mpl .venv/bin/python -m pytest -q

build:
	MPLCONFIGDIR=/tmp/integrated-report-mpl .venv/bin/python build_report.py
```

The clean target removes only generated comparison figures and temporary render
files under this report package; it does not remove frozen source results or
final `output/` artifacts.

- [ ] **Step 5: Document inputs, commands, outputs, and non-rerun guarantee**

README must identify all three source directories, show `make setup`, `make
test`, and `make build`, explain that the report reads frozen artifacts only, and
list both stable output paths.

- [ ] **Step 6: Run the full automated suite and build**

Run: `make test`

Expected: all tests pass.

Run: `make build`

Expected: both stable outputs are generated and automatic verification passes.

- [ ] **Step 7: Commit build integration**

```bash
git add tracks/qmc/solutions/卧龙凤雏/integrated-report output
git commit -m "feat: build verified three-model reports"
```

---

### Task 7: Render-and-Inspect Final Artifacts

**Files:**
- Verify: `output/html/three-model-central-charge-report.html`
- Verify: `output/pdf/three-model-central-charge-report.pdf`
- Temporary: `tmp/pdfs/three-model-central-charge-report-*.png`

**Interfaces:**
- Consumes final HTML and PDF.
- Produces visual QA evidence and no new scientific values.

- [ ] **Step 1: Inspect PDF metadata and extracted text**

Run: `pdfinfo output/pdf/three-model-central-charge-report.pdf`

Expected: A4 pages, 25-35 pages, valid metadata, no encryption.

Run:

```bash
.venv/bin/python -c "from pypdf import PdfReader; r=PdfReader('output/pdf/three-model-central-charge-report.pdf'); print(len(r.pages))"
```

Expected: readable PDF with no parser error.

- [ ] **Step 2: Render every PDF page**

Run:

```bash
mkdir -p tmp/pdfs
pdftoppm -png -r 120 output/pdf/three-model-central-charge-report.pdf tmp/pdfs/three-model-central-charge-report
```

Expected: one PNG per PDF page.

- [ ] **Step 3: Visually inspect every rendered page**

Check title page, headers, footers, numbering, section starts, equations, tables,
charts, captions, code blocks, and provenance. There must be no clipping,
overlap, black squares, unreadable glyphs, orphan headings, detached captions,
or illegibly small chart labels. If a defect exists, fix the responsible
renderer/content code, rebuild, rerender all pages, and inspect again.

- [ ] **Step 4: Open and inspect the self-contained HTML**

Use the in-app browser to inspect the full report at multiple viewport widths.
Verify table-of-contents navigation, image embedding, responsive table overflow,
figure grids, code blocks, section anchors, and print styling. Fix, rebuild, and
reinspect if any defect exists.

- [ ] **Step 5: Confirm source data remains unchanged**

Record SHA-256 hashes of all consumed source artifacts before and after the build
and assert equality. Confirm `git status --short` contains only intended report
source/output changes.

- [ ] **Step 6: Run final verification**

Run: `make test`

Expected: all tests pass.

Run: `make build`

Expected: output verification passes and stable files remain at the declared
paths.

- [ ] **Step 7: Remove temporary page renderings**

Remove only `tmp/pdfs/three-model-central-charge-report-*.png` after the final
visual review. Preserve both final report artifacts.

## Plan Self-Review

- Every approved design section maps to Tasks 1-7.
- Source adapters explicitly handle the three incompatible result schemas.
- Both renderers consume the same `ReportDocument`.
- The plan contains no simulation rerun.
- Automated checks and visual checks cover both formats.
- Output paths, model targets, audience, language, and page target match the
  approved specification.
