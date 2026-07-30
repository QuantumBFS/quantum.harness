# Challenge 194 Production Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and gate the first post-Day-0 subproject: a deterministic, Numba-compiled Philox/Poisson/Newman-Ziff engine with independently testable semantics, restartable immutable artifacts, and a fail-closed local correctness/performance decision.

**Architecture:** Python owns canonical request validation, independent mathematical references, stream derivation, artifact publication, validation, and benchmark orchestration. Numba owns only fixed-dtype numerical kernels: Philox draws, alias sampling, open-address membership, incremental union-find, and the monotone event loop; independent Python and compiled implementations meet only at immutable kernel/request inputs and validation outputs.

**Tech Stack:** CPython 3.12, NumPy 2.2.6, SciPy 1.15.3, h5py 3.14.0, the latest Python-3.12/NumPy-2.2.6-compatible Numba resolved by `uv add numba` and then exactly pinned in `pyproject.toml` and `uv.lock`, pytest, uv.

## Global Constraints

- All committed implementation stays under this challenge directory.
- No implementation is copied from ONMC.
- The existing quadratic and geometric samplers remain independent scientific oracles.
- The production engine uses Philox4x32-10 with published Random123 test vectors.
- Each trajectory receives a disjoint key derived from:

```text
(master_seed, phase, L, sigma_grid_id, replica, stream_id)
```

- The derivation is canonical, versioned, and hashed.
- Pilot and confirmatory phases use distinct namespaces.
- Thread count, job-array order, retries, and machine scheduling cannot change a trajectory stream.
- Floating uniforms use a fixed open-interval mapping.
- Uniform integers use rejection sampling, never modulo reduction.
- Alias-column, alias-threshold, edge-offset, and exponential draws use registered stream identifiers so refactoring one draw family cannot silently perturb another.
- For each exact `(L, sigma)`, construct the immutable class weights

```text
w_d = M_d J_d
Lambda = sum_d w_d
```

- Repeated events are required by the Poisson construction and are not treated as errors.
- Open-edge membership uses a deterministic open-addressed hash set whose load factor never exceeds 0.70.
- Optimization may change layout, compilation strategy, and batching, but not model semantics, RNG mapping, retained observables, or artifact schemas without repeating validation.
- One trajectory is the smallest restart unit.
- Existing valid artifacts are never overwritten.
- Stale, extra, partially published, or hash-mismatched files fail closed.
- The raw batch schema stores every trajectory as the resampling unit and keeps all retained couplings from that trajectory together.
- Aggregates never replace raw batches.
- Statistical checks use fixed seeds and preregistered familywise thresholds.
- No failed seed is replaced.
- Exact invariants use exact or deterministic floating tolerances.
- The gate publishes a machine-readable report with raw counts and margins to every threshold.
- Correctness and performance are separate gates.
- steady-state wall time at most 120 seconds on one CPU core;
- peak resident memory at most 4 GiB.
- Compilation time is measured and reported separately.
- The gate uses fresh subprocesses, reports median and maximum values over five steady-state runs, and does not hide failed or outlying runs.
- A standalone C++17 backend is authorized only if the measured Numba engine fails either part of this frozen gate on one complete `L = 2^18` trajectory through the full pilot kappa grid, including basic observables.
- Pilot execution is forbidden until the production engine passes the three-way sampler gate.
- Any three-way sampler disagreement blocks pilot execution.
- Numba performance-gate failure triggers a recorded optimization pass and then, if still failing, a separately validated C++17 backend.
- This plan ends at the Numba capability decision. It excludes pilot runs, cluster submission, confirmatory production, physics fits, figures, final reporting, and C++ implementation.
- All implementation tasks use strict RED then GREEN test cycles.
- Every local commit stages only the paths named by its task; `git add .` is forbidden.

---

## File Map

- `pyproject.toml` — exact Numba runtime pin after resolver selection.
- `uv.lock` — complete resolved environment, including Numba and llvmlite.
- `src/long_range_percolation/runtime.py` — runtime fingerprint and Numba capability metadata.
- `src/long_range_percolation/counter_rng.py` — canonical stream derivation plus pure-Python and Numba Philox4x32-10 primitives.
- `src/long_range_percolation/alias.py` — immutable deterministic distance-class Walker table and compiled draw primitive.
- `src/long_range_percolation/edge_set.py` — full-range `uint64` open-address set and diagnostics.
- `src/long_range_percolation/observables.py` — basic observable schema and deterministic root-scan summaries.
- `src/long_range_percolation/production_union_find.py` — array-only incremental union-find state and compiled updates.
- `src/long_range_percolation/poisson_reference.py` — independently structured exact monotone Python semantics.
- `src/long_range_percolation/poisson_sweep.py` — Numba event engine and immutable trajectory result.
- `src/long_range_percolation/validation.py` — fixed validation protocol, raw statistics, threshold margins, and gate report.
- `src/long_range_percolation/artifacts.py` — canonical schemas, semantic reload, fsync, atomic publication, and restart reconstruction.
- `src/long_range_percolation/benchmark.py` — subprocess protocol, metrics, frozen gate, optimization ledger, and backend decision.
- `src/long_range_percolation/__init__.py` — production-engine public API exports.
- `tests/data/random123_philox4x32_10.json` — published Random123 vectors with source citation.
- `tests/test_runtime.py` — pinning, fresh-process import, and capability metadata.
- `tests/test_counter_rng.py` — vectors, stream separation, open uniforms, rejection accounting, and numeric boundaries.
- `tests/test_alias.py` — deterministic construction, invariants, and simultaneous frequency gate.
- `tests/test_edge_set.py` — full `uint64` domain, growth, probes, and stream-preserving behavior.
- `tests/test_production_union_find.py` — incremental moments, deterministic ties, sector masks, and root-scan agreement.
- `tests/test_poisson_reference.py` — independent event semantics and analytic Poisson/Bernoulli laws.
- `tests/test_poisson_sweep.py` — scripted semantic equivalence, Numba execution, extremes, and scheduling invariance.
- `tests/test_validation.py` — fixed family definitions, raw margins, all-graph and three-way acceptance.
- `tests/test_artifacts.py` — crash consistency, immutable publication, corruption rejection, and reconstruction.
- `tests/test_benchmark.py` — fresh subprocesses, warmup separation, five-run aggregation, frozen thresholds, and fallback report.
- `scripts/validate_production.py` — one-command correctness report.
- `scripts/benchmark_production.py` — one-command compilation/steady-state capability report.
- `scripts/decide_production_backend.py` — fail-closed optimization/revalidation and Numba-versus-C++ decision report.
- `README.md` — post-Day-0 setup, local gates, artifact locations, and phase boundary.

All paths in tasks below are relative to
`tracks/qmc/solutions/frustration-free/challenge-194/`. Commands run from that
directory unless a command explicitly starts with `git -C`.

---

## Shared Interface and Type Contract

The following names and types are frozen across tasks. Host dataclasses may
contain strings and dictionaries; every `@numba.njit` boundary receives only
scalars and contiguous NumPy arrays with the stated dtype.

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

import numpy as np
import numpy.typing as npt

Phase = Literal["validation", "benchmark", "pilot", "confirmatory"]
U8 = npt.NDArray[np.uint8]
U32 = npt.NDArray[np.uint32]
U64 = npt.NDArray[np.uint64]
I64 = npt.NDArray[np.int64]
F64 = npt.NDArray[np.float64]

STREAM_ALIAS_COLUMN: int = 0
STREAM_ALIAS_THRESHOLD: int = 1
STREAM_EDGE_OFFSET: int = 2
STREAM_EXPONENTIAL: int = 3
STREAM_COUNT: int = 4

@dataclass(frozen=True)
class StreamIdentity:
    master_seed: int
    phase: Phase
    length: int
    sigma_grid_id: str
    replica: int
    stream_id: int

@dataclass(frozen=True)
class StreamMaterial:
    key: U32                 # shape (2,)
    initial_counter: U32     # shape (4,)
    material_sha256: str

@dataclass(frozen=True)
class AliasTable:
    probability: F64         # shape (L // 2,)
    alias: I64               # shape (L // 2,)
    multiplicity: U64        # shape (L // 2,)
    class_weight: F64        # shape (L // 2,)
    total_rate: float
    kernel_sha256: str
    normalized_residual: float

