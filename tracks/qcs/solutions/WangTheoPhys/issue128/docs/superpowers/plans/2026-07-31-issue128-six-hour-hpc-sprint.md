# Issue 128 Six-Hour HPC Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, deploy, monitor, and recover a deterministic Slurm sprint that regenerates the accepted Issue 128 proof, computes an exact sharded degree-eight right-generator coefficient map, and screens all 24 matching-color orderings without weakening the frozen `4.050498110614909x` certificate.

**Architecture:** The trusted branch remains anchored at `ebb055926302c7d911e5ab00805513c382ac458d`. Exact D8 work is decomposed into one independent contribution per one of the 31 merged Suzuki stages; every shard serializes coordinate-addressed Pauli coefficients in `Q[cuberoot(4)]`, so processes with different bit registries can be reduced safely. A reducer verifies all manifests and hashes, sums exact coefficients before any norm inequality, and emits a rigorous Pauli-l1 site-density upper bound. A separate untrusted discovery array evaluates all 24 fragment permutations with the existing floating-point right-generator recurrence.

**Tech Stack:** Python 3.12, `Fraction`, exact `Cubic`, gzip JSON, pytest, Bash, Slurm arrays, `scripts/harness_slurm.sh`, SSH/rsync.

## Global Constraints

- Physical benchmark is fixed: periodic square spin-1/2 isotropic Heisenberg, `L=12`, `N=144`, `T=1`, operator-norm tolerance `1e-6`.
- Frozen accepted claim is `11791/2911 = 4.050498110614909...`; no new ratio may be claimed unless a complete exact global ledger and fast/deep verification pass.
- D8 shards must be merged coefficient-by-coefficient before taking any norm; shard norms must never be triangle-summed.
- Discovery may use float ranking, but trusted outputs use integers, `Fraction`, `Cubic`, outward rational intervals, and SHA-256.
- Each Slurm cell uses one CPU thread, `PYTHONHASHSEED=0`, and BLAS thread counts fixed to one.
- No computation runs on a login node. All remote compute is submitted to `xhacnormalb` under account `giggleliu` and the user's assigned QOS.
- Every cell writes an atomic manifest with commit, arguments, status, timing, counts, and output digest.
- The sprint stops launching discovery jobs after 4 hours 15 minutes and reserves the final 1 hour 45 minutes for reduction, verification, fetch, and packaging.

---

### Task 1: Exact stage-contribution recurrence

**Files:**
- Modify: `src/trottercert/cubic_local.py`
- Test: `tests/test_cubic_right_generator.py`

**Interfaces:**
- Consumes: `Cubic`, `CubicStage`, `fourth_order_suzuki_cubic_stages`, `cubic_fragment_adjoint`.
- Produces: `exact_right_generator_stage_contribution(stages: Sequence[CubicStage], stage_index: int, order: int) -> tuple[CoordinateRegistry, list[CubicTerms]]` and `merge_cubic_series(target: list[CubicTerms], source: Sequence[Mapping[SymplecticPauli, Cubic]]) -> None`.

- [ ] **Step 1: Write failing algebra tests**

```python
def test_stage_contributions_reconstruct_order_conditions() -> None:
    stages = fourth_order_suzuki_cubic_stages()
    shards = [exact_right_generator_stage_contribution(stages, i, 4) for i in range(len(stages))]
    coordinate_series = merge_coordinate_series([coordinate_encode_series(*shard) for shard in shards])
    assert not coordinate_series[1]
    assert not coordinate_series[2]
    assert not coordinate_series[3]
    assert coordinate_series[4]

def test_rejects_invalid_stage_index() -> None:
    with pytest.raises(IndexError):
        exact_right_generator_stage_contribution(fourth_order_suzuki_cubic_stages(), 31, 8)
```

- [ ] **Step 2: Run the focused tests and observe missing interfaces**

Run: `pytest -q tests/test_cubic_right_generator.py`

Expected: import failure for `exact_right_generator_stage_contribution`.

- [ ] **Step 3: Implement exact conjugation and stage contributions**

