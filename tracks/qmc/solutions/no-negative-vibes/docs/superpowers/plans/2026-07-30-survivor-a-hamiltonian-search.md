# Survivor-A Hamiltonian Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and launch a resumable, exact-promotion-first search for
local interacting Hamiltonians guided by Survivor A and the already certified
oddcycle alphabet.

**Architecture:** One domain module owns exact seed reconstruction,
high-precision analysis, target projection, and deterministic word scoring.
Small matrix-level extensions reuse the frozen word, cone, target, and exact
promotion oracles. One runner owns immutable settings, shared catalogs,
stable sharding, append-only attempts, exact promotion, and collection.

**Tech Stack:** Python 3, SymPy exact rational algebra, NumPy memory maps,
SciPy/HiGHS numerical screening, mpmath high-precision spectral analysis,
pytest, canonical JSON/JSONL, Git, WSL, and the 64-core CPU machine.

## Global Constraints

- Design source:
  `docs/superpowers/specs/2026-07-30-survivor-a-hamiltonian-reverse-construction-design.md`
  at commit `a6a01105258e073b9c971c4205b0f81c678efde7`.
- Immutable settings:
  `protocols/oddcycle-survivor-a-v1/settings.json`.
- Survivor source result SHA-256:
  `12e8ac1e0dcb8b06130556b9ea91392e558521ca20d3b7aeb71413fa77b5d01c`.
- No scientific compute on local Windows. Tiny synthetic unit tests may run
  locally; all source-evidence analysis runs on WSL or the CPU machine.
- WSL uses 14 workers; CPU uses 62 workers; BLAS/OpenMP thread counts are one
  and `PYTHONHASHSEED=0`.
- The existing Task-8 runner's schemas and scientific classifications remain
  unchanged.
- Float64 catalogs, ranks, residuals, and duals are discovery evidence only.
  Every exact claim rebuilds the precise active columns with SymPy rationals.
- Production code follows strict RED-GREEN-REFACTOR. Every new public
  behavior first has a test that is observed failing for the expected reason.
- Every persisted object binds source, settings, plan, catalog, code, and
  payload hashes. Compute errors are operational records, never scientific
  infeasibility.
- Production launch uses a three-layer immutable closure:
  `settings.json` freezes scientific axes and the reviewed plan hash;
  `batch-manifest.json` expands every objective/target/sample cell against
  one code commit and settings hash; `launch.json` binds the byte hashes of
  the plan, settings, batch manifest, analysis, and catalog used by every
  production command.
- Every scientific CLI subcommand requires `sys.platform == "linux"` and an
  explicit runtime role allowed for that command. `analyze`, `promote`, and
  `freeze-launch`, and `collect` require `wsl`; `catalog`,
  `freeze-manifest`, `search-shard`, and `portfolio-shard` require `cpu`.
- Do not stage or upload `AGENT_HANDOFF.md`.

---

## File map

**Create**

- `oracle/oddcycle_survivor_a.py` — seed identity, exact transfer,
  high-precision logarithm, projections, target rationalization, and word
  scoring.
- `oracle/oddcycle_survivor_a_runner.py` — settings expansion, catalog
  production, attempts, shards, promotions, collection, and CLI.
- `tests/test_oddcycle_survivor_a.py` — domain behavior.
- `tests/test_oddcycle_survivor_a_runner.py` — persistence, sharding, and
  synthetic end-to-end behavior.
- `protocols/oddcycle-survivor-a-v1/README.md` — exact commands and claim
  boundary.
- `protocols/oddcycle-survivor-a-v1/batch-manifest.json` — canonical expanded
  cell IDs, objective labels/signs, exact targets, column sets, owners, and
  Route-2 intervals; generated and committed before science.
- `protocols/oddcycle-survivor-a-v1/launch.json` — final byte-hash closure
  over code/settings/plan/batch/analysis/catalog; generated after analysis and
  catalog, before search or promotion.

**Modify**

- `oracle/oddcycle_word_operator.py` — single/selected word construction.
- `oracle/oddcycle_local_hs_scan.py` — coordinate-matrix entry points and
  retained evidence.
- `oracle/oddcycle_local_targets.py` — exact coordinate target constructor.
- `oracle/oddcycle_local_hs_exact.py` — affine rational promotion and target
  certificate.
- Corresponding existing test modules.
- `docs/EXPERIMENT_LOG.md` and `docs/RESEARCH_OPERATIONS.md` only after an
  actual run or reusable operational finding.

### Task 1: Frozen Survivor-A identity and exact SPD transfer

**Files:**

- Create: `oracle/oddcycle_survivor_a.py`
- Create: `tests/test_oddcycle_survivor_a.py`
- Test: `protocols/oddcycle-survivor-a-v1/settings.json`

