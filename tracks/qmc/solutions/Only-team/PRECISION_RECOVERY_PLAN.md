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
