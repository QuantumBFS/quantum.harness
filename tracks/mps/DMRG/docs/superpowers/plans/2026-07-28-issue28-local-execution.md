# Issue #28 Local N3/N4 Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. The user explicitly requested inline execution, no subagents, and no Git commits.

**Goal:** Add a fail-closed, resource-bounded local execution path for the frozen Issue #28 N3 pilot and N4 five-seed formal experiment, then run N3 and N4 without changing any scientific gate.

**Architecture:** Keep the existing N3 and N4 scientific kernels and add explicit local authorization plus worker limits at their public boundaries. A subprocess coordinator executes the five immutable N4 bundles in waves of two, two, and one, records atomic state and host provenance, and drops to one concurrent bundle when available memory is below 12 GiB. Slurm remains supported as a fallback, but local executions are visibly marked `LOCAL_COMPUTE_DEVIATION` in manifests and the frozen formal protocol.

**Tech Stack:** Python 3.12, NumPy, SciPy, Numba, `concurrent.futures`, `subprocess`, atomic JSON artifacts, pytest.

## Global Constraints

- Physical setup remains periodic 45 x 45 Ising at `K = 0.436` with non-overlapping 3 x 3 majority blocking.
- Every successful formal seed completes exactly five dependent neural-to-neural rounds.
- Every handoff remains `U_next = -V_frozen` and the pure-neural 13-operator branch remains bitwise all-zero float64.
- N3 uses the disjoint `n3-five-round-pilot` seed bundle; N4 uses exactly `formal-1` through `formal-5` with no replacement or extension.
- Held-out BAR objective, bridge ladder, stopping thresholds, gauge reference, paired streams, and terminal classifications remain unchanged.
- N3 and N4 never overlap. N4 runs at most two bundles concurrently and at most eight Issue #28 workers per bundle.
- The second bundle in a wave starts only when available memory is at least 12 GiB; otherwise execution continues with one bundle.
- Large local compute is rejected unless every public entry receives explicit `allow_large_local=True` or `--allow-large-local`.
- BLAS, OpenMP, and Numba thread environment variables are set to the per-bundle worker limit before child processes start.
- Existing output directories are never overwritten. Resume accepts only hash-matching manifests and the five preregistered bundle IDs.
- A child scientific negative is retained and never retried. A nonzero child exit stops new launches and is recorded separately as a protocol failure.
- Runtime manifests record code hash, protocol hash, host, logical CPUs, CPU affinity, memory, worker limit, maximum bundle concurrency, and `LOCAL_COMPUTE_DEVIATION`.
- MPS results remain optional and never enter Issue #28 success gates.
- User-facing CLI and progress output remain Simplified Chinese.
- No Git commit is created during this execution.

---

## File Map

- Create `src/vmcrg_ref/local_execution.py`: worker validation, Linux host/memory provenance, bounded subprocess scheduler, atomic coordinator state, and five-bundle local N4 orchestration.
- Create `scripts/issue28_local_formal.py`: Simplified-Chinese CLI for the immutable local N4 schedule.
- Create `tests/test_issue28_local_execution.py`: authorization, worker limit, memory downgrade, concurrency, failure, no-retry, resume, and output non-overwrite tests.
- Modify `src/vmcrg_ref/hybrid_neural.py`: accept and honor an explicit optimizer worker limit.
- Modify `src/vmcrg_ref/multi_optimizer.py`: accept and honor an explicit traditional-arm worker limit.
- Modify `scripts/neural_challenge.py`: pass the worker limit into neural training and record it.
- Modify `src/vmcrg_ref/one_round.py`: carry backend/worker/local-deviation provenance through round one.
- Modify `src/vmcrg_ref/five_round.py`: authorize large local N3, cap later-round executors, and record local host provenance.
- Modify `scripts/issue28_five_round.py`: add `--allow-large-local` and `--workers`.
- Modify `src/vmcrg_ref/formal.py`: authorize local N4 bundle execution and pass backend/worker metadata to compute.
- Modify `src/vmcrg_ref/formal_compute.py`: remove hard-coded Slurm provenance, cap linear/autocorrelation workers, and propagate backend to all neural rounds and final manifests.
- Modify `scripts/issue28_formal.py`: add local backend, explicit authorization, and worker CLI options.
- Modify `src/vmcrg_ref/formal_protocol.py`: freeze matched-local resources from measured N3 provenance and validate the deviation record.
- Modify `tests/test_issue28_five_round.py`, `tests/test_issue28_formal.py`, and `tests/test_issue28_formal_protocol.py`: replace obsolete Slurm-only assertions with explicit authorization and provenance contracts.
- Modify `PLAN.md`: preserve the scientific plan while documenting the user-authorized local compute deviation and current run commands.

