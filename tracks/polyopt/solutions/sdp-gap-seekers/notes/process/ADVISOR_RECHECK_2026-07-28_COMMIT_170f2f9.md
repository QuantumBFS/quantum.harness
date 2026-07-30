# Advisor recheck after the portable-certificate update

Date: 2026-07-28  
Branch: `challenge/polyopt-sdp-gap`  
Reviewed commit: `170f2f9`  
Compared against the previous audit point: `8775271`

## Scope

This is a static review only. I inspected the commits, patch, exporter,
standalone verifier, committed evidence, ledgers, and still-relevant scripts. I
did **not** run Julia, deserialize the certificate, run the verifier, execute
tests, or launch any SDP/solver job.

The committed `.jls` artifact is therefore treated as an opaque binary whose
contents are described by the exporter and the committed verifier output, not
as something independently observed during this review.

## Executive verdict

The worker made substantial progress:

- the previous “independently validated” overclaim was retracted;
- a full variable vector and sparse affine map are now exported;
- a standalone verifier and a committed evidence bundle were added;
- the source patch now includes `Project.toml`;
- the current ledger explicitly keeps the result at “numerical candidate,”
  because the solver termination is still `SLOW_PROGRESS`.

However, the new verifier is **not yet a sound certificate verifier**. It
checks three duplicated representations without checking that they describe
the same conic ray:

1. affine feasibility is checked with `a.ray_values`;
2. PSD membership is checked with separate `a.pos_mats` / `a.gpos_mats`;
3. objective improvement is checked with separate `a.lambda`.

The artifact contains no variable-index maps binding the Gram-matrix entries
and `lambda` back to `a.ray_values`. Consequently, the verifier can pass even
if the vector satisfying the affine equations is not PSD or has no positive
objective direction.

This is a structural issue in the verifier, not merely missing polish.
Therefore:

> Stage 2, certificate data export, is meaningful but incomplete.  
> Stage 3, independent verification, must remain **PARTIAL / NOT YET SOUND**.

The strongest defensible claim at `170f2f9` is:

> A solver-produced candidate ray, an exported affine map, and separately
> exported Gram matrices were checked by a standalone Julia script, producing
> small floating-point residuals. The current verifier does not yet bind all
> checks to one ray, and the solve ended in `SLOW_PROGRESS`; this is not a
> rigorous certificate.

## What changed since the last review

Seven commits were added after `8775271`:

- `37fd2b4`: retracted the earlier independent-validation overclaim;
- `7fc065e` through `a54448d`: added and refined artifact export;
- `170f2f9`: committed the binary artifact and verifier output.

Only six solution artifacts changed:

- `evidence/tfim_cert_N9_g0.26.jls`;
- `evidence/tfim_N9_g0.26_verifier_output.txt`;
- `gap-cert-ledger.md`;
- `scripts/gap_cert_export.sh`;
- `scripts/verify_certificate.jl`;
- `spectralgap_a1171c9.patch`.

No other earlier checklist area was changed by these commits.

## Detailed correctness review

### 1. Critical: the verifier does not bind the cone blocks to the affine ray

In `scripts/verify_certificate.jl`, the affine residual is reconstructed as:

```julia
coef * a.ray_values[varpos]
```

The PSD checks are instead computed from:

```julia
a.pos_mats
a.gpos_mats
```

Those matrices are not reconstructed from `a.ray_values`, and the artifact does
not contain a map from each matrix entry to its variable position.

Thus the verifier establishes:

```text
A * x ≈ 0
P_i ⪰ 0
G_j ⪰ 0
```

but never establishes that the entries of `P_i` and `G_j` are the corresponding
coordinates of `x`.

The exporter probably populated both representations from the same JuMP result,
but the verifier trusts that fact instead of verifying it. An exporter mistake,
indexing mistake, stale field, or altered artifact would not necessarily be
detected.

#### Required fix

Export index matrices:

```text
pos_var_positions[block][row, col]
gpos_var_positions[block][row, col]
```

