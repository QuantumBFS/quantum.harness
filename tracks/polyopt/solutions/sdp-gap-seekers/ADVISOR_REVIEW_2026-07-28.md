# Advisor review — correctness audit and recommended next work

**Date:** 2026-07-28  
**Reviewed branch:** `challenge/polyopt-sdp-gap`  
**Primary input:** `SESSION_STATUS_2026-07-28.md`  
**Purpose:** handoff to the worker agent responsible for the next implementation
session.

> This was a static audit only. I read the notes, committed scripts, local
> `SpectralGap.jl` source, and locally installed `QMBCertify` source. I did not
> execute Julia/Python calculations, tests, or SDP solves.

## Executive assessment

The project has a sound mathematical starting point and a useful solver-free
Square J1-J2 foundation. The historical TFIM and Kagome transition values are
plausible and consistent with the upstream examples. However, the current
status summary materially overstates what has been established:

1. **Neither reported gap value is presently a certified upper bound.** They are
   numerical flag-transition candidates. The current certificate extractor
   reads the wrong side of the conic model.
2. **The claimed `d`-convergence is not convergence.** For the tested values,
   the basis builders stop changing, so the compared SDPs are identical by
   construction.
3. **The `rdm=16` energy experiment is invalid as an RDM-strengthening probe.**
   QMBCertify supports only `rdm=8,9,10`; `rdm=16` adds no RDM constraint.
4. **The frozen reproduction path is broken in the current checkout.** The
   scripts and patch disagree about return types and dependencies, raw results
   are not committed, and the provenance document describes an older patch.
5. **Kagome is a calibration, not the main challenge target.** Challenge #88
   explicitly asks for extensions to Square J1-J2, Shastry-Sutherland, and then
   triangular J1-J2. Reproducing the bundled Kagome example has low novelty.
6. **Some physical and symmetry statements are wrong.** In particular, the
   square-lattice Heisenberg model at `g=0` is gapless, and the Kagome reduction
   does not implement Square translations/C4/mirrors or a full SU(2) irrep
   quotient.

The recommended headline is:

> Build an auditable certificate path for the state-polynomial gap hierarchy,
> validate it on TFIM, and use it in a new Square J1-J2 adapter. Keep Kagome as a
> legacy-pipeline regression test.

## Reliability map

| Component or claim | Assessment | Reason |
|---|---|---|
| Bulk-gap logical direction and covariance term | **Reliable** | The authoritative SPEC correctly distinguishes finite-relaxation feasibility from physical gap statements and uses the state covariance. |
| Square patch geometry and J1/J2 Hamiltonian enumeration | **Reliable within reviewed scope** | Counts, spin normalization, and one-layer interaction buffer are internally consistent and solver-free tests cover them. |
| TFIM transition near `0.26` | **Plausible numerical reproduction** | The historical flag scan is consistent with the legacy pipeline, but lacks a validated exclusion witness and frozen raw output. |
| Kagome N=13 transition near `1.28` | **Plausible numerical reproduction** | It agrees with the bundled upstream example, but is not yet an auditable certificate or a novel result. |
| Kagome `d=3 = d=4` convergence | **Incorrect interpretation** | The basis and bulk-basis builders are identical at those two inputs. |
| Energy `d=4 = d=6 = d=8` convergence | **Incorrect interpretation** | QMBCertify's basis builder has no additional branch beyond `d>3`. |
| Energy `rdm=16` probe | **Invalid experiment** | `rdm=16` is unsupported and silently receives no RDM PSD constraint after a warning. |
| “Two certified gap upper bounds” | **Unsupported** | No complete witness has been extracted and independently validated. |
| “Energy-cert floor complete and certified” | **Overstated** | The scripts store objective values but not sufficient solver status, residual, or certificate evidence; the declared Shastry-Sutherland deliverable is also unfinished. |
| Current source/provenance reproducibility | **Broken** | Patch, package dependency, hashes, scripts, and stored outputs do not describe one consistent executable state. |
| PR #3 structured basis | **Not assessable from this checkout** | The current branch contains counts but no `basis_manifest(problem, role)` implementation. |

