# YueYuan Attempt 004 Report

## Summary

Attempt 004 implements the challenge #113 pipeline: optimize a pulse on a
differentiable quantum-gate model, extract a local Hessian subspace, and use that
subspace for noisy query-only closed-loop calibration.

The main positive result is that the Hessian subspace reduces black-box device
queries on the one-qubit target and improves or matches success on aligned
two-qubit cases. The main failure result is that medium and large model-device
mismatch can remove the advantage, especially for the two-qubit `CZ` target.

## Model

The simulator uses phase-insensitive gate fidelity,
`F = |Tr(U_target^dagger U)|^2 / d^2`, with piecewise-constant controls and JAX
automatic differentiation through the time-ordered propagator.

- `one_qubit_x`: `d=2`, target `X`, 8 segments, 2 controls, 16 pulse parameters.
- `two_qubit_cz`: `d=4`, target `CZ`, 8 segments, 6 local controls, 48 pulse
  parameters, and a `ZZ` entangling drift.

The two-qubit model keeps the requested 32-64 parameter scale while adding local
phase controls so `CZ` is reachable inside the fixed unit-time toy simulator.

## Methods

Each work item starts from the same model-optimized pulse, computes a dense
Hessian at that model optimum, and then evaluates:

- model-only transfer to the true device;
- full-space Nelder-Mead over all pulse parameters;
- random-subspace Nelder-Mead at the benchmark rank;
- Hessian-subspace Nelder-Mead over a sweep of `k`.

All closed-loop optimizers use the same query budget, target infidelity
`1e-3`, shots per query, seed set, clipping bounds, and noisy scalar device
interface. Exact true fidelity is used only by the audit layer for scoring and
stopping-accounting diagnostics; the optimizer receives only finite-shot scalar
infidelity estimates.

## Full Sweep

The full CPU sweep ran as 144 independent Slurm array tasks with 4 CPU cores per
task and 10 concurrent tasks. It produced:

- 1,656 run records;
- 5,121 open-loop history rows;
- 144 Hessian spectra;
- 207 aggregate method/system/gap/shot/k groups;
- CSV summary tables for group statistics, headline comparisons, and failure
  modes, plus a recovery study comparing benchmark `k` against the best widened
  Hessian subspace;
- zero tracebacks in the checked Slurm logs.

Generated artifacts are intentionally ignored by git and are stored locally under
`tracks/qcs/results/YueYuan/attempt-004/full_reachable/`.

Required figures were regenerated under
`tracks/qcs/results/YueYuan/attempt-004/full_reachable/figures/`:

- `model_optimization_history.png`
- `hessian_spectrum.png`
- `queries_to_target_vs_k.png`
- `shots_to_target_vs_k.png`
- `advantage_vs_gap.png`
- `success_rate_vs_shots.png`
- `failure_mode.png`
- `recovery_study.png`

The headline query/shot, success-rate, and failure-mode figures use visible
interquartile or confidence intervals. Machine-readable tables are generated
under `tracks/qcs/results/YueYuan/attempt-004/full_reachable/summary_tables/`:

- `group_summary.csv`
- `headline_comparison.csv`
- `failure_modes.csv`
- `recovery_study.csv`

## Headline Results

Success rates below are reported as binomial normal-approximation 95% intervals
over 8 seeds for each system/gap/shot/k cell.

| System | Gap | Shots | Hessian `k` | Hessian success | Hessian median queries | Full success | Full median queries | Random success | Random median queries |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| one-qubit X | small | 128 | 3 | 1.00 +/- 0.00 | 3.0 | 0.88 +/- 0.23 | 13.0 | 0.50 +/- 0.35 | 1.5 |
| one-qubit X | small | 2048 | 3 | 1.00 +/- 0.00 | 3.0 | 1.00 +/- 0.00 | 15.5 | 0.62 +/- 0.34 | 2.0 |
| one-qubit X | medium | 2048 | 3 | 0.75 +/- 0.30 | 9.5 | 0.25 +/- 0.30 | 19.5 | 0.50 +/- 0.35 | 10.5 |
| one-qubit X | large | 2048 | 3 | 0.88 +/- 0.23 | 14.0 | 0.12 +/- 0.23 | 2.0 | 0.38 +/- 0.34 | 11.0 |
| two-qubit CZ | small | 128 | 15 | 0.62 +/- 0.34 | 3.0 | 0.62 +/- 0.34 | 4.0 | 0.50 +/- 0.35 | 11.5 |
| two-qubit CZ | small | 512 | 15 | 0.88 +/- 0.23 | 8.0 | 0.62 +/- 0.34 | 4.0 | 0.50 +/- 0.35 | 11.5 |
| two-qubit CZ | small | 2048 | 15 | 0.62 +/- 0.34 | 3.0 | 0.62 +/- 0.34 | 4.0 | 0.62 +/- 0.34 | 12.0 |

