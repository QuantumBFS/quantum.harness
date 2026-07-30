# Issue #230 Research Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a polished, evidence-backed Issue #230 delivery consisting of deterministic data summaries, figures, a Chinese Markdown/LaTeX/PDF technical report, and an updated public PR #266.

**Architecture:** Existing selected certificate JSON files remain the sole numerical source of truth. A deterministic builder validates and summarizes them; a plotting script consumes only that summary; the Markdown and XeLaTeX reports explain the proof architecture and embed the generated evidence. GitHub delivery updates the already-public fork branch and existing upstream pull request.

**Tech Stack:** Python 3.11+, `decimal`, `hashlib`, `json`, `csv`, Matplotlib, pytest, XeLaTeX/latexmk, Poppler, Git, GitHub CLI.

## Global Constraints

- Keep every changed path under `tracks/polyopt/solutions/WangTheoPhys/issue230/`.
- Preserve `h=(XX+YY+ZZ)/4` and `e_B=1/4-log(2)` normalization exactly.
- Bethe data is a verifier-only oracle and must not enter certificate construction or repair.
- Do not claim a literature record unless the strict gate and a normalization-matched literature comparison both pass.
- Use positive, concrete prose while retaining every correctness boundary needed to audit the result.
- Publish through the existing public `JunkaiWang-TheoPhy/quantum.harness` fork and PR #266.
- Do not publish the mixed private `Quantum-Harness-2607-Hefei` workspace.

---

### Task 1: Deterministic delivery-data builder

**Files:**
- Create: `tracks/polyopt/solutions/WangTheoPhys/issue230/src/xxzcert/delivery.py`
- Create: `tracks/polyopt/solutions/WangTheoPhys/issue230/scripts/build_delivery_data.py`
- Create: `tracks/polyopt/solutions/WangTheoPhys/issue230/tests/test_delivery.py`
- Modify: `tracks/polyopt/solutions/WangTheoPhys/issue230/pyproject.toml`

**Interfaces:**
- Consumes: `LevelCertificate.read(path)` and selected files under `outputs/final/`.
- Produces: `RecordGateSummary`, `build_delivery_bundle(root: Path) -> DeliveryBundle`, and a CLI that writes stable CSV/JSON/TXT files.

- [ ] **Step 1: Write exact-arithmetic and coverage tests**

```python
def test_record_gate_uses_exact_decimal_strings():
    gate = evaluate_record_gate(
        Decimal("-0.443976567"),
        Decimal("-0.4428702958784947210360110613724028607783"),
    )
    assert gate.width == Decimal(
        "0.0011062711215052789639889386275971392217"
    )
    assert gate.target == Decimal("0.0003")


def test_build_delivery_bundle_contains_all_selected_grid_certificates():
    bundle = build_delivery_bundle(PROJECT_ROOT)
    assert len(bundle.grid_rows) == 27
    assert bundle.strongest_xxx.level == 47
```

- [ ] **Step 2: Run the focused test before implementation**

Run: `.venv/bin/pytest tests/test_delivery.py -q`

Expected: import failure for the new `xxzcert.delivery` module.

- [ ] **Step 3: Implement exact record arithmetic**

```python
@dataclass(frozen=True)
class RecordGateSummary:
    lower: Decimal
    upper: Decimal
    width: Decimal
    target: Decimal
    required_lower: Decimal
    passes: bool


def evaluate_record_gate(lower: Decimal, upper: Decimal) -> RecordGateSummary:
    if lower > upper:
        raise ValueError("certified lower endpoint exceeds upper endpoint")
    target = Decimal("0.0003")
    width = upper - lower
    return RecordGateSummary(
        lower=lower,
        upper=upper,
        width=width,
        target=target,
        required_lower=upper - target,
        passes=width < target,
    )
```

- [ ] **Step 4: Implement deterministic artifact writing**

The CLI writes `certificate-summary.csv`, `record-gate.json`, and `DATA_MANIFEST.txt`. Rows are sorted by numeric delta and level, use stored decimal strings without binary-float round trips, and record SHA-256 plus byte count for every selected proof payload.

- [ ] **Step 5: Regenerate twice and require identical hashes**

Run:

```bash
.venv/bin/pytest tests/test_delivery.py -q
.venv/bin/python scripts/build_delivery_data.py
shasum -a 256 outputs/final/certificate-summary.csv outputs/final/record-gate.json outputs/final/DATA_MANIFEST.txt
.venv/bin/python scripts/build_delivery_data.py
shasum -a 256 outputs/final/certificate-summary.csv outputs/final/record-gate.json outputs/final/DATA_MANIFEST.txt
```

Expected: tests pass and both hash triplets are identical.

- [ ] **Step 6: Commit data code and artifacts**

Run: `git commit -m "Add audited Issue 230 delivery data"` after staging only the four implementation/test files and three generated artifacts listed above.

### Task 2: Evidence figures

