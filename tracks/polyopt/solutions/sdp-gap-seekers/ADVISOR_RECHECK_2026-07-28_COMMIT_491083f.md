# Advisor recheck after the one-vector verifier update

Date: 2026-07-28  
Branch: `challenge/polyopt-sdp-gap`  
Reviewed commit: `491083f`  
Previous reviewed commit: `170f2f9`

## Review scope

This is a static review of the committed code, patch, ledger, and evidence. I
did **not** run Julia, deserialize the `.jls` artifact, execute the verifier or
corruption tests, run repository tests, or launch a solver/SDP job.

The numerical output is assessed for consistency with the code and committed
files, but it is not independently reproduced here.

## Executive verdict

The worker fixed the central defect from the previous review:

- one vector `x = ray_values` is now the source of the affine residual;
- the objective is reconstructed as `c'x`;
- every nonempty Gram block is reconstructed from `x` through variable-index
  maps;
- the old separately trusted matrices and scalar `lambda` were removed;
- the output correctly says `NUMERICALLY_AUDITED_CANDIDATE`, not certified;
- the shell driver now stops on command failures;
- the committed artifact SHA-256 begins with the value reported in the ledger.

For a **well-formed artifact emitted by the current exporter**, the previous
three-unbound-copies problem is genuinely closed.

However, the current claim that the verifier is fully “SOUND” and Priority 0 is
done is still too strong. The verifier accepts an artifact with missing or empty
PSD-block index maps, skips all cone checks, and treats cone membership as
vacuously true. Its five corruption tests do not cover this omission case.

The best current assessment is:

> The reported TFIM artifact has a credible standalone floating-point audit in
> which the normal exporter binds the affine equations, objective, and displayed
> Gram blocks to one vector. The verifier is not yet robust against malformed or
> incomplete artifact schemas, and the solve remains `SLOW_PROGRESS`. The result
> is a numerical candidate, not a rigorous gap certificate.

## What changed since `170f2f9`

Eight commits were added:

- `37b87f9`: one-vector schema and verifier;
- `74b9132`: refreshed source patch;
- `30504f8`, `83bd108`, `026665d`, `9bce7f6`, `6beea4e`: execution/syntax and
  verifier fixes;
- `491083f`: refreshed artifact, evidence, and ledger.

Changed solution artifacts:

- `evidence/tfim_cert_N9_g0.26.jls`;
- `evidence/tfim_N9_g0.26_verifier_output.txt`;
- `gap-cert-ledger.md`;
- `scripts/gap_cert_export.sh`;
- `scripts/test_verifier_corruption.jl`;
- `scripts/verify_certificate.jl`;
- `spectralgap_a1171c9.patch`.

No Square, Shastry-Sutherland, energy-branch, legacy-driver, deterministic
assembly, or provenance file changed in this update.

## What is genuinely fixed

### 1. The same vector now drives the three principal checks

The exporter builds:

```text
x
A and affine constants
c
lambda variable position
positivity-block variable-index maps
gap-block variable-index maps
```

The verifier then computes:

```text
A*x + constants
c'x
Gram blocks reconstructed from x
```

This directly addresses the previous finding that the residual, PSD matrices,
and positive `lambda` were checked from unrelated copies.

The exporter obtains the index maps from the same JuMP variable references used
to form `all_variables(model)`, so the normal export path is internally
consistent.

### 2. The reported claim is now appropriately limited

The verifier reports:

```text
NUMERICALLY_AUDITED_CANDIDATE
```

and explicitly states that a `SLOW_PROGRESS` floating-point result is not a
rigorous proof. This wording is appropriate.

The committed output reports:

- `nvars=23949`;
- `ncons=2705`;
- `14360` affine-map entries;
- affine residual `1.3062e-13`;
- `c'x=0.005075589...`;
- two reconstructed positivity blocks with positive minimum eigenvalues;
- two reconstructed gap blocks, one numerically on the PSD boundary;
- all five implemented corruption cases rejected.

I did not reproduce these values, but they are consistent with the new code and
the earlier solver output.

### 3. The artifact hash in the ledger is correct

The current committed artifact has SHA-256:

```text
7b6fa98ca8d2a9aaf15984b7b7e107c6b45376b85b12e570f93895c239904e68
```

This matches the `7b6fa98c…` prefix in `gap-cert-ledger.md`.

### 4. The source patch is synchronized

The SHA-256 of `spectralgap_a1171c9.patch` matches the textual diff of the
relevant modified external files:

```text
0cb3994af7d436e84e1845385edea4bdedd252924057ccb8b4c78cdb42c880a0
```

The earlier missing-patch synchronization problem is fixed for
`Project.toml`, `src/SpectralGap.jl`, and `src/sdp.jl`.

### 5. The shell pipeline now propagates failures

`gap_cert_export.sh` now uses:

```bash
set -euo pipefail
```

and explicitly exits when no certificate artifact exists. A verifier or
corruption-test failure now stops the job rather than being hidden by the final
`echo`.

## Remaining correctness issue: omitted cone blocks pass

This is the most important new finding.

The verifier iterates only over the block maps supplied by the artifact:

```julia
for (i, im) in enumerate(a.pos_var_positions)
    isempty(im) && continue
    ...
end
```

and later:

```julia
for (i, im) in enumerate(a.pos_var_positions)
    isempty(im) && continue
    ...
end
```

There is no check that:

```text
length(pos_var_positions) == length(pos_sizes)
length(gap_var_positions) == length(gap_sizes)
```

and no requirement that:

```text
declared block size > 0  =>  index map is nonempty
declared block size == 0 =>  index map is exactly 0×0
```

Therefore a corrupted artifact can replace:

```text
pos_var_positions
gap_var_positions
```

with empty lists or empty matrices. The affine and objective checks still use
`x`, but no PSD eigenvalue is computed. The code then sets:

```julia
psd_ok = true
```

because both minimum-eigenvalue arrays are empty.

That artifact can pass even though the affine vector is not known to lie in the
PSD cone. This is a real soundness hole.

### Required fix

Before reconstructing anything, require:

```text
length(pos_var_positions) == length(pos_sizes)
length(gap_var_positions) == length(gap_sizes)
```

For every block:

```text
size(index_map) == (declared_size, declared_size)
```

including zero-size blocks. Do not `continue` before validating the declared
dimension.

Require at least the exact expected block inventory for the artifact schema.
Missing or additional maps must produce `SCHEMA_FAIL`.

Add corruption tests that:

1. delete one positivity-block map;
2. delete one gap-block map;
3. replace a positive-size map with `zeros(Int, 0, 0)`;
4. truncate a map to a wrong rectangular shape;
5. add an unexpected extra block.

All must return a structured failure, not pass or throw.

## Additional schema-validation gaps

### 1. Wrong dimensions are recorded as notes, then computation continues

Examples:

```julia
length(a.c) == nvars || push!(notes, ...)
```

and:

```julia
(1 <= k <= ncons) || push!(notes, ...)
```

The verifier subsequently calls `dot(a.c, x)` or indexes `cons[k]`. A malformed
artifact can therefore throw a dimension or bounds exception instead of
returning `SCHEMA_FAIL`.

Similarly, block checks validate only `size(im, 1)`, not both dimensions, and
then `_reconstruct_block` assumes a square matrix.

### Required fix

Every schema violation must return immediately with `SCHEMA_FAIL` before any
numerical operation.

Check:

- `nvars > 0`;
- `nconstraints >= 0`;
- objective length exactly equals `nvars`;
- every affine row and variable index is in range;
- both dimensions of every block map;
- exact block-list counts;
- finite affine coefficients, constants, objective entries, and ray entries;
- all required fields and exact `schema_version`.

### 2. `schema_version` is exported but not checked

The artifact contains `schema_version=1`, but the verifier never validates it.
An older, future, or incompatible schema should fail explicitly rather than be
interpreted opportunistically.

### 3. The five corruption tests do not prove general soundness

The existing tests are useful and appear to test the intended mutations.
However:

- they do not test omitted cone blocks;
- they do not test wrong block counts or dimensions;
- they do not test out-of-range constraint indices;
- they do not test objective-length mismatch;
- they do not test schema-version mismatch;
- the PSD corruption can be skipped, while the script can still print
  `ALL CORRUPTION TESTS PASS`;
- the script counts accepted corruptions, not the number of corruption tests
  actually executed.

Replace the fixed “5/5” claim with an explicit test counter. A skipped required
test must fail the test suite.

Corruption tests demonstrate coverage of selected failure modes; they do not by
themselves prove verifier soundness.

## Objective/status classification issue

The verifier labels an audited ray `DECISIVE_AUDITED` when:

```julia
a.termination == "DUAL_INFEASIBLE" || a.termination == "OPTIMAL"
```