@dataclass(frozen=True)
class BasicObservables:
    open_edges: int
    component_count: int
    largest_size: int
    second_largest_size: int
    s1_fraction: float
    s2_fraction: float
    sum_size_sq: float
    sum_size_fourth: float
    q_g: float
    four_sector_crossing: bool

@dataclass(frozen=True)
class TrajectoryRequest:
    length: int
    sigma: float
    sigma_grid_id: str
    kappas: F64              # finite, sorted, unique, nonnegative
    master_seed: int
    phase: Phase
    replica: int
    kernel_sha256: str

@dataclass(frozen=True)
class TrajectoryResult:
    request_sha256: str
    observables: F64         # shape (n_kappa, 10), fixed column order
    terminal_counters: U32   # shape (STREAM_COUNT, 4)
    draw_counts: U64         # shape (STREAM_COUNT, 3): words, blocks, rejections
    event_count: int
    duplicate_count: int
    hash_diagnostics: U64    # capacity, size, total probes, max probe, rehashes
```

`TrajectoryResult.observables` columns are, in order:
`open_edges`, `component_count`, `largest_size`, `second_largest_size`,
`s1_fraction`, `s2_fraction`, `sum_size_sq`, `sum_size_fourth`, `q_g`,
`four_sector_crossing`. Integer-valued columns are exactly representable for
the scoped sizes; moments are `float64` because `L^4` exceeds `uint64` at
`L = 2^18`.

---

### Task 1: Resolve and Pin Numba Runtime

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `src/long_range_percolation/runtime.py`
- Create: `tests/test_runtime.py`

**Interfaces:**
- Produces `runtime_capability() -> dict[str, object]`.
- The dictionary has exactly `schema_version`, `python`, `implementation`,
  `platform`, `machine`, `numpy`, `scipy`, `h5py`, `numba`, `llvmlite`,
  `cpu_name`, `cpu_features`, `threading_layer`, `numba_disable_jit`,
  `fastmath`, and `boundscheck`.
- `schema_version == "challenge-194-runtime-v1"`, `fastmath is False`, and
  `boundscheck is True` for correctness commands.

- [ ] **Step 1: Write the failing runtime tests**

```python
import importlib.metadata
import json
import subprocess
import sys

from long_range_percolation.runtime import runtime_capability


def test_numba_is_exactly_pinned_and_imports_in_fresh_python():
    declared = open("pyproject.toml", encoding="utf-8").read()
    version = importlib.metadata.version("numba")
    assert f'"numba=={version}"' in declared
    completed = subprocess.run(
        [sys.executable, "-c", "import numba, numpy; print(numba.__version__)"],
        check=True, capture_output=True, text=True,
    )
    assert completed.stdout.strip() == version


def test_runtime_capability_is_complete_and_json_stable():
    first = runtime_capability()
    second = runtime_capability()
    assert first == second
    assert first["schema_version"] == "challenge-194-runtime-v1"
    assert first["fastmath"] is False
    assert first["boundscheck"] is True
    assert json.loads(json.dumps(first, sort_keys=True)) == first
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `uv run pytest tests/test_runtime.py -q`

Expected: collection fails with
`ModuleNotFoundError: No module named 'long_range_percolation.runtime'`.

- [ ] **Step 3: Resolve, then pin the actual compatible Numba version**

Run:

```bash
uv add numba
uv run python -c 'import importlib.metadata as m; print(m.version("numba")); print(m.version("llvmlite"))'
NUMBA_VERSION="$(uv run python -c 'import importlib.metadata as m; print(m.version("numba"))')"
uv add "numba==$NUMBA_VERSION"
uv lock
uv sync --frozen
```

Expected: the first `uv add numba` succeeds for Python 3.12 and NumPy 2.2.6;
the second `uv add` replaces the resolver's range with equality to the exact
installed version; `uv sync --frozen` makes no lockfile changes. No version is
guessed before resolution.

- [ ] **Step 4: Implement deterministic capability capture**

```python
from __future__ import annotations

import importlib.metadata
import os
import platform
import sys

import numba


def runtime_capability() -> dict[str, object]:
    return {
        "schema_version": "challenge-194-runtime-v1",
        "python": platform.python_version(),
        "implementation": sys.implementation.name,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy": importlib.metadata.version("numpy"),
        "scipy": importlib.metadata.version("scipy"),
        "h5py": importlib.metadata.version("h5py"),
        "numba": importlib.metadata.version("numba"),
        "llvmlite": importlib.metadata.version("llvmlite"),
        "cpu_name": numba.config.CPU_NAME or "",
        "cpu_features": numba.config.CPU_FEATURES or "",
        "threading_layer": os.environ.get("NUMBA_THREADING_LAYER", ""),
        "numba_disable_jit": bool(numba.config.DISABLE_JIT),
        "fastmath": False,
        "boundscheck": True,
    }
```

- [ ] **Step 5: Run GREEN and the complete Day-0 regression suite**

Run:

```bash
uv sync --frozen
uv run pytest tests/test_runtime.py -q
uv run pytest -q
```

Expected: runtime tests pass; every pre-existing Day-0 test remains green.

- [ ] **Step 6: Commit the resolved runtime**

```bash
git add pyproject.toml uv.lock \
  src/long_range_percolation/runtime.py tests/test_runtime.py
git commit -m "Pin production Numba runtime"
```

---

### Task 2: Philox4x32-10 and Stream Contract

**Files:**
- Create: `tests/data/random123_philox4x32_10.json`
- Create: `src/long_range_percolation/counter_rng.py`
- Create: `tests/test_counter_rng.py`

**Interfaces:**
- Produces `derive_stream_material(identity: StreamIdentity) -> StreamMaterial`.
- Produces `philox4x32_10_reference(counter: U32, key: U32) -> U32`.
- Produces Numba-callable
  `philox4x32_10(counter: U32, key: U32, out: U32) -> None`.
- Produces Numba-callable
  `next_u32(counter, key, block, lane_and_valid, accounting) -> np.uint32`.
- Produces Numba-callable
  `uniform_open(counter, key, block, lane_and_valid, accounting) -> float`.
- Produces Numba-callable
  `bounded_u32(bound, counter, key, block, lane_and_valid, accounting) -> np.uint32`.
- `lane_and_valid` is `uint8[2]` (`lane`, `valid`); `accounting` is
  `uint64[3]` (`words`, `blocks`, `rejections`).

- [ ] **Step 1: Add published vectors and failing vector tests**

Create the JSON fixture with source
`https://github.com/DEShawResearch/random123/blob/main/tests/kat_vectors`
and these published Philox4x32-10 cases:

```json
{
  "algorithm": "Philox4x32-10",
  "source": "https://github.com/DEShawResearch/random123/blob/main/tests/kat_vectors",
  "vectors": [
    {
      "counter": ["00000000", "00000000", "00000000", "00000000"],
      "key": ["00000000", "00000000"],
      "output": ["6627e8d5", "e169c58d", "bc57ac4c", "9b00dbd8"]
    },
    {
      "counter": ["ffffffff", "ffffffff", "ffffffff", "ffffffff"],
      "key": ["ffffffff", "ffffffff"],
      "output": ["408f276d", "41c83b0e", "a20bc7c6", "6d5451fd"]
    }
  ]
}
```

```python
def test_reference_and_numba_philox_match_published_vectors():
    vectors = json.loads(Path("tests/data/random123_philox4x32_10.json").read_text())
    for case in vectors["vectors"]:
        counter = np.array([int(x, 16) for x in case["counter"]], np.uint32)
        key = np.array([int(x, 16) for x in case["key"]], np.uint32)
        expected = np.array([int(x, 16) for x in case["output"]], np.uint32)
        np.testing.assert_array_equal(philox4x32_10_reference(counter, key), expected)
        actual = np.empty(4, np.uint32)
        philox4x32_10(counter, key, actual)
        np.testing.assert_array_equal(actual, expected)
```

- [ ] **Step 2: Add failing stream, conversion, and rejection tests**

