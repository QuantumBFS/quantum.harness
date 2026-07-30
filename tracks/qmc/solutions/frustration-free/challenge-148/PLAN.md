# Challenge #148 QMC Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible two-code QMC workflow, anchored by exact small-system calculations, that can determine whether the triangular-to-honeycomb TFIM critical-field ratio is compatible with `sqrt(5)` at the challenge precision.

**Architecture:** A solution-local Python package owns graph generation, exact diagonalization, artifact integrity, acceptance tests, finite-size analysis and cluster planning. An owned Rust executable linked to pinned QMC_SSE is the primary solver. An owned Julia wrapper directly calling pinned QMC_LTFIM's current library API is the independent solver; it bypasses the broken upstream CLI and general-constructor paths without modifying upstream. Both consume hash-verified canonical graph JSON but independently construct and measure their Pauli-normalized Hamiltonians.

**Tech Stack:** Python 3.12.13, NumPy, SciPy, h5py, jsonschema, pytest, Rust 2024 edition, QMC_SSE revision `35f100af856f3273cc67d31962f3e67f801b0c37`, Julia 1.11.6, QMC_LTFIM revision `524860b9c0e212ac630b0d9754075bb24198da3b`, Slurm.

## Global Constraints

- Work only under `tracks/qmc/solutions/frustration-free/challenge-148/`; write run products only under `tracks/qmc/results/frustration-free/challenge-148/`.
- Do not modify root `pyproject.toml`, root `uv.lock`, shared scripts, or the QMC team README.
- Use `H = -J sum sigma_z sigma_z - h sum sigma_x`, `J = 1`, Pauli eigenvalues `+1/-1`, periodic boundaries, and bonds counted once.
- Use triangular `N=L^2`, degree 6, `3N` bonds and honeycomb `N=2L^2`, degree 3, `3N/2` bonds.
- Use `Q_L = <m^2>^2/<m^4>` with `m = sum sigma_z/N`.
- Full thermal ED is local-only for guarded dimensions no larger than `2^12`; sparse ground-state ED may extend to `N=20` after an explicit memory estimate.
- No non-trivial local computation may exceed ten estimated minutes or 16 GiB; larger work uses the active Slurm profile with `ch148-` job names.
- Use TDD for every numerical, publication and adapter behavior; every task ends in a focused commit that stages only owned paths.
- Both adapters must verify canonical graph hashes, use deterministic distinct seeds, preserve immutable raw bins, and separately pass ED acceptance for energy, transverse magnetization, `m²`, `m⁴`, and Binder ratio before pilot work.
- QMC_SSE is `GPL-3.0-only`; QMC_LTFIM is `Apache-2.0`. Adapter distribution and provenance must retain those license facts.
- Never accept partial, stale, non-finite, hash-mismatched or unconverged output as a completed result.

---

### Task 1: Pin local environments and source provenance

**Files:**
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/.python-version`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/pyproject.toml`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/uv.lock`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/references/SOURCES.json`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/__init__.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/provenance.py`
- Test: `tracks/qmc/solutions/frustration-free/challenge-148/tests/test_provenance.py`

**Interfaces:**
- Produces: `canonical_json(value: object) -> bytes`
- Produces: `sha256_file(path: Path) -> str`
- Produces: `verify_source_manifest(path: Path, external_root: Path) -> dict`
- Source entries contain `name`, `kind`, `url`, `revision` or `sha256`, `license`, and `local_relative_path`.

- [ ] **Step 1: Write manifest-verification tests**

```python
def test_source_manifest_binds_pdf_hashes_and_repository_revisions(tmp_path):
    manifest = load_fixture_manifest(tmp_path)
    verified = provenance.verify_source_manifest(
        manifest, tmp_path / ".external" / "challenge-148"
    )
    assert verified["valid"] is True
    assert verified["sources"]["QMC_SSE"]["revision"] == (
        "35f100af856f3273cc67d31962f3e67f801b0c37"
    )
    assert verified["sources"]["QMC_LTFIM"]["revision"] == (
        "524860b9c0e212ac630b0d9754075bb24198da3b"
    )


def test_source_manifest_rejects_hash_or_revision_drift(tmp_path):
    manifest = load_fixture_manifest(tmp_path)
    (tmp_path / ".external/challenge-148/papers/reference.pdf").write_bytes(b"drift")
    with pytest.raises(ValueError, match="source integrity mismatch"):
        provenance.verify_source_manifest(manifest, tmp_path / ".external/challenge-148")
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
uv run --project tracks/qmc/solutions/frustration-free/challenge-148 \
  python -m pytest tracks/qmc/solutions/frustration-free/challenge-148/tests/test_provenance.py -q
```

Expected: import or missing-function failure.

- [ ] **Step 3: Add the solution-local Python project and minimal provenance implementation**

Use Python `==3.12.13` and pin direct dependencies:

```toml
[project]
name = "challenge148"
version = "0.1.0"
requires-python = "==3.12.13"
dependencies = [
  "h5py==3.14.0",
  "jsonschema==4.26.0",
  "matplotlib==3.10.9",
  "numpy==2.2.6",
  "pytest==9.1.1",
  "scipy==1.15.3",
]

