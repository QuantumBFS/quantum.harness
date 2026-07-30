# Shastry–Sutherland compute status — 2026-07-30

This note separates verified artifacts from scheduler state and failed routes.
The target setup in this batch is the unrestricted infinite-system
Shastry–Sutherland local-consistency relaxation

`H = Σ_dimer S_i·S_j + g Σ_square-NN S_i·S_j`

at `g = 4/5`, with `d = 2`. The active feasibility tests use `γ = 2`.

## Verified local result: L=1 native primal truth gate

SCNet job `118173485` completed in 8:27 with exit code zero and
18,936,840 KiB peak RSS. It used source commit
`568d3579c30240054b9f09a4f66fd0666974a714`.

- Native model: 7,231 scalar moment variables, 23 affine PSD blocks,
  75,967 packed PSD rows, and 233,206 scalar coefficient terms.
- The exact coefficient-map hash
  `2a6753a6ea7c57fa43bd33e09339046206fae5217ac3ae47c0cf9cc3b2dc2679`
  matches the independently assembled reference model.
- MOSEK returned `PRIM_AND_DUAL_FEAS` / `OPTIMAL`.
- Reconstructed maximum affine-conic and equality violations are both zero.
- Native task construction took 28.76 s. MOSEK took 403.87 s, including
  118.89 s factor setup and eight interior-point iterations.
- Factorization grew from `2.23×10^8` to `3.91×10^8` nonzeros and cost an
  estimated `2.40×10^12` flops.

This is a verified feasible point of the finite `L=1,d=2,γ=2` relaxation. It
validates the native solver path, but it is not a positive bulk-gap
certificate and is not a physical gap value.

Fetched artifacts:

- `results/ss-native-primal-l1-g0p8-gamma2-scnet-118173485/runmeta.toml`
- `results/ss-native-primal-l1-g0p8-gamma2-scnet-118173485/slurm-118173485.out`

## Failed local routes

The old JuMP/bridge L=2 direct solve is not usable at the available memory
scale:

- SCNet `118171391`: `OUT_OF_MEMORY` after 2:27:56 at 105,617,508 KiB.
- xH5 `23011251`: `OUT_OF_MEMORY` after 1:48:50 at 234,603,960 KiB.

The following are implementation smoke-test failures rather than physics
results:

- SCNet `118172420`: incompatible first streaming/MOSEK smoke route.
- SCNet `118172483`: on-demand coefficients requested without the structural
  primal mode required by that route.
- SCNet `118172519`: MosekTools direct mode does not accept the attempted
  vector-affine PSD constraint representation.
- SCNet `118172813`: scalar affine equality constant was not moved into its
  equality set.
- xH5 `23012281`: failed version of the same early streaming/MOSEK route.

Each of these failure signatures has been superseded by the native affine-PSD
path verified by job `118173485`.

## Active local L=3 route

xH5 job `23013517` is running the native primal `L=3,d=2,γ=2` path from commit
`568d357` on 128 CPUs with a 480 GB request. At 5:09 elapsed it had reached
positive PSD block 7 while constructing coefficients. Peak RSS was
56,957,224 KiB. It had not entered MOSEK optimization.

The exact structural inventory before coefficient expansion is:

- positive basis dimension: 53,950;
- stationarity rows before exact reduction: 8,400;
- 20 positive PSD blocks plus 6 gap blocks;
- 65,544,123 packed PSD entries;
- largest PSD side: 3,675.

The native coefficient builder has discovered 6,987,373 distinct scalar moment
variables. Therefore the earlier shorthand “53,950 final moments” was
incorrect: 53,950 is the positive-basis dimension, not the final native
moment-variable count. The active run is useful as a measured scale probe, but
its eventual MOSEK factorization is now high risk even if coefficient
construction completes.

Four older SCNet L=3 preflights remain in the exact S3 isotypic cone-blocking
stage and have produced no solver artifact:

- `118170188`, `118170649`, `118170956`, and `118171078`.

They are obsolete implementation comparisons, not independent physics
calculations.

## Remote research-agent result

The remote agent's strongest verified contribution is an exact L=2 structural
reduction, not a numerical bulk-gap result:

- 343,761 moment equations;
- an exact stabilizer split into 38 PSD blocks;
- 2,540,067 packed entries;
- maximum block side 490;
- 16,110,543 scalar coefficient terms;
- coefficient hash
  `b4a9884636dcea65be67e60e6f2ef0dffe23812e1ab8e6bf5205f23f549874e5`.

The exact cross-zero gate `118189871` checked 1,906,425 entries. Build-only job
`118190562` reproduced the split inventory and hash.

The corresponding 500 GB decision solve `118192695` reached MOSEK presolve but
was killed during the first factorization at 509,850,832 KiB, before iteration
zero. Earlier 114 GB, 256 GB, and 500 GB unsplit/reduced attempts failed at the
same factorization boundary. None supplies feasibility, infeasibility, or a
bulk-gap conclusion.

The remote agent is now testing whether some equal-dimensional SO(3) `l=2`
cones are exactly congruent and can therefore be removed without weakening the
relaxation. It is fail-closed:

- L=1 control `118194879` found 14,715 exactly matching projected entries but
  1,107 scalar-sector mismatches.
- Norm-corrected control `118195346` reproduced the same 1,107 mismatches,
  disproving the diagonal row-normalization hypothesis.
- No L=2 cone deletion is authorized by these tests.

The agent then implemented an exact exceptional-sector search at commit
`e81c463e66beef2aa02d9576c1be48ce0b545f70`. It fixes every already-proved
ordinary row, searches only the 3-row and 6-row exceptional scalar sectors,
and requires one complete signed-permutation/rational-scale congruence across
ordinary–exceptional and exceptional–exceptional entries. SCNet truth-only job
`118195948` is running this changed signature on 8 CPUs and 16 GB; it has no
optimizer and cannot delete a cone unless the exact gate passes. The remote
working branch is clean at status commit `63072a3`.

No new credential or user decision is currently required.

## Decision consequence

The native path is correct at L=1, but brute-force L=3 is not presently the
shortest route to a challenge result. The decision-relevant bottleneck is
MOSEK factorization fill, not coefficient generation alone. Work that can
change the outcome is exact cone reduction or a certifiable formulation whose
factorization graph is substantially smaller; merely increasing memory has
already failed at 500 GB for L=2.
