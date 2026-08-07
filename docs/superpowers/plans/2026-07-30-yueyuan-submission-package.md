# YueYuan Challenge 113 Submission Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PR #203 independently reproducible, easy for judges to evaluate, and ready for formal review.

**Architecture:** Use a two-layer submission package: `SUBMISSION.md` presents the scientific argument, while `REPRODUCE.md` gives exact commands and expected outputs. Add a tested Python quick-check entry point and make the full Slurm sweep use complete per-task shards before combining, so both the fast and research-scale evidence paths are reproducible.

**Tech Stack:** Python 3.11, JAX, NumPy, SciPy, Matplotlib, pytest, Slurm, Markdown, GitHub CLI/API.

## Global Constraints

- Generated data and figures must stay under `tracks/qcs/results/` and out of git.
- No HPC account, hostname, password, private-key path, or login command may appear in committed files or the PR.
- `Ion.lock` is unrelated and must remain unstaged and unpublished.
- The public claim is software black-box calibration, not real-hardware calibration.
- PR #203 becomes ready for review only after fresh-environment verification succeeds.
- Publish a clean tree snapshot to the existing PR branch; do not push the local historical commit chain directly.

---

### Task 1: Make the full sweep safely reproducible

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_reproducibility.py`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/experiments.py`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_full_sweep.py`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/cpu_sweep.sbatch`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/gpu_verify.sbatch`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/README.md`

**Interfaces:**
- Produces: `experiments.expected_record_count(sweep, include_adaptive: bool) -> int`
- Produces: `experiments.combine_task_outputs(out_dir: Path, expected_task_files: int | None = None) -> dict`
- Changes: `experiments.run_sweep(..., include_adaptive: bool = True)` writes indexed task files when `selected_index` is set.
- Produces CLI flags: `run_full_sweep.py --exclude-adaptive` and `run_full_sweep.py --combine-tasks`.

- [ ] **Step 1: Add failing tests for the historical record count and shard completeness**

```python
def test_reported_full_profile_has_1656_records():
    sweep = config.default_full_sweep()
    assert experiments.work_item_count(sweep) == 144
    assert experiments.expected_record_count(sweep, include_adaptive=False) == 1656


def test_full_sweep_combine_rejects_partial_task_set(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "runs_000.jsonl").write_text('{"row": 0}\n')
    (tasks / "open_loop_history_000.jsonl").write_text('{"step": 0}\n')
    (tasks / "hessian_spectra_000.json").write_text('[{"rank": 1}]\n')

    with pytest.raises(ValueError, match="expected 2 complete task shards"):
        experiments.combine_task_outputs(tmp_path, expected_task_files=2)
```

- [ ] **Step 2: Add a failing test for successful aggregation**

Create two complete fake shards with:

```text
tasks/runs_000.jsonl
tasks/open_loop_history_000.jsonl
tasks/hessian_spectra_000.json
tasks/runs_001.jsonl
tasks/open_loop_history_001.jsonl
tasks/hessian_spectra_001.json
```

Assert that `combine_task_outputs(..., expected_task_files=2)` writes
`runs.jsonl`, `open_loop_history.jsonl`, and `hessian_spectra.json`, returns
`task_files == 2`, and reports two rows in each aggregate.

- [ ] **Step 3: Run the focused tests and verify the new tests fail**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_reproducibility.py -q
```

Expected: failures because `expected_record_count` and
`combine_task_outputs` do not exist.

- [ ] **Step 4: Implement task-specific output paths and strict aggregation**

In `experiments.py`:

- add `include_adaptive=True` to `run_sweep`;
- skip the adaptive record when `include_adaptive` is false;
- write the three indexed task artifacts under `out_dir/tasks/` whenever
  `selected_index` is provided;
- preserve the existing root-level files for non-array runs;
- calculate the expected record count from the configured systems, gaps, shot
  budgets, seeds, `k` grids, and the adaptive flag;
- reject missing or extra shard indices before writing aggregate files;
- combine JSONL rows and flatten each shard's Hessian-spectrum JSON list.

In `run_full_sweep.py`:

- reject `--combine-tasks` together with `--task-index`;
- pass `include_adaptive=not args.exclude_adaptive`;
- print the combine summary as sorted JSON.

- [ ] **Step 5: Update the Slurm entry points**

Make the CPU array invoke:

```bash
run_full_sweep.py \
  --out tracks/qcs/results/YueYuan/attempt-004/full \
  --task-index "${SLURM_ARRAY_TASK_ID}" \
  --exclude-adaptive