**Interfaces:**

- Produces:

```python
@dataclass(frozen=True)
class FrozenSourceSpec:
    result_sha256: str
    source_cell_payload_sha256: str
    source_raw_file_sha256: str
    source_cell_id: str
    sample_index: int
    sample_seed: int
    exact_shift: sp.Rational
    exact_vacuum_value: sp.Rational
    exact_minimum_row_margin: sp.Rational

@dataclass(frozen=True)
class SurvivorASeed:
    source_result_sha256: str
    source_cell_payload_sha256: str
    source_cell_id: str
    sample_index: int
    seed: int
    words: tuple[tuple[int, ...], ...]
    transpose_words: tuple[tuple[int, ...], ...]
    weights: tuple[sp.Rational, ...]
    shift: sp.Rational
    vacuum_value: sp.Rational
    minimum_row_margin: sp.Rational

def load_survivor_a(
    result_path: Path,
    *,
    expected: FrozenSourceSpec,
    label: str = "A",
) -> SurvivorASeed: ...

def reconstruct_survivor_transfer(
    seed: SurvivorASeed,
) -> tuple[sp.ImmutableMatrix, tuple[WordPairColumn, ...], dict[str, object]]: ...
```

- Consumes: existing exact word construction and the tracked Task-8 result.

- [ ] **Step 1: Write failing identity/hash tests**

Add tests that load the real tracked result and assert:

```python
seed = load_survivor_a(
    Path("protocols/oddcycle-local-hs-v1/result.json"),
    expected=FrozenSourceSpec(
        result_sha256="12e8ac1e0dcb8b06130556b9ea91392e558521ca20d3b7aeb71413fa77b5d01c",
        source_cell_payload_sha256="b93465d16f4c9d796bac26104b035ae74f85c1e1e297cc94ff2cb8e4373e2c42",
        source_raw_file_sha256="c16d32355448d9bd89e282323fbaa64852a408edc8439404feb82ff5bc21cae7",
        source_cell_id="portfolio-l2",
        sample_index=122,
        sample_seed=20260730,
        exact_shift=sp.Rational(42),
        exact_vacuum_value=sp.Rational(44),
        exact_minimum_row_margin=sp.Rational(12213, 15625),
    ),
)
assert seed.source_cell_id == "portfolio-l2"
assert seed.sample_index == 122
assert seed.shift == 42
assert seed.vacuum_value == 44
assert seed.minimum_row_margin == sp.Rational(12213, 15625)
assert all(weight > 0 for weight in seed.weights)
assert sum(seed.weights) == 1
```

Copy the result to `tmp_path`, flip one weight numerator, and assert
`load_survivor_a` raises `ValueError("source result SHA-256 mismatch")`.
With unmodified result bytes, independently change every
`FrozenSourceSpec` digest/identity/value and assert the loader rejects:
result digest, cell payload digest, raw-file digest, cell ID, sample index,
sample seed, shift, vacuum value, and row margin. The payload/raw digests are
verified against the frozen references embedded in the tracked Task-8 result;
when the ignored raw is present on WSL its bytes receive a separate preflight
hash replay before launch.

- [ ] **Step 2: Run RED**

Run from the solution root:

```bash
python -m pytest -q tests/test_oddcycle_survivor_a.py
```

Expected: import failure for missing `oracle.oddcycle_survivor_a`.

- [ ] **Step 3: Implement the minimal loader**

Hash result bytes before parsing. Require the tracked schema, exactly one label
`A`, all three frozen digests/references, cell ID/sample/seed/shift/vacuum/row
margin, positive rational weights, equal word/transpose/weight lengths, and
weight sum one. Parse rationals only from `{numerator, denominator}` objects.

- [ ] **Step 4: Run GREEN**

Run the Task-1 test file. Expected: loader tests pass.

- [ ] **Step 5: Write failing exact-transfer tests**

Assert reconstruction returns exact symmetry, vacuum entry 44, and:

```python
margin = min(
    transfer[i, i] - sum(
        abs(transfer[i, j]) for j in range(transfer.cols) if j != i
    )
    for i in range(transfer.rows)
)
assert margin == sp.Rational(12213, 15625)
assert certificate["strict_symmetric_diagonal_dominance"] is True
assert certificate["positive_diagonal"] is True
```

Assert every provided transpose word equals `transpose_word(word)`.

- [ ] **Step 6: Run RED, implement exact reconstruction, run GREEN**

Construct only the twelve declared columns, replay `shift*I + sum(q*Phi)`,
and compute the SPD gates from the exact matrix. Freeze the canonical
rational-matrix SHA-256 in the test after independently printing it once.
Expected: all Task-1 tests pass.

