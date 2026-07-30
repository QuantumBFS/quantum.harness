# Autoresearch State

- stage: run
- topic: finite-abelian-nc-moment-sdp
- batch_size: 10
- time_limit_seconds: 8
- authorized_attempts: 0
- next_attempt: 1
- next_cycle: 1
- gates:
  - survey_gate: passed 2026-07-28
  - validator_gate: passed 2026-07-28
  - precursor_gate: passed 2026-07-28 (finite-dimensional invariant-Hermitian character decomposition only)
  - abelian_nc_moment_gate: passed 2026-07-28 (independent Julia order-1/2 affine moment SDP; Z2 and Z2xZ2 dense/reduced Mosek equivalence)
  - issue_229_gate: partial (finite Abelian sign actions completed; general issue scope, including non-Abelian/permutation/SU(2), is not claimed)
- solver_env: Julia + JuMP + MosekTools/Mosek; NCTSSoS installed but not used by the independent builder
- precursor_report: docs/discussion/issue-229-final.html
- moment_sdp_runner: research/nc_moment_sdp/run.jl
- overrides: 2026-07-28 scope narrowed with user approval to finite Abelian symmetry; permutation and SU(2) are deferred. The numerical-matrix character decomposition remains a precursor. The completed finite-Abelian NC milestone constructs normalized NC words and the affine moment pencil, lifts Z2^k sign characters, keeps every real moment free in the original dense hierarchy, and applies group-average zeros only in the reduced character-block hierarchy; deterministic order-1/2 instances verify their equivalent optima.
