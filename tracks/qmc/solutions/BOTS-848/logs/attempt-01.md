---
attempt: 01
branch: challenge/qmc-chiral-graviton-a01
worktree: D:/Playground/worktrees/quantum.harness/challenge-qmc-chiral-graviton-a01
starting_commit: 9f1dd4ad5d0bdce1de2b5e4a530e2e4401410e87
started_at: 2026-07-27T23:17:43+08:00
closed_at: 2026-07-27T23:39:57+08:00
outcome: slice-pass
attempts_remaining: 4
---

# Attempt 01 journal

## Hypothesis and scope

- Hypothesis: a custom NumPy/SciPy fixed-M exact diagonalization can produce a symmetry-certified `N=6`, `2Q=15`, strict-LLL `L=0/L=2` oracle within one short local attempt.
- Evidence motivating it: the full LLL Fock space has only `binom(16,6)=8008` determinants, and fixed-M sectors are much smaller.
- Included: LLL Coulomb integrals, fixed-M Fock ED, `L^2`, fivefold `M=-2..2` extraction, raw and paper-comparable energy views, JSON schema.
- Excluded: NQS/VMC, chirality, larger N, finite kappa, thermodynamic extrapolation, Slurm jobs.
- Active-development timebox: 90 minutes.

## Frozen physics and compute setup

- Hamiltonian: Eq. (7)-style strict-LLL chord-distance Coulomb interaction on the Haldane sphere.
- Geometry, sector, and size: fully polarized fermions, `N=6`, `2Q=15`, `nu=1/3`, ground `L=0`, target `L=2`.
- Energy views: immutable raw LLL eigenvalues plus a derived paper-comparable view with uniform-background and density-shift corrections.
- Local/remote choice: local CPU; full Fock dimension 8008 and expected fixed-M matrices are below the repository's 10-minute/16-GB local threshold.
- Cluster: configured and read-only probed, but not used in this attempt.

## Decision criteria

- Pass if: the scoped tests and CLI pass; `L=0`, all five `L=2,M` components, `L^2=6`, commutator residual, multiplet splitting, and both conventions are present in valid JSON.
- Fail if: the two-body construction violates Hermiticity/rotation symmetry, the target sectors cannot be classified, the local timebox expires, or no independently checkable run artifact is produced.
- Baseline: `python -m pytest scripts/tests -q` returned `199 passed, 24 failed`; all failures are pre-existing Windows attempts to execute `scripts/harness_slurm.sh` directly (`WinError 193`). The repository's coverage command additionally requires an unavailable `pytest-cov` plugin. No raw traceback is archived because it echoes process environment variables.

## Commands and evidence

| Time | Working directory | Command | Exit | Evidence/log |
|---|---|---|---:|---|
| 2026-07-27 23:17 +08 | integration worktree | `git worktree add ... -b challenge/qmc-chiral-graviton-a01` | 0 | branch starts at `9f1dd4a` |
| 2026-07-27 23:18 +08 | attempt worktree | repository pytest command with coverage | 4 | `pytest-cov` unavailable |
| 2026-07-27 23:18 +08 | attempt worktree | `python -m pytest scripts/tests -q` | 1 | `199 passed, 24` Windows shell-launch failures |
| 2026-07-27 23:20-23:36 +08 | attempt worktree | scoped RED/GREEN pytest sequence | 0/1 as expected | conventions `3 passed`; LLL Coulomb `3 passed`; Fock ED `6 passed`; oracle `4 passed`; reporting-contract regressions each observed RED before GREEN |
| 2026-07-27 23:37 +08 | attempt worktree | `python tracks/qmc/solutions/BOTS-848/run_ed_oracle.py --output tracks/qmc/results/BOTS-848-benchmark-v0-attempt-01/run.json` | 0 | `oracle_pass=True`; `stdout.log`; empty `stderr.log` |
| 2026-07-27 23:38 +08 | attempt worktree | `python -m pytest tracks/qmc/solutions/BOTS-848/tests -q` | 0 | `16 passed in 10.92s` |
| 2026-07-27 23:39 +08 | attempt worktree | machine-readable JSON structural check | 0 | schema valid; all ED-oracle gates true; M=`-2..2`; full benchmark correctly remains pending |

- Raw-log directory: `tracks/qmc/results/BOTS-848-benchmark-v0-attempt-01/`
- Implementation commit: `d3e4567` (`feat(qmc): add challenge 15 ED reference oracle`).
- Journal-only commit: this closure commit; resolve with `git log -1` after creation.
- Slurm job IDs: none.

## Result

- Outcome: `slice-pass`. The deterministic ED reference slice is complete; the full Benchmark v0 is not yet passed because the NQS/VMC candidate and its Monte Carlo/ED-comparison gates remain pending.
- Raw LLL total energies: `E0=3.8716349140212465`, combined `E2=4.003323325986339`, and `Delta2=0.13168841196509273` in `e^2/(epsilon*l_B)`.
- The five raw `E2M` values for `M=-2,-1,0,1,2` are `4.003323325986336`, `4.003323325986341`, `4.003323325986342`, `4.003323325986341`, and `4.003323325986336`.
- Paper-comparison convention: background- and density-corrected total `E0=-2.4656970386099815`, per-particle `E0/N=-0.4109495064349969`, and total `Delta2=0.12021452299219086`.
- Residuals: orbital overlap `1.80e-14`; antisymmetry `2.22e-16`; Hamiltonian Hermiticity `1.25e-16`; `[H,L^2]` `4.83e-13`; fivefold splitting `6.22e-15`; maximum `L^2` error `1.15e-14`; maximum `Var(L^2)` `7.11e-14`.
- ED-oracle gates newly passed: `lll_valid`, `antisymmetry_valid`, `so3_equivariance_valid`, `l2_casimir_valid`, `fivefold_multiplet_valid`, `zero_statistical_error_valid`, `ed_reference_valid`, and `reproducible_run_valid`.
- Fresh verification: `16 passed in 10.92s`; CLI exit `0`; JSON structural check passed; stderr empty.

## Failure analysis and lesson

- Observed setup difference: the repository-wide Slurm shell tests are POSIX-only under the current native Windows pytest process.
- Two reporting defects were caught before closure: CF-Flow Figure 4 reports absolute energy per particle, so the JSON now distinguishes corrected total and per-particle views; an ED reference alone cannot truthfully set the full Benchmark v0 pass flag, so the report marks `ed_reference_ready` with the candidate gates pending.
- What should be preserved: the exact failing baseline count without sensitive raw environment output, the RED/GREEN history, and the two reporting-contract corrections.
- Next-attempt change: implement the `L=0/L=2` NQS/VMC candidate against this immutable ED oracle and reuse its JSON gates; do not alter the ED normalization unless an independent reference exposes a mismatch.
