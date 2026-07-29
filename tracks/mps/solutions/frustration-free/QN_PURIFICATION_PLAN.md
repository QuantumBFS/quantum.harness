# QN-Conserving Impurity Purification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit, fail-closed `Nf`/`Sz`-conserving dual purification for validated finite chains while preserving direct-star/non-QN defaults and keeping `N_b=48` forbidden.

**Architecture:** A gauge-versioned `PurificationSpec` selects either the existing non-QN identity pairs or native Electron QNs with complementary ancilla occupation. The physical chain MPO remains unchanged and zero-flux; Green operators enter explicit shifted sectors. Request, output, checkpoint, acceptance, convergence, and capability contracts bind mode, gauge, sector, representation, and mapping SHA.

**Tech Stack:** Python 3.12.13, NumPy 2.5.1, SciPy 1.18.0, pytest 9.1.1, JSON Schema draft 2020-12, Julia 1.11.6, ITensors 0.9.30, ITensorMPS 0.4.1, HDF5 0.17.3.

## Global constraints

- Modify only `tracks/mps/solutions/frustration-free/`.
- Do not modify or generate checked-in files under `results/`.
- Keep direct-star/non-QN as the default in every public API and CLI.
- Permit `qn_dual` only with an explicitly selected, validated chain mapping.
- Use QN names `Nf` and `Sz`; `Sz` stores twice physical spin projection.
- Use QN gauge `electron_nf_sz_ancilla_particle_hole`, version `1`.
- Use pair coefficients `+1/2` in locked basis order and the dual map
  `Emp->UpDn`, `Up->Dn`, `Dn->Up`, `UpDn->Emp`.
- Disable redundant `NfParity` when conserving integer `Nf`.
- Never project the physical grand-canonical trace.
- Never fall back from QN to non-QN after any probe or runtime failure.
- Preserve endpoint identities; apply operators exactly once only on interior
  branches.
- QN completion may set small-bath QN validation through `N_b=6`; it must leave
  the scalable combined benchmark false, `n_bath_48_execution_validated=false`,
  capability evidence null, and `N48_CAPABILITY_ALLOWLIST` empty.
- Run commands from repository root
  `/home/footman/code/quantum.harness-challenge-81`.

## Planned file responsibilities

- `julia/finite_bath_purification.jl`: purification specification, QN sites,
  dual identity pairs, capability probe, MPO/base-flux validation.
- `julia/finite_bath_observables.jl`: context mode, operator-sector validation,
  creation/annihilation branches, QN diagnostics and resume checks.
- `julia/finite_bath_checkpoint.jl`: gauge/base/active-sector checkpoint
  identity, serialization, HDF5 flux validation.
- `julia/finite_bath_mps_runner.jl`: schema-4 request parsing and exact output
  provenance.
- `acceptance.py`: default non-QN and explicit QN request construction and
  output verification.
- `convergence.py` and `convergence.schema.json`: explicit plan mode,
  small-bath QN capability, retained scalable/N48 gates.
- Existing Julia/Python test modules: all scientific, corruption, resume, and
  benchmark evidence.
- `README.md`: exact opt-in commands, limitations, and pilot procedure.

---

### Task 1: Lock QN labels and local dual identity

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/julia/finite_bath_purification.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_purification.jl`

**Interfaces:**
- Produces:
  `PurificationSpec`,
  `non_qn_purification()::PurificationSpec`,
  `qn_dual_purification(parameters)::PurificationSpec`,
  `interleaved_sites(parameters; purification=...)`, and
  `identity_purification(parameters; purification=...)`.
- The old positional calls remain non-QN.

- [ ] **Step 1: Add failing specification and label tests**

Add constants and expected constructor assertions:

```julia
const QN_GAUGE = "electron_nf_sz_ancilla_particle_hole"
const QN_GAUGE_VERSION = 1

