# Advisor re-audit after the claimed fixes

Date: 2026-07-28  
Primary branch reviewed: `challenge/polyopt-sdp-gap` at `8775271`  
Energy branch sampled separately: `feature/energy-cert-floor` at `6c1dd8d`

## Review scope

This is a static review of the committed notes, scripts, source patch, and
repository state. I did **not** run Julia, a solver, an SDP, or any numerical
experiment. Therefore this note assesses whether the written claims are
supported by the committed artifacts; it does not independently confirm any
reported numerical value.

## Bottom line

The worker fixed several important descriptions and corrected the direction of
the candidate conic ray, but **did not fix all review comments**.

The strongest new statement,

> “primal ray extracted + independently validated”

is not supported by the committed artifact. What has been implemented is an
**internal residual check of solver-returned variable values in the same JuMP
model**. That is useful progress, but it is not an independent certificate
verification and does not yet justify promoting the TFIM transition from a
numerical candidate to a certified bound.

The current honest status is:

> A candidate primal improving ray was read from variable primal values and
> passed same-model floating-point checks of positive `lambda`, Gram
> semidefiniteness, and affine residual. The solve terminated with
> `SLOW_PROGRESS`; no complete ray artifact or independent verifier report is
> committed.

## What was genuinely fixed

1. The notes now retract the false `d=3` versus `d=4` Kagome convergence claim
   and explain that the basis builder produces the same SDP.
2. The energy branch retracts the analogous `d=4/6/8` convergence claim and
   marks `rdm=16` as unsupported/no-op.
3. The gap ledger now explains the necessary three-way distinction between
   feasible, decisively excluded, and unknown solver outcomes.
4. The ray direction was corrected: for the homogeneous maximization model,
   the candidate primal improving ray must be read from variable primal values
   such as `value.(pos)`, `value.(gpos)`, and `value(lambda)`, not from
   `dual(con_eq)`.
5. The correction banners properly state that Square Heisenberg at `g=0` is
   gapless and that Shastry-Sutherland at the decoupled-dimer point is the
   appropriate positive-gap calibration.
6. The repository remote no longer exposes the credential that appeared in the
   earlier configuration.

These are real improvements. They correct several scientific and provenance
errors, but they are mostly status/wording fixes plus a preliminary ray audit.

## Blocking finding 1: the “independently validated” claim is still an overclaim

`scripts/gap_cert_extract.sh` checks:

- `cert_ray.lambda > 1e-6`;
- minimum eigenvalues computed from `value.(pos)` and `value.(gpos)`;
- `maximum(abs, value.(cons)) < 1e-6`.

The patched certifier returns only:

```text
(lambda, pos_min_eig, gpos_min_eig, cons_residual)
```

This is not the ray itself. In particular, the committed output does not
contain:

- all normalized Gram matrices;
- the free stationarity multipliers;
- the complete coefficient vector or sparse affine-map data;
- the ordered monomial/support basis needed to interpret every coordinate;
- scale and normalization metadata;
- a hash binding the certificate to the exact assembly;
- a standalone verifier result.

Moreover, `value.(cons)` evaluates the constraints constructed by the same code
and populated by the same solve. It is independent of the legacy binary
`flag`, but it is **not independent of the model assembly or solver result**.
The message printed by the script, “VALIDATES (independent of solver flag),” is
therefore materially weaker than “independently validated certificate.”

The numerical checks are also floating-point, use an absolute unscaled
`1e-6` tolerance, and come from a `SLOW_PROGRESS` termination. Rational or
interval post-processing remains absent.

### Required correction

Until a separate verifier exists, replace all instances of:

> extracted + independently validated

with:

> extracted candidate ray; internally residual-checked in the originating
> JuMP model

Do not call the result a certified upper bound.

## Blocking finding 2: the ledger contradicts itself

`gap-cert-ledger.md` currently says:

- near the top: no result has an independently validated witness;
- in the methodology: the witness is not yet extracted;
- in TFIM row 1: the primal ray was extracted and independently validated;
- in the open items: extraction and independent validation still need to be
  done.

All four cannot be true simultaneously. The row-1 promotion at commit
`8775271` should be reverted to the honest wording above, and the open-item
section should distinguish:

1. preliminary same-model extraction/check — done;
2. complete certificate serialization — not done;
3. independent verification — not done;
4. decisive solver status or rigorous post-processing — not done.

## Blocking finding 3: the frozen scripts do not consistently consume the new API

The certifier now returns a named record, but several scripts still treat the
whole return value as the old integer `flag`:

- `scripts/gap_tfim_validate.sh`;
- `scripts/gap_kagome.sh`;
- `scripts/gap_kagome_d4.sh`;
- `scripts/gap_kagome_n27.sh`.

`gap_kagome.sh` also declares an old
`Tuple{Float64,Int,Float64}` result element type.

`scripts/gap_tfim_status.sh` refers to removed fields
`farkas_min_eig` and `farkas_mmat` and does not import `LinearAlgebra` even
though it calls `norm`. Its exception fallback also implements the old field
layout.

