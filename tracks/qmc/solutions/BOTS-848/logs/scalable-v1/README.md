# Scalable v1 research-step index

| Step | Purpose | Current attempt | Status |
|---:|---|---:|---|
| 1 | common protocol and evaluator | a03 | step-pass |
| 2A | occupation autoregressive NQS | not started | pending |
| 2B | continuous holomorphic NQS | not started | pending |
| 2C | strict-LLL CF operator NQS | a01 | attempt-failed; route open |
| 2D | analytic L=2 seed times neural correlator | not started | pending |
| 3 | synchronized audit, ED reveal, and route selection | not started | pending |
| 4 | winner N=8 | not started | pending |
| 5 | winner SCNet N=10/12 | not started | pending |

## Step 1 attempt accounting

Step 1 used three implementation attempts within one research step:

- [Attempt a01](s01-a01.md) completed Tasks 1-4, then stopped at its
  90-minute active-development limit. It did not claim `step-pass`.
- [Attempt a02](s01-a02.md) completed Tasks 5-6, then stopped at its
  90-minute active-development limit with Task 7 closure still pending.
- [Attempt a03](s01-a03.md) performed Task 7 closure and classified Step 1 as
  `step-pass` after fresh verification.

Attempts a04 and a05 were unused. The additive Route D admission consumes no
Step 2 attempt. After admission, Steps 2A-2D start in separate worktrees and
each has its own `a01` through `a05` implementation-attempt counter.

## Step 2C attempt accounting

- [Attempt a01](s02c-a01.md) completed the common Route C amendment, exact
  projected-density/scalar primitives, and the JK-projected `L=0/2` seed
  family. It failed at the frozen two-layer exact coordinate-action boundary;
  no trainer, checkpoint, freeze receipt, or ED reveal was produced.

Attempts a02 through a05 remain available. Route C is not `route-stopped` or
`route-frozen`; resumption requires either a common protocol amendment or an
exact depth-two backend that first passes the frozen batch/resource
microbenchmark.

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