The verifier must reconstruct every Gram matrix from `ray_values` using those
indices. Prefer removing the duplicated floating-point matrices entirely.

For symmetric JuMP matrix variables, repeated upper/lower entries must map to
the same variable position. The verifier should check this explicitly and
check matrix symmetry rather than wrapping an arbitrary matrix in `Symmetric`,
which silently chooses one triangle.

### 2. Critical: positive `lambda` is not bound to the affine ray

The verifier checks:

```julia
lam = a.lambda
lam > tol
```

but does not know which entry of `a.ray_values` is the objective variable
`lambda`. Therefore it does not establish that the same vector satisfying
`A*x≈0` has positive objective.

For example, changing only the separately stored `a.lambda` to a positive
number would change the improvement check without changing the affine vector.

#### Required fix

At minimum export `lambda_var_position` and require:

```text
a.lambda == a.ray_values[a.lambda_var_position]
```

within a scale-aware consistency tolerance.

The cleaner general format is to export the complete objective vector `c` and
verify `c'x > 0`. This avoids hard-coding the assumption that the objective is
exactly one named scalar.

### 3. High: constants and dimensions are not independently checked

The exported map contains only `(constraint_index, variable_index,
coefficient)`. The verifier does not receive or check:

- the number of variables;
- the number of constraints;
- affine constants;
- an explicit objective vector;
- declared cone-variable index maps;
- coverage and bounds of all indices.

The present model is intended to be homogeneous, so all affine constants should
be zero. That should be exported and verified, not assumed. The verifier's
dictionary also contains only row indices that occur in `affine_map`; omitted
rows are invisible.

The verifier does not compare `pos_sizes` / `gap_sizes` against the actual
number and dimensions of the matrices. Empty or missing block lists can
vacuously pass the current checks.

#### Required fix

The artifact schema should include:

- `schema_version`;
- `nvars` and `nconstraints`;
- `affine_constants`;
- sparse `A`;
- objective vector `c`;
- cone block index maps;
- expected block counts and dimensions.

The verifier must reject out-of-range indices, missing blocks, wrong
dimensions, non-finite values, asymmetric matrices, and schema mismatches.

### 4. High: this is solver-independent checking, not formulation-independent checking

The verifier no longer calls JuMP, Mosek, or the original assembly routine.
That is a genuine improvement.

However, both the affine map and the ray are exported by the original model
assembly. The artifact lacks the ordered monomial/support basis and Hamiltonian
coefficient manifest needed to establish that the exported `A` is the intended
TFIM relaxation rather than merely some homogeneous conic program.

Once the binding problems above are fixed, the script may honestly be called a
**standalone or solver-independent verifier for the exported conic instance**.
It should not be called formulation-independent unless a second implementation
reconstructs `A` from a frozen problem/basis manifest and compares it.

#### Required fix

Export:

- the exact Hamiltonian support and coefficients;
- ordered positivity and gap bases;
- ordered constraint support;
- stationarity-multiplier inventory;
- source/assembly hashes.

Either add an independent assembler or explicitly limit the claim to
verification of the exported conic instance.

### 5. High: floating-point audit is not strict certification

The committed output reports:

- `termination=SLOW_PROGRESS`;
- affine residual about `1.3e-13`;
- positive-block minimum eigenvalues about `1.1e-3`;
- one gap-block minimum eigenvalue about `-5.2e-19`;
- `lambda≈0.00508`.

These values are encouraging, and the ledger correctly says rational/interval
post-processing remains undone.

The gap block is effectively on the PSD boundary. A small correction needed to
make the affine equations exact could move it outside the PSD cone. A raw
floating-point residual and eigenvalue tolerance therefore do not by
themselves prove the existence of an exact conic ray.

Keep the result classified as a numerical candidate until one of the following
is available:

1. a decisive solver certificate plus a sound, scale-aware verification
   policy; or
2. rational/interval reconstruction that proves equality and cone membership;
   or
3. a rigorously justified projection/correction argument that preserves PSD
   and positive objective margin.