```python
def test_stream_identity_is_canonical_and_domain_separated():
    base = StreamIdentity(7, "validation", 256, "sigma-1-binary", 3, 0)
    materials = [
        derive_stream_material(dataclasses.replace(base, stream_id=stream))
        for stream in range(STREAM_COUNT)
    ]
    assert len({item.material_sha256 for item in materials}) == STREAM_COUNT
    assert len({item.key.tobytes() + item.initial_counter.tobytes()
                for item in materials}) == STREAM_COUNT
    repeated = derive_stream_material(base)
    np.testing.assert_array_equal(repeated.key, materials[0].key)
    np.testing.assert_array_equal(repeated.initial_counter, materials[0].initial_counter)
    assert repeated.material_sha256 == materials[0].material_sha256
    changed = derive_stream_material(dataclasses.replace(base, phase="benchmark"))
    assert changed.material_sha256 != materials[0].material_sha256


def test_uniform_open_excludes_endpoints_for_extreme_words():
    assert u32_to_open(np.uint32(0)) == 2.0 ** -33
    assert u32_to_open(np.uint32(0xFFFFFFFF)) == 1.0 - 2.0 ** -33


@pytest.mark.parametrize("bound", [1, 3, 7, 2**31 - 1, 2**31, 2**32 - 1])
def test_bounded_u32_matches_reference_and_accounts_for_every_rejection(bound):
    threshold = ((1 << 32) - bound) % bound
    words = [max(0, threshold - 1), threshold, 0xFFFFFFFF]
    ref_value, ref_state = bounded_u32_from_words_reference(bound, words)
    value, state = bounded_u32_from_words_compiled(bound, words)
    assert value == ref_value
    assert state.words == ref_state.words
    assert state.rejections == ref_state.rejections
    assert 0 <= value < bound
```

Also test carry from counters
`[0xffffffff, 0xffffffff, 0xffffffff, 0]` and rejection sequences that consume
multiple Philox blocks. The reference generator must be ordinary Python and
must not call a jitted function. The two named `bounded_u32_from_words_*`
helpers are test-only adapters defined in `tests/test_counter_rng.py`; each
returns `(value, Accounting(words: int, blocks: int, rejections: int))` and
raises `AssertionError` if the supplied finite word tape is exhausted.

- [ ] **Step 3: Run the RNG tests and verify RED**

Run: `uv run pytest tests/test_counter_rng.py -q`

Expected: collection fails because `counter_rng.py` does not exist.

- [ ] **Step 4: Implement stream derivation and pure reference Philox**

Use canonical JSON with sorted keys, ASCII separators `(",", ":")`, and
integer range checks `master_seed, replica in [0, 2**64)` and
`stream_id in [0, STREAM_COUNT)`. Hash
`b"challenge-194-philox-stream-v1\0" + canonical_json` with SHA-256. Decode
digest bytes `[0:8]` as two little-endian key words, bytes `[8:24]` as four
little-endian initial-counter words, and retain the full digest hex as
`material_sha256`. Construct all four materials before a trajectory and reject
any duplicate `(key, initial_counter)` pair.

```python
PHILOX_M0 = np.uint32(0xD2511F53)
PHILOX_M1 = np.uint32(0xCD9E8D57)
PHILOX_W0 = np.uint32(0x9E3779B9)
PHILOX_W1 = np.uint32(0xBB67AE85)
RNG_VERSION = "philox4x32-10/open32-v1/bounded-reject-v1"


def u32_to_open(word: np.uint32) -> float:
    return (float(word) + 0.5) * (2.0 ** -32)
```

Implement each Philox round with explicit 32-bit masks after Python integer
multiplication. Keep this reference separate from the compiled multiply-high
helper.

- [ ] **Step 5: Implement Numba primitives with explicit fixed dtypes**

Use `@numba.njit(cache=True, boundscheck=True, fastmath=False)`. Compute
`product = np.uint64(multiplier) * np.uint64(word)`, low with
`np.uint32(product & np.uint64(0xffffffff))`, and high with
`np.uint32(product >> np.uint64(32))`. Increment the four-word counter
little-endian with carry after materializing each block.

For `bounded_u32`, require `1 <= bound <= 0xffffffff`, set
`threshold = ((1 << 32) - bound) % bound` using `uint64`, reject while
`word < threshold`, increment `rejections` for each rejected word, and return
`word % bound` only after acceptance. `words` increments for every consumed
word, including rejected words; `blocks` increments for every generated
four-word block. This modulo after rejection is required and is not biased
modulo reduction.

- [ ] **Step 6: Run GREEN, disabled-JIT parity, and full regressions**

Run:

```bash
uv run pytest tests/test_counter_rng.py -q
NUMBA_DISABLE_JIT=1 uv run pytest tests/test_counter_rng.py -q
uv run pytest -q
```

Expected: published vectors, boundary cases, accounting, and both execution
modes pass; Day-0 tests remain green.

- [ ] **Step 7: Commit RNG files**

```bash
git add src/long_range_percolation/counter_rng.py \
  tests/test_counter_rng.py tests/data/random123_philox4x32_10.json
git commit -m "Add deterministic Philox counter streams"
```

---

### Task 3: Deterministic Distance-Class Alias Table

**Files:**
- Create: `src/long_range_percolation/alias.py`
- Create: `tests/test_alias.py`

**Interfaces:**
- Produces
  `build_distance_alias(length: int, sigma: float, kernel: F64, kernel_sha256: str) -> AliasTable`.
- Produces Numba-callable
  `draw_alias(probability: F64, alias: I64, column_word: np.uint32, threshold_word: np.uint32) -> int`.
- Construction order is increasing distance; worklists are FIFO arrays, not
  Python sets or heaps.

- [ ] **Step 1: Write failing deterministic and invariant tests**

```python
def test_alias_table_is_deterministic_and_read_only():
    kernel = periodic_kernel(256, 0.9)
    first = build_distance_alias(256, 0.9, kernel, sha256(kernel.tobytes()).hexdigest())
    second = build_distance_alias(256, 0.9, kernel.copy(), first.kernel_sha256)
    np.testing.assert_array_equal(first.probability, second.probability)
    np.testing.assert_array_equal(first.alias, second.alias)
    assert not first.probability.flags.writeable
    assert not first.alias.flags.writeable


def test_alias_invariants_cover_antipodal_class_and_finite_extremes():
    for length, sigma in [(2, 1.0), (256, math.ulp(1.0)), (256, 128.0)]:
        kernel = periodic_kernel(length, sigma)
        table = build_distance_alias(length, sigma, kernel, digest(kernel))
        assert np.all((0.0 <= table.probability) & (table.probability <= 1.0))
        assert np.all((0 <= table.alias) & (table.alias < length // 2))
        assert table.multiplicity[-1] == length // 2
        assert table.total_rate == pytest.approx(kernel_weight_sum(length, sigma), rel=2e-13)
        assert abs(table.normalized_residual) <= 8 * np.finfo(float).eps
```

- [ ] **Step 2: Write the failing simultaneous frequency test**

Use `n = 2_000_000`, fixed Philox identity
`(194, validation, 256, "alias-sigma-0.9", 0, stream)`, and simultaneous
threshold

```python
epsilon = math.sqrt(math.log(2 * class_count / 0.001) / (2 * n))
assert max(abs(observed / n - expected)) <= epsilon
```

Store every class's observed count, expected probability, absolute error,
threshold, and `margin = threshold - absolute_error` in the assertion message.

- [ ] **Step 3: Run alias tests and verify RED**

Run: `uv run pytest tests/test_alias.py -q`

Expected: collection fails because `alias.py` does not exist.

- [ ] **Step 4: Implement deterministic Walker construction**

Validate exact shape `(length // 2,)`, finite positive kernel values, and
matching SHA-256. Form multiplicities in `uint64`, class weights in `float64`,
and `total_rate = math.fsum(float(x) for x in class_weight)`. Normalize by
`total_rate`, scale by class count, enqueue indices with scaled weight `< 1`
into the small FIFO and all others into the large FIFO, then process in queue
order. Clamp only final roundoff within eight ulps of `[0, 1]`; reject larger
violations. Freeze defensive copies.

`draw_alias` maps `column_word` with multiply-high
`(uint64(column_word) * uint64(n)) >> 32`, maps `threshold_word` through
`u32_to_open`, and returns the column when the open uniform is
`<= probability[column]`, otherwise `alias[column]`. It consumes exactly the
two supplied words and does not own stream state.

- [ ] **Step 5: Run GREEN and regressions**

Run:

```bash
uv run pytest tests/test_alias.py -q
uv run pytest -q
```

Expected: deterministic invariants and the one simultaneous frequency family
pass.

- [ ] **Step 6: Commit alias implementation**

```bash
git add src/long_range_percolation/alias.py tests/test_alias.py
git commit -m "Add deterministic distance alias table"
```

---

### Task 4: Full-Range uint64 Open-Address Edge Set

**Files:**
- Create: `src/long_range_percolation/edge_set.py`
- Create: `tests/test_edge_set.py`

