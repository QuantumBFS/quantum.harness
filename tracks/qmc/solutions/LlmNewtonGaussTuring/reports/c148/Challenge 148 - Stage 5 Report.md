---
title: "Challenge 148: Stage 5 Report - Pilot Scaling and Feasibility"
date: 2026-07-29
tags:
  - quantum-harness
  - challenge-148
  - stage-report
  - sse
  - finite-size-scaling
  - cost-model
status: gate-pending
stage: 5
related:
  - Harnessing Quantum 2026/Challenge 148 - TFIM Critical-Field Ratio.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 4 Report.md
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 4.md
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 5.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 7 Report.md
---

# Challenge 148: Stage 5 Report

## 1. Stage status

| Item | Status |
|---|---|
| Doubled-$c_\tau$ target-lattice grids | Complete through $L=20$ |
| Sampling diagnostics on doubled grids | Pass at every point |
| Pointwise aspect-ratio rule | Corrected by Protocol Revision 5 |
| Fitted finite-temperature shift budget | **Failed by under-resolution** |
| Timing and statistical-error cost model | Complete |
| Larger-size pilot sequence | **Not run** |
| Feasible route to registered precision on current local resources | **Not demonstrated** |
| **Overall stage** | **Gate-pending** |

The completed pilot establishes that the current data volume cannot resolve
the finite-temperature or final statistical budgets. It does not authorize a
production scan or the sealed ratio calculation.

## 2. Work completed before Stage 5

Stage 4 delivered complete resumable square, triangular, and honeycomb grids
at $c_\tau=1$, with no missing cells and no Revision 3/4 sampling-gate
failures. The published critical-field anchors lie within the pilot 95%
intervals, but the fit errors remain orders of magnitude above the registered
targets.

Protocol Revision 4 froze the doubled-$c_\tau$ and remaining sampling checks
before Stage 5 data generation. Protocol Revision 5 later corrected only the
false requirement that dimensionless observables remain pointwise invariant
when the space-time aspect ratio changes.

## 3. Stage objective

Stage 5 was intended to:

1. test $c_\tau=1$ against $c_\tau=2$ at common sizes and fields;
2. estimate the finite-temperature bound on each fitted critical field;
3. model cell wall time and the statistics required at larger sizes;
4. decide whether the registered precision is feasible before committing to
   Stage 6 production.

The provisional larger-size sequence is $L=24,32,40,48,56,64$. No cells on
that sequence have been generated.

## 4. Doubled-$c_\tau$ runs

Both runs used clean source commit
`7b7890073383868628a70189549125abb2f6d645`, four independent chains per point,
5,000 thermalization sweeps, and 200 bins of 25 sweeps.

| Run ID | Sizes | Fields | Cells | Merged raw SHA-256 |
|---|---|---|---:|---|
| `c148-triangular-ctau2-stage5-v1` | 10, 12, ..., 20 | 4.74 to 4.80 by 0.01 | 168/168 | `7a06765214d3d55a26703bd711ce937665158edee0456c9fdf836aa22669db98` |
| `c148-honeycomb-ctau2-stage5-v1` | 10, 12, ..., 20 | 2.11 to 2.15 by 0.01 | 120/120 | `d325ca9aab98426d99787d952dba1c601ebdbd52bae86e152f5f46ca31873dbe` |

All 42 triangular and 30 honeycomb common points pass the hot/cold,
stationarity, reblocking, error-ratio, chain-spread, and additional-prefix
sampling gates. The doubled-run fits each completed 200 bootstrap replicates
with zero failures.

## 5. Finite-temperature gate

Changing $c_\tau$ changes the finite-size scaling functions, so pointwise
shifts in $Q_L$ and $\xi_L/L$ are retained as diagnostics only. The hard gate
is the two-sided 95% upper bound on the fitted critical-field shift.

| Lattice | Observable | Fitted shift significance | 95% upper bound | Budget | Result |
|---|---|---:|---:|---:|---|
| Triangular | $Q_L$ | 0.607 standard errors | $2.77645\times10^{-2}$ | $4.5\times10^{-6}$ | Unresolved |
| Triangular | $\xi_L/L$ | 0.654 standard errors | $2.33524\times10^{-2}$ | $4.5\times10^{-6}$ | Unresolved |
| Honeycomb | $Q_L$ | 0.683 standard errors | $1.35928\times10^{-2}$ | $2.0\times10^{-6}$ | Unresolved |
| Honeycomb | $\xi_L/L$ | 0.272 standard errors | $6.49057\times10^{-3}$ | $2.0\times10^{-6}$ | Unresolved |

The shifts are statistically consistent with zero at this resolution, but
their upper bounds exceed the allocated budgets by several orders of
magnitude. Under Protocol Revision 5, both finite-temperature gates therefore
fail by insufficient resolution.

Gate-file hashes:

- triangular: `af9d93b89e167589c794ce1ff6db509cf113236e312ed5d868cd25f33afea54a`;
- honeycomb: `85808756c76218a051a9672067bd43b2955ffa1633476fb85567802a8ee14b16`.

No target-lattice ratio was evaluated.

## 6. Cost and error model

`tools/estimate_stage5.py` fits median cell wall time to

$$
t_{\rm cell}(L)=aL^p
$$

and combines this with the optimistic critical-slope gain
$dO/dh\propto L^{1/\nu}$. The future grid assumes four chains per point,
16 ideal workers, six sizes through $L=64$, and no queueing or I/O overhead.

