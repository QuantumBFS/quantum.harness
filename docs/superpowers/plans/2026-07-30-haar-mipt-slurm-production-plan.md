# Haar-MIPT Slurm Production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run and validate 300,000 generic-Haar monitored-circuit trajectories on the `jhzhu` Slurm account, then extract the slope-based effective central charge for `L = 6, 8, 10, 12, 14, 16`.

**Architecture:** Keep the physics kernel unchanged, add a literature-aligned per-trajectory entropy-slope estimator, and execute deterministic 1,000-trajectory batches through the repository's generic parameter-scan and Slurm machinery. Each Slurm cell writes one compressed batch plus one generic cell manifest, allowing atomic completion, exact resume, scheduler classification, and streaming local analysis without creating 300,000 small files.

**Tech Stack:** Python 3.12, NumPy 2.5.1, pytest, Slurm job arrays, `scripts/parameter_scan.py`, `scripts/harness_slurm.sh`, SSH/rsync.

## Global Constraints

- Physics parameters are fixed at `p = 0.170`, periodic brick-wall Haar `U(4)` gates, conditional Born sampling, `4L` equilibration, and `24L` recording.
- Widths are exactly `6, 8, 10, 12, 14, 16`.
- Initial-state families are exactly `global_haar` and `product`, with equal one-half weights only after separate averaging and bootstrapping.
- Production contains exactly 25,000 trajectories per `(L, family)`, split into 25 cells of 1,000 trajectories, for 300 cells and 300,000 trajectories total.
- Each Slurm cell requests one CPU, at most 2 GiB memory, and at most four hours; the array runs at most 100 cells concurrently.
- The user-approved hard ceiling remains 100 concurrent CPUs and six hours per cell.
- Credentials are interactive only and never enter Git, config values, logs, manifests, shell history, or result artifacts.
- Existing dirty changes under `.agents/skills` and `.claude/skills` are never staged, shipped, or modified.
- Long-running cells print 20--50 flushed progress updates and atomically preserve completed work.

---

### Task 1: Bootstrap a private passwordless cluster profile

**Files:**
- Modify: `.gitignore`
- Create locally but keep ignored: `skills/using-slurm/profiles/jhzhu-lab.toml`
- Create locally but keep ignored: `skills/using-slurm/profiles/active.toml`
- Create outside the repository: `~/.ssh/id_ed25519_quantum_harness`
- Modify outside the repository: `~/.ssh/config`

**Interfaces:**
- Consumes: the approved host `172.16.42.240`, user `jhzhu`, password supplied interactively, and the probed Slurm topology.
- Produces: SSH alias `jhzhu-haar`, active cluster profile, and a passing `scripts/harness_slurm.sh precheck`.

- [ ] **Step 1: Add only the private profile name to `.gitignore`**

```gitignore
# Private laboratory Slurm profile; contains a user-specific host and key path.
skills/using-slurm/profiles/jhzhu-lab.toml
```

- [ ] **Step 2: Create a dedicated automation key only when absent**

Run in WSL:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
test -f ~/.ssh/id_ed25519_quantum_harness || \
  ssh-keygen -q -t ed25519 -N '' -f ~/.ssh/id_ed25519_quantum_harness
chmod 600 ~/.ssh/id_ed25519_quantum_harness
ssh-copy-id -i ~/.ssh/id_ed25519_quantum_harness.pub jhzhu@172.16.42.240
```

Enter the supplied password only at the `ssh-copy-id` prompt. Do not place it in the command or an environment variable.

- [ ] **Step 3: Add an idempotent SSH alias**

Ensure `~/.ssh/config` contains exactly one block with this content:

```sshconfig
Host jhzhu-haar
    HostName 172.16.42.240
    User jhzhu
    Port 22
    IdentityFile ~/.ssh/id_ed25519_quantum_harness
    IdentitiesOnly yes
