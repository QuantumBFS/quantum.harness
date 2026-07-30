# Sparse-Anchor Channel Response Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested sparse-anchor channel-response fitter, held-out scorer, and conditional DFPT cost model without overstating physical validation or speed.

**Architecture:** A standard-library coefficient-space response module fits a small multi-output ridge map, while an independent cost module decides whether declared sparse sampling assumptions beat a dense baseline.  A synthetic held-out example exercises the full path; reviewer documents and the TeX report separate software reproduction from real-material validation.

**Tech Stack:** Python 3 standard library, JSON-compatible YAML, `unittest`, XeLaTeX/latexmk, Poppler.

---

### Task 1: Freeze the approved sparse-anchor design

**Files:**
- Create: `docs/superpowers/specs/2026-07-30-sparse-anchor-response-design.md`
- Create: `docs/superpowers/plans/2026-07-30-sparse-anchor-response-implementation-plan.md`

- [ ] **Step 1: Record the approved scope**

State that the existing correction is not faster than a single DFPT calculation,
that the new cost claim is conditional on amortization, and that the bundled
held-out example is synthetic rather than a physical benchmark.

- [ ] **Step 2: Check the design for placeholders and scope drift**

Run:

```bash
rg -n "T[B]D|TO[D]O|implement lat[e]r|universal speed[u]p" docs/superpowers
```

Expected: no matches in the two new documents.

- [ ] **Step 3: Commit the approved design**

```bash
git add docs/superpowers/specs/2026-07-30-sparse-anchor-response-design.md \
        docs/superpowers/plans/2026-07-30-sparse-anchor-response-implementation-plan.md
git commit -m "docs: design sparse-anchor response MVP"
```

### Task 2: Specify response fitting with failing tests

**Files:**
- Create: `tests/test_response_model.py`
- Create: `src/response_model.py`

- [ ] **Step 1: Write tests for identity and channel mixing**

Add tests equivalent to:

```python
def test_identity_response_is_recovered(self):
    inputs = [[1, 0], [0, 1], [1, 1]]
    model = fit_response_matrix(inputs, inputs)
    assert_matrix_close(self, model["response_matrix"], [[1, 0], [0, 1]])

def test_off_diagonal_response_predicts_held_out_vector(self):
    inputs = [[1, 0], [0, 1], [1, 1]]
    targets = [[2, 0.5], [1, 3], [3, 3.5]]
    model = fit_response_matrix(inputs, targets)
    predicted = predict_coefficients(model, [[2, -1]])
    assert_matrix_close(self, predicted, [[3, -2]])
```

Also require rejection of empty, ragged, nonnumeric, mismatched, and singular
unregularized inputs, and require a positive ridge value to make a rank-deficient
case solvable.

- [ ] **Step 2: Run the tests and verify the expected failure**

Run:

```bash
python3 -m unittest tests.test_response_model -v
```

Expected: FAIL because `src.response_model` does not exist.

- [ ] **Step 3: Implement the minimum response model**

Implement numeric validation, conjugate-transpose normal equations,
partial-pivoting Gaussian elimination, prediction, and error metrics.  Encode a
numerically real coefficient as a JSON number and a genuinely complex coefficient
as `{"real": value, "imag": value}` so the model remains JSON serializable.  The
model dictionary must contain:

```python
{
    "response_matrix": [[...], [...]],
    "channel_count": 2,
    "anchor_count": 3,
    "ridge": 0.0,
    "training_metrics": {
        "rmse": 0.0,
        "relative_rmse": 0.0,
        "max_abs_error": 0.0,
    },
}
```

- [ ] **Step 4: Re-run response-model tests**

Run:

```bash
python3 -m unittest tests.test_response_model -v
```

Expected: all response-model tests pass.

### Task 3: Specify conditional cost accounting with failing tests

**Files:**
- Create: `tests/test_cost_model.py`
- Create: `src/cost_model.py`

- [ ] **Step 1: Write faster and slower workflow tests**

Require this sparse case to be faster:

```python
result = compare_sparse_to_dense(
    full_points=100,
    anchor_points=10,
    dfpt_cost_per_point=1.0,
    inference_cost_per_point=0.01,
)
self.assertTrue(result["is_faster"])
self.assertAlmostEqual(result["dense_cost"], 100.0)
self.assertAlmostEqual(result["sparse_cost"], 10.9)
```

Require a case with expensive high-level anchors to be slower, and reject negative
costs, zero campaigns, nonintegral counts, and more anchors than full points.

- [ ] **Step 2: Verify the tests fail because the module is absent**

Run:

```bash
python3 -m unittest tests.test_cost_model -v
```

Expected: FAIL because `src.cost_model` does not exist.

- [ ] **Step 3: Implement the explicit cost equations**

Return:

```python
{
    "dense_cost": dense_cost,
    "sparse_cost": sparse_cost,
    "speedup": dense_cost / sparse_cost,
    "is_faster": sparse_cost < dense_cost,
    "saved_cost": dense_cost - sparse_cost,
}
```

