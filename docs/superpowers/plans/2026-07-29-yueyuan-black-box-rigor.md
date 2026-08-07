# YueYuan Black-Box Rigor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen attempt 004's software black-box evidence by sealing optimizer/scorer separation, adding dev/holdout evaluation, adding a pulse-distortion true-device mode, and preparing a conservative CPU Slurm sweep.

**Architecture:** Add a focused `sealed_black_box.py` module that runs closed-loop optimization using only a query oracle and returns a query transcript. Add a post-run scoring helper that receives the hidden true system only after optimization is complete. Add a `run_black_box_holdout.py` runner that evaluates dev and holdout splits, plus a conservative Slurm script for the moderate sweep.

**Tech Stack:** Python 3, NumPy, JAX, pytest, matplotlib, CSV/JSONL outputs, Slurm.

## Global Constraints

- Do not claim real hardware execution.
- Do not expose true-device internals to optimizer functions.
- Do not use exact true fidelity for optimization decisions.
- Count every black-box query and every shot.
- Keep generated results under ignored results directories or `/tmp`.
- Keep `Ion.lock` unstaged and untouched.
- Do not commit usernames, hostnames, credentials, SSH commands, private keys, or passwords.
- HPC sweep must stay below 200 concurrent CPU cores and at most one GPU. This plan uses CPU only: 4 CPUs per task and at most 8 concurrent tasks.

---

### Task 1: Pulse-Distortion True-Device Mode

**Files:**
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/device.py`
- Test: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_black_box_rigor.py`

**Interfaces:**
- Produces: `distort_pulse_parameters(pulse_parameters, system_config, smoothing: float, memory: float) -> np.ndarray`
- Produces: `build_query_device(model_system, mismatch_name: str, seed: int, query_seed: int | None = None) -> QueryOnlyDevice`
- Modifies: `QueryOnlyDevice(..., pulse_transform=None)` while keeping existing call sites compatible.

- [ ] **Step 1: Write failing pulse-distortion test**

Create `test_attempt_004_black_box_rigor.py` with:

```python
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"
sys.path.insert(0, str(ATTEMPT))

import config
import device
import pulses
import systems


def test_attempt_004_pulse_distortion_changes_pulse_and_counts_queries():
    system = systems.build_system(config.ONE_QUBIT_X)
    theta = pulses.initial_pulse(config.ONE_QUBIT_X, seed=501)

    distorted = device.distort_pulse_parameters(
        theta,
        config.ONE_QUBIT_X,
        smoothing=0.2,
        memory=0.15,
    )

    assert distorted.shape == theta.shape
    assert not np.allclose(distorted, theta)
    assert np.max(np.abs(distorted)) <= config.ONE_QUBIT_X.max_amplitude

    oracle = device.build_query_device(system, "pulse_distortion", seed=502, query_seed=503)
    value = oracle.query(theta, shots=64)

    assert 0.0 <= value <= 1.0
    assert oracle.query_count == 1
    assert oracle.shot_count == 64
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_black_box_rigor.py::test_attempt_004_pulse_distortion_changes_pulse_and_counts_queries -q
```

Expected: fail because `distort_pulse_parameters` or `build_query_device` is missing.

- [ ] **Step 3: Implement pulse-distortion mode**

In `device.py`:

- extend `MismatchConfig` with default fields `pulse_smoothing: float = 0.0` and `pulse_memory: float = 0.0`;
- add a `pulse_distortion` mismatch entry with drift/control/crosstalk/rotate perturbation and nonzero smoothing/memory;
- implement `distort_pulse_parameters`;
- allow `QueryOnlyDevice` to accept an optional `pulse_transform` and apply it inside `query`;
- add `build_query_device` that calls `build_true_system` and wraps it in `QueryOnlyDevice` with a transform only when the mismatch asks for pulse distortion.

- [ ] **Step 4: Run pulse-distortion test**

Run the command from Step 2. Expected: pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/device.py tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_black_box_rigor.py
git commit -m "Add pulse-distorted true-device mode"
```

### Task 2: Sealed Black-Box Optimizer Path

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/sealed_black_box.py`
- Modify test: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_black_box_rigor.py`

**Interfaces:**
- Produces: `QueryTranscriptEntry`
- Produces: `SealedRunResult`
- Produces: `RecordingQueryOracle`
- Produces: `run_sealed_subspace_method(...) -> SealedRunResult`
- Produces: `run_sealed_device_informed_adaptive_hessian_method(...) -> SealedRunResult`
- Produces: `score_sealed_run(system, sealed_result, true_system, shots, query_budget, seed, target_infidelity, mismatch) -> baselines.RunRecord`

- [ ] **Step 1: Write failing sealed-boundary test**

Append:

```python
import sealed_black_box


