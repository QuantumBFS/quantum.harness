# Exponential Decomposition Validation Implementation Plan

**Goal:** Fit the infinite power-law kernel by bounded exponential sums and
validate its analytical periodization against the exact finite-ring coupling.

**Architecture:** `exponential_fit.py` owns the deterministic variable-
projection fit and reconstruction formulas. `validate_exponential_fit.py`
owns the K-series experiment and serialization; it calls the Phase 1 coupling
module only after fitting.

**Tech Stack:** Python 3.11, NumPy, SciPy, pytest.

## Global constraints

- Fit only `r^(-1-sigma)`, never periodic reference data.
- Require `0 < lambda_k < 1`.
- Use deterministic initialization and optimization.
- Validate `K=8,12,16` at `L=64`, `sigma=1.75`, `r_fit=512`.
- Do not import TeNPy or implement MPO/DMRG.

## Task 1: Fitting and reconstruction API

- [ ] Add failing tests for deterministic results, lambda bounds, relative
      error metrics, analytical periodization, and periodic symmetry.
- [ ] Run the focused tests and confirm failure because the module is absent.
- [ ] Implement the bounded variable-projection fitter and reconstruction
      functions.
- [ ] Run the focused and full test suites.

## Task 2: K-series validation command

- [ ] Add a failing CLI test for CSV and JSON artifacts.
- [ ] Run it and confirm failure because the command is absent.
- [ ] Implement the validation command with defaults `64`, `1.75`, `512`, and
      `8,12,16`.
- [ ] Run the CLI test and full suite.

## Task 3: Numerical validation and documentation

- [ ] Run the default K-series and inspect maximum/RMS kernel and periodic
      errors plus distance profiles.
- [ ] Update the README and methodology with the command and fitting contract.
- [ ] Run the full suite, `git diff --check`, and a scope audit.

## Task 4: Periodized residual diagnostics

- [ ] Extend the CLI test to require `global_maximum`, `short_distance`, and
      `central_region` in every per-K and aggregate JSON entry.
- [ ] Confirm the test fails because those fields are absent.
- [ ] Add a residual-summary helper using `r=1,...,10` and the five distances
      centered on `L/2`.
- [ ] Regenerate the default artifacts and report the K=8,12,16 values.
- [ ] Explain nonnegative least squares and coefficient positivity in the
      methodology, then run the full verification suite.

## Task 5: Extended K-convergence study

- [ ] Change the CLI regression test to invoke the default K series and require
      `K=8,12,16,20,24`.
- [ ] Confirm failure because the current default ends at K=16.
- [ ] Extend only the command default, preserving the fitting protocol.
- [ ] Regenerate L=64, sigma=1.75, r_fit=512 summaries and profiles.
- [ ] Compare kernel, periodic, global, short-distance, and central errors;
      classify the K=20 to K=24 trend as continued decrease or a plateau.
- [ ] Update methodology only if that classification changes the existing
      finite-window-tail interpretation; run full verification.

## Task 6: Correlation-length-bound redesign

- [ ] Add failing tests for `min_rate_scale`, the exact
      `min(a_k)*r_fit >= alpha` invariant, deterministic fitting, and invalid
      alpha values.
- [ ] Add failing CLI tests for `--min-rate-scale` and JSON fields `rates`,
      `min_rate_times_r_fit`, and `min_rate_scale`.
- [ ] Implement the constrained lower bound without changing NNLS or the
      infinite-kernel residual objective.
- [ ] Run the focused and full tests.
- [ ] Execute the 18 constrained cells for alpha=0.25,0.5,1.0,
      K=16,24, and r_fit=512,1024,2048.
- [ ] Compare spectra and errors against the six Phase 2.5 baseline cells,
      update methodology with the stability conclusion, and verify scope.