**Interfaces:**
- Produces host constructor
  `allocate_edge_set(expected_size: int) -> tuple[U64, U8, U64]`.
- Produces Numba-callable
  `edge_set_insert(keys: U64, occupied: U8, diagnostics: U64, value: np.uint64) -> tuple[U64, U8, bool]`.
- Produces `encode_edge_id(class_start: U64, distance_index: int, offset: int) -> np.uint64`.
- Diagnostics are `[capacity, size, total_probes, max_probe, rehashes]`.
- Occupancy is separate from keys, so every `uint64`, including `0` and
  `2**64 - 1`, is representable.

- [ ] **Step 1: Write failing sentinel, growth, and probe tests**

```python
def test_edge_set_accepts_entire_uint64_domain_without_sentinel_collision():
    values = np.array([0, 1, 2**63, 2**64 - 2, 2**64 - 1], np.uint64)
    keys, occupied, diagnostics = allocate_edge_set(1)
    for value in values:
        keys, occupied, inserted = edge_set_insert(keys, occupied, diagnostics, value)
        assert inserted
    for value in values:
        keys, occupied, inserted = edge_set_insert(keys, occupied, diagnostics, value)
        assert not inserted
    assert diagnostics[1] == len(values)
    assert diagnostics[0] & (diagnostics[0] - 1) == 0
    assert diagnostics[1] / diagnostics[0] <= 0.70


def test_growth_is_deterministic_and_does_not_consume_rng():
    values = np.arange(10_000, dtype=np.uint64) * np.uint64(0x9E3779B97F4A7C15)
    first = insert_all(values)
    second = insert_all(values)
    assert first.diagnostics.tolist() == second.diagnostics.tolist()
    np.testing.assert_array_equal(first.keys, second.keys)
    np.testing.assert_array_equal(first.occupied, second.occupied)
```

Add collision-crafted tests that assert `total_probes >= size`,
`max_probe > 1`, and `rehashes > 0`, plus edge-ID tests proving all
distance-class ranges are disjoint and cover exactly
`[0, L*(L-1)//2)` for `L in (2, 8, 256)`.

- [ ] **Step 2: Run tests and verify RED**

Run: `uv run pytest tests/test_edge_set.py -q`

Expected: collection fails because `edge_set.py` does not exist.

- [ ] **Step 3: Implement fixed-dtype hashing and deterministic growth**

Use the SplitMix64 finalizer, power-of-two capacities, linear probing, and an
`occupied: uint8[capacity]` array. Count one probe for every inspected slot.
Before inserting a new value, grow when
`10 * (size + 1) > 7 * capacity`; double capacity, reinsert occupied slots in
ascending old-slot order, and include rehash probes in `total_probes`. Reject
capacity overflow before allocation. The hash set receives no RNG state and
cannot affect draw accounting.

Build `class_start` by a checked `uint64` prefix sum of class multiplicities.
`encode_edge_id` validates the distance index and offset on the host; the
compiled event loop uses the prevalidated expression
`class_start[distance_index] + uint64(offset)`.

- [ ] **Step 4: Run GREEN under JIT and disabled JIT**

Run:

```bash
uv run pytest tests/test_edge_set.py -q
NUMBA_DISABLE_JIT=1 uv run pytest tests/test_edge_set.py -q
```

Expected: full-range keys, deterministic growth, and diagnostics pass in both
modes.

- [ ] **Step 5: Commit edge set**

```bash
git add src/long_range_percolation/edge_set.py tests/test_edge_set.py
git commit -m "Add deterministic uint64 edge set"
```

---

### Task 5: Incremental Union-Find and Basic Observables

**Files:**
- Create: `src/long_range_percolation/observables.py`
- Create: `src/long_range_percolation/production_union_find.py`
- Create: `tests/test_production_union_find.py`

**Interfaces:**
- Produces
  `allocate_union_find(length: int) -> tuple[I64, I64, U8, F64, I64]`.
- State arrays are `parent`, `size`, `sector_mask`, `moments`, `counts`.
- `moments == [sum_size_sq, sum_size_fourth]` as `float64`.
- `counts == [open_edges, component_count, largest_size]` as `int64`.
- Produces Numba-callable
  `union_incremental(parent, size, sector_mask, moments, counts, left, right) -> bool`.
- Produces
  `scan_basic_observables(parent, size, sector_mask, moments, counts) -> BasicObservables`.

- [ ] **Step 1: Write failing controlled-union tests**

```python
def test_incremental_state_matches_exact_partition_after_every_edge():
    state = allocate_union_find(8)
    edges = [(0, 1), (2, 3), (1, 2), (4, 5), (6, 7), (5, 6), (0, 7), (0, 7)]
    python_uf = UnionFind(8)
    for index, edge in enumerate(edges, start=1):
        merged = union_incremental(*state, *edge)
        python_uf.union(*edge)
        sizes = python_uf.component_sizes()
        summary = scan_basic_observables(*state)
        assert summary.open_edges == index
        assert summary.component_count == len(sizes)
        assert summary.sum_size_sq == float(sum(int(s) ** 2 for s in sizes))
        assert summary.sum_size_fourth == float(sum(int(s) ** 4 for s in sizes))
        assert merged is (index != len(edges))
```

Add tests for deterministic equal-size root ties, duplicated edges increasing
`open_edges` only when the caller indicates a unique insertion, `L=2`, and
`L=2**18` moment initialization without integer overflow.

- [ ] **Step 2: Write failing root-scan observable tests**

For hand-built partitions, assert largest and second-largest sizes use
descending size then smallest-root tie order, `Q_G = sum4 / sum2**2`, and
four-sector crossing is true exactly when one root's OR-reduced four-bit mask
equals `0b1111`. Assign vertex `i` to sector
`min(3, (4 * i) // L)`; this exact formula is shared by host initialization
and tests.

- [ ] **Step 3: Run tests and verify RED**

Run: `uv run pytest tests/test_production_union_find.py -q`

Expected: collection fails because the production modules do not exist.

- [ ] **Step 4: Implement array-only incremental connectivity**

Initialize `parent = arange(L, int64)`, `size = ones(L, int64)`, masks from
the fixed formula, `moments = [float(L), float(L)]`, and
`counts = [0, L, 1]`. Implement iterative path halving and union by size with
smaller-root tie break.

On a successful merge of sizes `a, b`, update:

```python
moments[0] += float((a + b) ** 2 - a ** 2 - b ** 2)
moments[1] += float((a + b) ** 4 - a ** 4 - b ** 4)
counts[1] -= 1
counts[2] = max(counts[2], a + b)
```

The compiled expression must cast each size to `float64` before fourth powers
to avoid `int64` overflow. The event engine increments `counts[0]` exactly
once after a successful edge-set insertion, before calling union; a union that
finds an existing path does not mean a duplicate edge.

The root scan walks indices in ascending order, considers only
`parent[i] == i`, and checks incremental moments with deterministic tolerance
`32 * eps * max(1, exact_scan_value)`. A mismatch raises in the host wrapper
and returns a nonzero status code inside Numba.

- [ ] **Step 5: Run GREEN and all regressions**

Run:

```bash
uv run pytest tests/test_production_union_find.py -q
uv run pytest -q
```

Expected: all incremental and root-scan checks pass without changing Day-0
`UnionFind`.

- [ ] **Step 6: Commit production connectivity**

```bash
git add src/long_range_percolation/observables.py \
  src/long_range_percolation/production_union_find.py \
  tests/test_production_union_find.py
git commit -m "Add incremental production observables"
```

---

### Task 6: Independent Monotone Poisson Reference

**Files:**
- Create: `src/long_range_percolation/poisson_reference.py`
- Create: `tests/test_poisson_reference.py`

**Interfaces:**
- Produces
  `validate_trajectory_request(request: TrajectoryRequest) -> None`.
- Produces
  `run_poisson_reference(request: TrajectoryRequest, kernel: F64) -> TrajectoryResult`.
- The reference uses Python `set[int]`, cumulative class weights with
  `bisect`, the existing Day-0 `UnionFind` only for checkpoint reconstruction,
  and reference Philox functions. It must not import `alias`, `edge_set`,
  `production_union_find`, or `poisson_sweep`.

- [ ] **Step 1: Write failing request and independence tests**

