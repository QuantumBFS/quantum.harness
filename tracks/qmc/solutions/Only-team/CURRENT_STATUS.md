# Challenge #148 current status

Status time: 2026-07-30 19:23 CST

This is the single entry point for the current scientific and operational
state. Earlier design, submission, and analysis documents remain dated
snapshots and link here when their execution state has changed.

## Completed and verified

- The Julia discrete-imaginary-time cluster Monte Carlo implementation,
  triangular and honeycomb lattices, local and ordinary Wolff updates, MPI
  independent chains, and output analysis are implemented.
- Small-system exact diagonalization and exact finite-Trotter checks support
  the Hamiltonian convention and the measured Binder ratio on both lattices;
  see `VALIDATION.md`.
- The first production data set contains 177 integrity-valid cells. Its audit
  verifies every manifest, declared artifact hash, 32-bin sequence, rank-seed
  list, finite observable, and per-bin Binder formula.
- The self-contained report is at
  `tracks/qmc/results/Only-team/challenge-analysis-20260729/report.html`.

The audited 177-cell estimate is

```text
h_c(triangular, Δτ→0) = 4.768728679 ± 0.001167797
h_c(honeycomb, Δτ→0)  = 2.132617106 ± 0.000794629
R                     = 2.236062909 ± 0.001006930
R − √5                = −0.000005069
```

It is statistically compatible with `√5`, but its uncertainty does not meet
the challenge's fifth-decimal target. The recorded limitations are
triangular field coverage, large-cell Binder uncertainty, and sensitivity of
the time-step extrapolation.

Git commit `9048612` contains the verified implementation, analysis workflow,
data-collapse report structure, and the 177-cell reliability record.
Generated data and figures remain under the gitignored result tree.

## Completed 66-cell recovery analysis

The 66-cell recovery scan uses 32 MPI ranks per cell,
`nWarm=10000`, `NmBin=32`, `NSwep=2000`, `nLocal=1`, and `nWolff=5`.

- Triangular: `L=32,40,48`; requested `Δτ=0.010,0.013,0.016`;
  45 cells.
- Honeycomb: `L=24,28,32`; requested `Δτ=0.010,0.016`; 21 cells.
- Slurm arrays `23012200` and `23012219` completed all 20 bundles with
  scheduler exit code zero.
- All 66 manifests and all `66×32=2112` bin rows passed the integrity audit.
- The merged analysis contains 243 cells and 7776 bin rows.

The recovery-window analysis gives

```text
h_c(triangular, Δτ→0) = 4.768626879 ± 0.001019229
h_c(honeycomb, Δτ→0)  = 2.132538417 ± 0.000562147
R                     = 2.236157603 ± 0.000759908
R − √5                = +0.000089625
```

The 95% interval for `R` is `[2.234599154, 2.237603704]`, so the result remains
compatible with `√5` but does not meet the fifth-decimal precision target.
The recovery window captures the large-size triangular crossings; the
remaining limitations are one triangular step estimate at the edge of its
field window, the two-stage versus joint-fit difference, and per-cell
statistical uncertainty. The updated report is at
`tracks/qmc/results/Only-team/challenge-analysis-recovery-20260730/report.html`.

## Completed small-time-step sensitivity

The requested `Δτ=0.004` scan contains 30 cells:

| Lattice | Sizes | Fields |
|---|---|---|
| triangular | 32, 40, 48 | 4.7677, 4.7682, 4.7687, 4.7692, 4.7697 |
| honeycomb | 24, 28, 32 | 2.1317, 2.1322, 2.1327, 2.1332, 2.1337 |

The final layout used 20 independent 32-core allocations, one per calculation
lane, for 640 cores in total. Jobs `23015225`–`23015236` and
`23015238`–`23015245` all completed with scheduler exit code zero. All 30
manifests passed the standard hash, bin, seed, finiteness, and Binder-formula
audit. The merged data set contains 273 cells and 8736 bin rows.

Earlier startup attempts exposed three wrapper/specification faults before
scientific sampling: two generated shell runners lacked execute permission,
the scan-level time step was checked against an unrelated default, and the
time-step scan label was outside the accepted categories. The first three
attempts produced no manifests. A subsequent packed-allocation check showed
that nested Slurm steps serialized; those eight jobs were cancelled after
about three minutes, and their eight incomplete directories were moved to
`failed-startup-attempts/23015155-23015162/` for audit rather than deleted.
The independent-job layout removes the nested-step dependency.

Pending jobs `23013562` and `23013563` were also cancelled before execution
when the original allocation layout was superseded. They consumed no measured
runtime and produced no cell manifests.

The predeclared primary fit remains the 243-cell result above. Adding the
smaller time step as a sensitivity gives

```text
h_c(triangular, Δτ→0) = 4.768620763 ± 0.000575824
h_c(honeycomb, Δτ→0)  = 2.132295859 ± 0.000355061
R                     = 2.236429014 ± 0.000461302
R − √5                = +0.000361036
```

The sensitivity 95% interval for `R` is
`[2.235482503, 2.237300897]`. The smaller time step reduces the ratio
bootstrap standard error by 39.3%, but the interval still contains `√5` and
the two-stage versus joint-fit difference remains above the fifth-decimal
target. The final report is at
`tracks/qmc/results/Only-team/challenge-analysis-final-20260730/report.html`.

## PR handoff

- The final self-contained HTML report was reviewed with seven embedded
  figures, including the separately labelled `Δτ=0.004` sensitivity plot.
- The 35 Python post-processing tests and the complete Julia package test
  suite pass.
- The tracked solution tree passes the prohibited-wording, production-path,
  Python-compilation, and whitespace checks.
- Generated data, figures, and HTML remain under
  `tracks/qmc/results/Only-team/`, which is intentionally gitignored.
- PR #224 is the single review target for this submission.