chain = FiniteBathParameters(
    :chain;
    epsilon = [0.0],
    V = [0.1],
    chain_onsite = [0.0],
    chain_hopping = Float64[],
    lambda = 0.1,
    mapping_sha256 = repeat("a", 64),
)
spec = qn_dual_purification(chain)
@test spec.mode === :qn_dual
@test spec.qn_gauge == QN_GAUGE
@test spec.qn_gauge_version == 1
@test (spec.base_sector_nf, spec.base_sector_sz) == (4, 0)
@test_throws ArgumentError qn_dual_purification(
    FiniteBathParameters([0.0], [0.1])
)
```

For every QN site assert `hasqns(site)`, exact `Nf`/`Sz` charges for
`Emp,Up,Dn,UpDn`, and absence of `NfParity`.

- [ ] **Step 2: Add the failing reduced-density test**

For `M=1`, contract the pair to a dense `4x4` coefficient matrix `A` in
physical/ancilla basis order and assert:

```julia
@test A == [
    0 0 0 0.5
    0 0.5 0 0
    0 0 0.5 0
    0.5 0 0 0
]
@test A * A' ≈ Matrix{Float64}(I, 4, 4) / 4 atol = 1e-15
@test norm(psi) ≈ 1.0 atol = 1e-15
@test flux(psi) == QN(("Nf", 2, -1), ("Sz", 0))
```

Also inspect the four amplitudes directly so a valid reduced identity with
different phases fails the gauge test.

- [ ] **Step 3: Run RED**

```bash
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_purification.jl
```

Expected: fail because `PurificationSpec` and QN constructors do not exist.

- [ ] **Step 4: Implement the minimum QN pair constructor**

Add the exact type:

```julia
struct PurificationSpec
    mode::Symbol
    qn_gauge::Union{Nothing,String}
    qn_gauge_version::Union{Nothing,Int}
    base_sector_nf::Union{Nothing,Int}
    base_sector_sz::Union{Nothing,Int}
end
```

Create QN sites with `conserve_qns=true`, `conserve_nf=true`,
`conserve_sz=true`, `conserve_nfparity=false`. Build each pair with a
four-dimensional QN pair link whose blocks connect only the four complementary
states. Set exactly four amplitudes to `0.5`; use dimension-one zero-flux links
between pairs. Assert normalized MPS flux equals the specification.

- [ ] **Step 5: Run GREEN and commit**

Run the Step 3 command. Expected: all purification tests pass.

```bash
git add \
  tracks/mps/solutions/frustration-free/julia/finite_bath_purification.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_purification.jl
git commit -m "Add QN dual identity purification"
```

### Task 2: Validate QN physical MPO and locked capability

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/julia/finite_bath_purification.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_purification.jl`

**Interfaces:**
- Produces:
  `validate_purification_fluxes(sites, psi, hamiltonian, spec)`,
  `probe_qn_purification_capability()`.

- [ ] **Step 1: Add failing MPO matrix and spectrum tests**

For mapped chains `N_b=1..6`, construct non-QN and QN MPOs from identical
`FiniteBathParameters`. Compare dense matrix elements for `N_b<=2`, sorted
one-particle and `(N_up,N_down)=(1,1)` spectra for all sizes and `U in
(0.0,0.8)`, and all nonempty sectors for `N_b<=3`. Assert Hermiticity,
Jordan-Wigner signs across ancillas, and:

```julia
@test flux(qn_hamiltonian) == QN(("Nf", 0, -1), ("Sz", 0))
@test all(iszero, expect(qn_identity, "Ntot")[1:2:end] .-
    expect(non_qn_identity, "Ntot")[1:2:end])
```

- [ ] **Step 2: Add a failing locked capability probe test**

The probe must return an immutable named tuple with exact fields:

```text
supported, qn_gauge, qn_gauge_version, julia_version,
itensors_version, itensormps_version, site_labels_valid,
identity_sector_valid, mpo_zero_flux_valid, operator_sectors_valid,
tdvp_step_valid, hdf5_roundtrip_valid, failure
```

On success every boolean is true and `failure === nothing`. Monkeypatch an
internal probe stage to throw and assert `supported=false` with a nonempty
failure; no fallback state is returned.

- [ ] **Step 3: Run RED**

Run Task 1 Step 3. Expected: probe/flux APIs are undefined.

- [ ] **Step 4: Implement flux checks and the probe**

Reuse `physical_hamiltonian_mpo`; do not fork term assembly. The probe uses a
one-bath validated chain fixture, all four physical operators, one bounded TDVP
increment (`beta=0.02`, `time_step=0.02`, `maxdim=16`,
`krylov_expansion_dim=0`), and an HDF5 temporary-directory round trip.
Any exception becomes a failed probe result. QN request consumers later turn
that result into `ArgumentError`.

- [ ] **Step 5: Run GREEN and commit**

