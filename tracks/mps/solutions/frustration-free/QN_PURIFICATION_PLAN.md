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
- Modify: `tracks/mps/solutions/frustration-free/julia/finite_bath_mps_runner.jl`
- Create: `tracks/mps/solutions/frustration-free/julia/test/validated_chain_fixture.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_purification.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl`

**Interfaces:**
- Produces:
  non-exported `ValidatedChainMappingCapability`,
  `PurificationSpec`,
  `non_qn_purification()::PurificationSpec`,
  `qn_dual_purification(parameters::FiniteBathParameters,
  validated::ValidatedChainMappingCapability)::PurificationSpec`,
  `interleaved_sites(parameters::FiniteBathParameters;
  purification::PurificationSpec=non_qn_purification())`, and
  `identity_purification(parameters::FiniteBathParameters;
  purification::PurificationSpec=non_qn_purification())`.
- The old positional calls remain non-QN.
- Replaces `FiniteBathParameters(:chain; raw coefficients and mapping SHA)`
  with `FiniteBathParameters(validated::ValidatedChainMappingCapability;
  U=0.8, epsilon_d=-Float64(U)/2, mu=0.0)`.

- [ ] **Step 1: Add failing specification and label tests**

Generate a schema-1 mapping with the existing Python writer, pass its canonical
bytes and source bath through runner
`validate_chain_mapping_artifact(mapping, mapping_json, bath_artifact)`, and
use the returned capability:

```julia
const QN_GAUGE = "electron_nf_sz_ancilla_particle_hole"
const QN_GAUGE_VERSION = 1

validated = validated_chain_fixture(n_bath = 1)
chain = FiniteBathParameters(validated; U = 0.8, epsilon_d = -0.4, mu = 0.0)
spec = qn_dual_purification(chain, validated)
@test spec.mode === :qn_dual
@test spec.qn_gauge == QN_GAUGE
@test spec.qn_gauge_version == 1
@test (spec.base_sector_nf, spec.base_sector_sz) == (4, 0)
@test_throws ArgumentError qn_dual_purification(
    FiniteBathParameters([0.0], [0.1]), validated
)
@test_throws MethodError FiniteBathParameters(
    :chain;
    epsilon = [0.0],
    V = [0.1],
    chain_onsite = [0.0],
    chain_hopping = Float64[],
    lambda = 0.1,
    mapping_sha256 = repeat("a", 64),
)
```

`validated_chain_fixture.jl` owns that test seam. It creates `bath.json` and
`chain-mapping.json` in `mktempdir` by invoking the locked Python project,
parses both with runner `strict_json_read`, calls the production validator, and
returns only its `ValidatedChainMappingCapability`. It contains no capability
constructor call and no digest/array shortcut.

For every QN site assert `hasqns(site)`, exact `Nf`/`Sz` charges for
`Emp,Up,Dn,UpDn`, and absence of `NfParity`.
Runner tests must validly rehash a corrupted mapping, assert validation throws,
and assert no capability or chain parameters are returned.

- [ ] **Step 2: Add the failing reduced-density test**

For `M=1`, contract the pair to a dense `4x4` coefficient matrix `A` in
physical/ancilla basis order and assert:

```julia
@test A == [
    0 0 0 0.5
    0 0 0.5 0
    0 0.5 0 0
    0.5 0 0 0
]
@test A * A' ≈ Matrix{Float64}(I, 4, 4) / 4 atol = 1e-15
@test norm(psi) ≈ 1.0 atol = 1e-15
@test flux(psi) == QN(("Nf", 2, -1), ("Sz", 0))
terms = [
    ("Emp", "UpDn", 0 + 2, 0 + 0),
    ("Up", "Dn", 1 + 1, 1 - 1),
    ("Dn", "Up", 1 + 1, -1 + 1),
    ("UpDn", "Emp", 2 + 0, 0 + 0),
]
@test all(term -> term[3] == 2 && term[4] == 0, terms)
```

Also assert the four listed amplitudes are `+0.5` and all other entries are
zero, so a valid reduced identity with wrong permutation or phases fails.

- [ ] **Step 3: Run RED**

```bash
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_purification.jl
```

Expected: fail because the validated capability and `PurificationSpec` APIs do
not exist and the raw chain constructor still accepts a fabricated SHA.

- [ ] **Step 4: Implement the minimum QN pair constructor**