```

Then run:

```bash
chmod 600 ~/.ssh/config
ssh -o BatchMode=yes jhzhu-haar echo ok
```

Expected: `ok` with no password prompt.

- [ ] **Step 4: Write and activate the private profile**

Create `skills/using-slurm/profiles/jhzhu-lab.toml` with the fully probed values:

```toml
[identity]
name = "jhzhu-lab"
purpose = "CPU exact-state Haar-MIPT production"
maintainer = "Jinhong Zhu"

[connection]
repo_path_remote = "/home/jhzhu/quantum.harness-haar"
login_shell = false

[connection.ssh]
alias = "jhzhu-haar"
host = "172.16.42.240"
user = "jhzhu"
identity_file = "~/.ssh/id_ed25519_quantum_harness"
port = 22

[scheduler]
type = "slurm"
default_partition = "batch"

[[partitions]]
name = "batch"
class = "default-cpu"
cores = 192
memory = "1500000M"
max_wall = "UNLIMITED"
gpu = ""

[[partitions]]
name = "bigmem"
class = "high-mem"
cores = 128
memory = "4100000M"
max_wall = "UNLIMITED"
gpu = ""

[[partitions]]
name = "gpu"
class = "gpu"
cores = 96
memory = "2000000M"
max_wall = "UNLIMITED"
gpu = "generic:8"

[filesystem]
home = "/home/jhzhu"
scratch = "/home/jhzhu/scratch"
project = "/home/jhzhu/quantum.harness-haar"
quota = ""

[network]
internet_from_login = false
internet_from_compute = false

[region]
region = "mainland_china"

[limits.hard]
max_walltime = "06:00:00"
max_nodes = 1
max_cpus = 100
max_array_size = 500

[limits.soft]
warn_walltime = "04:00:00"
warn_cpus = 64
unusual_partitions = ["bigmem", "gpu"]

[limits.paths]
allowed_roots = ["/home/jhzhu/quantum.harness-haar/results", "/home/jhzhu/scratch"]

[commands]
squeue = "squeue -u jhzhu"
sacct = "sacct --format=JobID,State,ExitCode,MaxRSS,Elapsed"
sinfo = "sinfo -o '%P %a %.10l %.6D %.6t'"
quota_command = "sacctmgr -n show assoc user=jhzhu format=Account,Partition,QOS,GrpTRES,MaxTRES,MaxJobs"

[[gotchas]]
symptom = "Password prompts break BatchMode prechecks and monitoring"
cause = "The original connection used password authentication"
fix = "Use the dedicated id_ed25519_quantum_harness key and jhzhu-haar alias"

[notes]
text = "Live discovery found QOS strict_limit with cpu=480; the user-approved 100-CPU ceiling is stricter. Network flags remain false until a scheduled or login probe establishes otherwise."
```

Activate it in WSL:

```bash
cd /mnt/c/Users/jinhong/Documents/summer-school/quantum.harness
ln -sfn jhzhu-lab.toml skills/using-slurm/profiles/active.toml
```

- [ ] **Step 5: Validate the profile and precheck**

```bash
python3 scripts/cluster_profile.py \
  --field connection.ssh.alias \
  --profile skills/using-slurm/profiles/jhzhu-lab.toml
scripts/harness_slurm.sh precheck
scripts/harness_slurm.sh probe-partitions
```

Expected: alias `jhzhu-haar`, `ssh_ok: true`, and `batch`, `bigmem`, `gpu` rows. The already approved partition remains `batch`; stop for user ratification only if its live state is unavailable or materially more congested than another CPU partition.

- [ ] **Step 6: Commit only the ignore rule**

```bash
git add .gitignore
git commit -m "Ignore private Haar Slurm profile"
```

---

### Task 2: Add an explicit Slurm array concurrency option

**Files:**
- Modify: `scripts/harness_slurm.sh`
- Modify: `scripts/tests/test_harness_slurm.py`

**Interfaces:**
- Consumes: existing `submit --array N` behavior.
- Produces: `submit --array N --max-concurrent M`, rendered as `sbatch --array=1-N%M`, with validation `1 <= M <= N`.

- [ ] **Step 1: Write failing dry-run tests**

Add:

```python
def test_submit_array_applies_explicit_concurrency_cap(tmp_path):
    profile = write_profile(tmp_path)
    script = write_job_script(tmp_path)
    spec = tmp_path / "run_spec.json"
    spec.write_text('{"cells": [{"cell_id": "cell-0001"}]}')
    r = run(
        ["--dry-run", "submit", "--script", str(script), "--array", "300",
         "--max-concurrent", "100", "--run-spec", str(spec),
         "--command", "python3 worker.py"],
        env={"HARNESS_PROFILE_FILE": str(profile)},
    )
    assert r.returncode == 0
    assert "--array=1-300%100" in r.stderr