- [ ] **Step 7: Run focused regressions and commit**

```bash
python -m pytest -q \
  tests/test_oddcycle_survivor_a.py \
  tests/test_oddcycle_word_operator.py \
  tests/test_oddcycle_transfer_portfolio.py
git add oracle/oddcycle_survivor_a.py tests/test_oddcycle_survivor_a.py
git commit -m "feat(qmc): reconstruct frozen Survivor A exactly"
```

### Task 2: High-precision logarithm, exact claim boundary, and projections

**Files:**

- Modify: `oracle/oddcycle_survivor_a.py`
- Modify: `tests/test_oddcycle_survivor_a.py`

**Interfaces:**

- Consumes: `SurvivorASeed` and exact transfer from Task 1.
- Produces:

```python
@dataclass(frozen=True)
class HamiltonianAnalysis:
    decimal_places: tuple[int, ...]
    exponential_residuals: tuple[str, ...]
    coordinate_deltas: tuple[str, ...]
    coordinates: tuple[str, ...]
    body_order_norms: tuple[str, ...]

def analyze_hamiltonian(
    transfer: sp.MatrixBase,
    vacuum_value: sp.Rational,
    *,
    decimal_places: tuple[int, ...],
    machine_role: str,
) -> HamiltonianAnalysis: ...

def project_hamiltonian(
    analysis: HamiltonianAnalysis,
    spec: LocalitySpec,
) -> dict[str, object]: ...
```

- [ ] **Step 1: Write failing synthetic precision tests**

Use `diag(1, 2, 3, 4)` with vacuum one and the ladder `(40, 60)`. Assert
the returned coordinates and residuals are decimal strings, the final
exponential residual is below `1e-45`, and changing eigenvector signs cannot
change the reconstructed matrix. Assert `machine_role="windows"` raises
`ValueError("scientific analysis requires machine_role wsl or cpu")`.

- [ ] **Step 2: Run RED**

Expected: missing `analyze_hamiltonian`.

- [ ] **Step 3: Implement the minimal precision ladder**

Use `mpmath.eigsy` on the exact-rational matrix converted at each declared
precision. Reconstruct `H = -V diag(log(lambda)) V.T`, symmetrize, replay
`mp.expm(-H)`, and compile numerical normal-ordered coordinates without
comparing eigenvectors. Serialize all scientific floats as decimal strings
with the precision level.

- [ ] **Step 4: Run GREEN**

Expected: synthetic precision tests pass without running the real seed.

- [ ] **Step 5: Write failing projection tests**

Construct a synthetic coordinate vector with one allowed two-body term and
one forbidden three-body term. Assert projection returns exact label
partitions, `L2`, `Linf`, dominant Hermitian orbits, and the largest
forbidden coefficient. Assert a repeated precision ladder is numerical
evidence only and never sets `exact_forbidden_nonzero=true`.

- [ ] **Step 6: Implement projection, run GREEN, commit**

Only a separately supplied certified interval may set the exact nonzero
gate. Commit after:

```bash
python -m pytest -q tests/test_oddcycle_survivor_a.py
git add oracle/oddcycle_survivor_a.py tests/test_oddcycle_survivor_a.py
git commit -m "feat(qmc): analyze Survivor A Hamiltonian precisely"
```

### Task 3: Selected word construction and one shared coordinate catalog

**Files:**

- Modify: `oracle/oddcycle_word_operator.py`
- Modify: `tests/test_oddcycle_word_operator.py`
- Modify: `oracle/oddcycle_survivor_a.py`
- Modify: `tests/test_oddcycle_survivor_a.py`

**Interfaces:**

```python
def word_pair_column(word: Sequence[int]) -> WordPairColumn: ...

def build_selected_word_dictionary(
    words: Sequence[Sequence[int]],
) -> tuple[WordPairColumn, ...]: ...

def build_coordinate_catalog(
    *,
    maximum_word_length: int,
    output_npy: Path,
    output_metadata: Path,
) -> dict[str, object]: ...

def select_coordinate_catalog(
    *,
    full_catalog_metadata: Path,
    analysis: HamiltonianAnalysis,
    targets: Sequence[TargetPoint],
    settings: Mapping[str, object],
    output_manifest: Path,
) -> dict[str, object]: ...
```

- [ ] **Step 1: Write failing single-word equivalence tests**

For every representative returned by `build_word_dictionary(2)`, assert
`word_pair_column(column.word) == column`. Assert a transpose-equivalent
input resolves to the same exact matrix orbit and duplicate selected inputs
are rejected.

- [ ] **Step 2: Run RED, implement single/selected constructors, run GREEN**

Factor one-column construction out of existing code without changing
`build_word_dictionary` ordering or deduplication. Run:

```bash
python -m pytest -q tests/test_oddcycle_word_operator.py
```

- [ ] **Step 3: Write failing tiny catalog tests**

Build through length two into `tmp_path`. Assert metadata records 252 rows,
the exact ordered word identities, matrix-orbit keys, shape/dtype, and
SHA-256 of the `.npy` bytes. Reopening with `np.load(..., mmap_mode="r")`
must reproduce each exact column converted to float64.

Add a tiny selection fixture and assert `select_coordinate_catalog` writes
the exact selected word identities, four independent score/rank channels,
selection reasons, anchor flags, exact tie-break fields, full-array hash,
analysis hash, settings hash, and its own canonical payload hash. Route-1
cells consume either this `selected.json` identity list or the declared full
catalog; exact promotion rebuilds only the listed active words.

- [ ] **Step 4: Implement one-pass catalog production**

Enumerate raw words once, deduplicate exact matrix orbits once, write the
float array atomically, and hash both array and canonical metadata. Do not
retain thousands of SymPy columns after their row is serialized.

- [ ] **Step 5: Run tests/regressions and commit**

```bash
python -m pytest -q \
  tests/test_oddcycle_word_operator.py \
  tests/test_oddcycle_survivor_a.py \
  tests/test_oddcycle_local_hs_scan.py
git add \
  oracle/oddcycle_word_operator.py \
  oracle/oddcycle_survivor_a.py \
  tests/test_oddcycle_word_operator.py \
  tests/test_oddcycle_survivor_a.py
git commit -m "feat(qmc): build shared oddcycle word catalog"
```

### Task 4: Coordinate-matrix cone scans with retained evidence

**Files:**

- Modify: `oracle/oddcycle_local_hs_scan.py`
- Modify: `tests/test_oddcycle_local_hs_scan.py`

**Interfaces:**

```python
def scan_local_coordinate_kernel(
    coordinates: np.ndarray,
    labels: Sequence[NormalOrderedLabel],
    spec: LocalitySpec,
    *,
    objective_index: int | None = None,
    objective_sign: int | None = None,
) -> NumericalConeResult: ...

def scan_target_coordinate_cone(
    coordinates: np.ndarray,
    labels: Sequence[NormalOrderedLabel],
    target_coordinates: Sequence[sp.Rational],
) -> NumericalConeResult: ...
```

Extend `NumericalConeResult` with optional `primal_residual_vector` and
`equality_marginals`, both NumPy arrays or `None`.

- [ ] **Step 1: Write failing equivalence tests**

For `build_word_dictionary(2)`, compare the new coordinate entry point with
`scan_positive_local_kernel` for every locality and one signed objective.
Statuses, active indices, objective, and maximum residual must match.

- [ ] **Step 2: Run RED, implement shared core, run GREEN**

Refactor both high-level and matrix-level entry points through one internal
solver call. Preserve current status semantics.

- [ ] **Step 3: Write failing evidence/error tests**

On a soluble synthetic matrix assert the full residual vector equals
`A_eq@q-b_eq`. If HiGHS raises `RuntimeError`, assert it propagates to the
runner boundary rather than returning infeasible. If marginals are absent,
store `None`.

- [ ] **Step 4: Implement evidence retention, run regressions, commit**

```bash
python -m pytest -q \
  tests/test_oddcycle_local_hs_scan.py \
  tests/test_oddcycle_local_hs_runner.py
git add oracle/oddcycle_local_hs_scan.py tests/test_oddcycle_local_hs_scan.py
git commit -m "feat(qmc): retain guided cone scan evidence"
```

### Task 5: Exact coordinate targets and affine positive promotion

**Files:**

- Modify: `oracle/oddcycle_local_targets.py`
- Modify: `tests/test_oddcycle_local_targets.py`
- Modify: `oracle/oddcycle_local_hs_exact.py`
- Modify: `tests/test_oddcycle_local_hs_exact.py`

**Interfaces:**

```python
def exact_coordinate_target(
    *,
    target_id: str,
    family: str,
    formula: str,
    coordinates: Mapping[NormalOrderedLabel, sp.Rational],
    locality: LocalitySpec,
    parameters: tuple[tuple[str, sp.Rational], ...] = (),
) -> TargetPoint: ...

def exact_positive_affine_vector(
    matrix: sp.MatrixBase,
    rhs: sp.MatrixBase,
    approximate: np.ndarray,
    *,
    max_denominator: int = 10**9,
) -> tuple[sp.Rational, ...]: ...

def exact_target_hs_certificate(
    columns: Sequence[WordPairColumn],
    weights: np.ndarray,
    target: TargetPoint,
    *,
    max_active_rays: int,
) -> dict[str, object]: ...
```

