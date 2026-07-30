# Precision recovery plan

Date: 2026-07-29

## Current evidence

The completed data set contains 177 integrity-valid cells. Exact
diagonalization checks on small triangular and honeycomb systems support the
implementation and observable definitions. The challenge analysis gives

- triangular: `h_c(Δτ→0) = 4.768728679 ± 0.001167797`;
- honeycomb: `h_c(Δτ→0) = 2.132617106 ± 0.000794629`;
- ratio: `R = 2.236062909 ± 0.001006930`;
- `R - √5 = -5.07e-6`, or `-0.005` estimated standard errors.

The result is therefore statistically compatible with `√5`, but it does not
resolve equality at the declared fifth-decimal precision.

The primary finite-size estimates at requested `Δτ=0.013` have bootstrap
standard errors of about `6.71e-5` for each lattice. Propagating only those two
errors gives a ratio-error floor of about `7.71e-5`, which is `6.48` times the
challenge target `1.19e-5`. Reducing this floor by sampling alone would require
about `42` times as many independent measurements, before accounting for
finite-size and time-step systematics.

## Dominant limitation

The triangular step-specific critical fields for requested
`Δτ=0.013, 0.016, 0.020` lie outside their measured field windows. More sweeps
in those same windows would reduce Monte Carlo noise without correcting the
field extrapolation. The first priority is therefore to bracket the
finite-step critical points.

Increasing the maximum size is also lower priority under the deadline:
the cost grows approximately as `L^3`, while it does not repair the time-step
field coverage. Increasing `NSwep` has the usual inverse-square-root return;
doubling wall time reduces statistical errors by only `√2`.

## Report presentation

The report places a finite-size data-collapse figure before the
`Δτ²→0` extrapolation. For the declared primary family
(`Lmin=16`, terms `a2`, `y_t=1.587`, `y_i=-0.815`), it plots

```text
x = (h - h_c)L^y_t
Q_corrected = Q - b1 L^y_i
```

with the fitted scaling function and standardized residuals. This figure
shows the finite-size-scaling evidence directly while retaining the fit-family
stability plot as a systematic diagnostic.

## Approved 66-cell scan

All new cells retain the verified production settings:

```text
J1=-1, J2=0, periodic boundaries
BetaT=L/h
32 independent MPI chains
nWarm=10000, NmBin=32, NSwep=2000
nLocal=1, nWolff=5
```

Triangular sizes are `L=32,40,48`:

| Requested Δτ | Fields |
|---|---|
| 0.010 | 4.7705, 4.7710, 4.7715, 4.7720, 4.7725 |
| 0.013 | 4.7728, 4.7733, 4.7738, 4.7743, 4.7748 |
| 0.016 | 4.7743, 4.7748, 4.7753, 4.7758, 4.7763 |

This contributes `3 × 3 × 5 = 45` cells.

Honeycomb sizes are `L=24,28,32`:

| Requested Δτ | Fields |
|---|---|
| 0.010 | 2.1318, 2.1323, 2.1328, 2.1333, 2.1338 |
| 0.016 | 2.1340, 2.1345 |

The existing `Δτ=0.013` scan already brackets the honeycomb crossing. The new
honeycomb work contributes `3 × (5+2) = 21` cells.

Total: `45+21=66` cells. Longest cells are submitted first within each array.
Measured production runtimes predict approximately `125–140` aggregate
cell-hours. With 32-core cells and the observed scheduler capacity, the
scientific wall-time estimate is `13–15` hours, leaving a limited margin for
queueing, collection, and re-analysis inside the 20-hour deadline.

This scan is designed to make the continuum extrapolation better controlled.
It cannot guarantee the fifth-decimal target with the available measurement
budget.

## Submission status

Status time: 2026-07-30 07:42 CST

The approved 66 cells are running as 12 triangular and 8 honeycomb sequential
bundles, with one 32-core allocation per bundle:

| Lattice | Slurm array | Allocations | State |
|---|---:|---:|---|
| triangular | 23012200 | 12 × 32 cores | all running |
| honeycomb | 23012219 | 8 × 32 cores | all running |

All 20 bundles subsequently completed with scheduler exit code zero. Their
66 cells were collected and passed the standard manifest-level audit. The
merged 243-cell analysis uses the recovery windows at `Δτ=0.010,0.013,0.016`
for triangular and retains the bracketed honeycomb `Δτ=0.020` point. The
unbracketed triangular `Δτ=0.020` point remains a recorded diagnostic rather
than entering the primary continuum fit.

The resulting continuum estimates are:

```text
h_c(triangular) = 4.768626879 ± 0.001019229
h_c(honeycomb)  = 2.132538417 ± 0.000562147
R               = 2.236157603 ± 0.000759908
```

The ratio remains statistically compatible with `√5`; the 66-cell recovery
improves field coverage and reduces the ratio standard error from
`0.001006930` to `0.000759908`, but it does not reach the challenge target.

An additional `Δτ=0.004` anchor contains five fields at each of three sizes:

| Lattice | Sizes | Fields |
|---|---|---|
| triangular | 32, 40, 48 | 4.7677, 4.7682, 4.7687, 4.7692, 4.7697 |
| honeycomb | 24, 28, 32 | 2.1317, 2.1322, 2.1327, 2.1332, 2.1337 |

The 30 cells used 20 independent 32-core allocations, each running one or two
cells sequentially. Jobs `23015225`–`23015236` and `23015238`–`23015245`
completed with scheduler exit code zero. All 30 manifests passed the standard
integrity audit, producing a merged total of 273 cells and 8736 bin rows.
Their configurations retained `FixedDltau=0.004`, `nLocal=1`, and
`nWolff=5`.

The independent layout replaces an eight-job packed layout whose nested
Slurm steps did not run concurrently. Startup diagnostics also found and
corrected generated-runner permissions, scan-level time-step validation, and
the time-step scan category before any successful manifest was produced.
Eight incomplete warmup directories from the packed-layout check were moved
to `failed-startup-attempts/23015155-23015162/` for audit rather than deleted.

Pending jobs `23013562` and `23013563` were cancelled before execution and
superseded by the balanced 20-lane layout. They consumed no measured runtime
and produced no cell manifests.

The primary 243-cell estimate remains unchanged. Adding `Δτ=0.004` as the
predeclared sensitivity gives

```text
h_c(triangular) = 4.768620763 ± 0.000575824
h_c(honeycomb)  = 2.132295859 ± 0.000355061
R               = 2.236429014 ± 0.000461302
```

Its 95% ratio interval is `[2.235482503, 2.237300897]`. The additional anchor
reduces the ratio standard error by 39.3% but still does not resolve equality
with `√5`; the two-stage versus joint-fit difference also remains above the
fifth-decimal target.

Generated run specifications, logs, manifests, data, and figures remain in
`tracks/qmc/results/Only-team/` and are not added to Git. Scheduler states
will not be treated as scientific results; every completed cell must pass the
post-run audit before entering a fit.