---

### Task 1: Explicit Worker Limits and Large-Local N3 Authorization

**Files:**
- Create: `src/vmcrg_ref/local_execution.py`
- Create: `tests/test_issue28_local_execution.py`
- Modify: `tests/test_issue28_five_round.py`
- Modify: `src/vmcrg_ref/hybrid_neural.py`
- Modify: `src/vmcrg_ref/multi_optimizer.py`
- Modify: `scripts/neural_challenge.py`
- Modify: `src/vmcrg_ref/one_round.py`
- Modify: `src/vmcrg_ref/five_round.py`
- Modify: `scripts/issue28_five_round.py`

**Interfaces:**
- Produce: `resolve_worker_limit(requested: int | None, tasks: int) -> int`
- Produce: `local_host_provenance(*, workers_per_bundle: int, max_parallel_bundles: int) -> dict[str, object]`
- Change: `HybridNeuralVMCRGOptimizer(..., max_workers: int | None = None)`
- Change: `MultiOperatorOptimizer(..., max_workers: int | None = None)`
- Change: `train(..., max_workers: int | None = None)`
- Change: `run_one_round(..., backend: str | None = None, workers: int | None = None, local_compute_deviation: bool = False)`
- Change: `run_five_round_chain(..., allow_large_local: bool = False, workers: int | None = None)`

- [ ] **Step 1: Write failing worker-limit and authorization tests**

```python
def test_large_local_n3_requires_explicit_authorization(tmp_path):
    with pytest.raises(ValueError, match="allow_large_local"):
        run_five_round_chain(
            load_issue28_protocol(PROTOCOL_PATH),
            five_round_pilot_bundle(),
            tmp_path / "N3",
            backend="local",
            resume=False,
            preset="pilot",
            rounds=5,
            workers=8,
        )

def test_worker_limit_is_bounded_by_tasks_not_cpu_count(monkeypatch):
    monkeypatch.setattr(os, "cpu_count", lambda: 256)
    assert resolve_worker_limit(3, 8) == 3
    assert resolve_worker_limit(20, 8) == 8
    with pytest.raises(ValueError, match="positive"):
        resolve_worker_limit(0, 8)

def test_n3_cli_exposes_explicit_large_local_gate():
    args = build_parser().parse_args([
        "--preset", "pilot", "--rounds", "5", "--backend", "local",
        "--workers", "8", "--allow-large-local", "--output", "run",
    ])
    assert args.allow_large_local is True
    assert args.workers == 8
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_local_execution.py tests/test_issue28_five_round.py -q`

Expected: FAIL because `resolve_worker_limit`, the CLI flags, and the new function parameters do not exist.

- [ ] **Step 3: Implement the minimal worker contract**

```python
def resolve_worker_limit(requested: int | None, tasks: int) -> int:
    if tasks <= 0:
        raise ValueError("task count must be positive")
    value = max(1, os.cpu_count() or 1) if requested is None else int(requested)
    if value <= 0:
        raise ValueError("worker limit must be positive")
    return min(tasks, value)
```

Store the resolved value on both optimizers and pass it to every relevant `ThreadPoolExecutor`. Preserve existing defaults when no explicit worker limit is supplied.

- [ ] **Step 4: Implement N3 authorization and provenance**

The large-local guard is exactly:

```python
large = preset != "smoke" or round_count > 2
if backend == "local" and large and not allow_large_local:
    raise ValueError("large local N3 requires allow_large_local=True")
```

Pass `workers` through round one and later rounds. Record `backend="local"`, `execution_policy="LOCAL_COMPUTE_DEVIATION"`, the resolved worker limit, and host provenance in `resources.json`, round reports, chain report, and final N3 manifest.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `../../../.venv/bin/python -m pytest tests/test_training_protocol.py tests/test_traditional_certification.py tests/test_issue28_one_round.py tests/test_issue28_five_round.py tests/test_issue28_local_execution.py -q`

Expected: PASS with no warnings or failures.

### Task 2: Local N4 Bundle API and Matched Three-Arm Resources

**Files:**
- Modify: `tests/test_issue28_formal.py`
- Modify: `src/vmcrg_ref/formal.py`
- Modify: `src/vmcrg_ref/formal_compute.py`
- Modify: `scripts/issue28_formal.py`

