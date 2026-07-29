# Finite Star-to-Chain Mapping Before QN Purification

## Decision and scope

This design introduces a deterministic finite-bath star-to-chain transform as
the first phase of the scalable finite-temperature MPS work. Quantum-number
(QN) conserving purification is deliberately a later phase. This phase must
produce scientifically equivalent direct-star and chain Hamiltonians with the
existing non-QN `Electron` sites before any QN site construction is attempted.

The direct-star path remains the default. A chain run requires both:

1. an explicit `bath_representation: "chain"` request, and
2. a validated, hash-bound chain-mapping artifact derived from the requested
   star bath.

Completing this phase does not validate `N_b=48`, does not change the current
`n_bath_48_execution_validated: false` capability, and does not permit an
`N_b=48` convergence cell to run. Large-bath enablement requires separate
resource and numerical evidence after the later QN phase.

Only files under `tracks/mps/solutions/frustration-free/` are in scope.
Existing result trees, integration/QMC paths, root dependencies, and remote
jobs are outside this work.

## Existing interfaces and required change points

### Star bath and dense ED

- `bath.py`
  - `discretize_semicircular_bath(...) -> (epsilon, coupling)` emits the
    authoritative star arrays.
  - `make_bath_artifact(...)` and `verify_bath_artifact(...)` own the canonical
    schema-2 star artifact and its payload SHA256.
  - `_canonical_json(...)` defines the current Python canonical bytes.
- `finite_bath_ed.py`
  - `_consume_bath_artifact(...)` verifies and copies the star artifact.
  - `build_hamiltonian(epsilon, V, U, epsilon_d, mu, ...)` builds the direct
    star many-body Hamiltonian.
  - `_solve_consumed_bath(...)` and `solve_finite_bath(...)` compute thermal
    observables and Green functions.
  - `make_oracle_artifact(...)` binds the ED result to the star bath.

The transform will be a new module, `chain_mapping.py`, rather than an
extension of the authoritative star artifact. The star artifact remains the
source input; the mapping artifact is a derived, independently verified
artifact linked to the star payload SHA256.

### Julia Hamiltonian and observable path

- `julia/finite_bath_purification.jl`
  - `FiniteBathParameters` currently contains `epsilon`, `V`, `U`,
    `epsilon_d`, and `mu`.
  - `physical_hamiltonian_mpo(...)` builds impurity-to-every-bath-site star
    hopping on interleaved physical/ancilla sites.
  - `identity_purification(...)` and `interleaved_sites(...)` are geometry
    independent and remain non-QN in this phase.
- `julia/finite_bath_observables.jl`
  - `build_finite_bath_context(...)` builds and reuses the identity and MPO.
  - resumable thermal and Green branches consume only
    `FiniteBathParameters`; their algorithms need no geometry-specific branch.
- `julia/finite_bath_mps_runner.jl`
  - `read_request(...)` verifies the embedded star artifact and constructs
    `FiniteBathParameters`.
  - `checkpoint_identity(...)` binds request, bath, settings, source, and
    runtime hashes.
  - `make_output(...)` emits solver settings and provenance.
- `julia/finite_bath_checkpoint.jl`
  - `CheckpointIdentity` currently binds `bath_sha256` and solver settings.
    Geometry and mapping identity must be included so a star checkpoint cannot
    resume a chain request or vice versa.

The Julia parameter type will gain a representation and chain coefficients,
while preserving the current constructor as a direct-star default. The
observable and TDVP engines remain shared.

### Request, convergence, and provenance path

- `acceptance.py`
  - `_make_mps_request(...)` creates canonical runner schema-2 requests.
  - `_checkpoint_request_identity()` hashes the Julia sources.
  - `expected_runner_provenance(...)` and `verify_mps_output(...)` close the
    result provenance boundary.
  - the existing acceptance fixture stays direct-star.
- `convergence.py`
  - `_source_hashes(...)` binds solution Python/Julia sources.
  - `make_plan(...)` currently hard-codes
    `solver_capability.bath_representation = "direct_star"`.
  - `_runner_request_for_cell(...)` constructs each runner request.
  - `_n48_solver_capability_is_valid(...)` and `run_cell(...)` forbid
    unvalidated `N_b=48`.
