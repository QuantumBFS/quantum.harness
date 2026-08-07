# Challenge 113 Submission: Hessian-Guided Sim-to-Real Gate Calibration

## Verdict

Hessian-informed closed-loop search reduces finite-shot black-box calibration
cost when the differentiable model and query-only device remain sufficiently
aligned. When mismatch rotates useful directions away from the model Hessian,
counted device-informed residual probes improve robustness on average, but do
not uniformly solve the hardest two-qubit case.

This is a software black-box result. It does not claim a calibration run on
real quantum hardware.

## What Was Tested

The implementation follows the three-stage pipeline in
[challenge #113](https://github.com/QuantumBFS/quantum.harness/issues/113):

1. optimize a pulse on a differentiable one- or two-qubit dynamics model;
2. extract leading model-Hessian directions at the open-loop optimum;
3. refine the pulse with derivative-free optimization against a finite-shot,
   query-only true device.

The software true device hides drift, coupling, unmodeled-control, or internal
pulse-distortion mismatch behind a scalar noisy-query interface. The sealed
runner gives optimizers only `query`, `query_count`, and `shot_count`; exact
fidelity is evaluated afterward by a separate scorer.

## Main Evidence

The completed sealed holdout study contains 48/48 task shards, 240 method
records, 120 aggregate groups, and 24 split/system/variant/shot comparison
cells. It covers one-qubit `X` and two-qubit `CZ` targets, dev and holdout
seeds, 512 and 2048 shots per query, and medium, large, and hidden
pulse-distortion true-device variants.

| Method | Mean target success | Median of cell-median final infidelity |
|---|---:|---:|
| Device-informed adaptive Hessian | 0.562500 | 0.002078 |
| Widen-only adaptive Hessian | 0.520833 | 0.002162 |
| Fixed Hessian subspace | 0.416667 | 0.003515 |
| Full-space Nelder-Mead | 0.187500 | 0.006854 |
| Random subspace | 0.187500 | 0.006864 |

Device-informed probing lowered median final infidelity in:

- 24/24 cells versus full-space search;
- 24/24 cells versus random-subspace search;
- 17/24 cells versus fixed Hessian, with 4 ties;
- 11/24 cells versus widen-only adaptive Hessian, with 4 ties.

The broader eight-seed sweep provides the clearest low-mismatch query result:
for the one-qubit small-gap target, Hessian `k=3` reached `1-F <= 1e-3` in a
median of 3 device queries, versus 13 to 15.5 for full-space search at 128 and
2048 shots per query.

## Why This Is Useful

The model contributes more than a warm-start pulse: it identifies a compact
experiment space in which expensive device queries can be spent. The measured
residual-probe extension also gives a practical response to sim-to-real
failure: use counted device data to add directions when a fixed model subspace
stalls.

The result is therefore a decision rule, not a claim that Hessian reduction
always wins:

- use the compact model subspace while transfer remains aligned;
- widen or probe residual directions when the noisy device response stalls;
- fall back from the reduced-space claim when the measured mismatch remains
  outside the model span.

## Why The Comparison Is Credible

- **Sealed black-box boundary:** optimizer functions cannot inspect or
  differentiate through the true system; they return query transcripts for
  post-run scoring.
- **Counted physical currency:** every black-box call and every measurement
  shot is charged, including residual-direction probes.
- **Fair baselines:** full, random, fixed-Hessian, adaptive-Hessian, and
  device-informed methods share the derivative-free optimizer family, target,
  bounds, query budget, shot budget, and seed protocol.
- **Held-out mismatch:** dev and holdout seeds are reported separately, and a
  hidden pulse-distortion transform is evaluated in addition to Hamiltonian
  perturbations.
- **Complete aggregation:** the moderate combiner rejects missing or extra
  shards; the full and adaptive-focus combiner also enforces the expected
  aggregate method-profile count before writing results.
- **Uncertainty and negative evidence:** the full sweep reports seed intervals,
  while failed target-reaching cells remain visible rather than being removed.
- **Executable checks:** tests cover dynamics, Hessians, query isolation,
  counters, hardware-style count ingestion, invariant probes, shard
  completeness, and the one-command submission path.

## Failure And Claim Boundary

The strongest remaining failure is the pulse-distorted two-qubit holdout at
2048 shots per query. Device-informed probing improved its median final
infidelity to `0.002565`, but it did not reach the `1e-3` target. This is useful
negative evidence: device-informed directions help on average, yet a larger
model-device rotation or a richer physical model is still needed for that
regime.

The current evidence is limited by two seeds per moderate split cell, four
across dev and holdout for each system/variant/shot setting, and by the lack of
a real-hardware run. It supports a reproducible software sim-to-real result, not
a hardware or publication-grade statistical claim.

## Review And Reproduce

- [Exact reproduction guide](research/attempts/attempt-004/REPRODUCE.md)
- [Detailed scientific report](research/attempts/attempt-004/REPORT.md)
- [Implementation map](research/attempts/attempt-004/README.md)
- [Challenge #113](https://github.com/QuantumBFS/quantum.harness/issues/113)

After installing the pinned environment, the fast end-to-end check is:

```bash
python tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/verify_submission.py
```

It runs the black-box boundary tests, validator controls, a sealed dev/holdout
experiment, and exact output-structure checks.
