# Phase 9 Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, resumable Phase 9 NN/mean-field validation
workflow and final report generator without starting any physics calculation.

**Architecture:** A pure `phase9_protocol` module owns fixed cell sets,
crossing/gap analysis, and convergence flags. Separate CLIs plan cells, run
one NN parity state, and assemble reports. The existing long-range
single-state runner and sigma-fit regeneration remain unchanged and are
referenced by generated commands.

**Tech Stack:** Python 3.11, NumPy, TeNPy, matplotlib, pytest, JSON/CSV/HDF5.

## Global Constraints

- New physics is limited to NN `L=16,32,64` and the qualified mean-field
  benchmark `sigma=2/3` at `L=16,32,64,96`. Sigma=0.4 is coupling-only.
- NN uses fixed `Gamma={0.98,1.00,1.02}`; mean field uses the published
  fixed fields `Gamma_c=3.673` and `5.85`, respectively.
- Baseline `chi=64`, `K=24`, `alpha=0.5`, `r_fit=2048`.
- No automatic `chi=128`, no `chi=256`, no `K=32`, no `L>96`, and no Gamma
  extension.
- NN z is a scaling-pipeline diagnostic, not a precision estimate.
- Pairwise `z_eff` values are discrete logarithmic slopes of DMRG parity
  gaps. They are gap-based pairwise effective dynamical exponents, not the
  QMC finite-size estimator used by Shiratani--Todo.
- Mean-field output contains z only; never `beta/nu` or `gamma/nu`.
- Sigma=2.0 is a reused finite-size crossing comparison, not an exact
  reproduction.
- Every cell is independently resumable and records complete provenance.
- No physics command is executed while implementing this plan.

---

### Task 1: Lock Phase 9 pure protocol

**Files:**
- Create: `src/lrtfim/phase9_protocol.py`
- Create: `tests/test_phase9_protocol.py`

**Interfaces:**
- Produces:
  `build_nn_spec(output_dir) -> dict`,
  `build_mean_field_spec(output_dir, fit_summaries) -> dict`,
  `state_diagnostics(summary) -> dict`,
  `analyze_nn(summaries) -> dict`,
  `analyze_mean_field(summaries, sigma, gamma) -> dict`, and
  `published_gamma_comparison() -> dict`.

- [ ] **Step 1: Write failing specification tests**

Test that NN contains exactly 18 `chi=64` cells, mean field exactly 8
`chi=64` cells, no command contains `chi=128`, the fixed fields/sizes cannot
change, and output labels exclude `beta/nu` and `gamma/nu`.

- [ ] **Step 2: Verify RED**

Run:

```bash
env PYTHONPATH=src:. conda run -n mps python -m pytest \
  tests/test_phase9_protocol.py -q
```

Expected: import failure for `lrtfim.phase9_protocol`.

- [ ] **Step 3: Implement the pure protocol**

Use `linear_crossing` for unique NN brackets, record half-grid resolution
`0.01`, compute generic gap-based pairwise effective dynamical exponents
`-log(Delta_2/Delta_1)/log(L_2/L_1)`, call
`phase8_scaling.direct_gap_power_law`, and classify state diagnostics using
relative variance `1e-10`, discarded weight `1e-7`, sweep-cap completion,
and energy ordering.

- [ ] **Step 4: Verify GREEN**

Run the Task 1 test command; expected all tests pass.

### Task 2: Add deterministic Phase 9 planner

**Files:**
- Create: `scripts/plan_phase9_validation.py`
- Create: `tests/test_phase9_planner_cli.py`

**Interfaces:**
- CLI subcommands:
  `nn --output ...`,
  `mean-field --fit-summary <sigma=2/3> --output ...`, and
  `all --fit-summary <sigma=2/3> --output-root ...`.

- [ ] **Step 1: Write failing CLI tests**

Assert exact cell order, stable identifiers, commands with `python -u`,
one output directory per cell, fit hash/provenance for mean field, no HDF5
creation, and no optional refinement cells.

- [ ] **Step 2: Verify RED**

Run the planner test alone; expected failure because the script is missing.

- [ ] **Step 3: Implement atomic planner output**

Generate NN commands invoking `scripts/run_phase9_nn_cell.py`. Generate
mean-field commands invoking `scripts/benchmark_phase6_optimizations.py`
with one parity sector, `K=24`, `alpha=0.5`, `r_fit=2048`, `chi=64`,
`--direct-only`, and the qualified fixed field `Gamma=3.673`.

- [ ] **Step 4: Verify GREEN**