- `convergence.schema.json`
  - recursively closes plan, cell, capability, and solver-setting objects.
- `acceptance.py`, `convergence.py`, their tests, and Julia runner tests all
  enumerate exact request/provenance keys.

The request and schemas must evolve together. Existing direct-star call sites
remain valid through defaults, but serialized requests use a new schema
version because their exact key sets change.

## Mathematical convention

For `N_b = N >= 1`, define the star bath before applying chemical potential:

```text
E = diag(epsilon[0], ..., epsilon[N-1])
v = (V[0], ..., V[N-1])^T
lambda = ||v||_2
```

The accepted star gauge is unchanged: `v` is real and componentwise
nonnegative. For `lambda > 0`, the first chain orbital is fixed by

```text
q_0 = v / lambda.
```

The transform `Q` is real orthogonal, with chain orbitals in its columns. It
must satisfy

```text
Q^T Q = I
T = Q^T E Q
Q^T v = lambda e_0
```

where `T` is symmetric tridiagonal, including possible zero hoppings between
canonically deflated blocks. The same `Q` is applied to the up- and down-spin
bath operators. No spin-dependent phase or ordering is allowed.

The bath one-body term is transformed before subtracting chemical potential:

```text
E -> T = Q^T E Q
T -> T - mu I
```

This ordering is recorded in the mapping convention. Although transforming
`E - mu I` is algebraically equivalent for an orthogonal `Q`, computing the
unshifted transform avoids making the mapping depend on a model-level `mu`.

The chain Hamiltonian for each spin is

```text
K_bath =
  sum_j (T[j,j] - mu) f_j^dag f_j
  + sum_j t_j (f_j^dag f_{j+1} + f_{j+1}^dag f_j),

K_hyb = lambda (d^dag f_0 + f_0^dag d),
```

with `t_j = T[j,j+1] >= 0`. The impurity interaction and energy are unchanged.

### Exact decoupled convention

If `v` is exactly zero, the mapping is exactly:

```text
lambda = 0
Q = I
T = E
chain_onsite = epsilon
chain_hopping = zeros(N - 1)
```

No Lanczos seed is invented. This identity mapping preserves the input orbital
order and makes the decoupled case byte-stable and unsurprising.

## Deterministic fully reorthogonalized Lanczos

### Input validation

`derive_chain_mapping(bath_artifact)` first calls
`bath.verify_bath_artifact`. It then copies finite `float64` `epsilon` and
real nonnegative `V`. The mapping does not refit or reorder the star bath.

For nonzero `v`, use `q_0 = v / ||v||_2` and build columns in order. At column
`j`:

1. Compute `alpha_j = q_j^T E q_j`.
2. Form `r = E q_j - alpha_j q_j`; for `j > 0`, also subtract
   `beta_{j-1} q_{j-1}`.
3. Fully reorthogonalize `r` against every accepted column in two deterministic
   modified-Gram-Schmidt passes, iterating columns from `0` through `j`.
4. Let `beta_j = ||r||_2`.
5. If `beta_j` exceeds the breakdown threshold, set
   `q_{j+1} = r / beta_j`. The norm is nonnegative by construction, so the
   resulting hopping is nonnegative.
6. Otherwise record an exact zero block-boundary hopping and use canonical
   deflation to select the next column.

All dot products and norms use NumPy `float64` operations in fixed array order.
The mapping provenance records Python and NumPy versions; cross-runtime
byte-identical eigensolver behavior is not claimed.

### Breakdown threshold

The scale-aware threshold is

```text
breakdown_tolerance =
  64 * eps(float64) * max(1, ||E||_inf) * N.
```

The artifact records this formula and the realized numeric value. A residual
with norm at or below the threshold is treated as a block boundary. Validation
replays the derivation with the same locked runtime and requires the stored
arrays to match.

### Canonical deflation

On breakdown before `N` columns exist:

1. Visit coordinate vectors `e_0, e_1, ..., e_{N-1}` in ascending index order.
2. For each candidate, perform two modified-Gram-Schmidt passes against every
   accepted column in ascending column order.
