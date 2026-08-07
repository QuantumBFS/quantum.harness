# Finite Star-to-Chain Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, provenance-bound finite star-to-chain bath representation that is equivalent to the existing direct-star ED and non-QN Julia MPS paths.

**Architecture:** Python derives one canonical mapping artifact from the authoritative star bath. Dense ED and Julia consume that same artifact through explicit geometry selection; the direct-star path remains the default. Request, result, checkpoint, acceptance, and convergence schemas bind representation and mapping identity, while the existing `N_b=48` gate remains closed.

**Tech Stack:** Python 3.12.13, NumPy 2.5.1, SciPy 1.18.0, pytest 9.1.1, JSON Schema draft 2020-12, Julia 1.11, ITensors, ITensorMPS, JSON3, SHA, HDF5.

## Global Constraints

- Modify only `tracks/mps/solutions/frustration-free/`.
- Do not modify or generate files under `results/`.
- Do not modify integration/QMC paths or repository-root dependency files.
- Do not submit, cancel, or alter remote jobs.
- The binding star convention is `E = diag(epsilon)`, real componentwise-nonnegative `v`, `lambda = norm(v)`, and `q0 = v/lambda`.
- Use deterministic two-pass fully reorthogonalized Lanczos, nonnegative chain hoppings, and deterministic canonical coordinate deflation.
- For exactly zero `v`, emit the exact identity mapping.
- Apply the same real transform to both spins.
- Compute `Q' * E * Q` before subtracting `mu`.
- Keep the mapping as a separate canonical hash-bound artifact linked to the star bath.
- Direct star is the default; chain requires an explicit request and valid capability.
- Star-to-chain support alone must not set `n_bath_48_execution_validated` or permit `N_b=48`.
- Keep `conserve_qns = false` and `spin_qn_enabled == false`; QN purification is a subsequent plan.
- Run all commands from the repository root
  `/home/footman/code/quantum.harness-challenge-81`.

## Planned file structure

- Create `tracks/mps/solutions/frustration-free/chain_mapping.py`:
  deterministic transform, artifact construction, semantic verification, and
  durable canonical writer.
- Create `tracks/mps/solutions/frustration-free/tests/test_chain_mapping.py`:
  `N_b=1..6` algebra, moments, resolvents, continued fractions, broadened
  bath, deterministic deflation, corruption, and publication tests.
- Modify `tracks/mps/solutions/frustration-free/finite_bath_ed.py`:
  geometry-neutral one-body input and explicit chain consumption.
- Modify `tracks/mps/solutions/frustration-free/tests/test_finite_bath_ed.py`:
  one-particle, sector-spectrum, thermal, and Green-function equivalence.
- Modify `tracks/mps/solutions/frustration-free/julia/finite_bath_purification.jl`:
  explicit parameter representation and chain MPO terms.
- Modify `tracks/mps/solutions/frustration-free/julia/test/finite_bath_purification.jl`:
  chain MPO, matrix, spectra, and non-QN tests.
- Modify `tracks/mps/solutions/frustration-free/julia/finite_bath_mps_runner.jl`:
  schema-3 geometry parsing, mapping verification, provenance, and checkpoint
  identity.
- Modify `tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl`:
  direct/chain parsing, corruption, provenance, and cross-geometry rejection.
- Modify `tracks/mps/solutions/frustration-free/julia/finite_bath_checkpoint.jl`:
  explicit representation and mapping digest in `CheckpointIdentity`.
- Modify `tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl`:
  serialized identity and mismatch coverage.
- Modify `tracks/mps/solutions/frustration-free/julia/finite_bath_observables.jl`:
  propagate geometry diagnostics without changing the evolution algorithm.
- Modify `tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl`:
  direct-star/chain MPS observable equivalence.
- Modify `tracks/mps/solutions/frustration-free/acceptance.py` and
  `tracks/mps/solutions/frustration-free/tests/test_acceptance.py`:
  schema-3 direct default and optional explicit chain fixture.
- Modify `tracks/mps/solutions/frustration-free/convergence.py`,
  `tracks/mps/solutions/frustration-free/convergence.schema.json`, and
  `tracks/mps/solutions/frustration-free/tests/test_convergence.py`:
  explicit representation/capability, mapping-file publication, and retained
  `N_b=48` refusal.
- Modify `tracks/mps/solutions/frustration-free/README.md`:
  document direct default, explicit finite-chain pilot, and the still-closed
  QN/`N_b=48` gate.

---

### Task 1: Deterministic Lanczos transform

**Files:**
- Create: `tracks/mps/solutions/frustration-free/chain_mapping.py`
- Create: `tracks/mps/solutions/frustration-free/tests/test_chain_mapping.py`

**Interfaces:**
- Consumes: a verified schema-2 star bath artifact from `bath.py`.
- Produces:
  `derive_chain_mapping(bath_artifact: dict[str, Any]) -> dict[str, Any]`,
  `verify_chain_mapping_artifact(mapping, bath_artifact) -> None`, and
  `write_chain_mapping_json(path, *, bath_artifact) -> dict[str, Any]`.

- [ ] **Step 1: Write failing transform tests for every size**

Create the test module with a local module loader and these concrete checks:

```python
@pytest.mark.parametrize("n_bath", range(1, 7))
def test_mapping_has_binding_orthogonality_chain_and_coupling_invariants(n_bath):
    star = bath.make_bath_artifact(
        gamma=0.13,
        bandwidth=1.2,
        n_bath=n_bath,
        frequency_grid=[-1.2, 0.0, 1.2],
    )
    mapping = chain.derive_chain_mapping(star)
    payload = mapping["payload"]
    epsilon = np.asarray(star["payload"]["epsilon"])
    coupling = np.asarray(star["payload"]["V"])
    Q = np.asarray(payload["Q"])
    T = Q.T @ np.diag(epsilon) @ Q
    target = np.zeros(n_bath)
    target[0] = np.linalg.norm(coupling)

    assert Q.T @ Q == pytest.approx(np.eye(n_bath), abs=2e-13)
    assert T == pytest.approx(np.triu(np.tril(T, 1), -1), abs=2e-13)
    assert Q.T @ coupling == pytest.approx(target, abs=2e-13)
    assert payload["lambda"] == pytest.approx(np.linalg.norm(coupling))
    assert all(value >= 0.0 for value in payload["chain_hopping"])
    assert chain.verify_chain_mapping_artifact(mapping, star) is None
```