Run Task 1 Step 3. Expected: all tests pass.

```bash
git add \
  tracks/mps/solutions/frustration-free/julia/finite_bath_purification.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_purification.jl
git commit -m "Validate QN Electron MPO capability"
```

### Task 3: Put Green operators in explicit sectors

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/julia/finite_bath_observables.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl`

**Interfaces:**
- Produces:
  `OperatorSector`,
  `operator_sector(spec, insertion, spin)`,
  QN-aware `build_finite_bath_context(parameters; purification=...)`.

- [ ] **Step 1: Add failing sector tests**

For `M=3`, assert:

```julia
@test operator_sector(spec, :creation, :up) ==
      OperatorSector(:creation, :up, 7, 1)
@test operator_sector(spec, :creation, :dn) ==
      OperatorSector(:creation, :dn, 7, -1)
@test operator_sector(spec, :annihilation, :up) ==
      OperatorSector(:annihilation, :up, 5, -1)
@test operator_sector(spec, :annihilation, :dn) ==
      OperatorSector(:annihilation, :dn, 5, 1)
```

Apply each operator to a thermal QN state and compare actual MPS flux with the
expected sector. Add zero-amplitude branch checks without inventing a sector.

- [ ] **Step 2: Add failing creation/annihilation equivalence tests**

At two interior points, run both norm identities with explicit
`insertion=:creation` and `:annihilation`; compare values within `1e-10` at
small beta and require distinct expected sectors. Endpoints must retain
`branch_status=:endpoint_identity` and null operator sectors.

- [ ] **Step 3: Run RED**

```bash
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl
```

Expected: missing `OperatorSector` and purification keywords.

- [ ] **Step 4: Implement sector-aware context and branches**

Add `purification` to `FiniteBathContext`, derive
`spin_qn_enabled = purification.mode === :qn_dual`, validate actual flux
immediately after operator application, and include nullable
`operator_sector` in every point diagnostic. Keep creation as the public
interior convention and endpoint processing unchanged.

- [ ] **Step 5: Run GREEN and commit**

Run Step 3. Expected: all observable tests pass.

```bash
git add \
  tracks/mps/solutions/frustration-free/julia/finite_bath_observables.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl
git commit -m "Bind Green branches to QN sectors"
```

### Task 4: Prove thermal and observable equivalence through N_b=6

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl`
- Modify: `tracks/mps/solutions/frustration-free/tests/test_finite_bath_ed.py`

**Interfaces:**
- Consumes existing Python mapping and ED APIs unchanged.
- Produces small-bath QN-chain versus non-QN-chain/direct/ED evidence.

- [ ] **Step 1: Add failing thermal-trace and observable matrix**

For `N_b=1..6`, `U=0`, compare QN-chain with non-QN chain, non-QN direct, and
the one-particle ED path for `logZ`, spin/total occupancy, double occupancy,
and `G_up/G_down` at `[0,beta/4,beta/2,3beta/4,beta]`. For `N_b=1..3`,
repeat with `U=0.8` and full-Fock ED. Use exact endpoint identities and require
two genuine interior points. Retain the existing `1e-6` MPS acceptance bound;
use `5e-12` for ED representation equivalence.

Add a one-physical-orbital test comparing
`M*log(4)+2*log_unnormalized_norm` with a direct dense thermal trace over all
four physical states.

- [ ] **Step 2: Run RED**

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_finite_bath_ed.py -q
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl
```

Expected: QN matrix fails until Task 3 mode propagation is complete; ED
regressions must remain green.

- [ ] **Step 3: Fix only scientific propagation gaps**

Do not modify ED algorithms. Correct QN context, log-partition normalization,
or branch diagnostics only where a failing independent comparison identifies
a mismatch.

- [ ] **Step 4: Run GREEN and commit**

Run Step 2. Expected: both commands pass.

```bash
git add \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl \
  tracks/mps/solutions/frustration-free/tests/test_finite_bath_ed.py
git commit -m "Verify QN purification against direct ED"
```

### Task 5: Bind QN identity and active sector to checkpoints

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/julia/finite_bath_checkpoint.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/finite_bath_observables.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl`

**Interfaces:**
- Extends `CheckpointIdentity` with mode, gauge/version, and base sector.
- Extends `ObservableResumeState` with nullable `active_sector`.

- [ ] **Step 1: Add failing identity mismatch tests**

