---
title: "Challenge 148: Stage 4 Report - Corrected Historical-Window Reproduction"
date: 2026-07-29
tags:
  - quantum-harness
  - challenge-148
  - stage-report
  - sse
  - quantum-monte-carlo
  - triangular-lattice
  - honeycomb-lattice
status: gate-pending
stage: 4
related:
  - Harnessing Quantum 2026/Challenge 148 - TFIM Critical-Field Ratio.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 0 Preregistration.md
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 1.md
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 2.md
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 3.md
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 4.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 3 Report.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 5 Report.md
---

# Challenge 148: Stage 4 Report

## 1. Stage status

| Item | Status |
|---|---|
| Audit recovery and corrected validation layer | Complete |
| Numeric fit windows and $L_{\min}$ matrix | Frozen in Protocol Revision 2 |
| Resumable per-cell pipeline and immutable manifests | Complete |
| Fresh square calibration | Complete; published anchor inside the 95% fit interval |
| Fresh triangular historical-window scan through $L=20$ | Complete |
| Fresh honeycomb historical-window scan through $L=20$ | Complete |
| Revision 3/4 sampling diagnostics | Pass at every analyzed point |
| Published triangular and honeycomb anchors | Inside the respective 95% pilot intervals |
| Comparable-to-2002 precision | **Not reached** |
| Doubled-$c_\tau$ systematic gate | **Unresolved; continued in Stage 5** |
| **Overall stage** | **Gate-pending** |

Stage 4 now has valid corrected data, replacing the previous report state in
which production had not started. The historical-window central estimates are
kept separate and the triangular-to-honeycomb ratio remains sealed.

## 2. Work completed before this update

Stages 1-3 built the lattice layer, finite-temperature ED oracle, and
graph-agnostic SSE cluster update. The consolidated audit then repaired:

1. the Lanczos Ritz-vector and physical-residual contract;
2. checked Hilbert-space dimensions and malformed-lattice handling;
3. honeycomb embedding consolidation and shortest reciprocal momenta;
4. cross-field seed reuse and nondeterministic threaded output;
5. bin-only uncertainty estimates that ignored chain structure and
   autocorrelation;
6. the exact imaginary-time moment estimator for
   $Q_L=\langle\bar m^2\rangle^2/\langle\bar m^4\rangle$.

Historical Stage 3/4 pilot errors remain invalid. This report uses only the
fresh cell-based runs listed below.

## 3. Stage objective and frozen setup

The target Hamiltonian is unchanged:

$$
H=-\sum_{\langle ij\rangle}\sigma_i^z\sigma_j^z
  -h\sum_i\sigma_i^x,
$$

with Pauli-matrix normalization, periodic boundaries, and no longitudinal
field. The production aspect ratio is

$$
\beta h=L
$$

for $c_\tau=1$. The primary estimator is the full-imaginary-time Binder ratio
$Q_L$; the mandatory secondary estimator is equal-time $\xi_L/L$ averaged
over all symmetry-related shortest torus momenta.

The Stage 4 objective was to reproduce the published square, triangular, and
honeycomb critical regions with the corrected code and sampling contract
before attempting larger systems.

## 4. Fresh run records

Every point used four independent chains: two hot and two cold starts. Each
chain used 5,000 thermalization sweeps followed by 200 bins of 25 sweeps.

| Run ID | Sizes | Field grid | Cells | Merged raw SHA-256 |
|---|---|---|---:|---|
| `c148-square-calibration-v1` | 4, 6, ..., 20 | 3.00 to 3.10 by 0.01 | 396/396 | `a92efe8cedcb7b7a277f9f3a682b59c3c66e3a8e33d72469328e78fada61ed16` |
| `c148-triangular-stage4-v1` | 6, 8, ..., 20 | 4.70 to 4.84 by 0.01 | 480/480 | `9e57cee182932be909c505e105a68c28a05c8684de15a0d4dd39ff99571bb3df` |
| `c148-honeycomb-stage4-v1` | 10, 12, ..., 20 | 2.08 to 2.18 by 0.01 | 264/264 | `3163c8a0645ad6e7a6096fb6cda7395606fc55541a5df90551b03ac2e18cb41c` |

The square run was generated at source commit
`1a2fb572231ae571824cbb66fb1e7909e537431b`; both target-lattice runs were
generated from clean source commit
`44979df43692f62634f4b26815de878ba4f3d09f`. Their collection manifests
contain no missing or invalid cells.

## 5. Scientific results

### 5.1 Square calibration

The registered joint fit used 200 chain-plus-circular-block bootstrap
replicates. Both $Q_L$ and $\xi_L/L$ fits completed with zero failed
replicates. The published square critical field lies inside the
$\xi_L/L$ 95% interval; the bootstrap standard error is $1.51\times10^{-3}$.
This validates location and normalization at pilot resolution, not published
precision.

### 5.2 Triangular historical window

Both dimensionless-observable fits completed with zero failed bootstrap
replicates. The published triangular anchor lies inside both 95% intervals.
The smaller of the two bootstrap standard errors is $2.99\times10^{-3}$,
which is about two orders of magnitude above the registered
$1.8\times10^{-5}$ target.

### 5.3 Honeycomb historical window

Both fits again completed with zero failed bootstrap replicates, and the
published honeycomb anchor lies inside both 95% intervals. The smaller
bootstrap standard error is $2.37\times10^{-3}$, far above the registered
$8\times10^{-6}$ target.

The three fit-table hashes are:

| Run | Diagnostic fit SHA-256 |
|---|---|
| Square | `39c34f4f3f272a927cd9510edf3897efb9df3d95f49976994feb42fe1819a757` |
| Triangular | `d3e34fe7d2cf3d33db0a93238864eb197e0b4430edac6b571258514dfe487e9b` |
| Honeycomb | `96f85d06867c6e107d976d90c7001da5d6194b5de90c94cd6f9809b3123ddda7` |

No ratio was evaluated from these pilot fits.

## 6. Sampling and reproducibility evidence

Protocol Revisions 3 and 4 were applied to the five stored raw observables.

| Run | Analyzed points | Sampling-gate failures | Largest prefix-refit shift |
|---|---:|---:|---:|
| Square | 99 | 0 | 0.204 combined standard errors |
| Triangular | 120 | 0 | 0.573 combined standard errors |
| Honeycomb | 66 | 0 | 0.236 combined standard errors |

Every point had at least the required number of autocorrelation blocks. The
hot/cold, stationarity, base-versus-doubled-block, error-ratio, single-chain
spread, and 10%/20% discarded-prefix gates all passed.

The production implementation provides:

- one atomic output and manifest per
  `(lattice,L,h,initial_state,replica)` cell;
- source commit, dirty state, binary hash, compiler, geometry, seed, host,
  wall time, completion state, and raw hash in each manifest;
- deterministic collection that rejects missing, failed, mismatched, or
  hash-invalid cells.

## 7. Artifacts and validation

The implementation and protocol copy are in
`tracks/qmc/solutions/LlmNewtonGaussTuring/`. Generated data are ignored under
the training worktree's `results/` directory and are identified above by run
ID and SHA-256.

The continuation implementation at commit
`e2b8323d79deb41b3916c1d8ef2a018e3e5f65f8` passes:

| Validation | Result |
|---|---|
| Default Release build | Pass |
| Default CTest | 9/9 pass; 230.20 s |
| Python analysis tests | Pass |
| `git diff --check` | Pass |

The Stage 4 conclusions depend on the corrected fresh runs, not on the older
monolithic pilots under `tracks/qmc/results/stage4/`.

## 8. Deviations and unresolved risks

1. The historical fields are reproduced only at pilot precision, not at the
   precision reported in 2002 or required by the challenge verdict.
2. $c_\tau=1$ versus $c_\tau=2$ is not resolved to the allocated absolute
   finite-temperature budget.
3. The measured errors imply a very large statistics increase; Stage 5's
   optimistic cost model makes a local precision campaign infeasible.
4. No accepted larger-size production sequence exists.
5. ParaToric normalization is qualified only on finite-volume energy
   components; no independent thermodynamic-limit result exists.
6. The final critical-field estimates, error envelopes, and sealed verdict
   remain unauthorized.

## 9. Stage-gate decision

| Gate | Status |
|---|---|
| Corrected cell-based historical-window data | Pass |
| Complete manifests and raw hashes | Pass |
| Sampling diagnostics at all analyzed points | Pass |
| Statistical consistency with published anchors | Pass at pilot resolution |
| Comparable historical precision | **Fail: under-resolved** |
| Finite-temperature budget | **Pending** |
| Independent thermodynamic-limit route | **Pending** |
| Sealed ratio verdict | **Not authorized** |

**The Stage 4 gate remains open.** The corrected solver reproduces the three
critical regions without a detected sampling failure, but the historical-
precision requirement is not met.

## 10. Next-stage plan

1. Complete the doubled-$c_\tau$ comparison under Protocol Revision 5.
2. Use measured cell timings and fit errors to quantify the cost of larger
   sizes and target statistical precision.
3. Do not launch a production scan until a feasible compute allocation and
   error model are documented.
4. Qualify the independent ParaToric normalization before any independent
   thermodynamic-limit scan.
5. Keep both target-lattice fits separate and the ratio sealed.

## 11. Agent Review and Suggestions

### 11.1 Requested review focus

- Audit the Stage 5 cost model's ideal-scaling assumptions before allocating
  remote compute.
- Check whether the fit robustness matrix needs additional predeclared larger
  $L_{\min}$ values once larger sizes exist.
- Review ParaToric's first nondegenerate honeycomb-target size and finite-size
  observable mapping before the independent scan.

### 11.2 Suggestions log

| Reviewer | Date | Finding | Disposition | Status |
|---|---|---|---|---|
| Consolidated audit | 2026-07-28 | Historical seed reuse and bin-only bootstrap invalidated prior Stage 4 statistics | Require fresh cell runs | Resolved |
| Continuation audit | 2026-07-29 | Fit windows and $L_{\min}$ values were omitted from the preregistration | Freeze pre-verdict values in Revision 2 | Resolved |
| Continuation audit | 2026-07-29 | The old 3.5 per-comparison sampling threshold was not family-wise calibrated | Freeze block and 5.0 maximum-$z$ rule in Revision 3 | Resolved |
| Continuation audit | 2026-07-29 | Reblocking, chain spread, and prefix checks were incomplete | Freeze and implement Revision 4 diagnostics | Resolved |
| Continuation audit | 2026-07-29 | Pilot precision is insufficient for the Stage 4 precision gate | Carry feasibility and $c_\tau$ work into Stage 5 | Open |

### 11.3 Protocol-change rule

The Hamiltonian, primary estimator, fit family, uncertainty rules, blinding
rule, and verdict gate remain frozen. Any change to them requires a new
append-only protocol revision.
