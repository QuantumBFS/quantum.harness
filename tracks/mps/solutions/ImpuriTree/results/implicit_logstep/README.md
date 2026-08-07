# Implicit log-step reproduction scripts (STATUS: no full data set yet)

These are the exact production harness scripts behind the implicit
logarithmic-grid results quoted in `../report.md` (Method B). They are
provided for reproducibility; **the full beta = 16 data set does not exist
yet** — the production sweeps were still running when this snapshot was
taken, and the partial deliverables so far are:

- beta = 16: paired first-step gate passed; preparation sweeps in flight
  (exact-RHS baseline past `tau = 1.0`, all steps `<= 1e-6`).
- beta = 4 control: preparation complete (21/21 implicit steps converged);
  `G(tau)` measurement partial — 5 of 17 points at the time of writing
  (see `../beta4_partial/`).

## Heavy-computing warning

This is not a laptop workload. Representative costs on one shared Snellius
Genoa node:

- beta = 16 preparation: ~30 min per implicit step at bond 128 with the
  exact right-hand side (~24 grid steps), 32 cores / 240 GB; certified RHS
  truncation roughly halves the per-step cost.
- `G(tau)` measurement: 8-task fan-out, 16 cores per task, one implicit
  branch propagation per tau point.
- beta = 4 control: 90 min preparation + O(1 h) measurement.

Julia runs with `JULIA_NUM_THREADS = SLURM_CPUS_PER_TASK` and BLAS/Strided
pinned to one thread (`configure_parallel_runtime!` is called by
`rde_beta16_common.jl`).

## Bath input (ESPRIT-tau)

The bath is fitted in the tau domain by ESPRIT with a hard Hankel-rank gate:

- beta = 16: 9 poles per spin (257 tau samples, relative L2 `2.4e-8`).
- **beta = 4: 7 poles per spin** — the block-Hankel numerical rank drops to
  8 at this temperature, so a 9-pole request is refused by the rank gate;
  the 7-pole fit on 513 tau samples reaches relative L2 `9.0e-12`
  (`GRAFT_RDE_NPOLES=7`, `GRAFT_RDE_NTAU_FIT=513`).

## Files

| file | role |
|---|---|
| `rde_beta16_common.jl` | model build, ESPRIT bath fit, evolver/policy factories, grids, checked bootstrap and implicit-step helpers, lock utilities |
| `rde_beta16_first_step.jl` | paired RDE/two-site matched-budget first-step diagnostic (the gate) |
| `rde_beta16_prepare.jl` | full imaginary-time preparation on the merged log/checkpoint grid with thermal checkpoints |
| `rde_beta16_gtau_shard.jl` | one `G(tau)` fan-out worker (operator insertion + branch propagation) |
| `rde_beta16_merge.jl` | fail-closed merge/validation for first-step and `G(tau)` outputs |
| `rde_beta16_plot.jl` | final `G(tau)` figure |
| `run_rde_beta16_prepare.sh`, `run_rde_beta16_gtau_shard.sh` | runner shells showing the exact environment contract |

## Environment contract (run-config)

All solver settings come from environment variables (written into an
immutable `logs/run-config.env` by the staging step in production). Key
values used for the runs quoted in the report:

```
GRAFT_RDE_BETA=16 (or 4)        GRAFT_RDE_NPOLES=9 (or 7)
GRAFT_RDE_NTAU_FIT=257 (or 513) GRAFT_RDE_U=2.0  GRAFT_RDE_EPSILON_D=-1.0
GRAFT_RDE_SOLVE_TOL=1e-6        GRAFT_RDE_PREP_CAP=128
GRAFT_RDE_PREP_METHOD=two_site | residual_driven
GRAFT_RDE_TWO_SITE_TRUNC_RTOL=1e-12
GRAFT_RDE_STEP_FAILURE_POLICY=warn   # measurement mode; error = fail closed
GRAFT_RDE_BOOTSTRAP_KRYLOV_DIM=2 (frozen)
GRAFT_RDE_BOOTSTRAP_MAX_EXACT_BOND=512
GRAFT_RDE_BOOTSTRAP_MAX_EXACT_PAYLOAD=536870912
GRAFT_EXACT_RESIDUAL_MAX_BOND=32768
GRAFT_EXACT_RESIDUAL_MAX_PAYLOAD=1000000000
GRAFT_RHS_TRUNC_ATOL=1e-10
GRAFT_RDE_FIT_SWEEPS=1  GRAFT_RDE_KRYLOV_DIM=20  GRAFT_RDE_KRYLOV_MAXITER=30
GRAFT_RDE_MAX_ROUNDS=16 GRAFT_RDE_WEIGHT_ATOL=1e-14 GRAFT_RDE_WEIGHT_RTOL=0
GRAFT_RDE_ENRICHMENT_ATOL=1e-12 GRAFT_RDE_ENRICHMENT_RTOL=1e-10
GRAFT_RDE_BOOTSTRAP_TAU=0.05 GRAFT_RDE_BOOTSTRAP_GRAM_ATOL=0
GRAFT_RDE_BOOTSTRAP_GRAM_RTOL=1e-12
```

Code revisions: Graft `49d97da` (certified truncation and guard knobs
included), GraftImpurity `0a320ce`, GreenFunc `fa7b48b`, Julia 1.12.6.
Production runs execute under immutable content-locked run roots on
Snellius with source/config/environment hash verification; the evidence
trail lives in the team harness ledger (workstream
`residual-driven-expansion`).