@pytest.mark.parametrize(("size", "cap"), [("0", "1"), ("10", "0"), ("10", "11")])
def test_submit_rejects_invalid_array_concurrency(tmp_path, size, cap):
    profile = write_profile(tmp_path)
    script = write_job_script(tmp_path)
    r = run(
        ["--dry-run", "submit", "--script", str(script), "--array", size,
         "--max-concurrent", cap, "--run-spec", "run_spec.json",
         "--command", "python3 worker.py"],
        env={"HARNESS_PROFILE_FILE": str(profile)},
    )
    assert r.returncode != 0
    assert "array" in r.stderr.lower()
```

- [ ] **Step 2: Run the new tests and verify failure**

```bash
python3 -m pytest scripts/tests/test_harness_slurm.py \
  -k 'explicit_concurrency or invalid_array_concurrency' -q
```

Expected: failure because `--max-concurrent` is unknown.

- [ ] **Step 3: Implement and validate `--max-concurrent`**

In `cmd_submit`, parse an integer `max_concurrent`, reject non-numeric values, reject a cap without an array, and render either `--array=1-$array` or `--array=1-$array%$max_concurrent`. Preserve the reported logical cell count as `N`, not `M`.

- [ ] **Step 4: Run cluster helper tests**

```bash
python3 -m pytest scripts/tests/test_harness_slurm.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/harness_slurm.sh scripts/tests/test_harness_slurm.py
git commit -m "Support capped Slurm array concurrency"
```

---

### Task 3: Implement the paper-aligned entropy-slope estimator

**Files:**
- Modify: `scripts/haar_mipt_analysis.py`
- Modify: `scripts/tests/test_haar_mipt_analysis.py`

**Interfaces:**
- Consumes: one trajectory record containing `L`, `record_steps`, `record_cost`, and `cumulative_record_cost`.
- Produces: `trajectory_entropy_fit(record, start_fraction=0.0) -> dict` with `slope`, `intercept`, `points`, and `start_index`; `aggregate_trajectory_records(records, estimator="slope")` uses the slope by default while retaining `estimator="endpoint"` as a diagnostic.

- [ ] **Step 1: Write failing synthetic slope tests**

Add:

```python
def test_trajectory_entropy_fit_recovers_slope_and_intercept():
    L, steps = 8, 40
    slope, intercept = 0.111, 0.37
    record = _record(L, "global_haar", 0, slope)
    record["cumulative_record_cost"] = [
        L * (intercept + slope * t) for t in range(1, steps + 1)
    ]
    record["record_steps"] = steps
    record["record_cost"] = record["cumulative_record_cost"][-1]
    fit = module.trajectory_entropy_fit(record)
    assert fit["slope"] == pytest.approx(slope, abs=1e-13)
    assert fit["intercept"] == pytest.approx(intercept, abs=1e-13)


def test_aggregate_uses_slope_not_endpoint_by_default():
    records = []
    for family in ("global_haar", "product"):
        for index in range(2):
            record = _record(8, family, index, 0.2)
            record["cumulative_record_cost"] = [8 * (1.0 + 0.2 * t)
                                                 for t in range(1, 193)]
            record["record_cost"] = record["cumulative_record_cost"][-1]
            records.append(record)
    row = module.aggregate_trajectory_records(records)[0]
    assert row["tilde_f"] == pytest.approx(0.2)
