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

## Exact spin-axis involution result

The global π spin rotation about `(x+z)/sqrt(2)` acts as
`X↔Z, Y↦−Y` and commutes with the conjugation realification. Exact averaging
reduces 16,660 real moments to 8,803. It splits the stable V4 blocks into
involution eigenspaces and retains one representative of each exchanged X--Z
block pair. The resulting equivalent model has 12 real PSD blocks, maximum
side 81, and 16,707 packed triangle entries.

| gamma | Slurm job | status/audit | minimum block eigenvalue | total wall | peak process RSS | factor nonzeros |
|---|---:|---|---:|---:|---:|---:|
| 0 | 22988457 | `OPTIMAL`; primal/dual feasible; residual audit passed | 0.11159895759531112 | 40.568 s | 2,602,300 KiB | 4.14e7 |
| 1/2 | 22988479 | `OPTIMAL`; primal/dual feasible; residual audit passed | 0.07937511269712764 | 38.496 s | 2,449,480 KiB | 4.12e7 |

For gamma=1/2 this is an 18.2x reduction in process peak RSS and an 11.1x
reduction in total wall relative to the original exact Hermitian-bridge solve.
It is also a 2.45x RSS and 2.54x total-wall reduction relative to the
conjugation-only real model. The exact finite-relaxation decision is
unchanged: gamma=1/2 is feasible and therefore not excluded by this `d=2`
outer relaxation. This is not a proof of a physical bulk gap.

Additional preserved artifacts:

- Exact spin-axis proof:
  `EXACT_SPIN_AXIS_INVOLUTION.md`.
- Passing exact truth gate:
  `tracks/polyopt/solutions/sdp-gap-seekers/results/ss-spin-axis-truth-xh5-20260729-r2/`
  (`test.log` SHA-256
  `f286d48a89b462b11dfbd199d22339e403b167c0672b2ac34c76ed816b39d66d`).
- Gamma=0 spin-axis solve:
  `tracks/polyopt/solutions/sdp-gap-seekers/results/ss-spin-axis-real-g0p8-gamma0-xh5-20260729-r1/`
  (`result.toml` SHA-256
  `68d145b91ba34bec17d3c5ca5088a5a8419ee37caaaa39b60e68ab5e9d66465c`).
- Gamma=1/2 spin-axis solve:
  `tracks/polyopt/solutions/sdp-gap-seekers/results/ss-spin-axis-real-g0p8-gamma0p5-xh5-20260729-r1/`
  (`result.toml` SHA-256
  `63e1f7bcc6d6bde6d9de84e226aac448941e1d1b3680e2db0364a0665f2fe50b`).
- Immutable gamma=0 and gamma=1/2 input model SHA-256 values are
  `9b9519a2059e718651af52a7b98e75dc046eab57be33ca3ea9d2325ba28d7fb2`
  and
  `f12eaa63e64d8643e4b361d245669d013bdf853d83bda8c35499e8f42dbde485`.

## Exact full spin-permutation result

The full six-element spin-axis permutation group further reduces the
conjugation-real moment inventory to 3,250 exact orbit variables while
retaining all 12 already-proved spin-axis PSD cones. Exhaustive truth gates
checked all 190,860 source coefficient covariance identities before the
conjugation phase gauge.

| gamma | Slurm job | status/audit | minimum block eigenvalue | total wall | peak process RSS | factor nonzeros |
|---|---:|---|---:|---:|---:|---:|
| 0 | 22988532 | `OPTIMAL`; primal/dual feasible; residual audit passed | 0.13079207445451374 | 43.098 s | 2,750,960 KiB | 6.07e7 |
| 1/2 | 22988534 | `OPTIMAL`; primal/dual feasible; residual audit passed | 0.09503337763320019 | 37.017 s | 2,736,824 KiB | 6.03e7 |

This exact quotient preserves the gamma=1/2 feasibility decision. It is 3.8%
faster but uses 11.7% more process RSS than the spin-axis model at gamma=1/2,
so the 8,803-variable spin-axis representation remains the measured
memory-best form. The result identifies cone-row elimination, rather than
scalar moment count alone, as the next exact memory target.

Additional preserved artifacts:

- Full spin-permutation proof:
  `EXACT_FULL_SPIN_PERMUTATION.md`.
- Passing model truth gate:
  `tracks/polyopt/solutions/sdp-gap-seekers/results/ss-full-spin-truth-xh5-20260729-r2/`
  (`test.log` SHA-256
  `9ef5f74de8b184d44233c2744f32a9977948c89f8f5bee5210d161cc0f67eae2`).
- Gamma=0 solve:
  `tracks/polyopt/solutions/sdp-gap-seekers/results/ss-full-spin-g0p8-gamma0-solve-xh5-20260729-r1/`
  (`result.toml` SHA-256
  `365bef5ca2bae523fdc4903650bcf4cbbfd3c53a7b54a015dcc7b9a2b0dc542c`).
- Gamma=1/2 solve:
  `tracks/polyopt/solutions/sdp-gap-seekers/results/ss-full-spin-g0p8-gamma0p5-solve-xh5-20260729-r1/`
  (`result.toml` SHA-256
  `d19b811d37dcbc6229351d1642afe6cc197f072bf5c8e862a5a4989a282ff5d3`).
- Immutable gamma=0 and gamma=1/2 model SHA-256 values are
  `4f62a5e16822d2df174af8d9013bb1622c54d8c47bd2f78a59a086524ad4d67f`
  and
  `e47bf0d3146ada223bbb389920ea4ca1f79efef467ee7a81ef72d42741652e9f`.

