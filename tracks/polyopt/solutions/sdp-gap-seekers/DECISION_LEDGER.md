# Challenge 88 decision ledger

## 2026-07-29 — preserve the exact finite relaxation

The supplied rational congruence, V4 character decomposition, and exact gap
facial reduction are treated as an equivalence transformation. No constraints,
moments, blocks, state classes, or basis words may be dropped for memory.

## 2026-07-29 — immutable input allowlist

The solver accepts only the supplied gamma=0 and gamma=1/2 MOF/runmeta pairs.
It checks the external `SHA256SUMS`, hard-coded pair hashes, all runmeta setup
and reduction fields, every recorded source-file hash, and the named cone
inventory after MOF reload.

## 2026-07-29 — numerical claim rule

A feasible solver status is promoted only to
`feasible_residual_checked_float` after normalization, all affine equalities,
and all 11 reconstructed Hermitian PSD blocks pass a declared scale-aware
`1e-7` audit. An infeasibility status remains only
`infeasibility_candidate_requires_independent_ray_replay`.

## 2026-07-29 — xH5 resource choice

Use `xhacnormalb`, one node, 16 CPUs, 60 GiB, and a two-hour allocation. This
fits xH5's per-CPU memory policy and keeps all operations that may approach or
exceed 1 GiB RSS off login/Bohrium nodes.

## 2026-07-29 — MOF Hermitian packing

Gamma=0 attempt r1 (job `22987967`) showed that MathOptFormat reload preserves
the named `HermitianPositiveSemidefiniteConeTriangle` set and side dimension
but not JuMP's original `HermitianMatrixShape`. The corrected runner validates
the cone set/dimension, then independently rebuilds each matrix from MOI's
real-upper followed by imaginary-strict-upper vector packing. No optimizer was
attached in r1 and no scientific status was produced.

## 2026-07-29 — MosekTools raw attributes

Gamma=0 attempt r2 (job `22987979`) passed the immutable-input, source-hash,
setup, count, and named-cone checks. It then stopped before `optimize!` because
MosekTools 0.15.10 accepts `MSK_IPAR_NUM_THREADS` through MOI's string-valued
raw optimizer attribute, not the Mosek.jl enum used by the older Square
runner. The Shastry runner now uses the supported raw attribute API.
