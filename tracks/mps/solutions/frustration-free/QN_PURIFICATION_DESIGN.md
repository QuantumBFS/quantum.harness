# QN-Conserving Impurity Purification Design

## Decision and phase boundary

This phase adds an explicit quantum-number-conserving purification to the
finite-bath Julia solver. It does not replace the existing solver mode:

- `direct_star` plus non-QN identity purification remains the default for
  library calls, acceptance, plans, and command-line use.
- QN purification is opt-in and is accepted only with
  `bath_representation = "chain"` and a mapping artifact already validated
  against the authoritative star bath.
- A QN request never falls back to non-QN execution. If the locked ITensors
  stack cannot construct, evolve, checkpoint, and reload the required sectors,
  the request fails before scientific output publication.
- Completing the QN implementation sets only the small-bath QN validation
  fact. It does not set `n_bath_48_execution_validated`, populate the capability
  allowlist, or permit an `N_b=48` cell.

Only files under `tracks/mps/solutions/frustration-free/` are in scope.
Production code is not changed by this design phase.

## Locked runtime evidence and remaining probe

`julia/Project.toml` and `julia/Manifest.toml` lock Julia 1.11.6,
ITensors 0.9.30, and ITensorMPS 0.4.1. The locked Electron site implementation
supports simultaneous `conserve_nf=true` and `conserve_sz=true`. Its state
labels are:

```text
Emp   -> QN(("Nf",0,-1), ("Sz", 0))
Up    -> QN(("Nf",1,-1), ("Sz",+1))
Dn    -> QN(("Nf",1,-1), ("Sz",-1))
UpDn  -> QN(("Nf",2,-1), ("Sz", 0))
```

Here `Sz` is twice the physical spin projection. A direct locked-runtime probe
also constructs a zero-flux Electron MPO containing number and hopping terms.
This establishes that the intended labels and elementary MPO path exist; it
does not establish end-to-end capability. The implementation must run a
deterministic `probe_qn_purification_capability()` that additionally checks the
dual pair, physical MPO, all four shifted operator sectors, one TDVP step, and
HDF5 round-trip. The result is diagnostic only and is never allowed to weaken
request validation.

## Existing interfaces at current HEAD

Current HEAD is `9e3fdea2a69171b119304a288797164d7e5eead0` on
`challenge/81-frustration-free`. The completed chain phase has these binding
interfaces.

### Python request and geometry

`acceptance.py`:

- `RUNNER_SCHEMA_VERSION = 3`.
- `acceptance_fixture()` selects `solver_settings.bath_representation =
  "direct_star"`.
- `_make_mps_request(bath_json, fixture)` emits an exact outer object
  `{payload_json, sha256}`. Its canonical payload has exact keys
  `schema_version`, `bath_artifact_json`, `bath_artifact_file_sha256`,
  `bath_geometry`, `checkpoint`, `model`, `tau`, and `solver_settings`.
- `bath_geometry` has exact keys `representation`,
  `chain_mapping_artifact_json`, and
  `chain_mapping_artifact_file_sha256`.
- Runner-facing `solver_settings` currently contains only `time_step`,
  `cutoff`, `maxdim`, and `krylov_expansion_dim`; geometry is a separate
  payload object.
- `_checkpoint_request_identity()` binds source hashes for
  `chain_mapping.py`, checkpoint, model definition, observables, purification,
  and runner, plus Project and Manifest hashes.
- `expected_runner_provenance()` and `verify_mps_output()` require exact
  representation and nullable chain-mapping provenance.

`chain_mapping.py` owns schema-1 canonical chain artifacts and
`verify_chain_mapping_artifact(mapping, bath_artifact)`. QN mode consumes this
validated result; it does not derive another basis or alter its SHA.

`finite_bath_ed.py` remains the independent full-grand-canonical oracle.
`FiniteBathGeometry` selects direct-star or mapped-chain one-body data.
`solve_finite_bath`, `make_oracle_artifact`, and `verify_oracle_artifact`
already bind representation and mapping. ED acquires no QN execution mode:
the QN MPS result is compared with the same exact thermal trace.

### Julia parameters, MPO, and purification

`julia/finite_bath_purification.jl`:

- `FiniteBathParameters` stores star inputs, model values,
  `bath_representation`, chain coefficients, `lambda`, and nullable
  `mapping_sha256`.
- `FiniteBathParameters(epsilon, V; ...)` remains direct-star.
- `FiniteBathParameters(:chain; ...)` validates chain dimensions and mapping
  identity.
- `interleaved_sites(parameters)` currently returns
  `[d_phys,d_anc,c1_phys,c1_anc,...]` Electron indices with
  `conserve_qns=false`.
- `identity_purification(parameters)` builds normalized same-label local
  identity pairs.
- `physical_hamiltonian_mpo(sites, parameters)` acts only on odd physical
  sites. Direct-star and chain differ only in one-body term assembly.
- `_evolve_normalized_state` implements normalized two-site TDVP, callback
  checkpoints, and `EvolutionResumeState`.

### Julia observables and operator branches

`julia/finite_bath_observables.jl`:

- `FiniteBathContext` reuses parameters, sites, identity MPS, MPO, norm bound,
  representation, and mapping SHA. It currently hard-codes
  `spin_qn_enabled=false`.
- `_apply_impurity_operator` applies `Cdagup`, `Cdagdn`, `Cup`, or `Cdn` at
  physical site 1, normalizes the branch, and records its log norm.
- `_green_branch` uses the creation norm identity for interior tau and has an
  annihilation form for the cyclic branch. Public endpoint processing uses
  occupancy identities and does not launch TDVP.
- `finite_bath_observables` supports uninterrupted and resumable execution.
  `ObservableCursor` distinguishes thermal/complete from Green
  `(tau_index, spin, before|after)` positions. An interior operator is applied
  exactly once between `before` and `after`.

### Julia checkpoint and runner

`julia/finite_bath_checkpoint.jl`:

- `CheckpointIdentity` binds request and payload digests, bath SHA,
  representation, nullable mapping SHA, solver settings, source and Julia
  environment hashes, package versions, checkpoint schema, and writer version.
- `ObservableResumeState` contains cursor, current evolution state, completed
  thermal MPS, and typed data.
- canonical metadata and HDF5 MPS state are hash-bound into immutable
  generations; `load_current_checkpoint` requires exact identity equality.

`julia/finite_bath_mps_runner.jl`:

- `read_request` validates exact schema-3 keys, canonical bytes, star and
  mapping artifacts, model values, numerical settings, source hashes, and the
  locked Julia project before constructing `FiniteBathParameters`.
- `checkpoint_identity(request)` converts validated request state into the
  checkpoint identity.
- `make_output` emits exact solver settings, observables, diagnostics, package
  and source provenance, representation, and mapping SHA.

### Convergence, acceptance, and capability

`convergence.py`:

- `make_plan(..., bath_representation="direct_star")` is the public default.
- `_cell_input_payload` and `_runner_request_for_cell` bridge plan cells to
  `_make_mps_request`.
- `solver_capability` currently records validated finite-chain mapping through
  `N_b=6`, `qn_purification_validated=false`,
  `n_bath_48_execution_validated=false`, and null evidence.
- `_n48_solver_capability_is_valid` requires all relevant booleans and an
  evidence SHA in the compiled `N48_CAPABILITY_ALLOWLIST`, which is empty.
- `run_cell` checks the `N_b=48` capability before executor entry and separately
  rejects chain sizes above the validated mapping limit.

`convergence.schema.json` closes solver settings, capability, plan, cell,
checkpoint, resource, calibration, and result objects. Every request/capability
change in this phase must evolve Python, Julia, schema, and exact-key tests
together.

## Chosen purification contract

### Explicit specification object

Add a Julia value type independent of `FiniteBathParameters`:

```julia
struct PurificationSpec
    mode::Symbol
    qn_gauge::Union{Nothing,String}
    qn_gauge_version::Union{Nothing,Int}
    base_sector_nf::Union{Nothing,Int}
    base_sector_sz::Union{Nothing,Int}
end
```

Public constructors are:

```julia
non_qn_purification()::PurificationSpec
qn_dual_purification(parameters::FiniteBathParameters)::PurificationSpec
```

The non-QN value is `(:non_qn, nothing, nothing, nothing, nothing)`.
The QN constructor requires `parameters.bath_representation === :chain` and a
non-null mapping SHA. For `M = N_b + 1` physical orbitals it returns:

```text
mode             = :qn_dual
qn_gauge         = "electron_nf_sz_ancilla_particle_hole"
qn_gauge_version = 1
base_sector_nf   = 2*M
base_sector_sz   = 0
```

Existing calls keep their behavior through
`purification=non_qn_purification()` keyword defaults. There is no environment
variable or bath-size heuristic that selects QN mode.

### Request schema 4

Runner schema 4 adds one exact payload object:

```json
"purification": {
  "mode": "non_qn",
  "qn_gauge": null,
  "qn_gauge_version": null,
  "base_sector": null
}
```

or, only for an explicit validated chain:

```json
"purification": {
  "mode": "qn_dual",
  "qn_gauge": "electron_nf_sz_ancilla_particle_hole",
  "qn_gauge_version": 1,
  "base_sector": {"Nf": 4, "Sz": 0}
}
```

The example is the minimum supported bath, `N_b=1`; every request derives
`Nf=2*(N_b+1)` from the verified bath and serializes that exact value.
`base_sector` has exact keys `Nf` and `Sz`. Parsing rejects:

- QN mode with direct star, null mapping, wrong-source mapping, unsupported
  gauge/version, or a sector inconsistent with `N_b`;
- non-QN mode with any gauge, version, or sector;
- unknown keys or modes.

`acceptance_fixture()` and `make_plan()` default to non-QN. The explicit API is
`purification_mode="qn_dual"` and requires
`bath_representation="chain"`. `_runner_request_for_cell` propagates the
already validated cell specification; it does not infer QN from chain geometry.

## Dual local pair and fixed global sector

Use Electron sites with:

```julia
siteinds(
    "Electron", 2*M;
    conserve_qns=true,
    conserve_nf=true,
    conserve_sz=true,
    conserve_nfparity=false,
)
```

`NfParity` is redundant when integer `Nf` is conserved and is explicitly
disabled. The physical and ancilla sites use the same locked QN labels. The
ancilla is interpreted in a particle-hole dual basis:

```text
physical Emp   <-> ancilla UpDn
physical Up    <-> ancilla Dn
physical Dn    <-> ancilla Up
physical UpDn  <-> ancilla Emp
```

For orbital `j`, define

```text
|Omega_j> = 1/2 (
    |Emp>_p   |UpDn>_a
  + |Up>_p    |Dn>_a
  + |Dn>_p    |Up>_a
  + |UpDn>_p  |Emp>_a
).
```

Every summand has pair charge `(Nf,Sz)=(2,0)`, so
`|Omega> = tensor_j |Omega_j>` lies in exactly
`(Nf,Sz)=(2*M,0)`. It is not a projection of the physical thermal trace:
different physical particle sectors are balanced by complementary ancilla
charges inside one enlarged-space sector.

### Reduced physical identity proof

The four ancilla dual labels are orthonormal and the pairing is bijective.
Therefore

```text
Tr_a |Omega_j><Omega_j|
  = 1/4 sum_s |s><s|
  = I_physical,j / 4.
```

Taking the tensor product gives

```text
Tr_anc |Omega><Omega| = I_physical / 4^M.
```

Consequently physical-only imaginary-time evolution gives

```text
|| exp(-beta*K/2) |Omega> ||^2 = Z / 4^M
log Z = M*log(4) + 2*log_unnormalized_norm,
```

which preserves the current full grand-canonical thermal trace and partition
normalization.

### Fermionic phase convention

The phase convention is part of QN gauge version 1:

1. site order is
   `[d_phys,d_anc,c1_phys,c1_anc,...]`;
2. the locked Electron basis order is `Emp, Up, Dn, UpDn`;
3. `UpDn` is the locked ITensors state, whose operator matrices include the
   existing down-spin sign convention
   `Cdagdn|Up> = -|UpDn>`;
4. all four displayed pair coefficients are real `+1/2`;
5. no fermionic swap is performed while forming a pair or tensoring pairs in
   site order.

This convention defines a tensor-product dual map, not an undocumented
particle-hole operator acting on Fock space. Unit-modulus rephasing would leave
the reduced identity unchanged but would change MPS bytes and branch signs, so
it is forbidden within gauge version 1. Physical hopping continues to use
`Cdag*`/`C*` OpSum terms; ITensors inserts Jordan-Wigner parity strings across
intervening ancillas exactly as in the validated non-QN implementation.

