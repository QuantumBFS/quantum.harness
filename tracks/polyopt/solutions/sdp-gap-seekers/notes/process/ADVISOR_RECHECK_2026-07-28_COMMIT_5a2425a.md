# Advisor recheck after Priority 0A/0B closure

Date: 2026-07-28  
Branch: `challenge/polyopt-sdp-gap`  
Reviewed commit: `5a2425a`  
Previous reviewed commit: `491083f`

## Review scope

This is a static review only. I inspected the new verifier, corruption tests,
driver, evidence log, source patch, ledger, and repository state. I did **not**
run Julia, deserialize the artifact, execute tests or verifiers, or launch any
solver/SDP job.

## Executive verdict

The worker has materially closed the core Priority-0 verifier defect.

In particular:

- exact block-map counts are required;
- every block map must have its declared square dimension, including `0×0`;
- an empty map cannot stand in for a positive-size PSD block;
- affine row/variable indices are range checked;
- objective length, schema version, finite values, and required fields are
  checked;
- malformed cases short-circuit inside `audit`;
- `OPTIMAL` plus a positive improving ray is now classified as
  `STATUS_CONTRADICTION`;
- actual affine constants are exported;
- 14 required corruption cases are counted and reported;
- the driver writes the artifact under `evidence/` and propagates failures;
- the gap ledger was rewritten into one substantially consistent current
  status.

The earlier omitted-cone-block attack no longer passes.

For the committed, well-typed artifact produced by the current exporter, the
standalone audit design is now credible. The result remains correctly labelled:

```text
NUMERICALLY_AUDITED_CANDIDATE
```

because the solver termination is `SLOW_PROGRESS`, the ray is floating point,
and strict post-processing is absent.

The remaining verifier issues are narrower robustness claims, not a repeat of
the central one-vector/cone-binding failure. Priority 0 can reasonably be
considered closed for the current artifact after the wording is softened from
“every malformed schema never throws” to the more precise implemented scope.

## What was genuinely fixed

### 1. Exact cone-block inventory

`_validate_blocks` now requires:

```text
length(var_positions) == length(sizes)
size(index_map_i) == (sizes[i], sizes[i])
```

before any block is skipped or reconstructed.

This closes the specific failure in the `491083f` review, where empty or absent
block lists caused the PSD check to pass vacuously.

### 2. Schema short-circuiting inside `audit`

The following now return `SCHEMA_FAIL` before the main numerical calculations:

- missing required fields;
- unsupported schema version;
- invalid `nvars`/`nconstraints`;
- wrong ray/constants/objective lengths;
- non-finite ray, constants, objective, or affine coefficients;
- out-of-range affine row/variable indices;
- invalid `lambda_var_position`;
- wrong block counts or dimensions;
- out-of-range cone-map indices.

This is a meaningful improvement over collecting notes and then indexing or
calling `dot` on malformed arrays.

### 3. Actual affine constants

The exporter now stores:

```julia
Float64(cons[k].constant)
```

instead of hard-coding a zero vector.

The regenerated artifact is byte-identical to the old artifact, supporting the
claim that all constants in this particular model were genuinely zero.

### 4. Better status classification

The verifier no longer treats `OPTIMAL` like `DUAL_INFEASIBLE`. A positive
improving ray with a finite optimum is correctly marked as a status/data
contradiction.

### 5. Corruption-test coverage

The committed evidence reports all 14 required tests executing and rejecting
their corrupted artifact:

- affine coefficient;
- PSD index asymmetry;
- zero objective;
- non-finite ray;
- wrong lambda position;
- missing positivity map;
- missing gap map;
- empty map for positive declared size;
- rectangular map;
- extra block;
- out-of-range affine row;
- out-of-range affine variable;
- wrong objective length;
- wrong schema version.

An exact test counter prevents a skipped required test from being reported as a
complete pass.

I did not execute the suite, but the logged results are consistent with the
test code.

### 6. Ledger reconciliation

`gap-cert-ledger.md` is much clearer than its previous append-only state. The
top summary, run row, staged status, current claim, and open items mostly agree.

It correctly distinguishes:

- exported-conic-instance auditing;
- physical-formulation auditing;
- numerical candidate;
- rigorous certificate.

## Remaining verifier robustness issues

These are worth fixing, but they do not invalidate the current well-typed
artifact.