## P0 finding: the attempted §8 witness extraction uses the wrong conic side

### What the current code actually solves

The sign-symmetric TFIM and Kagome routines build PSD Gram variables, free
stationarity multipliers, and a scalar `λ`, then impose a homogeneous
coefficient identity:

```julia
@variable(model, λ)
cons[1] += λ
@objective(model, Max, λ)
@constraint(model, cons .== 0)
```

See `.external/SpectralGap/src/sdp.jl`, especially the TFIM block around
lines 134–178 and the Kagome block around lines 503–520.

This is an SOS-side conic optimization problem, not the direct primal
moment-feasibility problem described in SPEC §8. Its intended behavior is:

- at a relaxation-feasible `γ`, the homogeneous SOS problem is bounded, normally
  with optimum `λ=0`;
- if the corresponding moment problem is inconsistent, an SOS identity with
  `λ>0` can be scaled, making this SOS problem unbounded;
- a primal improving ray of this SOS problem is therefore the object that can
  prove the opposite moment problem infeasible.

### Correct MathOptInterface interpretation

MathOptInterface defines:

- `primal_status == INFEASIBILITY_CERTIFICATE` as an improving ray of the
  **primal JuMP model**;
- the ray is available through variable primal values;
- `dual_status == NO_SOLUTION` is expected when the solver has produced only a
  primal ray proving dual infeasibility/unboundedness.

Official reference:

<https://jump.dev/MathOptInterface.jl/stable/background/infeasibility_certificates/>

Therefore the current observation

```text
primal_status = INFEASIBILITY_CERTIFICATE
dual_status   = NO_SOLUTION
```

does not mean “Mosek has a primal-infeasibility witness that JuMP failed to
expose through `dual()`.” It means the likely certificate data are on the
variable-primal side, while the current code requests equality-constraint
duals from the unavailable side.

This explains why:

```julia
dual_var = -dual.(con_eq)
```

produces missing or degenerate data.

### Why the current `farkas_mmat` is not a complete certificate

Even if `dual(con_eq)` returned nonzero values, the present reconstruction:

- includes only matrices derived from the ordinary positivity basis;
- does not preserve or validate the gap Gram blocks;
- does not preserve the free stationarity multipliers;
- does not validate the complete coefficient identity;
- does not establish a positive normalized `λ`;
- is based on the wrong result side for the observed solver status.

Checking only “the reconstructed moment matrices are PSD” cannot prove the
required infeasibility statement.

### Effect of `termination = SLOW_PROGRESS`

The raw tuple reportedly contains:

```text
termination = SLOW_PROGRESS
primal_status = INFEASIBILITY_CERTIFICATE
dual_status = NO_SOLUTION
```

The canonical MOI outcome for a proved primal improving ray would normally have
`termination = DUAL_INFEASIBLE`. `SLOW_PROGRESS` means the overall solver
termination remains numerically ambiguous. The returned ray may still be useful,
but it must be treated as a candidate and validated independently before it
changes the scientific conclusion.

Thus:

- **acceptable hackathon wording now:** “numerical flag-transition candidate”;
- **not acceptable now:** “certified upper bound”;
- **promotion condition:** the extracted ray passes an independent affine and
  cone-membership audit, ideally with rational or interval post-processing.

### Recommended certificate implementation

Refactor the certifier so it retains named references to every conic variable:

```text
positive_blocks
gap_blocks
stationarity_multipliers
lambda
coefficient_rows / exact affine map
support ordering
basis manifest and hash
```

On a candidate ray:

1. Require `result_count(model) >= 1`.
2. Record raw termination, primal, and dual statuses without collapsing them.
3. Read `value.(...)` for all primal variables from the certificate result.
4. Require the ray objective direction to be positive:

   ```text
   λ_ray > 0
   ```

5. Normalize all ray components by `λ_ray`, giving `λ=1`.
6. Serialize the normalized certificate separately from the solver model.
7. In a solver-independent verifier:

   - reconstruct every affine coefficient row;
   - check the normalized identity residual;
   - check every positive Gram block is PSD;
   - check every gap Gram block is PSD;
   - account for all free stationarity multipliers;
   - reject NaN/Inf/missing values;
   - report scale-aware residuals, not only absolute residuals.