Add `ChainMappingValidationSeal`, its private singleton,
`ValidatedChainMappingCapability`, and `PurificationSpec` exactly as specified
in `QN_PURIFICATION_DESIGN.md`. The runner validator calls the sealed inner
constructor only after every existing scientific/provenance check. Remove the
raw chain constructor; no test-only bypass is permitted.

Add the exact purification type:

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
  tracks/mps/solutions/frustration-free/julia/finite_bath_mps_runner.jl \
  tracks/mps/solutions/frustration-free/julia/test/validated_chain_fixture.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_purification.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl
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
- Modify: `tracks/mps/solutions/frustration-free/julia/finite_bath_checkpoint.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl`

**Interfaces:**
- Produces:
  `OperatorSector`,
  `AppliedOperatorBranch`,
  `operator_sector(spec, insertion, spin)`,
  QN-aware `build_finite_bath_context(parameters::FiniteBathParameters;
  purification::PurificationSpec=non_qn_purification())`, and
  `finite_bath_observables(parameters::FiniteBathParameters; beta, tau,
  green_insertion=:creation, time_step=0.05, cutoff=1e-12, maxdim=256,
  krylov_expansion_dim=0, progress=false, checkpoint_manager=nothing,
  resume=nothing, stop_requested=_NEVER_STOP)`.
- Extends `ObservableCursor` with `insertion`; Green cursors bind
  `:creation|:annihilation`, thermal/complete cursors bind `:none`.

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
expected sector.

For an exactly empty creation or annihilation branch, assert:

```julia
result = FiniteBathObservables._apply_impurity_operator(
    blocked_state, sites[1], :up, :creation, expected
)
@test result.status === :zero
@test result.psi === nothing
@test result.log_norm == -Inf
@test result.expected_sector == expected
```

The zero branch must publish a `segment=:terminal` checkpoint with expected
sector metadata, `active_state_present=false`, and no active MPS dataset. It
must perform zero after-operator TDVP steps. Reload/resume validates the
terminal record and advances to the next branch without claiming MPS flux.

- [ ] **Step 2: Add failing creation/annihilation equivalence tests**

At two interior points, run both norm identities with explicit
`green_insertion=:creation` and `green_insertion=:annihilation`; compare values
within `1e-10` at small beta and require distinct expected sectors. Interrupt
each form once after insertion, assert cursor insertion/segment and shifted
sector, HDF5 round-trip it, then resume to the uninterrupted value. Resume an
annihilation checkpoint under a creation request and assert identity mismatch.
Endpoints retain `branch_status=:endpoint_identity`, `insertion=:none`, and
null operator sectors.

- [ ] **Step 3: Run RED**

```bash
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl
```

Expected: missing sector/result types, insertion-bound cursor, and public
annihilation keyword.

- [ ] **Step 4: Implement sector-aware context and branches**

Add `purification` to `FiniteBathContext`, derive
`spin_qn_enabled = purification.mode === :qn_dual`, validate actual flux
immediately after operator application, and include nullable
`operator_sector` in every point diagnostic. Propagate `green_insertion`
through validation, branch duration selection, cursors, resumable data, and
checkpoint serialization. Creation remains the default; annihilation is an
equally executable resumable mode. Implement the zero-amplitude terminal
semantics from the design without constructing or serializing a fictitious MPS.

- [ ] **Step 5: Run GREEN and commit**

Run Step 3. Expected: all observable tests pass.

```bash
git add \
  tracks/mps/solutions/frustration-free/julia/finite_bath_observables.jl \
  tracks/mps/solutions/frustration-free/julia/finite_bath_checkpoint.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl
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

Use a deterministic `StopAfterCursor` callback, never elapsed time or a signal.
It matches the complete tuple
`(kind=:green, tau_index=2, spin=:up, insertion, segment=:after,
completed_steps=1)`, returns `false` until that generation is durably written,
then returns `true` exactly once. Run it separately for `insertion=:creation`
and `:annihilation`, and require `current.json` to name the expected generation
before the observable call reports interruption.

Also interrupt thermal and interior-before positions. Reload every generation
through the production HDF5 loader, assert actual MPS flux equals base or
shifted-sector metadata, then resume to the uninterrupted typed data and
observable values. Validly rehash metadata after corrupting each active-sector
field and require rejection before TDVP. Reject a base-sector MPS under an
after-operator cursor, a shifted-sector MPS under a before cursor, and an
annihilation checkpoint under a creation request.

Write and reload a zero-amplitude `segment=:terminal` generation. Require
expected insertion/spin/sector, `branch_status=:zero`,
`active_state_present=false`, no active MPS HDF5 dataset, and zero
after-operator steps. Reject a terminal record with an MPS, missing expected
sector, nonzero status, or a claimed measured flux.

Expose focused test entry points and run both exact shifted-sector HDF5 resume
commands:

```bash
julia --project=tracks/mps/solutions/frustration-free/julia \
  -e 'include("tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl"); run_shifted_sector_hdf5_resume_test(:creation)'
