# L=8 Transport Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the validated L=8 workflow with offset pump paths and Delta0 scans, then produce transport-first static and interactive figures.

**Architecture:** Add path centers to the canonical model with zero defaults, and add one focused study module/CLI that composes existing Chern, polarization, and dynamics solvers. Keep old result schemas readable and reuse the completed center-path aggregate. A compact export drives plotting without copying many-body states to the local machine.

**Tech Stack:** Python, NumPy, SciPy, QuSpin, Matplotlib, Plotly, Slurm.

---

### Task 1: Offset pump paths

**Files:** `src/model.py`, `src/cluster_workflows.py`, `tests/test_model.py`, `tests/test_batch.py`

- [ ] Add failing tests for centered-path identity, offset coefficients, checkpoint metadata, and real-time reconstruction.
- [ ] Run focused tests and confirm failures are due to missing center parameters.
- [ ] Add finite `delta_center`/`Delta_center` defaults and use them only in `delta(phi)`/`Delta(phi)`.
- [ ] Persist centers conditionally so zero-center legacy checkpoints stay byte-contract compatible.
- [ ] Run focused and full regression tests.

### Task 2: Study manifest and restartable workers

**Files:** `src/transport_study.py`, `scripts/transport_study.py`, `cluster/transport_study.slurm`, `cluster/launch_transport_study.sh`, `tests/test_transport_study.py`

- [ ] Add failing manifest tests for the Delta0 grid, offset paths, deterministic unique keys, and omission of reusable center cases.
- [ ] Implement immutable JSONL manifests and deterministic per-case directories.
- [ ] Compose existing static and real-time workers without duplicating Hamiltonian or solvers.
- [ ] Add validation/aggregation that publishes only when every manifest item validates.
- [ ] Run focused and full regression tests.

### Task 3: Compact analysis export and figures

**Files:** `src/transport_analysis.py`, `scripts/plot_transport.py`, `tests/test_transport_analysis.py`

- [ ] Add failing tests for `eta=Q/2`, old/new table combination, and exact-grid plotting records.
- [ ] Export summaries plus `P(phi)`, cumulative `Q(phi)`, and theta-zero `E0/gap` arrays.
- [ ] Generate transport-first PNG/PDF panels and a standalone Plotly HTML with discrete markers and labeled interpolation.
- [ ] Verify file creation, data provenance labels, and representative numerical values.

### Task 4: Cluster deployment

**Files:** immutable remote source snapshot and one remote run directory

- [ ] Commit the tested source and deploy one immutable snapshot.
- [ ] Create the study run directory and reuse the existing center-path aggregate by reference.
- [ ] Launch one named tmux controller and one Slurm submission path.
- [ ] Verify tmux, scheduler job, resource placement, first log, and manifest counts once; then stop polling.

### Task 5: Final analysis after completion

**Files:** `results/transport_analysis/`, `results/transport_analysis/report.md`

- [ ] Validate all expected static and real-time outputs.
- [ ] Export compact data and generate all static/interactive figures.
- [ ] Interpret topology, gap protection, nonadiabatic loss, path dependence, and efficiency.
- [ ] Record exact parameters, provenance, numerical caveats, and artifact paths in Chinese.
