# Challenge 73 Stage 5: Large-ED and iPEPS Readiness

**Author:** LlmNewtonGaussTuring / Xeri Chen

**Date:** 2026-07-29

**Track:** `tracks/peps/solutions/LlmNewtonGaussTuring/`

**Status:** gate-pending

**Code checkpoint:** `ac176dc94a06726655077ab4ed6eebff964b24b5`

## Previous Work

Stages 0-3 established the Berry-curvature conventions, complex Lanczos exact
diagonalization (ED), the SSE response estimator, and small-square FHS versus
spectral-response checks. Stage 4 implemented and tested a pure-NumPy dense-ED
plus snake-MPS FHS engine. That stage passed its own small-system gate but did
not provide a genuine thermodynamic-limit PEPS result.

## Stage Goal

Remove the small dense-ED ceiling, add finite-size analysis, parameterize the
Rydberg laser phase, and establish a genuine PEPSKit iPEPS route suitable for
bond/environment-dimension convergence studies.

## Completed Deliverables

1. `berry.cpp` now has a matrix-free complex-Hermitian Lanczos route for the
   square TFIM and the scan accepts systems through `N=16`.
2. `analyze_berry_scaling.py` provides finite-size scaling analysis for Berry
   scan output.
3. The Berry Hamiltonian supports the Rydberg laser-phase parameterization.
4. `ipeps_convergence.jl` and `ipeps_tfim.jl` provide PEPSKit/TensorKit
   ground-state optimization and `D, chi` convergence scaffolding.
5. The merged checkpoint builds successfully. Four existing Berry CTests pass,
   the Python scaling script compiles, both Julia scripts parse, and PEPSKit and
   TensorKit load from the pinned Julia environment.

## What Is Not Yet Complete

The Stage 5 iPEPS scripts currently optimize a ground state and report energy
and simple magnetizations. They do **not** yet compute normalized overlaps
between independently optimized iPEPS states at the four corners of a
`(theta, Omega)` plaquette, assemble the gauge-invariant FHS Wilson loop, or
emit Berry curvature with overlap, CTMRG, and optimization diagnostics.

Consequently, the genuine iPEPS thermodynamic-limit route requested by
Challenge 73 is not production-ready. The current pure-NumPy FHS path remains
a dense-ED/snake-MPS validation route, while the C++ matrix-free ED path is a
larger finite-size oracle. Neither substitutes for the missing iPEPS overlap
contraction and curvature pipeline.

The new Julia code has only static/API-load validation in this checkpoint. No
completed `D, chi` production grid, optimized-state checkpoint set, iPEPS FHS
curvature table, or thermodynamic extrapolation has been recorded.

## Stage Gate

`gate-pending`. Large finite-size ED and analysis infrastructure are ready to
run, and the iPEPS ground-state skeleton is present, but the core iPEPS Berry
overlap/curvature observable is still a software gap. Challenge 73 is therefore
not at the “only run and analyze” stage.

## Next Stage Plan

1. Implement normalized mixed-iPEPS overlap contraction for neighboring
   `(theta, Omega)` states, with phase/gauge handling and small-system tests.
2. Assemble the four-link FHS plaquette, reject near-zero overlaps, and emit
   curvature plus CTMRG/gradient diagnostics in a resumable data format.
3. Validate the iPEPS observable against the existing ED FHS oracle at a small
   point before production.
4. Run registered `D, chi` convergence and parameter grids only after the
   observable-level tests pass.
5. Analyze finite-size/bond-dimension convergence and compare with the QMC
   benchmark before closing the challenge.

## Agent Review and Suggestions

| Finding or suggestion | Decision | Status |
|---|---|---|
| The iPEPS scripts report energy but no Berry curvature. | Treat them as readiness scaffolding, not a completed primary method. | Open |
| Static parsing does not validate PEPSKit runtime calls through optimization. | Require a bounded smoke run before production. | Open |