Add exact decoupled and deterministic-deflation fixtures:

```python
def test_zero_coupling_is_exact_identity_mapping():
    star = bath.make_bath_artifact(
        gamma=0.0, bandwidth=1.0, n_bath=6,
        frequency_grid=[-1.0, 0.0, 1.0],
    )
    payload = chain.derive_chain_mapping(star)["payload"]
    assert payload["lambda"] == 0.0
    assert payload["Q"] == np.eye(6).tolist()
    assert payload["chain_onsite"] == star["payload"]["epsilon"]
    assert payload["chain_hopping"] == [0.0] * 5

def test_repeated_energy_breakdown_uses_canonical_deflation():
    star = synthetic_star_artifact(
        epsilon=[-0.5, -0.5, 0.5, 0.5],
        coupling=[0.5, 0.5, 0.0, 0.0],
    )
    first = chain.derive_chain_mapping(star)
    second = chain.derive_chain_mapping(star)
    assert first == second
    assert first["payload"]["deflation_boundaries"]
    assert any(
        first["payload"]["chain_hopping"][index] == 0.0
        for index in first["payload"]["deflation_boundaries"]
    )
```

The test helper `synthetic_star_artifact` must start from
`bath.make_bath_artifact`, replace `epsilon` and `V`, update `n_bath`, and
canonical-rehash the payload. Monkeypatch `bath.verify_bath_artifact` only for
these algorithm fixtures so production artifact verification remains strict.

- [ ] **Step 2: Run the focused tests and confirm the missing module failure**

Run:

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_chain_mapping.py -q
```

Expected: collection fails because `chain_mapping.py` does not exist.

- [ ] **Step 3: Implement validation, Lanczos, and canonical deflation**

Implement these exact module constants and public functions:

```python
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = 1
BREAKDOWN_TOLERANCE_RULE = (
    "64 * eps(float64) * max(1, norm(E, inf)) * n_bath"
)

def _breakdown_tolerance(epsilon: np.ndarray) -> float:
    return float(
        64.0 * np.finfo(np.float64).eps
        * max(1.0, np.linalg.norm(epsilon, ord=np.inf))
        * epsilon.size
    )

def _reorthogonalize(
    vector: np.ndarray, columns: list[np.ndarray]
) -> np.ndarray:
    result = vector.copy()
    for _ in range(2):
        for column in columns:
            result -= float(column @ result) * column
    return result

def _canonical_deflation(
    columns: list[np.ndarray], tolerance: float, size: int
) -> np.ndarray:
    for coordinate in range(size):
        candidate = np.zeros(size, dtype=np.float64)
        candidate[coordinate] = 1.0
        candidate = _reorthogonalize(candidate, columns)
        norm = float(np.linalg.norm(candidate))
        if norm > tolerance:
            candidate /= norm
            first = next(
                index for index, value in enumerate(candidate)
                if abs(value) > tolerance
            )
            if candidate[first] < 0.0:
                candidate *= -1.0
            return candidate
    raise ValueError("canonical deflation could not complete the basis")
```

`_lanczos(epsilon, coupling)` must return `Q`, `T`, `lambda`,
`deflation_boundaries`, and tolerance. Use two reorthogonalization passes,
ascending column order, exact zero block boundaries, deterministic block sign
correction, and direct recomputation `T = Q.T @ np.diag(epsilon) @ Q`.

- [ ] **Step 4: Run transform tests**

Run the Step 2 command.

Expected: all transform, identity, and deflation tests pass.

- [ ] **Step 5: Commit the transform**

```bash
git add \
  tracks/mps/solutions/frustration-free/chain_mapping.py \
  tracks/mps/solutions/frustration-free/tests/test_chain_mapping.py
git commit -m "Add deterministic finite bath chain mapping"
```

### Task 2: Mapping artifact science and integrity

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/chain_mapping.py`
- Modify: `tracks/mps/solutions/frustration-free/tests/test_chain_mapping.py`

**Interfaces:**
- Consumes: Task 1 transform arrays.
- Produces: canonical schema-1 mapping artifacts and durable files suitable for
  Python and Julia consumers.

- [ ] **Step 1: Add failing moments, resolvent, broadening, and corruption tests**

Add the independent moment and complex-resolvent checks:

```python
@pytest.mark.parametrize("n_bath", range(1, 7))
def test_star_and_chain_moments_match_through_twice_size_minus_one(n_bath):
    star, payload, E, v, T = mapped_semicircle(n_bath)
    e0 = np.eye(n_bath)[:, 0]
    for power in range(2 * n_bath):
        left = float(v @ np.linalg.matrix_power(E, power) @ v)
        right = float(
            payload["lambda"] ** 2
            * e0 @ np.linalg.matrix_power(T, power) @ e0
        )
        assert right == pytest.approx(left, abs=4e-12)

@pytest.mark.parametrize("n_bath", range(1, 7))
def test_complex_hybridization_matches_matrix_and_continued_fraction(n_bath):
    star, payload, E, v, T = mapped_semicircle(n_bath)
    for z in (complex(-0.7, 0.03), complex(0.2, 0.11), complex(1.4, 0.5)):
        expected = v @ np.linalg.solve(z * np.eye(n_bath) - E, v)
        matrix_chain = payload["lambda"] ** 2 * np.linalg.inv(
            z * np.eye(n_bath) - T
        )[0, 0]
        continued = continued_fraction(
            z, payload["chain_onsite"], payload["chain_hopping"]
        )
        assert matrix_chain == pytest.approx(expected, abs=3e-12)
        assert payload["lambda"] ** 2 * continued == pytest.approx(
            expected, abs=3e-12
        )
```