julia --project=tracks/mps/solutions/frustration-free/julia \
  -e 'include("tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl"); run_shifted_sector_hdf5_resume_test(:annihilation)'
```

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
active `psi` and stored `thermal_psi`. Change
`write_checkpoint_generation(root, identity, cursor,
psi::Union{Nothing,MPS}, resume_state)` so `nothing` is accepted only for a
zero terminal branch; `state.h5` then omits `psi` but must contain
`thermal_psi`.

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
Add `"green_insertion"=>"creation"` to the direct fixture and a QN
`"annihilation"` fixture. Assert request parsing, checkpoint identity, Green
cursors, output settings, and provenance retain the selected insertion.

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
requests. Add exact solver setting `green_insertion`; reject values other than
`creation` and `annihilation`, and pass the validated symbol to resumable
observables.

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
The fixture-side `green_insertion` defaults to `"creation"`; add an explicit
annihilation QN fixture and assert request/output/checkpoint propagation.

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
and existing immutable result path. Parse exact fixture setting
`green_insertion`, defaulting to creation only when the key is absent for old
in-process callers.

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
- Modify: `tracks/mps/solutions/frustration-free/convergence_slurm_array.sh`
- Modify: `tracks/mps/solutions/frustration-free/tests/test_convergence.py`

**Interfaces:**
- `make_plan(; betas=DEFAULT_GRID["betas"], bath_sizes=nothing,
  time_steps=nothing, cutoffs=DEFAULT_GRID["cutoffs"], maxdims=nothing,
  tau_fractions=DEFAULT_GRID["tau_fractions"], stage="production",
  tolerances=nothing, julia_project=JULIA_DIR,
  bath_representation="direct_star", purification_mode="non_qn",
  green_insertion="creation")`.
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
Add parser tests for deterministic pilot-only flags:

```text
--force-interruption-phase green
--force-interruption-insertion annihilation
--force-interruption-spin up
--force-interruption-tau-index 2
--force-interruption-segment after
--force-interruption-completed-steps 1
--require-resume-from-checkpoint
```

The six force fields are all-or-none, accepted only for `stage=pilot`, and
must match the planned `green_insertion`. The runner callback requests shutdown
only after the named shifted-sector step has been durably written and
reload-validated. The first command must return 75. A later command with
`--require-resume-from-checkpoint` must prove it loaded that generation before
doing work.

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
Leave `N48_CAPABILITY_ALLOWLIST = frozenset()`. Add exact plan setting
`green_insertion`, default `"creation"`, and CLI
`--green-insertion {creation,annihilation}`.
Implement the forced-interruption flags and record the force specification,
written generation, and resumed generation in cell telemetry. Update
`convergence_slurm_array.sh` to forward the exact optional environment
variables `HARNESS_FORCE_INTERRUPTION_PHASE`,
`HARNESS_FORCE_INTERRUPTION_INSERTION`, `HARNESS_FORCE_INTERRUPTION_SPIN`,
`HARNESS_FORCE_INTERRUPTION_TAU_INDEX`,
`HARNESS_FORCE_INTERRUPTION_SEGMENT`,
`HARNESS_FORCE_INTERRUPTION_COMPLETED_STEPS`, and
`HARNESS_REQUIRE_RESUME_FROM_CHECKPOINT`. Partial environment configuration
exits before Python.

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
  tracks/mps/solutions/frustration-free/convergence_slurm_array.sh \
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
- Produces canonical `qnPairedBenchmark` artifacts through:
  `make_qn_paired_benchmark(non_qn_cell, qn_cell,
  non_qn_telemetry, qn_telemetry) -> dict[str, Any]`,
  `validate_qn_paired_benchmark(artifact) -> None`, and CLI
  `convergence.py benchmark-qn` plus
  `convergence.py validate-qn-benchmark --benchmark PATH`.
- Does not produce scalable capability evidence and is not allowlist eligible.

- [ ] **Step 1: Add failing benchmark schema tests**

Add the exact `qnPairedBenchmark` schema from
`QN_PURIFICATION_DESIGN.md`: top-level keys are `schema_version`,
`artifact_type`, `status`, `matched_identity`, `matched_work`, `samples`,
`derived`, `selection`, and `artifact_sha256`. `samples` requires both
`non_qn` and `qn_dual`. Each raw sample requires:

```text
plan_sha256, cell_id, cell_input_sha256, result_sha256,
checkpoint_start_generation, checkpoint_end_generation,
purification_mode, wall_seconds, peak_rss_bytes, checkpoint_bytes,
checkpoint_write_seconds, checkpoint_read_seconds, mpo_link_dimensions,
maximum_link_dimensions_by_bond, truncation_max_error,
krylov_max_error_estimate, krylov_all_converged, maxdim_saturated,
observables
```

`observables` has exact keys `n_d`, `double_occupancy`, `G_up`, and `G_down`.
`matched_identity` has exact model, `n_bath`, tau, bath/mapping identity,
chain representation, QN gauge/version/base sector, insertion, numerical
settings, all source hashes, Project/Manifest hashes, runtime versions, and
execution target. `matched_work` has exact thermal step, branch count,
before/after step, completed tau/spin, forced interruption, and resumed
generation counts.

Reject mixed identities/work, absent raw samples, nonfinite or nonpositive
resource denominators, mismatched array lengths, symlinks, and `N_b>6`.

- [ ] **Step 2: Add failing benchmark generation tests**

Use a fake executor with deterministic telemetry. Assert canonical bytes,
independent SHA replay, immutable publication, and these exact formulas:

```python
ratio = lambda key: qn[key] / non_qn[key]
assert derived["wall_seconds_qn_over_non_qn"] == ratio("wall_seconds")
assert derived["peak_rss_qn_over_non_qn"] == ratio("peak_rss_bytes")
assert derived["checkpoint_bytes_qn_over_non_qn"] == ratio("checkpoint_bytes")
assert derived["checkpoint_write_qn_over_non_qn"] == ratio(
    "checkpoint_write_seconds"
)
assert derived["checkpoint_read_qn_over_non_qn"] == ratio(
    "checkpoint_read_seconds"
)
assert derived["maximum_mpo_link_qn_over_non_qn"] == (
    max(qn["mpo_link_dimensions"]) / max(non_qn["mpo_link_dimensions"])
)
assert derived["maximum_mps_link_qn_over_non_qn"] == (
    max(qn["maximum_link_dimensions_by_bond"])
    / max(non_qn["maximum_link_dimensions_by_bond"])
)
```

Compute `observable_max_absolute_delta` over both scalars and every spin/tau
entry. Recompute `scientific_validation_passed` from identity/work equality,
both Krylov booleans, both saturation booleans, named diagnostic limits, and
`delta<=1e-6`. Select the lexicographic minimum of
`(peak_rss_bytes, wall_seconds, checkpoint_bytes)`, with `non_qn` winning a
tie. Assert `production_or_n48_eligible is False` and no capability or
allowlist changes.

- [ ] **Step 3: Run RED**

```bash
SKIP_CHALLENGE81_CONVERGENCE_PILOT=1 \
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py \
  -k "qn_benchmark" -q