## Physical Hamiltonian and QN invariants

The Hamiltonian MPO remains physically identical and acts only on odd sites.
All direct physical terms preserve physical `Nf` and `Sz`, hence also the
enlarged total QNs:

- `Ntot` and `Nupdn` have zero flux;
- each spin-preserving hopping pair has net zero `Nf` and `Sz`;
- no operator acts on an ancilla.

QN context construction must assert:

```text
flux(identity)    = QN("Nf",2*M; "Sz",0)
flux(hamiltonian) = QN("Nf",0;   "Sz",0)
```

and must verify every site has QNs named exactly `Nf` and `Sz`. The non-QN
context continues to assert `hasqns(site) == false`.

## Green branches and shifted sectors

Let the thermal/base sector be `Q0=(2*M,0)`. Operator insertion changes the
total sector exactly:

```text
Cdagup : Q0 -> (2*M+1,+1)
Cdagdn : Q0 -> (2*M+1,-1)
Cup    : Q0 -> (2*M-1,-1)
Cdn    : Q0 -> (2*M-1,+1)
```

The implementation introduces:

```julia
struct OperatorSector
    insertion::Symbol
    spin::Symbol
    nf::Int
    sz::Int
end

operator_sector(spec, insertion, spin)::OperatorSector
```

`_apply_impurity_operator` validates the branch flux after application, before
normalization or checkpoint publication. `_green_branch` accepts an internal
explicit `insertion` keyword. The public production convention remains:

- endpoint tau values use occupancy identities and create no shifted branch;
- interior tau values use the creation form;
- the cyclic annihilation form is retained and tested as an equivalent
  scientific branch, including its distinct sector.

The branch sector and insertion are carried in point diagnostics and resumable
data. A `before` cursor has the base sector; an `after` cursor must have the
operator sector. A mismatch between cursor, spin, insertion, reported sector,
and actual MPS flux is corruption and fails before evolution resumes.

## Checkpoint, output, and provenance identity

Increment the checkpoint schema and writer version. Add these exact fields to
`CheckpointIdentity`:

```text
purification_mode::String
qn_gauge::Union{Nothing,String}
qn_gauge_version::Union{Nothing,Int}
base_sector_nf::Union{Nothing,Int}
base_sector_sz::Union{Nothing,Int}
```

Representation and `chain_mapping_sha256` remain separately bound. Thus
request digest, representation, mapping SHA, QN gauge/version, and base sector
all participate in identity equality.

Add the following to serialized `ObservableResumeState`:

```text
active_sector = null
```

for thermal, complete, endpoint-before, and interior-before base-state
snapshots, or:

```json
"active_sector": {
  "insertion": "creation",
  "spin": "up",
  "Nf": 5,
  "Sz": 1
}
```

for the creation-up branch of the minimum supported bath, `N_b=1`. All values
are derived from `M`. On write and load, compare metadata to `flux(psi)`.
For QN mode, compare `thermal_psi` to the base sector as well. Non-QN
checkpoints require null QN identity and active-sector fields.

Runner output solver settings, diagnostics, and provenance add:

```text
purification_mode
qn_gauge
qn_gauge_version
base_sector
```

Each Green diagnostic adds nullable `operator_sector`. Exact-key Python
verification rejects omission, inconsistent nullability, wrong sector,
wrong gauge, and rehashed corruption.

## Acceptance and equivalence

The existing binding acceptance fixture remains direct-star/non-QN and retains
its `1e-6` threshold and result location. QN validation is a focused,
non-result-generating acceptance test that uses:

- the same authoritative finite bath;
- explicit validated chain mapping;
- `purification_mode="qn_dual"`;
- the same ED oracle, tau order, model, and numerical settings.

For every `N_b=1..6`, tests compare QN-chain, non-QN-chain, non-QN-direct-star,
and ED where computationally bounded. Required evidence includes:

- local reduced identity and one-site thermal trace;
- exact site QN labels, base flux, MPO zero flux, and all four operator fluxes;
- dense MPO matrix elements, Hermiticity, fermionic signs, and sorted spectra;
- occupancy, double occupancy, Green endpoints, and at least two interior tau
  values;
