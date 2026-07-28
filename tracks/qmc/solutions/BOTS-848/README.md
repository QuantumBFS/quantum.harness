## Team

| | |
|---|---|
| **Team name** | BOTS:848 |
| **Members** | Shaojie Tai, Huanjing Gong, Bohan Jia |

## Challenge

| Row | |
|---|---|
| **Challenge** | Can an exchange-antisymmetric, SO(3)-equivariant neural quantum state compute the chiral-graviton neutral gap Δ = E(L=2) − E(L=0) at ν = 1/3 and certify the spin-2 mode through ⟨L²⟩ = 6 and fivefold degeneracy, while reaching system sizes beyond exact diagonalization? |
| **Catalog issue** | `Addresses #15` — “Symmetric neural-network ansatz for the chiral graviton in ν = 1/3 fractional quantum Hall state,” released by Lei Wang, Institute of Physics, Chinese Academy of Sciences. |
| **Track** | `tracks/qmc/` — selected from the challenge issue's `Method` field: `Variational Monte Carlo / Neural Quantum States`. |

## Current scope

The Challenge #15 minimum acceptance criteria are the project benchmark. Benchmark v0 fixes the required instance to `N=6`, `2Q=15`, in the lowest Landau level on the Haldane sphere with the chord-distance Coulomb interaction. A candidate passes only after reporting `E(L=0)`, all five `E(L=2,M)` values, the neutral gap and Monte Carlo uncertainty, together with antisymmetry, SO(3) covariance, `⟨L²⟩=6`, fivefold degeneracy, exact-diagonalization agreement, and a reproducible run.

Larger systems, thermodynamic extrapolation, chiral-metric response, and Landau-level-mixing scans are research extensions. They do not block Benchmark v0.

## Working documents

| Document | Purpose |
|---|---|
| [Benchmark v0](docs/benchmark-v0.md) | Fixed problem, required outputs, pass/fail gates, and quantitative ranking metrics. |
| [CF-Flow extension study](docs/cf-flow-extension-study.md) | Source-faithful comparison with arXiv:2512.00527 and the post-benchmark research routes. |
| [Execution protocol](docs/execution-protocol.md) | Five-attempt hard limit, isolated worktrees, timeboxes, logging, and failure-learning rules. |
| [Attempt journals](logs/README.md) | Attempt counter, outcome index, and the journal template used for every implementation. |
| [Scalable v1 protocol](scalable_v1/protocol.json) | Frozen route-independent budgets, thresholds, and resource ceilings. |
| [Scalable v1 logs](logs/scalable-v1/README.md) | Five research steps and per-step implementation-attempt accounting. |
| [Scalable v1 design](../../../../docs/superpowers/specs/2026-07-28-challenge-15-scalable-v1-design.md) | Three-route comparison, oracle isolation, scalable gates, five research steps, and per-step attempt accounting. |
| [Scalable v1 Step 1 plan](../../../../docs/superpowers/plans/2026-07-28-challenge-15-scalable-v1-step-1.md) | TDD plan for the frozen common protocol, audit-first evaluator, schema, gates, resources, and attempt logs. |

## Status

- Challenge registration metadata is present.
- Benchmark scope and paper-gap analysis are archived.
- Benchmark implementation is capped at five short, worktree-isolated attempts. Attempt 01 closed as an ED-oracle `slice-pass`; Attempt 02 closed as `benchmark-pass`, so Attempts 03-05 were not started.
- The projected random-feature NQS candidate gives raw `E0=3.871634914021247`, `E2=4.003323325986339`, and `Delta2=0.1316884119650923`, with a gap discrepancy of `4.44e-16` from ED and a reported total uncertainty of `1.414e-12`.
- Every frozen Benchmark v0 gate passes. The candidate uses ED-sized exact `L^2` projection and Ritz optimization, so larger-N scalability and the final challenge research contribution remain future work rather than part of the v0 claim.
- Scalable v1 Step 1 is complete: the audit-first evaluator is available through [run_scalable_evaluator.py](run_scalable_evaluator.py).
- No scalable candidate route has been implemented; Step 2 begins with occupation-space autoregressive NQS Attempt a01.