Add a broadened test that diagonalizes `T`, forms
`lambda**2 * abs(eigenvectors[0, :])**2`, and reproduces
`broadened_finite_bath_hybridization` on the star artifact's grid and Gaussian
width. Add parametrized validly-rehashed corruptions for `Q`, `lambda`,
`chain_onsite`, `chain_hopping`, `deflation_boundaries`,
`source_bath_sha256`, every convention, every numerics field, and every
provenance field.

Add writer tests that require canonical bytes, file and directory `fsync`,
atomic replacement, rollback, backup cleanup, and rejection of symlink and
directory destinations, matching the transaction cases in `test_bath.py`.

- [ ] **Step 2: Run tests and observe artifact failures**

Run:

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_chain_mapping.py -q
```

Expected: new tests fail because artifact replay, scientific diagnostics, and
durable publication are incomplete.

- [ ] **Step 3: Implement artifact construction, replay verification, and writer**

Use exact payload keys from `CHAIN_QN_DESIGN.md`. Compute diagnostics from
stored arrays, then require them during verification. Verification must derive
a fresh artifact and compare every scientific field, not merely check reported
residuals.

Implement:

```python
def derive_chain_mapping(bath_artifact: dict[str, Any]) -> dict[str, Any]:
    bath.verify_bath_artifact(bath_artifact)
    payload = _mapping_payload(bath_artifact)
    return {
        "payload": payload,
        "sha256": hashlib.sha256(_canonical_json(payload)).hexdigest(),
    }

def verify_chain_mapping_artifact(
    mapping: Any, bath_artifact: dict[str, Any]
) -> None:
    _verify_structure_and_digest(mapping)
    bath.verify_bath_artifact(bath_artifact)
    if mapping["payload"]["source_bath_sha256"] != bath_artifact["sha256"]:
        raise ValueError("mapping source bath SHA256 mismatch")
    expected = derive_chain_mapping(bath_artifact)
    if mapping != expected:
        raise ValueError("mapping scientific replay mismatch")
```

Use the existing `bath.py` durable-write transaction shape, with mapping-
specific error messages and no dependency changes.

- [ ] **Step 4: Run mapping and bath regressions**

Run:

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_chain_mapping.py \
  tracks/mps/solutions/frustration-free/tests/test_bath.py -q
```

Expected: both modules pass.

- [ ] **Step 5: Commit artifact integrity**

```bash
git add \
  tracks/mps/solutions/frustration-free/chain_mapping.py \
  tracks/mps/solutions/frustration-free/tests/test_chain_mapping.py
git commit -m "Bind chain mappings to finite bath artifacts"
```

### Task 3: Dense ED geometry equivalence

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/finite_bath_ed.py`
- Modify: `tracks/mps/solutions/frustration-free/tests/test_finite_bath_ed.py`

**Interfaces:**
- Consumes: star artifact and optional verified mapping artifact.
- Produces: direct-star-default Hamiltonians and observables with explicit
  `bath_representation="chain"` support.

- [ ] **Step 1: Write failing one-particle and many-body equivalence tests**

Add `N_b=1..6` one-particle tests without allocating the full many-body space:

```python
@pytest.mark.parametrize("n_bath", range(1, 7))
def test_one_particle_star_and_chain_are_unitarily_equivalent(n_bath):
    star = _bath_artifact(n_bath=n_bath, gamma=0.13, bandwidth=1.2)
    mapping = chain.derive_chain_mapping(star)
    epsilon_d, mu = -0.31, 0.07
    star_h = ed.build_one_particle_hamiltonian(
        bath_artifact=star, epsilon_d=epsilon_d, mu=mu
    )
    chain_h = ed.build_one_particle_hamiltonian(
        bath_artifact=star,
        chain_mapping_artifact=mapping,
        bath_representation="chain",
        epsilon_d=epsilon_d,
        mu=mu,
    )
    Q = np.asarray(mapping["payload"]["Q"])
    transform = scipy.linalg.block_diag(np.ones((1, 1)), Q)
    assert chain_h == pytest.approx(transform.T @ star_h @ transform, abs=3e-12)
    assert np.linalg.eigvalsh(chain_h) == pytest.approx(
        np.linalg.eigvalsh(star_h), abs=3e-12
    )
```

For every `N_b=1..6`, add fixed-`(N_up,N_down)=(1,1)` sorted spectrum
comparisons for both `U=0` and `U=0.83`; the largest matrix is only 49 by 49
but the interacting impurity state is present. For `N_b=1..3`, additionally
compare every nonempty sector. Add explicit failures for
chain-without-mapping, star-with-mapping, wrong source bath, and unsupported
representation.

- [ ] **Step 2: Run focused ED tests and observe missing geometry APIs**

Run:

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_finite_bath_ed.py \
  -k "chain or one_particle or sector" -q
```

Expected: failures report missing `build_one_particle_hamiltonian` and unknown
geometry keywords.

- [ ] **Step 3: Implement geometry validation and Hamiltonian construction**

Add:

```python
@dataclass(frozen=True)
class FiniteBathGeometry:
    representation: str
    onsite_matrix: np.ndarray
    impurity_coupling: np.ndarray
    source_bath_sha256: str
    mapping_sha256: str | None

def _consume_geometry(
    bath_artifact: dict[str, Any],
    *,
    bath_representation: str,
    chain_mapping_artifact: dict[str, Any] | None,
) -> FiniteBathGeometry:
    consumed = _consume_bath_artifact(bath_artifact)
    if bath_representation == "direct_star":
        if chain_mapping_artifact is not None:
            raise ValueError("direct-star geometry cannot consume a chain mapping")
        return FiniteBathGeometry(
            representation="direct_star",
            onsite_matrix=np.diag(consumed["epsilon"]),
            impurity_coupling=np.asarray(consumed["V"], dtype=np.float64),
            source_bath_sha256=consumed["sha256"],
            mapping_sha256=None,
        )
    if bath_representation != "chain":
        raise ValueError("bath_representation must be direct_star or chain")
    if chain_mapping_artifact is None:
        raise ValueError("chain geometry requires a chain mapping artifact")
    _CHAIN_MODULE.verify_chain_mapping_artifact(
        chain_mapping_artifact, bath_artifact
    )
    mapped = chain_mapping_artifact["payload"]
    onsite = np.diag(np.asarray(mapped["chain_onsite"], dtype=np.float64))
    hopping = np.asarray(mapped["chain_hopping"], dtype=np.float64)
    onsite += np.diag(hopping, 1) + np.diag(hopping, -1)
    impurity = np.zeros(consumed["n_bath"], dtype=np.float64)
    impurity[0] = mapped["lambda"]
    return FiniteBathGeometry(
        representation="chain",
        onsite_matrix=onsite,
        impurity_coupling=impurity,
        source_bath_sha256=consumed["sha256"],
        mapping_sha256=chain_mapping_artifact["sha256"],
    )
```

The direct case uses `diag(epsilon)` and `V`; the chain case imports
`chain_mapping.py`, verifies linkage, builds the tridiagonal `T`, and uses
`lambda` in component zero and exact zeros in all remaining components.
Replace star-specific diagonal/hopping loops in
`build_hamiltonian` with matrix entries from `onsite_matrix` and
`impurity_coupling`. Subtract `mu` only from the diagonal after geometry
construction.

Keep all old keywords and defaults. Add optional representation and mapping
fields to `solve_finite_bath`, `_solve_consumed_bath`, `make_oracle_artifact`,
and `write_oracle_json`. Increment the ED artifact schema and module versions,
and bind representation plus nullable mapping SHA256.

- [ ] **Step 4: Run complete dense ED tests**

Run:

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_finite_bath_ed.py -q
```

Expected: all direct regressions and geometry spectrum tests pass.

- [ ] **Step 5: Commit dense geometry support**

```bash
git add \
  tracks/mps/solutions/frustration-free/finite_bath_ed.py \
  tracks/mps/solutions/frustration-free/tests/test_finite_bath_ed.py
git commit -m "Add chain geometry to finite bath ED"
```

### Task 4: Dense thermal and Green-function equivalence

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/tests/test_finite_bath_ed.py`

**Interfaces:**
- Consumes: Task 3 direct and chain solver paths.
- Produces: scientific equivalence evidence at endpoints and interior tau.

- [ ] **Step 1: Add failing thermal equivalence tests**

```python
@pytest.mark.parametrize("n_bath", range(1, 7))
def test_star_and_chain_thermal_observables_and_green_match(
    n_bath
):
    star = _bath_artifact(n_bath=n_bath, gamma=0.17, bandwidth=1.1)
    mapping = chain.derive_chain_mapping(star)
    beta = 2.3
    tau = [0.0, 0.37, 1.41, beta]
    common = dict(
        bath_artifact=star,
        U=0.0,
        epsilon_d=-0.29,
        mu=0.06,
        beta=beta,
        tau=tau,
    )
    direct = ed.solve_finite_bath(**common)
    transformed = ed.solve_finite_bath(
        **common,
        bath_representation="chain",
        chain_mapping_artifact=mapping,
    )
    assert transformed["logZ"] == pytest.approx(direct["logZ"], abs=4e-12)
    assert transformed["occupancy"] == pytest.approx(
        direct["occupancy"], abs=4e-12
    )
    assert transformed["double_occupancy"] == pytest.approx(
        direct["double_occupancy"], abs=4e-12
    )
    for spin in ("up", "down", "average"):
        assert transformed["green_function"][spin] == pytest.approx(
            direct["green_function"][spin], abs=5e-12
        )
```

Assert separately that index 0 and index -1 satisfy the endpoint identities
and indices 1 and 2 are true interior points. This all-size test must use the
one-particle Fermi-matrix ED path so it does not weaken the dense-memory guard.
Add a second parametrized test for `N_b=1..3` with `U=0.8` through the
production full-Fock ED solver and the same endpoint/interior grid.

- [ ] **Step 2: Run the new test and confirm any propagation gaps**

Run:

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_finite_bath_ed.py \
  -k "thermal_observables_and_green" -q
```

Expected: fail if any solver or artifact path still drops geometry.

- [ ] **Step 3: Propagate geometry through every ED solve and verifier path**

Ensure `_solve_consumed_bath` receives a validated `FiniteBathGeometry` and
that `verify_oracle_artifact` recomputes with the serialized representation and
mapping artifact. The direct artifact must serialize `mapping_input: null` and
`mapping_input_sha256: null`; chain must embed and hash-bind the complete
mapping.

- [ ] **Step 4: Run all Python mapping, bath, and ED tests**

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_chain_mapping.py \
  tracks/mps/solutions/frustration-free/tests/test_bath.py \
  tracks/mps/solutions/frustration-free/tests/test_finite_bath_ed.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit ED equivalence evidence**

```bash
git add \
  tracks/mps/solutions/frustration-free/finite_bath_ed.py \
  tracks/mps/solutions/frustration-free/tests/test_finite_bath_ed.py
git commit -m "Verify star and chain thermal equivalence"
```

### Task 5: Julia chain parameter and MPO support

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/julia/finite_bath_purification.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_purification.jl`

**Interfaces:**
- Consumes: explicit star or chain coefficients.
- Produces: a shared non-QN site layout and geometry-specific MPO.

- [ ] **Step 1: Write failing Julia chain MPO tests**

Add a constructor test and a matrix-element test:

```julia
@testset "explicit finite chain parameters preserve non-QN sites" begin
    parameters = FiniteBathParameters(
        :chain;
        epsilon = [-0.4, 0.2, 0.7],
        V = [0.31, 0.0, 0.0],
        chain_onsite = [-0.4, 0.2, 0.7],
        chain_hopping = [0.13, 0.09],
        lambda = 0.31,
        mapping_sha256 = repeat("a", 64),
        U = 0.8,
        epsilon_d = -0.4,
        mu = 0.07,
    )
    sites = interleaved_sites(parameters)
    @test parameters.bath_representation === :chain
    @test all(!hasqns(site) for site in sites)
    @test length(sites) == 8
end
```

Construct occupation-product MPS states that isolate impurity-to-chain-site-1,
chain-site-1-to-2, and chain-site-2-to-3 hops, with both even and odd
intervening fermion parity. Compare matrix elements to `lambda`,
`chain_hopping[1]`, and `chain_hopping[2]` with their Jordan-Wigner signs.

Build independent dense star and chain matrices for every `N_b=1..6`, `U in
(0.0, 0.8)`, and compare sorted spectra in the `(1,1)` sector. For
`N_b=1..3`, additionally compare every nonempty `(N_up,N_down)` sector.

- [ ] **Step 2: Run the Julia purification test and observe constructor failure**

Run:

```bash
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_purification.jl
```

Expected: chain constructor and representation fields are undefined.

- [ ] **Step 3: Extend parameters, MPO terms, and norm bound**

Add fields:

```julia
struct FiniteBathParameters
    epsilon::Vector{Float64}
    V::Vector{Float64}
    U::Float64
    epsilon_d::Float64
    mu::Float64
    bath_representation::Symbol
    chain_onsite::Vector{Float64}
    chain_hopping::Vector{Float64}
    lambda::Float64
    mapping_sha256::Union{Nothing,String}
end
```

Keep the current positional constructor direct-star. Add the explicit
`:chain` constructor with exact length checks:

```julia
length(chain_onsite) == length(epsilon)
length(chain_hopping) == max(0, length(epsilon) - 1)
length(V) == length(epsilon)
V == [lambda; zeros(length(V) - 1)]
all(>=(0.0), chain_hopping)
```

In `physical_hamiltonian_mpo`, branch only term assembly. Chain bath physical
sites remain `3, 5, 7, ...`; add nearest-neighbor chain terms and one impurity
link. In `_hamiltonian_norm_bound`, sum selected onsite absolute values and
four times each selected hopping, including `lambda`.

- [ ] **Step 4: Run Julia purification tests**

Run the Step 2 command.

Expected: direct-star regressions, matrix elements, Hermiticity, and sector
spectra pass.

- [ ] **Step 5: Commit Julia chain MPO support**

```bash
git add \
  tracks/mps/solutions/frustration-free/julia/finite_bath_purification.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_purification.jl
git commit -m "Add finite chain MPO geometry"
```

### Task 6: Runner schema and mapping consumption

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/julia/finite_bath_mps_runner.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl`

**Interfaces:**
- Consumes: runner schema-3 `bath_geometry` and canonical mapping bytes.
- Produces: validated `FiniteBathParameters`, mapping-aware output provenance,
  and mapping-aware checkpoint identity.

- [ ] **Step 1: Write failing direct and chain request tests**

Change `minimal_runner_request` to schema 3 and include:

```julia
"bath_geometry" => Dict(
    "representation" => "direct_star",
    "chain_mapping_artifact_json" => nothing,
    "chain_mapping_artifact_file_sha256" => nothing,
)
```

Add `chain_runner_request()` that runs Python
`chain_mapping.write_chain_mapping_json` in a temporary directory, embeds the
canonical bytes, sets `representation = "chain"`, and computes the file
SHA256. Assert:

```julia
direct = read_request(direct_path)
chain = read_request(chain_path)
@test direct.parameters.bath_representation === :direct_star
@test direct.mapping_sha256 === nothing
@test chain.parameters.bath_representation === :chain
@test chain.mapping_sha256 == chain_mapping["sha256"]
@test chain.parameters.mapping_sha256 == chain.mapping_sha256
```

Add failures for absent mapping, mapping on direct-star, wrong mapping file
hash, wrong payload hash, wrong source bath SHA256, noncanonical mapping JSON,
negative chain hopping, and unsupported representation.

- [ ] **Step 2: Run runner tests and confirm schema-2 assumptions fail**

Run:

```bash
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl
```

Expected: schema/key validation and geometry parsing tests fail.

- [ ] **Step 3: Implement strict schema-3 mapping validation**

Set `RUNNER_SCHEMA_VERSION = 3` and increment `RUNNER_VERSION`. Add
`bath_geometry` to the exact request payload keys. Implement Julia-side
scientific consumption checks, not mapping derivation:

```julia
function validate_chain_mapping_artifact(
    mapping_artifact, mapping_json, bath_artifact
)
    # exact keys and canonical file bytes
    # payload/file SHA256 checks
    # source bath linkage
    # finite dimensions and nonnegative hopping
    # Q'Q, Q'diag(epsilon)Q, and Q'V invariants
    # transform-before-mu convention equality
end
```

Construct chain `FiniteBathParameters` only after validation. Add
`bath_representation` and nullable `chain_mapping_sha256` to solver settings,
diagnostics, and provenance. Add `chain_mapping.py` to source hash maps in
runner request fixtures.

- [ ] **Step 4: Run runner and purification tests**

```bash
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_purification.jl
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl
```

Expected: both pass.

- [ ] **Step 5: Commit runner mapping consumption**

```bash
git add \
  tracks/mps/solutions/frustration-free/julia/finite_bath_mps_runner.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl
git commit -m "Validate chain mappings in the Julia runner"
```

### Task 7: Cross-geometry checkpoint identity

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/julia/finite_bath_checkpoint.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/finite_bath_mps_runner.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl`

**Interfaces:**
- Consumes: representation and nullable mapping SHA256 from Task 6.
- Produces: checkpoint metadata that cannot cross geometry.

- [ ] **Step 1: Write failing cross-geometry rejection tests**