```python
def exact_right_generator_stage_contribution(stages, stage_index, order):
    stage = stages[stage_index]
    registry, base = exact_matching_density(stage.fragment_index)
    series = [{} for _ in range(order + 1)]
    series[0] = {pauli: stage.coefficient * coefficient for pauli, coefficient in base.items()}
    for later in stages[stage_index + 1:]:
        series = conjugate_cubic_series_by_stage(registry, series, later.fragment_index, later.coefficient)
    return registry, [canonicalize_cubic_density(registry, degree) for degree in series]
```

- [ ] **Step 4: Verify exact cancellation through degree three**

Run: `pytest -q tests/test_cubic_right_generator.py`

Expected: all tests pass and degree four is nonempty.

---

### Task 2: Registry-independent serialization and atomic manifests

**Files:**
- Create: `src/trottercert/hpc_artifacts.py`
- Test: `tests/test_hpc_artifacts.py`

**Interfaces:**
- Consumes: `CoordinateRegistry`, `CubicTerms`.
- Produces: `coordinate_encode_series`, `write_shard_gzip`, `read_shard_gzip`, `write_manifest_atomic`, and `sha256_file`.

- [ ] **Step 1: Write round-trip and corruption tests**

```python
def test_coordinate_round_trip_is_registry_independent(tmp_path: Path) -> None:
    first_registry, first = build_fixture_with_registration_order("xy")
    second_registry, second = build_fixture_with_registration_order("yx")
    assert coordinate_encode_terms(first_registry, first) == coordinate_encode_terms(second_registry, second)

def test_reader_rejects_payload_digest_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "shard.json.gz"
    write_shard_gzip(path, fixture_payload())
    raw = bytearray(path.read_bytes())
    raw[-8] ^= 1
    path.write_bytes(raw)
    with pytest.raises((OSError, ValueError)):
        read_shard_gzip(path)
```

- [ ] **Step 2: Run tests and confirm missing functions**

Run: `pytest -q tests/test_hpc_artifacts.py`

- [ ] **Step 3: Implement canonical coordinate keys and fraction triples**

```python
def encode_cubic(value: Cubic) -> list[list[int]]:
    return [[part.numerator, part.denominator] for part in (value.a0, value.a1, value.a2)]

def coordinate_pauli_key(registry, pauli):
    return tuple(sorted((x, y, op) for x, y, op in pauli_coordinates(registry, pauli)))
```

Use sorted keys, compact JSON separators, gzip `mtime=0`, temporary sibling files, `fsync`, and `Path.replace`.

- [ ] **Step 4: Run deterministic double-write test**

Run: `pytest -q tests/test_hpc_artifacts.py`

Expected: two writes of the same payload have identical SHA-256.

---

### Task 3: D8 shard CLI and reducer

**Files:**
- Create: `scripts/build_d8_shard.py`
- Create: `scripts/reduce_d8_shards.py`
- Test: `tests/test_d8_cli.py`

**Interfaces:**
- `build_d8_shard.py --stage-index I --order 8 --output PATH --manifest PATH` writes one exact shard.
- `reduce_d8_shards.py --input-root DIR --expected-stages 31 --output PATH --summary PATH` verifies and reduces all shards.

- [ ] **Step 1: Write CLI tests using order four fixtures**

```python
def test_all_stage_shards_reduce_to_exact_order_conditions(tmp_path: Path) -> None:
    for index in range(31):
        run_shard(index=index, order=4, root=tmp_path)
    summary = reduce_shards(tmp_path, expected_stages=31, order=4)
    assert summary["missing_stages"] == []
    assert summary["degree_term_counts"]["1"] == 0
    assert summary["degree_term_counts"]["2"] == 0
    assert summary["degree_term_counts"]["3"] == 0
    assert summary["degree_term_counts"]["4"] > 0
```

- [ ] **Step 2: Implement the shard CLI with progress and failure manifests**

The CLI writes `status="running"` before compute, prints a flushed progress line, writes the payload, then atomically replaces the manifest with `status="complete"`. Exceptions atomically write `status="failed"` and are re-raised.