```

The GPU array may keep the adaptive method, but it must use the new indexed task
files. Document the exact post-array combine command in `slurm/README.md`:

```bash
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_full_sweep.py \
  --out tracks/qcs/results/YueYuan/attempt-004/full \
  --exclude-adaptive \
  --combine-tasks
```

- [ ] **Step 6: Run the new and existing attempt-004 tests**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_reproducibility.py -q
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit the reliable sweep path**

```bash
git add tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_reproducibility.py
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/experiments.py
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_full_sweep.py
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/cpu_sweep.sbatch
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/gpu_verify.sbatch
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/README.md
git commit -m "Make attempt 004 sweeps reproducible"
```

### Task 2: Add the pinned environment and one-command quick check

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/requirements-lock.txt`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/verify_submission.py`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_reproducibility.py`

**Interfaces:**
- Produces: `verify_submission.validate_fast_output(out_dir: Path) -> dict`
- Produces CLI: `python verify_submission.py [--out PATH]`
- Default output: `tracks/qcs/results/YueYuan/attempt-004/submission_quick`

- [ ] **Step 1: Add failing tests for fast-output validation**

Build a fake output directory containing:

- `summary.json` with `{"records": 10, "groups": 10}`;
- ten JSONL rows spanning `dev` and `holdout`;
- only the `pulse_distortion` true-device variant;
- all five expected methods;
- ten rows in `summary_tables/black_box_holdout_summary.csv`;
- either `figures/black_box_holdout_success.png` or the documented skipped marker.

Test that `validate_fast_output` returns:

```python
{
    "records": 10,
    "groups": 10,
    "splits": ["dev", "holdout"],
    "true_device_variants": ["pulse_distortion"],
}
```

Add a second test changing `records` to 9 and assert that validation raises
`RuntimeError` with `expected 10 records`.

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_reproducibility.py -q
```

Expected: failure because `verify_submission.py` does not exist.

- [ ] **Step 3: Implement `verify_submission.py`**

The default command must:

1. find the repository root from the script location;
2. run the black-box rigor test file with the current Python interpreter;
3. run `research/validator/self_test.py`;
4. run `run_black_box_holdout.py --fast` into the selected output directory;
5. validate exact counts, splits, variant, methods, summary CSV, and figure or
   skipped marker;
6. print one sorted JSON result and return zero.

Every subprocess must use `check=True`, execute from the repository root, and
fail immediately on a nonzero exit.

- [ ] **Step 4: Add the exact tested dependency lock**

Create `requirements-lock.txt` with:

```text
contourpy==1.3.3
cycler==0.12.1
fonttools==4.63.0
iniconfig==2.3.0
jax==0.10.2
jaxlib==0.10.2
kiwisolver==1.5.0
matplotlib==3.11.1
ml_dtypes==0.5.4
numpy==2.4.6
opt_einsum==3.4.0
packaging==26.2
pillow==12.3.0
pluggy==1.6.0
Pygments==2.20.0
pyparsing==3.3.2
pytest==9.1.1
python-dateutil==2.8.2
scipy==1.17.1
six==1.16.0
```

- [ ] **Step 5: Run the focused tests and the one-command check**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_reproducibility.py -q
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/verify_submission.py
```

Expected quick-check payload:

```json
{"groups": 10, "records": 10, "splits": ["dev", "holdout"], "true_device_variants": ["pulse_distortion"]}
```

- [ ] **Step 6: Commit the quick reproduction path**

