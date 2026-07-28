# Challenge 88 exact-reduction result

## Fixed setup

Shastry--Sutherland spin-1/2 antiferromagnet with dimer coupling 1 and square
nearest-neighbor coupling 4/5; infinite lattice represented by the level-1
local-consistency window; no physical boundary condition; unrestricted KMS
class; polynomial degree `d=2`.

The finite relaxation is the exact reduced model from source commit
`5e84422586c8de8acb58699a1102a28353291562`: 74,602 source moments to 19,108
invariant moments, 11 PSD blocks, maximum side 109. No constraint was dropped.

## Numerical result

| gamma | Slurm job | MOI status | normalization | max affine residual | worst PSD violation | smallest block eigenvalue | solver wall | peak process RSS |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | 22987983 | `OPTIMAL`; primal/dual feasible | 1 | 0 | 0 | 0.0948505094335904 | 444.861 s | 46,385,640 KiB |
| 1/2 | 22988032 | `OPTIMAL`; primal/dual feasible | 1 | 0 | 0 | 0.08943315828795756 | 407.505 s | 44,494,548 KiB |

Both rows pass the declared scale-aware `1e-7` audit after independent
reconstruction of all named Hermitian blocks from the MOI packed cone values.

## Decision

The gamma=0 numerical truth gate passes. At gamma=1/2, the exact `d=2` finite
relaxation is numerically feasible with a strictly interior returned point.
Therefore this relaxation does not exclude a bulk gap of 1/2.

This is not a proof that the physical Shastry--Sutherland model has bulk gap
at least 1/2. Feasibility of a truncated outer relaxation is not a physical
lower-gap certificate. No infeasibility certificate or ray was returned, so
the independent ray-replay branch is inapplicable.

## Preserved artifacts

- Gamma=0:
  `tracks/polyopt/solutions/sdp-gap-seekers/results/ss-reduced-g0p8-gamma0-xh5-20260729-r3/`
  (`result.toml` SHA-256
  `ec362cdf456a7ad7f180ce2418bcea1b547f831c8d0c21cfc827844b2e06258e`).
- Gamma=1/2:
  `tracks/polyopt/solutions/sdp-gap-seekers/results/ss-reduced-g0p8-gamma0p5-xh5-20260729-r1/`
  (`result.toml` SHA-256
  `63c3ed036605c9ed15e67e762115bf73f67b1724b7e6ea6281cf21559b1dc021`).
- Each directory includes `runner.log`, input metadata, final `sacct` output,
  the Slurm log, and a verified `SHA256SUMS` manifest.
- Diagnostic plot:
  `tracks/polyopt/solutions/sdp-gap-seekers/results/challenge88-summary-20260729/psd-min-eigenvalues.png`
  (SHA-256
  `a66cbe63cc03153bbe1d16211f4edb33690eb34f55a2e3b77d13749ae6749e9d`).
- The same paths exist in the isolated xH5 checkout under
  `/work/home/sihhu/quantum-hackson/challenge-88/bohr-agent/ss-exact-reduction/`.

The scientific runner code is commit `40b1f02035413bac724b2eb32156ce199bde84bd`
on branch `bohr/challenge88-ss-reduced-runner`. Gamma=1/2 ran at branch commit
`fb4dd43e757b8b8d4cb97c758215ac21bf447585`, whose only later change was the
gamma=0 state record.

## Exact real-cone implementation result

Computational-basis conjugation is an exact antiunitary symmetry of the fixed
Hamiltonian and finite relaxation. Averaging the unrestricted functional with
its conjugate removes 2,448 conjugation-odd moments. A fixed diagonal phase
then maps every remaining Hermitian block to a real symmetric block without
changing PSD feasibility.

The resulting immutable models have 16,660 moments, zero surviving affine
equalities, and 11 real PSD blocks with the same side dimensions. Mosek sees
31,807 scalarized semidefinite coordinates instead of 126,525.

| gamma | Slurm job | status/audit | minimum block eigenvalue | total wall | peak process RSS | factor nonzeros |
|---|---:|---|---:|---:|---:|---:|
| 0 | 22988279 | `OPTIMAL`; primal/dual feasible; residual audit passed | 0.09561232145445703 | 93.057 s | 5,917,112 KiB | 1.11e8 |
| 1/2 | 22988295 | `OPTIMAL`; primal/dual feasible; residual audit passed | 0.07713795086656225 | 97.869 s | 6,001,456 KiB | 1.12e8 |

For gamma=1/2 this is a 7.4x reduction in process peak RSS and a 4.3x
reduction in total wall relative to the exact Hermitian-bridge solve. The
scientific conclusion is unchanged: the exact `d=2` finite relaxation is
feasible at gamma=1/2 and therefore does not exclude that candidate gap; this
is not a proof of a physical bulk gap.

Additional preserved artifacts:

- Exact conjugation proof and gates:
  `EXACT_CONJUGATION_REDUCTION.md`.
- Gamma=0 real solve:
  `tracks/polyopt/solutions/sdp-gap-seekers/results/ss-conjugation-real-g0p8-gamma0-xh5-20260729-r1/`
  (`result.toml` SHA-256
  `de1b023911579f1952d7585524730c2e77b248997b98d467b9f0c9b58d50dc36`).
- Gamma=1/2 real solve:
  `tracks/polyopt/solutions/sdp-gap-seekers/results/ss-conjugation-real-g0p8-gamma0p5-xh5-20260729-r1/`
  (`result.toml` SHA-256
  `3c5bd696a41a35939df1cd305f52d89be4b6088c5b1cc14590d9223579d6fb38`).
