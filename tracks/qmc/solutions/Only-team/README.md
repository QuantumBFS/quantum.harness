## Team

| | |
|---|---|
| **Team name** | Only-team |
| **Members** | Xingcan-Liu |

## Challenge

| Row | |
|---|---|
| **Challenge** | Determine whether the ratio of the triangular- and honeycomb-lattice transverse-field Ising critical fields is exactly √5, improving the 2002 precision by at least a factor of five. |
| **Catalog issue** | Addresses #148 — released by Xiao-Yan Xu, Shanghai Jiao Tong University. |
| **Track** | `qmc` — selected from the issue's `Method: Quantum Monte Carlo` field. |

## Method

The calculation uses discrete-imaginary-time cluster Monte Carlo for the
transverse-field Ising model,

```text
H = J1 sum_<i,j> sigma_z_i sigma_z_j - hTrfd sum_i sigma_x_i,
```

with `J1=-1`, `J2=0`, periodic boundaries, and `BetaT=L/hTrfd`.  Each of 32
MPI ranks runs a complete independent Markov chain with deterministic rank
seeds.  Measurements use `Q=<m²>²/<m⁴>`.

The challenge scan contains triangular sizes through `L=48`, honeycomb sizes
through `L=32`, and requested time steps `0.013`, `0.016`, and `0.020`.
Finite-size fits fix `yt=1.587` and `yi=-0.815`; time-step fits use each
cell's actual `Dltau²`, including the even-`LTrot` rounding.

## Verification

Small-system exact diagonalization and exact finite-Trotter calculations
validate both lattices and the measured Binder ratio; see `VALIDATION.md`.
The post-run audit additionally verifies all 177 manifests, file hashes,
32-bin sequences, rank seeds, finite observables, and per-bin Binder formulas.

The completed scan is statistically compatible with `√5`, but it does not
reach the requested fifth-decimal precision.  In particular, the largest
triangular cells miss the declared Binder-error target, step-specific
triangular critical fields lie beyond the measured field windows, and the
two-stage and joint time-step fits differ beyond the target tolerance.  These
limitations are reported rather than absorbed into a smaller error bar.

## Reproducible post-run analysis

From the repository root, with the four completed raw result directories
available under `tracks/qmc/results/Only-team/`, run:

```bash
.venv/bin/python tracks/qmc/solutions/Only-team/scripts/audit_challenge_results.py \
  --run-dir tracks/qmc/results/Only-team/challenge-extremes-min-20260729 \
  --run-dir tracks/qmc/results/Only-team/challenge-extremes-max-20260729 \
  --run-dir tracks/qmc/results/Only-team/challenge-production-triangular-20260729 \
  --run-dir tracks/qmc/results/Only-team/challenge-production-honeycomb-20260729 \
  --output-dir tracks/qmc/results/Only-team/challenge-analysis-20260729 \
  --write-ratified-selection

.venv/bin/python tracks/qmc/solutions/Only-team/scripts/assemble_challenge_dataset.py \
  --run-dir tracks/qmc/results/Only-team/challenge-extremes-min-20260729 \
  --run-dir tracks/qmc/results/Only-team/challenge-extremes-max-20260729 \
  --run-dir tracks/qmc/results/Only-team/challenge-production-triangular-20260729 \
  --run-dir tracks/qmc/results/Only-team/challenge-production-honeycomb-20260729 \
  --output-dir tracks/qmc/results/Only-team/challenge-analysis-20260729

.venv/bin/python tracks/qmc/solutions/Only-team/scripts/fit_binder_scaling.py \
  --cells tracks/qmc/results/Only-team/challenge-analysis-20260729/cells.csv \
  --bins tracks/qmc/results/Only-team/challenge-analysis-20260729/bins.csv \
  --output-dir tracks/qmc/results/Only-team/challenge-analysis-20260729 \
  --bootstrap 2000 --seed 20260729

.venv/bin/python tracks/qmc/solutions/Only-team/scripts/extrapolate_dtau.py \
  --cells tracks/qmc/results/Only-team/challenge-analysis-20260729/cells.csv \
  --bins tracks/qmc/results/Only-team/challenge-analysis-20260729/bins.csv \
  --output-dir tracks/qmc/results/Only-team/challenge-analysis-20260729 \
  --bootstrap 2000 --seed 20260731 \
  --finite-size-fits tracks/qmc/results/Only-team/challenge-analysis-20260729/finite_size_fits.csv \
  --finite-size-sensitivities tracks/qmc/results/Only-team/challenge-analysis-20260729/finite_size_sensitivities.csv

.venv/bin/python tracks/qmc/solutions/Only-team/scripts/plot_challenge_results.py \
  --cells tracks/qmc/results/Only-team/challenge-analysis-20260729/cells.csv \
  --finite-size-fits tracks/qmc/results/Only-team/challenge-analysis-20260729/finite_size_fits.csv \
  --dtau-fits tracks/qmc/results/Only-team/challenge-analysis-20260729/dtau_fits.csv \
  --final-results tracks/qmc/results/Only-team/challenge-analysis-20260729/final_results.json \
  --output-dir tracks/qmc/results/Only-team/challenge-analysis-20260729/figures

.venv/bin/python tracks/qmc/solutions/Only-team/scripts/build_challenge_run.py \
  tracks/qmc/results/Only-team/challenge-analysis-20260729
```

The ignored analysis directory separates three uncertainty sources:

- bin-bootstrap statistical uncertainty;
- actual-`Dltau²` extrapolation uncertainty;
- finite-size model and size-cut systematic spread.

No result directory needs to be added to Git.