Create otherwise identical identities:

```julia
direct_identity = CheckpointIdentity(;
    common...,
    bath_representation = "direct_star",
    chain_mapping_sha256 = nothing,
)
chain_identity = CheckpointIdentity(;
    common...,
    bath_representation = "chain",
    chain_mapping_sha256 = repeat("a", 64),
)
```

Write a generation with `direct_identity`, then assert
`load_current_checkpoint(root, chain_identity)` throws
`ArgumentError("checkpoint identity mismatch")`. Repeat in the opposite
direction. Add constructor failures for unsupported representation,
direct-star with mapping SHA256, and chain with null mapping SHA256.

- [ ] **Step 2: Run checkpoint tests and observe missing fields**

Run:

```bash
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl
```

Expected: `CheckpointIdentity` rejects unknown geometry keywords.

- [ ] **Step 3: Extend checkpoint identity and runner binding**

Add:

```julia
bath_representation::String
chain_mapping_sha256::Union{Nothing,String}
```

to `CheckpointIdentity`, `_identity_dict`, `_identity_from_dict`, equality, and
validation. In runner `checkpoint_identity(request)`, source both values from
the validated request. The whole request digest remains bound as defense in
depth.

- [ ] **Step 4: Run checkpoint and runner tests**

```bash
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl
```

Expected: checkpoint serialization, same-geometry resume, and both
cross-geometry rejection directions pass.

- [ ] **Step 5: Commit geometry-bound checkpoints**

```bash
git add \
  tracks/mps/solutions/frustration-free/julia/finite_bath_checkpoint.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl \
  tracks/mps/solutions/frustration-free/julia/finite_bath_mps_runner.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl
git commit -m "Reject cross-geometry MPS checkpoints"
```

### Task 8: Julia MPS observable equivalence

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/julia/finite_bath_observables.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl`

**Interfaces:**
- Consumes: geometry-aware `FiniteBathParameters`.
- Produces: shared direct/chain thermal and Green results with explicit
  geometry diagnostics and no QNs.

- [ ] **Step 1: Add failing MPS equivalence tests**

Generate Python mapping fixtures for every `N_b=1..6`, then run the same Julia
test body for each fixture. Use `beta=0.04`, `time_step=0.04`,
`krylov_expansion_dim=0`, and `maxdim=128` for the all-size bounded check.
Keep the existing two-site acceptance settings as an additional stricter
fixture. The core test body is:

```julia
function chain_fixtures()
    gamma = 0.1
    bandwidth = 1.0
    return [
        (;
            n_bath,
            epsilon = [
                bandwidth * cos(k * pi / (n_bath + 1))
                for k in 1:n_bath
            ],
            coupling = [
                sqrt(
                    gamma * bandwidth / (n_bath + 1) *
                    sin(k * pi / (n_bath + 1))^2
                )
                for k in 1:n_bath
            ],
            lambda = sqrt(gamma * bandwidth / 2),
            chain_onsite = zeros(n_bath),
            chain_hopping = fill(bandwidth / 2, max(0, n_bath - 1)),
            mapping_sha256 = repeat(string(n_bath), 64)[1:64],
        )
        for n_bath in 1:6
    ]
end

@testset "direct star and finite chain MPS observables agree" begin
    for fixture in chain_fixtures()
        beta = fixture.n_bath <= 2 ? 0.5 : 0.04
        tau = [0.0, beta / 4, beta / 2, 3 * beta / 4, beta]
        direct = FiniteBathParameters(
            fixture.epsilon,
            fixture.coupling;
            U = 0.8,
            epsilon_d = -0.4,
            mu = 0.0,
        )
        transformed = FiniteBathParameters(
            :chain;
            epsilon = fixture.epsilon,
            V = [fixture.lambda; zeros(fixture.n_bath - 1)],
            chain_onsite = fixture.chain_onsite,
            chain_hopping = fixture.chain_hopping,
            lambda = fixture.lambda,
            mapping_sha256 = fixture.mapping_sha256,
            U = 0.8,
            epsilon_d = -0.4,
            mu = 0.0,
        )
        settings = (
            beta = beta,
            tau = tau,
            time_step = fixture.n_bath <= 2 ? 0.02 : 0.04,
            cutoff = 1.0e-14,
            maxdim = 128,
            krylov_expansion_dim = fixture.n_bath <= 2 ? 32 : 0,
        )
        star_result = finite_bath_observables(direct; settings...)
        chain_result = finite_bath_observables(transformed; settings...)
        @test chain_result.n_d ≈ star_result.n_d atol = 1.0e-6
        @test chain_result.double_occupancy ≈
              star_result.double_occupancy atol = 1.0e-6
        @test chain_result.G_up ≈ star_result.G_up atol = 1.0e-6
        @test chain_result.G_dn ≈ star_result.G_dn atol = 1.0e-6
        @test chain_result.G_up[[1, end]] ≈
              star_result.G_up[[1, end]] atol = 1.0e-6
        @test chain_result.G_up[2:(end - 1)] ≈
              star_result.G_up[2:(end - 1)] atol = 1.0e-6
    end
end
```

Assert both contexts have `spin_qn_enabled == false`, chain diagnostics report
`:chain`, direct diagnostics report `:direct_star`, and the same transform is
used for both spin branches.

- [ ] **Step 2: Run observable tests and observe missing diagnostics**

Run:

```bash
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl
```

Expected: numerical paths may run, but geometry diagnostics/provenance tests
fail until propagation is implemented.

- [ ] **Step 3: Propagate geometry without branching the evolution engine**

Add `bath_representation` and `chain_mapping_sha256` to context/result
diagnostics and provenance. Do not duplicate `_evolve_normalized_state`,
Green-branch, endpoint, or resume logic. Keep:

```julia
spin_qn_enabled = false
```

for both representations.

- [ ] **Step 4: Run all Julia tests**

```bash
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/runtests.jl
```

Expected: all Julia tests pass, including endpoints, interior tau, resume, and
runner integration.

- [ ] **Step 5: Commit MPS equivalence**

```bash
git add \
  tracks/mps/solutions/frustration-free/julia/finite_bath_observables.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl
git commit -m "Verify star and chain MPS observables"
```

### Task 9: Acceptance request defaults and provenance

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/acceptance.py`
- Modify: `tracks/mps/solutions/frustration-free/tests/test_acceptance.py`

**Interfaces:**
- Consumes: direct-star fixture by default; optional explicit chain fixture for
  focused tests.
- Produces: schema-3 requests and mapping-aware expected provenance.

- [ ] **Step 1: Write failing direct-default and explicit-chain tests**

Assert:

```python
fixture = acceptance.acceptance_fixture()
assert fixture["solver_settings"]["bath_representation"] == "direct_star"
direct = acceptance._make_mps_request(bath_json, fixture)
direct_payload = acceptance.strict_json_loads(direct["payload_json"])
assert direct_payload["bath_geometry"] == {
    "representation": "direct_star",
    "chain_mapping_artifact_json": None,
    "chain_mapping_artifact_file_sha256": None,
}
```

Create a mapping file with `chain_mapping.write_chain_mapping_json`, pass its
bytes through an explicit chain fixture, and assert exact canonical embedding,
file SHA256, payload SHA256, solver setting, expected runner provenance, and
ED chain oracle linkage. Add fail-closed request tests for inconsistent
representation/mapping combinations.

- [ ] **Step 2: Run acceptance tests and observe schema/provenance failures**

Run:

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_acceptance.py -q
```

Expected: request exact-key and expected-provenance assertions fail.

- [ ] **Step 3: Evolve acceptance request and verification**

Set `RUNNER_SCHEMA_VERSION = 3`, increment `MODULE_VERSION`, include
`bath_geometry`, and add `bath_representation` to solver settings. Update
`expected_runner_provenance` and `verify_mps_output` with nullable
`chain_mapping_sha256` plus the `chain_mapping.py` source SHA256.

Keep `acceptance_fixture()` direct-star. Add an internal explicit chain helper
used only by focused tests; do not change the established acceptance run or
its result path.

- [ ] **Step 4: Run acceptance tests without generating results**

```bash
SKIP_CHALLENGE81_ACCEPTANCE=1 \
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_acceptance.py -q
```

Expected: all non-result-generating acceptance tests pass; the real acceptance
test is skipped by the explicit environment variable.

- [ ] **Step 5: Commit direct-default request evolution**

```bash
git add \
  tracks/mps/solutions/frustration-free/acceptance.py \
  tracks/mps/solutions/frustration-free/tests/test_acceptance.py
git commit -m "Add explicit chain requests to acceptance"
```

### Task 10: Convergence capability and closed N_b=48 gate

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/convergence.py`
- Modify: `tracks/mps/solutions/frustration-free/convergence.schema.json`
- Modify: `tracks/mps/solutions/frustration-free/tests/test_convergence.py`

**Interfaces:**
- Consumes: explicit `bath_representation` plan selection.
- Produces: hash-bound chain mapping files for finite validation cells, while
  retaining the hard `N_b=48` refusal.

- [ ] **Step 1: Write failing plan, schema, publication, and gate tests**

Add:

```python
def test_plan_defaults_to_direct_star_and_chain_is_explicit():
    direct = _plan(betas=[0.2], bath_sizes=[2], stage="pilot")
    chain_plan = _plan(
        betas=[0.2],
        bath_sizes=[2],
        stage="pilot",
        bath_representation="chain",
    )
    assert direct["solver_capability"]["default_bath_representation"] == (
        "direct_star"
    )
    assert direct["cells"][0]["solver_settings"]["bath_representation"] == (
        "direct_star"
    )
    assert chain_plan["cells"][0]["solver_settings"]["bath_representation"] == (
        "chain"
    )
    assert chain_plan["cells"][0]["chain_mapping_artifact"]["payload"][
        "source_bath_sha256"
    ] == chain_plan["cells"][0]["bath_artifact_sha256"]
```

Add schema rejection for unknown capability/mapping fields. Run a chain pilot
with a fake executor and require published files to be exactly:

```python
{"bath.json", "chain-mapping.json", "mps-input.json", "mps-result.json",
 "cell.json"}
```

For both local and cluster targets, construct a chain `N_b=48` plan with
`finite_chain_mapping_validated = True` but
`qn_purification_validated = False` and
`n_bath_48_execution_validated = False`; assert the executor is never called
and the error contains `solver capability`.

- [ ] **Step 2: Run focused convergence tests and observe schema failures**

Run:

```bash
SKIP_CHALLENGE81_CONVERGENCE_PILOT=1 \
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py \
  -k "representation or chain_mapping or n48 or solver_capability" -q
```

Expected: chain plan arguments and schema fields are unsupported.

- [ ] **Step 3: Implement explicit capability and conditional mapping files**

Update `make_plan(..., bath_representation="direct_star")`. Use the exact
capability object from `CHAIN_QN_DESIGN.md`. Chain cells derive a mapping and
include its artifact and SHA256 in `input_sha256`; direct cells serialize null
mapping fields.

Update `_source_hashes` for `chain_mapping.py`. Update
`_runner_request_for_cell`, staging, cell artifact hashes, immutable validation,
and schemas so `chain-mapping.json` is required only for chain cells.

Keep `_n48_solver_capability_is_valid` fail-closed:

```python
return (
    capability["default_bath_representation"] == "direct_star"
    and capability["finite_chain_mapping_validated"] is True
    and capability["qn_purification_validated"] is True
    and capability["n_bath_48_execution_validated"] is True
    and capability["capability_evidence_sha256"] in N48_CAPABILITY_ALLOWLIST
)
```

The allowlist remains empty in this phase.

- [ ] **Step 4: Run convergence tests without launching pilots**

```bash
SKIP_CHALLENGE81_CONVERGENCE_PILOT=1 \
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py -q
```