- [ ] **Step 1: Write failing target-constructor tests**

Build one exact hopping plus density-density target from coordinates. Assert
exact Fock reconstruction, Hermiticity, locality, deterministic ID/formula,
and rejection of non-rational coefficients or forbidden support.

- [ ] **Step 2: Run RED, implement constructor, run GREEN**

Use `reconstruct_normal_ordered`; do not round.

- [ ] **Step 3: Write failing affine-promotion tests**

Cover a unique positive solution, a two-dimensional rational solution face
near an approximate point, a mixed-sign rejection, and an inconsistent
system. Distinguish exact rejection from arithmetic/operational
inconclusive.

- [ ] **Step 4: Implement exact affine solver**

Solve the exact augmented system, parameterize its rational nullspace, and
reuse the existing positive-null-vector strategy. Replay
`matrix*q == rhs` exactly.

- [ ] **Step 5: Write failing full target-certificate test**

Use a tiny exact synthetic target/columns and assert:

```python
assert cert["status"] == "exact-local-target-hs-survivor"
assert cert["strictly_positive_exact_weights"]
assert cert["exact_forbidden_coordinates_zero"]
assert cert["exact_full_fock_replay"]
assert cert["maximum_body_order"] <= 2
assert cert["exact_two_body_nonzero"]
```

- [ ] **Step 6: Implement certificate, run regressions, commit**

```bash
python -m pytest -q \
  tests/test_oddcycle_local_targets.py \
  tests/test_oddcycle_local_hs_exact.py \
  tests/test_oddcycle_local_hs_scan.py
git add \
  oracle/oddcycle_local_targets.py \
  oracle/oddcycle_local_hs_exact.py \
  tests/test_oddcycle_local_targets.py \
  tests/test_oddcycle_local_hs_exact.py
git commit -m "feat(qmc): promote exact local Hamiltonian targets"
```

### Task 6: Deterministic target projection and word scoring

**Files:**

- Modify: `oracle/oddcycle_survivor_a.py`
- Modify: `tests/test_oddcycle_survivor_a.py`

**Interfaces:**

```python
def rationalize_projected_targets(
    analysis: HamiltonianAnalysis,
    *,
    locality_names: tuple[str, ...],
    orbit_counts: tuple[int, ...],
    max_denominator: int,
) -> tuple[TargetPoint, ...]: ...

def score_word_columns(
    coordinates: np.ndarray,
    metadata: Mapping[str, object],
    analysis: HamiltonianAnalysis,
    targets: Sequence[TargetPoint],
    settings: Mapping[str, object],
) -> dict[str, object]: ...
```

- [ ] **Step 1: Write failing rational-target tests**

Assert Hermitian coordinate orbits are included or excluded together, the
pivot becomes exactly one, all coefficients have denominator at most
1,000,000, targets without an exact two-body term are rejected, and input
ordering cannot change target IDs.

- [ ] **Step 2: Run RED, implement target projection, run GREEN**

Use the settings' localities and orbit counts `(8, 12, 16, 24)`.

- [ ] **Step 3: Write failing independent-score tests**

Use a shuffled synthetic catalog with ties. Assert separate
`target_alignment`, `leakage_cancellation`, `locality_ratio`, and `coverage`
ranks, fixed quotas, union selection reasons, all length-at-most-four
anchors, and the exact declared tie break.

- [ ] **Step 4: Implement scores without an opaque aggregate**

Store every score component, rank, selection flag/reasons, settings hash,
analysis hash, coordinate-array hash, and canonical catalog hash.

- [ ] **Step 5: Run focused tests and commit**

```bash
python -m pytest -q tests/test_oddcycle_survivor_a.py
git add oracle/oddcycle_survivor_a.py tests/test_oddcycle_survivor_a.py
git commit -m "feat(qmc): guide local H targets from Survivor A"
```

### Task 7: Resumable attempts, stable shards, and immutable settings

**Files:**

- Create: `oracle/oddcycle_survivor_a_runner.py`
- Create: `tests/test_oddcycle_survivor_a_runner.py`
- Test: `protocols/oddcycle-survivor-a-v1/settings.json`

**Interfaces:**