Write one generation, then reject otherwise identical identities differing in
each of mode, gauge, version, base `Nf`, base `Sz`, representation, and mapping
SHA. Non-QN identity requires all QN fields null; QN identity requires all
fields and chain geometry.

- [ ] **Step 2: Add failing interrupted branch resume tests**

Interrupt thermal, interior-before, creation-after, and annihilation-after
positions. Reload from HDF5 and assert actual flux equals metadata. Resume to
the uninterrupted result. Validly rehash metadata after corrupting each active
sector field and require rejection before TDVP. Also reject a base-sector MPS
under an after-operator cursor and vice versa.

- [ ] **Step 3: Run RED**

```bash
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl
```

Expected: unknown identity/active-sector fields.

- [ ] **Step 4: Implement schema-2 checkpoint identity**

Set checkpoint schema to `2` and writer version to `2.0.0`. Update constructor,
dictionary conversion, exact keys, typed resume serialization, write-time
validation, load-time validation, and HDF5 MPS flux checks. Validate both
active `psi` and stored `thermal_psi`.

- [ ] **Step 5: Run GREEN and commit**

Run Step 3. Expected: all checkpoint and observable tests pass.

```bash
git add \
  tracks/mps/solutions/frustration-free/julia/finite_bath_checkpoint.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl \
  tracks/mps/solutions/frustration-free/julia/finite_bath_observables.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl
git commit -m "Bind checkpoints to QN sectors"
```

### Task 6: Evolve runner request and output to schema 4

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/julia/finite_bath_mps_runner.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl`

**Interfaces:**
- Consumes schema-4 `purification`.
- Produces validated `PurificationSpec`, schema-4 output, and checkpoint
  identity fields.

- [ ] **Step 1: Add failing exact request tests**

Extend the direct fixture with:

```julia
"purification" => Dict(
    "mode" => "non_qn",
    "qn_gauge" => nothing,
    "qn_gauge_version" => nothing,
    "base_sector" => nothing,
)
```

Add an explicit QN chain fixture with gauge/version and derived
`Dict("Nf"=>2*(n_bath+1),"Sz"=>0)`. Reject unknown keys, wrong sector, wrong
gauge/version, QN direct-star, QN missing mapping, and non-QN non-null fields.
Force the capability probe to fail and assert request rejection.

- [ ] **Step 2: Add failing output/provenance tests**

Require mode, gauge/version, base sector, and point operator sectors in solver
settings, diagnostics, and provenance. Require source hashes to change when
purification, observables, checkpoint, or runner changes.

- [ ] **Step 3: Run RED**

```bash
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl
```

Expected: schema-3 exact-key failures.

- [ ] **Step 4: Implement strict parsing and output**

Set runner schema to `4`, increment runner version, checkpoint constants to
schema `2`/writer `2.0.0`, and add `purification` to exact payload keys.
Derive expected sector from the verified bath; never trust the serialized
sector alone. Invoke the end-to-end probe before context construction for QN
requests.

- [ ] **Step 5: Run GREEN and commit**

Run Step 3. Expected: all runner tests pass.

```bash
git add \
  tracks/mps/solutions/frustration-free/julia/finite_bath_mps_runner.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl
git commit -m "Add explicit QN runner requests"
```

### Task 7: Preserve non-QN acceptance and add focused QN acceptance

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/acceptance.py`
- Modify: `tracks/mps/solutions/frustration-free/tests/test_acceptance.py`

**Interfaces:**
- `_make_mps_request` defaults to non-QN.
- `_explicit_qn_chain_fixture(mapping_bytes)` is test/pilot-only.

- [ ] **Step 1: Add failing default and explicit tests**

Assert `acceptance_fixture()` remains direct-star and has
`purification_mode="non_qn"` only in fixture-side settings. Its runner payload
must contain the exact non-QN object and no mapping. Add a QN helper requiring
chain mapping bytes and assert exact derived base sector.

Reject all invalid mode/geometry/gauge/sector combinations before Julia.

- [ ] **Step 2: Add failing verification corruption tests**

For validly rehashed output, independently corrupt mode, gauge, version, base
sector, each operator sector, representation, and mapping SHA. Require
`verify_mps_output` to reject every mutation.

- [ ] **Step 3: Run RED**

```bash
SKIP_CHALLENGE81_ACCEPTANCE=1 \
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_acceptance.py -q
```