```python
def test_request_rejects_nonfinite_unsorted_or_duplicate_couplings():
    for values in ([0.2, 0.1], [0.1, 0.1], [math.nan], [math.inf], [-1.0]):
        with pytest.raises(ValueError):
            validate_trajectory_request(make_request(kappas=values))


def test_reference_does_not_import_compiled_selection_or_connectivity():
    source = inspect.getsource(poisson_reference)
    for forbidden in ("alias", "edge_set", "production_union_find", "poisson_sweep"):
        assert forbidden not in source
```

- [ ] **Step 2: Write failing exact-semantic tests**

Inject a finite scripted sequence of exponential uniforms, class uniforms, and
offset integers through a private test-only stream adapter. Assert:

1. event times are `kappa += -log(u_open) / Lambda`;
2. every crossed requested coupling receives the state before the later event;
3. duplicate event IDs increment `event_count` and `duplicate_count` but do
   not alter connectivity or `open_edges`;
4. one event may cross multiple requested couplings;
5. `kappa=0` records the empty graph without consuming any stream;
6. a positive largest coupling consumes exactly one final exponential draw to
   establish that the next event lies beyond it, but consumes no class,
   threshold, or offset draw for that overshooting event.

- [ ] **Step 3: Write failing analytic law tests**

With fixed identities and no seed replacement, test event counts as
`Poisson(kappa_max * Lambda)`, open-edge frequencies as
`1-exp(-kappa*J_d)`, no-edge probability as `exp(-kappa*Lambda)`, and
open-edge mean/variance from Day-0 analytic functions. Use one familywise
alpha `0.001`, divide it by the exact number of asserted scalar laws before
sampling, and include raw observed, expected, threshold, and signed margin in
every failure message.

- [ ] **Step 4: Run tests and verify RED**

Run: `uv run pytest tests/test_poisson_reference.py -q`

Expected: collection fails because `poisson_reference.py` does not exist.

- [ ] **Step 5: Implement the independent reference**

Validate all finite numeric extremes before allocation: `L` is an even Python
integer at least two; `sigma` is finite, positive, and
`1.0 + sigma > 1.0`; kappas satisfy the interface contract; `replica` and
`master_seed` fit `uint64`; kernel shape is exact, finite, positive, and its
bytes match `kernel_sha256`.

Build cumulative `M_d * J_d` with `math.fsum`; choose a class by
`bisect_left(cumulative, u_open * Lambda)` with a final-index clamp only for
roundoff; choose an offset with reference rejection-based bounded integers.
Decode endpoints independently from `canonical_edge`: for
`d < L/2`, use `left=offset`, `right=(offset+d)%L`; for the antipodal class,
require `offset < L/2`. Canonicalize endpoint order only when reconstructing a
checkpoint.

- [ ] **Step 6: Run GREEN and Day-0 regressions**

Run:

```bash
uv run pytest tests/test_poisson_reference.py -q
uv run pytest -q
```

Expected: semantic, analytic, independence, and existing tests pass.

- [ ] **Step 7: Commit the reference**

```bash
git add src/long_range_percolation/poisson_reference.py \
  tests/test_poisson_reference.py
git commit -m "Add independent monotone Poisson reference"
```

---

### Task 7: Numba Poisson/Newman-Ziff Engine

**Files:**
- Create: `src/long_range_percolation/poisson_sweep.py`
- Create: `tests/test_poisson_sweep.py`
- Modify: `src/long_range_percolation/__init__.py`

**Interfaces:**
- Produces
  `run_poisson_numba(request: TrajectoryRequest, kernel: F64, alias: AliasTable) -> TrajectoryResult`.
- Internal compiled entry:

```python
_run_poisson_kernel(
    length: int,
    kappas: F64,
    total_rate: float,
    alias_probability: F64,
    alias_index: I64,
    multiplicity: U64,
    class_start: U64,
    keys: U64,
    occupied: U8,
    hash_diagnostics: U64,
    parent: I64,
    size: I64,
    sector_mask: U8,
    moments: F64,
    counts: I64,
    counters: U32,
    keys_by_stream: U32,
    blocks: U32,
    lane_valid: U8,
    draw_counts: U64,
    output: F64,
) -> tuple[int, int, int]
```

Shapes are fixed by the shared contract:
`counters (4,4)`, `keys_by_stream (4,2)`, `blocks (4,4)`,
`lane_valid (4,2)`, `draw_counts (4,3)`.
Return values are `(status, event_count, duplicate_count)`.

- [ ] **Step 1: Write failing scripted semantic-equivalence tests**

Factor a test-only `_run_scripted_events` compiled kernel that receives arrays
of interarrival uniforms, class indices, and offsets. Compare every checkpoint
column against a separate Python reconstruction for duplicate events,
antipodal edges, multi-coupling crossings, and a final event after
`kappa_max`. This test isolates event semantics from random class-selection
statistics.

- [ ] **Step 2: Write failing RNG scheduling tests**

```python
def test_draw_families_are_isolated_and_accounted():
    result = run_poisson_numba(request, kernel, table)
    expected_exponential_words = result.event_count + int(request.kappas[-1] > 0.0)
    assert result.draw_counts[STREAM_EXPONENTIAL, 0] == expected_exponential_words
    assert result.draw_counts[STREAM_ALIAS_COLUMN, 0] == result.event_count
    assert result.draw_counts[STREAM_ALIAS_THRESHOLD, 0] == result.event_count
    assert result.draw_counts[STREAM_EDGE_OFFSET, 0] >= result.event_count
    assert result.draw_counts[STREAM_EDGE_OFFSET, 2] == (
        result.draw_counts[STREAM_EDGE_OFFSET, 0] - result.event_count
    )
```

Run identical trajectory IDs sequentially, reversed, with
`multiprocessing.get_context("spawn").Pool(2)`, and after a forced retry.
Assert byte-identical `TrajectoryResult` arrays. Assert changing only one
registered stream's initial counter changes that family's draws without
changing any other terminal counter.

- [ ] **Step 3: Write failing finite-extreme and saturation tests**

Cover `kappa=0`, `L=2`, antipodal-only edge selection, the smallest positive
finite sigma accepted by `ModelSpec`, `sigma=128`, `kappa_max` just below
float overflow, duplicate-heavy saturation, and hash growth. Require finite
outputs or a specific preflight `ValueError`; no NaN, wraparound, silent
infinite loop, or allocation after a failed preflight is accepted.

- [ ] **Step 4: Run tests and verify RED**

Run: `uv run pytest tests/test_poisson_sweep.py -q`

Expected: collection fails because `poisson_sweep.py` does not exist.

- [ ] **Step 5: Implement the compiled event loop**

Preflight on the host, allocate all arrays, derive all four streams, and reject
stream-material collisions. In the compiled loop:

1. record all zero couplings from initialized state;
2. draw one exponential open uniform and compute
   `delta = -log(u) / total_rate`;
3. stop without class/offset draws when `current_kappa + delta > kappa_max`;
4. draw alias column and threshold from their distinct streams;
5. draw bounded offset from the offset stream;
6. increment event count;
7. insert the encoded ID into the edge set;
8. on a duplicate, increment duplicate count only;
9. on a new edge, increment open-edge count, decode endpoints, and union;
10. record every coupling smaller than the next event time;
11. after the loop, fill remaining checkpoints from the final state.

Use `fastmath=False`, checked status codes for nonfinite time/moment values,
and no Python containers inside compiled code. Host code converts nonzero
status to a stable exception before constructing `TrajectoryResult`.

- [ ] **Step 6: Run GREEN, compile inspection, and regressions**

Run:

```bash
uv run pytest tests/test_poisson_sweep.py -q
uv run python -c 'from long_range_percolation.poisson_sweep import assert_nopython_signatures; assert_nopython_signatures()'
NUMBA_DISABLE_JIT=1 uv run pytest tests/test_poisson_sweep.py -q
uv run pytest -q
```

Expected: normal and disabled-JIT semantics pass; the signature check confirms
every production kernel has at least one nopython signature and no object-mode
fallback.

- [ ] **Step 7: Commit the Numba engine**

```bash
git add src/long_range_percolation/poisson_sweep.py \
  src/long_range_percolation/__init__.py tests/test_poisson_sweep.py
git commit -m "Add Numba Poisson sweep engine"
```

---

### Task 8: Fixed Three-Way Correctness Gate Through L=256

**Files:**
- Create: `src/long_range_percolation/validation.py`
- Create: `tests/test_validation.py`
- Create: `scripts/validate_production.py`

