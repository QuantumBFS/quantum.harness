# Challenge #148 Post-run Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:executing-plans` to execute this plan task by task in the
> current session.  Do not delegate work unless the user explicitly requests
> delegation.

**Goal:** Turn the completed triangular- and honeycomb-lattice QMC scans into
audited critical fields, an actual-`Dltau²` extrapolation, the ratio
`h_c(triangular)/h_c(honeycomb)`, and a reproducible challenge report.

**Architecture:** Preserve the four raw run directories as immutable inputs.
Build one normalized cell/bin table, apply quality gates before fitting, then
run the declared finite-size model and time-step extrapolation from that table.
All derived data, plots, and reports go to one ignored analysis result
directory; reusable analysis code and tests stay under the solution directory.

**Tech stack:** Python 3 standard library, NumPy 2.5, SciPy 1.18,
Matplotlib 3.11, existing Julia/MPI tests, and the harness report renderer.
Pandas is not required.

## Global constraints

- Hamiltonian:
  `H = J1 Σ_<i,j> σᶻ_i σᶻ_j − hTrfd Σ_i σˣ_i`.
- Preserve `J1 = −1`, `J2 = 0`, periodic boundaries, and `BetaT = L/hTrfd`.
- Primary observable: `Q = ⟨m²⟩²/⟨m⁴⟩`.
- Use metadata `actual_parameters.Dltau`, never only requested
  `FixedDltau`, in the time-step analysis.
- Use fixed PRE exponents `yt = 1.587` and `yi = −0.815`.
- Never choose a fit because its result is closer to `√5`.
- Never silently omit a missing, failed, nonfinite, or rejected cell.
- Do not combine original and extended sampling budgets without an explicit
  run identifier and selection record.
- Result directories remain gitignored and must not be force-added.
- Preserve the pre-existing `.knowledge/` changes and keep them outside any
  solution-code staging operation.
- Do not run `git add .`, commit, push, or update PR #224 without the user's
  explicit confirmation after the final verification.

## Planned file map

Create:

```text
tracks/qmc/solutions/Only-team/
├── POST_RUN_ANALYSIS_PLAN.md
├── scripts/
│   ├── audit_challenge_results.py
│   ├── assemble_challenge_dataset.py
│   ├── fit_binder_scaling.py
│   ├── extrapolate_dtau.py
│   ├── plot_challenge_results.py
│   └── build_challenge_run.py
└── test/
    └── test_postrun_analysis.py
```

Create the ignored output directory:

```text
tracks/qmc/results/Only-team/challenge-analysis-20260729/
├── raw_inventory.json
├── audit.csv
├── audit.json
├── cells.csv
├── bins.csv
├── finite_size_fits.csv
├── finite_size_bootstrap.csv
├── dtau_fits.csv
├── dtau_bootstrap.csv
├── final_results.json
├── run.json
├── report.json
├── report.html
└── figures/
```

---

### Task 1: Freeze and fetch the completed raw runs

**Files:**

- Read:
  `tracks/qmc/results/Only-team/challenge-extremes-min-20260729/`
- Read:
  `tracks/qmc/results/Only-team/challenge-extremes-max-20260729/`
- Populate:
  `tracks/qmc/results/Only-team/challenge-production-triangular-20260729/`
- Populate:
  `tracks/qmc/results/Only-team/challenge-production-honeycomb-20260729/`
- Create:
  `tracks/qmc/results/Only-team/challenge-analysis-20260729/raw_inventory.json`

**Interfaces:**

- Consumes the remote root
  `/work/home/acyv3xww1l/qmc-tfim-challenge-production-20260729-a`.
- Produces four immutable local input runs and a SHA-256 inventory.

- [ ] **Step 1: Verify scheduler completion before copying**

  Run:

  ```bash
  ssh scnet \
      'sacct -j 22989492,22989502,22989546,22989553 \
      --format=JobID,State,ExitCode,Elapsed,MaxRSS -n -P'
  ```

  Expected: every scientific task is `COMPLETED` with exit code `0:0`; no
  `FAILED`, `TIMEOUT`, or `OUT_OF_MEMORY` entry.

