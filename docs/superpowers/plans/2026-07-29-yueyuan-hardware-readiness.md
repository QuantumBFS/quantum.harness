# YueYuan Hardware Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a batch-oriented hardware boundary and dry-run workflow so attempt 004 can be exercised like a real hardware experiment.

**Architecture:** Add `hardware_adapter.py` for backend-neutral candidates, jobs, results, objective reconstruction, dry-run submission, and artifact export/ingest. Add `run_hardware_dry_run.py` as a small reproducible hardware-style batch experiment that uses the adapter without changing the existing optimizer results.

**Tech Stack:** Python 3, NumPy, CSV/JSON/JSONL artifacts, pytest, existing attempt-004 `QueryOnlyDevice`.

## Global Constraints

- Do not include credentials, usernames, hostnames, SSH commands, private keys, or private access markers.
- Do not claim real hardware was used.
- Do not change the existing full-sweep or adaptive-sweep scientific results.
- Do not use exact true-device fidelity for hardware-style objective decisions.
- Generated artifacts remain under `tracks/qcs/results/YueYuan/attempt-004/` and stay ignored by git.
- Keep `Ion.lock` unstaged and untouched.

---

### Task 1: Hardware Adapter Contracts And Dry-Run Backend

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/hardware_adapter.py`
- Test: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hardware.py`

**Interfaces:**
- Produces: `HardwareCandidate(candidate_id: str, pulse_parameters: np.ndarray, metadata: dict | None = None)`
- Produces: `HardwareJob(job_id: str, candidate_id: str, shots: int, metadata: dict)`
- Produces: `HardwareResult(job_id: str, candidate_id: str, shots: int, counts: dict[str, int], metadata: dict)`
- Produces: `HardwareEvaluation(candidate_id: str, objective: float, shots: int, counts: dict[str, int], metadata: dict)`
- Produces: `DryRunBatchBackend(true_system, seed: int = 0, success_key: str = "target")`
- Produces: `evaluate_result(result: HardwareResult, success_key: str = "target") -> HardwareEvaluation`

- [ ] **Step 1: Write failing tests**

Add tests that create two candidates, submit them to `DryRunBatchBackend`, collect results, and assert:

```python
assert backend.query_count == 2
assert backend.shot_count == 2 * shots
assert len(results) == 2
assert all(result.shots == shots for result in results)
assert all(sum(result.counts.values()) == shots for result in results)
assert all(0.0 <= evaluate_result(result).objective <= 1.0 for result in results)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hardware.py -q
```

Expected: fail because `hardware_adapter.py` does not exist.

- [ ] **Step 3: Implement minimal adapter**

Create dataclasses and dry-run backend. The dry-run backend should call
`QueryOnlyDevice.query()` once per candidate, convert returned noisy infidelity
to a success count, and expose only count dictionaries and resource counters.

- [ ] **Step 4: Verify tests pass**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hardware.py -q
```

Expected: pass.

### Task 2: Batch Export And Result Ingestion

**Files:**
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/hardware_adapter.py`
- Test: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hardware.py`

**Interfaces:**
- Produces: `write_batch_bundle(candidates, out_dir: Path, shots: int, metadata: dict | None = None) -> dict`
- Produces: `write_results_jsonl(results, path: Path) -> Path`
- Produces: `read_results_jsonl(path: Path) -> list[HardwareResult]`
- Produces: `summarize_evaluations(evaluations: list[HardwareEvaluation]) -> dict`

- [ ] **Step 1: Write failing tests**

Add tests that export a two-candidate batch and assert files exist:
`batch_manifest.json`, `candidates.csv`, `pulse_payloads.jsonl`. Then write and
read `hardware_results.jsonl` and assert candidate IDs and counts round-trip.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hardware.py -q
```

Expected: fail because export/ingest helpers do not exist.

- [ ] **Step 3: Implement export/ingest helpers**

Use only JSON, JSONL, and CSV. Manifest should include `shots_per_candidate`,
`candidate_count`, `total_planned_shots`, and `objective_proxy`.

- [ ] **Step 4: Verify tests pass**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hardware.py -q
```

Expected: pass.

### Task 3: Hardware Dry-Run Script And Docs

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_hardware_dry_run.py`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/README.md`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPORT.md`
- Test: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hardware.py`

**Interfaces:**
- Produces CLI: `python3 .../run_hardware_dry_run.py --out <dir> --shots 256`
- Produces files: `batch_manifest.json`, `candidates.csv`, `pulse_payloads.jsonl`, `hardware_results.jsonl`, `hardware_summary.json`

- [ ] **Step 1: Write failing CLI smoke test**

Run the script into `tmp_path / "hardware"` and assert the five expected files
exist, `hardware_summary.json` has `candidate_count > 0`, and `total_shots` is
positive.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hardware.py -q
```

Expected: fail because `run_hardware_dry_run.py` does not exist.

- [ ] **Step 3: Implement dry-run script**

Build a one-qubit model, optimize a short model pulse, compute Hessian basis,
create a center candidate plus plus/minus candidates along the top three
directions, export bundle, dry-run submit, write results, and write summary.

- [ ] **Step 4: Update README and REPORT**

Add a hardware-readiness section explaining the batch adapter, dry-run backend,
artifact files, and no-real-hardware limitation.

- [ ] **Step 5: Run verification**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hardware.py -q
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests -q
python3 tracks/qcs/solutions/YueYuan/research/validator/self_test.py
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_candidate.py --fast --out /tmp/yueyuan-attempt004-candidate.json
```

Expected: all tests and validator pass.

- [ ] **Step 6: Privacy scan, commit, publish**

Run the local private-marker scan over `tracks/qcs/solutions/YueYuan` and
`docs/superpowers`. Commit intended files only, then update PR #203.