**Interfaces:**
- Produces `ValidationProtocol.production_v1() -> ValidationProtocol`.
- Produces
  `run_production_validation(protocol: ValidationProtocol, output: Path) -> dict[str, object]`.
- The report schema is `challenge-194-validation-v1` and every check stores
  `family`, `case_id`, `raw`, `expected`, `threshold`, `margin`, and `passed`.

- [ ] **Step 1: Write failing protocol-freeze tests**

Freeze the protocol in code:

```python
VALIDATION_PROTOCOL_VERSION = "challenge-194-validation-v1"
FAMILYWISE_ALPHA = 0.001
LENGTHS = (4, 6, 8, 16, 32, 64, 128, 256)
SIGMAS = (0.8, 1.0, 1.1)
KAPPAS = (0.0, 0.25, 0.7, 2.0, 6.0)
SAMPLES_BY_LENGTH = {
    4: 32768, 6: 32768, 8: 32768, 16: 16384,
    32: 8192, 64: 4096, 128: 2048, 256: 1024,
}
SAMPLERS = ("quadratic", "geometric", "poisson-reference", "poisson-numba")
MASTER_SEEDS = tuple(range(194_000_000, 194_032_768))
```

The first three-way family uses quadratic, geometric, and Numba Poisson.
Python Poisson is a fourth independent diagnostic and cannot rescue a failed
three-way case. Assert the family denominators are computed solely from these
constants before draws and serialized in the report.

- [ ] **Step 2: Write failing exact and deterministic families**

Require exact/deterministic checks for published Philox vectors, stream
separation, bounded-integer accounting, alias invariants, edge-ID uniqueness,
hash full-range/growth, all graph distributions for `L<=6`, `kappa=0`,
saturated coupling, antipodal counts, tiny/huge finite parameters, duplicate
limits, incremental/root-scan moments, and process-order identity. Each exact
check uses `threshold=0`, with `margin=0` on equality or a negative numeric
distance on failure.

- [ ] **Step 3: Write failing statistical family implementation**

Use these fixed simultaneous rules, separately Bonferroni-adjusted within each
named family at familywise alpha `0.001`:

- Bernoulli edge/class frequencies: exact two-sided `scipy.stats.binomtest`;
- Poisson event counts: exact two-sided `scipy.stats.poisson` tail probability
  with the doubled smaller tail capped at one;
- scalar sampler-pair means (`open_edges`, `S1/L`, `S2/L`, `Q_G`, crossing,
  normalized second/fourth moments): paired-independent permutation test with
  exactly 49,999 Philox-derived label permutations;
- bond-length and component-partition histograms: fixed-bin multinomial
  likelihood-ratio statistic calibrated by exactly 49,999 parametric
  multinomial replicates from the pooled null;
- all-graph `L<=6` probabilities: exact binomial tests against enumeration.

The threshold for p-value checks is
`FAMILYWISE_ALPHA / frozen_family_denominator`; store
`margin = pvalue - threshold`. Store all bins, counts, seeds, test statistic,
replicate count, and p-value. Zero expected bins are exact invariants rather
than divisions. No seed is discarded or regenerated.

- [ ] **Step 4: Write failing report and CLI tests**

The CLI accepts only:

```text
--output PATH
--protocol production-v1
--jobs INTEGER
```

`--jobs` changes scheduling only. Test `jobs=1` versus `jobs=2` for identical
canonical report payload after excluding measured elapsed time. Exit zero only
when all exact, reference, and three-way families pass; exit 2 on a scientific
failure and still atomically publish all raw margins.

- [ ] **Step 5: Run tests and verify RED**

Run: `uv run pytest tests/test_validation.py -q`

Expected: collection fails because `validation.py` does not exist.

- [ ] **Step 6: Implement gate without sharing oracle selection logic**

Adapters may normalize each sampler's output into edge IDs, partitions, and
basic observables, but may not share random draws or edge-selection routines.
Poisson reference and Numba use distinct stream identities. Quadratic and
geometric retain `numpy.random.Generator` and independent seed ranges. Add a
source-structure test proving the four sampler modules do not import one
another.

Canonical JSON uses sorted keys, separators `(",", ":")`, `allow_nan=False`,
and decimal hexadecimal strings for all binary64 protocol values. Include
runtime capability, source revision, clean-tree status, protocol hash, raw
counts, all margins, and an overall pass flag.

- [ ] **Step 7: Run focused GREEN and the reduced smoke protocol**

Run:

```bash
uv run pytest tests/test_validation.py -q
uv run scripts/validate_production.py \
  --protocol production-v1 --jobs 1 \
  --output ../../../../results/frustration-free/challenge-194/validation-smoke/report.json
```

Expected: unit tests pass. The full command publishes a complete report and
returns either zero for a scientifically passing gate or 2 with preserved raw
failures; infrastructure errors return 1. During implementation, tests use a
constructor with reduced sample counts, while the CLI refuses reduced counts.

- [ ] **Step 8: Commit validation gate**

```bash
git add src/long_range_percolation/validation.py \
  tests/test_validation.py scripts/validate_production.py
git commit -m "Add fixed production validation gate"
```

---

### Task 9: Immutable Atomic Trajectory and Batch Artifacts

**Files:**
- Create: `src/long_range_percolation/artifacts.py`
- Create: `tests/test_artifacts.py`

**Interfaces:**
- Produces
  `publish_trajectory(run_dir: Path, request: TrajectoryRequest, result: TrajectoryResult, provenance: dict[str, object]) -> Path`.
- Produces
  `publish_batch_manifest(run_dir: Path, batch_id: str, trajectory_paths: Sequence[Path]) -> Path`.
- Produces
  `load_verified_trajectory(path: Path, expected: dict[str, str]) -> TrajectoryResult`.
- Produces
  `reconstruct_progress(run_dir: Path, expected: dict[str, str]) -> dict[str, object]`.
- Trajectories are HDF5; immutable batch manifests and progress are canonical
  JSON. A batch manifest references trajectory hashes and never aggregates
  away a trajectory.

- [ ] **Step 1: Write failing schema round-trip and immutability tests**

```python
def test_trajectory_round_trip_preserves_complete_resampling_unit(tmp_path):
    path = publish_trajectory(tmp_path, request, result, provenance)
    loaded = load_verified_trajectory(path, expected_hashes)
    np.testing.assert_array_equal(loaded.observables, result.observables)
    np.testing.assert_array_equal(loaded.terminal_counters, result.terminal_counters)
    np.testing.assert_array_equal(loaded.draw_counts, result.draw_counts)
    with pytest.raises(FileExistsError):
        publish_trajectory(tmp_path, request, result, provenance)
```

Assert every requested coupling and all ten basic observables for one
trajectory are in one HDF5 file. Assert fixed little-endian dtypes, exact
dataset shapes, schema/RNG/conversion versions, request/kernel/source/lock
hashes, clean-tree flag, initial and terminal counters, key-material hashes,
draw accounting, hash diagnostics, and whole-file SHA-256 sidecar fields.

- [ ] **Step 2: Write failing crash-consistency tests**

Monkeypatch each boundary (`flush`, file `fsync`, semantic reload, hash,
`os.replace`, directory `fsync`) to fail in turn. Before rename, assert no
final path exists and a uniquely named `.partial` remains detectable. After
rename but before directory fsync, assert a durable publication-intent marker
makes reconstruction fail closed. Existing valid files are never removed or
overwritten.

- [ ] **Step 3: Write failing corruption and restart tests**

Test truncated HDF5, changed dataset byte, changed request hash, wrong source
revision, dirty-tree provenance, wrong lock/kernel/analysis-plan/RNG hash,
unknown extra final file, stale `.partial`, duplicate trajectory ID, batch
manifest with missing member, and extra valid trajectory absent from all batch
manifests. Every case raises `ArtifactIntegrityError`.

For a valid directory, delete `progress.json`, call `reconstruct_progress`,
and assert byte-identical regenerated progress from verified immutable
trajectory and batch files only.

- [ ] **Step 4: Run tests and verify RED**

Run: `uv run pytest tests/test_artifacts.py -q`

Expected: collection fails because `artifacts.py` does not exist.

- [ ] **Step 5: Implement staged publication**

