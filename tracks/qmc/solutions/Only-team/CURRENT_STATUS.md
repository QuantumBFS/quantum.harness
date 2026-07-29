# Challenge #148 current status

Status time: 2026-07-30 00:40 CST

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

## Active calculations

### Field-window and precision recovery

The 66-cell recovery scan uses 32 MPI ranks per cell,
`nWarm=10000`, `NmBin=32`, `NSwep=2000`, `nLocal=1`, and `nWolff=5`.

- Triangular: `L=32,40,48`; requested `Δτ=0.010,0.013,0.016`;
  45 cells.
- Honeycomb: `L=24,28,32`; requested `Δτ=0.010,0.016`; 21 cells.
- Slurm arrays `23012200` and `23012219` provide 20 simultaneous 32-core
  allocations.
- At 00:40 CST all 20 allocations were running with no scheduler failure.
  Their current cells had completed 9–29 of 32 bins. The estimated last
  bundle completion is approximately 06:20 CST.

The exact field grids and rationale are recorded in
`PRECISION_RECOVERY_PLAN.md`.

### Small-time-step anchor

The requested `Δτ=0.004` scan contains 30 cells:

| Lattice | Sizes | Fields |
|---|---|---|
| triangular | 32, 40, 48 | 4.7677, 4.7682, 4.7687, 4.7692, 4.7697 |
| honeycomb | 24, 28, 32 | 2.1317, 2.1322, 2.1327, 2.1332, 2.1337 |

Jobs `23013840`–`23013846` and `23013848` form 20 isolated 32-core
calculation lanes across four 96-core and four 64-core allocations, for 640
cores in total. At 00:40 CST they were pending with
`AssocGrpCpuLimit`, as expected while the 66-cell scan occupied the account's
640-core allowance. They are designed to start as those allocations finish.
The conservative completion window remains 16:00–17:30 CST, before the
18:00 analysis cutoff.

The earlier pending jobs `23013562` and `23013563` were cancelled before
running and were replaced by this balanced layout; they consumed no measured
runtime and produced no cell manifests.

Scheduler state alone is not scientific evidence. Active runs will enter the
final analysis only after their results are fetched and pass the same
manifest, hash, bin, seed, and observable audit as the first 177 cells.

## Remaining work

1. Monitor both scans through completion and fetch their result directories.
2. Audit all 96 new cells and classify any missing or failed cell explicitly.
3. Assemble the enlarged data set, rerun finite-size fits, data collapse, and
   actual-`Dltau²` extrapolation.
4. Compare fit families without selecting a result for proximity to `√5`.
5. Regenerate the HTML report and state whether the fifth-decimal target is
   reached.
6. Run the complete Julia and Python test suites before the final explicit
   Git staging operation.