```python
def load_settings(path: Path) -> dict[str, object]: ...
def freeze_batch_manifest(
    settings: Mapping[str, object],
    *,
    code_commit: str,
    exact_targets: Sequence[TargetPoint],
    selected_catalog: Mapping[str, object],
) -> dict[str, object]: ...
def expand_cells(
    settings: Mapping[str, object],
    batch_manifest: Mapping[str, object],
) -> tuple[dict[str, object], ...]: ...
def shard_owner(cell_id: str, shard_count: int) -> int: ...
def require_runtime_role(command: str, machine_role: str) -> dict[str, str]: ...
def freeze_launch_manifest(
    *,
    settings_path: Path,
    plan_path: Path,
    batch_manifest_path: Path,
    analysis_path: Path,
    catalog_path: Path,
    selected_catalog_path: Path,
    code_commit: str,
    wsl_output: Path,
    cpu_output: str,
) -> dict[str, object]: ...
def run_shard(..., shard_index: int) -> dict[str, object]: ...
def promote_attempts(...) -> dict[str, object]: ...
def collect_shards(...) -> dict[str, object]: ...
def main(argv: Sequence[str] | None = None) -> int: ...
```

- [ ] **Step 1: Write failing settings/cell tests**

Parse the tracked settings and assert its design commit, source hashes,
reviewed implementation-plan path/hash, precision ladder, quotas, 62 CPU
shards, 16,384 Route-2 samples, four disjoint 4,096-sample strategy ranges,
PCG64 seed formula, exact perturbation rules, exact shift/slack rule,
lexicographic objective, and exact output templates. Reject unknown keys,
changed source/plan hashes, invalid template variable names, Windows
scientific role, and strategy ranges that do not cover `[0, 16384)` exactly
once.

- [ ] **Step 2: Run RED, implement strict settings validation, run GREEN**

Implement `require_runtime_role` centrally and call it before every
scientific subcommand does file creation or computation. On Windows each of
`analyze`, `catalog`, `search-shard`, `portfolio-shard`, `promote`, and
`freeze-manifest`, `freeze-launch`, and `collect` must fail. On Linux,
enforce roles:

```text
wsl: analyze, freeze-launch, promote, collect
cpu: catalog, freeze-manifest, search-shard, portfolio-shard
```

Persist platform, role, hostname, thread environment, and code commit in
every artifact.

- [ ] **Step 2a: Write failing canonical batch-manifest tests**

Freeze a tiny manifest and assert every cell explicitly stores:

```text
cell_id, route, exact target ID/formula/parameters or objective label/sign,
column-set ID/hash, owner, settings hash, plan hash, code commit,
and for Route 2 strategy/sample_start/sample_end/derived-seed rule.
```

Assert the real manifest contains every canonical target returned by the
current `first_target_library`, every expanded projected/C5 target, every
permitted two-body label/sign, both column sets, and 62 exactly-once shards
for each Route-2 strategy. Reordering coordinate labels or changing a target
must change the manifest hash. `expand_cells` validates the tracked manifest;
it never silently infers a new batch from the live library.

- [ ] **Step 2b: Implement manifest freeze/validation and run GREEN**

Write canonical `batch-manifest.json` with explicit cell records and a
payload SHA-256. It binds code commit, settings bytes, reviewed plan bytes,
exact targets, and selected catalog bytes. Return its ID-sorted immutable
cell tuple.

- [ ] **Step 3: Write failing stable-owner tests**

Assert:

```python
owner = shard_owner(cell_id, 62)
assert owner == shard_owner(cell_id, 62)
assert owner == int(hashlib.sha256(cell_id.encode()).hexdigest()[:16], 16) % 62
```

Reordering or appending other cells must not change owners.

- [ ] **Step 4: Write failing append-only attempt tests**

Inject one successful computation, one `RuntimeError`, one orphan start, and
one retry. Assert start is durable before compute, no attempt is overwritten,
the error records stage/type/message/bounded traceback, only verified
scientific results receive `terminal.json`, and resume skips only matching
terminal hashes.

- [ ] **Step 5: Implement attempt store and run GREEN**

Reuse the Task-8 canonical JSON, atomic write, and JSONL tail-repair helpers.
Do not edit Task-8 schemas.

- [ ] **Step 6: Write failing collection-conflict tests**

Reject duplicate cell IDs, wrong shard owners, mismatched plan/catalog/code
hashes, missing payloads, and changed payload hashes. Accept a complete
two-shard synthetic inventory.

- [ ] **Step 7: Implement collection/CLI, run tests, commit**

CLI subcommands are exactly:

```text
analyze
catalog
freeze-manifest
freeze-launch
search-shard
portfolio-shard
promote
collect
```

Run:

```bash
python -m pytest -q tests/test_oddcycle_survivor_a_runner.py
git add \
  oracle/oddcycle_survivor_a_runner.py \
  tests/test_oddcycle_survivor_a_runner.py \
  protocols/oddcycle-survivor-a-v1/settings.json
git commit -m "feat(qmc): add resumable Survivor A search runner"
```

### Task 8: Synthetic end-to-end protocol, remote commands, and launch gate

**Files:**