`OPTIMAL` should not be grouped with `DUAL_INFEASIBLE` for a positive improving
ray. If `A*x=0`, `x` lies in the cone, and `c'x>0`, the homogeneous primal has an
improving ray and cannot simultaneously have a finite optimum. An `OPTIMAL`
status in that situation is a status/data inconsistency requiring
investigation, not a decisive certificate label.

Required classification:

- `DUAL_INFEASIBLE` plus the appropriate primal certificate status and a passed
  audit: solver-decisive numerical audit;
- `SLOW_PROGRESS` plus passed floating-point audit:
  `NUMERICALLY_AUDITED_CANDIDATE`;
- `OPTIMAL` plus a passed positive-ray audit: `STATUS_CONTRADICTION`;
- all other ambiguous statuses: numerical/unknown unless rigorous algebra
  independently settles the result.

Even a decisive solver status is not, by itself, rational or interval
certification.

## Numerical rigor remains open

The verifier still uses a single absolute tolerance:

```text
1e-6
```

for the affine residual, objective margin, and PSD eigenvalues. These quantities
have different scales and scaling behavior.

The ray is not normalized. Because the conic system is homogeneous, rescaling
`x` changes:

- the absolute residual;
- `c'x`;
- every eigenvalue.

The audit outcome should not depend arbitrarily on the solver's ray scaling.

Recommended approach:

1. normalize the ray, for example to `c'x=1`, when safely positive;
2. report `||A*x||∞` relative to a documented matrix/vector scale;
3. use block-relative PSD tolerances based on spectral or Frobenius norms;
4. retain raw values as well as rounded displays;
5. pursue rational/interval reconstruction for strict certification.

The smallest reported gap-block eigenvalue is approximately zero. Consequently,
an exact affine correction could leave the PSD cone. The current conservative
`NUMERICALLY_AUDITED_CANDIDATE` label remains necessary.

## Exporter limitations

### 1. Affine constants are hard-coded

The exporter stores:

```julia
affine_constants=zeros(Float64, length(cons))
```

rather than exporting the actual constants from each assembled `AffExpr`.

The present code appears homogeneous, so the intended constants are zero.
Nevertheless, a verifier should check what was assembled, not a separately
hard-coded assertion. Export:

```text
Float64(cons[k].constant)
```

for each row and verify homogeneity afterward.

### 2. The artifact verifies an exported conic instance, not the physical formulation

The artifact still lacks:

- exact Hamiltonian support and coefficients;
- ordered monomial/support basis;
- ordered constraint-support manifest;
- stationarity-multiplier inventory;
- independent assembly or comparison hash.

The current script can become a sound standalone verifier for the exported
conic data after the schema fixes. It is not a formulation-independent check
that the exported conic data faithfully represents the intended TFIM
relaxation.

Use the phrase:

> standalone verifier for the exported conic instance

not:

> independent verification of the physical formulation

## Evidence and reproducibility status

### Improvements

- The binary artifact and verifier output are committed.
- The ledger records the correct artifact hash prefix.
- The output records dimensions, statuses, residual, objective, eigenvalues,
  label, and corruption-test results.
- The patch is synchronized with the relevant external textual diff.

### Still missing

The committed output begins at Step 2. It omits:

- node/start information;
- Step-1 solver/export output;
- artifact creation confirmation;
- exact source and environment hashes;
- Julia/JuMP/MOI/MosekTools/Mosek/LAPACK versions;
- full artifact and verifier hashes in the output itself.

`gap_cert_export.sh` still writes the artifact into the repository root, while
the committed artifact lives under `evidence/`. The move and selection of
output are not automated.

The artifact is still an opaque Julia `Serialization` file rather than a
versioned stable interchange format.

`GAP_RUN_PROVENANCE.md` remains stale and contains statements already invalidated
by the current patch and artifact.

## Gap-ledger consistency

The new staged section is the most accurate portion, but earlier sections still
contradict it:

- lines 7–9 say no independently validated witness exists;
- lines 34–36 say the witness itself has not been extracted;
- row 1 says only the same-model check exists and independent verification is
  still needed;
- lines 90–95 list extraction/independent validation as future work;
- lines 120–136 say sound standalone verification is done.

The ledger also overstates the schema guards: it says wrong dimensions are
rejected, although some are merely noted and others can throw or be skipped.

Rewrite the document into one current status rather than preserving obsolete
claims above a newer appendix.

## Status of the previous checklist