### 1. `verify` can still throw after an `audit` schema failure

`audit(a)` correctly returns `SCHEMA_FAIL` when a required field is absent.
However, `verify` then unconditionally prints fields such as:

```julia
a.N
a.gamma
a.nvars
a.affine_map
```

If the schema failure was caused by one of those fields being absent, the
command-line verifier can throw while attempting to display the failure.

The corruption suite calls `audit` directly, so it does not exercise this
end-to-end path.

Required small fix:

- if `r.label == "SCHEMA_FAIL"`, print only `r.notes` and return before accessing
  artifact fields;
- add command-line tests for a missing required field and a bad schema version.

### 2. Container element types are not fully validated

The schema checks lengths and finite values but do not fully establish that
every container has a compatible structure before iteration or reconstruction.
Examples:

- an affine-map entry with the wrong arity can throw during tuple
  destructuring;
- `ray_values` can pass some outer checks with a non-`Vector{Float64}` type,
  while `_reconstruct_block` requires exactly `Vector{Float64}`;
- block validation accepts `AbstractMatrix{<:Integer}`, while
  `_reconstruct_block` requires exactly `Matrix{Int}`;
- a container whose elements do not support `isfinite` can throw.

Two acceptable approaches:

1. declare and enforce exact schema types; or
2. generalize reconstruction methods to the validated abstract types and wrap
   structural validation safely.

The current exporter emits the expected concrete types, so this is defensive
hardening rather than evidence that the committed artifact is wrong.

### 3. The aliasing claim is value-based

The verifier checks `issymmetric(m)` after reconstructing matrix values. It
does not require:

```text
index_map[j,k] == index_map[k,j]
```

For JuMP symmetric variables, exact index aliasing is the cleaner schema
contract. A corrupted map that points to two distinct coordinates with
coincidentally equal current values can pass the value-symmetry check.

Require the index map itself to be symmetric in addition to checking the
reconstructed values.

### 4. The output still overstates the implication of selected corruption tests

The test source correctly says that selected corruption tests do not prove
general soundness. The final output still says:

```text
ALL CORRUPTION TESTS PASS ... (sound)
```

Prefer:

```text
ALL 14 DECLARED CORRUPTION TESTS PASS
```

This accurately reports coverage without claiming a finite test list proves
general verifier soundness.

## Evidence and provenance review

### Improvements

The committed evidence now contains:

- node and start/finish times;
- Julia version;
- repository short SHA;
- patch SHA-256;
- Hamiltonian printed explicitly;
- raw solver statuses;
- JuMP and MosekTools versions;
- artifact dimensions;
- verifier output;
- all 14 corruption-test results;
- full artifact SHA-256.

The recorded hashes match the committed files:

```text
patch:
3bdd31f7bc228af87d673d99df9b7afd36675564bc0e38fc0929b66386490f81

artifact:
7b6fa98ca8d2a9aaf15984b7b7e107c6b45376b85b12e570f93895c239904e68
```

### The “full log” is still curated

Line 11 of `tfim_N9_g0.26_full_log.txt` is a human-written replacement for
approximately 1.2 MB of automatically displayed tuple data:

```text
[line 11 was ... Suppressed ...]
```

That is a sensible way to avoid committing a huge duplicate dump, but it means
the file is not a byte-for-byte raw/full log. Call it a **curated complete
pipeline log**, or retain the raw stdout separately with compression and a
hash.

The driver also does not direct SLURM stdout to this evidence filename. Its
SBATCH output remains:

```text
gap_cert_export.out
```

so copying/curating the log into `evidence/` is still a manual step.

### Solver/version claim is not completely evidenced

The log prints:

- Julia `1.11.5`;
- JuMP `1.31.1`;
- MosekTools `0.15.10`.

The ledger additionally states Mosek `11.2.2`, but that solver version is not
printed by the committed driver/log. Also absent are:

- MathOptInterface version;
- SpectralGap source/package identifier beyond the patch hash;
- linear-algebra/LAPACK details relevant to eigenvalue checks;
- external source-file hashes or a clean patch-apply verification.

These can be added during Priority 1; they do not block the current numerical
candidate label.

### Stable artifact format remains open

The `.jls` file is still Julia-specific and opaque. The ledger correctly leaves
a versioned stable format in Priority 1.

## Numerical rigor remains unchanged

