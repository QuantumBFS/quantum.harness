# Learning-Induced MIT Effective Central Charge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fit an exploratory entanglement effective central charge from existing data, generate a separate adaptive DIII production-v2 data set, cross-check it with a Casimir–anisotropy estimate, and publish the fully qualified results in all English and Chinese reports.

**Architecture:** Rust remains the sole trajectory generator and gains an explicit production-v2 scan plus deterministic adaptive-refinement support. Focused Python modules implement candidate selection, chord-length fitting, hierarchical uncertainty, stability gates, and report-ready result records; the existing analysis orchestrator composes them without conflating diagnostic `c` with either effective-central-charge estimator. Standalone reports consume the full summary, while the integrated report loads only the hash-selected v2 summary.

**Tech Stack:** Rust 2021, `rand_xoshiro::Xoshiro256PlusPlus`, Serde/TOML, NumPy, SciPy, Matplotlib, ReportLab, pypdf, pytest, Make, SHA-256 manifests.

## Global Constraints

- Preserve `tracks/qmc/results/learning-mit-production-20260730-112758` byte-for-byte.
- Write new results only under `tracks/qmc/results/learning-mit-production-v2-*`.
- Target 3600 seconds; ordinary stop 3300; scientific hard stop 5100; finalization reserve 300.
- Rust performs all physical sampling; Python performs no Monte Carlo evolution.
- `Xoshiro256PlusPlus` is the only Rust RNG used by physical and diagnostic streams.
- Show exploratory numerical estimates and all failed gates; never label them universal constants.
- Require at least five widths, four streams per selected width, and 32 complete blocks for `candidate`.
- Fit stability means covariance condition number at most `1e10`, bootstrap failures at most 5%, and smallest-size deletion stable within combined 95% uncertainty.
- Anisotropy stability means all declared-window estimates are positive and their range/median is at most 25%.
- English and Chinese outputs must contain identical numbers, intervals, states, caveats, and provenance.
- Existing three-model benchmark cards remain unchanged.

---

### Task 1: Isolate the implementation and declare production-v2

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/configs/production-v2.toml`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/Makefile`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/run.sh`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/tests/cli.rs`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/tests/config_rng.rs`

**Interfaces:**
- Consumes: existing `RunConfig`, `StageConfig`, CLI pipeline, and runtime contract.
- Produces: `make run-production-v2` and `./run.sh production-v2 [run-directory]`.

- [ ] **Step 1: Create an isolated worktree**

Run the `using-git-worktrees` skill, create branch
`feature/learning-mit-effective-central-charge`, and confirm both source and
worktree are clean. In the isolated learning-MIT module, run `make setup` if
`.venv/bin/python` is absent, then verify imports with:

```bash
.venv/bin/python -c 'import numpy, scipy, matplotlib, reportlab, pypdf, PIL, pytest'
```

- [ ] **Step 2: Write failing orchestration tests**

Add assertions equivalent to:

```rust
assert!(makefile.contains("run-production-v2"));
assert!(script.contains("production-v2"));
assert!(script.contains("forecast_seconds"));
assert!(script.contains("5100"));
assert!(production_v2.contains("name = \"xy-validation\""));
assert!(production_v2.contains("name = \"diii-locator\""));
assert!(production_v2.contains("widths = [8, 12, 16, 20, 24, 28, 32]"));
assert!(production_v2.contains("measurement_layers_per_width = 64"));
```

Also load `production-v2.toml` and assert the exact
`3600/3300/5100/300` runtime tuple, nine angles from `0.16` through `0.32`,
four streams, burn-in 16, and block size 8. The `xy-validation` stage repeats
the frozen validation grid `phi_pi = [0.18, 0.21, 0.24, 0.25, 0.27, 0.30]`
at widths `[8, 12, 16, 24]`, so the v2 result independently carries its XY
gate rather than silently borrowing a claim from v1.

- [ ] **Step 3: Run the tests and verify RED**

Run:

```bash
cargo test --offline --test cli --test config_rng
```

Expected: failure because the production-v2 config and entry points do not
exist.

- [ ] **Step 4: Add the minimal production-v2 entry points**

Create `production-v2.toml` with the `xy-validation` and `diii-locator`
stages and the exact values above. Extend the Makefile and the `run.sh` mode
case so the default directory prefix is `learning-mit-production-v2-`.
After writing `raw/benchmark.json`, parse its finite `forecast_seconds` and
stop before simulation when it exceeds 5100.

- [ ] **Step 5: Verify GREEN and RNG exclusivity**

Run:

```bash
cargo test --offline --test cli --test config_rng
rg -n 'Xoshiro256PlusPlus|StdRng|SmallRng|thread_rng|rand::random' src tests
```

Expected: tests pass; RNG search shows `Xoshiro256PlusPlus` and no alternative
Rust RNG implementation.

- [ ] **Step 6: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/learning-mit
git commit -m "feat: declare learning MIT production v2 scan"
```