### 6. Medium: the “portable artifact” wording is too strong

Julia `Serialization` produces a Julia-specific opaque binary. It is convenient
for the same Julia environment but is not a stable, language-neutral,
long-term certificate format. The committed reviewer cannot inspect it without
executing Julia deserialization.

Use “serialized Julia artifact” for the current `.jls`. For a portable
certificate, use a versioned, documented format with explicit arrays and
metadata, such as a text manifest plus stable binary/sparse-matrix files.

At minimum record:

- artifact schema version;
- Julia version;
- endianness/platform if relevant;
- artifact SHA-256;
- verifier SHA-256;
- source patch SHA-256;
- repository commit;
- solver and solver-wrapper versions.

### 7. Medium: the export driver does not enforce a successful verification

`scripts/gap_cert_export.sh`:

- writes `tfim_cert_N9_g0.26.jls` in the repository root, while the committed
  artifact is under `evidence/`;
- does not automatically write the full log to the committed evidence path;
- prints the verifier exit code, then executes another `echo`, so the overall
  shell script can finish with exit code zero even if verification failed;
- has no `set -euo pipefail`;
- documents `export_cert=...`, although the call does not pass that keyword and
  the keyword is unused by the certifier.

The driver should write directly to a temporary file, verify it, then copy it
into `evidence/` only after success. A failed verifier must make the job fail.

### 8. Medium: the patch is more complete, but cleanup remains

This part was genuinely improved:

- `spectralgap_a1171c9.patch` now includes `Project.toml`;
- the checked-in patch matches the relevant textual diff of the current
  external SpectralGap checkout.

Remaining issues:

- `Serialization` is still added as a SpectralGap package dependency even
  though serialization was moved to the driver and the package no longer uses
  it;
- `export_cert=nothing` remains an unused keyword;
- the comment says the design avoids adding `Serialization` as a package
  dependency, contradicting `Project.toml`;
- `objective_value(model)` remains unguarded for statuses with no available
  result;
- the patch contains cosmetic executable-mode changes.

These do not invalidate the reported candidate, but they weaken the claim that
the patch is clean and robust.

## Ledger and provenance consistency

### Gap ledger

The row-1 wording was corrected and is now appropriately conservative.
However, `gap-cert-ledger.md` again contradicts itself:

- lines 7–9 say no result has an extracted and independently validated witness;
- lines 34–36 say the witness itself is not yet extracted;
- lines 90–95 still list extraction and independent validation as future work;
- lines 115–124 say complete serialization and independent verification are
  done.

The staged section is the newest description, but Stage 3 is overstated for the
binding reasons above. Rewrite the entire earlier methodology/open-items text
instead of appending another status section.

Recommended stages:

1. same-model extraction/check — **done**;
2. raw conic-data export — **partial**;
3. sound standalone verification of one bound ray — **not yet done**;
4. formulation/assembly cross-check — **not done**;
5. rigorous certification — **not done**.

### Provenance

`GAP_RUN_PROVENANCE.md` remains marked stale and now contains facts invalidated
by the new commits, including the claim that the patch omits `Project.toml`.
It also retains obsolete hashes, old APIs, old commands, and old result
semantics.

The new evidence text does not bind itself to the binary artifact with a hash
and does not record the full source/environment inventory. Static review cannot
establish that the committed opaque binary is exactly the artifact that
produced the committed output.

Regenerate provenance now; do not add another correction banner.

## Status of the previous acceptance checklist

