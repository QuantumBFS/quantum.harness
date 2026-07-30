# Core sim-to-real status

Last updated: 2026-07-29, after Attempt 52 delivery audit

## Decision

The core synthetic-CNOT experiment is scientifically frozen and complete.
Attempt 49 passed all preregistered confirmation gates; Attempt 50 packages,
audits, and replays that result without changing the method, truths, or claim.
No further tuning on the Attempt-49 benchmark is allowed.

The next work is team integration and submission engineering. The
platform-adaptive direction remains paused at its frozen budget.

## Evidence hierarchy

- **Formal confirmation:** Attempt 49, one-shot preregistered fresh holdout,
  288/288 completed runs, six/six gates passed.
- **Independent reconstruction:** Attempt 50, 18/18 checks passed without
  importing the simulator.
- **Core deliverable derivation:** Attempt 51, 11/11 checks passed; no new
  simulator or device query.
- **Gap/invariant delivery audit:** Attempt 52, 22/22 checks passed; no new
  simulator query or confirmation truth.
- **Development/mechanism:** Attempts 42–45.
- **Synthetic-platform boundary:** Attempts 46–47b.
- **Integrity checkpoint:** Attempt 48, 47/47 checks passed.
- **Historical confirmation:** Attempt 22 for the older Joint-15 v1 method.

## Formal numbers

| Method | Success | Truth-cell bootstrap 95% interval | Queries/run | Shots/run |
|---|---:|---:|---:|---:|
| model-informed `k=15` | 90.625% | [81.25%, 97.92%] | 66 | 2,099,200 |
| completed model-informed `k=40` | 25.00% | [12.50%, 37.50%] | 166 | 5,376,000 |
| raw-coordinate `k=40` | 0.00% | [0.00%, 0.00%] | 166 | 5,376,000 |

The paired `k=15 - k=40` advantage is 65.625 percentage points, with lower
95% bound 51.04 points. The paired advantage over raw `k=40` is 90.625
points, with lower bound 81.25 points. No destructive proposal was accepted
among 165 accepted nonzero `k=15` steps; the one-sided exact 95% upper bound
is 1.799%.

The post-hoc restricted-mean queries-to-target values on the same fresh
benchmark are 48.76 [45.35, 52.47] for `k=15`, 160.63 [153.69, 165.84] for
completed model-informed `k=40`, and 166 [166, 166] for raw `k=40`. These
values retain failures at the full method cap and cannot be used as an online
stopping rule.

## Retained negative results

- Attempt 43 rejected the proposed online early-stop certificate.
- Attempt 52 rejects the unconditional rank law and retains only a conditional
  local endpoint/Hessian-rank invariant across `d=2,3,4`.
- Attempt 28 did not identify a cross-dimension resource advantage because
  its frozen epsilon left zero-cost raw warm starts.
- Attempt 47b did not authorize a finite-shot platform pilot.
- Attempt 49's compact formal artifact retains ledger closure and hashes, not
  every query row; the Attempt-50 MWE retains complete rows.
- In drift-only Attempt-49 metadata, a sampled control-map norm describes a
  candidate map that was not applied. The actual applied control-map
  perturbation is zero; this label issue does not affect simulation or gates.

## Exact next sequence

1. Validate the package from a clean clone and record the environment.
2. Freeze and push the final package commit to the public team repository.
3. Compare the teammates' paper reproduction and platform-simulator outputs
   with this direction's mechanism and claim boundary.
4. On the agreed submission day, copy only the reviewed package into the
   official challenge branch with explicit path staging.
5. Verify the protected notebook is untouched, render the final report, update
   team metadata, and only then mark the existing PR ready for review.