Expected: all tests pass and every `N_b=48` execution test remains refused.

- [ ] **Step 5: Commit capability and schema changes**

```bash
git add \
  tracks/mps/solutions/frustration-free/convergence.py \
  tracks/mps/solutions/frustration-free/convergence.schema.json \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py
git commit -m "Add finite chain convergence capability"
```

### Task 11: Full provenance corruption matrix

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/tests/test_chain_mapping.py`
- Modify: `tracks/mps/solutions/frustration-free/tests/test_acceptance.py`
- Modify: `tracks/mps/solutions/frustration-free/tests/test_convergence.py`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl`

**Interfaces:**
- Consumes: all prior integrity boundaries.
- Produces: exhaustive fail-closed evidence for rehashed semantic corruption
  and cross-geometry replay.

- [ ] **Step 1: Add parametrized corruption tests**

The Python mapping test must mutate and canonical-rehash each of:

```text
source_bath_sha256
source_bath_schema_version
n_bath
representation
lambda
Q
chain_onsite
chain_hopping
deflation_boundaries
every conventions key/value
algorithm
breakdown_tolerance
breakdown_tolerance_rule
orthogonality_max_error
off_tridiagonal_max_abs
coupling_max_error
every provenance key/value
```

Acceptance and convergence tests must corrupt mapping file bytes, embedded
bytes, mapping payload SHA256, mapping file SHA256, cell mapping SHA256, source
hash, representation, and capability, then assert rejection before executor
entry or pointer advancement.

Julia tests must cover both direct-to-chain and chain-to-direct checkpoint
replay plus a mapping with a valid outer digest but corrupted scientific
arrays.

- [ ] **Step 2: Run corruption-focused tests and confirm uncovered paths fail**

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_chain_mapping.py \
  tracks/mps/solutions/frustration-free/tests/test_acceptance.py \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py \
  -k "corrupt or tamper or provenance or cross_geometry" -q
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl
```

Expected: any semantic field not independently replayed exposes a failing test.

- [ ] **Step 3: Close every uncovered validation path**

Make verifiers require exact key sets and replay every derived field. No
verifier may trust stored residual diagnostics or a valid outer SHA256 as
scientific proof. Ensure publication and checkpoint pointer updates occur only
after all mapping and geometry checks succeed.

- [ ] **Step 4: Re-run the corruption commands**

Expected: all pass.

- [ ] **Step 5: Commit fail-closed provenance coverage**

```bash
git add \
  tracks/mps/solutions/frustration-free/tests/test_chain_mapping.py \
  tracks/mps/solutions/frustration-free/tests/test_acceptance.py \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl
git commit -m "Close chain mapping provenance validation"
```

### Task 12: Documentation and complete local verification

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/README.md`

**Interfaces:**
- Consumes: completed finite-chain behavior.
- Produces: exact user commands and an explicit boundary before QN work.

- [ ] **Step 1: Add failing documentation assertions**

In `tests/test_convergence.py`, assert README contains:

```python
readme = (SOLUTION_DIR / "README.md").read_text(encoding="utf-8")
assert "direct_star" in readme
assert "bath_representation chain" in readme
assert "QN purification is not implemented" in readme
assert "does not unlock N_b=48" in readme
```

- [ ] **Step 2: Run the documentation assertion**

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py \
  -k "documentation" -q
```

Expected: fail until README states the new contract.

- [ ] **Step 3: Document direct and explicit finite-chain pilots**

Add one direct-default example and one explicit chain pilot command using:

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen python \
  tracks/mps/solutions/frustration-free/convergence.py plan \
  --stage pilot --betas 0.2 --bath-sizes 2 --time-steps 0.1 \
  --maxdims 32 --bath-representation chain \
  --output-root /tmp/challenge81-chain-pilot
```

State that this command derives a finite mapping artifact, remains non-QN, and
does not unlock `N_b=48`. Do not run the command in this task because it
creates a run bundle.

- [ ] **Step 4: Run complete local verification**

Run documentation-safe checks first:

```bash
git diff --check
python3 - <<'PY'
from pathlib import Path
for name in ("CHAIN_QN_DESIGN.md", "CHAIN_QN_PLAN.md", "README.md"):
    text = (
        Path("tracks/mps/solutions/frustration-free") / name
    ).read_text(encoding="utf-8")
    assert "\t" not in text
    assert text.endswith("\n")
print("documentation checks passed")
PY
```

Then run the complete local suites without result-generating acceptance or
pilot execution:

```bash
SKIP_CHALLENGE81_ACCEPTANCE=1 \
SKIP_CHALLENGE81_CONVERGENCE_PILOT=1 \
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest tracks/mps/solutions/frustration-free/tests -q
julia --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/runtests.jl
```

Expected: documentation checks print `documentation checks passed`; all Python
and Julia tests pass; no files appear under `results/`.

- [ ] **Step 5: Commit documentation**

```bash
git add tracks/mps/solutions/frustration-free/README.md
git commit -m "Document explicit finite chain execution"
```

## Phase completion gate

Before beginning a separate QN purification design:

1. `git status --short` contains no generated result or dependency changes.
2. Direct-star requests remain byte-deterministic under schema 3 and are still
   the default.
3. Mapping tests pass for every `N_b=1..6`, including moments through
   `2*N_b-1`, complex continued fractions, and broadened bath equivalence.
4. Python one-particle, interacting-sector, thermal, endpoint, and interior
   Green-function equivalence tests pass.
5. Julia MPO/MPS equivalence and cross-geometry checkpoint rejection pass.
6. Provenance corruption fails even after valid outer rehashing.
7. Both local and cluster `N_b=48` execution remain forbidden.
8. `spin_qn_enabled == false` remains asserted for both representations.

The next phase gets a separate design and plan for QN-conserving purification,
QN-compatible local identity pairs, operator-sector Green branches, and
scalable capability evidence. It must not be folded into this implementation.
