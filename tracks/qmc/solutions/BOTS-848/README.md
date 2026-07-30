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

> **Submission entry point:** [SUBMISSION.md](SUBMISSION.md) contains the
> evaluator-facing result, acceptance checklist, reproduction command, and an
> honest separation between the passing Benchmark v0 and the scalable Route D+
> research candidate.

## Working documents

| Document | Purpose |
|---|---|
| [Benchmark v0](docs/benchmark-v0.md) | Fixed problem, required outputs, pass/fail gates, and quantitative ranking metrics. |
| [CF-Flow extension study](docs/cf-flow-extension-study.md) | Source-faithful comparison with arXiv:2512.00527 and the post-benchmark research routes. |
| [Execution protocol](docs/execution-protocol.md) | Five-attempt hard limit, isolated worktrees, timeboxes, logging, and failure-learning rules. |
| [Attempt journals](logs/README.md) | Attempt counter, outcome index, and the journal template used for every implementation. |
| [Scalable v1 protocol](scalable_v1/protocol.json) | Frozen route-independent budgets, thresholds, and resource ceilings. |
| [Scalable v1 logs](logs/scalable-v1/README.md) | Five research steps and per-step implementation-attempt accounting. |
| [Scalable v1 design](../../../../docs/superpowers/specs/2026-07-28-challenge-15-scalable-v1-design.md) | Four-route comparison, oracle isolation, scalable gates, five research steps, and per-step attempt accounting. |
| [Scalable v1 Step 1 plan](../../../../docs/superpowers/plans/2026-07-28-challenge-15-scalable-v1-step-1.md) | TDD plan for the frozen common protocol, audit-first evaluator, schema, gates, resources, and attempt logs. |
| [Four-route admission plan](../../../../docs/superpowers/plans/2026-07-28-challenge-15-four-route-admission.md) | Additive Route D capacity, reveal-only ED fidelity, and the exact common comparison SHA. |
| [Route A plan](../../../../docs/superpowers/plans/2026-07-28-challenge-15-route-a-occupation-autoregressive.md) | Occupation-space autoregressive NQS in five bounded attempts. |
| [Route B plan](../../../../docs/superpowers/plans/2026-07-28-challenge-15-route-b-continuous-holomorphic.md) | Continuous fixed-degree holomorphic NQS in five bounded attempts. |
| [Route C plan](../../../../docs/superpowers/plans/2026-07-28-challenge-15-route-c-cf-flow-l2.md) | CG-coupled CF-Flow `L=2` prototype and explicit LLL-leakage decision. |
| [Route D plan](../../../../docs/superpowers/plans/2026-07-28-challenge-15-route-d-analytic-seed-neural-correlator.md) | Analytic `L=2` projected-density mother dressed by a scalar neural correlator. |
| [Route D+ Phase 1](docs/route-d-plus-phase1.md) | Final physics-first workflow: fixed conventions, remote JAX x64/GPU gate, and reproducible environment manifest. |
| [AITP import source](docs/aitp-2-migration-handoff.md) | Pinned source imported into the current AITP Research Memory Entries and working Note. |

## Status

- Challenge registration metadata is present.
- Benchmark scope and paper-gap analysis are archived.
- Benchmark implementation is capped at five short, worktree-isolated attempts. Attempt 01 closed as an ED-oracle `slice-pass`; Attempt 02 closed as `benchmark-pass`, so Attempts 03-05 were not started.
- The final clean GPU reproduction of the projected random-feature NQS gives
  raw `E0=3.871634914021250`, `E2=4.003323325986342`, and
  `Delta2=0.13168841196509184`, with a gap discrepancy of `7.11e-15` from ED
  and a reported total uncertainty of `1.4142135649e-12`.
- Every frozen Benchmark v0 gate passes. The candidate uses ED-sized exact `L^2` projection and Ritz optimization, so larger-N scalability and the final challenge research contribution remain future work rather than part of the v0 claim.
- Scalable v1 Step 1 is complete: the audit-first evaluator is available through [run_scalable_evaluator.py](run_scalable_evaluator.py).
- The scalable Route D+ candidate is implemented through continuous-coordinate
  VMC/SR, certificate schemas, isolated Slurm workflows, Phase 7 ED comparison,
  and optimizer remediation.
- Route D+ Phases 1–5 and Phase 6A passed remote GPU certificate gates.
  Phase 7 completed on jobs `23029855` and `23030080`; the first frozen D+0
  family has mean ground/tower fidelities `0.99741`/`0.87731` and gap error
  `0.009995`. The span ceiling (`0.99996`/`0.97806`) identifies an optimization
  failure rather than a capacity failure, so no final scalable-accuracy claim
  is made.
- The current AITP Research Memory runtime is active at
  `/home/bhjia/physics/vmc_nqs`; the Phase 1 result is pinned by a canonical
  Entry and closeout Note. No project code or tests have run on the local host.