- uninterrupted versus interrupted/resumed thermal and operator branches;
- request, output, checkpoint, and capability corruption;
- wall time, peak RSS, MPO widths, MPS link dimensions, and checkpoint bytes.

No single TDVP setting establishes convergence. QN/non-QN/ED agreement uses
the existing small-bath tolerance; resource evidence is descriptive until the
separate scalable gate is passed.

## Convergence and capability gates

After small-bath QN completion, the plan capability may state:

```json
{
  "bath_representations": ["direct_star", "finite_chain"],
  "default_bath_representation": "direct_star",
  "finite_chain_mapping_validated": true,
  "finite_chain_max_validated_n_bath": 6,
  "qn_purification_validated": true,
  "qn_purification_max_validated_n_bath": 6,
  "scalable_chain_qn_benchmark_validated": false,
  "n_bath_48_execution_validated": false,
  "capability_evidence_sha256": null
}
```

`_n48_solver_capability_is_valid` additionally requires:

```text
bath representation is chain
purification mode is qn_dual
mapping is validated for N_b=48 by the combined evidence artifact
scalable_chain_qn_benchmark_validated is true
n_bath_48_execution_validated is true
capability_evidence_sha256 is in N48_CAPABILITY_ALLOWLIST
```

The allowlist remains empty in this phase. QN completion alone therefore cannot
unlock `N_b=48`.

The later combined evidence artifact must bind the plan/cell input, bath SHA,
mapping SHA, QN gauge/version and sector, source and Project/Manifest hashes,
runtime versions, local pilot results, cluster pilot checkpoint generations,
wall time, MaxRSS, checkpoint bytes/timing, MPO width, maximum per-bond MPS
dimensions, truncation and Krylov diagnostics, and observable deltas against a
smaller validated control. Only a separately reviewed commit may add its digest
to the allowlist.

## Fail-closed policy

- A QN request with direct star or without a validated chain mapping is invalid.
- A failed runtime QN capability probe is an error, never a mode downgrade.
- Unexpected QN names, state charges, MPO flux, branch flux, or HDF5 reload
  flux are errors.
- A QN checkpoint cannot resume under non-QN mode, another gauge/version,
  another base or operator sector, another representation, or another mapping.
- Valid outer hashes do not excuse semantically inconsistent sector metadata.
- No output is published after any capability, provenance, or flux failure.
- Non-QN direct-star behavior and bytes change only as required by the schema
  version; scientific defaults do not change.

## Alternatives and tradeoffs

### Chosen: native Electron `Nf`/`Sz` with complementary ancilla occupation

This uses locked site semantics, keeps the physical MPO unchanged, retains the
full grand-canonical trace in one enlarged-space sector, and exposes operator
branches as ordinary shifted QN sectors. Its cost is a gauge-versioned custom
identity-pair constructor and stricter checkpoint identity.

### Rejected: custom ancilla site with negative physical charges

A custom dual site could assign ancilla charges `(-Nf,-Sz)` and place the
identity in total zero. It would require custom state/operator definitions,
fermion-string behavior, HDF5 compatibility, and a larger maintenance and
provenance surface. The locked native Electron labels already provide a fixed
sector through complementary occupation.

### Rejected: fixed physical particle-number thermal projection

Selecting one physical `Nf,Sz` sector would simplify the initial MPS but would
compute a canonical trace, contradicting the authoritative grand-canonical ED
oracle and the challenge Hamiltonian.

### Rejected: silently retry without QNs

Fallback would make a request's scientific and resource identity depend on
runtime behavior and could mislabel a non-QN result as scalable. Explicit
failure is required.

## Phase completion criteria

The QN implementation phase is complete only when:

1. all local pair, QN label, MPO, spectra, thermal, Green, checkpoint, request,
   provenance, and resource tests pass;
2. QN-chain agrees with non-QN direct-star and ED for every `N_b=1..6` within
   named tolerances;
3. both creation and annihilation shifted sectors and interrupted resume paths
   are validated;
4. direct-star/non-QN remains the default;
5. local and cluster pilot stopping criteria in the implementation plan pass;
6. `N_b=48` remains rejected on every target and the allowlist remains empty.