- [ ] **Step 2: Fetch production results without deleting local files**

  Run:

  ```bash
  rsync -a --checksum --itemize-changes \
      scnet:/work/home/acyv3xww1l/qmc-tfim-challenge-production-20260729-a/tracks/qmc/results/Only-team/challenge-production-triangular-20260729/ \
      tracks/qmc/results/Only-team/challenge-production-triangular-20260729/

  rsync -a --checksum --itemize-changes \
      scnet:/work/home/acyv3xww1l/qmc-tfim-challenge-production-20260729-a/tracks/qmc/results/Only-team/challenge-production-honeycomb-20260729/ \
      tracks/qmc/results/Only-team/challenge-production-honeycomb-20260729/
  ```

  Expected: 78 triangular and 71 honeycomb cell directories are present.

- [ ] **Step 3: Record raw provenance**

  `raw_inventory.json` must contain the four run IDs, four run-spec hashes,
  all 177 manifest hashes, scheduler job IDs, fetch time, remote root, and
  the command used to fetch the data.

- [ ] **Step 4: Confirm raw directories remain ignored**

  Run:

  ```bash
  git status --short --ignored tracks/qmc/results/Only-team/
  git diff --cached --name-only
  ```

  Expected: result directories are ignored and the staging area is empty.

---

### Task 2: Implement the production-integrity audit with TDD

**Files:**

- Create:
  `tracks/qmc/solutions/Only-team/scripts/audit_challenge_results.py`
- Create:
  `tracks/qmc/solutions/Only-team/test/test_postrun_analysis.py`
- Produce:
  `tracks/qmc/results/Only-team/challenge-analysis-20260729/audit.csv`
- Produce:
  `tracks/qmc/results/Only-team/challenge-analysis-20260729/audit.json`

**Interfaces:**

- `load_cell(cell_dir: Path) -> CellRecord`
- `half_chain_z(values: Sequence[float]) -> float`
- `audit_runs(run_dirs: Sequence[Path]) -> AuditReport`
- `AuditReport.write_csv(path)` and `AuditReport.write_json(path)`

- [ ] **Step 1: Write failing audit tests**

  Tests must construct temporary synthetic cells and assert:

  ```python
  self.assertEqual(report.total_cells, 177)
  self.assertEqual(report.unique_parameter_cells, 177)
  self.assertEqual(report.failed_cells, [])
  self.assertEqual(report.missing_cells, [])
  self.assertEqual(record.bin_count, 32)
  self.assertEqual(record.rank_seed_count, 32)
  self.assertEqual(record.distinct_rank_seed_count, 32)
  self.assertTrue(record.hashes_valid)
  ```

  Separate tests must corrupt one hash, remove one bin, duplicate one
  parameter key, insert `NaN`, and duplicate one rank seed; each corruption
  must produce a named audit failure.

- [ ] **Step 2: Run the focused test and observe failure**

  Run:

  ```bash
  .venv/bin/python -m unittest \
      tracks/qmc/solutions/Only-team/test/test_postrun_analysis.py -v
  ```

  Expected: failure because `audit_challenge_results.py` is not implemented.

- [ ] **Step 3: Implement the minimal audit**

  Validate for every cell:

  - manifest state is `success`;
  - manifest parameters equal metadata actual parameters;
  - `J1 = −1`, `J2 = 0`, `nLocal = 1`, `nWolff = 5`;
  - `BetaT = L/hTrfd`;
  - `Dltau = BetaT/LTrot`;
  - exactly 32 bins numbered 1 through 32;
  - exactly 32 distinct rank seeds;
  - all `m2_bin`, `m4_bin`, and `Q_bin` values are finite;
  - `Q_bin = m2_bin²/m4_bin`;
  - all manifest-declared file hashes match;
  - every parameter key
    `(lattice,L,hTrfd,FixedDltau,actual_Dltau)` is unique.