```bash
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/requirements-lock.txt
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/verify_submission.py
git add tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_reproducibility.py
git commit -m "Add submission reproduction check"
```

### Task 3: Write the judge-facing submission and reproduction guides

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/SUBMISSION.md`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPRODUCE.md`
- Modify: `tracks/qcs/solutions/YueYuan/README.md`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/README.md`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPORT.md`

**Interfaces:**
- `SUBMISSION.md` is the primary reviewer entry point.
- `REPRODUCE.md` is the canonical command reference.
- Existing READMEs link to both without duplicating their full content.

- [ ] **Step 1: Write `SUBMISSION.md`**

Use these sections and claims:

- **Verdict:** Hessian-informed closed-loop search reduces finite-shot
  black-box calibration cost when model and device remain aligned; counted
  device-informed residual probes improve robustness under mismatch but do not
  uniformly solve the hardest two-qubit case.
- **Strongest evidence:** 48/48 shards, 240 method records, 120 groups, 24
  comparison cells; mean success `0.562500` device-informed versus `0.520833`
  adaptive, `0.416667` fixed Hessian, and `0.187500` full/random.
- **Pairwise evidence:** lower median final infidelity in 24/24 cells versus
  full and random, 17/24 versus fixed Hessian, and 11/24 versus widen-only
  adaptive, with four ties against each Hessian baseline.
- **Usefulness:** converts simulator curvature into a lower-dimensional
  experiment plan while retaining a measured fallback signal when transfer
  fails.
- **Correctness:** sealed oracle/transcript/scorer separation, equal query and
  shot budgets, finite-shot noise, dev/holdout seeds, complete-shard check,
  confidence/error intervals, validator controls, and automated tests.
- **Failure boundary:** the pulse-distorted two-qubit holdout at 2048 shots
  reaches median infidelity `0.002565`, not the `1e-3` target.
- **Claim boundary:** software black box only; no real quantum hardware claim.

Link to challenge #113, `REPRODUCE.md`, `REPORT.md`, and the implementation
directory.

- [ ] **Step 2: Write `REPRODUCE.md`**

Document Python 3.11.2 as the tested interpreter and include:

```bash
python3 -m venv .venv-yueyuan
. .venv-yueyuan/bin/activate
python -m pip install --upgrade pip
python -m pip install -r tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/requirements-lock.txt
python tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/verify_submission.py
```

Document the moderate local command and the 48-task Slurm-plus-combine commands.
State expected moderate outputs: 48 shards, 240 records, 120 groups, both
splits, and three true-device variants.

Document the exact historical full profile:

```bash
python tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_full_sweep.py \
  --out tracks/qcs/results/YueYuan/attempt-004/full_reproduction \
  --exclude-adaptive
python tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/make_figures.py \
  --results tracks/qcs/results/YueYuan/attempt-004/full_reproduction
```

Explain that `--exclude-adaptive` reproduces the reported 1,656-row full sweep;
adaptive recovery was a later focused experiment reported separately.

- [ ] **Step 3: Update existing entry points**

Add prominent links to `SUBMISSION.md` and `REPRODUCE.md` near the top of both
READMEs. In `REPORT.md`, clarify that the 1,656-row full sweep used the
pre-adaptive baseline profile and cite the exact reproduction flag.

- [ ] **Step 4: Check links, placeholders, private markers, and formatting**

Run:

```bash
rg -n "TBD|TODO|PLACEHOLDER|XXX" tracks/qcs/solutions/YueYuan/SUBMISSION.md tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPRODUCE.md
rg -n "ssh -i|BEGIN OPENSSH PRIVATE KEY|password:" tracks/qcs/solutions/YueYuan
git diff --check
```

Expected: no placeholder or private-marker hits and no formatting errors.

- [ ] **Step 5: Commit the submission documents**

```bash
git add tracks/qcs/solutions/YueYuan/SUBMISSION.md
git add tracks/qcs/solutions/YueYuan/README.md
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/README.md
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPRODUCE.md
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPORT.md
git commit -m "Document YueYuan challenge submission"
```