Expected: schema/provenance assertions fail.

- [ ] **Step 4: Implement schema-4 Python request and verifier**

Set `RUNNER_SCHEMA_VERSION=4`, update checkpoint constants, add explicit
fixture-side mode parsing, derive sector from verified bath, and close output
exact keys. Keep `run_acceptance()` on the existing direct-star/non-QN fixture
and existing immutable result path.

- [ ] **Step 5: Run GREEN and commit**

Run Step 3. Expected: all tests pass with the real acceptance skipped.

```bash
git add \
  tracks/mps/solutions/frustration-free/acceptance.py \
  tracks/mps/solutions/frustration-free/tests/test_acceptance.py
git commit -m "Add focused QN acceptance requests"
```

### Task 8: Evolve convergence schema and retain the N_b=48 gate

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/convergence.py`
- Modify: `tracks/mps/solutions/frustration-free/convergence.schema.json`
- Modify: `tracks/mps/solutions/frustration-free/tests/test_convergence.py`

**Interfaces:**
- `make_plan(..., purification_mode="non_qn")`.
- QN plans require `bath_representation="chain"`.

- [ ] **Step 1: Add failing plan/schema tests**

Assert direct/non-QN defaults and explicit QN-chain cells. Extend capability
with:

```json
"qn_purification_validated": true,
"qn_purification_max_validated_n_bath": 6,
"scalable_chain_qn_benchmark_validated": false,
"n_bath_48_execution_validated": false,
"capability_evidence_sha256": null
```

Schema must reject missing/unknown fields and inconsistent cell mode, gauge,
sector, representation, or mapping.

- [ ] **Step 2: Add failing N_b=48 refusal matrix**

For local and cluster targets, vary each capability boolean and insert a fake
evidence SHA into a copied plan. Assert executor call count remains zero for
every case, including `qn_purification_validated=true`. Assert the compiled
allowlist remains empty.

- [ ] **Step 3: Run RED**

```bash
SKIP_CHALLENGE81_CONVERGENCE_PILOT=1 \
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py \
  -k "purification or qn or n48 or capability or schema" -q
```

Expected: unsupported mode/capability fields.

- [ ] **Step 4: Implement plan propagation and strict gate**

Add purification to `_cell_input_payload`, cell solver settings,
`_runner_request_for_cell`, completed-cell validation, source hashes, and JSON
schema. Update `_n48_solver_capability_is_valid` to require QN-chain mode,
combined benchmark boolean, execution boolean, and allowlisted evidence.
Leave `N48_CAPABILITY_ALLOWLIST = frozenset()`.

- [ ] **Step 5: Run GREEN and commit**

Run the complete convergence test with the pilot skipped:

```bash
SKIP_CHALLENGE81_CONVERGENCE_PILOT=1 \
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py -q
```

Expected: all tests pass; every `N_b=48` executor remains uncalled.

```bash
git add \
  tracks/mps/solutions/frustration-free/convergence.py \
  tracks/mps/solutions/frustration-free/convergence.schema.json \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py
git commit -m "Gate QN convergence capability"
```

### Task 9: Close the provenance corruption matrix

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/tests/test_acceptance.py`
- Modify: `tracks/mps/solutions/frustration-free/tests/test_convergence.py`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl`

**Interfaces:**
- Produces fail-closed evidence after valid outer rehashing.

- [ ] **Step 1: Add every semantic mutation**

Parametrize mutations of:

```text
purification mode
QN gauge and version
base Nf and Sz
active insertion, spin, Nf, and Sz
representation
chain mapping payload and SHA
request payload SHA
source hashes
Project and Manifest hashes
ITensors and ITensorMPS versions
checkpoint schema and writer version
capability booleans, maxima, and evidence SHA
```

Recompute all outer JSON and file hashes. Each mutation must fail semantic
validation before executor entry, checkpoint pointer advancement, resume TDVP,
or result publication.

- [ ] **Step 2: Run RED**

```bash
SKIP_CHALLENGE81_ACCEPTANCE=1 \
SKIP_CHALLENGE81_CONVERGENCE_PILOT=1 \
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_acceptance.py \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py \
  -k "corrupt or tamper or qn or sector or provenance" -q
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl
```

Expected: any validator that trusts hashes without replay exposes a failure.

- [ ] **Step 3: Close uncovered validators**

Require exact keys and independently derive every mode/sector relation. Do not
accept reported probe booleans or sector metadata as proof.

- [ ] **Step 4: Run GREEN and commit**

Run Step 2. Expected: all commands pass.

```bash
git add \
  tracks/mps/solutions/frustration-free/tests/test_acceptance.py \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl
git commit -m "Close QN sector provenance validation"
```

### Task 10: Add reproducible resource benchmark records

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/convergence.py`
- Modify: `tracks/mps/solutions/frustration-free/convergence.schema.json`
- Modify: `tracks/mps/solutions/frustration-free/tests/test_convergence.py`

**Interfaces:**
- Produces a canonical `qnBenchmark` artifact for small-bath comparisons.
- Does not produce scalable capability evidence and is not allowlist eligible.

- [ ] **Step 1: Add failing benchmark schema tests**

Require paired non-QN-chain and QN-chain measurements with exact shared
scientific input and fields:

```text
schema_version, artifact_type, status, plan_sha256, cell_input_sha256,
bath_sha256, chain_mapping_sha256, qn_gauge, qn_gauge_version, base_sector,
source_sha256, julia_environment_sha256, runtime_versions, execution_target,
wall_seconds, peak_rss_bytes, checkpoint_bytes, checkpoint_write_seconds,
checkpoint_read_seconds, mpo_link_dimensions,
maximum_link_dimensions_by_bond, truncation_max_error,
krylov_max_error_estimate, observable_max_delta, artifact_sha256
```

Reject mixed inputs, missing telemetry, nonfinite values, symlinks, and any
sample above `N_b=6`.

- [ ] **Step 2: Add failing benchmark generation tests**

Use a fake executor with deterministic telemetry. Assert canonical bytes,
independent SHA replay, QN/non-QN ratio calculations, immutable publication,
and that no capability field or allowlist changes.

- [ ] **Step 3: Run RED**

```bash
SKIP_CHALLENGE81_CONVERGENCE_PILOT=1 \
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py \
  -k "qn_benchmark" -q
```

Expected: missing benchmark definition/API.

- [ ] **Step 4: Implement canonical small-bath benchmark publication**

Add `make_qn_benchmark(non_qn_cell, qn_cell, telemetry)` and
`validate_qn_benchmark`. Status is exactly
`"small_bath_validation_only"`. No code path may convert it into
`capability_evidence_sha256`.

- [ ] **Step 5: Run GREEN and commit**

Run Step 3. Expected: all benchmark tests pass.

```bash
git add \
  tracks/mps/solutions/frustration-free/convergence.py \
  tracks/mps/solutions/frustration-free/convergence.schema.json \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py
git commit -m "Record small bath QN resource benchmarks"
```

### Task 11: Complete local verification and local pilot

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/README.md`
- Modify: `tracks/mps/solutions/frustration-free/tests/test_convergence.py`

**Interfaces:**
- Documents exact opt-in behavior and local stopping criteria.

- [ ] **Step 1: Add failing documentation assertions**

Require README text for `direct_star`, `non_qn`, explicit `chain` plus
`qn_dual`, gauge/version, fail-closed probe, and
`QN completion does not unlock N_b=48`.

- [ ] **Step 2: Run RED**

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py \
  -k documentation -q
```

Expected: README assertions fail.

- [ ] **Step 3: Document and run the local pilot**

Document the exact plan command:

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen python \
  tracks/mps/solutions/frustration-free/convergence.py plan \
  --stage pilot --betas 0.2 --bath-sizes 1,2,3,4,5,6 \
  --time-steps 0.04 --cutoffs 1e-14 --maxdims 128 \
  --tau-fractions 0,0.25,0.5,0.75,1 \
  --bath-representation chain --purification-mode qn_dual \
  --output-root /tmp/challenge81-qn-local-pilot
```

Resolve the immutable run from `current.json`, then execute cells sequentially
with `execution-target local`, plan-bound resources, and exact resource SHA
acknowledgment. Publish paired non-QN-chain/QN-chain benchmark records.

Stop immediately if any cell has nonfinite output, failed probe, wrong sector,
checkpoint mismatch, observable delta above `1e-6`, unconverged Krylov update,
truncation above the plan limit, maxdim saturation, RSS above 16 GiB, or wall
time above 600 seconds. Do not continue to a larger bath after a failure.

- [ ] **Step 4: Run complete local suites**

```bash
git diff --check
SKIP_CHALLENGE81_ACCEPTANCE=1 \
SKIP_CHALLENGE81_CONVERGENCE_PILOT=1 \
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest tracks/mps/solutions/frustration-free/tests -q
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/runtests.jl
```

Expected: all checks pass and no tracked/generated result files appear.

- [ ] **Step 5: Commit documentation**

```bash
git add \
  tracks/mps/solutions/frustration-free/README.md \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py