- [ ] **Step 4: Add quality diagnostics without automatic rejection**

  Compute raw first-half/second-half z-scores independently for m² and Q:

  ```text
  z = |mean(first) − mean(second)|
      / sqrt(SEM(first)² + SEM(second)²)
  ```

  Record `z_m2`, `z_Q`, `binder_Q_error`, and the declared gate result.  Do
  not resubmit or discard a cell in this task.

- [ ] **Step 5: Run focused and full existing tests**

  Run:

  ```bash
  .venv/bin/python -m unittest \
      tracks/qmc/solutions/Only-team/test/test_postrun_analysis.py -v

  julia --project=tracks/qmc/solutions/Only-team \
      tracks/qmc/solutions/Only-team/test/runtests.jl
  ```

  Expected: all Python tests and all Julia/MPI tests pass.

---

### Task 3: Assemble one normalized analysis dataset

**Files:**

- Create:
  `tracks/qmc/solutions/Only-team/scripts/assemble_challenge_dataset.py`
- Modify:
  `tracks/qmc/solutions/Only-team/test/test_postrun_analysis.py`
- Produce:
  `tracks/qmc/results/Only-team/challenge-analysis-20260729/cells.csv`
- Produce:
  `tracks/qmc/results/Only-team/challenge-analysis-20260729/bins.csv`

**Interfaces:**

- `assemble_cells(audit: AuditReport) -> list[CellRow]`
- `assemble_bins(audit: AuditReport) -> list[BinRow]`

`cells.csv` must include:

```text
run_id,cell_id,lattice,L,hTrfd,FixedDltau,Dltau,LTrot,
nprocs,nWarm,NmBin,NSwep,NmMeaConfg,
m2,m2_error,binder_Q,binder_Q_error,
z_m2,z_Q,scan_kind,quality_status
```

`bins.csv` must include:

```text
run_id,cell_id,lattice,L,hTrfd,FixedDltau,Dltau,
bin,m2_bin,m4_bin,Q_bin
```

- [ ] **Step 1: Write failing assembly tests**

  Assert exact column order, 177 cell rows, `177×32 = 5664` bin rows, stable
  sorting, no duplicated parameter key, and preservation of actual
  `Dltau`.

- [ ] **Step 2: Implement deterministic assembly**

  Sort cells by:

  ```text
  lattice, FixedDltau, L, hTrfd
  ```

  Write floats with 17 significant digits and use only the Python standard
  `csv` module so the result is reproducible without pandas.

- [ ] **Step 3: Verify byte-for-byte reproducibility**

  Run the assembler twice into two temporary directories and compare:

  ```bash
  sha256sum <first>/cells.csv <second>/cells.csv
  sha256sum <first>/bins.csv <second>/bins.csv
  ```

  Expected: matching hashes for each corresponding file.

---

### Task 4: Apply quality gates and decide whether any extension is needed

**Files:**

- Modify:
  `tracks/qmc/solutions/Only-team/scripts/audit_challenge_results.py`
- Modify:
  `tracks/qmc/solutions/Only-team/test/test_postrun_analysis.py`
- Produce:
  `tracks/qmc/results/Only-team/challenge-analysis-20260729/quality_gates.csv`
- Produce:
  `tracks/qmc/results/Only-team/challenge-analysis-20260729/rerun_candidates.json`

**Interfaces:**

- `evaluate_quality(cell: CellRecord) -> QualityDecision`

- [ ] **Step 1: Encode the declared automatic gates**

  A cell fails an automatic gate if:

  - a completeness or finiteness audit fails;
  - `z_m2 > 3` or `z_Q > 3`;
  - triangular `L ≥ 40` and `SEM(Q) > 1.0×10⁻⁴`.

  The design text specifies a honeycomb threshold only under `L ≥ 40`, but
  the approved honeycomb maximum is `L=32`.  Preserve that literal rule and
  separately report `SEM(Q)` for honeycomb `L=28,32` as a diagnostic.  Do not
  silently reinterpret the threshold.

- [ ] **Step 2: Test gate boundaries**

  Include exact tests at z-score 3, triangular SEM `1.0×10⁻⁴`, and one value
  immediately above each boundary.

