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

## 2026-07-29 — retain the clean-tree gate after build r3

Slurm job `22988216` reached the clean-source check and refused to build
because its own default `slurm-22988216.out` was untracked at the checkout
root. The gate is correct and remains strict. The sbatch wrapper now routes
scheduler stdout into the ignored track-results tree, so generated job logs
cannot masquerade as source dirtiness.

## 2026-07-29 — exact conjugation-reduced MOFs accepted

Slurm job `22988221` completed both clean, solver-free builds and reload
checks. The exact real model has 16,660 moments, zero surviving affine
equalities, and 31,810 real PSD triangle coordinates. This is a 2,448-moment
and 94,715-cone-coordinate reduction relative to the V4 model as presented to
Mosek's generic Hermitian bridge.

The gamma=0 and gamma=1/2 model SHA-256 values are respectively
`0a2c9166eb033a2e782ab91a062491961a5d8139a1b04e80f6f564d1a75a6e14`
and
`b50d66a48a45de0f2a25e411ab3dcc6a06f3a99b06626951277ae09686062707`.
They are immutable derived inputs. The real-cone runner must pass gamma=0
before the gamma=1/2 memory comparison is authorized.

## 2026-07-29 — real-cone gamma=0 truth gate passed

Slurm job `22988279` passed all immutable-input, fixed-setup, exact-reduction,
source-hash, variable-count, constraint-count, and named-real-cone gates
before attaching Mosek. It returned `OPTIMAL` with primal and dual feasible
points. Independent reconstruction gave normalization 1, zero PSD violation,
and minimum eigenvalue 0.09561232145445703.

The solver representation changed the factor from 1.45 billion to 111 million
nonzeros and the run from 46,385,640 KiB / 462.4 s to 5,917,112 KiB /
93.1 s process peak / total wall. This validates the exact realification
numerically at gamma=0 and authorizes the gamma=1/2 run without changing the
physical or relaxation setup.

## 2026-07-29 — real-cone gamma=1/2 passed with a 7.4x RSS reduction

Slurm job `22988295` returned `OPTIMAL` with primal and dual feasible points.
Independent reconstruction gave normalization 1, zero PSD violation, and
minimum eigenvalue 0.07713795086656225. No infeasibility ray is applicable.

Relative to the exact Hermitian-bridge gamma=1/2 run, process peak RSS fell
from 44,494,548 to 6,001,456 KiB, total wall from 425.4 to 97.9 s, and
post-factor nonzeros from 1.51 billion to 112 million. The finite-relaxation
decision is unchanged: gamma=1/2 is feasible, while the exact implementation
now fits comfortably inside a 32 GiB allocation.

## 2026-07-29 — bounded dual-form audit

The automatic real-cone solve selected Mosek's primal form. A forced dual form
is mathematically the same SDP and may change only the Newton factorization.
Test it first at gamma=0 under the same 16-CPU, 32 GiB cap. Continue to
gamma=1/2 only if factor fill or peak RSS improves; otherwise close the route
after the gamma=0 artifact instead of repeating a worse setting.

## 2026-07-29 — close the forced-dual route at gamma=0

Slurm job `22988322` passed all fail-closed gates and recorded the requested
solve form as `dual`, but Mosek reported `Optimizer - solved problem : the
primal`. Its 68.5-million-before / 111-million-after factor nonzero counts and
iterate sequence match the default real-cone gamma=0 run. It returned
`OPTIMAL`, zero audited residual and PSD violation, and minimum eigenvalue
`0.09561232145445703`.

There is no factor-fill improvement to justify a gamma=1/2 repeat. The
process peak was 6,235,104 KiB versus 5,917,112 KiB for the default, and the
preserved `result.toml` SHA-256 is
`b8007b0d9e50338cc770789a8472555b0ce1706f13f13b6e808ed4a11054ae36`.
Close this tuning route and move to an exact model-level involution:
`X↔Z, Y↦−Y`, a π spin rotation that commutes with the already-proved
conjugation symmetry.