git commit -m "Document QN purification pilots"
```

### Task 12: Run a bounded cluster pilot without unlocking scalability

**Files:**
- No production source changes.
- Generated pilot artifacts remain under a user-selected untracked run root.

**Interfaces:**
- Consumes the locally validated immutable `N_b=6` QN plan/cell.
- Produces cluster telemetry for small-bath validation only.

- [ ] **Step 1: Validate local artifacts before submission**

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen python \
  tracks/mps/solutions/frustration-free/convergence.py validate-existing \
  --plan "$RUN/plan.json" --resources "$RUN/resources.json" \
  --run-directory "$RUN"
```

Expected: validation succeeds and the selected QN cell has `N_b=6`,
chain representation, gauge version 1, and a mapping SHA.

- [ ] **Step 2: Submit exactly one bounded pilot**

Use the site-specific partition/account externally; the repository wrapper
remains profile-neutral:

```bash
RESOURCE_ACK="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["resource_sha256"])' \
  "$RUN/resources.json")"
sbatch --signal=B:USR1@300 --array="$N6_CELL_INDEX" \
  --export=ALL,HARNESS_SOLUTION_DIR="$PWD/tracks/mps/solutions/frustration-free",HARNESS_RUN_SPEC="$RUN/plan.json",HARNESS_RESOURCES="$RUN/resources.json",HARNESS_RESOURCE_ACK="$RESOURCE_ACK",HARNESS_RUN_DIR="$RUN",JULIA_PROJECT="$PWD/tracks/mps/solutions/frustration-free/julia" \
  tracks/mps/solutions/frustration-free/convergence_slurm_array.sh
```

- [ ] **Step 3: Apply cluster stopping criteria**

Stop after this one cell. Require scheduler exit 0 or continuation exit 75 with
a newly validated checkpoint; actual Julia/BLAS threads matching provenance;
MaxRSS within allocation and 16 GiB; checkpoint read/write success; no maxdim
saturation; named truncation/Krylov limits; observable delta at most `1e-6`;
and exact mode/gauge/sector/mapping identity after reload. Any failure blocks
further cluster sizes.

- [ ] **Step 4: Record, but do not allowlist, the benchmark**

Create and validate the `qnBenchmark` record with
`status="small_bath_validation_only"`. Confirm:

```text
scalable_chain_qn_benchmark_validated == false
n_bath_48_execution_validated == false
capability_evidence_sha256 == null
N48_CAPABILITY_ALLOWLIST is empty
```

- [ ] **Step 5: Re-run the N_b=48 refusal test**

```bash
SKIP_CHALLENGE81_CONVERGENCE_PILOT=1 \
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py \
  -k "n48" -q
```

Expected: all local and cluster `N_b=48` executions are refused before
executor entry.

## Separate combined chain+QN scalable gate

Do not fold this gate into the QN implementation commits. A later design and
review must define validated chain mapping beyond `N_b=6`, bounded local then
cluster pilots, a resource envelope, checkpoint continuity, and observable
controls at larger sizes. It must produce one canonical evidence artifact
binding representation, mapping SHA, QN gauge/version/sector, complete runtime
identity, telemetry, and scientific diagnostics. Only after independent review
may a separate commit set both scalable booleans and add that exact digest to
`N48_CAPABILITY_ALLOWLIST`.

## QN phase stopping gate

Stop the phase without claiming completion if any of these is false:

1. direct-star/non-QN remains the default and its regression suite passes;
2. QN mode rejects direct star and stale/missing mappings;
3. reduced identity, grand-canonical thermal trace, labels, MPO flux, and all
   four operator sectors pass;
4. QN-chain matches non-QN direct and ED through `N_b=6`;
5. endpoint, interior, interrupted resume, and corruption tests pass;
6. local pilot and one bounded cluster pilot satisfy named limits;
7. QN small-bath capability is explicit and no scalable claim is made;
8. every `N_b=48` local/cluster attempt is still refused.