- [ ] **Step 3: Stop for a scientific decision if candidates exist**

  Present the candidate table before fitting.  A cell that fails only the
  SEM target may be proposed for `NSwep=4000` in a new run directory.  No
  extension is submitted automatically, and no original output is replaced.

- [ ] **Step 4: Freeze the accepted-cell selection**

  Write the accepted run ID for every parameter key and hash the resulting
  selection.  All later fits consume this file rather than rediscovering
  cells independently.

---

### Task 5: Fit the finite-size Binder-ratio model

**Files:**

- Create:
  `tracks/qmc/solutions/Only-team/scripts/fit_binder_scaling.py`
- Modify:
  `tracks/qmc/solutions/Only-team/test/test_postrun_analysis.py`
- Produce:
  `tracks/qmc/results/Only-team/challenge-analysis-20260729/finite_size_fits.csv`
- Produce:
  `tracks/qmc/results/Only-team/challenge-analysis-20260729/finite_size_bootstrap.csv`

**Interfaces:**

- `binder_model(theta, L, h, terms) -> ndarray`
- `fit_variant(rows, lattice, Lmin, terms) -> FitResult`
- `bootstrap_variant(bin_rows, fit_spec, samples, rng) -> BootstrapResult`

Use:

```text
x = h − h_c

Q_L(h) =
    Q*
    + a1 x L^yt
    + a2 x² L^(2yt)
    + b1 L^yi
    + b2 L^(2yi)
    + c1 x L^(yt+yi)

yt = 1.587
yi = −0.815
```

- [ ] **Step 1: Write synthetic recovery tests**

  Generate deterministic synthetic curves with known `h_c`, `Q*`, `a1`,
  `b1`, and optional correction terms.  Assert that noiseless fits recover
  `h_c` within `1×10⁻¹⁰` and noisy bootstrap intervals contain the injected
  value.

- [ ] **Step 2: Implement weighted nonlinear least squares**

  Use `scipy.optimize.least_squares` with residuals:

  ```text
  residual_i = (Q_i − model_i) / SEM(Q_i)
  ```

  Record parameter values, covariance estimate, `χ²`, degrees of freedom,
  `χ²/dof`, convergence status, and boundary contact.

- [ ] **Step 3: Enumerate every declared analysis variant**

  For each lattice and `Lmin = 12,16,20,24`, run the eight predeclared
  combinations obtained by independently including or excluding
  `a2`, `b2`, and `c1`.  Never stop after finding a preferred central value.

- [ ] **Step 4: Bootstrap from bin-level inputs**

  For each of at least 2000 deterministic bootstrap replicas:

  - resample each cell's post-discard bins independently with replacement;
  - apply the declared extrema trimming;
  - recompute the cell Q estimate;
  - refit the same model variant;
  - retain every success and count every failed replica explicitly.

  Require at least 95% successful replicas before treating a variant as
  numerically stable.

- [ ] **Step 5: Apply predeclared fit-selection rules**

  A reportable fit must:

  - converge without a parameter at its allowed boundary;
  - place `h_c` inside the measured field range, otherwise carry an explicit
    extrapolation warning;
  - have positive degrees of freedom;
  - have a stable bootstrap;
  - remain compatible under adjacent `Lmin` choices and removal of the
    largest size.

  Report all fits.  The primary fit is selected from stability and fit
  quality only, before computing `R−√5`.

---

### Task 6: Perform the actual-`Dltau²` extrapolation

**Files:**

- Create:
  `tracks/qmc/solutions/Only-team/scripts/extrapolate_dtau.py`
- Modify:
  `tracks/qmc/solutions/Only-team/test/test_postrun_analysis.py`
- Produce:
  `tracks/qmc/results/Only-team/challenge-analysis-20260729/dtau_fits.csv`
- Produce:
  `tracks/qmc/results/Only-team/challenge-analysis-20260729/dtau_bootstrap.csv`

**Interfaces:**