8. For strict certification, use rational reconstruction or outward-rounded
   interval bounds. TFIM N=9,d=2 is the correct first target because the
   certificate is comparatively small.

Mosek's automatic infeasibility report can help diagnose a model, but it is not
the first extraction route to pursue here. The observed MOI status already
indicates that variable primal values are the relevant candidate ray.

## P0 finding: the `d`-convergence conclusions are artifacts

### Kagome gap basis

In `.external/SpectralGap/src/basicfunction.jl`:

- `get_kagome_basis(...)` adds triangle words only when `d > 2`;
- it contains no further `d > 3` or higher-order branch;
- `get_kagome_bulkbasis(...)` adds its larger content when `d > 1`;
- it also contains no higher-order branch.

The certifier calls:

```julia
basis  = get_kagome_basis(..., d)
gbasis = get_kagome_bulkbasis(..., d - 1)
```

Therefore:

```text
certifier d=3:
  positive basis sees d=3  -> d>2 branch included
  gap basis sees d=2       -> d>1 branch included

certifier d=4:
  positive basis sees d=4  -> same d>2 branch
  gap basis sees d=3       -> same d>1 branch
```

With fixed `N`, `lso`, Hamiltonian, and symmetry settings, these are the same
SDP. Equality of the 1.28 transition is a regression check, not convergence
evidence.

Required correction:

> Replace “d-converged at N=13” with “the current legacy structured basis
> saturates by the input label d=3; d=4 is an identical formulation.”

### Energy basis

In the installed QMBCertify source,
`src/basic_function.jl:get_basis(...)` uses only:

```text
d > 1
d > 2
d > 3
```

No new basis entries appear for `d=5,6,7,8`. In
`src/bound_gsp.jl`, the `d` argument is passed to this basis builder and is not
otherwise used to generate a higher hierarchy level.

Thus the observed equality:

```text
d=4 = d=6 = d=8
```

is guaranteed by code. It does not show that the mathematical hierarchy has
converged or that the residual error is an irreducible hierarchy floor.

Required correction:

> Replace “d-converged” with “basis implementation capped at degree-four word
> families; larger numeric d values currently repeat the same model.”

### Consequence for Q5

The project has found an **implementation plateau**, not the hierarchy's
mathematical limit. Productive tightening requires one of:

- a genuinely larger nested structured basis;
- a larger local window;
- additional valid positivity/localizing blocks;
- explicitly implemented symmetry reduction that preserves the chosen state
  class.

It is premature to conclude that only `L/rdm` matters until the basis family
actually changes with `d`.

## P0 finding: `rdm=16` is unsupported and adds no RDM constraint

QMBCertify's `GSB` recognizes only:

```julia
rdm == 8
rdm == 9
rdm == 10
```

For other non-false values it prints:

```text
Adding rdm > 10 is not supported!
```

and later adds no `posepsd*` constraint.

The energy ledger's `rdm=16` value matching the weaker no-RDM value is therefore
expected. It does not show that a larger RDM is looser, that it “over-reaches
the patch,” or that `rdm=8` is optimal.

Required corrections:

1. Mark the `rdm=16` ledger row **invalid/no-op**, not a completed RDM probe.
2. Remove the “rdm=8 is the sweet spot/optimal” conclusion.
3. If the energy track remains active, test only supported `rdm=9` or `rdm=10`,
   after estimating their memory costs.
4. Add argument validation so unsupported values fail before model assembly.

## P0 finding: current frozen reproduction is internally inconsistent

### Return-type break

The committed patch changes `certify_*_gap` from returning an integer to
returning a named tuple:

```julia
(flag=..., termination=..., primal=..., dual=..., objective=...)
```

But these scripts still assume an integer:

- `scripts/gap_tfim_validate.sh`
- `scripts/gap_kagome.sh`
- `scripts/gap_kagome_d4.sh`
- `scripts/gap_kagome_n27.sh`