- Modify: `tests/test_oddcycle_survivor_a_runner.py`
- Create: `protocols/oddcycle-survivor-a-v1/README.md`
- Modify: `docs/RESEARCH_OPERATIONS.md` only if a new reusable operational
  lesson is observed.

**Interfaces:**

- Consumes every prior task.
- Produces a reviewed exact command sequence for WSL and CPU, but does not
  claim scientific success until collected artifacts replay.

- [ ] **Step 1: Write failing two-shard end-to-end test**

Use a tiny injected coordinate catalog, one free cell, one target cell, one
Route-2 shard, an injected first-attempt failure, resumed success, one exact
promotion, and collection. Assert every planned cell is accounted for and
scientific versus compute status counts are separate.

- [ ] **Step 2: Run RED, implement missing integration, run GREEN**

Run:

```bash
python -m pytest -q \
  tests/test_oddcycle_survivor_a.py \
  tests/test_oddcycle_survivor_a_runner.py
```

- [ ] **Step 3: Write the exact protocol README**

Document these immutable phases and CLI commands:

```bash
python -m oracle.oddcycle_survivor_a_runner analyze \
  --settings protocols/oddcycle-survivor-a-v1/settings.json \
  --machine-role wsl \
  --output "$WSL_OUTPUT"

python -m oracle.oddcycle_survivor_a_runner catalog \
  --settings protocols/oddcycle-survivor-a-v1/settings.json \
  --analysis "$WSL_OUTPUT/analysis.json" \
  --machine-role cpu \
  --output "$CPU_OUTPUT"

python -m oracle.oddcycle_survivor_a_runner freeze-manifest \
  --settings protocols/oddcycle-survivor-a-v1/settings.json \
  --analysis "$CPU_OUTPUT/analysis.json" \
  --catalog "$CPU_OUTPUT/catalog.json" \
  --selected-catalog "$CPU_OUTPUT/selected.json" \
  --code-commit "$CODE_COMMIT" \
  --machine-role cpu \
  --output "$CPU_OUTPUT/batch-manifest.json"

```

At this point, and before any shard command, checksum-copy `catalog.json`,
`selected.json`, `coordinates.npy`, and `batch-manifest.json` from CPU to
WSL. Then create the only authoritative launch closure:

```bash
python -m oracle.oddcycle_survivor_a_runner freeze-launch \
  --settings protocols/oddcycle-survivor-a-v1/settings.json \
  --plan docs/superpowers/plans/2026-07-30-survivor-a-hamiltonian-search.md \
  --batch-manifest "$WSL_OUTPUT/batch-manifest.json" \
  --analysis "$WSL_OUTPUT/analysis.json" \
  --catalog "$WSL_OUTPUT/catalog.json" \
  --selected-catalog "$WSL_OUTPUT/selected.json" \
  --code-commit "$CODE_COMMIT" \
  --wsl-output "$WSL_OUTPUT" \
  --cpu-output "$CPU_OUTPUT" \
  --machine-role wsl \
  --output "$WSL_OUTPUT/launch.json"
```

Checksum-copy that exact `launch.json` back to CPU. Only then launch:

```bash
python -m oracle.oddcycle_survivor_a_runner search-shard \
  --launch "$CPU_OUTPUT/launch.json" \
  --catalog "$CPU_OUTPUT/catalog.json" \
  --selected-catalog "$CPU_OUTPUT/selected.json" \
  --machine-role cpu \
  --shard-index "$SHARD" \
  --output "$CPU_OUTPUT/search"

python -m oracle.oddcycle_survivor_a_runner portfolio-shard \
  --launch "$CPU_OUTPUT/launch.json" \
  --analysis "$CPU_OUTPUT/analysis.json" \
  --catalog "$CPU_OUTPUT/catalog.json" \
  --selected-catalog "$CPU_OUTPUT/selected.json" \
  --machine-role cpu \
  --shard-index "$SHARD" \
  --output "$CPU_OUTPUT/portfolio"

python -m oracle.oddcycle_survivor_a_runner promote \
  --launch "$WSL_OUTPUT/launch.json" \
  --analysis "$WSL_OUTPUT/analysis.json" \
  --catalog "$WSL_OUTPUT/catalog.json" \
  --selected-catalog "$WSL_OUTPUT/selected.json" \
  --incoming "$WSL_OUTPUT/incoming" \
  --machine-role wsl \
  --output "$WSL_OUTPUT/promotions"

python -m oracle.oddcycle_survivor_a_runner collect \
  --launch "$WSL_OUTPUT/launch.json" \
  --analysis "$WSL_OUTPUT/analysis.json" \
  --catalog "$WSL_OUTPUT/catalog.json" \
  --selected-catalog "$WSL_OUTPUT/selected.json" \
  --search "$WSL_OUTPUT/search" \
  --portfolio "$WSL_OUTPUT/portfolio" \
  --promotions "$WSL_OUTPUT/promotions" \
  --machine-role wsl \
  --output "$WSL_OUTPUT/result.json"
```

