# Stage 4 temporal-block sampler result

Date: 2026-07-29
Source revision: `852a83a1bfb1b20aab4c246bd9e9ac7330e53ae2`

## Pre-registered decision

**STOP.**  The mandatory `m=3` gate failed, so the censored Stage 4
`m=8,beta=8` A/B point was not run.

The run used four paired-seed replicas per sampler, 240 warmup sweeps, 800
measurement sweeps, `measure_every=2`, eight independent WSL processes, and
one BLAS thread.  No seed, scale, budget, or threshold was changed after
observing the result.

## Gate evidence

| Audit | Local control | Temporal block | Frozen gate |
|---|---:|---:|---:|
| Energy | `-5.69029(184)` | `-5.75972(159)` | compare with ED |
| Energy vs ED `|z|` | `0.077` | **`4.285`** | `<=3.0` |
| Combined Q | `1.00022(219)` | `1.00696(227)` | compare with ED |
| Combined Q vs ED `|z|` | `0.636` | `2.356` | `<=3.0` |
| Total acceptance | `0.764-0.769` | `0.773-0.779` | `[0.05,0.995]` |
| Block acceptance | disabled | `0.909-0.918` | `[0.05,0.995]` |
| Minimum direct sign | `+1` | `+1` | positive |
| Maximum log-weight error | `4.47e-11` | `5.04e-11` | `<=1e-6` |
| Median worst tau | `4.812` | `3.799` | descriptive at m=3 |
| CPU seconds / effective sample | `0.0811` | `0.0958` | report separately |

All five sampler-to-sampler observables pass the frozen mutual 3-sigma gate;
the largest is energy at `2.861 sigma`.  Density, all monitored
autocorrelations, sign and determinant-stability checks pass.  Nevertheless,
the temporal-block energy misses the independent ED result
`-5.6917131418` by `4.285 sigma`, which is a mandatory stop.

The block proposal lowers the median worst tau by `21.1%`, below the later
Stage 4 A/B advance threshold of `25%`, while its measured CPU cost per
effective sample is `18.2%` higher.  These efficiency observations do not
override the failed ED gate.

## Interpretation and consequence

The exact pCN detailed-balance argument and software regressions remain valid,
but this fixed-scale implementation did not produce an audit-passing finite
chain result.  A statistical fluctuation or underestimated finite-chain error
cannot be excluded; the pre-registration intentionally prevents resolving that
ambiguity by extending only the unfavorable arm or trying another scale.

Therefore:

- do not use `temporal_block_scale=0.1` for Stage 4 or Stage 5 evidence;
- do not launch the programmatically gated `m=8,beta=8` A/B run;
- do not reinterpret the observed energy displacement as physics;
- retain the control, failed arm, all seeds, and the early-stop reason.

Artifacts are under
`results/stage4_20260729/autocorrelation_mitigation/m3_ed/`.