`scripts/gap_cross_solver.sh` still defines agreement as
`rm.flag == rc.flag`. Because the legacy flag collapses all non-optimal
outcomes, two timeouts, two unknown outcomes, or two numerical failures can be
reported as agreement. Cross-solver agreement on collapsed flags is not an
independent infeasibility certificate.

### Required correction

Create one shared classifier with exactly three results:

- `FEASIBLE`;
- `EXCLUDED_WITH_CERTIFICATE`;
- `UNKNOWN`.

Classification must use raw termination and result statuses, not merely
`flag`. Scripts must read named fields consistently. Cross-solver comparison
must never convert `UNKNOWN == UNKNOWN` into scientific agreement.

## Blocking finding 4: the purported reproducibility artifact is incomplete

`spectralgap_a1171c9.patch` imports and selects Clarabel, but the patch does not
include the corresponding `Project.toml` dependency change. The modified
external checkout contains that dependency, so the patch is not a complete
reconstruction of the tested state.

The patch also calls `objective_value(model)` without first establishing that
an objective value is available for every returned status.

The external SpectralGap checkout still contains a randomized row-selection
path:

```julia
rd = ceil.(Int, rand(length(tsupp))*10^8)
```

This makes an allegedly frozen model assembly depend on unrecorded randomness.
Either replace it with deterministic ordering/keys or record and enforce the
seed and verify that collision behavior cannot change the model.

`GAP_RUN_PROVENANCE.md` was marked stale rather than regenerated. No committed
raw `.out`, `.err`, `.results`, JSON, or TOML evidence file supports the
reported `lambda=0.0051`, eigenvalue checks, residual, statuses, solver
versions, and hashes.

### Required correction

A frozen reproduction must contain:

1. a complete patch, including dependency metadata;
2. deterministic assembly;
3. an API-compatible driver;
4. a machine-readable full certificate;
5. raw solver-status output;
6. source, environment, and certificate hashes;
7. a separate verifier report.

## Blocking finding 5: Square J1-J2 remains the scientific target

The repository contains useful Square geometry/Hamiltonian construction and
generic model/prototype code. That is not yet evidence of an end-to-end,
validated `certify_Heisenberg_square_gap` result. The current branch still has
no demonstrated integration of the reported PR-3
`basis_manifest(problem, role)` / `:one_symbol_lift` implementation into a
complete Square certificate pipeline.

Kagome is an upstream calibration example, not the requested novelty. Further
Kagome scans should remain low priority until the certificate path and Square
pipeline are sound.

The appropriate calibration sequence is:

1. a deliberately small/toy instance for which the full certificate can be
   serialized and independently verified;
2. Shastry-Sutherland at `g=0`, with exact bulk gap `1`;
3. Square J1-J2 target points;
4. only then larger or more expensive scans.

## Energy-branch status

Commit `6c1dd8d` correctly relabels the table entries as numerical SDP lower
bounds, retracts the false `d`-convergence interpretation, and invalidates the
`rdm=16` row.

However, the same ledger still calls the planned writeup and several quantities
“certified” in its deliverable and phase-diagram prose. The scripts discard
solver status/residual information, depend on a runtime `@eval` patch, and keep
raw result files off-branch. The two declared Shastry-Sutherland rows remain
`TBD`. Therefore this track is not yet a complete certified deliverable either.

Required wording is “numerical SDP lower bound” until the exact solver status,
residual checks, reproducible patch, and raw evidence are committed.

## Acceptance checklist for the worker

The original comments should be considered fixed only when all of the following
are true:

- [ ] Remove the unsupported “independently validated” promotion from commit
      `8775271` and reconcile every contradictory status note.
- [ ] Export the complete normalized primal ray, not only summary statistics.
- [ ] Export an ordered basis/support manifest and the sparse affine map needed
      to interpret and recheck the ray.
- [ ] Add a separate verifier that does not call the original JuMP model,
      Mosek, or the original constraint-construction routine.
- [ ] Verify affine residuals with scale-aware tolerances and PSD blocks with a
      clearly documented numerical policy; preferably add rational/interval
      post-processing.
- [ ] Commit the raw TFIM result and verifier report with source/environment
      hashes.
- [ ] Fix every driver to consume the named return type and use three-way
      semantics.
- [ ] Make cross-solver comparison treat unknown outcomes as unknown.
- [ ] Include `Project.toml` in the SpectralGap patch and remove or control the
      randomized row filtering.
- [ ] Regenerate, rather than merely disclaim, the run-provenance document.
- [ ] Integrate and review the actual structured-basis manifest used by the
      Square SDP.
- [ ] Demonstrate the end-to-end certificate path first on a small controlled
      instance and then on Shastry-Sutherland `g=0`.
- [ ] Produce a Square J1-J2 result before treating the challenge work as
      scientifically complete.
- [ ] On the energy branch, commit raw status/residual evidence and either
      finish the Shastry-Sutherland rows or stop describing that deliverable as
      complete.

## Recommended next action

Do not spend the next cycle on another large scan. The highest-value task is to
turn the existing TFIM candidate into a portable certificate artifact and
verify it with a genuinely separate checker. This will settle the semantics,
the API, the evidence format, and the provenance contract on a small instance.
The same machinery can then be applied to Shastry-Sutherland and Square J1-J2
without repeating the current ambiguity.
