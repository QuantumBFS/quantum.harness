# Scalable v1 research-step index

| Step | Purpose | Current attempt | Status |
|---:|---|---:|---|
| 1 | common protocol and evaluator | a03 | step-pass |
| 2 | occupation autoregressive NQS | not started | pending |
| 3 | continuous holomorphic NQS | not started | pending |
| 4 | CF-Flow L=2 and route selection | not started | pending |
| 5 | winner N=8, then SCNet N=10/12 | not started | pending |

## Step 1 attempt accounting

Step 1 used three implementation attempts within one research step:

- [Attempt a01](s01-a01.md) completed Tasks 1-4, then stopped at its
  90-minute active-development limit. It did not claim `step-pass`.
- [Attempt a02](s01-a02.md) completed Tasks 5-6, then stopped at its
  90-minute active-development limit with Task 7 closure still pending.
- [Attempt a03](s01-a03.md) performed Task 7 closure and classified Step 1 as
  `step-pass` after fresh verification.

Attempts a04 and a05 were unused. Step 2 starts in a new worktree and resets
its implementation-attempt counter to a01.

## Trusted-pipeline boundary

`human_blind=false`. The static AST/text audit and hashed manifest checks are
evidence for a cooperative trusted pipeline; they are not a sandbox against
malicious dynamic Python or arbitrary file access. A concrete route may claim
`oracle_isolated` only after a route-specific factory test proves that the
evaluator loads the same checkpoint produced by that route's trainer and bound
to that run by its manifest.

## Resource lifecycle boundary

Step 1 `resource_budget_valid` enforces only the placement-selected wall-time,
peak-RSS, and checkpoint-size ceilings. The frozen `remote_max_cpus=32` becomes
enforceable in Step 5, where tests must inspect the actual `using-slurm` job
request. Peak VRAM remains observed-only until a hardware-specific ceiling is
approved and frozen; no VRAM ceiling is implied by Step 1. Independently, the
Step 2 route-factory test that binds the trainer-produced checkpoint to the same
run manifest remains a hard requirement for `oracle_isolated`.