Use unique partial names produced by
`f".trajectory-{trajectory_id}.{os.getpid()}.{uuid.uuid4().hex}.partial"`.
Before publication, create and fsync a unique intent file containing the
partial/final names and expected semantic hashes, then fsync the directory.
Write HDF5 with track times disabled, flush HDF5,
`os.fsync(file.fileno())`, close, reopen through the semantic loader, hash
bytes, `os.replace(partial, final)`, and fsync the parent directory opened
with `os.O_DIRECTORY`. Only then unlink the intent and fsync the directory
again. Reconstruction rejects every surviving intent marker, so interruption
at any boundary cannot expose a final file as committed. The immutable batch
manifest records the verified whole-file trajectory hashes. Never derive
progress from filenames alone.

Canonical run paths are:

```text
request.json
environment.json
kernel/
seed-manifest.json
capability.json
trajectories/
batches/
progress.json
manifest.json
```

This subproject does not create `analysis-plan.json`, `derived/`, or
`figures/`; expected hashes may include an explicit
`analysis_plan_sha256 = "not-created-pre-pilot"` value.

- [ ] **Step 6: Run GREEN and filesystem regressions**

Run:

```bash
uv run pytest tests/test_artifacts.py -q
uv run pytest -q
```

Expected: every injected crash or corruption fails closed; clean publication
and reconstruction pass.

- [ ] **Step 7: Commit artifact layer**

```bash
git add src/long_range_percolation/artifacts.py tests/test_artifacts.py
git commit -m "Add immutable trajectory artifacts"
```

---

### Task 10: Fresh-Subprocess Performance Gate

**Files:**
- Create: `src/long_range_percolation/benchmark.py`
- Create: `tests/test_benchmark.py`
- Create: `scripts/benchmark_production.py`

**Interfaces:**
- Produces
  `BenchmarkProtocol.production_v1() -> BenchmarkProtocol`.
- Produces
  `run_benchmark(protocol: BenchmarkProtocol, output: Path) -> dict[str, object]`.
- Worker modes are `compile`, `steady`, and `measure-observables`.
- Report schema is `challenge-194-benchmark-v1`.

- [ ] **Step 1: Write failing frozen-protocol tests**

Freeze:

```python
BENCHMARK_LENGTHS = (2**10, 2**14, 2**18)
BENCHMARK_SIGMAS = (0.8, 0.9, 1.0, 1.1)
BENCHMARK_KAPPAS = tuple(
    value for value in (0.25 * 1.25**j for j in range(32)) if value <= 6.0
)
STEADY_RUNS = 5
WALL_LIMIT_SECONDS = 120.0
RSS_LIMIT_BYTES = 4 * 1024**3
GATE_LENGTH = 2**18
```

Assert these values are serialized as binary64 hex strings and cannot be
overridden by CLI flags. Quadratic is benchmarked only through `L=256`;
geometric and Poisson are attempted at every feasible benchmark point, with a
recorded timeout or allocation failure retained rather than omitted.

- [ ] **Step 2: Write failing subprocess and warmup-separation tests**

Mock the worker executable and assert:

1. compilation runs in one fresh subprocess with an empty unique
   `NUMBA_CACHE_DIR`;
2. each of five steady runs uses a separate fresh subprocess and a populated,
   read-only copy of the compile cache;
3. each steady worker imports modules and executes one untimed `L=2`
   signature warmup before starting `perf_counter_ns`;
4. timed work is exactly one target trajectory through all frozen kappas with
   basic observables;
5. worker JSON separates startup, cache load/warmup, compile, sampling,
   observable, artifact-serialization, wall, CPU, and peak RSS;
6. parent wall timeout and nonzero exits produce visible failed run records.

- [ ] **Step 3: Write failing metric and gate tests**

Require raw per-run values for events, unique edges, unions, duplicates, total
and maximum probes, rehashes, bytes, wall, CPU, and RSS. Aggregate median and
maximum without dropping outliers. Gate each `(sigma, L=2**18)` cell on
`max_wall_seconds <= 120.0` and `max_peak_rss_bytes <= 4*1024**3`; the Numba
backend passes only if all four sigma cells and the correctness report pass.
Compilation and warmup are reported but excluded from the 120-second value.

- [ ] **Step 4: Run tests and verify RED**

Run: `uv run pytest tests/test_benchmark.py -q`

Expected: collection fails because `benchmark.py` does not exist.

- [ ] **Step 5: Implement the worker and orchestrator**

Use `subprocess.run` with explicit environment:

```python
{
    "NUMBA_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "PYTHONHASHSEED": "0",
}
```

On Linux, workers collect `resource.getrusage(RUSAGE_SELF).ru_maxrss * 1024`,
pin to one available CPU with `os.sched_setaffinity`, and report the selected
CPU. If affinity cannot be set, capability fails closed. The parent validates
one JSON object per worker, preserves stdout/stderr and exit status, and
atomically publishes the report through the artifact helper.

- [ ] **Step 6: Implement and test CLI behavior**

CLI:

```text
benchmark_production.py --validation-report PATH --output PATH
```

No size, sigma, kappa, repeat, wall, or RSS override is accepted. Exit zero
only when correctness and the frozen gate pass; exit 2 for a measured gate
failure with a complete report; exit 1 for infrastructure failure with
captured diagnostics.

Run:

```bash
uv run pytest tests/test_benchmark.py -q
uv run scripts/benchmark_production.py \
  --validation-report ../../../../results/frustration-free/challenge-194/validation-smoke/report.json \
  --output ../../../../results/frustration-free/challenge-194/benchmark-smoke/capability.json
```

Expected: unit tests pass. The real command records compile plus all five raw
steady runs at every frozen point and returns according to the measured gate;
it never presents a smoke or reduced protocol as the frozen capability gate.

- [ ] **Step 7: Commit benchmark harness**

```bash
git add src/long_range_percolation/benchmark.py \
  tests/test_benchmark.py scripts/benchmark_production.py
git commit -m "Add frozen production benchmark gate"
```

---

### Task 11: Optimization/Revalidation and Fail-Closed Backend Decision

**Files:**
- Modify: `src/long_range_percolation/benchmark.py`
- Modify: `tests/test_benchmark.py`
- Create: `scripts/decide_production_backend.py`

**Interfaces:**
- Produces
  `decide_backend(baseline: Path, optimized: Path | None, validation: Path, output: Path) -> dict[str, object]`.
- Decision values are exactly `numba-approved`, `numba-optimization-required`,
  `cpp17-fallback-authorized`, and `blocked-invalid-evidence`.
- This task writes a report only; it creates no C++ source, build file, binding,
  or C++ test.

- [ ] **Step 1: Write failing decision-table tests**

```python
@pytest.mark.parametrize(
    ("correct", "baseline_pass", "optimized_present", "optimized_pass", "decision"),
    [
        (True, True, False, False, "numba-approved"),
        (True, False, False, False, "numba-optimization-required"),
        (True, False, True, True, "numba-approved"),
        (True, False, True, False, "cpp17-fallback-authorized"),
        (False, True, False, False, "blocked-invalid-evidence"),
        (False, False, True, False, "blocked-invalid-evidence"),
    ],
)
def test_backend_decision_table(
    tmp_path, correct, baseline_pass, optimized_present, optimized_pass, decision
):
    validation, baseline, optimized = write_decision_fixture(
        tmp_path,
        correctness_passed=correct,
        baseline_passed=baseline_pass,
        include_optimized=optimized_present,
        optimized_passed=optimized_pass,
    )
    report = decide_backend(
        baseline,
        optimized,
        validation,
        tmp_path / "decision.json",
    )
    assert report["decision"] == decision
```

Also reject missing raw runs, fewer than five runs, hidden failures, mismatched
protocol/runtime/source/schema hashes, changed RNG mapping, changed artifact
schema, changed observable columns, or an optimization report that lacks a
fresh full validation report.

`write_decision_fixture` is a test-only helper in `tests/test_benchmark.py`.
It writes canonical minimal validation and capability JSON using the exact
schemas and hashes defined in Tasks 8 and 10, emits five raw steady runs for
each frozen gate cell, and returns
`tuple[Path, Path, Path | None]`. It changes only the four booleans named in
its signature, so every row exercises one decision-table condition.

- [ ] **Step 2: Define the bounded optimization ledger**

The first failed baseline produces
`numba-optimization-required`. An optimization attempt may change only:
array layout, initial hash capacity estimate, allocation reuse, compilation
specialization, and host batching. It must record exact source diff hash and
one or more of those registered categories. It may not change Philox/version,
stream IDs, key derivation, open-uniform conversion, bounded-integer mapping,
event ordering, alias construction, duplicate semantics, edge encoding,
observable definitions/order, retained kappas, or artifact schemas.