Define `WSL_OUTPUT` and `CPU_OUTPUT` by expanding the exact settings templates
with the verified code commit and settings SHA-256. The exact WSL-side SSH
alias is `nnv-cpu-worker`; its private local SSH config supplies host, user,
and key. Document and test these hash-verified transfers:

```bash
rsync -a --checksum "$WSL_OUTPUT/analysis.json" \
  "nnv-cpu-worker:$CPU_OUTPUT/analysis.json"

rsync -a --checksum \
  "nnv-cpu-worker:$CPU_OUTPUT/catalog.json" \
  "nnv-cpu-worker:$CPU_OUTPUT/selected.json" \
  "nnv-cpu-worker:$CPU_OUTPUT/coordinates.npy" \
  "nnv-cpu-worker:$CPU_OUTPUT/batch-manifest.json" \
  "$WSL_OUTPUT/"

rsync -a --checksum "$WSL_OUTPUT/launch.json" \
  "nnv-cpu-worker:$CPU_OUTPUT/launch.json"

rsync -a --checksum \
  "nnv-cpu-worker:$CPU_OUTPUT/search/" \
  "nnv-cpu-worker:$CPU_OUTPUT/portfolio/" \
  "$WSL_OUTPUT/incoming/"
```

After every transfer, compare sender/receiver SHA-256 for each declared file.
Launch all shard IDs exactly once with `seq 0 61`; each shard validates its
owner records from the tracked batch manifest.

- [ ] **Step 3a: Freeze the launch manifest**

Write a failing test for `freeze_launch_manifest`: it must bind byte SHA-256
values for settings, reviewed plan, batch manifest, analysis, catalog, and
selected catalog; the exact code commit; canonical WSL/CPU output paths;
allowed roles; exact shard IDs `0..61`; and its own canonical payload hash.
Changing any input byte, path, role, shard, or code commit must make launch
validation fail. Implement the API and `freeze-launch` CLI, generate the
manifest on WSL after the CPU artifacts return, and copy identical bytes to
CPU. Every later production subcommand accepts `--launch`, hashes all
referenced inputs, and rejects a stale plan/settings/batch/analysis/catalog/
selected-catalog/code identity before work.

- [ ] **Step 4: Run the complete Linux regression on WSL**

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0 \
python -m pytest -q \
tests/test_oddcycle_survivor_a.py \
tests/test_oddcycle_survivor_a_runner.py \
tests/test_oddcycle_word_operator.py \
tests/test_oddcycle_transfer_portfolio.py \
tests/test_oddcycle_local_hs_scan.py \
tests/test_oddcycle_local_hs_exact.py \
tests/test_oddcycle_local_targets.py \
tests/test_oddcycle_local_hs_runner.py
```

Expected: all pass at the exact code commit.

- [ ] **Step 5: Independent code/evidence review**

The reviewer must confirm TDD evidence, exact-vs-float boundaries, stable
sharding, complete settings coverage, no Windows scientific path, no
Task-8 schema changes, and secret-free commands. Fix every Critical or
Important finding and re-review.

- [ ] **Step 6: Commit, push, verify, then launch**

```bash
git add \
  tests/test_oddcycle_survivor_a_runner.py \
protocols/oddcycle-survivor-a-v1/README.md \
  protocols/oddcycle-survivor-a-v1/batch-manifest.json \
  protocols/oddcycle-survivor-a-v1/launch.json \
  docs/RESEARCH_OPERATIONS.md
git commit -m "docs(qmc): freeze Survivor A production protocol"
git push shared work/zibo/representation-cones
git ls-remote shared refs/heads/work/zibo/representation-cones
```

Only after the remote SHA equals local HEAD, launch `analyze` on WSL and
`catalog -> search-shard/portfolio-shard` on CPU. Monitor through artifact
settle time; process state alone is not success.

## Plan self-review

- Spec coverage: fixed transfer, exact SPD, high precision, target projection,
  full length-six catalog, independent scoring, exact affine promotion,
  two scientific routes, stable shards, failures, and lattice claim boundary
  all map to Tasks 1-8.
- Placeholder scan: no `TODO`, `TBD`, “similar to,” or unspecified behavior
  remains.
- Type consistency: Task-1 seed/transfer feeds Task 2; Task-3 catalog feeds
  Tasks 4/6/7; Task-5 targets/certificates feed Task 7; Task 7 CLI names and
  Task-8 commands agree.
- Execution boundary: remote science cannot launch before Task-8 review,
  commit, push, and SHA equality.
