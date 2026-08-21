# Issue 147 h=3 Validation Assembly

## Goal

Turn the approved h=3 SCNet runs into a strict, one-command evidence bundle
before the hackathon deadline. Assembly performs no production compute and
never treats scheduler completion as scientific success.

## Fixed setup

- H = -J sum_<ij> Z_i Z_j - h sum_i X_i, using Pauli operators.
- J=1, h=3, and a 10x10 open lattice for QMC and PEPO.
- PEPO D=4, delta_beta=0.025, ordinary and thermodynamic compression.
- Boundary contraction chi=16 and 32.
- Optional 4x4 ED is labeled only as a finite-size diagnostic.

## Acceptance

The three run specifications are the authoritative cell lists. Every QMC,
PEPO evolution, and PEPO measurement cell must have a success manifest whose
parameters, settings, and protocol match its run specification.

QMC additionally requires M=32,64,128, four chains per point, at least 32 bins
per chain, and a complete Cartesian grid. PEPO requires both compression modes
and both chi values. Measurement hashes, finite values, increasing beta, and
the Hermiticity threshold are checked before assembly. The production protocol
requires beta=0.025,...,1.0; fixture protocols may use a shorter grid.

## Analysis

QMC is extrapolated linearly in (beta/M)^2. Bootstrap samples propagate chain
uncertainty through internal energy, free energy, and specific heat.

PEPO reports the chi=32 curve. The chi gate requires a relative internal-energy
change below 0.1 percent and an absolute change in log(Z)/N below 1e-4. The
stable-beta result is the longest converged prefix. Since only one D and one
delta_beta are available, truncation and PEPO Trotter convergence are marked
not assessed.

At beta=0.8, the summary records the 1 percent energy and 3 percent
specific-heat targets and whether QMC uncertainty resolves the discrepancy.

## Artifacts

- `thermodynamics.csv`: curves with separated uncertainty and status fields.
- `convergence.csv`: QMC finite-M and PEPO chi diagnostics.
- `resources.csv`: per-chain and per-checkpoint resources.
- `comparison.png/pdf` and `convergence.png/pdf`.
- `summary.json`: setup, completeness, stability, targets, and limitations.

Missing or inconsistent evidence aborts before final artifacts are promoted.
