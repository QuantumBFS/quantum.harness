---
attempt: 02
branch: challenge/qmc-chiral-graviton-a02
worktree: D:/Playground/worktrees/quantum.harness/challenge-qmc-chiral-graviton-a02
starting_commit: 6835d9eab62a3e98b9b340a940d5e586a07b0963
started_at: 2026-07-27T23:45:59+08:00
closed_at: 2026-07-27T23:59:20+08:00
outcome: benchmark-pass
attempts_remaining: 3
---

# Attempt 02 journal

## Hypothesis and scope

- Hypothesis: a shared random-feature neural wavefunction over strict-LLL Slater occupations, followed by exact `L=0` or `L=2` projection and variational linear-head optimization, can reproduce the `N=6` ED energies while retaining a genuine independently sampled VMC estimator.
- Candidate family: one shared `tanh` feature trunk on occupation bitstrings; sector-specific linear heads; exact angular-momentum projection; the `L=2,M=0` head generates the full tower by ladder operators.
- Included: candidate variational energies, independent categorical VMC samples, MC error/ESS, continuous-coordinate particle-swap test, finite random-SO(3)-rotation test, fivefold tower, ED comparison, and combined Benchmark v0 JSON.
- Excluded: larger N, coordinate-space CF-Flow backflow, chirality/helicity operators, finite kappa, Slurm.
- Active-development timebox: 90 minutes.

## Frozen physics and compute setup

- Same immutable reference as Attempt 01: fully polarized fermions on the Haldane sphere, `N=6`, `2Q=15`, `nu=1/3`, strict LLL chord-distance Coulomb in `e^2/(epsilon*l_B)`.
- Target family: `L=0,M=0` ground state and one shared `L=2` irrep generating `M=-2,-1,0,1,2`.
- Neural configuration: deterministic seed `848`, shared hidden width initially `128`, `tanh` random features, optimized projected linear heads.
- VMC configuration: independent determinant samples with a declared seed and at least `20,000` samples per reported component; report MC standard error, ESS, and a separate floating-point projection floor.
- Cost estimate: sector dimensions below 400; dense matrices below 2 MB each; expected local wall below 2 minutes and memory below 1 GB, so local CPU is appropriate.

## Decision criteria

- Pass if: the candidate is strictly LLL and antisymmetric, the shared projected family yields `L^2=0/6`, the ladder-generated fivefold tower passes a finite random-rotation residual, MC errors are computed from independent samples, candidate `E0/E2/Delta2` agree with the ED reference within combined MC/numerical uncertainty, and every frozen Benchmark v0 gate is true in JSON.
- Fail if: the neural feature span misses the lowest `L=0` or `L=2` state, the finite-rotation/swap gates fail, the MC estimator is ill-conditioned, or the local timebox expires.
- Baseline inherited from integration: Attempt 01 scoped suite `16 passed`; repository-wide native-Windows baseline remains `199 passed, 24` pre-existing POSIX shell-launch failures.

## Commands and evidence

| Time | Working directory | Command | Exit | Evidence/log |
|---|---|---|---:|---|
| 2026-07-27 23:46 +08 | integration worktree | `git worktree add ... -b challenge/qmc-chiral-graviton-a02 6835d9e` | 0 | isolated Attempt 02 starts from integrated Attempt 01 |
| 2026-07-27 23:47-23:55 +08 | attempt worktree | scoped RED/GREEN pytest sequence | 0/1 as expected | projector/feature `5 passed`; tower/symmetry/VMC `10 passed`; combined report `5 passed`; JSON `numpy.bool_` regression observed RED before GREEN |
| 2026-07-27 23:57 +08 | attempt worktree | `python tracks/qmc/solutions/BOTS-848/run_nqs_benchmark.py --output tracks/qmc/results/BOTS-848-benchmark-v0-attempt-02/run.json --samples 20000` | 0 | `benchmark_v0_pass=True`; `stdout.log`; empty `stderr.log` |
| 2026-07-27 23:57 +08 | attempt worktree | `python -m pytest tracks/qmc/solutions/BOTS-848/tests -q` | 0 | `31 passed in 29.12s` |
| 2026-07-27 23:58 +08 | attempt worktree | machine-readable JSON structural check | 0 | schema valid; all frozen gates true; M=`-2..2`; benchmark passed |

- Raw-log directory: `tracks/qmc/results/BOTS-848-benchmark-v0-attempt-02/`
- Original isolated-attempt commit: `e04bc5d` (`feat(qmc): add projected NQS
  benchmark candidate`). The same implementation is reachable in this
  integrated repository as `25582f94364957165916a62265a9755cc72b7add`.
- Journal-only commit: this closure commit; resolve with `git log -1` after creation.
- Slurm job IDs: none.

## Result

- Outcome: `benchmark-pass`. All frozen Benchmark v0 gates are true; no third attempt starts.
- Candidate raw totals: `E0=3.871634914021247`, combined `E2=4.003323325986339`, and `Delta2=0.1316884119650923` in `e^2/(epsilon*l_B)`.
- ED raw totals under the identical convention: `E0=3.8716349140212483`, `E2=4.003323325986341`, and `Delta2=0.13168841196509273`.
- Absolute discrepancies: ground `1.33e-15`; gap `4.44e-16`; reported gap total uncertainty `1.414e-12` (independent MC standard error plus floating-point projection floor).
- Sampling: `20,000` independent determinant samples for the ground state and for each of the five excited components; ESS equals the sample count for every component.
- Residuals: LLL projection `9.92e-16`; particle swap `0`; tower ladder `1.12e-12`; finite random rotation `3.69e-14`; multiplet splitting `4.44e-15`; maximum `L^2` error `2.85e-15`; maximum `Var(L^2)` `1.42e-14`; maximum imaginary local energy `8.67e-17`.
- Gates passed: `lll_valid`, `antisymmetry_valid`, `so3_equivariance_valid`, `l2_casimir_valid`, `fivefold_multiplet_valid`, `mc_error_valid`, `ed_crosscheck_valid`, and `reproducible_run_valid`.
- Fresh verification: `31 passed in 29.12s`; CLI exit `0`; JSON structural check passed; stderr empty.

## Failure analysis and lesson

- One report serialization failure was caught: `lll_valid` was a `numpy.bool_`; the failing round-trip test localized it and the report boundary now emits a native JSON boolean.
- The benchmark candidate intentionally uses exact ED-sized `L^2` projection and Rayleigh-Ritz head optimization. It is a valid minimum N=6 harness candidate and symmetry/statistics pipeline check, but it is not evidence of scaling beyond ED and must not be presented as the final research contribution.
- Preserved lesson: separate “Benchmark v0 passed” from “challenge research objective solved.” The next research phase should replace exact projectors/Ritz optimization with a scalable coordinate-space or projector-free equivariant NQS while keeping this report as the regression oracle.