| Previous requirement | Current status | Assessment |
|---|---|---|
| Retract unsupported independent-validation wording | **Mostly fixed** | Row 1 is honest, but the new Stage-3 “DONE” claim is too strong and old contradictory text remains. |
| Export the complete normalized ray | **Partial** | A full variable vector appears to be exported, but it is not normalized, not mapped to cone blocks/objective, and is stored in an opaque Julia format. |
| Add a separate verifier | **Implemented but unsound** | It is separate from JuMP/Mosek, but its three checks are not bound to the same vector. |
| Commit raw result and verifier evidence | **Partial** | Binary + selected output are committed; full raw log, hashes, environment, and artifact-output binding are missing. |
| Fix all scripts for the named API and three-way semantics | **Not fixed** | The old TFIM/Kagome/status/cross-solver scripts are unchanged and still contain the previously identified errors. |
| Include dependency metadata in the patch | **Fixed** | `Project.toml` is now included. `Serialization` is unnecessary and comments are inconsistent, but the missing-file defect is fixed. |
| Make stationarity selection deterministic | **Not fixed** | `filter_mons` still uses unseeded `rand(...)`. |
| Reconcile stale ledgers/provenance | **Not fixed** | The gap ledger is internally contradictory and provenance is still stale. |
| Integrate the structured Square basis/certifier | **Not fixed** | No Square integration or result was added in these commits. |
| Complete Shastry-Sutherland calibration/result | **Not fixed** | No Shastry result was added. |
| Repair energy-track evidence and wording | **Not fixed in this update** | `feature/energy-cert-floor` remains at `6c1dd8d`. |

## Exact next requirements for the worker

### Priority 0: make the verifier sound

- [ ] Export `nvars`, `nconstraints`, constants, sparse `A`, and objective `c`.
- [ ] Export PSD-block variable-index matrices, including symmetric-entry
      aliasing.
- [ ] Reconstruct Gram matrices and objective directly from the single
      `ray_values` vector.
- [ ] Reject wrong block counts/dimensions, invalid indices, missing rows,
      non-finite data, and asymmetry.
- [ ] Add negative self-tests that deliberately alter:
      - one affine-ray entry;
      - one PSD-block entry;
      - the objective coordinate;
      - a block-index map;
      - a constraint coefficient.
      Every corruption must make verification fail.
- [ ] Distinguish `NUMERICALLY_AUDITED_CANDIDATE` from
      `RIGOROUSLY_CERTIFIED`; do not return or print “certificate audits” for a
      `SLOW_PROGRESS` floating-point candidate without that qualifier.

### Priority 1: make the evidence reproducible

- [ ] Replace or supplement `.jls` with a versioned documented artifact format.
- [ ] Write the artifact and log directly under `evidence/`.
- [ ] Make the shell job fail if export or verification fails.
- [ ] Record artifact, verifier, patch, source, and environment hashes.
- [ ] Record Julia, Mosek, MosekTools, JuMP, MOI, and LinearAlgebra/LAPACK
      versions.
- [ ] Remove unseeded randomness from `filter_mons`, or freeze and record it
      with a defensible collision-free selection method.
- [ ] Regenerate `GAP_RUN_PROVENANCE.md`.

### Priority 2: finish the previously requested engineering work

- [ ] Repair all legacy drivers to consume named fields.
- [ ] Implement a single three-way classifier and use it everywhere.
- [ ] Ensure cross-solver `UNKNOWN == UNKNOWN` is never called agreement.
- [ ] Remove the unused `export_cert` keyword and unused package dependency, or
      implement/document them consistently.
- [ ] Guard result/objective access for no-result solver statuses.
- [ ] Consolidate the contradictory ledger text.

### Priority 3: return to the scientific target

- [ ] Freeze the ordered basis/support manifest and independently audit the
      exported conic instance.
- [ ] Validate the end-to-end path on Shastry-Sutherland `g=0`, where the exact
      bulk gap is `1`.
- [ ] Integrate the structured Square J1-J2 basis and produce the requested
      Square result.
- [ ] Keep further Kagome scans below these tasks in priority.

## Recommended immediate action

Do not run another expensive SDP yet. First change the artifact so that one
vector `x` is the sole source of truth for:

```text
A*x = 0
cone_blocks(x) are PSD
c'x > 0
```

Then add corruption tests that prove the verifier rejects inconsistent
artifacts. Once that passes, regenerate the same TFIM artifact and provenance.
Only after this should the worker pursue rigorous post-processing and the
Shastry/Square targets.