```

Expected: missing paired benchmark definition and CLI.

- [ ] **Step 4: Implement canonical small-bath benchmark publication**

Implement the two interfaces and both subcommands. `benchmark-qn` takes exact
arguments:

```text
--non-qn-plan PATH --non-qn-run-directory PATH --non-qn-cell-index INT
--qn-plan PATH --qn-run-directory PATH --qn-cell-index INT
--output-root PATH
```

It independently validates both plans, cells, results, checkpoint generations,
and telemetry; publishes
`OUTPUT_ROOT/qn-paired-benchmark-<artifact_sha256>/benchmark.json` atomically;
then advances canonical `OUTPUT_ROOT/current.json`. Status is exactly
`small_bath_validation_only`. No code path converts its digest into capability
evidence.

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

- [ ] **Step 3: Document exact local execution and benchmark publication**

README must contain these commands verbatim. Create matched chain plans that
differ only in purification mode:

```bash
for MODE in non_qn qn_dual; do
  uv run --project tracks/mps/solutions/frustration-free --frozen python \
    tracks/mps/solutions/frustration-free/convergence.py plan \
    --stage pilot --betas 0.2 --bath-sizes 1,2,3,4,5,6 \
    --time-steps 0.04 --cutoffs 1e-14 --maxdims 128 \
    --tau-fractions 0,0.25,0.5,0.75,1 \
    --bath-representation chain --purification-mode "$MODE" \
    --green-insertion annihilation \
    --output-root "/tmp/challenge81-${MODE}-local-pilot"