```

- [ ] **Step 2: Verify the tests fail for the endpoint estimator**

```bash
python3 -m pytest scripts/tests/test_haar_mipt_analysis.py \
  -k 'entropy_fit or uses_slope' -q
```

- [ ] **Step 3: Implement the minimal least-squares estimator**

Use integer times from `t = 1` through `t = record_steps` and fit `cumulative_record_cost/L = intercept + slope*t` with `numpy.linalg.lstsq`. Validate monotonic finite input, require at least two retained points, and let `start_fraction=0.5` select the late-window diagnostic.

- [ ] **Step 4: Update bootstrap and CSV artifacts to preserve estimator identity**

Thread an `estimator` argument through aggregation and bootstrap. Write `entropy_estimator`, full-window slope, late-window slope, endpoint density, and fitted intercept into trajectory summaries. Keep all family resampling independent.

- [ ] **Step 5: Run all Haar analysis tests**

```bash
python3 -m pytest scripts/tests/test_haar_mipt_analysis.py -q
```

Expected: all tests pass and synthetic `c_eff = 0.25` tests remain unchanged.

- [ ] **Step 6: Commit**

```bash
git add scripts/haar_mipt_analysis.py scripts/tests/test_haar_mipt_analysis.py
git commit -m "Fit Haar free energy from trajectory slopes"
```

---

### Task 4: Add compressed, atomic Haar batch cells

**Files:**
- Create: `scripts/haar_mipt_slurm_cell.py`
- Create: `scripts/tests/test_haar_mipt_slurm_cell.py`
- Create: `scripts/requirements-haar-mipt.txt`
- Reuse: `scripts/haar_mipt_transfer.py`
- Reuse: `scripts/haar_mipt_production.py:48` (`trajectory_seed`)

**Interfaces:**
- Consumes: `HARNESS_RUN_SPEC`, `SLURM_ARRAY_TASK_ID`, one parameter-scan cell with `L`, `initial_family`, and `block_index`, and shared settings.
- Produces: paths such as `results/haar-mipt-production-20260730/cells/cell-0001/batch.npz` plus the sibling `manifest.json`; functions `select_cell`, `run_cell`, `validate_batch`, and `iter_batch_records` are importable for tests and local analysis.

- [ ] **Step 1: Pin the remote numerical dependency**

Create `scripts/requirements-haar-mipt.txt`:

```text
numpy==2.5.1
```

- [ ] **Step 2: Write failing tests for cell selection, deterministic ranges, and atomic resume**

Create tests that assert:

```python
def test_select_cell_is_one_based(tmp_path):
    spec = make_run_spec(tmp_path, cells=2, samples_per_cell=3)
    cell = module.select_cell(spec, 1)
    assert cell["cell_id"] == "cell-0001"


def test_run_cell_writes_one_valid_compressed_batch_and_manifest(tmp_path):
    spec = make_run_spec(tmp_path, cells=1, samples_per_cell=3)
    result = module.run_cell(spec, 1, trajectory_runner=fake_trajectory)
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["status"] == "success"
    assert manifest["samples_expected"] == manifest["samples_valid"] == 3
    assert result.batch_path.suffix == ".npz"
    assert not list(result.batch_path.parent.glob("*.tmp"))


def test_resume_skips_a_valid_completed_batch(tmp_path):
    spec = make_run_spec(tmp_path, cells=1, samples_per_cell=2)
    first = module.run_cell(spec, 1, trajectory_runner=fake_trajectory)
    second = module.run_cell(spec, 1, trajectory_runner=fail_if_called)
    assert second.batch_path == first.batch_path
    assert second.resumed is True