## Exact nontrivial-character cone reduction result

Full spin invariance makes the three nontrivial V4 character cones one orbit.
Exact phase-corrected congruence replay removes two redundant 81-side
positive cones and one redundant gap scalar. The equivalent model has 3,250
moments, nine real PSD cones, 10,064 packed triangle entries, and maximum
side 73.

| gamma | Slurm job | status/audit | minimum block eigenvalue | total wall | peak process RSS | factor nonzeros |
|---|---:|---|---:|---:|---:|---:|
| 0 | 22988753 | `OPTIMAL`; primal/dual feasible; residual audit passed | 0.1252658219892882 | 27.593 s | 1,699,824 KiB | 2.63e7 |
| 1/2 | 22988816 | `OPTIMAL`; primal/dual feasible; residual audit passed | 0.09098861640180578 | 34.586 s | 1,666,944 KiB | 2.64e7 |

At gamma=1/2 this cuts process RSS by 32.0% and factor fill by 35.9%
relative to the spin-axis representation. It is 26.7x smaller in process RSS
and 12.3x faster in total wall than the original Hermitian-bridge solve. The
exact finite-relaxation decision remains feasible; this is not a physical
bulk-gap proof.

Additional preserved artifacts:

- Exact cone-redundancy proof:
  `EXACT_FULL_SPIN_CONE_REDUCTION.md`.
- Gamma=0 solve:
  `tracks/polyopt/solutions/sdp-gap-seekers/results/ss-full-spin-cone-real-g0p8-gamma0-solve-xh5-20260729-r1/`
  (`result.toml` SHA-256
  `f3b394aff863243aee7706f7c52f728ca303df043429e7c70245e6d79ce2e3a0`).
- Gamma=1/2 solve:
  `tracks/polyopt/solutions/sdp-gap-seekers/results/ss-full-spin-cone-real-g0p8-gamma0p5-solve-xh5-20260729-r1/`
  (`result.toml` SHA-256
  `f24c297da06061b08aa9e94e83f401967cb055e89620bb9eceb834425c16e031`).
- Immutable gamma=0 and gamma=1/2 model SHA-256 values are
  `a34c629a502b515fc615467bc876f691c0494d523c32f4e1dc5323d84b235d26`
  and
  `ce3f4030afdc19d90b0f3a1bd2e8a2d6f3f06c19aad6c61e3b0bbbfe68de17a9`.

## Exact full-spin isotypic result

The remaining trivial-character blocks contain one S3-trivial component and
two equivalent copies of the S3-standard component. Exact integer
isotypic bases remove one standard copy without changing the finite
relaxation. The resulting representation has 3,250 moments, nine real PSD
cones, 6,104 packed triangle entries, and maximum side 45.

| gamma | Slurm job | status/audit | minimum block eigenvalue | solver wall | peak process RSS |
|---|---:|---|---:|---:|---:|
| 0 | 22988910 | `OPTIMAL`; primal/dual feasible; residual audit passed | 0.11113568782699743 | 6.624 s | 1,016,136 KiB |
| 1/2 | 22988996 | `OPTIMAL`; primal/dual feasible; residual audit passed | 0.08228797924548609 | 7.804 s | 1,138,120 KiB |

For gamma=1/2 this exact representation reduces process peak RSS by 39.1x
and solver wall by 52.2x relative to the original Hermitian bridge. The
result SHA-256 is
`84ef32c708b7d26871b868faf9afdc0ef75a06d9cb8f929f79d98909407d158a`.
All 3,250 primal values were exported by exact IEEE-754 bit pattern under
SHA-256
`8ccbb186f7c0b66e2dafa5d0e28782757b88afadba4982f1532dbb4ca77ff1be`
for a separate exact rational positive-definiteness replay.

The scientific decision remains limited but now inexpensive to reproduce:
the exact `d=2` finite relaxation is feasible at gamma=1/2 and therefore does
not exclude that candidate gap. This is not a proof of the physical bulk
gap.

The separate solver-free replay strengthens the numerical statement. Slurm
job `22991012` rounded all 3,250 moments to common denominator `10^6`,
reconstructed all 6,104 entries over exact rationals, and proved strictly
positive no-pivot LDL pivots in all nine PSD blocks. The exact replay and
rational witness SHA-256 values are
`a6f37449f4902b5eda13935f19fe46339f79a32994d7f0a6b837320dab5c7088`
and
`ce50fa42e1a86b8d165139d350faf367a7138950c636dc9ca6d7ae04695b5978`.
This is an exact strictly feasible witness for the finite relaxation, not a
lower bound on the physical bulk gap.

Additional preserved artifacts:

- Exact isotypic proof:
  `EXACT_FULL_SPIN_ISOTYPIC_REDUCTION.md`.
- Gamma=0 input/solve:
  `results/ss-full-spin-isotypic-real-g0p8-gamma0-builder-20260729-r1/`
  and
  `results/ss-full-spin-isotypic-real-g0p8-gamma0-solve-xh5-20260729-r1/`.
- Gamma=1/2 input/solve:
  `results/ss-full-spin-isotypic-real-g0p8-gamma0p5-builder-20260729-r1/`
  and
  `results/ss-full-spin-isotypic-real-g0p8-gamma0p5-solve-xh5-20260729-r1/`.
- Exact gamma=1/2 rational witness:
  `results/ss-full-spin-isotypic-rational-witness-xh5-20260729-r3/`.