| Requirement | Status at `491083f` | Assessment |
|---|---|---|
| Bind affine, objective, and PSD checks to one `x` | **Fixed for normal exporter output** | This central design correction is real. |
| Robust standalone verifier | **Partial** | Missing/empty cone maps can pass; malformed schemas can throw. |
| Corruption tests | **Partial** | Five useful cases are reported as passing, but omission and dimension attacks are untested. |
| Honest numerical-candidate label | **Fixed** | Current output does not claim rigorous certification. |
| Complete stable artifact format | **Not fixed** | Julia `.jls`, incomplete schema validation, and no basis/problem manifest. |
| Scale-aware/rational verification | **Not fixed** | Absolute `1e-6`, unnormalized ray, no rigorous post-processing. |
| Complete raw evidence/provenance | **Partial** | Artifact/output committed and hash prefix matches; full log, versions, hashes, and regenerated provenance are missing. |
| Complete source patch | **Mostly fixed** | Relevant textual diff matches patch; unused dependency/keyword and unguarded objective access remain. |
| Deterministic stationarity selection | **Not fixed** | `filter_mons` still uses unseeded `rand(...)`. |
| Named API and three-way semantics in all scripts | **Not fixed** | Legacy TFIM/Kagome/status/cross-solver scripts were not changed. |
| Reconciled status documents | **Not fixed** | Gap ledger and provenance remain internally stale. |
| Square structured-basis/certifier integration | **Not fixed** | No scientific-target implementation or result added. |
| Shastry-Sutherland calibration | **Not fixed** | No Shastry result added. |
| Energy-track evidence/wording | **Not changed** | Energy branch remains at `6c1dd8d`. |

## Exact next requirements

### Priority 0A: close the remaining verifier hole

- [ ] Require exact equality between block-map counts and declared block counts.
- [ ] Require every map to have exactly the declared square dimension,
      including zero-size blocks.
- [ ] Reject missing, empty-for-positive-size, extra, rectangular, and
      out-of-range maps.
- [ ] Check `schema_version` and required fields.
- [ ] Return `SCHEMA_FAIL` for every malformed artifact rather than throwing.
- [ ] Check all numeric arrays and coefficients for finite values.
- [ ] Export actual affine constants.
- [ ] Remove `OPTIMAL` from the decisive-ray classification.

### Priority 0B: strengthen negative tests

- [ ] Add missing positivity-map and gap-map tests.
- [ ] Add empty positive-size map tests.
- [ ] Add wrong row/column dimension tests.
- [ ] Add extra-block and truncated-block-list tests.
- [ ] Add out-of-range affine row and variable tests.
- [ ] Add wrong objective length and schema-version tests.
- [ ] Require an exact expected number of executed tests; skipped tests fail.
- [ ] Integrate these checks into a repeatable test target rather than only a
      standalone evidence script.

### Priority 1: make the audit scale-aware and reproducible

- [ ] Normalize `x` and use documented relative residual/PSD policies.
- [ ] Write artifact and complete output directly under `evidence/`.
- [ ] Record complete hashes and package/solver/environment versions.
- [ ] Regenerate `GAP_RUN_PROVENANCE.md`.
- [ ] Replace or supplement `.jls` with a versioned documented format.
- [ ] Remove unseeded randomness from `filter_mons`.

### Priority 2: finish earlier engineering work

- [ ] Repair all legacy drivers for the named return API.
- [ ] Use one three-way classifier everywhere.
- [ ] Ensure unknown cross-solver outcomes are never called agreement.
- [ ] Remove or consistently implement the unused `export_cert` keyword.
- [ ] Remove the unused `Serialization` package dependency if serialization
      stays in the driver.
- [ ] Guard objective/result access when a solver returns no result.
- [ ] Consolidate the contradictory ledger and session/provenance notes.

### Priority 3: return to the scientific deliverable

- [ ] Add the problem/basis/support manifest needed to audit the formulation.
- [ ] Demonstrate the pipeline on Shastry-Sutherland `g=0`, exact bulk gap `1`.
- [ ] Integrate the structured Square J1-J2 basis and certifier.
- [ ] Produce the requested Square result before prioritizing further Kagome
      scans.

## Recommended immediate action

The worker should not rerun the SDP yet. First make schema completeness part of
the proof:

```text
the artifact declares every cone block
    -> every declared block has an exact index map
    -> every Gram entry is reconstructed from the one x
    -> no block can be omitted or skipped
```

Then add omission/dimension corruption tests and regenerate the same TFIM
artifact and full evidence bundle. This is a small, targeted follow-up to an
otherwise meaningful correction.
