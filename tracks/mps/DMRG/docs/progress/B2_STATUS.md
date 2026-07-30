# B2 Thread Status: Stage 4 MPS Regression Gate

## Thread identity

- Thread: B2
- Date closed: 2026-07-28
- Scope: implementation-plan Tasks 1-2 and the Stage 4 / M4 gate only
- Execution mode: subagent-driven development with independent task review
- Branch retained: `challenge/issue28-pure-neural`
- HEAD remained: `a734162e0e75098fd9326e0aeb45e9ae3247b0f5`
- Plan: [`2026-07-28-issue28-hard-goal-3d-spin-glass.md`](../superpowers/plans/2026-07-28-issue28-hard-goal-3d-spin-glass.md)
- State: Stage 4 complete; Stage 5 has not started

## Completed in this thread

1. Added the isolated `spinglass3d` package boundary and strict immutable TOML
   loader.
2. Froze the confirmed iid equal-probability +/-J Edwards-Anderson model,
   lattice sizes, RG policy, route roles, TT ranks, independent FSS evidence,
   terminal classes, and ten-clause success contract.
3. Added the Stage 4 2D MPS/VMCRG regression config and consolidated
   `scripts/hard_goal.py stage4` entry point.
4. Re-ran all existing MPS tests and fresh numerical checks for TT gradients,
   canonicalization, 100 incremental updates, and checkpoint equality.
5. Ran the required fresh L=45, b=3, chi=2 connectivity cell with four walkers,
   eight optimizer steps, eight thermal sweeps, and sixteen frozen measurement
   sweeps.
6. Fixed the review-discovered publication race with Linux
   `renameat2(RENAME_NOREPLACE)` and a test that creates the destination during
   execution. Unsupported platforms fail closed.
7. Preserved the original `stage4-b2` evidence and published the fixed-source
   run separately at `results/hard_goal/stage4-b2-r1/`.

## Key decisions and evidence

- Confirmed contract hash:
  `4b165b203b0f8f64fda7eae5dfb0645280290f1ba8a94700d95d3eee1780b48f`.
- Fresh manifest classification: `PASS`, with no failed gates.
- Fresh manifest SHA-256:
  `1241e62660f35221b9a675909f239a75130f9b0a4649be0be59b0d0bcceb96a7`.
- Original manifest remained unchanged at
  `97c4d4cbac3c7df609e74a05e0fedbafc6de94fff0320ee188fe6260009ca310`.
- All seven published artifact hashes were independently recomputed and
  matched; the current workflow source hash matches the fresh manifest.
- The frozen MPS remained array-identical across all sixteen measurement
  sweeps.
- Stage 4 is explicitly two-dimensional regression evidence only. It is not
  equilibration, spin-glass, finite-size, transition-temperature, or other 3D
  Hard Goal evidence.

## Tests and reviews

| Check | Result |
|---|---|
| Task 1 focused config tests | 13 passed |
| Existing MPS tests | 24 passed |
| Task 2 focused tests after race fix | 8 passed |
| Combined final B2 suite | 45 passed in 4.12 s |
| Python syntax compilation | PASS |
| Scoped `git diff --check` | PASS |
| Task 1 independent review | Spec PASS; quality approved; no findings |
| Task 2 scoped re-review | Atomic race addressed; no new breakage |
| B2 integrated final review | No Critical or Important findings |

The integrated reviewer retained two non-load-bearing minor items for later
hardening: record `changed:<path>` source-integrity details, and add direct
classifier tests for canonicalization, local-delta, and checkpoint failures.
Both affect diagnostics or branch-level coverage, not the current fail-closed
M4 result.

## Not completed

- No 3D cubic bond, exact-oracle, overlap, observable, RG, gauge, symmetry, TT,
  parallel-tempering, equilibration, VMCRG-training, or accelerator code has
  been implemented.
- No Stage 5 exact or small-3D validation has run.
- Second RG remains disabled.
- No Stage 6 pilot, Stage 7 production request, L=45 3D production data, FSS
  fit, Tc estimate, or Hard Goal report exists.
- No local large compute, Slurm submission, commit, push, branch switch, PR
  mutation, or Ready-for-review action was performed.

## Next thread

Open B3 for Stage 5 only. Resume at plan Task 3 and complete Tasks 3-13 through
the exact and small-3D M5 validation gate. The M4 PASS authorizes that work but
does not authorize second RG, a medium pilot, production, or cluster
submission. Carry the two deferred minor findings into the final review and
fix them when the Stage 4 integrity inventory is next regenerated.