The verifier still uses one absolute tolerance `1e-6` on an unnormalized
homogeneous ray.

The result remains sensitive to scaling because rescaling `x` changes:

- the absolute affine residual;
- objective improvement;
- PSD eigenvalues.

One gap block remains numerically on the PSD boundary. Therefore the current
audit does not establish an exact cone ray.

The ledger correctly keeps open:

- ray normalization;
- scale-aware residuals;
- block-relative PSD tolerances;
- rational or interval post-processing;
- decisive solver status.

## Unchanged engineering work

No changes were made to the previously broken legacy drivers:

- `gap_tfim_validate.sh`;
- `gap_tfim_status.sh`;
- `gap_kagome.sh`;
- `gap_kagome_d4.sh`;
- `gap_kagome_n27.sh`;
- `gap_cross_solver.sh`.

They still need:

- the named return API;
- one three-way classifier;
- no `UNKNOWN == UNKNOWN` agreement;
- removal of stale `farkas_*` fields.

`filter_mons` still uses unseeded random fingerprints, so assembly is not
bit-for-bit deterministic.

`GAP_RUN_PROVENANCE.md` remains stale and should be regenerated rather than
retained behind a correction banner.

The patch still contains:

- an unused `export_cert` keyword;
- an unnecessary package-level `Serialization` dependency if serialization
  remains in the driver;
- unguarded `objective_value(model)` access for statuses without a result.

## Scientific status is unchanged

This update improves certificate infrastructure for a TFIM calibration case.
It does not advance the requested scientific extension:

- no Shastry-Sutherland `g=0` calibration;
- no integrated Square J1-J2 certifier;
- no Square J1-J2 result;
- no triangular result;
- no formulation-independent problem/basis audit.

The energy branch also remains at `6c1dd8d`.

The team should avoid spending many more cycles polishing a private `.jls`
calibration path if Sihan's separately developed MOF model/ray format can become
the shared evidence contract.

## New coordination input from Sihan

Sihan reported an independent MOF-model/ray audit at a tighter TFIM point
`γ=0.25125` and correctly rejected the Kagome `γ=1.272` candidate. This is
potentially more useful than duplicating certificate formats.

However, Sihan's latest chat summary contains a blocking configuration
contradiction:

- message label: `N=7,g=1,d=3`;
- reported dimensions: those of `N=9,g=0.5,d=2`.

The referenced commits are not yet visible in the current repository refs.
Do not merge those external claims into the local ledger until the configuration
is confirmed from machine-readable run metadata and the commits/artifacts are
available for review.

## Checklist status

| Requirement | Status at `5a2425a` |
|---|---|
| One-vector affine/objective/cone binding | **Fixed** |
| Exact declared cone-block inventory | **Fixed** |
| Fourteen requested corruption cases | **Fixed/reported passing** |
| Actual affine constants | **Fixed** |
| `OPTIMAL` status contradiction | **Fixed** |
| Driver failure propagation and evidence-path artifact | **Fixed** |
| Reconciled gap ledger | **Mostly fixed** |
| Total malformed-schema handling through CLI | **Minor hardening remains** |
| Raw immutable full log | **Partial; current log is curated** |
| Full environment/version provenance | **Partial** |
| Scale-aware or rigorous certificate | **Not fixed** |
| Deterministic assembly | **Not fixed** |
| Legacy driver/API repair | **Not fixed** |
| Stable artifact format | **Not fixed** |
| Physical-formulation audit | **Not fixed** |
| Shastry/Square scientific result | **Not fixed** |

## Recommended next action

Do one short hardening pass:

1. make `verify` report missing-field/schema failures without accessing absent
   fields;
2. require symmetric index maps;
3. add two end-to-end CLI malformed-artifact tests;
4. soften “tests prove sound” wording.

Then stop iterating on the same TFIM `.jls` path until coordination with Sihan
settles the shared MOF evidence format.

The main effort should move to:

1. deterministic/frozen formulation metadata;
2. Shastry-Sutherland `g=0` calibration;
3. Square J1-J2 integration and result.

## Bottom line

The worker did fix the latest Priority-0 comments in substance. The current
TFIM artifact is a credible, independently replayed **floating-point candidate
for the exported conic instance**. It is not a strict mathematical certificate
and it is not the challenge's new-geometry result.