3. Select the first candidate whose residual norm exceeds the breakdown
   threshold.
4. Normalize it.
5. Fix its sign so its first component with magnitude greater than the
   breakdown threshold is positive.
6. Start a new Lanczos block from that vector, with the hopping across the
   previous block boundary fixed to exactly `0.0`.

If no coordinate residual survives, fail rather than emit an incomplete
matrix. This path handles repeated energies, invariant Krylov subspaces, and
zero couplings deterministically without calling an eigensolver.

After all columns are built, compute `T = Q.T @ E @ Q` directly. Symmetrize
only roundoff with `(T + T.T) / 2`, reject off-tridiagonal entries above the
validation tolerance, and serialize:

- `chain_onsite[j] = T[j,j]`,
- `chain_hopping[j] = abs(T[j,j+1])`, after requiring
  `T[j,j+1] >= -validation_tolerance`,
- exact `0.0` for recorded deflation boundaries.

If a tiny negative off-diagonal appears away from a recorded boundary, flip
the sign of all subsequent columns in that Lanczos block and recompute `T`.
This deterministic block sign correction preserves `q_0`, orthogonality, and
all previous nonnegative hoppings.

## Derived mapping artifact

`chain_mapping.py` owns schema version 1 and module version 1.0.0. The artifact
is separate from `bath.json`:

```json
{
  "payload": {
    "schema_version": 1,
    "source_bath_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "source_bath_schema_version": 2,
    "n_bath": 1,
    "representation": "finite_chain",
    "lambda": 0.1,
    "Q": [[1.0]],
    "chain_onsite": [0.0],
    "chain_hopping": [],
    "deflation_boundaries": [],
    "conventions": {
      "star_matrix": "E = diag(epsilon)",
      "coupling_gauge": "v is real and componentwise nonnegative",
      "initial_vector": "q0 = v / norm(v) when norm(v) > 0",
      "spin_transform": "the same real Q is used for up and down",
      "chemical_potential": "transform E before subtracting mu",
      "hopping_gauge": "chain hoppings are nonnegative",
      "breakdown": "deterministic canonical coordinate deflation",
      "decoupled": "v = 0 maps with Q = I"
    },
    "numerics": {
      "algorithm": "two-pass fully reorthogonalized Lanczos",
      "breakdown_tolerance": 0.0,
      "breakdown_tolerance_rule": "64 * eps(float64) * max(1, norm(E, inf)) * n_bath",
      "orthogonality_max_error": 0.0,
      "off_tridiagonal_max_abs": 0.0,
      "coupling_max_error": 0.0
    },
    "provenance": {
      "module": "chain_mapping",
      "module_version": "1.0.0",
      "python_version": "3.12.13",
      "numpy_version": "2.5.1",
      "schema_version": 1
    }
  },
  "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
}
```

The example values above illustrate types, not a fixture. Production code
emits full `N x N` `Q`.

`verify_chain_mapping_artifact(mapping, bath_artifact)` performs:

1. exact-key, type, finiteness, version, convention, and digest checks;
2. independent verification of the source star artifact;
3. exact linkage to `bath_artifact["sha256"]`;
4. deterministic replay of the mapping from the star arrays;
5. numerical invariants for orthogonality, tridiagonality, coupling, and
   nonnegative hopping;
6. exact identity checks for `v = 0`.

Rehashing corrupted `Q`, chain coefficients, source linkage, conventions,
deflation boundaries, tolerances, or provenance must still fail semantic
verification.

`write_chain_mapping_json(...)` follows the existing durable canonical JSON
pattern: temporary file in the destination directory, file `fsync`, atomic
replace, directory `fsync`, rollback for a pre-existing regular destination,
and rejection of symlink/directory destinations.

## Runtime representation model

### Python

Add a geometry-neutral validated data object internal to `finite_bath_ed.py`:

```text
FiniteBathGeometry(
    representation,
    onsite_matrix,
    impurity_coupling,
    source_bath_sha256,
    mapping_sha256,
)
```

For a direct star:

```text
onsite_matrix = diag(epsilon)
impurity_coupling = V
mapping_sha256 = None
```

For a chain:

```text
onsite_matrix = tridiag(chain_hopping, chain_onsite, chain_hopping)
impurity_coupling = [lambda, 0, ..., 0]
mapping_sha256 = mapping["sha256"]
```

`build_hamiltonian` gains keyword-only
`bath_representation="direct_star"` and
`chain_mapping_artifact=None`. The old call remains direct-star. Chain
selection without an artifact, a mapping supplied to a star request, or a
mapping linked to another bath fails before allocating the dense Hamiltonian.

The ED artifact records representation and optional mapping linkage. Its
scientific verifier recomputes observables through the requested geometry,
while equivalence tests compare star and chain spectra and observables.

### Julia

Extend `FiniteBathParameters` with:

```text
bath_representation::Symbol       # :direct_star or :chain
chain_onsite::Vector{Float64}
chain_hopping::Vector{Float64}
lambda::Float64
mapping_sha256::Union{Nothing,String}
```

The current constructor remains:

```julia
FiniteBathParameters(epsilon, V; U, epsilon_d, mu)
```

and produces `:direct_star`. A separate explicit constructor/helper consumes a
validated runner mapping and produces `:chain`.

`physical_hamiltonian_mpo` dispatches only its one-body terms:

- direct star: current impurity-to-each-bath hopping;
- chain: impurity-to-first-chain hopping `lambda`, nearest-neighbor chain
  hopping, and chain onsite terms.

Both use the same interleaved physical/ancilla order. No QNs are enabled:
`conserve_qns = false` and `FiniteBathContext.spin_qn_enabled == false` remain
binding in this phase.

The Hamiltonian norm bound uses the selected geometry's onsite and hopping
coefficients. Purification, Green branches, checkpoint storage, and observable
measurement remain geometry neutral.

## Request and capability contract

Runner schema version 3 adds an exact `bath_geometry` object:

```json
{
  "representation": "direct_star",
  "chain_mapping_artifact_json": null,
  "chain_mapping_artifact_file_sha256": null
}
```

or, only when explicitly requested:

```json
{
  "representation": "chain",
  "chain_mapping_artifact_json": "the complete canonical chain-mapping.json text",
  "chain_mapping_artifact_file_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
}
```

The chain mapping's payload digest is also added to runner output provenance
and checkpoint identity. Direct-star output uses `null`. The result's solver
settings include `bath_representation`, so geometry is visible in every
comparison and completed cell.

The plan-level capability becomes:

```json
{
  "bath_representations": ["direct_star", "finite_chain"],
  "default_bath_representation": "direct_star",
  "finite_chain_mapping_validated": true,
  "finite_chain_max_validated_n_bath": 6,
  "qn_purification_validated": false,
  "n_bath_48_execution_validated": false,
  "capability_evidence_sha256": null
}
```

`make_plan(...)` defaults to direct-star and accepts an explicit
`bath_representation` argument. Chain cells derive and bind a mapping artifact.
The capability states only what this phase proves. `_n48_solver_capability_is_valid`
continues to require all later evidence, including QN purification and a
non-null allowlisted capability evidence digest; therefore this phase alone
cannot unlock `N_b=48`.

Direct-star requests reject mapping bytes. Chain requests reject absent,
noncanonical, stale, or semantically invalid mapping bytes. Checkpoint identity
includes representation and mapping SHA256 in addition to the request digest,
making cross-geometry resume fail with `checkpoint identity mismatch`.

## Equivalence and validation

Tests cover every `N_b` from 1 through 6. Deterministic fixtures include:

- the supported semicircular discretization;
- asymmetric, nondegenerate star arrays;
- repeated energies that force breakdown and canonical deflation;
- sparse couplings with an invariant Krylov subspace;
- exactly zero `v`.

### Linear algebra invariants

For each size:

- `Q.T @ Q = I`;
- `Q.T @ diag(epsilon) @ Q` is tridiagonal;
- `Q.T @ v = lambda * e_0`;
- every serialized chain hopping is nonnegative;
- rerunning the transform produces identical artifact bytes.

Moments are checked independently through order `2*N_b - 1`:

```text
v^T E^m v =
lambda^2 e_0^T T^m e_0,  m = 0, ..., 2*N_b - 1.
```