[build-system]
requires = ["hatchling==1.27.0"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/challenge148"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Implement canonical UTF-8 JSON with sorted keys and no NaN/Infinity. Verify the
four PDF hashes already measured in `.external/challenge-148/papers/` and these
upstream revisions:

```text
QMC_SSE    35f100af856f3273cc67d31962f3e67f801b0c37
QMC_LTFIM  524860b9c0e212ac630b0d9754075bb24198da3b
```

- [ ] **Step 4: Generate the lock and run tests**

Run:

```bash
uv lock --project tracks/qmc/solutions/frustration-free/challenge-148
uv run --project tracks/qmc/solutions/frustration-free/challenge-148 --frozen \
  python -m pytest tracks/qmc/solutions/frustration-free/challenge-148/tests/test_provenance.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tracks/qmc/solutions/frustration-free/challenge-148
git commit -m "Pin Challenge 148 environments and sources"
```

### Task 2: Implement canonical periodic lattice graphs

**Files:**
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/lattice.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/schemas/graph.schema.json`
- Test: `tracks/qmc/solutions/frustration-free/challenge-148/tests/test_lattice.py`

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class PeriodicGraph:
    lattice: Literal["triangular", "honeycomb"]
    length: int
    site_count: int
    bonds: tuple[tuple[int, int], ...]

def triangular_graph(length: int) -> PeriodicGraph: ...
def honeycomb_graph(length: int) -> PeriodicGraph: ...
def validate_graph(graph: PeriodicGraph) -> None: ...
def graph_sha256(graph: PeriodicGraph) -> str: ...
def write_graph_json(graph: PeriodicGraph, path: Path) -> None: ...
```

- Consumers: ED, Julia and Rust adapters.

- [ ] **Step 1: Write failing graph-contract tests**

```python
@pytest.mark.parametrize("length", [3, 4, 6])
def test_triangular_periodic_graph_contract(length):
    graph = triangular_graph(length)
    assert graph.site_count == length**2
    assert len(graph.bonds) == 3 * graph.site_count
    assert degree_sequence(graph) == [6] * graph.site_count
    assert graph.bonds == tuple(sorted(set(graph.bonds)))


@pytest.mark.parametrize("length", [2, 3, 4])
def test_honeycomb_periodic_graph_contract(length):
    graph = honeycomb_graph(length)
    assert graph.site_count == 2 * length**2
    assert len(graph.bonds) == 3 * graph.site_count // 2
    assert degree_sequence(graph) == [3] * graph.site_count


def test_triangular_length_two_is_rejected_as_parallel_bond_cell():
    with pytest.raises(ValueError, match="length must be at least 3"):
        triangular_graph(2)
```

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run --project tracks/qmc/solutions/frustration-free/challenge-148 --frozen \
  python -m pytest tracks/qmc/solutions/frustration-free/challenge-148/tests/test_lattice.py -q
```

Expected: missing module/functions.

- [ ] **Step 3: Implement the graphs**

For triangular cells index `(x, y)` as `x + L*y` and add only positive
directions `(1,0)`, `(0,1)`, `(1,-1)`. For honeycomb cells index sublattices as
`2*(x + L*y) + s`; connect every A site to B in cells `(x,y)`, `(x-1,y)` and
`(x,y-1)`. Canonicalize every edge as `(min(i,j), max(i,j))`.

Validate integer lengths, bounds, no self-loops, no duplicate edges,
connectivity, expected degrees and bond counts. Serialize a closed-schema JSON
with an embedded hash computed over the payload excluding the hash field.

- [ ] **Step 4: Run graph tests**

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/lattice.py \
  tracks/qmc/solutions/frustration-free/challenge-148/schemas/graph.schema.json \
  tracks/qmc/solutions/frustration-free/challenge-148/tests/test_lattice.py
git commit -m "Add canonical Challenge 148 lattice graphs"
```

### Task 3: Build and validate the Pauli TFIM Hamiltonian

**Files:**
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/ed.py`
- Test: `tracks/qmc/solutions/frustration-free/challenge-148/tests/test_ed_hamiltonian.py`

**Interfaces:**
- Consumes: `PeriodicGraph`
- Produces:

```python
@dataclass(frozen=True)
class EDResourceEstimate:
    site_count: int
    dimension: int
    dense_matrix_bytes: int
    dense_eigenvector_bytes: int

def estimate_ed_resources(site_count: int) -> EDResourceEstimate: ...
def build_sparse_hamiltonian(
    graph: PeriodicGraph, *, coupling: float = 1.0, field: float
) -> scipy.sparse.csr_matrix: ...
def build_dense_hamiltonian_oracle(
    graph: PeriodicGraph, *, coupling: float = 1.0, field: float
) -> numpy.ndarray: ...
```

- [ ] **Step 1: Write failing Hamiltonian tests**

```python
def test_sparse_hamiltonian_matches_independent_kronecker_oracle():
    graph = honeycomb_graph(2)
    sparse = build_sparse_hamiltonian(graph, coupling=1.0, field=2.1325)
    dense = build_dense_hamiltonian_oracle(graph, coupling=1.0, field=2.1325)
    np.testing.assert_allclose(sparse.toarray(), dense, atol=0, rtol=0)


def test_hamiltonian_uses_pauli_not_spin_half_normalization():
    graph = honeycomb_graph(2)
    h0 = build_sparse_hamiltonian(graph, coupling=1.0, field=0.0)
    all_up = 0
    assert h0[all_up, all_up] == -len(graph.bonds)


def test_dense_resource_guard_rejects_unsafe_thermal_dimension():
    estimate = estimate_ed_resources(16)
    assert estimate.dense_eigenvector_bytes == (2**16) ** 2 * 8
    with pytest.raises(MemoryError, match="full thermal ED"):
        build_dense_hamiltonian_oracle(triangular_graph(4), field=4.76811)
```

- [ ] **Step 2: Verify RED**

Run the focused test and confirm missing implementation.

- [ ] **Step 3: Implement sparse bit-basis assembly and independent dense oracle**

Use bit `0 -> sigma_z=+1`, bit `1 -> sigma_z=-1`. The diagonal is
`-J sum z_i z_j`; every site contributes an off-diagonal matrix element `-h`
to the state with that bit flipped. Build the dense oracle independently with
Kronecker products, not by converting the sparse matrix.

Reject non-finite parameters, unsafe site counts, malformed graphs and dense
allocations above the configured 2 GiB local guard.

- [ ] **Step 4: Run tests and sparse symmetry checks**

Expected: exact equality for small graphs, Hermitian matrix, and `N*2^N`
off-diagonal directed entries when `h != 0`.

- [ ] **Step 5: Commit**

```bash
git add tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/ed.py \
  tracks/qmc/solutions/frustration-free/challenge-148/tests/test_ed_hamiltonian.py
git commit -m "Add exact Pauli TFIM Hamiltonian oracle"
```

### Task 4: Add exact thermal and sparse ground-state observables

**Files:**
- Modify: `tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/ed.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/schemas/ed-result.schema.json`
- Test: `tracks/qmc/solutions/frustration-free/challenge-148/tests/test_ed_observables.py`

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class ThermalObservables:
    beta: float
    energy: float
    energy_density: float
    transverse_magnetization: float
    m2: float
    m4: float
    binder_ratio: float

def exact_thermal_observables(
    graph: PeriodicGraph, *, coupling: float, field: float, beta: float
) -> ThermalObservables: ...
def sparse_ground_state_observables(
    graph: PeriodicGraph, *, coupling: float, field: float
) -> ThermalObservables: ...
```

- [ ] **Step 1: Write limit and independent-trace tests**

```python
def test_exact_thermal_trace_matches_direct_matrix_exponential():
    graph = honeycomb_graph(2)
    result = exact_thermal_observables(graph, coupling=1.0, field=2.0, beta=0.7)
    expected = direct_expm_trace_observables(graph, field=2.0, beta=0.7)
    assert dataclasses.astuple(result) == pytest.approx(dataclasses.astuple(expected))


def test_binder_ratio_uses_paper_definition():
    result = exact_thermal_observables(
        honeycomb_graph(2), coupling=1.0, field=2.0, beta=0.7
    )
    assert result.binder_ratio == pytest.approx(result.m2**2 / result.m4)


def test_high_temperature_pauli_moments():
    result = exact_thermal_observables(
        honeycomb_graph(2), coupling=1.0, field=2.0, beta=1e-9
    )
    assert result.m2 == pytest.approx(1 / 8, rel=1e-7)
    assert result.m4 == pytest.approx((3 * 8**2 - 2 * 8) / 8**4, rel=1e-7)
```

- [ ] **Step 2: Verify RED**

Expected: missing observables functions.

- [ ] **Step 3: Implement stable eigentrace observables**

Use `numpy.linalg.eigh`, shift Boltzmann exponents by the minimum energy, and
evaluate diagonal matrix elements of `m^2`, `m^4` and `sum sigma_x/N` in the
eigenbasis. Require finite positive `beta`. Use `scipy.sparse.linalg.eigsh` for
the ground-state-only path and explicitly mark its result as `beta=inf`.

- [ ] **Step 4: Validate thermal ED only on triangular `L=3` and honeycomb `L=2`**

Run the full ED-observable suite. Add sparse ground-state characterization for
triangular `L=4` and honeycomb `L=3`; do not allocate dense eigenvectors there.

- [ ] **Step 5: Commit**

```bash
git add tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/ed.py \
  tracks/qmc/solutions/frustration-free/challenge-148/schemas/ed-result.schema.json \
  tracks/qmc/solutions/frustration-free/challenge-148/tests/test_ed_observables.py
git commit -m "Add exact thermal observables for Challenge 148"
```

### Task 5: Implement immutable, hash-bound run publication

**Files:**
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/artifacts.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/schemas/completion.schema.json`
- Test: `tracks/qmc/solutions/frustration-free/challenge-148/tests/test_artifacts.py`

**Interfaces:**
- Produces:

```python
def atomic_write_json(path: Path, value: object) -> str: ...
def publish_run(
    output_root: Path,
    *,
    run_spec: dict,
    producer: Callable[[Path], None],
) -> Path: ...
def validate_run(run_directory: Path, *, expected_spec_sha256: str) -> dict: ...
```

- [ ] **Step 1: Write failure-injection tests**

```python
def test_failed_first_publication_leaves_no_current_pointer(tmp_path):
    def fail(stage):
        (stage / "partial.json").write_text("{}")
        raise RuntimeError("injected")
    with pytest.raises(RuntimeError, match="injected"):
        publish_run(tmp_path, run_spec={"stage": "test"}, producer=fail)
    assert not (tmp_path / "current.json").exists()


def test_validation_rejects_symlink_hash_drift_and_unexpected_files(tmp_path):
    run = publish_valid_fixture(tmp_path)
    (run / "summary.json").write_text('{"changed":true}')
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        validate_run(run, expected_spec_sha256=fixture_spec_sha256())
```

- [ ] **Step 2: Verify RED**

Expected: missing artifact module.

- [ ] **Step 3: Implement staged-directory publication**

Create `.<run-id>.stage-*` in the destination filesystem, write and fsync every
artifact, reject symlinks/non-regular files, hash the exact file set, write
`completion.json`, fsync the stage directory, rename to `runs/run-<hash>`, fsync
`runs/`, and atomically advance `current.json`. Archive abandoned or invalid
stages with an audit suffix instead of deleting them.

- [ ] **Step 4: Run integrity and concurrency tests**

Include two publishers racing for the same spec and prove that they either
converge on the same immutable run or one fails without corrupting the winner.

- [ ] **Step 5: Commit**

```bash
git add tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/artifacts.py \
  tracks/qmc/solutions/frustration-free/challenge-148/schemas/completion.schema.json \
  tracks/qmc/solutions/frustration-free/challenge-148/tests/test_artifacts.py
git commit -m "Add crash-safe Challenge 148 run publication"
```

### Task 6: Implement the primary Rust QMC_SSE adapter

**Files:**
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-sse/Cargo.toml`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-sse/Cargo.lock`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-sse/src/main.rs`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/schemas/qmc-request.schema.json`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/schemas/qmc-checkpoint-generation.schema.json`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/schemas/qmc-sse-bin.schema.json`
- Test: `tracks/qmc/solutions/frustration-free/challenge-148/tests/test_primary_qmc_sse_adapter.py`

**Interfaces:**
- Executes exactly as `qmc-sse --request PATH --output-directory PATH`.
- Creates a closed `qmc-request-v1` schema with exactly these fields:
  `schema_version`, `adapter`, `graph_path`, `graph_sha256`, `beta`,
  `coupling`, `field`, `seed`, `thermalization_sweeps`, `retained_samples`,
  `thinning`, `bin_length`, `checkpoint_bins`, `expected_source_hash`, and
  `expected_build_hash`. No additional properties are allowed. `adapter` must
  name QMC_SSE or the executable fails before model construction.
  `retained_samples` and `bin_length` must be positive, and
  `retained_samples` must be divisible by `bin_length`; define
  `total_bins = retained_samples / bin_length`. `checkpoint_bins` must be a
  positive integer.
- Verifies the canonical graph's embedded SHA256 before constructing the model.
- Produces immutable `qmc-sse-bin-v1` NDJSON bins containing primitive sums and
  counts for energy, transverse magnetization, `m²`, `m⁴`, operator count,
  time-slice count and QMC_SSE-specific cluster diagnostics.
- Creates the common closed `qmc-checkpoint-generation-v2` progress-manifest
  schema with `schema_version`, `anchor_sha256`, `request_sha256`, `adapter`,
  `source_hash`, `build_hash`, `seed`, `completed_bin_count`, ordered
  `bin_object_hashes`, `previous_generation_sha256`, and
  `replay_update_count`, with no additional properties. `adapter` permits
  exactly QMC_SSE and QMC_LTFIM, and `anchor_sha256` is required for both. The
  schema/semantic validator permits a null predecessor only for canonical
  generation 0; every later generation names the SHA256 of its immediate
  predecessor. This is a pre-production breaking migration: no v1 production
  artifacts exist, `qmc-checkpoint-generation-v1` prototype data is rejected,
  and there is no silent v1-to-v2 migration.

- [ ] **Step 1: Write black-box CLI and normalization tests**

Test valid graph/request fixtures, graph-hash drift, Pauli normalization,
identical-seed byte identity, different-seed divergence, truncated output,
non-finite values, adapter mismatch and the transverse-estimator offset. Add
restart-equivalence tests across multiple completed-bin boundaries plus
corrupted-bin, corrupted-generation-manifest, stale-request and stale-build
tests; every mismatch must fail closed. Inject failures at bin rename,
generation rename, pointer replace and each fsync boundary. Test orphan
adoption/archive, stale-pointer recovery, conflicting-descendant rejection,
ancestry gaps, missing bin objects and no-overwrite behavior. Also test a crash
after first-generation rename before the first pointer with
`checkpoint_bins > 1`, a short final checkpoint interval, same-manifest-hash
concurrent publication convergence to one generation path with only the
unpublished staging loser archived, unique genesis-hash adoption, and rejection
of multiple distinct valid genesis hashes. A focused statistical test compares
energy, transverse magnetization, `m²`, `m⁴`, and Binder ratio with thermal ED.

- [ ] **Step 2: Verify RED**

Expected: missing Cargo project or executable.

- [ ] **Step 3: Pin QMC_SSE and adapter dependencies**

Use:

```toml
qmc = { git = "https://github.com/Renmusxd/QMC_SSE", rev = "35f100af856f3273cc67d31962f3e67f801b0c37", features = ["autocorrelations"] }
```

Pin CLI, serialization, SHA256 and seeded RNG crates in `Cargo.lock`. Record
QMC_SSE's `GPL-3.0-only` license in provenance and adapter documentation.

- [ ] **Step 4: Implement graph and Hamiltonian construction**

Build `GenericQMC::<bool, TFIMTerm<f64>>::new(N)`, add `TFIMTerm::X(h)` for
each site and `TFIMTerm::ZZ(-J)` for each canonical graph edge, and retain all
X-term handles. Reject malformed, noncanonical or hash-mismatched graphs before
calling QMC_SSE. A sweep is one diagonal update plus enough accepted or
attempted cluster updates to visit at least `N` sites according to a documented
counter; one single-cluster call is not a full sweep.

- [ ] **Step 5: Implement observables and immutable bin publication**

Map `bool` to Pauli `+1/-1`; compute `m²`, `m⁴`, and `get_energy(beta)`.
Compute the per-site transverse magnetization from retained X handles:

```text
mx = sum_i [n_i / beta] / (h N) - 1
```

Use only the request seed, record the exact RNG/version metadata, and reserve a
disjoint deterministic seed namespace from QMC_LTFIM. Under a per-run exclusive
lock, write and fsync each completed bin, validate its schema and finite values,
then atomically rename it to the content-addressed immutable object
`bins/<sha256>.ndjson` and fsync `bins/`. Byte-validate an existing same-hash
object and never overwrite it.

- [ ] **Step 6: Implement deterministic replay restart**

Do not serialize or claim support for opaque QMC_SSE state. Publish after each
interval of `checkpoint_bins` completed bins and once at final completion when
the final interval is shorter. Generation index `g` records
`completed_bin_count = min((g + 1) * checkpoint_bins, total_bins)` and contains
exactly that many ordered bin-object hashes. Under the per-run lock, first
durably publish an immutable content-addressed run-lock anchor. Create one
immutable generation directory whose closed v2 manifest binds that anchor's
canonical SHA256, request/source/build hashes, seed, completed-bin count,
ordered bin-object hashes, `previous_generation_sha256` and replay update
count. Canonical generation 0 sets `previous_generation_sha256 = null` and
`completed_bin_count = min(checkpoint_bins, total_bins)`; each later generation
names its immediate predecessor's canonical manifest SHA256.

The canonical manifest SHA256 is the generation directory identity. Validate
every referenced bin, fsync the manifest and staged directory, atomically
rename it to `generations/<generation-hash>/`, and fsync `generations/`. If the
path already exists, byte-validate the published manifest and referenced
generation contents, leave that path untouched, and archive only the
publisher's unpublished staging directory as an identical loser. Then
write/fsync a closed `qmc-current-generation-v2` temporary pointer binding the
same `anchor_sha256`, atomically replace `current-generation.json`, and fsync
the run directory. Reject a missing, malformed, stale or mismatched anchor in
either artifact. Reuse Task 5's durable write, fsync, rename and validation
primitives where applicable without sharing QMC adapter logic.

On recovery, audit unreferenced bin objects under the lock: adopt only a
byte-valid object that deterministic replay identifies as the next expected
bin, and archive every other orphan. If a generation rename completed before
the pointer update, scan for exactly one valid contiguous descendant of current
and advance to it. Conflicting descendants, gaps, stale hashes, malformed
generations or missing bin objects fail closed and are archived/diagnosed
rather than guessed.

If `current-generation.json` is absent, scan published generation directories
under the lock for fully valid `previous_generation_sha256 = null` genesis
candidates matching request/source/build hashes. Deterministic replay must
byte-verify every ordered retained bin in each candidate. Zero valid manifest
hashes starts fresh, exactly one is adopted, and more than one distinct valid
genesis manifest hash is a conflict that fails closed. Archive orphan staging
directories independently; they do not participate in genesis selection.
Publish the selected pointer through the normal durable protocol. After
selecting the generation, reconstruct RNG/model from the same seed, replay
thermalization and every update through the selected generation's
`replay_update_count`, and verify every retained bin byte-for-byte and by
content hash before continuing.

- [ ] **Step 7: Run Rust and Python adapter tests**

```bash
cargo test --locked --manifest-path \
  tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-sse/Cargo.toml
uv run --project tracks/qmc/solutions/frustration-free/challenge-148 --frozen \
  python -m pytest \
  tracks/qmc/solutions/frustration-free/challenge-148/tests/test_primary_qmc_sse_adapter.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-sse \
  tracks/qmc/solutions/frustration-free/challenge-148/schemas/qmc-request.schema.json \
  tracks/qmc/solutions/frustration-free/challenge-148/schemas/qmc-checkpoint-generation.schema.json \
  tracks/qmc/solutions/frustration-free/challenge-148/schemas/qmc-sse-bin.schema.json \
  tracks/qmc/solutions/frustration-free/challenge-148/tests/test_primary_qmc_sse_adapter.py
git commit -m "Add primary QMC_SSE adapter for challenge 148"
```

### Task 7: Implement the independent Julia QMC_LTFIM adapter

**Files:**
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-ltfim/Project.toml`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-ltfim/Manifest.toml`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-ltfim/src/Challenge148LTFIM.jl`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-ltfim/run_independent.jl`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-ltfim/test/runtests.jl`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/schemas/qmc-ltfim-bin.schema.json`
- Test: `tracks/qmc/solutions/frustration-free/challenge-148/tests/test_independent_qmc_ltfim_adapter.py`

**Interfaces:**
- Executes exactly as
  `julia run_independent.jl --request PATH --output-directory PATH` and consumes
  Task 6's closed `qmc-request-v1` schema. `adapter` must name QMC_LTFIM or the
  wrapper fails before model construction.
- Implements its own per-run lock and durable content-addressed run-lock anchor;
  its adapter-specific lock identity and acquisition mechanism remain
  independent of QMC_SSE. It consumes the identical shared
  `qmc-checkpoint-generation-v2` and `qmc-current-generation-v2` contracts,
  requiring the canonical anchor SHA256 in every generation and current
  pointer. It rejects v1 prototype checkpoint data without migration.
- Independently validates the graph's embedded SHA256, canonical edge ordering,
  integer bounds, absence of self-loops and duplicates, connectivity, and the
  lattice-specific length/site-count/bond-count/degree invariants before
  converting zero-based edges to Julia indices.
- Produces immutable `qmc-ltfim-bin-v1` NDJSON bins with the primitive sums and
  counts needed to summarize energy, transverse magnetization, `m²`, `m⁴`, and
  Binder ratio independently of QMC_SSE. Each bin also contains nonidentity
  operator count, operator-list capacity/time-slice count, cluster
  attempted/accepted counts, and available cluster count/size diagnostics from
  `Diagnostics`. Uses Task 6's common content-addressed bin and immutable
  checkpoint-generation protocol at completed-bin boundaries.

- [ ] **Step 1: Write direct-library and black-box tests**

Test graph indexing and sign conventions, exact matrix construction, Pauli
normalization, graph-hash drift, deterministic replay, seed separation from
QMC_SSE, immutable publication, adapter mismatch, and all five ED observables.
Add negative tests for noncanonical edge order, out-of-bounds endpoints,
self-loops, duplicate edges, disconnected graphs, and every lattice-specific
length/site/bond/degree invariant. Add restart equivalence across completed-bin
boundaries plus corrupted-bin, corrupted-generation-manifest, stale-request and
stale-build tests; every mismatch must fail closed. Inject failures at bin
rename, generation rename, pointer replace and each fsync boundary. Test orphan
adoption/archive, stale-pointer recovery, conflicting-descendant rejection,
ancestry gaps, missing bin objects and no-overwrite behavior. Also test a crash
after first-generation rename before the first pointer with
`checkpoint_bins > 1`, a short final checkpoint interval, same-manifest-hash
concurrent publication convergence to one generation path with only the
unpublished staging loser archived, unique genesis-hash adoption, and rejection
of multiple distinct valid genesis hashes. Tests must invoke the owned wrapper,
never the upstream CLI or general constructor.

- [ ] **Step 2: Verify RED**

Run:

```bash
julia --project=tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-ltfim \
  tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-ltfim/test/runtests.jl
```

Expected: missing wrapper project/module.

- [ ] **Step 3: Pin the direct library dependency**

Pin QMC_LTFIM revision
`524860b9c0e212ac630b0d9754075bb24198da3b` and Julia `1.11.6`; commit the
resulting `Manifest.toml`. Record QMC_LTFIM's `Apache-2.0` license. Do not patch
or vendor the upstream checkout.

- [ ] **Step 4: Construct the current thermal API directly**

Parse and verify the canonical graph before allocating the model. Build the
ferromagnetic coupling matrix in the exact sign and Pauli convention confirmed
by a dense small-system test, then call the checked revision's current API:

```julia
Jmatrix = zeros(Float64, N, N)
# For each canonical edge i < j:
Jmatrix[i, j] = -coupling
model = TFIM(UpperTriangular(Jmatrix), fill(field, N))
state = BinaryThermalState(model, initial_operator_capacity)
diagnostics = Diagnostics(RunStats(), NoTransitionMatrix())
num_ops = mc_step_beta!(
    measure!, rng, state, model, beta, diagnostics; eq=equilibrating
)
```

Only strict upper-triangle edge entries are `-coupling`; the diagonal and lower
triangle remain zero. Define `measure!(cluster_list_size, qmc_state, H)` for the
current callback signature. The calls above bind the pinned revision's current
`BinaryThermalState(H::Hamiltonian, cutoff::Int)`,
`Diagnostics(runstats, tmatrix)`, and
`mc_step_beta!(f::Function, rng::AbstractRNG,
qmc_state::BinaryThermalState, H::AbstractIsing, beta::Real, d::Diagnostics;
eq::Bool=false, kw...)` interfaces. The owned wrapper must bypass the
known-broken upstream CLI and general-constructor paths rather than adding
compatibility methods or modifying upstream.

- [ ] **Step 5: Implement independent estimators and raw bins**

Measure energy, transverse magnetization, `m²`, and `m⁴` from QMC_LTFIM's
thermal state/diagnostics using its current estimator conventions, with
explicit conversion to Pauli normalization. Derive Binder ratio only from
separately aggregated `m²` and `m⁴`. Use a deterministic seed supplied by the
request in a namespace disjoint from Task 6. Atomically publish schema-validated
immutable `bins/<sha256>.ndjson` objects under a per-run exclusive lock,
fsyncing `bins/` after rename and byte-validating rather than overwriting an
existing same-hash object. Record the nonidentity operator count, operator-list
capacity/time-slice count, cluster attempted/accepted counts and all available
cluster count/size diagnostics exposed by `Diagnostics`; do not invent missing
QMC_SSE-equivalent fields and do not reuse Rust serialization or estimator
code.

- [ ] **Step 6: Implement deterministic replay restart**

Do not serialize or claim support for opaque QMC_LTFIM state. Publish after each
interval of `checkpoint_bins` completed bins and once at final completion when
the final interval is shorter. Generation index `g` records
`completed_bin_count = min((g + 1) * checkpoint_bins, total_bins)` and contains
exactly that many ordered bin-object hashes. Under its independently
implemented per-run lock, first durably publish an immutable content-addressed
run-lock anchor. Publish the common immutable checkpoint generation: validate
all referenced bin objects, fsync the closed manifest and staged directory,
atomically rename it to `generations/<generation-hash>/`, and fsync
`generations/`; then write/fsync a temporary pointer, atomically replace
`current-generation.json`, and fsync the run directory. The v2 manifest binds
the anchor's canonical SHA256, request/source/build hashes, seed, completed-bin
count, ordered bin-object hashes, `previous_generation_sha256` and replay
update count. The closed v2 current pointer binds the same `anchor_sha256`.
Canonical generation 0 sets `previous_generation_sha256 = null` and
`completed_bin_count = min(checkpoint_bins, total_bins)`; each later generation
names its immediate predecessor's canonical manifest SHA256.

The canonical manifest SHA256 is the generation directory identity. If
`generations/<generation-hash>/` already exists, byte-validate the published
manifest and referenced generation contents, leave that path untouched, and
archive only the publisher's unpublished staging directory as an identical
loser. Recovery therefore sees at most one published directory for each
manifest hash. Reuse Task 5 durable publication primitives where applicable
while keeping the Julia adapter's lock, update, estimator and serialization
implementation independent of Rust. Reject v1, missing-anchor and
anchor-mismatch artifacts; do not infer or silently migrate an anchor.

Recovery audits unreferenced objects under the lock, adopting only a byte-valid
next bin identified by deterministic replay and archiving all other orphans. It
advances a stale pointer only when scanning finds exactly one valid contiguous
descendant. Conflicting descendants, gaps, stale hashes, malformed generations
or missing bin objects fail closed and are archived/diagnosed.

If `current-generation.json` is absent, scan published generation directories
under the lock for fully valid `previous_generation_sha256 = null` genesis
candidates matching request/source/build hashes. Deterministic replay must
byte-verify every ordered retained bin in each candidate. Zero valid manifest
hashes starts fresh, exactly one is adopted, and more than one distinct valid
genesis manifest hash is a conflict that fails closed. Archive orphan staging
directories independently; they do not participate in genesis selection.
Publish the selected pointer through the normal durable protocol. After
selecting the generation, reconstruct the RNG, model, state and diagnostics
from the same seed. Replay thermalization and every `mc_step_beta!` update
through the selected generation's `replay_update_count`; verify every retained
bin byte-for-byte and by content hash before continuing.

- [ ] **Step 7: Run Julia and Python adapter tests**

```bash
julia --project=tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-ltfim \
  tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-ltfim/test/runtests.jl
uv run --project tracks/qmc/solutions/frustration-free/challenge-148 --frozen \
  python -m pytest \
  tracks/qmc/solutions/frustration-free/challenge-148/tests/test_independent_qmc_ltfim_adapter.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-ltfim \
  tracks/qmc/solutions/frustration-free/challenge-148/schemas/qmc-ltfim-bin.schema.json \
  tracks/qmc/solutions/frustration-free/challenge-148/tests/test_independent_qmc_ltfim_adapter.py
git commit -m "Add independent QMC_LTFIM adapter for challenge 148"
```

### Task 8: Build the ED–QMC_SSE–QMC_LTFIM acceptance gate

**Files:**
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/statistics.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/acceptance.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/schemas/acceptance.schema.json`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/scripts/run_acceptance.py`
- Test: `tracks/qmc/solutions/frustration-free/challenge-148/tests/test_statistics.py`
- Test: `tracks/qmc/solutions/frustration-free/challenge-148/tests/test_acceptance.py`

**Interfaces:**
- Produces:

```python
def integrated_autocorrelation_time(samples: npt.NDArray[np.float64]) -> float: ...
def summarize_qmc_sse_bins(path: Path) -> dict: ...
def summarize_qmc_ltfim_bins(path: Path) -> dict: ...
def run_acceptance(request: dict, output_root: Path) -> Path: ...
```

For each adapter-specific request, invoke exactly:

```bash
"$CH148_QMC_SSE_BIN" \
  --request "$REQUEST" --output-directory "$OUTPUT_DIRECTORY"
julia --project="$CH148_SOLUTION_DIR/adapters/qmc-ltfim" \
  "$CH148_SOLUTION_DIR/adapters/qmc-ltfim/run_independent.jl" \
  --request "$REQUEST" --output-directory "$OUTPUT_DIRECTORY"
```

Set and verify `CH148_QMC_SSE_BIN` and `CH148_SOLUTION_DIR` from the owned
environment rather than the process working directory. Before summarization,
validate the request
against `qmc-request.schema.json`, QMC_SSE output against
`qmc-sse-bin.schema.json`, QMC_LTFIM output against
`qmc-ltfim-bin.schema.json`, every generation manifest against
`qmc-checkpoint-generation.schema.json`, and
`current-generation.json` plus every referenced immutable bin against the
generation ancestry and content hashes. Require
`qmc-checkpoint-generation-v2` and `qmc-current-generation-v2`; reject v1
prototype artifacts. For both adapters, verify that every generation and the
current pointer bind the same valid `anchor_sha256` as that adapter's durable
content-addressed run-lock anchor before reading any bin. The acceptance gate
does not assume that the adapters share lock implementation details.

- [ ] **Step 1: Write statistics tests with correlated synthetic chains**

Test IID, known AR(1) autocorrelation, constant-chain rejection, bin length
`>=10*tau_int`, half-chain agreement and independent-chain combined errors.

- [ ] **Step 2: Write acceptance failure tests**

```python
def test_acceptance_fails_when_one_observable_exceeds_four_sigma(tmp_path):
    fixture = three_way_fixture(tmp_path, qmc_sse_m4_shift_sigma=4.1)
    result = run_acceptance(fixture.request, tmp_path / "results")
    assert read_summary(result)["passed"] is False
    assert read_summary(result)["failures"] == [
        "primary_qmc_sse.m4.normalized_residual"
    ]
```

Also reject median residual above 1.5, missing bins, repeated seeds, provenance
drift, stale subprocess output and nonzero subprocess exit. Add contract
fixtures for minimal QMC_SSE-v2 and QMC_LTFIM-v2 generations, plus rejection of
v1, missing anchors, extra keys, malformed hashes, executable-specific adapter
mismatches and generation/current/lock-anchor mismatches.

- [ ] **Step 3: Implement autocorrelation-aware summaries**

Read `qmc-sse-bin-v1` and `qmc-ltfim-bin-v1` through separate parsers. Use
immutable bins, no naive per-sweep standard errors. Compute chain-level means,
effective sample counts and combined errors. Preserve each code's raw results
and compare `energy`, transverse magnetization, `m²`, `m⁴`, and Binder ratio.

- [ ] **Step 4: Implement the acceptance matrix**

Run full thermal ED, primary QMC_SSE and independent QMC_LTFIM for triangular
`L=3` and honeycomb `L=2` over at least two beta/field points. For each adapter
separately, require every one of energy, transverse magnetization, `m²`, `m⁴`,
and Binder ratio to have normalized residual `<=4`; require its median residual
to be `<=1.5`, chain and half-run agreement within `3 sigma`, valid immutable
bins, a verified graph hash, exact source provenance and a deterministic seed
distinct from the other adapter. Neither adapter's success can compensate for
the other's failure. Publish through `publish_run`.

- [ ] **Step 5: Run all acceptance tests and a real smoke**

The real smoke may use reduced samples and is labeled `characterization`; the
passing scientific acceptance uses the pre-registered sample count from its
request and cannot silently relax thresholds.

- [ ] **Step 6: Commit**

```bash
git add tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/statistics.py \
  tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/acceptance.py \
  tracks/qmc/solutions/frustration-free/challenge-148/scripts/run_acceptance.py \
  tracks/qmc/solutions/frustration-free/challenge-148/schemas/acceptance.schema.json \
  tracks/qmc/solutions/frustration-free/challenge-148/tests/test_statistics.py \
  tracks/qmc/solutions/frustration-free/challenge-148/tests/test_acceptance.py
git commit -m "Add three-way Challenge 148 acceptance gate"
```

### Task 9: Add the crossing pilot and resource profiler

**Files:**
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/planning.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/scripts/run_cell.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/scripts/profile_pilot.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/schemas/plan.schema.json`
- Test: `tracks/qmc/solutions/frustration-free/challenge-148/tests/test_planning.py`

**Interfaces:**
- Produces deterministic cells keyed by lattice, `L`, field, `beta/L`, code,
  seed and sampling settings.
- Produces common measured fields for adapter identity/build, site count,
  beta, retained samples, wall time, updates/sweeps per second, `tau_int`,
  effective sample count, peak RSS, immutable-bin bytes, generation-manifest
  and pointer bytes, deterministic replay wall time and projected CPU-hours for
  a target `Q_L` error.
- Preserves adapter-specific diagnostics separately: QMC_SSE operator-string
  and cluster counters, and QMC_LTFIM nonidentity operator count,
  operator-list capacity/time-slice count, cluster attempted/accepted counts
  and available `Diagnostics` cluster count/size fields. A field is never
  required from an adapter that does not expose it.

- [ ] **Step 1: Write deterministic-plan and safety tests**

Assert that the pilot includes `L=4,6,8`, both lattices, at least three fields
around each published critical point, multiple seeds and `beta/L` values.
Reject duplicate seeds, reused output paths, local cells above ten minutes or
16 GiB, and plans whose graph/source hashes do not match current inputs.

- [ ] **Step 2: Verify RED**

Expected: missing planning module.

- [ ] **Step 3: Implement pilot planning and one-cell execution**

Each cell runs exactly one code and writes one immutable result. Resubmission
skips only a fully validated matching cell. An interrupted matching cell
restarts only through the Task 6/7 deterministic replay protocol; stale,
corrupt or replay-mismatched cells fail closed and are archived, not
overwritten. Publish content-addressed bins, immutable checkpoint generations
and `current-generation.json` at the request-configured `checkpoint_bins`
interval rather than claiming opaque solver-state checkpoints.

- [ ] **Step 4: Implement measured resource projection**

Fit wall time and memory against measured `N`, beta, common update statistics
and autocorrelation, using adapter-specific diagnostics only in
adapter-specific models. Measure full interrupted-run validation and replay
time at representative completed-bin boundaries; report it separately from
uninterrupted throughput and include it in restart resource projections. Mark
extrapolations beyond the observed size range and apply explicit safety factors
of 2 for wall time and 1.5 for memory.

- [ ] **Step 5: Run a local sub-ten-minute profile**

Do not launch production. Produce the first measured feasibility report and
record whether the proposed `L<=96` grid is plausible.

- [ ] **Step 6: Commit**

```bash
git add tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/planning.py \
  tracks/qmc/solutions/frustration-free/challenge-148/scripts \
  tracks/qmc/solutions/frustration-free/challenge-148/schemas/plan.schema.json \
  tracks/qmc/solutions/frustration-free/challenge-148/tests/test_planning.py
git commit -m "Add Challenge 148 crossing pilot planner"
```

### Task 10: Implement finite-size scaling and the ratio verdict

**Files:**
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/fss.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/scripts/analyze.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/schemas/analysis.schema.json`
- Test: `tracks/qmc/solutions/frustration-free/challenge-148/tests/test_fss.py`

**Interfaces:**
- Produces:

```python
def fit_binder_scaling(dataset: BinderDataset, model: FitModel) -> FitResult: ...
def crossing_extrapolation(dataset: BinderDataset) -> CrossingResult: ...
def bootstrap_ratio(
    triangular: BinderDataset,
    honeycomb: BinderDataset,
    *,
    replicates: int,
    seed: int,
) -> RatioResult: ...
```

- [ ] **Step 1: Write synthetic recovery tests**

Generate synthetic 3D-Ising-like Binder data with known `h_c`, `y_t=1.587`,
`y_i=-0.815`, correlated bin noise and correction terms. Require unbiased
recovery, empirical interval coverage and deterministic bootstrap output.

- [ ] **Step 2: Write failure tests**

Reject underdetermined fits, singular covariance, non-overlapping field
windows, too few sizes, unstable `L_min` variation, non-finite bootstrap
replicates and ratio claims with `sigma_R > 1.2e-5`.

- [ ] **Step 3: Implement primary and robustness fits**

Primary: fixed `y_t=1.587`, `y_i=-0.815`, paper-style expansion. Robustness:
vary `L_min`, field window, polynomial order and selected exponents. Implement
crossing-point extrapolation independently. Preserve chain-resampled
covariance instead of fitting only independent error bars.

- [ ] **Step 4: Implement pre-registered verdict**

Return exactly one status:

```text
insufficient_precision
conjecture_survives
conjecture_rejected
```

Require all convergence and independent-code gates before either scientific
verdict.

- [ ] **Step 5: Run synthetic suite and commit**

```bash
git add tracks/qmc/solutions/frustration-free/challenge-148/src/challenge148/fss.py \
  tracks/qmc/solutions/frustration-free/challenge-148/scripts/analyze.py \
  tracks/qmc/solutions/frustration-free/challenge-148/schemas/analysis.schema.json \
  tracks/qmc/solutions/frustration-free/challenge-148/tests/test_fss.py
git commit -m "Add validated Challenge 148 scaling analysis"
```

### Task 11: Add profile-neutral Slurm execution

**Files:**
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/scripts/slurm_array.sh`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/scripts/submit_plan.py`
- Test: `tracks/qmc/solutions/frustration-free/challenge-148/tests/test_slurm_wrapper.py`

**Interfaces:**
- Requires explicit `CH148_SOLUTION_DIR`, `CH148_PLAN`, `CH148_RUN_ROOT`,
  `CH148_CELL_INDEX`, environment paths and resource-plan hash.
- Executes one zero-based cell and never embeds cluster names, credentials,
  partitions or account values.

- [ ] **Step 1: Write spooled-wrapper and environment tests**

Copy the wrapper to a fake Slurm spool directory and prove it resolves code
from `CH148_SOLUTION_DIR`, not `BASH_SOURCE`. Reject missing resource
acknowledgment, one-based indices and output roots outside the challenge path.

- [ ] **Step 2: Verify RED**

Expected: missing wrapper.

- [ ] **Step 3: Implement strict wrapper and submission dry run**

Use `set -euo pipefail`, `umask 077`, explicit interpreter paths and
`--execution-target cluster`. `submit_plan.py` reads the active cluster profile,
checks requested memory/wall/CPU limits, and emits `sbatch --test-only` before
real submission. It cannot submit cells marked unpermitted.

- [ ] **Step 4: Run wrapper tests and a scheduler-bounded smoke**

Only after the acceptance gate and measured profile pass, submit a small
`ch148-` calibration cell. Monitor `PD -> R`, inspect the first valid checkpoint
generation and `current-generation.json`, then fetch and validate the artifact.
A RUNNING state alone is not success.

- [ ] **Step 5: Commit**

```bash
git add tracks/qmc/solutions/frustration-free/challenge-148/scripts \
  tracks/qmc/solutions/frustration-free/challenge-148/tests/test_slurm_wrapper.py
git commit -m "Add isolated Slurm execution for challenge 148"
```

### Task 12: Document reproducibility and final verification

**Files:**
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/README.md`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/references/LITERATURE_AUDIT.md`
- Create: `tracks/qmc/solutions/frustration-free/challenge-148/references/SOFTWARE_AUDIT.md`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-148/DESIGN.md`
- Test: `tracks/qmc/solutions/frustration-free/challenge-148/tests/test_documentation.py`

**Interfaces:**
- README exposes one command each for environment setup, tests, exact oracle,
  acceptance, pilot, cluster plan validation and final analysis.
- Audits distinguish the target ferromagnetic nearest-neighbor spin-1/2 model
  from frustrated, antiferromagnetic, long-range and spin-1 variants.

- [ ] **Step 1: Write documentation-contract tests**

Assert every documented command references only owned paths, no absolute local
path, no missing file, no unpinned environment and no claim stronger than the
published analysis status.

- [ ] **Step 2: Complete the literature and software audits**

Record search databases, queries, dates, inclusion/exclusion criteria, paper
metadata and source hashes. Record why QMC_SSE is primary and why QMC_LTFIM is
accepted only through the owned direct-library wrapper. Document the broken
QMC_LTFIM upstream CLI/general-constructor paths and the decision not to modify
upstream. Record the verified StochasticSeriesExpansion.jl/Carlo.jl blocker:
its current four-leg abstract-loop update cannot reach the same-basis TFIM
single-spin-flip off-diagonal vertices from diagonal vertices, probes produced
zero transverse/off-diagonal counts and disagreed with ED, and a rotated basis
would require a new non-diagonal Binder estimator. This route is rejected for
the revision, not postponed. Include QMC_SSE's `GPL-3.0-only` and QMC_LTFIM's
`Apache-2.0` licenses.

- [ ] **Step 3: Write the README**

Document the exact Hamiltonian convention first. Separate `pilot`,
`calibration`, `production` and `verdict` commands. Explain that production
requires a passing acceptance artifact and acknowledged measured resource
plan.

- [ ] **Step 4: Run final verification**

Run:

```bash
uv run --project tracks/qmc/solutions/frustration-free/challenge-148 --frozen \
  python -m pytest tracks/qmc/solutions/frustration-free/challenge-148/tests -q
cargo test --locked --manifest-path \
  tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-sse/Cargo.toml
julia --project=tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-ltfim \
  tracks/qmc/solutions/frustration-free/challenge-148/adapters/qmc-ltfim/test/runtests.jl
git diff --check
```

Expected: zero failures and clean whitespace validation.

- [ ] **Step 5: Commit**

```bash
git add tracks/qmc/solutions/frustration-free/challenge-148
git commit -m "Document Challenge 148 reproducibility workflow"
```

## Execution checkpoints

- Stop after Task 4 for review of the exact oracle.
- Stop after Task 8 for review of real ED–QMC_SSE–QMC_LTFIM acceptance data.
- Stop after Task 9 to decide whether cluster production is feasible.
- Do not execute Tasks 10–11 on production data unless Task 9's measured
  resource plan is approved.
