# Attempt 02 Projected Random-Feature NQS Plan

**Goal:** Run a strict-LLL, antisymmetric, SO(3)-certified neural candidate through every frozen `N=6` Benchmark v0 gate against the Attempt 01 ED oracle.

**Architecture:** Evaluate one shared `tanh` random-feature trunk on `M=0` occupation bitstrings. Project its feature columns into exact `L=0` and `L=2` subspaces, optimize separate linear heads by Rayleigh-Ritz, generate the `L=2` tower with many-body ladder operators, and estimate energies by independent determinant VMC. Validate exchange antisymmetry in continuous coordinates and SO(3) through a finite random rotation in the direct-sum tower representation.

**Tech stack:** Existing Python 3.13, NumPy, SciPy, pytest; local CPU; no new packages.

## Task 1: Define angular-momentum projectors and neural feature family

- [x] Write failing tests for exact `L=0/L=2` projectors, shared feature shapes, deterministic seed behavior, and variational energies bounded below by ED.
- [x] Verify RED because `projected_nqs.py` does not exist.
- [x] Implement minimal projectors, shared random features, and projected Rayleigh-Ritz heads.
- [x] Verify GREEN.

## Task 2: Generate and certify the complete L=2 tower

- [x] Write failing tests for ladder normalization, all five M sectors, `L^2=6`, energy degeneracy, and generator closure.
- [x] Verify RED for the missing tower behavior.
- [x] Implement the tower and direct-sum angular-momentum generators.
- [x] Verify GREEN.

## Task 3: Add independent VMC and physical symmetry tests

- [x] Write failing tests for independent determinant sampling, standard error/ESS, continuous-coordinate particle-swap sign, and a seeded finite random SO(3) rotation residual.
- [x] Verify RED for the missing estimators and diagnostics.
- [x] Implement minimal VMC, coordinate evaluation, swap residual, and finite-rotation residual.
- [x] Verify GREEN.

## Task 4: Emit the combined Benchmark v0 candidate report

- [x] Write a failing end-to-end test requiring every frozen gate name and `benchmark_v0.pass=true`.
- [x] Verify RED because the candidate report/CLI does not exist.
- [x] Implement `run_nqs_benchmark.py`, the candidate schema, progress output, and JSON writer.
- [x] Run the full scoped suite and the one-command candidate run.

## Task 5: Close and integrate the attempt

- [ ] Record commands, configuration, numerical values, MC errors, residuals, and failure lessons.
- [ ] Run fresh scoped tests, CLI, JSON structural checks, `git diff --check`, and status.
- [ ] Commit implementation separately from the closure journal and integrate only after verification.
