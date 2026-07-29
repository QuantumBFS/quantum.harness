# Stage 4 pre-registration

Experiment ID: `stage4-dense-20260729-v1`

This note freezes the hypotheses, falsifiers, statistical policy, and early
stops before inspecting any Stage 4 samples. Stage 3 point estimates are used
only to choose the approved candidate families and compute cost bounds. No
Stage 4 threshold, seed, or cell may be changed in response to whether a result
looks positive.

## Candidate A: half-filled enhancement band

The frozen grid is
`g_B/g_A = 0.25, 0.5, 1`,
`t/g_A = 0.25, 0.5, 1`,
`mu/g_A = 0`,
`m = 4, 6, 8`, and `beta g_A = 4, 8`.

Hypothesis: the Stage 3 size/temperature enhancement contains a staggered
bond/channel collective mode, rather than only the extensive normalization of
an equal-time quadratic observable. A genuine ordered or near-critical signal
must be reproduced across independent replicas and accompanied by consistent
susceptibility, Binder, and correlation-length-proxy behavior.

Falsifiers:

- the long-chain `m=8 - m=4` and `beta=8 - beta=4` enhancements fall below
  two combined standard errors and five percent once replica errors are used;
- susceptibility and `xi/m` remain flat or decrease with size;
- Binder behavior is incompatible with the proposed collective mode;
- a nominal enhancement is carried by one replica or by ESS below the frozen
  audit threshold.

## Candidate B: paired competing-channel region

The frozen grid is
`g_B/g_A = 0.75, 1, 1.25`,
`t/g_A = 0.5, 1`,
`mu/g_A = -1.5, +1.5`,
`m = 4, 6, 8`, and `beta g_A = 8`.

Hypothesis: the Stage 3 channel reordering near equal couplings may reflect a
mixed or competing noncommuting order. The alternative explanations are an
ordinary crossover, short-chain autocorrelation, and a particle-hole-symmetric
response obscured by unequal noise.

The `+mu` and `-mu` cells in each matched pair receive the larger of their two
pilot-derived budgets. No particle-hole asymmetry claim is allowed unless both
members pass identical statistical, determinant, and stability audits.

Falsifiers:

- paired long chains agree within uncertainty and neither side develops
  size-enhanced susceptibility or `xi/m`;
- apparent channel balance changes are not replicated or disappear at
  `m=8`;
- only one member of a pair passes the numerical audit;
- Binder/structure diagnostics show only a smooth finite-size crossover.

## Frozen sampling and audit policy

- Two pilot replicas per cell: 160 warmup sweeps and 320 measurement sweeps,
  measuring every two sweeps.
- Four new production replicas per released cell.
- The production budget uses the worst integrated autocorrelation time among
  combined order, both channel orders, both HS response estimators, and the
  staggered structure factor.
- Target ESS is at least 40 per production replica. Production uses at least
  240 warmup and 640 measurement sweeps, and at most 1600 warmup and 3200
  measurement sweeps.
- Required cost above either cap is an autocorrelation early stop, not evidence
  against the phase.
- Acceptance must lie in `[0.05, 0.995]`; direct determinant sign must remain
  positive; structured/direct log-weight error must not exceed `1e-6`; density
  must remain within `1e-7` of its physical interval.
- WSL uses at most 14 processes, the CPU machine at most 62. OMP, OpenBLAS,
  MKL, and NumExpr are each forced to one thread.

## Interpretation gates

Stage 4 `SURVIVE` requires an audit-passing, replica-reproducible positive
size/temperature trend plus support from at least one independent collective
diagnostic (susceptibility, Binder, or `xi/m`). `EXTEND` is reserved for a
positive but statistically unresolved trend. An adequately sampled flat or
decreasing trend is `STOP`.

No thermodynamic phase or PRL-level claim is permitted at Stage 4. A candidate
must first pass an `m=10` sentinel and then a four-size Stage 5 analysis with
temperature, Trotter, replica, and independent-method controls. First-order,
continuous-critical, multicritical, mixed-order, and ordinary-crossover
explanations remain explicitly open until those tests.
