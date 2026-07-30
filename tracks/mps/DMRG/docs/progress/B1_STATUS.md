# B1 Thread Status: Stage 2 Confirmation and Stage 3 Plan

## Thread identity

- Thread: B1
- Date closed: 2026-07-28
- Scope: record Stage 2 decisions and complete the Stage 3 implementation plan
- Branch: `challenge/issue28-pure-neural`
- HEAD remained: `a734162e0e75098fd9326e0aeb45e9ae3247b0f5`
- Design: [`HARD_GOAL_DESIGN.md`](../../HARD_GOAL_DESIGN.md)
- Plan: [`2026-07-28-issue28-hard-goal-3d-spin-glass.md`](../superpowers/plans/2026-07-28-issue28-hard-goal-3d-spin-glass.md)
- State: Stage 3 complete; Stage 4 has not started

## User-confirmed decisions

On 2026-07-28 the user accepted all five Stage 2 choices:

1. iid equal-probability +/-J Edwards-Anderson model;
2. final Tc from unbiased correction-aware xi_L/L plus Binder, with neural RG
   flow as independent consistency evidence;
3. Route C main, Route B fallback, cube/cross first, chi=2/4/8;
4. sizes `{6,9,12,15,18,24,27,45}` and pilot/power-gated sample counts; and
5. the resource-gated supercomputer workflow, including qdeshell/SCNet pilot
   compatibility evaluation.

This confirms planning and staged implementation. It does not preapprove the
exact Stage 7 scheduler request, which remains a required stop after the pilot.

## Completed in this thread

1. Updated the design from provisional model status to a dated Stage 2 decision
   record while preserving pilot-derived values as provisional.
2. Read and applied the complete repository `writing-plans` skill.
3. Mapped current package, tests, configs, results, artifact helpers,
   autocorrelation code, parameter-scan code, Slurm harness, and qdeshell/scnet
   profiles.
4. Chose an isolated `src/spinglass3d/` package and `test_hg3d_*` namespace so
   Hard Goal work does not overwrite the dirty Easy Goal implementation.
5. Wrote a complete Stage 4-9 implementation plan with:
   - 18 independently reviewable tasks;
   - 124 checkbox actions;
   - exact file ownership and public interfaces;
   - test-first commands and expected failures/passes;
   - milestone go/no conditions;
   - immutable artifact and resume contracts; and
   - a separate Stage 7 preview/confirmation stop.
6. Replaced the writing-plan skill's commit checkpoints with diff-review
   checkpoints because the user forbids commit/push before Stage 9 review.
7. Completed the skill self-review for specification coverage, ambiguous
   placeholder removal, and cross-task interface consistency.
8. Corrected the design's symmetry wording: explicit group averaging and orbit
   canonicalization are distinct exact-invariant parameterizations and are not
   asserted equal for identical TT cores.

## Key implementation decisions

- NumPy/int8/float64 is the correctness reference; optional JAX vectorizes only
  over independent disorder, temperature, and walker states.
- Biased within-state updates remain random sequential unless a full
  RG-plus-bias conflict coloring is proven equivalent.
- Stage 4 reuses the existing 2D MPS implementation without modifying it.
- The primary finite linear comparator includes gauge-invariant
  flux-conditioned terms, preventing an unfair information advantage for TT.
- A complete PT ladder is one scheduling cell; temperatures are never a cell
  axis.
- Production configuration is generated only from a passing Stage 6 pilot and
  then shown to the user before any real submission.
- The stable production run ID in the plan is `hg3d-production-v1`; immutable
  result cells refuse overwrite.

## Review results

| Check | Result |
|---|---|
| Required `writing-plans` header and task format | PASS |
| Plan task count | 18 |
| Plan checkbox count | 124 |
| Forbidden ambiguous-pattern scan | PASS, no matches |
| Cross-task type/file ownership review | PASS after observable/report/manifest corrections |
| `git diff --check` for B0/B1 design and plan documents | PASS |
| New scientific or production code | Not written in this thread |
| Local/remote scientific compute | Not run in this thread |
| Commit, push, branch switch, PR update, Slurm submission | Not performed |

No new code tests were necessary because B1 changed planning documents only.
The preceding B0 thread recorded `24 passed` for all existing MPS tests.

## Not completed

- Stage 4 fresh 2D regression has not run.
- No `spinglass3d` source, test, config, runner, or Slurm wrapper exists yet.
- No 3D exact validation, PT pilot, production protocol, L=45 data, FSS fit, or
  Hard Goal report exists.
- No exact production resource request has been generated or approved.

## Next thread

Open B2 for Stage 4 only. Use the plan with `superpowers:executing-plans` inline
unless the user explicitly selects subagent-driven execution. Implement Tasks
1-2, run the fresh 2D regression gate, and write `docs/progress/B2_STATUS.md`
before deciding whether Stage 5 may begin.