Run Task 2 tests and Task 1 tests; expected all pass.

### Task 3: Add resumable NN parity-cell runner

**Files:**
- Create: `scripts/run_phase9_nn_cell.py`
- Create: `tests/test_phase9_nn_cell_cli.py`
- Modify: `src/lrtfim/checkpoints.py`

**Interfaces:**
- CLI arguments:
  `--length`, `--gamma`, `--sector`, `--chi`, `--max-sweeps`,
  `--output-dir`.
- Output:
  `summary.json`, `checkpoints/<sector>/chi<chi>/state.h5`, and
  `checkpoint.json`.

- [ ] **Step 1: Write failing lightweight tests**

Test CLI parsing, deterministic settings, NN checkpoint provenance with
`sigma=null`, exact-model hash, even-state raw-observable schema, odd-state
energy schema, and successful-cell reuse. Mock only the expensive DMRG call;
exercise real serialization helpers separately.

- [ ] **Step 2: Verify RED**

Run the NN runner tests; expected script/import failure.

- [ ] **Step 3: Implement one-cell execution**

Build `build_rotated_nearest_neighbor_tfim_mpo`, run `_run_sector`, compute
full physical `Sigmax-Sigmax` correlations and `R_xi` for even states, save
an atomic summary and HDF5 checkpoint, and flush every progress line.
Change only the checkpoint type annotation from `sigma: float` to
`sigma: float | None`; do not alter existing long-range validation.

- [ ] **Step 4: Verify GREEN**

Run checkpoint and NN runner tests; expected all pass without a production
DMRG calculation.

### Task 4: Add Phase 9 analysis/report generator

**Files:**
- Create: `scripts/report_phase9_validation.py`
- Create: `tests/test_phase9_report.py`

**Interfaces:**
- Consumes NN/mean-field summary roots, Phase 4 summary, Phase 7 broad and
  chi-validation records, Phase 8 analyses, and the approved cost estimate.
- Produces `analysis.json`, CSV tables, `report.md`, and PNG/PDF figures.

- [ ] **Step 1: Write failing fixture-driven tests**

Cover resolved and unresolved NN crossings, positive/invalid gaps,
convergence flags without refinement commands, mean-field z-only output,
sigma=2.0 finite-size wording, and explicit susceptibility limitation.

- [ ] **Step 2: Verify RED**

Run report tests; expected missing-script failure.

- [ ] **Step 3: Implement report generation**

Write cell diagnostics and independent branch status even when one branch is
unresolved. Never emit a refinement command. Include:

```text
NN: Gamma_x, gaps, L*Delta, z_eff, direct z, pipeline-only label
MF: gaps, L^(1/3)*Delta, z_eff, direct z
Gamma: sigma=1.75 and sigma=2.0 finite-size comparisons
Uncertainty: MPO, even MPS, odd MPS, finite-size/field sensitivity
Limitations: no susceptibility gamma/nu; equal-time S_eq auxiliary only
```

- [ ] **Step 4: Verify GREEN**

Run report and protocol tests; expected all pass.

### Task 5: Documentation and no-compute verification

**Files:**
- Modify: `README.md`
- Modify: `scripts/README.md`
- Verify: `docs/phase9-validation-design.md`
- Verify: `results/phase9-validation/proposal/cost-estimate.json`
- Verify: `results/phase9-validation/proposal/execution-order.md`

- [ ] **Step 1: Document exact planning commands**

Add Phase 9 scope, the three validation branches, fixed cell counts, and the
review gate. Do not describe a result that has not been computed.

- [ ] **Step 2: Generate planner outputs only**

Generate NN `run_spec.json`. Mean-field planning is allowed only after the
sigma=2/3 fit and sigma=0.4 K=24/K=32 qualification exist. The executable
specification contains only sigma=2/3 because sigma=0.4 failed the 1% gate.

- [ ] **Step 3: Run verification**

```bash
env PYTHONPATH=src:. conda run -n mps python -m pytest \
  tests/test_phase9_protocol.py \
  tests/test_phase9_planner_cli.py \
  tests/test_phase9_nn_cell_cli.py \
  tests/test_phase9_report.py -q
git diff --check
```

Expected: all focused tests pass; no new physics `summary.json` or HDF5 file
exists under `results/phase9-validation/nn-limit` or
`mean-field-fixed-fields`.

- [ ] **Step 4: Commit implementation separately from future results**

Stage only Phase 9 source, tests, documentation, and proposal/run
specification files. Do not stage `Ion.lock`, unrelated work, or any prior
result branch.