**Interfaces:**
- Change: `run_formal_bundle(..., allow_large_local: bool = False, workers: int | None = None)`
- Change: `execute_formal_bundle(..., backend: str, workers: int)`
- Change: `train_linear_round(..., workers: int | None = None)`
- Change: `measure_three_arm_autocorrelation(..., workers: int | None = None)`
- Change: `finalize_formal_bundle(..., backend: str, workers: int)`

- [ ] **Step 1: Write failing local-N4 tests**

```python
def test_local_formal_bundle_requires_explicit_authorization(tmp_path):
    with pytest.raises(ValueError, match="allow_large_local"):
        run_formal_bundle(
            load_issue28_protocol(PROTOCOL_PATH), "formal-1", tmp_path / "formal-1",
            backend="local", resume=False, formal_execution=_execution(), dry_run=True,
            workers=8,
        )

def test_authorized_local_formal_dry_run_records_worker_budget(tmp_path):
    plan = run_formal_bundle(
        load_issue28_protocol(PROTOCOL_PATH), "formal-1", tmp_path / "formal-1",
        backend="local", resume=False, formal_execution=_local_execution(), dry_run=True,
        allow_large_local=True, workers=8,
    )
    assert plan["runtime"]["backend"] == "local"
    assert plan["runtime"]["workers_per_bundle"] == 8
    assert plan["runtime"]["execution_policy"] == "LOCAL_COMPUTE_DEVIATION"
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_formal.py -q`

Expected: FAIL because the local formal interface is not implemented.

- [ ] **Step 3: Propagate backend and worker limit through one bundle**

Replace every hard-coded `backend="slurm"` within formal execution with the verified backend parameter. Pass eight workers into neural training, traditional training, and three-arm autocorrelation. The plan and final resources record the same hardware class and worker budget for neural, linear, and unbiased arms.

- [ ] **Step 4: Preserve fail-closed behavior**

Reject unknown backends, reject local without authorization, refuse nonempty output without `resume`, verify the frozen plan before resume, and preserve exact-zero checks before starting the linear arm.

- [ ] **Step 5: Run formal tests and verify GREEN**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_formal.py tests/test_issue28_formal_protocol.py tests/test_issue28_five_round.py -q`

Expected: PASS with local and Slurm paths both covered.

### Task 3: Bounded 2+2+1 Local Formal Coordinator

**Files:**
- Modify: `src/vmcrg_ref/local_execution.py`
- Create: `scripts/issue28_local_formal.py`
- Modify: `src/vmcrg_ref/__init__.py`
- Modify: `tests/test_issue28_local_execution.py`

**Interfaces:**
- Produce: `available_memory_bytes() -> int`
- Produce: `run_bounded_process_schedule(commands: Mapping[str, Sequence[str]], *, output: Path, max_parallel: int, minimum_memory_for_parallel_bytes: int, resume: bool) -> dict[str, object]`
- Produce: `run_local_formal(protocol: Path, output: Path, *, workers_per_bundle: int = 8, max_parallel_bundles: int = 2, minimum_available_gib: float = 12.0, resume: bool = False, allow_large_local: bool = False) -> dict[str, object]`

- [ ] **Step 1: Write failing scheduler tests using real short child processes**

```python
def test_schedule_runs_five_unique_cells_with_peak_two(tmp_path):
    commands = _timed_child_commands(tmp_path, ["formal-1", "formal-2", "formal-3", "formal-4", "formal-5"])
    result = run_bounded_process_schedule(
        commands, output=tmp_path / "state", max_parallel=2,
        minimum_memory_for_parallel_bytes=1, resume=False,
    )
    assert result["dispatch_order"] == ["formal-1", "formal-2", "formal-3", "formal-4", "formal-5"]
    assert result["maximum_observed_parallel"] == 2
    assert result["attempts"] == {f"formal-{index}": 1 for index in range(1, 6)}

def test_nonzero_child_stops_new_launches(tmp_path):
    commands = _failing_child_commands(tmp_path)
    result = run_bounded_process_schedule(
        commands, output=tmp_path / "state", max_parallel=1,
        minimum_memory_for_parallel_bytes=1, resume=False,
    )
    assert result["classification"] == "PROTOCOL_FAILURE"
    assert result["completed"] == []
    assert result["not_launched"] == ["formal-2", "formal-3", "formal-4", "formal-5"]
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_local_execution.py -q`

Expected: FAIL because the scheduler and coordinator are absent.

- [ ] **Step 3: Implement atomic coordinator state**

Use `subprocess.Popen` with one log file per bundle. After each launch and exit, atomically rewrite `local_coordinator.json`. The record contains ordered bundle IDs, PIDs, start/end timestamps, exit codes, attempts, peak concurrency, memory observations, thread environment, and the terminal classification.

- [ ] **Step 4: Implement memory downgrade and fail-stop rules**

The first child may start whenever no child is running. A second child may start only when `available_memory_bytes() >= 12 * 1024**3`. A nonzero exit sets `PROTOCOL_FAILURE`, prevents all remaining launches, and terminates a still-running sibling. Completed scientific negatives have exit code zero and remain completed without retry.

- [ ] **Step 5: Build exactly five immutable local commands**

Each child command is:

```text
<python> -u scripts/issue28_formal.py --protocol <frozen> --bundle formal-N \
  --output <root>/formal-N --backend local --workers 8 --allow-large-local
