# Phase 4 Benchmark Workflow Implementation Plan

**Goal:** Implement the NN-TFIM ED/DMRG qualification workflow without
starting long-range production calculations.

**Architecture:** `lrtfim.dmrg_workflow` owns model construction, state
targeting, and diagnostics. `benchmark_tfim.py` runs the L=8,10,12 gate and
creates CSV/JSON plus the L*gap figure.

**Tech Stack:** Python 3.11, NumPy, TeNPy 1.1.0, matplotlib, pytest.

## Constraints

- Periodic Pauli TFIM, Gamma=1 for the z=1 benchmark.
- Same DMRG settings for nearest-neighbor and long-range workflows.
- First excited state uses `orthogonal_to`.
- No L=256 run.

## Task 1: Exact benchmark MPO

- [x] Add failing dense-matrix tests for all NN ring bonds and the field.
- [x] Implement the compact NN periodic MPOGraph.
- [x] Verify Pauli normalization and Hermiticity.

## Task 2: DMRG state targeting

- [x] Add failing small-L tests for ground and orthogonal excited states.
- [x] Implement shared options, product-state starts, sweep-stat collection,
      variance, overlap, and discarded-weight reporting.
- [x] Compare small-L DMRG energies against ED.

## Task 3: Benchmark command and plot

- [x] Add a failing CLI/output-schema test.
- [x] Implement L=8,10,12 ED/DMRG execution and incremental JSON writes.
- [x] Plot Delta and L*Delta in PDF and PNG with accessible styling.
- [x] Run the complete L=8,10,12 verification without any production-size job.