- [ ] **Step 4: Re-run cost-model tests**

Run:

```bash
python3 -m unittest tests.test_cost_model -v
```

Expected: all cost-model tests pass.

### Task 4: Add a reproducible held-out example

**Files:**
- Create: `examples/sparse_anchor_response.yaml`
- Create: `examples/run_sparse_anchor.py`
- Modify: `Makefile`
- Test: `tests/test_sparse_anchor_example.py`

- [ ] **Step 1: Write the failing end-to-end test**

Require `run_case()` to return a held-out relative RMSE below `1e-10`, a fitted
matrix containing a nonzero off-diagonal entry, and a cost record with
`is_faster=True`.  Run the test and verify failure because the example is absent.

- [ ] **Step 2: Add the transparent synthetic dataset**

Use three channels named `charge`, `internal`, and `nonlocal`, at least four
linearly independent training anchors, two held-out vectors, and targets generated
from the declared matrix:

```text
[[1.0, 0.1, 0.0],
 [0.2, 1.5, 0.1],
 [0.0, 0.2, 0.8]]
```

The runner must not read this matrix during fitting; it is metadata for auditing
the synthetic case only.

- [ ] **Step 3: Add the example to `make examples` and `knowledge-check`**

Run:

```bash
make examples
make knowledge-check
```

Expected: both commands exit zero and the sparse example prints held-out metrics
and conditional cost results.

### Task 5: Update reviewer-facing claims and contract tests

**Files:**
- Modify: `README.md`
- Modify: `RESULTS.md`
- Modify: `REPRODUCE.md`
- Modify: `eval/EVALUATION.md`
- Modify: `tests/test_submission_contract.py`

- [ ] **Step 1: Update the contract test before the documents**

Require the reviewer documents to contain `sparse-anchor`, `held-out synthetic`,
`not faster than a single DFPT`, `python3 examples/run_sparse_anchor.py`, and the
actual fresh test count.  Run the test and confirm it fails on the old documents.

- [ ] **Step 2: Rewrite the claims consistently**

Explain that the new fitter predicts coefficient vectors only after a fixed
operator basis has been declared, that the synthetic example verifies software
behavior, and that a real speed claim requires measured comparison with converged
DFPT plus interpolation at matched accuracy.

- [ ] **Step 3: Re-run submission and full software checks**

Run:

```bash
python3 -m unittest tests.test_submission_contract -v
make check
```

Expected: all tests, 14 evaluation cases, three examples, and all JSON-compatible
YAML parsing checks pass.

### Task 6: Align and rebuild the scientific report

**Files:**
- Modify: `report/sections/07_next_generation_dfpt.tex`
- Modify: `report/sections/08_ai_research_program.tex`
- Modify: `report/sections/09_conclusions.tex`
- Modify: `REPRODUCE.md`
- Replace: `report/main.pdf`

- [ ] **Step 1: Add the response-matrix and cost equations**

State `c_ref = K c_DFPT + residual`, define every coefficient and matrix, add the
dense and sparse cost equations, and state the necessary break-even inequality.

- [ ] **Step 2: Remove unconditional speed claims**

Search:

```bash
rg -n "faster than DFPT|speedup" README.md RESULTS.md REPRODUCE.md report
```

Every match must either refer to a supplied cost record or explicitly state a
condition and an unproven physical benchmark.

- [ ] **Step 3: Build and check the PDF**

Run:

```bash
make report-check
```

Expected: XeLaTeX succeeds, references resolve, there are no overfull boxes, and
`pdfinfo` reports the rebuilt document.

- [ ] **Step 4: Render and inspect every page**

Run:

```bash
mkdir -p tmp/pdfs
pdftoppm -png -r 120 report/main.pdf tmp/pdfs/bots848
```

Inspect all rendered pages for clipped text, table overflow, broken equations,
missing figures, headers, footers, and page transitions.  Remove `tmp/pdfs` after
inspection and update the documented PDF SHA-256 digest.

### Task 7: Final verification and handoff commit

**Files:**
- Verify all changes below `tracks/agent-kb/solutions/BOTS-848/`.

- [ ] **Step 1: Run fresh complete verification**

```bash
make check-all
git diff --check
git status --short
```

Expected: zero command failures and no changes outside the solution directory.

- [ ] **Step 2: Commit with the requested attribution**

```bash
git add tracks/agent-kb/solutions/BOTS-848
GIT_AUTHOR_NAME='Codex' GIT_AUTHOR_EMAIL='codex@openai.com' \
GIT_COMMITTER_NAME='AroundPeking' \
GIT_COMMITTER_EMAIL='gonghuanjing@iphy.ac.cn' \
git commit -m 'feat: add sparse-anchor DFPT response MVP'
```

- [ ] **Step 3: Verify the local commit and do not push**

```bash
git log -1 --format='%h%nAuthor: %an <%ae>%nCommitter: %cn <%ce>%n%s'
```

Expected: author `Codex <codex@openai.com>`, committer
`AroundPeking <gonghuanjing@iphy.ac.cn>`, and no push performed.