```

Set `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, and `NUMBA_NUM_THREADS` to `8`; set `PYTHONHASHSEED=0`; use distinct `NUMBA_CACHE_DIR` values per bundle.

- [ ] **Step 6: Run coordinator tests and verify GREEN**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_local_execution.py tests/test_issue28_formal.py -q`

Expected: PASS, including peak concurrency two and fail-stop behavior.

### Task 4: Freeze Local Resource Provenance and Synchronize Plans

**Files:**
- Modify: `tests/test_issue28_formal_protocol.py`
- Modify: `src/vmcrg_ref/formal_protocol.py`
- Modify: `PLAN.md`
- Modify: `docs/superpowers/specs/2026-07-28-issue28-local-execution-deviation-design.md`

**Interfaces:**
- Change: `_resource_request(chain_report: dict[str, object]) -> dict[str, object]`
- Preserve: `freeze_formal_protocol(...) -> dict[str, object]`

- [ ] **Step 1: Write a failing local provenance freeze test**

```python
def test_formal_freeze_preserves_local_deviation_and_concurrency(tmp_path):
    manifest = _pilot_fixture(tmp_path / "pilot", "EASY_GOAL_SUCCESS", backend="local")
    value = freeze_formal_protocol(UMBRELLA, manifest, tmp_path / "formal.json")
    resources = value["formal_execution"]["resources"]
    assert resources["backend"] == "local"
    assert resources["execution_policy"] == "LOCAL_COMPUTE_DEVIATION"
    assert resources["workers_per_bundle"] == 8
    assert resources["max_parallel_bundles"] == 2
    assert resources["host"]["node"]
```

Extend `_pilot_fixture` with `backend: str = "slurm"`. For `backend="local"`, its chain resources contain the literal record below so the expected values are independent of the code under test:

```python
{
    "backend": "local",
    "execution_policy": "LOCAL_COMPUTE_DEVIATION",
    "workers_per_bundle": 8,
    "max_parallel_bundles": 2,
    "host": {"node": "test-local-host", "logical_cpus": 32, "memory_total_bytes": 32 * 1024**3},
}
```

- [ ] **Step 2: Run the test and verify RED**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_formal_protocol.py -q`

Expected: FAIL because `_resource_request` still hard-codes `matched_slurm_partition`.

- [ ] **Step 3: Freeze measured local resources without changing scientific fields**

For local N3, derive wall time, memory, output size, workers, host, and maximum concurrency from the verified chain report. For Slurm N3, retain the existing partition-freeze fields. Validate the local marker, worker count, concurrency bound, and nonempty host record in `load_formal_execution_protocol`.

- [ ] **Step 4: Synchronize durable documentation**

Update `PLAN.md` so its scientific goal and stage gates remain unchanged while the compute policy points to the confirmed local-deviation design and this implementation plan. State that local N3/N4 require explicit flags and that Slurm job `5311997` is only a fallback until local preflight passes.

- [ ] **Step 5: Run focused and complete suites**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_formal_protocol.py tests/test_issue28_local_execution.py tests/test_issue28_formal.py tests/test_issue28_five_round.py -q`

Run: `../../../.venv/bin/python -m pytest -q`

Expected: all tests pass with zero failures.

### Task 5: Small-Lattice Preflight and Remote Fallback Cancellation

**Files:**
- Create at runtime: `results/issue28-local-preflight-20260728-01/`

- [ ] **Step 1: Run a fresh two-round local smoke**

Run:

```bash
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMBA_NUM_THREADS=2 \
../../../.venv/bin/python -u scripts/issue28_five_round.py \
  --protocol config/issue28_easy_v1.json --preset smoke --rounds 2 \
  --backend local --workers 2 \
  --output results/issue28-local-preflight-20260728-01/N3-smoke
