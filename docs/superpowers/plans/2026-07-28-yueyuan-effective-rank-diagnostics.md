# YueYuan Effective-Rank Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface measured Hessian effective dimension in attempt 004 artifacts, tests, report, README, and PR text.

**Architecture:** Keep the change analytical: compute spectrum diagnostics from already-saved model Hessian eigenvalues and write them into generated metadata and CSV tables. Do not change optimization behavior, query budgets, run records, or reported success claims.

**Tech Stack:** Python 3, NumPy, CSV/JSON artifacts, pytest, existing attempt-004 JAX code.

## Global Constraints

- Do not run a new large Slurm sweep for this pass.
- Do not tune or change the reported optimizer results.
- Do not claim the hard two-qubit large-gap case is solved.
- Do not add any private account, hostname, SSH, or credential details.
- Generated data remains under `tracks/qcs/results/YueYuan/attempt-004/` and stays ignored by git.
- Keep `Ion.lock` unstaged and untouched.

---

### Task 1: Add Spectrum-Diagnostic Helpers

**Files:**
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/hessian.py`
- Test: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hessian.py`

**Interfaces:**
- Consumes: `effective_rank(eigenvalues: np.ndarray, threshold: float = 1e-8) -> int`
- Produces: `curvature_fraction(eigenvalues: np.ndarray, k: int) -> float`
- Produces: `min_k_for_curvature(eigenvalues: np.ndarray, fraction: float) -> int`

- [ ] **Step 1: Write failing tests**

Add this test to `test_attempt_004_hessian.py`:

```python
def test_attempt_004_effective_rank_and_curvature_cover_are_data_driven():
    eigenvalues = np.array([4.0, -2.0, 1.0, 0.25, 1e-10])

    assert hessian.effective_rank(eigenvalues, threshold=1e-8) == 4
    assert hessian.curvature_fraction(eigenvalues, k=0) == 0.0
    assert hessian.curvature_fraction(eigenvalues, k=2) == 6.0 / 7.25
    assert hessian.curvature_fraction(eigenvalues, k=99) == 1.0
    assert hessian.min_k_for_curvature(eigenvalues, 0.50) == 1
    assert hessian.min_k_for_curvature(eigenvalues, 0.90) == 3
    assert hessian.min_k_for_curvature(eigenvalues, 0.99) == 4
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hessian.py::test_attempt_004_effective_rank_and_curvature_cover_are_data_driven -q
```

Expected: fail because the new helper functions do not exist.

- [ ] **Step 3: Implement helpers**

In `hessian.py`, add:

```python
def curvature_fraction(eigenvalues: np.ndarray, k: int) -> float:
    values = np.sort(np.abs(np.asarray(eigenvalues, dtype=float)))[::-1]
    total = float(np.sum(values))
    if total <= 0.0 or k <= 0:
        return 0.0
    return min(1.0, float(np.sum(values[:k])) / total)


def min_k_for_curvature(eigenvalues: np.ndarray, fraction: float) -> int:
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be between 0 and 1")
    values = np.sort(np.abs(np.asarray(eigenvalues, dtype=float)))[::-1]
    total = float(np.sum(values))
    if total <= 0.0 or fraction <= 0.0:
        return 0
    cumulative = np.cumsum(values) / total
    return int(np.searchsorted(cumulative, fraction, side="left") + 1)
```

- [ ] **Step 4: Verify the helper test passes**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hessian.py::test_attempt_004_effective_rank_and_curvature_cover_are_data_driven -q
```

Expected: pass.

### Task 2: Surface Spectrum Metadata And CSV Table

**Files:**
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/experiments.py`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/analysis.py`
- Test: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py`

**Interfaces:**
- Consumes: `hessian.curvature_fraction(...)` and `hessian.min_k_for_curvature(...)`
- Produces: `spectrum_summary_rows(spectra: list[dict]) -> list[dict]`
- Produces table: `summary_tables/spectrum_summary.csv`

- [ ] **Step 1: Write failing smoke assertions**

In `test_attempt_004_make_figures_writes_required_pngs`, add
`"spectrum_summary.csv"` to the expected CSV set and assert these fields:

```python
with (tables / "spectrum_summary.csv").open() as handle:
    reader = csv.DictReader(handle)
    rows = list(reader)
    assert rows
    assert {
        "system",
        "seed",
        "effective_rank",
        "benchmark_rank",
        "curvature_at_benchmark_k",
        "k_for_90pct_curvature",
        "k_for_95pct_curvature",
        "k_for_99pct_curvature",
    } <= set(reader.fieldnames or [])
```

- [ ] **Step 2: Run the failing smoke table test**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py::test_attempt_004_make_figures_writes_required_pngs -q
```

Expected: fail because `spectrum_summary.csv` is not generated.

- [ ] **Step 3: Add spectrum metadata in experiments**

In `experiments.py`, import `hessian as hessian_tools` if needed, then include
these keys in each spectrum entry:

```python
"effective_rank": hessian.effective_rank(eig_values),
"benchmark_rank": system_cfg.benchmark_rank,
"curvature_at_benchmark_k": hessian.curvature_fraction(eig_values, system_cfg.benchmark_rank),
"k_for_90pct_curvature": hessian.min_k_for_curvature(eig_values, 0.90),
"k_for_95pct_curvature": hessian.min_k_for_curvature(eig_values, 0.95),
"k_for_99pct_curvature": hessian.min_k_for_curvature(eig_values, 0.99),
```

- [ ] **Step 4: Add CSV writer in analysis**

Add `SPECTRUM_FIELDS`, `spectrum_summary_rows()`, and write
`spectrum_summary.csv` from `write_summary_tables()`. It should tolerate old
spectra without metadata by recomputing from `eigenvalues`.

- [ ] **Step 5: Verify smoke table test passes**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py::test_attempt_004_make_figures_writes_required_pngs -q
```

Expected: pass.

### Task 3: Update Documentation And Publish

**Files:**
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPORT.md`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/README.md`

**Interfaces:**
- Consumes: generated `summary_tables/spectrum_summary.csv`
- Produces: reviewer-visible explanation of measured effective rank and curvature capture.

- [ ] **Step 1: Update report and README**

Mention that `spectrum_summary.csv` records measured effective rank and
curvature concentration, and that this directly addresses the challenge
requirement to infer dimension from the Hessian spectrum.

- [ ] **Step 2: Run full verification**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests -q
python3 tracks/qcs/solutions/YueYuan/research/validator/self_test.py
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_candidate.py --fast --out /tmp/yueyuan-attempt004-candidate.json
# Run the private-marker scan using the local redaction pattern kept outside git.
```

Expected: tests and validator pass; marker scan prints nothing.

- [ ] **Step 3: Commit intended files only**

Run:

```bash
git add tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hessian.py tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/hessian.py tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/experiments.py tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/analysis.py tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPORT.md tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/README.md
git commit -m "Add attempt 004 effective-rank diagnostics"
```

Do not stage `Ion.lock`.

- [ ] **Step 4: Publish PR update**

Push or use the existing GitHub API fallback to update PR #203. Update the PR
body to mention `spectrum_summary.csv` and the measured effective-dimension
evidence.