---

### Task 2: Implement chord-length effective-central-charge fits

**Files:**
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/effective_central_charge.py`
- Create: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_effective_central_charge.py`

**Interfaces:**
- Consumes: `np.ndarray` rows `[interval_sites, width, entropy, uncertainty]`.
- Produces:

```python
@dataclass(frozen=True)
class EntanglementCentralChargeFit:
    phi_pi: float
    widths: np.ndarray
    per_width: np.ndarray
    extrapolated: float
    interval: tuple[float, float]
    fitted: np.ndarray
    residuals: np.ndarray
    chi2_per_dof: float
    covariance_condition: float
    model_weights: dict[str, float]
    stable_without_smallest: bool

def chord_log(interval: np.ndarray, width: float) -> np.ndarray: ...
def fit_width_c_eff(rows: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]: ...
def extrapolate_c_eff(
    phi_pi: float,
    fits_by_width: dict[int, tuple[float, float]],
    model_weights: dict[str, float],
) -> EntanglementCentralChargeFit: ...
```

- [ ] **Step 1: Write failing analytic-fixture tests**

Use synthetic values with `c_true = 0.72`, `b = 0.3`, `q = 0.4`,
`L = (8, 12, 16, 20, 24, 28, 32)`, and
`ell/L in [1/4, 3/4]`. Assert:

```python
assert np.allclose(
    chord_log(np.array([2.0]), 8.0),
    np.log((8.0 / np.pi) * np.sin(np.pi * 2.0 / 8.0)),
)
assert fit.extrapolated == pytest.approx(0.72, abs=2e-3)
assert fit.stable_without_smallest
```

Add failure cases for fewer than four widths, nonfinite entropy, duplicate
widths, and condition number above `1e10`.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest analysis/tests/test_effective_central_charge.py -q
```

Expected: import failure for the new module.

- [ ] **Step 3: Implement the per-width fit**

Select only `0.25 <= ell/L <= 0.75`. Construct columns
`[1, chord_log / 3, cos(2*pi*ell/L)/L**2]`, perform weighted least squares,
and return the coefficient multiplying `chord_log / 3` as
`c_eff(L)`.

- [ ] **Step 4: Implement finite-size extrapolation and diagnostics**

Fit columns `[1, 1/L**2]`; derive the covariance, fitted values, residuals,
chi-square per degree of freedom, condition number, and the refit after
removing the smallest width. Use the combined 95% standard error to set
`stable_without_smallest`.

- [ ] **Step 5: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest analysis/tests/test_effective_central_charge.py -q
```

Expected: all new tests pass.

- [ ] **Step 6: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/effective_central_charge.py \
  tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_effective_central_charge.py
git commit -m "feat: fit entanglement effective central charge"
```

---

### Task 3: Add deterministic pseudo-critical selection and adaptive requests

**Files:**
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/phase.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_phase.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/src/runner.rs`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/tests/runner_cli.rs`

**Interfaces:**
- Consumes: ordered `PhaseEvidence` and v2 locator manifest.
- Produces:

```python
@dataclass(frozen=True)
class CandidateSelection:
    status: str  # "bracketed" | "exploratory"
    lower_phi_pi: float
    upper_phi_pi: float
    candidate_phi_pi: float
    reasons: tuple[str, ...]

