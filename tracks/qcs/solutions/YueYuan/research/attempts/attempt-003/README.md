# Attempt 003: Noisy-Oracle Simplex Optimizer

## Status

Accepted by the public development validator on 2026-07-27.

Attempt 003 keeps the toy two-qubit CZ dynamics from attempt 002 and replaces deterministic query traces with a local derivative-free optimizer. The optimizer receives only finite-shot noisy scalar infidelity values. Exact infidelity is used separately for query-to-target bookkeeping and the final guard.

## Method

- Device: two-qubit CZ toy model with 48 raw pulse parameters.
- Model Hessian: finite-difference Hessian at the model optimum, rank `15`.
- Optimizer: pure-NumPy Nelder-Mead-style simplex loop.
- Oracle: finite-shot noisy infidelity estimate with `1024` shots per query.
- Rows: full raw, tilted random subspace, and Hessian subspaces for `k = 0, 3, 8, 15, 24, 48`.

## Result

Public dev validator score: `3.235294117647059`.

| Gap | Median full queries | Median Hessian queries | Median random queries | Speedup |
|---:|---:|---:|---:|---:|
| `0.03` | `75` | `2` | `37` | `37.5` |
| `0.08` | `110` | `34` | `41` | `3.235294117647059` |

Small Hessian subspaces `k = 0, 3, 8` are reported as failures/plateaus.

## Caveat

This is now a real noisy-oracle optimizer loop, but it is still a toy local dynamics benchmark. The easier gap has a very fast Hessian hit because the first simplex edge already lands near the needed model-Hessian direction. Attempt 004 should make the query traces more research-grade by storing per-query traces and adding a plot/table sweep over `k`, gap, and shots.