- [ ] **Step 3: Implement exact reduction**

Reducer checks stage set `0..30`, order, formula id, git commit, payload SHA, and unique stage indices. It sums coordinate-addressed `Cubic` coefficients exactly. For degree eight, it encloses every coefficient with the registered cuberoot interval and sums `max(abs(lower), abs(upper))` into an exact rational Pauli-l1 site-density upper bound.

- [ ] **Step 4: Run CLI tests**

Run: `pytest -q tests/test_d8_cli.py`

---

### Task 4: Matching-order discovery array

**Files:**
- Create: `scripts/screen_matching_order.py`
- Test: `tests/test_matching_order_screen.py`

**Interfaces:**
- `screen_matching_order.py --permutation-index I --order 6 --output PATH --manifest PATH` evaluates one of `itertools.permutations(range(4))`.

- [ ] **Step 1: Write permutation coverage tests**

```python
def test_permutation_index_covers_exactly_24_orders() -> None:
    values = [permutation_from_index(i) for i in range(24)]
    assert len(set(values)) == 24
    assert values[0] == (0, 1, 2, 3)
```

- [ ] **Step 2: Implement float discovery only**

Remap each `ScalarStage.fragment_index`, run `right_generator_local_series(..., order=6)`, and record term count plus coefficient-l1 for degrees four through six. The manifest must say `trusted=false` and `purpose="discovery-ranking"`.

- [ ] **Step 3: Verify deterministic identity result**

Run: `pytest -q tests/test_matching_order_screen.py`

---

### Task 5: Slurm profiles, run specs, and sbatch scripts

**Files:**
- Create: `skills/using-slurm/profiles/xh5-acamtw.toml`
- Create: `skills/using-slurm/profiles/xh5-cfys.toml`
- Create: `hpc/issue128_d8_array.sbatch`
- Create: `hpc/issue128_d8_reduce.sbatch`
- Create: `hpc/issue128_screen_array.sbatch`
- Create: `hpc/issue128_verify.sbatch`
- Create: `scripts/plan_issue128_hpc.py`
- Test: `tests/test_issue128_hpc_plan.py`

**Interfaces:**
- Profiles select `xhacnormalb`, account `giggleliu`, and the matching user QOS.
- Planner writes `results/<run>/run_spec.json` with 31 D8 cells and 24 ordering cells.

- [ ] **Step 1: Write plan-schema tests**

```python
def test_sprint_plan_has_unique_cells_and_bounded_resources(tmp_path: Path) -> None:
    spec = build_run_spec("issue128-hpc-test")
    ids = [cell["cell_id"] for cell in spec["cells"]]
    assert len(ids) == len(set(ids)) == 55
    assert sum(cell["kind"] == "d8-stage" for cell in spec["cells"]) == 31
    assert sum(cell["kind"] == "ordering-screen" for cell in spec["cells"]) == 24
```

- [ ] **Step 2: Add fail-closed profiles and scripts**

Profiles set hard ceilings of six hours, one node, 64 CPUs, and 200 array cells. Sbatch scripts request one CPU per cell, fixed thread environment, explicit memory, array concurrency caps, and no GPU GRES.

- [ ] **Step 3: Inspect guardrails and dry-run submission**

Run:

```bash
python3 scripts/cluster_guardrail.py inspect hpc/issue128_d8_array.sbatch --profile skills/using-slurm/profiles/xh5-acamtw.toml
scripts/harness_slurm.sh --profile skills/using-slurm/profiles/xh5-acamtw.toml --dry-run submit --script hpc/issue128_d8_array.sbatch
```

Expected: no hard-limit violation and no remote command executed.

---

### Task 6: Local proof-preservation gate

**Files:**
- Modify: `tests/test_delivery_package.py`

- [ ] **Step 1: Run focused new tests**

Run: `pytest -q tests/test_cubic_right_generator.py tests/test_hpc_artifacts.py tests/test_d8_cli.py tests/test_matching_order_screen.py tests/test_issue128_hpc_plan.py`