Examples include:

```julia
flag == 1
flag == 0
```

and the Kagome driver declares:

```julia
results = Tuple{Float64,Int,Float64}[]
```

before attempting to insert the certifier return value. The current scripts
cannot reproduce their historical ledgers against the current patched package.

The historical runs can still be genuine: their cluster processes may have
loaded the older integer-return source before the status patch was applied.
However, run-to-source mapping is not frozen sufficiently to prove that.

### Missing import

`scripts/gap_tfim_status.sh` calls:

```julia
norm(mm)
```

without `using LinearAlgebra`. The current script is not self-contained.

### Incomplete committed patch

The local SpectralGap package has a content modification adding Clarabel to
`Project.toml`, while `spectralgap_a1171c9.patch` includes only the source-file
changes. Applying the committed patch to the base repository does not recreate
the complete package dependency state required by `using Clarabel`.

### Stale provenance

`GAP_RUN_PROVENANCE.md`:

- describes a smaller patch than the current committed patch;
- omits the status-return, optimizer keyword, and attempted certificate logic;
- records an obsolete `src/sdp.jl` hash;
- says successful results are bit-for-bit reproducible although raw result
  files are not committed;
- says only two content files are modified although the Clarabel dependency
  requires a `Project.toml` change.

The session summary has the current `sdp.jl` hash prefix, but the provenance
document does not.

### Randomized stationarity-row filtering

`filter_mons(...)` in SpectralGap uses:

```julia
rand(length(tsupp))
```

to generate a randomized row fingerprint. Even if collision probability is
small and the resulting constraint span is normally equivalent, the assembled
artifact is not literally bit-for-bit deterministic unless the random seed or,
preferably, a deterministic exact selection procedure is frozen.

### Raw evidence is absent

The ledger references result files on SCNet, but does not commit:

- per-γ result records;
- raw solver status tuples;
- solver logs;
- block sizes and affine-row counts;
- peak memory;
- certificate candidates;
- source hash recorded with each individual result.

The ledger is therefore a narrative record, not yet an auditable result bundle.

### Cross-solver agreement is unsafe

`scripts/gap_cross_solver.sh` computes:

```julia
agree = (rm.flag == rc.flag) ? "YES" : "NO"
```

Both flags are zero for every non-optimal outcome. Two timeouts or two numerical
failures can therefore be reported as agreement. Cross-solver validation must
compare decisive three-way conclusions:

```text
feasible | certified_infeasible | unknown
```

An independent solver using the same assembly is also only solver-independent,
not formulation-independent. It is useful, but weaker than an independent
certificate verifier.

### Required source-freeze repair

Before further headline compute:

1. Create one complete patch including `Project.toml`.
2. Pin the base commit and record hashes generated from the applied patch.
3. Make every script consume the named result type.
4. Remove all branching on `status != OPTIMAL`.
5. Store `result_count`, raw statuses, objective/ray direction, solver version,
   tolerances, block inventory, source hash, and basis hash per γ.
6. Commit the raw result files used by the ledger.
7. Make row filtering deterministic.
8. Add a small no-solver regression that checks script/API compatibility.

## P1 finding: important physical interpretations need correction

### Square Heisenberg `g=0` is not a positive-gap calibration

`SQUARE_BASIS_SPEC.md` says:

> the 3×3 patch with only J1 bonds should give a finite, positive gap upper bound
> of order ~1 (the square Heisenberg is gapped)

The parenthetical statement is false. The infinite two-dimensional
spin-1/2 square-lattice antiferromagnet has Néel order and gapless Goldstone
modes. A finite relaxation may return a positive upper bound, but that does not
mean the physical model is gapped and does not calibrate convergence toward a
positive exact value.

Use the Shastry-Sutherland decoupled-dimer point instead:

```text
g=0
Δ_bulk = 1
```

This is also the exact benchmark requested in challenge #88.

### TFIM N=9 is not a nine-site tunneling-gap calculation

The TFIM certifier's `N=9` is the size of a local consistency window in an
infinite-volume state-polynomial relaxation. It is not a physical nine-site
Hamiltonian diagonalization.