The clearest query advantage is the one-qubit small-gap regime: Hessian `k=3`
reaches the target in median 3 queries, compared with 13-15.5 full-space queries.
For two-qubit small-gap cases, Hessian `k=15` matches or improves success, but
does not uniformly dominate full-space query count; the result is more modest
and seed-limited.

## Failure Modes

The large model-truth gap introduces rotated and scaled error channels. The
observable symptom is loss of target-reaching success even when the query budget
and shot count are unchanged.

- One-qubit large gap can recover with a wider safety subspace: best Hessian
  `k=8` reaches success 1.00 +/- 0.00 at 2048 shots, with median 21 queries.
- Two-qubit medium and large gaps remain difficult: benchmark `k=15` has zero
  target-reaching success in all medium/large shot settings, and the best
  medium-gap result is only 0.12 +/- 0.23 success at `k=3` with higher shots.
- An earlier weak-entangler two-qubit configuration was a controllability
  failure: all two-qubit methods stagnated near median final infidelity 0.744.
  The current model fixes reachability by adding local phase controls while
  keeping 48 pulse parameters.

These failures support the challenge's intended conclusion: Hessian subspaces
help when the model and device remain sufficiently aligned, but fixed subspaces
can fail under rotated or missing true-device directions.

## Recovery Study

The recovery study compares the benchmark Hessian dimension against the best
widened Hessian dimension already present in the full `k` sweep. At 2048 shots:

| System | Gap | Benchmark `k` success | Best widened `k` | Best success | Delta |
|---|---:|---:|---:|---:|---:|
| one-qubit X | large | 0.875 | 8 | 1.000 | +0.125 |
| one-qubit X | medium | 0.750 | 4 | 1.000 | +0.250 |
| one-qubit X | small | 1.000 | 3 | 1.000 | +0.000 |
| two-qubit CZ | large | 0.000 | 3 | 0.000 | +0.000 |
| two-qubit CZ | medium | 0.000 | 3 | 0.125 | +0.125 |
| two-qubit CZ | small | 0.625 | 32 | 0.750 | +0.125 |

This separates two outcomes: widening the Hessian subspace can recover some
aligned or moderately shifted cases, but it does not solve the hardest
two-qubit large-gap case. That residual failure is the clearest evidence that
some mismatch rotates or adds relevant directions beyond what a fixed model
subspace captures.

## GPU Note

A GPU probe allocated one GPU successfully, but the installed JAX environment was
CPU-only and exposed only `CpuDevice(id=0)`. No GPU acceleration is claimed for
the reported sweep. Given the small matrix dimensions, CPU array parallelism was
the useful resource for this attempt.

## Checklist Status

- Differentiable model, open-loop optimizer, dense Hessian, HVP, and eigenspace:
  implemented.
- Strict query-only finite-shot device with query and shot counters: implemented.
- Model-only, full-space, random-subspace, and Hessian-subspace methods:
  implemented.
- Sweeps over `k`, model-truth gap, shot budget, two system sizes, and 8 seeds:
  completed.
- Query-to-target, shot-to-target, success, final fidelity, and failure status:
  recorded in JSONL.
- Success confidence intervals plus query/shot interquartile ranges: recorded in
  `summary.json` and CSV summary tables.
- Seven required figures plus one recovery-study figure: generated from the full
  sweep with visible uncertainty intervals where applicable.
- Recovery study: documents when widening `k` helps and when it fails.
- Failure case: documented for large mismatch and for the initial weak-entangler
  two-qubit model.
- Reproducibility: Slurm scripts, local smoke runner, full-sweep runner, tests,
  and report are committed; generated data stays under ignored `results/`.

## Verification

Local verification after the two-qubit reachability fix:

- Focused red/green reachability test: passing.
- Attempt-004 tests: passing (`19 passed`).
- Broader YueYuan attempt tests: passing (`33 passed`).
- Validator self-test controls: passing (`"status": "passed"`).
- Fast candidate export: passing (`schema_version=1`, 12 groups).
- Figure/table generation: passing (`1,656` rows, `207` groups, eight PNGs,
  four CSV tables).
- Full CPU sweep: completed with 144/144 tasks and zero tracebacks.

The generated files are intentionally ignored by git.

## Limitations

This is software calibration, not real hardware calibration. The black-box
boundary is enforced by the public query interface and tests, not by cryptographic
isolation. Confidence intervals are wide because each cell uses 8 seeds; more
seeds would be needed for publication-grade statistics.