**Files:**
- Create: `tracks/polyopt/solutions/WangTheoPhys/issue230/scripts/plot_delivery_summary.py`
- Create: paired PDF/PNG files for `xxx-interval-nesting`, `endpoint-error-budget`, and `symmetry-compression` under `docs/issue-230/figures/`.

**Interfaces:**
- Consumes: `outputs/final/certificate-summary.csv` and symmetry benchmark rows documented in `results.md`.
- Produces: three deterministic figure pairs with publication-readable labels.

- [ ] **Step 1: Implement the plotting entry point**

```python
def main() -> int:
    rows = read_summary(PROJECT_ROOT / "outputs/final/certificate-summary.csv")
    plot_xxx_nesting(rows, FIGURE_DIR)
    plot_endpoint_budget(rows, FIGURE_DIR)
    plot_symmetry_compression(FIGURE_DIR)
    return 0
```

- [ ] **Step 2: Generate all six figure files**

Run: `.venv/bin/python scripts/plot_delivery_summary.py`

Expected: six nonempty files under `docs/issue-230/figures/`.

- [ ] **Step 3: Render each PDF figure with Poppler**

Run one `pdftoppm -png -singlefile` command per figure and inspect the rendered PNG for complete labels, legends, and axes.

- [ ] **Step 4: Commit the plotting script and figures**

Run: `git commit -m "Visualize the certified XXZ frontier"` after staging only the plotting script and six generated files.

### Task 3: Technical report sources

**Files:**
- Create: `tracks/polyopt/solutions/WangTheoPhys/issue230/docs/issue-230/technical-report-zh.md`
- Create: `tracks/polyopt/solutions/WangTheoPhys/issue230/docs/issue-230/technical-report-zh.tex`
- Create: `tracks/polyopt/solutions/WangTheoPhys/issue230/docs/issue-230/references.bib`

**Interfaces:**
- Consumes: specification, results, reproduce guide, generated data, figures, and verified primary-source metadata.
- Produces: one consistent research narrative in Markdown and XeLaTeX.

- [ ] **Step 1: Verify primary literature metadata**

Use primary arXiv/publisher pages for `2212.03014`, `2402.02126`, `2604.01555`, and `2605.29959`. Record titles, authors, year, identifier, and the exact methodological role of each source in `references.bib`.

- [ ] **Step 2: Write the Markdown report**

Use these sections: Executive summary; problem and normalization; why the combined architecture advances the frontier; proof-producing lower-bound pipeline; exact rational-MPS upper bound; XXX result and XXZ calibration grid; symmetry and computational scaling; reproducibility and trust boundary; next certified frontier; conclusion.

- [ ] **Step 3: Write the XeLaTeX report**

Use `ctexart`, `geometry`, `booktabs`, `graphicx`, `hyperref`, `xcolor`, `amsmath`, and `microtype`. Embed the three vector PDF figures and target 8-14 pages.

- [ ] **Step 4: Scan claim language**

Run:

```bash
rg -n "TBD|TODO|placeholder|world record|state of the art" docs/issue-230/technical-report-zh.md docs/issue-230/technical-report-zh.tex
```

Expected: no placeholders or unsupported priority claims.

- [ ] **Step 5: Commit report sources**

Run: `git commit -m "Document the certified XXZ methodology"` after staging Markdown, TeX, and BibTeX sources.

### Task 4: PDF build and visual audit

**Files:**
- Create: `tracks/polyopt/solutions/WangTheoPhys/issue230/docs/issue-230/technical-report-zh.pdf`
- Create: `tracks/polyopt/solutions/WangTheoPhys/issue230/docs/issue-230/PDF_AUDIT.txt`

**Interfaces:**
- Consumes: report TeX, bibliography, and three vector figures.
- Produces: a stable PDF and human-readable audit record.

- [ ] **Step 1: Compile with latexmk and XeLaTeX**

Run:

```bash
latexmk -xelatex -interaction=nonstopmode -halt-on-error docs/issue-230/technical-report-zh.tex
```

Expected: exit zero and a nonempty PDF.

- [ ] **Step 2: Check PDF metadata and LaTeX diagnostics**

Run `pdfinfo` on the PDF and scan the log for `Undefined`, `Overfull`, `LaTeX Error`, and `Fatal error`. Correct every hit that affects the final layout.

- [ ] **Step 3: Render and inspect every page**

Run:

```bash
mkdir -p tmp/pdfs/issue230-report
pdftoppm -png -r 150 docs/issue-230/technical-report-zh.pdf tmp/pdfs/issue230-report/page
```

Expected: readable Chinese glyphs, unbroken equations, unclipped figures/tables, consistent headers, and visible page numbers on every page.

- [ ] **Step 4: Record and commit the audit**

`PDF_AUDIT.txt` records compile command, page count, byte size, SHA-256, inspected page count, and visual result. Commit PDF and audit with `Publish the Issue 230 technical report`.