def select_candidate(evidence: list[PhaseEvidence]) -> CandidateSelection: ...
```

The refinement JSON accepts `status` values `bracketed` and `exploratory`;
both contain endpoints, midpoint, seven widths, eight streams, burn-in 16,
measurement 96, and block size 8.

- [ ] **Step 1: Write failing selection tests**

Test a strict metal/insulator pair and this fallback fixture:

```python
evidence = [
    PhaseEvidence(0.16, "inconclusive", (8, 12, 16), 0.10),
    PhaseEvidence(0.18, "inconclusive", (8, 12, 16), 0.15),
    PhaseEvidence(0.20, "inconclusive", (8, 12, 16), 0.55),
    PhaseEvidence(0.22, "inconclusive", (8, 12, 16), 0.60),
]
selection = select_candidate(evidence)
assert selection.status == "exploratory"
assert (selection.lower_phi_pi, selection.upper_phi_pi) == (0.18, 0.20)
assert selection.candidate_phi_pi == 0.18
```

Add a tie fixture proving the lower midpoint/p lower angle rules.

- [ ] **Step 2: Write failing Rust request tests**

Serialize an `exploratory` request, hash-register it, and assert
`run_requested_tasks` schedules its tasks. Preserve rejection of unknown
statuses and mismatched hashes.

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest analysis/tests/test_phase.py -q
cargo test --offline --test runner_cli
```

- [ ] **Step 4: Implement selection and request handling**

Use adjacent absolute score differences for the fallback, then emit angles
`[lower, midpoint, upper]` in sorted unique order. Extend Rust validation to
accept `exploratory` without weakening schema, hash, seed, or task-config
checks.

- [ ] **Step 5: Verify GREEN and commit**

Run both commands from Step 3, then:

```bash
git add tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/phase.py \
  tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_phase.py \
  tracks/qmc/solutions/卧龙凤雏/learning-mit/src/runner.rs \
  tracks/qmc/solutions/卧龙凤雏/learning-mit/tests/runner_cli.rs
git commit -m "feat: refine exploratory DIII candidates deterministically"
```

---

### Task 4: Build hierarchical estimator diagnostics and claim gates

**Files:**
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/bootstrap.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/casimir.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/anisotropy.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/gates.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_bootstrap.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_casimir.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_anisotropy.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_gates.py`

**Interfaces:**
- Extends `CandidateDistribution` with entanglement samples, valid replicate
  count, failure fraction, and 2.5/97.5 percentiles.
- Extends `CasimirFit` with `covariance_condition` and
  `stable_without_smallest`.
- Produces `ClaimDecision(status, publish_central_charge, central_charge,
  reasons)` where status is `candidate`, `exploratory`, or `unavailable`.

- [ ] **Step 1: Write failing gate and bootstrap tests**

Assert exact reason strings:

```python
{
    "diii_transition_not_bracketed",
    "fewer_than_five_diii_widths",
    "fewer_than_four_streams_per_width",
    "fewer_than_32_complete_blocks",
    "casimir_fit_unstable",
    "anisotropy_unstable",
    "estimator_disagreement",
}
```

Test that a valid exploratory estimate is retained in
`central_charge` while `publish_central_charge` remains false, and that fewer
than four widths returns `unavailable`.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest \
  analysis/tests/test_bootstrap.py \
  analysis/tests/test_casimir.py \
  analysis/tests/test_anisotropy.py \
  analysis/tests/test_gates.py -q
```

- [ ] **Step 3: Add diagnostics and stability calculations**

Use `np.linalg.cond` on the normal matrix; bootstrap exactly 1000 replicates
with analysis seed 122; discard only numerically invalid replicates; mark
`unavailable` if more than 5% fail. Compare estimators with
`abs(c_s-c_c) <= 1.96*sqrt(sigma_s**2 + sigma_c**2)`.

- [ ] **Step 4: Make gate evaluation total and machine-readable**

Return all applicable reasons in deterministic order. Validation-oracle
failure remains stronger than scientific inconclusiveness and maps to
`unavailable` with the validation reason.

- [ ] **Step 5: Verify GREEN and commit**

Run Step 2, then:

```bash
git add tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis
git commit -m "feat: gate effective central charge estimates"
```

---

### Task 5: Integrate the estimators into the frozen summary

**Files:**
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/run_analysis.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/data_io.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/summary_fixture.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_data_io.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_end_to_end.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/verify_outputs.py`

**Interfaces:**
- Produces summary keys:

```json
{
  "candidate_selection": {},
  "entanglement_c_eff": {},
  "casimir_c_eff": {},
  "estimator_comparison": {},
  "claim": {"status": "", "reasons": []}
}
```

- [ ] **Step 1: Extend the fixture and write failing schema tests**

Assert that exploratory summaries contain finite point estimates and
intervals, `claim.reasons` is nonempty, and the legacy diagnostic
`entanglement.coefficients[].c` remains unchanged. Assert unavailable
summaries contain JSON `null`, never Python string `"None"`.

- [ ] **Step 2: Run end-to-end tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest \
  analysis/tests/test_data_io.py \
  analysis/tests/test_end_to_end.py -q
```

