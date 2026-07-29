# Quantum Harness Issue #88 — remote research agent status

Updated: 2026-07-29T14:48:39Z

- Objective: obtain a new reproducible numerical certificate for an
  unrestricted frustrated spin-1/2 model, prioritizing the Shastry--Sutherland
  local KMS gap relaxation at `g=4/5`, `gamma=2`, complete degree `d=2`.
- Local branch: `remote/challenge88-terminal-solve` at `87be3177694bbc3db6566016eb645018cb59213d`.
- Local checkout was clean at takeover. No user changes were shipped or
  overwritten.
- Preserved SCNet baseline job `118171391`: `RUNNING` on `kshcnormal`, 32 CPUs,
  114000 MiB, 12-hour limit. At 2026-07-29T14:48Z it was in exact `L=2,d=2`
  coefficient/isotypic assembly before JuMP/Mosek, with about 6.1 GB process
  RSS. It has not been cancelled or modified.
- Preserved xH5 baseline job `23011251`: `PENDING (Priority)` on
  `xhacnormalb`, 64 CPUs, 240 GB, 12-hour limit. It has not been cancelled or
  modified.
- Scientific interpretation guard: the run is an unrestricted finite
  relaxation feasibility test. A clean feasible result does not prove a
  physical gap; an infeasible status is not a certificate until an independent
  infeasibility-ray/residual replay passes.
- Immediate changed action: audit the single-pass construction opportunity and
  the missing post-solve numerical residual export while both immutable
  baseline jobs continue.
- Source-prepared improvement: the exact isotypic coefficient inventory now
  fingerprints bounded batches of row payloads through an incremental SHA-256
  context. It preserves the byte framing and coefficient hash while removing
  the all-entries `Vector{String}` and whole-stream `IOBuffer`. Julia syntax and
  a direct old-vs-streaming UTF-8 framing check pass locally. The full L=1
  structural pipeline also passes locally in 225.425 s for its coefficient
  stage: 7,231 moments, 75,967 PSD entries, and the unchanged regression hash
  `2a6753a6ea7c57fa43bd33e09339046206fae5217ac3ae47c0cf9cc3b2dc2679`.
- xH5 baseline job `23011251` entered `RUNNING` at 2026-07-29T14:49:17Z from
  its immutable older commit `2de1678`; it is in the same first coefficient
  pass as SCNet. Both baseline jobs remain untouched.
- Source-prepared audit change: direct solves now export every primal moment by
  exact Float64 bits, reconstruct and diagonalize every named real PSD block,
  measure normalization/equality/PSD residuals, and classify results as
  residual-checked feasible, infeasibility-candidate-needing-ray-replay, or
  unknown. A standalone synthetic Mosek regression is included; its remote
  Slurm run is the next software gate.
- Synthetic audit test r1, SCNet job `118172524`, failed before model creation:
  the top-level audit script had not imported `LinearAlgebra`, so `Symmetric`
  was undefined. This is an entry-point import error, not a solver or
  mathematical result. The shared build entry now imports `LinearAlgebra`;
  r2 will test that changed source once.

No user input or new credential is currently required.