The ledger's explanation that `Δ≈0.26` is an exponentially small finite-size
tunneling gap should be removed. The result is a finite-relaxation threshold for
the explicitly imposed symmetry class. It is neither a measured finite-chain
gap nor a proof of the true infinite-volume gap.

### The `0.258` source attribution is weak

The local upstream `example/example.jl` initializes:

```julia
ub = 0.24
lb = 0.24
```

so its bisection loop does not run. It does not visibly provide a `0.258`
reference. If `0.258` is from Table S1 of the paper or another historical run,
the ledger should cite that exact table/output rather than `example.jl`.

### Symmetry is misdescribed

For `model="kagome"`, the reviewed reduction performs:

- zeroing based on component-count parity;
- cyclic identification of X/Y/Z components through `reduce_perm`.

It does not:

- apply Square translations;
- apply C4 lattice rotations;
- apply Square mirrors;
- establish a full SU(2) irrep decomposition.

The older compatibility audit already states the correct warning:
component parity is not a full SU(2) irrep label. The newer
`SQUARE_BASIS_SPEC.md` regresses by calling labels SU(2) sectors and claiming
spatial symmetry is applied by `reduce!`.

For every result, record the actual state automorphisms being imposed. Do not
use the vague label “sign-symmetric” without listing them, and do not call a
component orbit a scalar/vector SU(2) block without a representation-theoretic
derivation.

## P1 finding: Kagome is not the requested headline extension

The official challenge description says:

> The goal is to extend the existing code to new two-dimensional lattice
> geometries and study the following models in order:
>
> 1. square-lattice J1-J2 Heisenberg;
> 2. Shastry-Sutherland;
> 3. triangular-lattice J1-J2 Heisenberg.

Challenge link:

<https://github.com/QuantumBFS/quantum.harness/issues/88>

Kagome is already implemented in the upstream code and its N=13 value is
included in the bundled example. Consequently:

- TFIM validates direction/API behavior;
- Kagome validates the legacy frustrated-model pipeline;
- neither is the main requested scientific extension;
- an N=13 Kagome value matching the bundled example has little competitive
  novelty.

If the only delivered gap result is Kagome N=13, describe it as a reproduction
or calibration, not the completed challenge target.

## Square J1-J2 code assessment

### What appears reliable

`src/SquareGapCertify.jl` correctly enumerates:

```text
H = J1 Σ_NN S_i·S_j + J2 Σ_NNN S_i·S_j
S_i·S_j = 1/4(XX+YY+ZZ)
J2 = g J1
```

The reviewed implementation:

- uses the correct SpectralGap site/component encoding;
- includes each J1 and J2 bond from the deterministic patch once;
- applies the factor `1/4`;
- returns the correct outer-site and eroded-inner-site geometry;
- is appropriately solver-agnostic.

The solver-free foundation in `SquareJ1J2Prototype.jl` and
`GenericGapModel.jl` is conservative about what it has not implemented. This is
good engineering and should remain the authoritative boundary.

### What is not yet implemented

The current branch still lacks:

- an explicit structured basis manifest;
- actual positivity and gap affine assembly for the generic state monomials;
- covariance-product assembly for Square;
- explicit symmetry constraints;
- a result adapter with `feasible/infeasible/unknown`;
- a validated witness path;
- a Square gap result.

The `one_symbol_lift_count` function is only a combinatorial count. It does not
itself construct a basis or prove compatibility with SpectralGap's legacy
`(word, state-symbols)` encoding.

PR #3 reportedly supplies `basis_manifest(problem, role)`, but that code is not
present in the reviewed checkout. It must be reviewed directly before treating
Square as unblocked.

### Problems in the newer Square basis specification

`SQUARE_BASIS_SPEC.md` should not be implemented verbatim because it assumes:

- labels 1–4 are SU(2) sectors;
- Kagome reduction supplies Square spatial symmetry;
- one representative per Square lattice orbit is sufficient under the existing
  reducer;
- the Square `g=0` system is gapped;
- copying the Kagome assembly is safe despite legacy randomized/low-precision
  internals.