| Quantity | Triangular | Honeycomb |
|---|---:|---:|
| Measured cells | 480 | 264 |
| Measured aggregate wall time | 2,593 s | 3,849 s |
| Measured $\xi_L/L$ fit error | $2.99\times10^{-3}$ | $2.37\times10^{-3}$ |
| Registered target error | $1.8\times10^{-5}$ | $8.0\times10^{-6}$ |
| Fitted wall exponent $p$ | 3.096 | 2.954 |
| Future-to-current slope gain | 6.337 | 6.337 |
| Optimistic statistics multiplier at $L=64$ | 687 | 2,185 |
| Optimistic aggregate time | $2.57\times10^7$ s | $1.02\times10^8$ s |
| Optimistic ideal wall time on 16 workers | $1.61\times10^6$ s | $6.37\times10^6$ s |

The ideal wall estimates are approximately 18.6 days for triangular and 73.8
days for honeycomb. These are lower bounds: the model assumes independent
samples and perfect worker scaling, and excludes worsening autocorrelation,
finite-size bias, failed robustness gates, the unresolved $c_\tau$ budget,
queueing, and I/O.

The current direct-SSE plan is therefore infeasible as a local precision run.
A remote allocation and a stronger variance/cost strategy would be required,
and neither has yet been demonstrated to meet the full error budget.

## 7. Artifacts and provenance

Generated artifacts are ignored under `results/`:

| Artifact | SHA-256 |
|---|---|
| `triangular_cost_model.json` | `e0b34e801eda0cfde72efcc28a83327b425930b6826e18868002dcbc09c336d4` |
| `triangular_wall_by_size.csv` | `a8f1c5a61a8be02e35ce4ed879c60045d8167d8fd87a93bb5cb5f600db87cff1` |
| `honeycomb_cost_model.json` | `5ad6a2788e95a3fbf5c88df7b4a7a4ae8ca68ed387a0762324df72b9d4b576ce` |
| `honeycomb_wall_by_size.csv` | `ce7c22b6c5d2793fcfccce08e8deea4e6223964406eff94425741b9ade4d6f12` |

The cost-model implementation and corrected $c_\tau$ gate are committed at
`e2b8323d79deb41b3916c1d8ef2a018e3e5f65f8`.

## 8. Validation evidence

| Validation | Result |
|---|---|
| Default Release build | Pass |
| Default CTest | 9/9 pass; 230.20 s |
| Python analysis and cost-model tests | Pass |
| Doubled-run collection completeness | 288/288 cells valid |
| Doubled-run sampling gates | 72/72 points pass |
| `git diff --check` | Pass |

## 9. Deviations and unresolved risks

1. No $L>20$ pilot was run, so the measured wall exponents are extrapolated
   beyond the observed size range.
2. The cost model uses ideal scaling and does not establish actual effective
   sample size at $L=64$.
3. The fitted finite-temperature upper bounds are thousands of times larger
   than their budgets.
4. The Stage 4 statistical errors remain far above the final precision
   targets.
5. No accepted cluster profile or remote allocation is recorded for this
   campaign.
6. The independent route is qualified only for normalization, not for a
   thermodynamic-limit critical field.

## 10. Stage-gate decision

| Gate | Status |
|---|---|
| Doubled-$c_\tau$ grids complete | Pass |
| Sampling quality of doubled grids | Pass |
| Correct physical $c_\tau$ invariant | Pass after Revision 5 |
| Finite-temperature absolute budget | **Fail: under-resolved** |
| Documented timing/error model | Pass |
| Precision feasible with available local resources | **No** |
| Larger-size drift and autocorrelation evidence | **Pending** |
| Stage 6 production authorization | **Blocked by open gates** |

**Stage 5 remains gate-pending.** The pilot produced a negative feasibility
result for the current local plan. It does not justify spending the projected
production budget without a revised, predeclared compute strategy.

## 11. Next-stage plan

1. Benchmark a small number of $L=24$ and $L=32$ cells only after selecting a
   suitable remote resource; use them to test the extrapolated wall and
   autocorrelation models.
2. Investigate variance reduction or validated reweighting without changing
   the frozen estimator or fit family.
3. Re-estimate the complete finite-temperature and finite-size error budget
   before proposing Stage 6.
4. Complete the ParaToric thermodynamic-limit route independently rather than
   using ED qualification as a substitute.
5. Keep the triangular and honeycomb acceptances separate and the verdict
   sealed.

## 12. Agent Review and Suggestions

### 12.1 Requested review focus

- Challenge the assumption that the $L^{1/\nu}$ slope gain transfers directly
  to the realized fit uncertainty.
- Estimate remote memory, core, and wall requirements from measured per-cell
  manifests before choosing a partition.
- Review whether a predeclared reweighting window can reduce field-count cost
  without introducing overlap bias.

### 12.2 Suggestions log

| Reviewer | Date | Finding | Disposition | Status |
|---|---|---|---|---|
| Continuation audit | 2026-07-29 | Revision 4 incorrectly treated finite-$L$ point values as aspect-ratio invariants | Replace pointwise gate with extrapolated-location gate in Revision 5 | Resolved |
| Continuation audit | 2026-07-29 | Current statistics cannot resolve the absolute $c_\tau$ budgets | Record hard gate failure; do not infer zero shift | Open |
| Continuation audit | 2026-07-29 | Optimistic direct-SSE production requires multi-week ideal wall time | Do not authorize local Stage 6 production | Open |