done
NON_QN_RUN="/tmp/challenge81-non_qn-local-pilot/$(python3 -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["relative_path"])' \
  /tmp/challenge81-non_qn-local-pilot/current.json)"
QN_RUN="/tmp/challenge81-qn_dual-local-pilot/$(python3 -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["relative_path"])' \
  /tmp/challenge81-qn_dual-local-pilot/current.json)"
for RUN in "$NON_QN_RUN" "$QN_RUN"; do
  ACK="$(python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["resource_sha256"])' \
    "$RUN/resources.json")"
  for CELL_INDEX in 0 1 2 3 4; do
    uv run --project tracks/mps/solutions/frustration-free --frozen python \
      tracks/mps/solutions/frustration-free/convergence.py run-cell \
      --plan "$RUN/plan.json" --run-directory "$RUN" \
      --resources "$RUN/resources.json" --acknowledge-resources "$ACK" \
      --execution-target local \
      --julia-project "$PWD/tracks/mps/solutions/frustration-free/julia" \
      --cell-index "$CELL_INDEX"
  done
done
```

Deterministically interrupt the `N_b=6` cell in the annihilation-up shifted
sector after its first post-insertion step. The expected first exit is exactly
75; then require resume from the durable HDF5 generation:

```bash
for RUN in "$NON_QN_RUN" "$QN_RUN"; do
  ACK="$(python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["resource_sha256"])' \
    "$RUN/resources.json")"
  set +e
  uv run --project tracks/mps/solutions/frustration-free --frozen python \
    tracks/mps/solutions/frustration-free/convergence.py run-cell \
    --plan "$RUN/plan.json" --run-directory "$RUN" \
    --resources "$RUN/resources.json" --acknowledge-resources "$ACK" \
    --execution-target local \
    --julia-project "$PWD/tracks/mps/solutions/frustration-free/julia" \
    --cell-index 5 \
    --force-interruption-phase green \
    --force-interruption-insertion annihilation \
    --force-interruption-spin up --force-interruption-tau-index 2 \
    --force-interruption-segment after \
    --force-interruption-completed-steps 1
  STATUS=$?
  set -e
  test "$STATUS" -eq 75
  uv run --project tracks/mps/solutions/frustration-free --frozen python \
    tracks/mps/solutions/frustration-free/convergence.py run-cell \
    --plan "$RUN/plan.json" --run-directory "$RUN" \
    --resources "$RUN/resources.json" --acknowledge-resources "$ACK" \
    --execution-target local \
    --julia-project "$PWD/tracks/mps/solutions/frustration-free/julia" \
    --cell-index 5 --require-resume-from-checkpoint
done
```

Both forced checkpoints contain an HDF5 active MPS and annihilation-up cursor.
The QN checkpoint additionally has expected sector `(Nf,Sz)=(13,-1)` for
`N_b=6`, and validation reloads that flux before accepting exit 75 or resume;
the non-QN checkpoint requires null QN-sector metadata. Publish and revalidate
the paired benchmark:

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen python \
  tracks/mps/solutions/frustration-free/convergence.py benchmark-qn \
  --non-qn-plan "$NON_QN_RUN/plan.json" \
  --non-qn-run-directory "$NON_QN_RUN" --non-qn-cell-index 5 \
  --qn-plan "$QN_RUN/plan.json" \
  --qn-run-directory "$QN_RUN" --qn-cell-index 5 \
  --output-root /tmp/challenge81-qn-paired-benchmark
BENCHMARK_RUN="/tmp/challenge81-qn-paired-benchmark/$(python3 -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["relative_path"])' \
  /tmp/challenge81-qn-paired-benchmark/current.json)"
uv run --project tracks/mps/solutions/frustration-free --frozen python \
  tracks/mps/solutions/frustration-free/convergence.py validate-qn-benchmark \
  --benchmark "$BENCHMARK_RUN/benchmark.json"
```

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