### Task 4: Verify from a clean environment

**Files:**
- Modify only if verification reveals a concrete compatibility or documentation defect.

**Interfaces:**
- Consumes: `requirements-lock.txt` and `verify_submission.py`.
- Produces: fresh verification evidence for the PR body.

- [ ] **Step 1: Create a temporary clean virtual environment**

Run from the repository root:

```bash
REPRO_VENV_DIR="$(mktemp -d /tmp/yueyuan-repro-XXXXXX)"
python3 -m venv "$REPRO_VENV_DIR/venv"
"$REPRO_VENV_DIR/venv/bin/python" -m pip install --upgrade pip
"$REPRO_VENV_DIR/venv/bin/python" -m pip install -r tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/requirements-lock.txt
```

- [ ] **Step 2: Run the one-command check with the clean interpreter**

```bash
"$REPRO_VENV_DIR/venv/bin/python" tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/verify_submission.py \
  --out tracks/qcs/results/YueYuan/attempt-004/submission_clean_env
```

Expected: ten records, ten groups, both splits, and only
`pulse_distortion`.

- [ ] **Step 3: Run the complete attempt suite and validator**

```bash
"$REPRO_VENV_DIR/venv/bin/python" -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests -q
"$REPRO_VENV_DIR/venv/bin/python" tracks/qcs/solutions/YueYuan/research/validator/self_test.py
```

Expected: all tests pass and validator status is `passed`.

- [ ] **Step 4: Run repository and privacy checks**

Run `git diff --check`, inspect `git status --short`, scan the public solution
and design paths with the operator-local exact private-marker set, and confirm
that only `Ion.lock` remains as an unrelated unstaged change.

- [ ] **Step 5: Commit any verification-driven documentation correction**

Only if measured runtime, Python compatibility, or output differs from the
guide, make the smallest factual correction, rerun the affected check, and
commit it as:

```bash
git commit -m "Correct submission reproduction instructions"
```

### Task 5: Review and publish PR #203

**Files:**
- Update: PR #203 body and draft status.
- Publish: committed files under `docs/superpowers/` and
  `tracks/qcs/solutions/YueYuan/`.

**Interfaces:**
- Consumes: verified local tree and fresh verification evidence.
- Produces: an open, non-draft PR with direct submission and reproduction links.

- [ ] **Step 1: Request a final code and submission review**

Use `superpowers:requesting-code-review`. Resolve every critical or important
finding and rerun affected checks before publication.

- [ ] **Step 2: Run final verification immediately before publishing**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests -q
python3 tracks/qcs/solutions/YueYuan/research/validator/self_test.py
git diff --check
git status --short
```

Also run the exact private-marker scan locally without placing private values in
any committed file, terminal transcript intended for publication, or PR text.

- [ ] **Step 3: Publish a clean tree snapshot**

Read the current remote PR head, upload only changed blobs under
`docs/superpowers/` and `tracks/qcs/solutions/YueYuan/`, create a Git tree on
top of the remote head, and assert that its tree SHA equals the intended local
`HEAD^{tree}` after excluding the unrelated unstaged `Ion.lock` change. Create
one remote snapshot commit and update the branch ref with `force: false`.

- [ ] **Step 4: Update the PR body**

Put the verdict and evidence first, then direct links to:

```text
tracks/qcs/solutions/YueYuan/SUBMISSION.md
tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPRODUCE.md
tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPORT.md
```

Include the one-command quick check, fresh-environment test result, validator
result, and the explicit no-real-hardware limitation.

- [ ] **Step 5: Mark the pull request ready and verify remote state**

Run:

```bash
gh pr ready 203 --repo QuantumBFS/quantum.harness
gh pr view 203 --repo QuantumBFS/quantum.harness --json isDraft,state,url,body
```

Expected: `state` is `OPEN`, `isDraft` is `false`, and the rendered body links
to both submission documents.
