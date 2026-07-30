# CP-AFQMC Ergodicity Challenge Submission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the completed CP-AFQMC ergodicity study as a clean, reproducible challenge submission with a paper-style report and self-contained HTML execution report.

**Architecture:** Keep reviewer-facing narrative and compact evidence at the
solution root, preserve the completed source workflow in a nested `test/`
snapshot, and keep large raw archives out of Git.  Generate the two 4x4 panels
from the compact replay CSV rather than editing a raster screenshot.

**Tech Stack:** C++17, oneMKL/LAPACK, Python 3, NumPy, Matplotlib, ALF,
CPMC-Lab/MATLAB, Slurm, Markdown, the harness HTML report renderer.

## Global Constraints

- All committed files must remain under `tracks/qmc/solutions/minnaka/`.
- Do not report Green-function stability diagnostics or the abandoned 0.01
  precision target.
- State that the mechanism is cumulative low conditional probability along a
  long path, not a single absolute node.
- Include exactly three scientific figures in the main evidence chain.
- Distinguish practical inaccessibility from a proof of global topological
  disconnection.
- State the assumptions and scope of the strict special-GHF construction.
- Do not commit build products, full Markov-chain archives, or raw cluster logs.

---

### Task 1: Curate source and evidence

**Files:**
- Create: `tracks/qmc/solutions/minnaka/test/alf_hirsch_binary/**`
- Create: `tracks/qmc/solutions/minnaka/test/cpmc_path_audit/**`
- Create: `tracks/qmc/solutions/minnaka/test/pqmc_cp_bridge/**`
- Create: `tracks/qmc/solutions/minnaka/data/replay_strata.csv`
- Create: `tracks/qmc/solutions/minnaka/data/sampling_efficiency_summary.json`
- Create: `tracks/qmc/solutions/minnaka/data/trace_dynamics_summary.json`
- Create: `tracks/qmc/solutions/minnaka/data/direct_reweight_summary.json`

**Interfaces:**
- Consumes: Git-tracked source from branch `codex/pqmc-cp-all-plans` and the
  completed result summaries.
- Produces: a self-contained source snapshot and compact evidence used by the
  figure script and reports.

- [ ] Copy only paths returned by `git ls-files test/alf_hirsch_binary
  test/cpmc_path_audit test/pqmc_cp_bridge`.
- [ ] Copy the 4x4 replay CSV and summary JSON files without raw archives.
- [ ] Write the direct-reweight summary with the recorded 1,920-chain,
  96,000-path ratio-of-sums results and provenance.
- [ ] Verify that no file larger than 10 MiB and no build/archive file entered
  the solution tree.

### Task 2: Generate the three evidence figures

**Files:**
- Create: `tracks/qmc/solutions/minnaka/scripts/make_report_figures.py`
- Create: `tracks/qmc/solutions/minnaka/figures/exhaustive_2x2_weight_efficiency.{pdf,png}`
- Create: `tracks/qmc/solutions/minnaka/figures/pqmc_weight_efficiency.{pdf,png}`
- Create: `tracks/qmc/solutions/minnaka/figures/prefix_barrier.{pdf,png}`

**Interfaces:**
- Consumes: `data/replay_strata.csv` plus the completed 2x2 vector figure.
- Produces: three colorblind-safe, publication-sized figures referenced by
  Markdown and HTML reports.

- [ ] Add a deterministic figure script that filters alive, unambiguous TI
  paths and independently reconstructs the worst one percent.
- [ ] Recreate centered physical-weight versus sampling-efficiency and
  prefix-barrier panels from numeric data.
- [ ] Copy the original 2x2 vector figure and PNG preview without altering its
  data.
- [ ] Run the script twice and compare hashes to verify deterministic output.

### Task 3: Write reviewer-facing reports

**Files:**
- Modify: `tracks/qmc/solutions/minnaka/README.md`
- Create: `tracks/qmc/solutions/minnaka/REPORT.md`
- Create: `tracks/qmc/solutions/minnaka/REPRODUCE.md`
- Create: `tracks/qmc/solutions/minnaka/EXECUTION_REPORT.md`

**Interfaces:**
- Consumes: the curated figures, measured summaries, issue #90, and Qin-Shi-
  Zhang 2016.
- Produces: a concise entry point, the scientific argument, exact reproduction
  commands, and a factual execution ledger.

- [ ] Lead `README.md` with the result, innovation, and three links.
- [ ] Write `REPORT.md` as a paper with equations, assumptions, captions,
  limitations, and citations.
- [ ] Include the positive-definite Gram-matrix proof for the special GHF trial
  and explicitly limit it to the symmetry-paired reachable sector.
- [ ] Write commands in `REPRODUCE.md` for 2x2 tests, compact 4x4 analysis, and
  the documented Slurm production workflow.
- [ ] Record hardware, path counts, energies, and runtime in
  `EXECUTION_REPORT.md`, omitting the excluded implementation diagnostics.
- [ ] Search all public documents for forbidden 0.01/Green discussion.

### Task 4: Build the self-contained challenge report

**Files:**
- Create: `tracks/qmc/results/minnaka-cpafqmc-ergodicity/run.json`
- Create: `tracks/qmc/results/minnaka-cpafqmc-ergodicity/report.json`
- Generate: `tracks/qmc/results/minnaka-cpafqmc-ergodicity/report.html`

**Interfaces:**
- Consumes: the approved title, lede, report blocks, and curated figures.
- Produces: one offline HTML page with embedded figures and equations.

- [ ] Populate the run manifest with model, method, evidence, numbers, and
  verdicts.
- [ ] Assemble Challenge, Approach, Results, and Highlight sections.
- [ ] Render with `python3 skills/report/render_report.py <run-dir>`.
- [ ] Verify that the HTML embeds all three figures and contains no missing-file
  warnings.

### Task 5: Verify and hand off

**Files:**
- Modify only files under `tracks/qmc/solutions/minnaka/` if verification finds
  issues.

**Interfaces:**
- Consumes: the completed solution tree.
- Produces: a clean, tested branch ready for PR review.

- [ ] Run the focused Python and C++ test suites from the copied source tree.
- [ ] Run Markdown link, JSON parse, figure-count, and forbidden-text checks.
- [ ] Run `git status`, `git diff --check`, and inspect the complete diff.
- [ ] Commit the solution, push the challenge branch, and confirm the existing
  PR points to the new commit.