class PoisonedOracle:
    def __init__(self):
        self.query_count = 0
        self.shot_count = 0

    def query(self, pulse_parameters, shots: int, seed=None) -> float:
        self.query_count += 1
        self.shot_count += int(shots)
        return 0.5

    def exact_infidelity(self, pulse_parameters):
        raise AssertionError("optimizer touched exact true-device scoring")


def test_attempt_004_sealed_optimizer_uses_only_query_api():
    system = systems.build_system(config.ONE_QUBIT_X)
    start = pulses.initial_pulse(config.ONE_QUBIT_X, seed=511)
    oracle = sealed_black_box.RecordingQueryOracle(PoisonedOracle())
    cfg = config.ClosedLoopConfig(query_budget=7, target_infidelity=1e-3, initial_step=0.04)

    result = sealed_black_box.run_sealed_subspace_method(
        "full_space_nelder_mead",
        system,
        oracle,
        start,
        np.eye(config.ONE_QUBIT_X.raw_dim),
        k=2,
        shots=32,
        seed=512,
        cfg=cfg,
    )

    assert result.query_count <= cfg.query_budget
    assert result.shot_count == result.query_count * 32
    assert len(result.transcript) == result.query_count
    assert not hasattr(oracle, "exact_infidelity")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_black_box_rigor.py::test_attempt_004_sealed_optimizer_uses_only_query_api -q
```

Expected: fail because `sealed_black_box` is missing.

- [ ] **Step 3: Implement sealed module**

Implement `sealed_black_box.py` with:

- transcript dataclasses that store query index, shots, total shots, pulse parameters, and noisy infidelity;
- a recording oracle wrapper exposing only `query`, `query_count`, `shot_count`, and `transcript`;
- sealed subspace and device-informed methods that accept an oracle, not a true system;
- a scorer that builds `RunRecord` after optimization by auditing transcript pulses and final pulse.

- [ ] **Step 4: Run sealed-boundary test**

Run the command from Step 2. Expected: pass.

- [ ] **Step 5: Add score-afterward test**

Append:

```python
def test_attempt_004_sealed_result_is_scored_after_optimization():
    system = systems.build_system(config.ONE_QUBIT_X)
    true_system = device.build_true_system(system, "small", seed=521)
    oracle = sealed_black_box.RecordingQueryOracle(
        device.QueryOnlyDevice(true_system, seed=522)
    )
    start = pulses.initial_pulse(config.ONE_QUBIT_X, seed=523)
    cfg = config.ClosedLoopConfig(query_budget=8, target_infidelity=1e-3, initial_step=0.04)

    sealed = sealed_black_box.run_sealed_subspace_method(
        "hessian_subspace_nelder_mead",
        system,
        oracle,
        start,
        np.eye(config.ONE_QUBIT_X.raw_dim),
        k=3,
        shots=32,
        seed=524,
        cfg=cfg,
    )
    record = sealed_black_box.score_sealed_run(
        system,
        sealed,
        true_system,
        shots=32,
        query_budget=cfg.query_budget,
        seed=524,
        target_infidelity=cfg.target_infidelity,
        mismatch="small",
    )

    assert record.query_count == sealed.query_count
    assert record.total_shots == sealed.shot_count
    assert 0.0 <= record.final_infidelity <= 1.0
```

- [ ] **Step 6: Run black-box rigor tests**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_black_box_rigor.py -q
```

Expected: pass.

- [ ] **Step 7: Commit Task 2**

```bash
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/sealed_black_box.py tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_black_box_rigor.py
git commit -m "Add sealed black-box optimizer path"
```

### Task 3: Dev/Holdout Device-Informed Runner

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_black_box_holdout.py`
- Modify test: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_black_box_rigor.py`

**Interfaces:**
- Produces CLI: `python3 .../run_black_box_holdout.py --out <dir> --fast`
- Produces task CLI: `python3 .../run_black_box_holdout.py --out <dir> --task-index <i>`
- Produces combine CLI: `python3 .../run_black_box_holdout.py --out <dir> --combine-tasks`
- Produces generated files: `runs.jsonl`, `summary_tables/black_box_holdout_summary.csv`, `figures/black_box_holdout_success.png`

- [ ] **Step 1: Write failing runner smoke test**

Append:

```python
import csv
import json
import subprocess


def test_attempt_004_black_box_holdout_runner_emits_dev_and_holdout(tmp_path):
    out_dir = tmp_path / "black_box_holdout"
    result = subprocess.run(
        [
            sys.executable,
            str(ATTEMPT / "run_black_box_holdout.py"),
            "--out",
            str(out_dir),
            "--fast",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in (out_dir / "runs.jsonl").read_text().splitlines()]
    assert {"dev", "holdout"} <= {row["split"] for row in rows}
    assert "device_informed_adaptive_hessian_nelder_mead" in {row["method"] for row in rows}
    assert "pulse_distortion" in {row["true_device_variant"] for row in rows}
    summary_rows = list(csv.DictReader((out_dir / "summary_tables" / "black_box_holdout_summary.csv").open()))
    assert summary_rows
    assert (out_dir / "figures" / "black_box_holdout_success.png").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_black_box_rigor.py::test_attempt_004_black_box_holdout_runner_emits_dev_and_holdout -q
```

