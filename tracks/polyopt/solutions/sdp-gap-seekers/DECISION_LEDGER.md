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

## 2026-07-29 — gamma=0 truth gate passed

Attempt r3 (job `22987983`, runner commit `40b1f02`) returned Mosek
`OPTIMAL` with primal and dual feasible points. Independent reconstruction
gave normalization 1 exactly, three zero affine residuals, zero PSD violation,
and a smallest block eigenvalue of 0.0948505094335904. The gamma=1/2 solve is
therefore unblocked without changing the Hamiltonian, window, state class,
degree, reduction, solver settings, or audit tolerance.

## 2026-07-29 — gamma=1/2 is feasible in the exact finite relaxation

Gamma=1/2 attempt r1 (job `22988032`) returned Mosek `OPTIMAL` with primal and
dual feasible points. Independent reconstruction gave normalization 1, zero
affine residual, zero PSD violation, and smallest block eigenvalue
0.08943315828795756. The decision-grade conclusion is numerical feasibility
of the exact `d=2` finite relaxation at gamma=1/2. It is not a certified
physical lower bound on the bulk gap.

No infeasibility ray replay is needed because the solver did not report
infeasibility.

## 2026-07-29 — reopen exact memory reduction after bridge diagnosis

The continuation objective requires pursuing the Challenge 88 result beyond
the wrapper milestone. The Mosek log shows that MOI's generic Hermitian bridge
turns the eight positive blocks into 126,525 scalarized semidefinite
coordinates and a 1.45--1.51-billion-nonzero factor. That makes an exact
representation reduction decision-relevant even though both fixed-gamma
solves fit the original 60 GiB allocation.

The highest-value route is computational-basis conjugation averaging. The
fixed Hamiltonian is invariant; averaging preserves unrestricted
feasibility, removes conjugation-odd moments, and a fixed diagonal unitary
gauge makes every remaining block real symmetric. The predicted positive-cone
coordinate count is 31,807. This route must pass exhaustive exact coefficient
and equality-space tests under Slurm before any derived MOF is generated or
solved.

## 2026-07-29 — conjugation truth gate passed; full-suite tail dropped

Slurm job `22988127` passed all 58 assertions in the exact M/K/V4 testset,
including the exhaustive 31,810-entry coefficient gate, in 102.2 s. The same
wrapper then spent more than ten minutes in an unrelated dense-ED oracle.
Because that tail cannot change the conjugation theorem, the job was canceled
at 12:34 and the passed test log was preserved. Subsequent jobs target only
the exact reduction build/reload path instead of repeating the bottleneck.

## 2026-07-29 — derived-MOF build r1 stopped before assembly

Slurm job `22988179` stopped during Julia macro expansion: a line break left
`@timed` without its expression. No source assembly, model, MOF, or solve ran.
The next attempt moves the macro argument into the same expression and first
loads the complete script through its `--help` path.

## 2026-07-29 — derived-MOF build r2 exposed xH5 Git compatibility

Slurm job `22988194` passed Julia macro expansion and stopped in source
provenance collection before assembly. The xH5 Git version does not implement
`branch --show-current`. The builder now uses the portable plumbing command
`symbolic-ref --short HEAD`; no model or MOF was emitted by r2.