- [ ] **Step 3: Compose the new modules in `build_summary`**

Select strict or exploratory candidate deterministically, construct
stream/block grouped inputs, fit both estimators, apply claim gates, and
serialize NumPy values as finite built-in numbers. Keep the existing XY
validation fields.

- [ ] **Step 4: Strengthen artifact verification**

Reject reports that publish a candidate without five widths, stable alpha,
estimator agreement, or complete finite diagnostics. Accept finite
exploratory values only when all failed reasons are present.

- [ ] **Step 5: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m pytest analysis/tests -q
git add tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis
git commit -m "feat: summarize dual effective central charge estimates"
```

---

### Task 6: Add plots and bilingual standalone report sections

**Files:**
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/plots.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/report_model.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/locale.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_plots.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis/tests/test_reports.py`

**Interfaces:**
- Produces six localized PNGs:
  `entropy-chord-fit.png`, `entropy-ceff-extrapolation.png`,
  `casimir-fit.png`, `casimir-residuals.png`,
  `anisotropy-stability.png`, `ceff-comparison.png`.
- Adds a localized estimator table and claim-gate table.

- [ ] **Step 1: Write failing plot/report tests**

Assert all six figures are nonempty, English and Chinese paths are distinct,
numeric fact dictionaries match, status wording contains `exploratory` /
`探索性`, and no report calls the legacy `c` a central charge.

- [ ] **Step 2: Run and verify RED**

Run:

```bash
.venv/bin/python -m pytest \
  analysis/tests/test_plots.py \
  analysis/tests/test_reports.py -q
```

- [ ] **Step 3: Implement plots**

Use error bars for both estimators, show fit windows and residual zero lines,
annotate failed gates outside the plotting area, and label all angles as
`\(\phi/\pi\)`. Plot unavailable quantities as an explanatory panel rather
than zero.

- [ ] **Step 4: Implement bilingual report content**

Explain the two formulas, parameter meanings, candidate selection, bootstrap,
stability checks, estimator disagreement, and claim level. Put an
exploratory-warning callout immediately before the numeric summary.

- [ ] **Step 5: Verify GREEN and commit**

Run all learning-MIT Python tests, then:

```bash
git add tracks/qmc/solutions/卧龙凤雏/learning-mit/analysis
git commit -m "docs: report learning MIT effective central charge fits"
```

---

### Task 7: Execute and freeze production-v2

**Files:**
- Create: the timestamped result directory printed by
  `./run.sh production-v2`, retained as shell variable `RESULT_DIR`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/FROZEN_RESULT`
- Modify: `tracks/qmc/solutions/卧龙凤雏/learning-mit/README.md`

**Interfaces:**
- Consumes: production-v2 config and completed implementation.
- Produces: hash-bound streams, blocks, summary, plots, bilingual HTML/PDF,
  manifest, and v2 frozen pointer.

- [ ] **Step 1: Run all pre-production tests**

Run:

```bash
make test
```

Expected: all Rust and learning-MIT Python tests pass.

- [ ] **Step 2: Run a deterministic tiny replay**

Run `run-test` twice with the same seed into two temporary directories and
compare `raw/blocks.csv` plus physical stream JSON files with `diff -qr`.
Expected: byte-identical physical outputs.

- [ ] **Step 3: Run the v2 benchmark and inspect forecast**

Declare a task-specific result path and start the run explicitly:

```bash
RESULT_DIR="$(pwd)/../../../results/learning-mit-production-v2-$(date +%Y%m%d-%H%M%S)"
./run.sh production-v2 "$RESULT_DIR"
```

The orchestration forecast gate must abort before locator simulation if
`raw/benchmark.json` exceeds the declared 5100-second scientific hard stop.
Otherwise retain the exact `RESULT_DIR` value for resume and freezing.

- [ ] **Step 4: Complete or resume production-v2**

Use the exact same run directory for resume. Do not edit seeds or a completed
task configuration. Permit reserve only for the declared largest-width or
candidate-stream reasons.

- [ ] **Step 5: Audit and freeze**

Verify every `manifest.artifact_sha256` entry with `shasum -a 256`, confirm
all physical streams are complete, and compute the summary hash. Update
`FROZEN_RESULT` to the v2 path, hash, and exact claim status without deleting
the v1 result.

- [ ] **Step 6: Commit**

```bash
test -n "$RESULT_DIR"
test -f "$RESULT_DIR/manifest.json"
git add -f "$RESULT_DIR"
git add tracks/qmc/solutions/卧龙凤雏/learning-mit/FROZEN_RESULT \
  tracks/qmc/solutions/卧龙凤雏/learning-mit/README.md