- [ ] **Step 2: Force one bounded shifted-sector interruption**

Use the site-specific partition/account externally; the repository wrapper
remains profile-neutral:

```bash
N6_CELL_INDEX=5
RESOURCE_ACK="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["resource_sha256"])' \
  "$RUN/resources.json")"
set +e
FORCED_JOB="$(sbatch --wait --parsable --signal=B:USR1@300 \
  --array="$N6_CELL_INDEX" \
  --export=ALL,HARNESS_SOLUTION_DIR="$PWD/tracks/mps/solutions/frustration-free",HARNESS_RUN_SPEC="$RUN/plan.json",HARNESS_RESOURCES="$RUN/resources.json",HARNESS_RESOURCE_ACK="$RESOURCE_ACK",HARNESS_RUN_DIR="$RUN",JULIA_PROJECT="$PWD/tracks/mps/solutions/frustration-free/julia",HARNESS_FORCE_INTERRUPTION_PHASE=green,HARNESS_FORCE_INTERRUPTION_INSERTION=annihilation,HARNESS_FORCE_INTERRUPTION_SPIN=up,HARNESS_FORCE_INTERRUPTION_TAU_INDEX=2,HARNESS_FORCE_INTERRUPTION_SEGMENT=after,HARNESS_FORCE_INTERRUPTION_COMPLETED_STEPS=1 \
  tracks/mps/solutions/frustration-free/convergence_slurm_array.sh)"
FORCED_STATUS=$?
set -e
test "$FORCED_STATUS" -eq 75
test "$(sacct -n -X -j "${FORCED_JOB%%;*}" --format=ExitCode | xargs)" = "75:0"
uv run --project tracks/mps/solutions/frustration-free --frozen python \
  tracks/mps/solutions/frustration-free/convergence.py validate-existing \
  --plan "$RUN/plan.json" --resources "$RUN/resources.json" \
  --run-directory "$RUN"
```

The forced callback, not the scheduler signal, is the expected stop mechanism.
`--signal` remains only a bounded preemption safety net. Validation must find a
new HDF5 generation at annihilation-up `segment=after`, completed step 1, with
actual shifted flux `(Nf,Sz)=(13,-1)`.

- [ ] **Step 3: Require deterministic cluster resume**

```bash
RESUME_JOB="$(sbatch --wait --parsable --signal=B:USR1@300 \
  --array="$N6_CELL_INDEX" \
  --export=ALL,HARNESS_SOLUTION_DIR="$PWD/tracks/mps/solutions/frustration-free",HARNESS_RUN_SPEC="$RUN/plan.json",HARNESS_RESOURCES="$RUN/resources.json",HARNESS_RESOURCE_ACK="$RESOURCE_ACK",HARNESS_RUN_DIR="$RUN",JULIA_PROJECT="$PWD/tracks/mps/solutions/frustration-free/julia",HARNESS_REQUIRE_RESUME_FROM_CHECKPOINT=1 \
  tracks/mps/solutions/frustration-free/convergence_slurm_array.sh
)"
test "$(sacct -n -X -j "${RESUME_JOB%%;*}" --format=ExitCode | xargs)" = "0:0"
uv run --project tracks/mps/solutions/frustration-free --frozen python \
  tracks/mps/solutions/frustration-free/convergence.py validate-existing \
  --plan "$RUN/plan.json" --resources "$RUN/resources.json" \
  --run-directory "$RUN"
```

Stop after this one cell. Require scheduler exit 0 or continuation exit 75 with
a newly validated checkpoint; actual Julia/BLAS threads matching provenance;
MaxRSS within allocation and 16 GiB; checkpoint read/write success; no maxdim
saturation; named truncation/Krylov limits; observable delta at most `1e-6`;
exact mode/gauge/sector/mapping identity after reload; and telemetry proving
the resumed generation equals the forced generation. Any failure blocks
further cluster sizes.

- [ ] **Step 4: Record cluster telemetry without fabricating a pair**

Retain the validated QN cell and forced/resumed generation telemetry as a raw
cluster pilot sample. Do not publish a `qnPairedBenchmark` with
`execution_target="cluster"` unless a separately executed non-QN cluster cell
has the exact matched identity and work required by Task 10. The local paired
benchmark remains the QN-phase comparison artifact. Confirm:

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
