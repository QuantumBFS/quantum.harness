# Advisor report: Square Rung C full-spin experiment result

Date: 2026-07-29

Experiment branch: `experiment/square-spin-isotypic-scnet2`

Base integration head: `e652894`

Builder/solver commit: `e7c83b2`

Exact-witness replay commit: `7064ad0`

Decision: **the symmetry port succeeds computationally, but Rung C remains
too weak scientifically through gamma 2**

## Bottom line

The integrated Shastry full-spin-isotypic pipeline transfers exactly to the
Square J1--J2 Rung C model.

Every model-dependent exact gate passed on the actual Square coefficients:

- global spin Hamiltonian invariance;
- 31,810 order-two spin-axis coefficient covariance checks;
- 190,860 full spin-permutation coefficient covariance checks;
- conjugation inventory closure;
- equality-space invariance;
- 8,460 spin-axis cross-entry zeros;
- 6,643 redundant-cone congruence entries;
- 3,240 stable-character cross-entry zeros;
- 7,848 trivial/standard isotypic cross-entry zeros;
- 1,332 exact `W=3M` isotypic relations;
- full ranks of all retained row bases;
- deterministic exact coefficient assemblies; and
- optimizer-free JuMP construction followed by independent MOF reload.

The resulting Square Rung C model has:

```text
source moments                         74,602
reduced moment variables                3,250
real PSD cones                              9
positive cone sides        36,36,36,45,37,36,36,45
gap cone side                                1
packed real PSD entries                  6,104
maximum PSD side                            45
MOF size                           about 1.87 MB
```

This is easily runnable on scnet2. The complete build, truth-gate, reload,
solve, and audit flow used under 1.3 GiB process peak RSS. The previous
D4-only screening estimate of 295--347 GiB is therefore no longer the
relevant resource model.

However, the exact-reduced finite relaxation is feasible at gamma `2`.
An exact rational replay proves this with a common denominator of `10^6` and
strictly positive exact LDL pivots in all nine PSD blocks.

Therefore:

> Square Rung C is now computationally solved, but it produces no finite-level
> upper bound at or below gamma 2. More symmetry can make the representation
> still smaller, but cannot change this feasibility conclusion.

## Scope and physical setup

The passing jobs use:

```text
model                    square-j1-j2
J1                       1
g = J2/J1                1/2
patch                    Lambda_1 = {-1,0,1}^2
inner window             central site
degree d                 2
basis                    one_symbol_lift/v1
state class              unrestricted finite relaxation
physical boundary        none; local consistency window
```

The positive `one_symbol_lift/v1` family is the declared finite Rung C
relaxation, not a complete infinite hierarchy. The result concerns this
finite relaxation only.

## Implementation

The experiment adds Square-specific versions of the already-audited Shastry
entry points:

- `scripts/build_square_full_spin_isotypic_reduced_mof.jl`;
- `scripts/solve_square_full_spin_isotypic_reduced_mof.jl`;
- `scripts/square_full_spin_isotypic_gamma_scan_scnet2.sbatch`;
- `scripts/replay_square_isotypic_rational_witness.jl`; and
- `scripts/square_isotypic_rational_witness_scnet2.sbatch`.

The mathematical reduction modules were not changed. The builder changes the
source problem to `square_j1j2_model(1//2)` and records Square-specific
schemas, setup metadata, source files, and hashes. The solver is dynamic-input
only and refuses to run without `SQUARE_SCAN_DYNAMIC_INPUT=1`; this prevents
accidentally accepting the old immutable Shastry inputs.

All work was performed from a clean isolated clone. The worker's integration
branch and dirty local advisor notes were not modified.

## Exact reduction inventory

The regenerated Square counts exactly match the predicted common
patch/basis/action counts:

| Stage | Moments | Positive block sides | Gap sides | Packed real PSD entries |
|---|---:|---|---|---:|
| Source | 74,602 | `703` | `7` | source form |
| V4 spin + facial | 19,108 | `108,81,81,81,109,81,81,81` | `1,1,1` | pre-realification |
| Conjugation-real | 16,660 | same | `1,1,1` | 31,810 |
| Spin-axis involution | 8,803 | `72,36,81,36,45,73,36,81,36,45` | `1,1` | 16,707 |
| Full spin quotient | 3,250 | same | `1,1` | 16,707 |
| Cone redundancy | 3,250 | `72,36,36,45,73,36,36,45` | `1` | 10,064 |
| Trivial isotypic | 3,250 | `36,36,36,45,37,36,36,45` | `1` | 6,104 |

The final exact Square isotypic assembly hashes depend on gamma, as expected.
At gamma `2` they are:

```text
assembly_sha256
    73b4eaa3f2496d5fb4cb4402635079d8f00e17230e3a279e4bcc34e01d3979de

coefficient_map_sha256
    fe5fec83d6eba8a31769e98e9874a83b0acc469e657394ebd5d2c14d6c09f3e7
```

## Job record

### Environment-only failed attempt

Job `118170937` failed after 28 seconds and before Square source assembly.
The installed Mosek package's generated `deps.jl` still pointed to:

```text
/work/home/iint_sjds/.../libmosek64.so.11.2
```

while the scnet2 library exists at:

```text
/public/home/iint_sjds/.../libmosek64.so.11.2
```

The single generated path was corrected, as already prescribed by
`notes/session-handoff.md`. No repository or mathematical code changed. The
failed job has no scientific interpretation and was not overwritten.

### Gamma zero gate

Job `118171007` completed successfully:

```text
State                 COMPLETED
ExitCode              0:0
Elapsed               00:03:47
Slurm batch MaxRSS    953,396 KiB
build wall            2:46.73
build process HWM     1,041,376 KiB
solver wall           10.785 s
Mosek-reported time   3.122 s
solve process HWM     1,237,604 KiB
status                OPTIMAL
primal/dual status    FEASIBLE_POINT / FEASIBLE_POINT
classification        feasible_residual_checked_float
```

Independent reconstruction found:

```text
normalization residual               0
worst affine residual                 0
worst PSD violation                   0
smallest block eigenvalue             0.13310796202959613
```

The immutable artifacts are bound by:

```text
MOF SHA-256
    847ab1e7bbcee5476f2f8f01eb2ade3283094a3f733dcf37d0c25bdf73b9d84c

runmeta SHA-256
    385b247ed101ad65652888fae1118da698a9a6aa1d8cc1f682dfb5a0cc9ce7da

floating primal table SHA-256
    7dbddd8edca306847760255fa90d0a15fe0391470071e8f4bb8bb4c7d4f9f687
```

### Gamma two decision point

Job `118171150` also completed successfully:

```text
State                 COMPLETED
ExitCode              0:0
Elapsed               00:04:20
Slurm batch MaxRSS    940,088 KiB
build wall            2:50.29
build process HWM     1,023,416 KiB
solver wall           12.300 s
Mosek-reported time   3.801 s
solve process HWM     1,222,236 KiB
status                OPTIMAL
primal/dual status    FEASIBLE_POINT / FEASIBLE_POINT
classification        feasible_residual_checked_float
```

Independent reconstruction found:

```text
normalization residual               0
worst affine residual                 0
worst PSD violation                   0
smallest block eigenvalue             0.01949018704413008
gap scalar                            0.06801361474504297
```

The factor contained about `8.54e6` nonzeros after factorization.

Artifact hashes:

```text
MOF SHA-256
    3310ea7c41b857223fe001e6bb3f9a64c75f187a33788585accbb10091055e68

runmeta SHA-256
    9085804ef2c2eaf836095f9df43b83e0cc5bc3feed2a6e1b87da7748b42fee7e

solve result SHA-256
    602975f64379a77b1c098eb20620f07051bd0c9bc56df82d7e5057a4b2f5044e

floating primal table SHA-256
    5b4a9c8b93fc51d0033997e82404809b09136f0804ae3d987f48d2bcae3a43e2
```

No intermediate gamma scan is required after this result.

## Exact rational gamma-two witness