```

Expected: two verified round manifests, contiguous predecessor hash, exact-zero 13-operator branch, and final smoke classification `SCIENTIFIC_NEGATIVE` solely because smoke is statistically insufficient.

- [ ] **Step 2: Verify hashes and local provenance**

Run a read-only verifier against the smoke manifest and confirm code, protocol, basis, gauge, output hashes, backend, worker count, and local host record.

- [ ] **Step 3: Recheck job 5311997 and cancel only if still pending**

Use the repository Slurm helper to query `5311997`. If its state is `PENDING`, cancel it and verify the terminal scheduler state before starting local N3. If it has started or ended, inspect its manifest first and refuse duplicate pilot execution.

### Task 6: Full Local N3 Pilot and Formal Protocol Freeze

**Files:**
- Create at runtime: `results/issue28-n3-local-20260728-01/`
- Create after N3 passes: `config/issue28_formal_v1.json`

- [ ] **Step 1: Launch N3 alone with eight workers**

Run:

```bash
OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 NUMBA_NUM_THREADS=8 \
../../../.venv/bin/python -u scripts/issue28_five_round.py \
  --protocol config/issue28_easy_v1.json --preset pilot --rounds 5 \
  --backend local --workers 8 --allow-large-local \
  --output results/issue28-n3-local-20260728-01
```

- [ ] **Step 2: Monitor progress and atomic outputs**

Check the live log at least every 30-60 minutes. Verify each completed `round-NN/manifest.json` before relying on the next round. Do not start N4 while N3 is running.

- [ ] **Step 3: Apply the N3 acceptance gate**

Require five contiguous rounds, exact-zero linear branch, finite parameters, verified code/protocol/basis/gauge hashes, local resource provenance, and top-level `classification="EASY_GOAL_SUCCESS"`. Stop before N4 for any correctness or protocol failure.

- [ ] **Step 4: Freeze the formal protocol exactly once**

Run:

```bash
../../../.venv/bin/python -u scripts/freeze_issue28_formal_protocol.py \
  --umbrella config/issue28_easy_v1.json \
  --pilot results/issue28-n3-local-20260728-01/manifest.json \
  --output config/issue28_formal_v1.json
```

Verify the generated protocol hash, pilot-manifest hash, five seed bundles, five rounds, frozen objective/training values, local host class, eight workers per bundle, and maximum concurrency two.

### Task 7: Five-Seed N4 Formal Run in 2+2+1 Waves

**Files:**
- Create at runtime: `results/issue28-n4-local-20260728-01/`

- [ ] **Step 1: Launch the immutable coordinator**

Run:

```bash
../../../.venv/bin/python -u scripts/issue28_local_formal.py \
  --protocol config/issue28_formal_v1.json \
  --output results/issue28-n4-local-20260728-01 \
  --workers-per-bundle 8 --max-parallel-bundles 2 \
  --minimum-available-gib 12 --allow-large-local
```

- [ ] **Step 2: Monitor each child independently**

Read `local_coordinator.json` and `logs/formal-N.log`. Verify each completed bundle manifest before accepting its exit status. Maintain at most two running children and fall back to one when the memory gate closes.

- [ ] **Step 3: Preserve all five declared outcomes**

Do not replace a failed seed, add a seed, change a threshold, or rerun a scientific negative. Use `--resume` only after hash verification for an interrupted computation.

- [ ] **Step 4: Final classification and report inputs**

Run `classify_formal_root` on exactly `formal-1` through `formal-5`. Distinguish `CORRECTNESS_FAILURE`, `PROTOCOL_FAILURE`, `SCIENTIFIC_NEGATIVE`, and `EASY_GOAL_SUCCESS`; then pass the verified artifacts into the existing N5 reporting path.

### Task 8: Final Verification and Chinese Report

**Files:**
- Create at runtime: final JSON/CSV/figures/HTML under the existing N5 report directory.

- [ ] **Step 1: Run the complete test suite fresh**

Run: `../../../.venv/bin/python -m pytest -q`

Expected: zero failures.

- [ ] **Step 2: Verify every formal artifact**

Check all five bundle identities, round counts, predecessor hashes, protocol/code/operator/gauge hashes, exact-zero branch, paired initial hashes, independent RNG stream hashes, three-arm outputs, resource records, and coordinator state.

- [ ] **Step 3: Generate the final Simplified-Chinese report**

The report leads with the terminal classification, then shows five-round neural-to-neural continuity, paired neural-versus-linear objective results, autocorrelation and ESS/s ratios, confidence intervals, overlap diagnostics, seed-direction counts, runtime, memory, and any valid negative conclusion.

- [ ] **Step 4: Record verification evidence without committing**

Report the exact test count, output paths, protocol/code hashes, N3/N4 classifications, runtime/resource totals, and final report path. Leave the worktree uncommitted as requested.