```

Also test rejection of duplicate sample indices, wrong seeds, truncated cumulative arrays, config-hash mismatch, NaNs, and a manifest whose artifact hash no longer matches `batch.npz`.

- [ ] **Step 3: Verify the new tests fail**

```bash
python3 -m pytest scripts/tests/test_haar_mipt_slurm_cell.py -q
```

- [ ] **Step 4: Implement the batch contract**

Use sample range

```python
start = block_index * samples_per_cell
stop = min(start + samples_per_cell, samples_per_family_width)
```

and derive every seed through the existing `trajectory_seed(base_seed, L, family, sample_index)`. Save typed arrays for sample indices, seeds, total costs, cumulative costs, runtimes, gate counts, attempted measurements, and outcome counts. Save immutable settings and provenance as canonical JSON strings. Write `batch.npz.tmp`, flush and fsync it, validate it, then `os.replace` it with `batch.npz`; write `manifest.json` by the same atomic pattern.

The success manifest must include:

```json
{
  "status": "success",
  "cell_id": "cell-0001",
  "samples_expected": 1000,
  "samples_valid": 1000,
  "artifact": "batch.npz",
  "artifact_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "sample_index_start": 0,
  "sample_index_stop": 1000,
  "mean_runtime_seconds": 0.0,
  "mean_entropy_density_slope": 0.0,
  "settings": {},
  "params": {},
  "provenance": {}
}
```

Print a flushed progress line every `max(1, samples_expected // 25)` trajectories with cell ID, completed count, elapsed time, estimated remaining time, and running mean slope.

- [ ] **Step 5: Implement the environment-driven CLI**

`main()` reads `HARNESS_RUN_SPEC` and `SLURM_ARRAY_TASK_ID`, sets all BLAS/OpenMP thread variables to `1` before importing NumPy, executes one cell, and exits nonzero after writing a failure manifest when validation fails.

- [ ] **Step 6: Run batch and transfer tests**

```bash
python3 -m pytest \
  scripts/tests/test_haar_mipt_slurm_cell.py \
  scripts/tests/test_haar_mipt_transfer.py \
  scripts/tests/test_haar_mipt_production.py -q
```

- [ ] **Step 7: Commit**

```bash
git add scripts/haar_mipt_slurm_cell.py \
  scripts/tests/test_haar_mipt_slurm_cell.py \
  scripts/requirements-haar-mipt.txt
git commit -m "Add resumable Haar Slurm batch cells"
```

---

### Task 5: Define calibration/production grids and streaming analysis

**Files:**
- Create: `design/haar-mipt-slurm/calibration-axes.json`
- Create: `design/haar-mipt-slurm/calibration-settings.json`
- Create: `design/haar-mipt-slurm/production-axes.json`
- Create: `design/haar-mipt-slurm/production-settings.json`
- Create: `design/haar-mipt-slurm/provenance.json`
- Create: `scripts/haar_mipt_slurm_analysis.py`
- Create: `scripts/tests/test_haar_mipt_slurm_analysis.py`
- Modify: `scripts/tests/test_haar_mipt_slurm_cell.py`

**Interfaces:**
- Consumes: batch manifests and compressed artifacts from Task 4.
- Produces: a 12-cell calibration spec, a 300-cell production spec, runtime projection, complete-cell audit, width table, bootstrap summary, plots, and paper/stability fits.

- [ ] **Step 1: Write exact grid inputs**

Calibration axes:

```json
{
  "L": [6, 8, 10, 12, 14, 16],
  "initial_family": ["global_haar", "product"]
}
```

Calibration settings set `samples_per_cell` and `samples_per_family_width` to `8`, `p` to `0.170`, `base_seed` to `122170`, and multipliers to `4` and `24`.

Production axes:

```json
{
  "L": [6, 8, 10, 12, 14, 16],
  "initial_family": ["global_haar", "product"],
  "block_index": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12,
                  13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]
}
```

Production settings set `samples_per_cell=1000`, `samples_per_family_width=25000`, and the same physics parameters. Provenance identifies arXiv:2107.03393, commit-derived source state, exact-state-vector/Born sampling, and the approved design document.

- [ ] **Step 2: Write failing grid and streaming-analysis tests**

Tests must assert:

```python
def test_declared_grids_have_expected_cell_counts():
    assert calibration_cell_count() == 12
    assert production_cell_count() == 300


def test_complete_audit_requires_exactly_25000_unique_samples_per_family_width(tmp_path):
    summary = module.audit_run(make_fake_complete_run(tmp_path))
    assert summary["complete"] is True
    assert all(count == 25000 for count in summary["counts"].values())


def test_audit_rejects_duplicate_or_missing_sample_indices(tmp_path):
    summary = module.audit_run(make_fake_run_with_duplicate(tmp_path))
    assert summary["complete"] is False
    assert summary["duplicates"]
    assert summary["missing"]
```

Add a synthetic finite-size dataset with known `c_eff=0.25` and assert recovery by both the `L_min=(6,8,10,12)` double fit and the direct `L^-2 + L^-4` fit.

- [ ] **Step 3: Verify the tests fail**

```bash
python3 -m pytest scripts/tests/test_haar_mipt_slurm_analysis.py \
  scripts/tests/test_haar_mipt_slurm_cell.py -q
```

- [ ] **Step 4: Implement calibration projection and exact run audit**

The calibration command computes mean and upper-confidence per-trajectory runtime for every `(L, family)`, then reports projected cell time as `1000 * upper_runtime`. It emits `calibration_projection.json` and refuses a production recommendation if any projected cell exceeds `03:30:00`, preserving 30 minutes below the requested four-hour wall time.

The audit streams one batch at a time, validates its hash/config, and tracks sample-index intervals without loading all cumulative traces simultaneously. It must report all 12 expected `(L, family)` groups, duplicates, gaps, invalid cells, and total valid count.

- [ ] **Step 5: Implement final analysis artifacts**

Generate:

- `trajectory_summary.csv` with slope, late-window slope, endpoint, family, and sample identity;
- `width_summary.csv` with equal-family means and bootstrap errors;
- `fit_summary.json` with primary double fit, exclude-`L=6` fit, direct `L^-2+L^-4` fit, anisotropy error, and fit-window envelope;
- `central_charge_fit.png` and `record_growth.png` using the existing plot style;
- `run_audit.json` proving exact sample counts and manifest validity.

Use 1,000 independent bootstrap resamples within each family. Never bootstrap individual time steps.

- [ ] **Step 6: Run all Haar and parameter-scan tests**

```bash
python3 -m pytest \
  scripts/tests/test_haar_mipt_slurm_analysis.py \
  scripts/tests/test_haar_mipt_slurm_cell.py \
  scripts/tests/test_haar_mipt_analysis.py \
  scripts/tests/test_parameter_scan.py -q
```

- [ ] **Step 7: Commit**

```bash
git add design/haar-mipt-slurm \
  scripts/haar_mipt_slurm_analysis.py \
  scripts/tests/test_haar_mipt_slurm_analysis.py \
  scripts/tests/test_haar_mipt_slurm_cell.py
git commit -m "Add Haar Slurm grids and streaming analysis"
```

---

### Task 6: Verify, ship, calibrate, submit, monitor, and fetch

**Files:**
- Generate locally: `results/haar-mipt-calibration-20260730/run_spec.json`
- Generate locally: `results/haar-mipt-production-20260730/run_spec.json`
- Generate remotely and fetch: `results/haar-mipt-calibration-20260730/cells/` and `results/haar-mipt-production-20260730/cells/`
- Generate locally: `results/haar-mipt-production-20260730/analysis/`

**Interfaces:**
- Consumes: committed implementation from Tasks 1--5 and active `jhzhu-lab` profile.
- Produces: Slurm job IDs, validated calibration, 300 completed production cells, fetched artifacts, scheduler classification, final central-charge report, and plots.

- [ ] **Step 1: Run the complete relevant local verification**

```bash
python3 -m pytest \
  scripts/tests/test_harness_slurm.py \
  scripts/tests/test_haar_mipt_transfer.py \
  scripts/tests/test_haar_mipt_production.py \
  scripts/tests/test_haar_mipt_analysis.py \
  scripts/tests/test_haar_mipt_slurm_cell.py \
  scripts/tests/test_haar_mipt_slurm_analysis.py \
  scripts/tests/test_parameter_scan.py -q
git diff --check
git status --short
```

Expected: all relevant tests pass; only the pre-existing `.agents/skills` and `.claude/skills` changes remain dirty.

- [ ] **Step 2: Build both generic run specs**

```bash
python3 scripts/parameter_scan.py plan \
  --axes design/haar-mipt-slurm/calibration-axes.json \
  --settings design/haar-mipt-slurm/calibration-settings.json \
  --provenance design/haar-mipt-slurm/provenance.json \
  --run-id haar-mipt-calibration-20260730
python3 scripts/parameter_scan.py plan \
  --axes design/haar-mipt-slurm/production-axes.json \
  --settings design/haar-mipt-slurm/production-settings.json \
  --provenance design/haar-mipt-slurm/provenance.json \
  --run-id haar-mipt-production-20260730
```

Expected: 12 and 300 cells respectively.

- [ ] **Step 3: Re-run precheck and live partition probe**

```bash
scripts/harness_slurm.sh precheck
scripts/harness_slurm.sh probe-partitions
```

Proceed with the ratified `batch` partition only if it is `up`; if it is unavailable, stop and ask before switching partitions.

- [ ] **Step 4: Ship only committed source plus the two ignored run specs**

```bash
export HAAR_EXPORT_DIR="$(mktemp -d)"
git archive HEAD | tar -xf - -C "$HAAR_EXPORT_DIR"
mkdir -p "$HAAR_EXPORT_DIR/results/haar-mipt-calibration-20260730"
mkdir -p "$HAAR_EXPORT_DIR/results/haar-mipt-production-20260730"
cp results/haar-mipt-calibration-20260730/run_spec.json \
  "$HAAR_EXPORT_DIR/results/haar-mipt-calibration-20260730/"
cp results/haar-mipt-production-20260730/run_spec.json \
  "$HAAR_EXPORT_DIR/results/haar-mipt-production-20260730/"
ssh jhzhu-haar 'mkdir -p /home/jhzhu/quantum.harness-haar'
rsync -az "$HAAR_EXPORT_DIR/" jhzhu-haar:/home/jhzhu/quantum.harness-haar/
```

Verify that `.agents/skills` and `.claude/skills` dirty content did not enter the export by comparing `git archive HEAD` paths, then remove only the validated `HAAR_EXPORT_DIR` temporary directory.

- [ ] **Step 5: Bootstrap and smoke-test the remote Python environment**

```bash
ssh jhzhu-haar \
  'cd /home/jhzhu/quantum.harness-haar && python3 -m venv .venv-haar && .venv-haar/bin/python -m pip install --upgrade pip && .venv-haar/bin/pip install -r scripts/requirements-haar-mipt.txt && .venv-haar/bin/python -c "import numpy; print(numpy.__version__)"'
```

If login-node package download fails, download the CPython-3.12 Linux x86_64 NumPy 2.5.1 wheel locally into `.external/haar-wheels/`, rsync that wheel directory, and install with `--no-index --find-links`; do not enable in-job internet installation.

- [ ] **Step 6: Test-only and submit calibration**

```bash
scripts/harness_slurm.sh submit --test-only \
  --array 12 --max-concurrent 12 \
  --run-spec results/haar-mipt-calibration-20260730/run_spec.json \
  --command '.venv-haar/bin/python -u scripts/haar_mipt_slurm_cell.py' \
  --partition batch --time 00:15:00 --cpus 1 --extra '--mem=2G'
CAL_SUBMIT="$(scripts/harness_slurm.sh submit \
  --array 12 --max-concurrent 12 \
  --run-spec results/haar-mipt-calibration-20260730/run_spec.json \
  --command '.venv-haar/bin/python -u scripts/haar_mipt_slurm_cell.py' \
  --partition batch --time 00:15:00 --cpus 1 --extra '--mem=2G')"
printf '%s\n' "$CAL_SUBMIT"
CAL_JOB_ID="$(printf '%s\n' "$CAL_SUBMIT" | awk '/job_id:/ {print $2}')"
```

Within three minutes, run `status "$CAL_JOB_ID"`; after the first task enters `RUNNING`, tail one `slurm-${CAL_JOB_ID}_*.out` log and verify progress output.

- [ ] **Step 7: Fetch and approve calibration programmatically**

After the job leaves the queue:

```bash
scripts/harness_slurm.sh fetch haar-mipt-calibration-20260730
scripts/harness_slurm.sh classify haar-mipt-calibration-20260730 "$CAL_JOB_ID"
python3 scripts/haar_mipt_slurm_analysis.py calibration \
  --run-dir results/haar-mipt-calibration-20260730 \
  --production-samples-per-cell 1000
```

Proceed only if all 12 cells have success manifests and every conservative 1,000-sample projection is below 03:30:00.

- [ ] **Step 8: Test-only and submit the 300-cell production array**

```bash
scripts/harness_slurm.sh submit --test-only \
  --array 300 --max-concurrent 100 \
  --run-spec results/haar-mipt-production-20260730/run_spec.json \
  --command '.venv-haar/bin/python -u scripts/haar_mipt_slurm_cell.py' \
  --partition batch --time 04:00:00 --cpus 1 --extra '--mem=2G'
PROD_SUBMIT="$(scripts/harness_slurm.sh submit \
  --array 300 --max-concurrent 100 \
  --run-spec results/haar-mipt-production-20260730/run_spec.json \
  --command '.venv-haar/bin/python -u scripts/haar_mipt_slurm_cell.py' \
  --partition batch --time 04:00:00 --cpus 1 --extra '--mem=2G')"
printf '%s\n' "$PROD_SUBMIT"
PROD_JOB_ID="$(printf '%s\n' "$PROD_SUBMIT" | awk '/job_id:/ {print $2}')"
```

- [ ] **Step 9: Monitor startup and long-run pulses**

Within three minutes, check pending/running state. After the first task runs, tail at least one log and confirm real trajectories and estimated remaining time are advancing. Poll every 30--60 minutes until the array leaves the queue. Do not report completion from scheduler state alone.

- [ ] **Step 10: Fetch, classify, and resume only missing cells**

```bash
scripts/harness_slurm.sh fetch haar-mipt-production-20260730
scripts/harness_slurm.sh classify haar-mipt-production-20260730 "$PROD_JOB_ID"
scripts/harness_slurm.sh pending-cells haar-mipt-production-20260730 \
  --success-field status --success-value success
python3 scripts/haar_mipt_slurm_analysis.py audit \
  --run-dir results/haar-mipt-production-20260730
```

If any cells fail, classify OOM, walltime, nonzero exit, or invalid manifest and obtain user ratification before resubmitting exactly those cells. Do not rerun successful cells.

- [ ] **Step 11: Generate and verify the final physics analysis**

```bash
python3 scripts/haar_mipt_slurm_analysis.py analyze \
  --run-dir results/haar-mipt-production-20260730 \
  --alpha 0.81 --alpha-se 0.09 --bootstrap 1000 --seed 122170
```

Inspect `run_audit.json`, `fit_summary.json`, `width_summary.csv`, `central_charge_fit.png`, and `record_growth.png`. Completion requires exactly 25,000 unique valid trajectories in every one of the 12 groups and finite primary/stability fits.

- [ ] **Step 12: Commit the reproducibility report, not raw production data**

Update `docs/reports/2026-07-30-haar-mipt-checkpoint.md` with job IDs, cluster profile name, actual sample counts, CPU/wall time, scheduler classification, fit values, uncertainty decomposition, and links to ignored local result artifacts.

```bash
git add docs/reports/2026-07-30-haar-mipt-checkpoint.md
git commit -m "Report Haar MIPT Slurm production"
```

Do not commit compressed batches, Slurm logs, credentials, the private profile, or raw result directories.