Job `118171424` rebuilt the complete exact gamma-two assembly from source,
checked every recorded assembly/coefficient hash, rounded all 3,250 moment
coordinates to common denominator `10^6`, and reconstructed all 6,104 matrix
entries over exact rationals.

It then performed no-pivot rational LDL on all nine PSD matrices. Every one of
the `308` total pivots was strictly positive:

```text
8 positive blocks:
    36 + 36 + 36 + 45 + 37 + 36 + 36 + 45 = 307 pivots

1 gap block:
    1 pivot
```

The exact gap pivot is:

```text
4251 / 62500 = 0.068016
```

Job record:

```text
State                 COMPLETED
ExitCode              0:0
Elapsed               00:01:36
Slurm batch MaxRSS    638,524 KiB
process wall          1:31.42
process HWM           722,868 KiB
exact replay wall     47.530 s
denominator           1,000,000
```

Certificate hashes:

```text
exact replay SHA-256
    41b2ae3e761ce7a6e2b8c015d43d1e8af4098e61dad48a4b3658d2a2232e840a

rational witness SHA-256
    1c9106f4ea27aefcfc3eefb037350baa62745e79254d48115186003238455089
```

This proves an exact strictly feasible point for the declared finite
relaxation at gamma `2`. It does **not** prove that the physical bulk gap is
at least `2`.

## Why gamma two settles the interval below it

For a fixed functional, the gap block has the exact form

```text
G(gamma) = E - gamma C,
```

where `C` is the centered covariance matrix constrained PSD by the positive
part of the same relaxation.

For `0 <= gamma_1 <= gamma_2`,

```text
G(gamma_1)
    = G(gamma_2) + (gamma_2 - gamma_1) C.
```

If `G(gamma_2)` and `C` are PSD, then `G(gamma_1)` is PSD. All other
constraints are gamma-independent. Therefore the exact witness at gamma `2`
is also an exact witness of nonemptiness for every gamma in `[0,2]`.

The conclusion is stronger than a sparse numerical scan:

> This finite Rung C relaxation cannot exclude any candidate gap in
> `0 <= gamma <= 2`.

## Scientific interpretation

The result separates two questions cleanly:

1. **Can the previously intractable Square Rung C computation be run?**

   Yes. Global spin symmetry reduces it by enough that complete exact
   builds and solves take minutes and about one GiB.

2. **Does this stronger finite relaxation produce a useful Square J1--J2
   gap upper bound?**

   No, not through gamma `2`. It is exactly strictly feasible there.

The symmetry reduction is itself a valuable computational result and makes
the Rung C negative conclusion rigorous. But symmetry averaging is an exact
reparameterization; adding spatial reflection or full D4 after spin cannot
turn this feasible relaxation into an infeasible one.

## Recommendation

Stop Square gamma scans here.

- Do not run gamma `1/2`, `1`, or other points below `2`; exact monotonicity
  already covers them.
- Do not add the anti-diagonal reflection merely to repeat the same
  feasibility decision more cheaply.
- Do not combine full spatial D4 with spin before the deadline; it improves
  representation size, not relaxation strength.
- Do not probe gamma above `2` for a nominal transition. Such a bound would
  not be competitive or physically informative for the intended model.

Use the remaining time to integrate and report:

1. fetch `experiment/square-spin-isotypic-scnet2` from the `scnet2` remote;
2. review/cherry-pick `e7c83b2` and `7064ad0`, or merge the experiment branch;
3. retain the Square builder, solver, and exact replay;
4. decide whether the scnet2-specific Slurm wrappers belong in the final PR
   or only in reproducibility notes;
5. incorporate the compact evidence bundle under
   `evidence/square-spin-rungc-isotypic-20260729/`;
6. update the README/result table with the exact gamma-two negative result;
7. describe the claim precisely as exact feasibility of the finite
   relaxation, not a physical-gap lower bound.

If the team wants a future positive scientific result, it requires a
genuinely stronger relaxation: a larger/different positive basis, higher
degree, a larger local consistency window, or additional valid physical
constraints. More symmetry alone cannot provide it.