- `fit_step_group(rows, fit_spec) -> StepCriticalField`
- `linear_dtau2_fit(points) -> ExtrapolationResult`

- [ ] **Step 1: Fix the time-step fit family before examining the extrapolated
  answer**

  Use the correction-term family selected from the main-grid stability
  analysis for all three requested steps.  Do not select a different model
  independently at each step.

- [ ] **Step 2: Fit one critical field per requested step**

  Use:

  ```text
  triangular L = 32,40,48
  honeycomb  L = 24,28,32
  FixedDltau = 0.013,0.016,0.020
  five matched fields per lattice and step
  ```

  For each group, record the mean, minimum, and maximum actual `Dltau²`.

- [ ] **Step 3: Extrapolate linearly**

  Fit:

  ```text
  h_c(Dltau) = h_c(0) + cτ Dltau²
  ```

  Propagate the finite-size bootstrap draws through this fit.  With three
  time-step points, report the one residual degree of freedom and show all
  three points.

- [ ] **Step 4: Run a joint-fit sensitivity check**

  As a diagnostic, embed
  `h_c(Dltau)=h_c(0)+cτ Dltau²` directly in the Binder model using each
  cell's actual `Dltau`.  Compare its `h_c(0)` with the primary two-stage
  extrapolation.

- [ ] **Step 5: Stop rather than force a nonlinear trend**

  If the three points do not support a linear `Dltau²` description, report
  the failure.  Propose `FixedDltau=0.010` only as a separate user-approved
  computation.  Closeness of a Binder ratio to 0.5 is a plotted diagnostic,
  not an inclusion rule.

---

### Task 7: Compute the ratio and challenge verdict

**Files:**

- Modify:
  `tracks/qmc/solutions/Only-team/scripts/extrapolate_dtau.py`
- Modify:
  `tracks/qmc/solutions/Only-team/test/test_postrun_analysis.py`
- Produce:
  `tracks/qmc/results/Only-team/challenge-analysis-20260729/final_results.json`

**Interfaces:**

- `ratio_bootstrap(tri_draws, honey_draws) -> RatioResult`

- [ ] **Step 1: Pair independent bootstrap draws deterministically**

  Compute for every paired draw:

  ```text
  R = h_c(triangular) / h_c(honeycomb)
  Δ√5 = R − √5
  ```

  Report the median, 68% interval, 95% interval, standard error, and
  `Δ√5/σ`.

- [ ] **Step 2: Evaluate the declared precision targets**

  Record pass/fail for:

  ```text
  σ[h_c(triangular)] ≤ 1.8×10⁻⁵
  σ[h_c(honeycomb)]  ≤ 8.0×10⁻⁶
  σ[R]               ≤ 1.19×10⁻⁵
  ```

- [ ] **Step 3: Test fifth-decimal stability**

  Compare the primary result against:

  - adjacent `Lmin` fits;
  - removal of the largest size;
  - accepted correction-term variants;
  - the joint time-step sensitivity fit.

  The final fifth decimal is stable only if every accepted variant rounds to
  the same fifth decimal.

- [ ] **Step 4: Compare with PRE without replacing the computed result**

  Include PRE central values and uncertainties, the achieved improvement
  factors, and whether the new interval supports, excludes, or cannot
  distinguish exact `√5`.

---

### Task 8: Generate diagnostic figures

**Files:**

- Create:
  `tracks/qmc/solutions/Only-team/scripts/plot_challenge_results.py`
- Modify:
  `tracks/qmc/solutions/Only-team/test/test_postrun_analysis.py`
- Produce figures under:
  `tracks/qmc/results/Only-team/challenge-analysis-20260729/figures/`

**Interfaces:**

- `plot_binder_curves(cells, lattice, path)`
- `plot_fit_stability(fits, lattice, path)`
- `plot_dtau_extrapolation(points, lattice, path)`
- `plot_ratio(result, path)`

- [ ] **Step 1: Add plot smoke tests**

  Use a noninteractive backend and assert that each plot function creates a
  nonempty PNG and PDF from a small synthetic dataset.