- [ ] **Step 2: Run accepted-certificate regression**

Run:

```bash
PYTHONPATH=src python scripts/verify.py certificates/issue128-certificate.json
PYTHONPATH=src python scripts/package_delivery.py --check
shasum -a 256 -c artifacts/SHA256SUMS
```

Expected: `valid=true`, exact ratio `11791/2911`, delivery PASS, and all ten hashes OK.

- [ ] **Step 3: Run the complete default suite**

Run: `pytest -q`

Expected: no regressions.

---

### Task 7: Remote bootstrap, smoke, and production submission

**Files:**
- Runtime outputs only: `results/<run>/job-record.json`, cell logs, manifests, sidecars.

- [ ] **Step 1: Precheck and probe**

```bash
scripts/harness_slurm.sh --profile skills/using-slurm/profiles/xh5-acamtw.toml precheck
scripts/harness_slurm.sh --profile skills/using-slurm/profiles/xh5-acamtw.toml probe-partitions
```

- [ ] **Step 2: Ship exact source**

Rsync only the clean sprint checkout, excluding `.git`, existing results, caches, and virtual environments. Record local commit and post-rsync remote file-list digest in `job-record.json`.

- [ ] **Step 3: Bootstrap once on the login node**

Create `.venv`, install `-e '.[test]'`, and run import-only smoke. Do not execute D8 on the login node.

- [ ] **Step 4: Submit four-cell smoke**

Submit D8 stages `0-3` with `--array=0-3%4`, wait for RUNNING, inspect one startup log, fetch four manifests, and require all four `status=complete` before production.

- [ ] **Step 5: Submit production arrays and dependent reducer**

Submit 31 D8 stages with concurrency 16, 24 ordering screens with concurrency 12, deep verifier, and full tests. Increase D8 concurrency to 32 only if smoke RSS and queue reasons allow. The reducer uses `afterok:<d8_jobid>`.

---

### Task 8: Monitor, fetch, reduce, and adjudicate the 5x gate

**Files:**
- Runtime outputs: `results/<run>/`
- Modify after evidence exists: `artifacts/verification-transcript.txt`, delivery summary, and report source.

- [ ] **Step 1: Monitor scheduler and one representative log**

Check PENDING→RUNNING, pending reasons, startup output, and 30–45 minute pulses. Do not treat scheduler completion as proof success.

- [ ] **Step 2: Fetch and classify**

```bash
scripts/harness_slurm.sh --profile skills/using-slurm/profiles/xh5-acamtw.toml fetch <run>
scripts/harness_slurm.sh --profile skills/using-slurm/profiles/xh5-acamtw.toml classify <run> <jobid>
```

- [ ] **Step 3: Verify every cell and the reducer**

Require 31/31 D8 manifests, digest matches, exact merge reproducibility under forward and reverse shard order, and a reducer summary with the exact D8 site-density bound.

- [ ] **Step 4: Evaluate the global claim boundary**

Only if an exact r=78 ledger is at most `1e-6`, the previous integer step fails, and fast/deep/fresh-clone verification pass may a 5x claim be added. Otherwise preserve `4.050498x` and label all new results as feasibility or negative evidence.

- [ ] **Step 5: Final package audit**

Render the PDF, inspect every page, regenerate JSON/TXT/transcript/SHA manifest, and reproduce from a fresh checkout before declaring the sprint complete.

## Self-Review

- Spec coverage: exact D8, discovery array, both Slurm accounts, six-hour ceiling, manifests, proof preservation, smoke/production/fetch, and final claim gate are assigned to Tasks 1–8.
- Placeholder scan: the plan contains no `TBD`, `TODO`, deferred implementation, or undefined “appropriate handling” steps.
- Type consistency: all D8 paths use `CubicTerms`; cross-process interchange uses coordinate-addressed keys; reducers never merge raw registry bit masks.
- Safety: GPU partitions are excluded, login-node compute is excluded, array concurrency is bounded, and the existing certificate remains authoritative unless the complete new gate passes.