### Task 5: Reader entrypoints and GitHub copy

**Files:**
- Modify: `tracks/polyopt/solutions/WangTheoPhys/issue230/README.md`
- Create: `tracks/polyopt/solutions/WangTheoPhys/issue230/docs/issue-230/PR_BODY.md`
- Create: `tracks/polyopt/solutions/WangTheoPhys/issue230/docs/issue-230/PR_COMMENT.md`

**Interfaces:**
- Consumes: final data, report, PDF audit, and validation results.
- Produces: reviewer-ready repository navigation, PR description, and comment.

- [ ] **Step 1: Update README opening and artifact table**

Lead with the proof-producing architecture and strongest certified interval. Add links to PDF, Markdown report, summary CSV, gate JSON, manifest, and reproduction guide.

- [ ] **Step 2: Write `PR_BODY.md`**

Cover team, challenge, scientific contribution, algorithmic innovations, strongest result, XXZ breadth, proof architecture, validation, reproduction, and claim boundary. Use positive, specific language and no unsupported `first` or record claim.

- [ ] **Step 3: Write `PR_COMMENT.md`**

Keep the comment below 2,500 characters. Tag a challenge-author username only if GitHub confirms it; otherwise address maintainers and challenge authors without guessing. Request Actions approval and one independent reviewer.

- [ ] **Step 4: Commit reader entrypoints**

Run: `git commit -m "Prepare the Issue 230 review package"`.

### Task 6: Completion audit

**Files:** Modify only listed delivery files if the audit finds a discrepancy.

**Interfaces:**
- Consumes: the full solution directory at the final commit candidate.
- Produces: passing test, build, path, secret, and claim gates.

- [ ] **Step 1: Run focused and fast test suites**

Run:

```bash
.venv/bin/pytest tests/test_delivery.py -q
.venv/bin/pytest -q --ignore=tests/test_published_outputs.py
```

Expected: all tests pass.

- [ ] **Step 2: Verify all 27 compact certificates**

Run the existing exact audit over `outputs/final/grid` and require every selected certificate to pass reconstruction and containment.

- [ ] **Step 3: Run scope, whitespace, and secrets gates**

Run:

```bash
git diff --check 6606c60..HEAD
git diff --name-only 6606c60..HEAD
rg -n --hidden -S "(BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|gh[opsu]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})" tracks/polyopt/solutions/WangTheoPhys/issue230
```

Inspect the name list and require every entry to start with the Issue #230 solution prefix. Expected: clean diff and no credential matches.

- [ ] **Step 4: Prove regeneration stability**

Regenerate data and plots and require `git status --short` to remain unchanged.

- [ ] **Step 5: Insert literal final validation values**

Update README and GitHub copy only with the completed test counts, PDF page count/hash, and verifier results.

### Task 7: Push and update PR #266

**Files:** No additional repository files.

**Interfaces:**
- Consumes: clean audited branch, `PR_BODY.md`, and `PR_COMMENT.md`.
- Produces: pushed public fork branch and updated upstream PR #266.

- [ ] **Step 1: Reconfirm identity and remote head**

Run:

```bash
gh auth status
git ls-remote origin refs/heads/agent/issue-230-xxz-certificate
git status --short --branch
```

Expected: authenticated as `JunkaiWang-TheoPhy`, remote head matches the pre-push baseline, and the worktree is clean.

- [ ] **Step 2: Push without force**

Run: `git push origin agent/issue-230-xxz-certificate`

Expected: fast-forward success.

- [ ] **Step 3: Update PR body and post delivery comment**

Run:

```bash
gh pr edit 266 --repo QuantumBFS/quantum.harness --body-file tracks/polyopt/solutions/WangTheoPhys/issue230/docs/issue-230/PR_BODY.md
gh pr comment 266 --repo QuantumBFS/quantum.harness --body-file tracks/polyopt/solutions/WangTheoPhys/issue230/docs/issue-230/PR_COMMENT.md
```

- [ ] **Step 4: Confirm public visibility and PR state**

Run:

```bash
gh repo view JunkaiWang-TheoPhy/quantum.harness --json visibility,url,defaultBranchRef
gh pr view 266 --repo QuantumBFS/quantum.harness --json headRefOid,mergeable,mergeStateStatus,statusCheckRollup,reviews,comments,url
```

Expected: fork visibility `PUBLIC`, PR head equals the pushed commit, and the new body/comment are visible.

## Self-review

- Spec coverage: data text, Markdown report, LaTeX source, PDF, figures, repository navigation, PR body, PR comment, public visibility, validation, and push each have an explicit task.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation step remains.
- Type consistency: `build_delivery_bundle`, `RecordGateSummary`, generated filenames, and downstream consumers use the same names throughout.
- Scope: every repository mutation stays inside the Issue #230 solution path; GitHub writes target the existing public fork and PR #266.