These conflict with:

- `notes/certify_Heisenberg_square_gap_SPEC.md`;
- `spectralgap-refactor-plan.md`;
- the actual `reduce!` implementation.

The older generic-refactor plan is technically safer and should govern the
implementation.

### Recommended Square implementation strategy

Use the simplest declared structured basis first, but do not silently inherit
Kagome assumptions:

1. Begin with **no state symmetry**.
2. Materialize explicit positive, stationarity, and gap basis entries.
3. Save their complete ordered manifests and SHA-256 hashes.
4. Assemble solver-independent sparse affine rows.
5. Compare a legacy TFIM or Kagome wrapper coefficient-by-coefficient with the
   original assembly.
6. Only then connect the Square Hamiltonian and geometry.
7. Add optional symmetry modes one generator at a time, with tests showing that
   each generator is an automorphism of the Hamiltonian and preserves the
   declared state class.

A hand-curated C4/SU(2) basis should not precede the correct unsymmetrized
baseline. It adds too much opportunity to delete a valid low-energy sector or
change the physical target.

## Kagome tractability advice

### N=13,d=3 value

`Δ≤1.28` is respectable as a reproduction of the existing frustrated-model
pipeline. It is not a strong standalone challenge result because the number is
already in the upstream example.

### Do not brute-force N=27,d=3 next

The 243 GB OOM and 486 GB run without a completed first solve show that the
current formulation is outside the practical range. “Zero progress” is not
enough to identify whether time was spent in:

- basis generation;
- randomized stationarity filtering;
- affine assembly;
- JuMP-to-Mosek transfer;
- presolve;
- interior-point iterations.

Before another large allocation, instrument these phases separately and save
the block/row inventory.

### Try N=27,d=2 before N=27,d=3

The zero-dimensional label-1 gap block at `d=2` is mathematically vacuous. The
committed guards:

```julia
lb[i] > 0 || continue
lgb[l] > 0 || continue
```

make it possible to omit that empty block without changing the relaxation. Thus
`d=2` is not structurally invalid; it was unsupported by the original attempt
because Mosek rejects a 0×0 PSD variable.

The upstream example plot lists an N=27,d=2 value near `1.24`, already tighter
than N=13,d=3 at `1.28`, and the model should be materially smaller than
N=27,d=3.

After the certificate path is fixed:

1. reproduce N=13,d=2 with the empty-block guards;
2. check it against the upstream `1.31` reference;
3. run one N=27,d=2 γ point near the expected transition;
4. expand to a bracket only if the first solve is decisive and affordable.

This is a better use of compute than another ten-point N=27,d=3 scan.

### If N=27,d=3 is revisited

Investigate, in order:

1. exact model inventory and per-phase timing;
2. lower but still sound `lso` values, calibrated at N=13;
3. deterministic removal of duplicate stationarity rows;
4. genuine spatial automorphisms of the chosen patch;
5. sparse/chordal PSD structure or a more compact state-polynomial basis;
6. only then a larger-memory machine.

Reducing `lso` or the basis can weaken the upper bound but remains potentially
sound if it only removes necessary conditions and the resulting basis
specification is reported exactly.

## Energy safety-net assessment

The energy values are plausible numerical outputs of the upstream
QMBCertify-style SOS bound, but the current evidence is not sufficient for the
word “certified” in the strict standard adopted by the gap SPEC.

The scripts:

- call `GSB(...)`;
- record only `opt` and runtime;
- discard the returned data object;
- do not store raw solver statuses or residuals;
- depend on a runtime `@eval` patch;
- leave result files on SCNet rather than in the branch.

QMBCertify itself queries `objective_value(model)` and returns it even after a
non-optimal status, printing the status rather than returning a structured
three-way result. The wrapper scripts therefore cannot audit the status from
their saved result file.

Required wording until repaired:

> numerical SDP lower bound produced by Mosek with the stated formulation

rather than:

> formally certified lower bound

Additional corrections:

- retract all d-convergence claims for `d≥4`;
- mark `rdm=16` invalid/no-op;
- do not describe the phase diagram as a completed challenge #88 deliverable;
- finish the declared Shastry-Sutherland anchor if the safety-net track is to be
  called complete;
- record exact reference provenance before quoting percentage gaps.

## Answers to the five questions in the session summary

### Q1. Is `INFEASIBILITY_CERTIFICATE + SLOW_PROGRESS` sufficient?

**No, not by itself.** It is promising evidence of a candidate primal ray in
the SOS model, but `SLOW_PROGRESS` prevents treating the solver outcome alone as
decisive. Extract the variable-primal ray and validate it independently.

The current `dual(con_eq)` route is conceptually wrong for the reported result
side.

### Q2. Is Kagome N=13 `Δ≤1.28` competitive?

It is a useful calibration and frustrated-model reproduction, but probably not
competitive as the main result because it duplicates the bundled upstream
example. N=27 is not mandatory if the project delivers the requested Square
extension or a genuinely auditable certificate pipeline.

If pursuing a tighter Kagome calibration, try N=27,d=2 before N=27,d=3.

### Q3. Generic basis or hand-crafted Square basis?

Use the simplest explicit generic structured basis first. Do not invest in a
hand-crafted “SU(2)/C4-reduced” basis until:

- the unsymmetrized assembly is correct;
- PR #3's manifest implementation is reviewed;
- the exact symmetry action is implemented and tested;
- the certificate path is operational.

The generic basis is not automatically valid merely because a count exists; its
actual monomials and covariance closure must be reviewed.

### Q4. Kagome or Square as the challenge target?

Square. Kagome should remain the legacy calibration. The official challenge
explicitly requests extensions to Square J1-J2 first.

A good final narrative is:

1. TFIM: certificate/result-semantics calibration;
2. Kagome: legacy frustrated-pipeline reproduction;
3. Square J1-J2: new geometry and scientific result.

### Q5. Is the observed plateau the hierarchy limit?

No evidence supports that conclusion. The tested numeric `d` values map to
identical hard-coded bases. This is an implementation ceiling.

## Recommended work order

### Phase 0 — correct the scientific record

Before further compute:

1. Relabel both gap numbers as numerical transition candidates.
2. Remove “Farkas cert available” from the TFIM ledger.
3. Retract Kagome and energy d-convergence claims.
4. Mark energy `rdm=16` invalid/no-op.
5. Correct the TFIM tunneling interpretation.
6. Correct the Square `g=0` gap statement.
7. Correct the symmetry descriptions.
8. Update stale running/killed statuses in the ledger.

### Phase 1 — freeze one reproducible TFIM instance

Deliverables:

- one complete SpectralGap patch, including dependency metadata;
- one API-compatible script;
- deterministic assembly;
- exact source and basis hashes;
- raw status/result file committed to the branch;
- block and affine-row inventory;
- candidate primal ray serialized.

Acceptance condition:

> A fresh checkout can reconstruct the identical TFIM model and obtain the same
> decisive/candidate result without relying on untracked package edits.

### Phase 2 — validate the primal SOS ray

Deliverables:

- solver-independent certificate format;
- independent affine/PSD validator;
- TFIM γ=0.26 candidate ray;
- residual report;
- rational or interval post-processing if feasible.

Acceptance condition:

> The validator establishes the normalized SOS identity and cone membership
> without calling Mosek or trusting a collapsed solver flag.

Only after this phase should the ledger promote TFIM `Δ≤0.26` from candidate to
the chosen level of certified/numerically certified claim.

### Phase 3 — integrate the Square structured basis

Deliverables:

- reviewed PR #3 basis manifests;
- explicit positive/gap/stationarity monomial lists;
- nestedness and hash tests;
- solver-independent affine assembly;
- coefficient-by-coefficient legacy regression;
- Square J1-J2 model connection.

Start with the smallest affordable Square window and no hidden symmetry.

### Phase 4 — calibrate on a true positive-gap model

Use Shastry-Sutherland `g=0`, `Δ_bulk=1`, rather than Square Heisenberg `g=0`.
This both validates direction and advances the second official target.

### Phase 5 — optional Kagome tightening