- [ ] **Step 2: Produce four scientific diagnostics**

  Create:

  ```text
  binder_Q_triangular.png/.pdf
  binder_Q_honeycomb.png/.pdf
  finite_size_fit_stability.png/.pdf
  dtau2_extrapolation.png/.pdf
  ratio_vs_sqrt5.png/.pdf
  ```

  Every figure must show uncertainties and identify excluded or warned cells
  without hiding them.

- [ ] **Step 3: Visually inspect every PNG**

  Confirm readable labels, visible error bars, no clipped legends, and no
  claim stronger than the audited fit supports.

---

### Task 9: Build the reproducible run record and challenge report

**Files:**

- Create:
  `tracks/qmc/solutions/Only-team/scripts/build_challenge_run.py`
- Modify:
  `tracks/qmc/solutions/Only-team/README.md`
- Produce:
  `tracks/qmc/results/Only-team/challenge-analysis-20260729/run.json`
- Produce:
  `tracks/qmc/results/Only-team/challenge-analysis-20260729/report.json`
- Produce:
  `tracks/qmc/results/Only-team/challenge-analysis-20260729/report.html`

**Interfaces:**

- `build_run(audit, fits, extrapolation, figures) -> dict`

- [ ] **Step 1: Write a schema fixture test**

  Assert that `run.json` contains the Hamiltonian, lattice sizes, scan axes,
  sampler settings, raw inventory hash, audit verdict, finite-size variants,
  time-step variants, final numbers, residual uncertainties, and figure
  paths.

- [ ] **Step 2: Generate `run.json` deterministically**

  Record exact commands, Python and Julia versions, Git commit if available,
  and hashes for every derived CSV, JSON, and figure.

- [ ] **Step 3: Update the README**

  Add the final reproducible analysis command and distinguish:

  - finite-size statistical uncertainty;
  - time-step extrapolation uncertainty;
  - fit-variant systematic spread;
  - unresolved limitations.

- [ ] **Step 4: Run the challenge-report cleanliness gate**

  Inspect `git status` and `git diff --stat HEAD`.  Allowed changes remain
  under `tracks/qmc/solutions/Only-team/`, ignored results, and the
  pre-existing `.knowledge/` paths.  Stop if any unrelated path appears.

- [ ] **Step 5: Draft the four challenge-report sections interactively**

  Confirm with the user, in order:

  - Challenge;
  - Approach;
  - Results;
  - Highlight.

- [ ] **Step 6: Render the standalone report**

  Run:

  ```bash
  python3 skills/report/render_report.py \
      tracks/qmc/results/Only-team/challenge-analysis-20260729
  ```

  Expected: a self-contained `report.html` with all figures present.

---

### Task 10: Final verification and commit handoff

**Files:**

- Verify all solution and analysis files.
- Do not create a commit in this task without explicit user confirmation.

- [ ] **Step 1: Run all tests**

  ```bash
  .venv/bin/python -m unittest \
      tracks/qmc/solutions/Only-team/test/test_postrun_analysis.py -v

  julia --project=tracks/qmc/solutions/Only-team \
      tracks/qmc/solutions/Only-team/test/runtests.jl
  ```

- [ ] **Step 2: Re-run the complete analysis**

  Run the audit, assembly, finite-size fits, time-step extrapolation, plots,
  and run-record generation into a fresh temporary result directory.  Compare
  all deterministic artifact hashes and compare bootstrap summaries using
  their fixed seed.

- [ ] **Step 3: Verify the final checklist**

  Require:

  - 177/177 unique cells audited;
  - zero missing or failed cells;
  - every quality warning disclosed;
  - all fit variants present;
  - all bootstrap failures counted;
  - actual `Dltau²` used;
  - `R`, `R−√5`, and uncertainty reported;
  - all figures and the HTML report open correctly;
  - no result directory staged.

- [ ] **Step 4: Present the commit boundary**

  Show the exact solution files proposed for staging, the ignored result
  artifacts, and the separate `.knowledge/` changes.  Wait for the user's
  confirmation before any `git add`, commit, push, or update to PR #224.