Expected: fail because the runner is missing.

- [ ] **Step 3: Implement holdout runner**

The runner should:

- use fast work items for local smoke:
  - one-qubit X, `pulse_distortion`, 256 shots, split `dev`, seed 0;
  - two-qubit CZ, `pulse_distortion`, 256 shots, split `holdout`, seed 100;
- use moderate work items for HPC:
  - systems: one-qubit X and two-qubit CZ;
  - mismatches: `medium`, `large`, `pulse_distortion`;
  - shots: 512 and 2048;
  - dev seeds: 0 and 1;
  - holdout seeds: 100 and 101;
- run the five methods listed in the design through sealed optimizers;
- write `runs.jsonl` for full local runs;
- for `--task-index`, write `tasks/runs_<index>.jsonl`;
- for `--combine-tasks`, combine task JSONL files into `runs.jsonl` and summary outputs;
- write a summary CSV grouped by split/system/mismatch/shots/method;
- write a compact success-rate bar plot.

- [ ] **Step 4: Run runner smoke test**

Run the command from Step 2. Expected: pass.

- [ ] **Step 5: Run all black-box rigor tests**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_black_box_rigor.py -q
```

Expected: pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_black_box_holdout.py tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_black_box_rigor.py
git commit -m "Add sealed holdout benchmark runner"
```

### Task 4: Conservative Slurm Script And Documentation

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/black_box_holdout.sbatch`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/README.md`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/README.md`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPORT.md`
- Modify: `docs/superpowers/snapshots/2026-07-29-yueyuan-solution-version-ledger.md`

**Interfaces:**
- Produces Slurm command: `sbatch tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/black_box_holdout.sbatch`

- [ ] **Step 1: Add Slurm script**

Create a CPU-only Slurm script with:

```bash
#SBATCH --job-name=yueyuan-a004-bbox
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=02:00:00
#SBATCH --array=0-47%8
```

It should run `run_black_box_holdout.py --out tracks/qcs/results/YueYuan/attempt-004/black_box_holdout_moderate --task-index "${SLURM_ARRAY_TASK_ID}"`.

- [ ] **Step 2: Update docs**

Document:

- sealed optimizer/scorer separation;
- pulse-distortion mode;
- dev/holdout split;
- local fast command and expected count;
- Slurm script resource use: 4 CPUs per task, 8 concurrent tasks, 32 CPUs maximum, CPU only.

- [ ] **Step 3: Run local fast benchmark**

Run:

```bash
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_black_box_holdout.py --out /tmp/yueyuan-a004-black-box-holdout --fast
```

Expected: JSON output with nonzero records, both dev and holdout splits, and output files.

- [ ] **Step 4: Run verification**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_black_box_rigor.py -q
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
python3 tracks/qcs/solutions/YueYuan/research/validator/self_test.py
git diff --check
```

Also run the local private-marker scan with exact private markers kept out of committed docs. Expected: no hits.

- [ ] **Step 5: Commit Task 4**

```bash
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/black_box_holdout.sbatch tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/README.md tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/README.md tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPORT.md
git add -f docs/superpowers/snapshots/2026-07-29-yueyuan-solution-version-ledger.md
git commit -m "Document sealed black-box holdout pass"
```

### Task 5: Moderate HPC Submission And PR Update

**Files:**
- No committed code changes expected unless HPC output reveals a bug.

**Interfaces:**
- Consumes: `slurm/black_box_holdout.sbatch`
- Produces: running Slurm job or a clear local blocker note.

- [ ] **Step 1: Upload current repo snapshot to HPC**

Use the existing SSH key-based path from the user's environment. Do not print,
commit, or document private machine/account details.

- [ ] **Step 2: Submit moderate CPU job**

Submit:

```bash
sbatch tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/black_box_holdout.sbatch
```

Expected: one Slurm job id. Resources: 48 array tasks, 4 CPUs each, `%8`
concurrency, maximum 32 CPUs at once, no GPU.

- [ ] **Step 3: Check queue**

Run a queue check for the user's jobs. Report job id, state, and array progress
without revealing private host/account details.

- [ ] **Step 4: Publish PR update**

After local verification and submission, update PR #203 with:

- sealed optimizer/scorer separation;
- pulse-distortion true-device mode;
- dev/holdout local fast results;
- moderate CPU Slurm job id/status;
- no real-hardware limitation;
- private-marker scan result.
