---
title: "Challenge 148: Protocol Revision 9 - Honeycomb Fine-Grid Statistics"
date: 2026-07-29
tags:
  - quantum-harness
  - challenge-148
  - protocol-revision
  - direct-sse
  - finite-size-scaling
status: frozen
related:
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 7.md
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 8.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 7 Report.md
---

# Challenge 148: Protocol Revision 9

Protocol identifier:
`c148-prereg-v1+rev1+rev2+rev3+rev4+rev5+rev6+rev7+rev9`.

Revision 8 remains a proposed, unratified repair for the independent ParaToric
$L=4$ normalization comparison and is not incorporated here. This append-only
revision freezes a direct-SSE statistical refinement before the new data are
generated. It does not alter the Hamiltonian, lattice convention, aspect
ratio, estimators, field window, fit family, correction exponents, blinding
rule, or verdict gate.

## 1. Triggering evidence

The independent honeycomb fine-grid runs at $L=32$ and $L=40$ pass all current
sampling gates, but their central $Q$ and $\xi/L$ curve differences change sign
multiple times on $h=2.130,\ldots,2.140$. Only 549 of 5,000 $Q$ bootstrap
resamples and 1,480 of 5,000 $\xi/L$ resamples contain exactly one root. Point
uncertainties of approximately 0.008--0.014 are comparable to the adjacent-size
curve differences. The crossing is therefore statistically unresolved, and an
$L=64$ fine scan is deferred.

## 2. Frozen physical setup

The target remains the periodic honeycomb transverse-field Ising model

$$
H=-\sum_{\langle ij\rangle}\sigma_i^z\sigma_j^z
  -h\sum_i\sigma_i^x,
$$

with $J=1$ and Pauli-matrix normalization. The inverse temperature obeys
$\beta h=L$ (`c_tau=1`). The primary estimator is
$Q=\langle\bar m^2\rangle^2/\langle\bar m^4\rangle$; the secondary estimator is
the equal-time $\xi/L$ obtained from $S(0)/S(q_{\min})$.

The run ID is `c148-honeycomb-l3240-fine-hp-v2`. Its complete axes are:

- sizes $L=32,40$;
- fields $h=2.130,2.131,2.132,2.133,2.134,2.135,2.136,2.137,2.138,2.139,2.140$;
- two hot and two cold independently seeded chains per $(L,h)$.

This gives 88 planned cells. Every chain uses 10,000 discarded thermalization
sweeps followed by 800 stored bins of 25 sweeps each. Seeds are deterministic,
nonzero hashes of the run ID and complete cell parameters and must be unique.
The new high-statistics run is analyzed on its own; the earlier short-chain
runs remain diagnostics and are not pooled into the new errors.

## 3. Sampling and crossing gates

Raw bins and manifests must satisfy the existing direct-SSE finite-value,
sign, geometry, aspect-ratio, hot/cold, stationarity, autocorrelation,
independent-block, chain-spread, and bin-growth gates. No failed or missing cell
may be silently omitted.

For each of $Q$ and $\xi/L$, recompute nonlinear estimates within 5,000
chain-plus-block bootstrap resamples. The $L=32/40$ crossing is statistically
resolved only if the central piecewise-linear curve difference has exactly one
root in the frozen interval and at least 99% of bootstrap resamples also have
exactly one root. A conditional spread from a lower-success bootstrap remains a
diagnostic and cannot enter the critical-field precision budget.

Failure of this gate leaves the fine crossing unresolved. It does not authorize
a field-window or fit-family change. An $L=64$ fine scan may be considered only
after this gate passes and the crossing sequence still requires a larger size.

## 4. Execution and ratification

Use the Release `sample_stage4_cell` executable from the
`c148-continuation` worktree. Execute locally with six independent workers and
collect through the provenance-aware Stage 4 runner. The production directory
is
`data/processed/challenge148/runs/c148-honeycomb-l3240-fine-hp-v2/`.

**Frozen before compute.** The user explicitly selected the existing C++
direct-SSE implementation and instructed the continuation to proceed with the
already agreed physical setup.