After any optimization, require in order:

```text
full production validation -> fresh full benchmark -> backend decision
```

A second measured failure authorizes only a C++17 planning subproject; no C++
implementation is part of this task.

- [ ] **Step 3: Run tests and verify RED**

Run:
`uv run pytest tests/test_benchmark.py -q -k 'decision or optimization'`

Expected: failures show `decide_backend` and the decision CLI are absent.

- [ ] **Step 4: Implement canonical evidence verification and decision report**

Report keys are exactly:

```python
{
    "schema_version": "challenge-194-backend-decision-v1",
    "decision": decision,
    "validation_sha256": validation_sha256,
    "baseline_capability_sha256": baseline_sha256,
    "optimized_capability_sha256": optimized_sha256_or_none,
    "frozen_wall_limit_seconds": 120.0,
    "frozen_rss_limit_bytes": 4 * 1024**3,
    "failed_cells": failed_cells,
    "optimization_categories": optimization_categories,
    "semantic_contract_hashes": semantic_contract_hashes,
    "cpp17_implementation_present": False,
}
```

Any malformed, inconsistent, scientifically failed, or noncanonical input
yields `blocked-invalid-evidence`, a nonzero CLI exit, and preserved reasons.
An authorized fallback report says only that a separately planned C++17
backend may begin and must pass the same scientific suite.

- [ ] **Step 5: Run GREEN and full regressions**

Run:

```bash
uv run pytest tests/test_benchmark.py -q
uv run pytest -q
uv run scripts/decide_production_backend.py --help
```

Expected: decision-table and evidence-integrity tests pass; help lists
`--validation`, `--baseline`, optional `--optimized`, and `--output` only.

- [ ] **Step 6: Commit decision logic**

```bash
git add src/long_range_percolation/benchmark.py \
  tests/test_benchmark.py scripts/decide_production_backend.py
git commit -m "Add fail-closed backend decision"
```

---

### Task 12: Public API, Documentation, and Completion Gate

**Files:**
- Modify: `src/long_range_percolation/__init__.py`
- Modify: `README.md`
- Modify: `tests/test_runtime.py`

**Interfaces:**
- Exports `AliasTable`, `BasicObservables`, `StreamIdentity`,
  `TrajectoryRequest`, `TrajectoryResult`, `build_distance_alias`,
  `derive_stream_material`, `run_poisson_numba`, and
  `run_poisson_reference`.
- Documentation exposes correctness, benchmark, and decision commands only;
  it contains no pilot, cluster, confirmatory, fit, figure, report-analysis, or
  C++ build command.

- [ ] **Step 1: Write failing export and documentation-scope tests**

```python
def test_production_public_api_is_explicit():
    expected = {
        "AliasTable", "BasicObservables", "StreamIdentity",
        "TrajectoryRequest", "TrajectoryResult", "build_distance_alias",
        "derive_stream_material", "run_poisson_numba",
        "run_poisson_reference",
    }
    assert expected <= set(long_range_percolation.__all__)
    for name in expected:
        assert getattr(long_range_percolation, name) is not None


def test_readme_stops_at_backend_decision():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "validate_production.py" in text
    assert "benchmark_production.py" in text
    assert "decide_production_backend.py" in text
    for forbidden in ("run_pilot.py", "run_production.py", "analyze_production.py",
                      "CMakeLists.txt", "pybind11"):
        assert forbidden not in text
```

- [ ] **Step 2: Run tests and verify RED**

Run: `uv run pytest tests/test_runtime.py -q`

Expected: production export and README command assertions fail.

- [ ] **Step 3: Export the frozen API and update README**

Document:

1. `uv sync --frozen`;
2. exact Numba and runtime capability inspection;
3. correctness command and exit meanings;
4. benchmark command, five fresh runs, warmup exclusion, and frozen
   `120 seconds / 4 GiB` rule;
5. decision command and the meaning of each decision;
6. immutable result root and restart fail-closed behavior;
7. explicit statement that passing this subproject permits later pilot
   planning but does not execute a pilot or support a physics conclusion.

- [ ] **Step 4: Run final verification**

Run:

```bash
uv sync --frozen
uv run pytest -q
NUMBA_DISABLE_JIT=1 uv run pytest \
  tests/test_counter_rng.py tests/test_alias.py tests/test_edge_set.py \
  tests/test_production_union_find.py tests/test_poisson_sweep.py -q
uv run python -c 'from long_range_percolation.poisson_sweep import assert_nopython_signatures; assert_nopython_signatures()'
git diff --check
```

Expected: all tests pass in normal mode; fixed-dtype semantic tests pass with
JIT disabled; nopython signatures exist; whitespace check exits zero.

- [ ] **Step 5: Audit committed scope**

Run:

```bash
git status --short
git diff --name-only HEAD
git check-ignore \
  ../../../../results/frustration-free/challenge-194/
```

Expected: only files in this plan are changed, result artifacts are ignored,
and no pilot/cluster/production-analysis/C++ file exists.

- [ ] **Step 6: Commit completion boundary**

```bash
git add README.md src/long_range_percolation/__init__.py tests/test_runtime.py
git commit -m "Document production engine gates"
```

---

## Production-Engine Completion Gate

The subproject is complete only when:

1. the dependency resolver selected Numba successfully and the exact selected
   version is pinned in both `pyproject.toml` and `uv.lock`;
2. published Philox vectors, stream separation, all open-uniform boundaries,
   bounded-integer rejection, and exact draw accounting pass;
3. alias, edge-set, union-find, and scripted event invariants pass in compiled
   and disabled-JIT modes;
4. the independent Python Poisson semantics and compiled Numba engine remain
   structurally independent;
5. all exact `L<=6` and three-way quadratic/geometric/Numba-Poisson families
   through `L<=256` pass their frozen familywise thresholds with raw margins;
6. immutable trajectory/batch artifacts survive semantic reload and every
   corruption/crash injection fails closed;
7. one complete trajectory at every frozen benchmark cell is measured in five
   fresh steady-state subprocesses after separately reported compilation and
   warmup;
8. all `L=2**18` sigma cells have maximum steady wall time at most 120 seconds
   and maximum peak RSS at most 4 GiB, or one registered optimization pass is
   followed by full revalidation and a fresh full benchmark;
9. the final decision is `numba-approved`,
   `numba-optimization-required`, `cpp17-fallback-authorized`, or
   `blocked-invalid-evidence`, with all evidence hashes and failed cells;
10. no pilot run, cluster submission, confirmatory production, physics fit,
    figure, final analysis report, or C++ implementation has been added.

## Self-Review Record

- Requirement coverage: all ten requested scope items map to Tasks 1–11;
  Task 12 closes API and phase boundaries.
- Marker scan: no unresolved implementation marker or unspecified version
  remains. The Numba version is deliberately obtained from
  `uv add numba`, printed, copied exactly, and locked rather than invented.
- Interface/type consistency: all cross-task names, shapes, dtypes, stream
  indices, observable columns, status codes, report schemas, and decision
  values match the Shared Interface and Type Contract.
- Independence review: the Python reference uses cumulative weights, Python
  sets, and checkpoint reconstruction; compiled code uses Walker alias,
  open-address arrays, and incremental union-find. Statistical validation,
  not shared edge-selection code, joins them.
- Numeric review: preflight covers nonfinite inputs; uniforms are open;
  rejection accounting includes discarded words; fourth moments use
  `float64`; edge-set occupancy is separate from keys and therefore preserves
  the complete `uint64` domain.
- Artifact review: flush, file fsync, semantic reload, hash, atomic rename,
  directory fsync, immutable collision handling, and reconstruction from
  verified files are each explicit and crash-tested.
- Benchmark review: compilation, cache load/warmup, and steady timing are
  separate; five raw fresh-process runs are retained; maximum rather than
  median enforces both frozen limits.
- Scope review: the plan ends with a fail-closed backend decision report and
  explicitly excludes C++ implementation and every later scientific phase.
- Contradiction review: “latest compatible Numba” and “exact pin” are ordered
  resolver actions; “fresh subprocess” and “warmup separation” are satisfied
  by untimed in-process signature warmup inside each new steady worker;
  “one trajectory restart unit” and “batch artifact” are satisfied by immutable
  per-trajectory HDF5 plus immutable manifests that reference, never merge,
  complete trajectories; the terminal overshoot consumes one exponential draw
  but no event-selection draws, consistently in reference, compiled engine,
  and accounting tests.