For complex points with nonzero imaginary part:

```text
Delta_star(z) = v^T (zI - E)^-1 v
Delta_chain(z) = lambda^2 e_0^T (zI - T)^-1 e_0.
```

`Delta_chain` is also evaluated by the finite continued fraction from
`chain_onsite` and `chain_hopping`. Both real and imaginary parts must agree.

The existing normalized-Gaussian broadened bath is reconstructed from the
chain eigenpairs: chain spectral weights are
`lambda^2 * abs(U[0,k])^2`. Applying the existing width and grid must reproduce
the star broadened finite-bath hybridization.

### Hamiltonian spectra

Independent one-particle matrices compare:

- all eigenvalues;
- impurity spectral weights;
- direct matrix-unitary equivalence using `diag(1, Q)` before chemical
  potential subtraction.

For every `N_b=1..6`, many-body tests compare sorted eigenvalues in the
`(N_up,N_down)=(1,1)` sector for both `U=0` and `U>0`; this sector has at most
49 states and still exercises the impurity interaction. Additional complete
small-bath sector sweeps cover every nonempty sector for `N_b<=3`. Sector
restriction is a test oracle only; the production thermal trace remains grand
canonical.

### Thermal observables and Green functions

For every `N_b=1..6`, noninteracting ED thermal quantities are evaluated from
the one-particle eigensystem and compare direct-star and chain results for:

- `logZ` and finite `Z`;
- spin-resolved and total impurity occupancy;
- double occupancy;
- `G_up` and `G_down` at `tau = 0`, at least two interior points, and
  `tau = beta`.

For `N_b<=3`, the same grid is also compared with `U>0` through the production
full-Fock ED solver. Endpoint identities remain exact and interior values
exercise the transformed dynamics. This split covers all sizes without
weakening the existing dense-memory guard or allocating the `N_b=6`
grand-canonical matrix.

### Julia MPO/MPS

Julia tests compare direct-star and chain for every `N_b=1..6`:

- dense matrix elements of the MPO for small baths;
- MPO Hermiticity and fermionic signs;
- sorted one-particle and `(1,1)` interacting sector spectra;
- `finite_bath_observables` occupancy, double occupancy, Green endpoints, and
  interior tau values at a bounded small beta within the existing `1e-6`
  acceptance threshold;
- non-QN context construction (`spin_qn_enabled == false`);
- runner parsing, output provenance, and checkpoint identity.

Complete all-sector and longer-beta checks remain on `N_b<=3`. The Julia chain
coefficients are consumed from the Python-derived artifact; Julia does not
independently derive a second transform.

### Fail-closed provenance

Tests validly rehash then corrupt every scientific mapping field and require
rejection. Runner tests reject mapping file hash mismatch, payload hash
mismatch, wrong source bath, noncanonical JSON, wrong representation, and
unsupported schema. A checkpoint written for direct-star must be rejected by
an otherwise identical chain request, and the reverse direction is also
tested.

## Error policy

- Invalid star input fails through `verify_bath_artifact`.
- Nonfinite or negative couplings fail before Lanczos.
- Incomplete canonical deflation fails; it never silently truncates the bath.
- Orthogonality, coupling, or tridiagonality residual above the declared
  tolerance fails artifact creation and verification.
- Geometry/artifact mismatch fails before dense allocation or MPS creation.
- A direct-star request remains valid without a mapping artifact.
- A chain request never falls back to direct-star.
- No chain-only result may claim QN conservation or `N_b=48` capability.

## Chosen approach and rejected alternatives

The chosen approach is a Python-owned, canonical, hash-bound mapping artifact
consumed by both ED and Julia.

Two alternatives were rejected:

1. Deriving the chain independently in Python and Julia would create two
   floating-point implementations and weaken provenance when their basis
   choices differ at degeneracy.
2. Embedding chain arrays into `bath.json` would blur authoritative star input
   with a derived solver representation and force unrelated consumers to
   accept a wider bath schema.

The separate artifact keeps one authoritative transform, preserves the direct
star contract, and provides an exact checkpoint and result identity boundary
for the later QN phase.