After the certificate tooling is reusable:

- N=13,d=2 guarded regression;
- N=27,d=2 one-point feasibility test;
- narrow bracket if affordable;
- no N=27,d=3 brute-force scan without an inventory and cost model.

### Phase 6 — repair the energy floor if retained

- structured status/result return around `GSB`;
- supported `rdm=9/10` only;
- no duplicate `d>4` runs until the basis grows;
- committed raw results;
- Shastry-Sutherland energy anchor;
- exact reference provenance.

## Suggested result language

### Current defensible language

```text
For TFIM N=9,g=0.5 with the legacy symmetry-restricted structured relaxation,
the Mosek status changes between γ=0.25 and γ=0.26. This is a numerical
transition candidate; a validated exclusion witness is not yet available.
```

```text
For the upstream Kagome N=13 structured relaxation, the legacy status changes
between γ=1.26 and γ=1.28, reproducing the bundled SpectralGap example. This is
a numerical calibration result, not yet a formally certified upper bound.
```

### Language to avoid

```text
Two certified upper bounds
d-converged at N=13
rdm=8 is optimal
the square Heisenberg model is gapped
N=9 TFIM tunneling gap
full SU(2)/C4 reduction
bit-for-bit reproducible
```

until the corresponding issues above are resolved.

## File-specific action list

### `SESSION_STATUS_2026-07-28.md`

- Change “TWO certified upper bounds” to “two numerical transition candidates.”
- Replace the §8 explanation with the SOS-primal-ray orientation.
- Retract `d`-convergence claims.
- Reframe Kagome as calibration and Square as primary challenge target.
- Correct the N=27 status from running to killed if that is the final state.

### `gap-cert-ledger.md`

- Change the title to avoid “certified” before a witness exists.
- Remove “Farkas cert available.”
- Replace every collapsed `flag=0 → infeasible` statement with three-way
  semantics.
- Mark d=4 as an identical-basis regression, not convergence.
- Reconcile stale “running” paragraphs with completed/killed rows.

### `GAP_RUN_PROVENANCE.md`

- Regenerate after the complete patch is frozen.
- Include `Project.toml`.
- Update all hashes.
- Include raw result artifacts and per-run source hashes.
- Remove the bit-for-bit claim until randomized filtering is eliminated.

### `spectralgap_a1171c9.patch`

- Include dependency metadata.
- Preserve primal ray variables.
- Guard all result-value access by result/status availability.
- Return a structured result without a legacy Boolean conclusion.
- Add a complete certificate serialization path.

### Gap scripts

- Consume named fields such as `r.flag`, never the whole named tuple.
- Prefer `r.conclusion` once the result adapter exists.
- Import `LinearAlgebra` where needed.
- Record unknown outcomes rather than inserting them into the infeasible set.
- Save assembly and solve timings separately.

### `SQUARE_BASIS_SPEC.md`

- Remove the positive-gap statement for Square `g=0`.
- Remove the claim that Kagome reduction applies Square spatial symmetry.
- Replace SU(2)-sector labels with the exact legacy word-selection rules.
- Make the generic refactor plan authoritative.

### Energy ledger and scripts

- Mark `rdm=16` invalid/no-op.
- Remove d-convergence claims for `d≥4`.
- Add status/residual capture.
- Commit outputs.
- Complete the declared Shastry-Sutherland work or stop calling the track
  complete.

## Security note

The configured `origin` Git remote contains a live-looking GitHub credential in
the URL. Treat that credential as exposed:

1. rotate/revoke it;
2. remove credentials from `.git/config`;
3. use a credential helper, SSH remote, or environment-managed authentication.

Do not copy the existing remote URL into reports, logs, or chat.

## Final recommendation

Do not spend the next session on another large N=27,d=3 job. The highest-value
work is to turn the already observed TFIM candidate ray into an independently
validated certificate and repair the frozen artifact. Then apply that
infrastructure to the requested Square J1-J2 extension using the simplest
explicit, unsymmetrized structured basis.

That path simultaneously improves rigor, reproducibility, novelty, and
alignment with challenge #88.