git commit -m "results: freeze learning MIT effective central charge study"
```

---

### Task 8: Integrate the v2 result into the four report outputs

**Files:**
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/sources.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/report_model.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/report_model_zh.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/analysis/locale.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/conftest.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_sources.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_report_model.py`
- Modify: `tracks/qmc/solutions/卧龙凤雏/integrated-report/tests/test_report_model_zh.py`

**Interfaces:**
- Extends `LearningMitResult` with both estimators, intervals, comparison,
  claim status, failed reasons, and six figure paths.
- Preserves the tuple of the three benchmark `ModelResult` objects exactly.

- [ ] **Step 1: Write failing loader tests**

Assert the loader follows `FROZEN_RESULT`, rejects a wrong summary hash,
requires both estimator records and all reasons, and does not add
learning-MIT to the three benchmark comparison tuple.

- [ ] **Step 2: Write failing bilingual chapter tests**

Assert the open-research chapter contains both estimates, both intervals,
candidate/exploratory state, failed gates, formulas, and all new figures in
English and Chinese.

- [ ] **Step 3: Run and verify RED**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_sources.py \
  tests/test_report_model.py \
  tests/test_report_model_zh.py -q
```

- [ ] **Step 4: Implement loader and chapters**

Validate all finite values and intervals at the loader boundary. Add the
effective-central-charge material only to the separate open-research chapter;
do not modify the existing three benchmark cards or their target comparisons.

- [ ] **Step 5: Build and verify**

Run:

```bash
make test
.venv/bin/python build_report.py --language all
```

Copy the standalone v2 HTML/PDF to their stable output names and rebuild the
two integrated HTML/PDF outputs.

- [ ] **Step 6: Commit**

```bash
git add tracks/qmc/solutions/卧龙凤雏/integrated-report output/html output/pdf
git commit -m "docs: integrate learning MIT effective central charge results"
```

---

### Task 9: Perform final scientific, structural, and visual verification

**Files:**
- Verify: all files changed since the design commit.

**Interfaces:**
- Produces: a clean, reviewable feature branch with reproducible evidence.

- [ ] **Step 1: Run fresh complete tests**

Run in the learning-MIT module:

```bash
make test
```

Run in the integrated-report module:

```bash
make test
```

- [ ] **Step 2: Audit determinism, RNG, and hashes**

Run:

```bash
rg -n 'StdRng|SmallRng|thread_rng|rand::random' \
  tracks/qmc/solutions/卧龙凤雏/learning-mit/src
git diff --check
```

Recompute all v2 manifest hashes and confirm the pointer summary hash matches.
Expected: no alternate RNG hits, no diff errors, zero hash mismatches.

- [ ] **Step 3: Audit HTML**

Verify all four HTML documents have the correct `lang`, viewport, responsive
CSS, valid navigation targets, embedded images, no external assets, and no
unfinished-marker text or literal `None`.

- [ ] **Step 4: Render and inspect PDFs**

Use the `pdf` skill to render every page of the four PDFs. Inspect contact
sheets plus every page containing a new fit, table, formula, or gate callout.
Reject clipping, overlapping labels, missing CJK glyphs, orphan captions,
unreadable axes, or inconsistent numeric facts.

- [ ] **Step 5: Request local review and address findings**

Use the `requesting-code-review` skill. Because subagent delegation requires
explicit user authorization in this environment, perform the review locally
unless the user has separately requested delegation. Re-run affected tests
after every correction.

- [ ] **Step 6: Commit final corrections and verify clean state**

```bash
git status --short
git log --oneline --decorate -12
```

Expected: clean feature worktree and all implementation commits present.

- [ ] **Step 7: Finish the branch**

Use `verification-before-completion`, then
`finishing-a-development-branch`, and offer local merge, push/PR, or keeping
the branch as-is.
