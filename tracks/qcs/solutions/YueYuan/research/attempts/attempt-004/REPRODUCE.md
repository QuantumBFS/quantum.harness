# Reproducing The YueYuan Challenge 113 Results

All commands below run from the repository root. Generated data and figures go
under `tracks/qcs/results/YueYuan/attempt-004/`, which is intentionally ignored
by git.

## 1. Check Out The Submission

```bash
git clone https://github.com/QuantumBFS/quantum.harness.git
cd quantum.harness
gh pr checkout 203
```

The last command checks out the submitted pull-request tree. After the pull
request is merged, use the repository's default branch instead.

## 2. Create The Tested Environment

The submission was verified with CPython 3.11.2. The lock file records the
complete direct and transitive Python package set used for the final check.

```bash
python3 -m venv .venv-yueyuan
. .venv-yueyuan/bin/activate
python -m pip install --upgrade pip
python -m pip install -r tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/requirements-lock.txt
```

`requirements.txt` remains the short development dependency list.
`requirements-lock.txt` is the exact reproduction environment.

## 3. Quick End-To-End Check

```bash
python tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/verify_submission.py
```

Expected final line:

```json
{"groups": 10, "records": 10, "splits": ["dev", "holdout"], "true_device_variants": ["pulse_distortion"]}
```

The command runs:

1. the sealed black-box rigor tests;
2. the validator self-test and negative controls;
3. a small finite-shot dev/holdout experiment;
4. exact checks of record counts, method coverage, splits, variant, summary
   table, and figure output.

On a typical CPU it should finish within a few minutes after dependencies are
installed. Its generated output is:

```text
tracks/qcs/results/YueYuan/attempt-004/submission_quick/
  runs.jsonl
  summary.json
  summary_tables/black_box_holdout_summary.csv
  figures/black_box_holdout_success.png
```

If Matplotlib cannot load, the numerical checks still run and the figure path
is replaced by `black_box_holdout_success.skipped.txt`.

## 4. Moderate Sealed Holdout

This is the primary current research result. It evaluates:

- one-qubit `X` and two-qubit `CZ`;
- medium, large, and hidden pulse-distortion true-device variants;
- 512 and 2048 shots per query;
- dev seeds 0 and 1, and holdout seeds 100 and 101;
- five derivative-free methods with equal closed-loop budgets.

### Local sequential run

```bash
python tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_black_box_holdout.py \
  --out tracks/qcs/results/YueYuan/attempt-004/black_box_holdout_reproduction
```

### Slurm array run

The committed script uses 48 tasks, 4 CPUs per task, `%8` concurrency, and at
most 32 CPU cores at once:

```bash
sbatch tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/black_box_holdout.sbatch
```

After all array tasks finish:

```bash
python tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_black_box_holdout.py \
  --out tracks/qcs/results/YueYuan/attempt-004/black_box_holdout_moderate \
  --combine-tasks
```

Expected combine result:

```json
{"groups": 120, "records": 240, "splits": ["dev", "holdout"], "task_files": 48, "task_files_expected": 48, "true_device_variants": ["large", "medium", "pulse_distortion"]}
```

Expected aggregate metrics:

| Method | Mean success | Median of cell-median final infidelity |
|---|---:|---:|
| Device-informed adaptive Hessian | 0.562500 | 0.002078 |
| Widen-only adaptive Hessian | 0.520833 | 0.002162 |
| Fixed Hessian subspace | 0.416667 | 0.003515 |
| Full-space Nelder-Mead | 0.187500 | 0.006854 |
| Random subspace | 0.187500 | 0.006864 |

The Slurm script contains no cluster identity. Site-specific partition,
accounting, module, or virtual-environment lines may be added locally without
committing them.

## 5. Reported Full Baseline Sweep

The report's 1,656-row full sweep predates the adaptive baseline. The
`--exclude-adaptive` flag fixes that historical method profile explicitly.
Without this flag, current code also runs the later adaptive method and produces
a different record count.

### Local sequential run

```bash
python tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_full_sweep.py \
  --out tracks/qcs/results/YueYuan/attempt-004/full_reproduction \
  --exclude-adaptive
python tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/make_figures.py \
  --results tracks/qcs/results/YueYuan/attempt-004/full_reproduction
```

### Slurm array run

The committed script uses 144 tasks, 4 CPUs per task, `%25` concurrency, and at
most 100 CPU cores at once:

```bash
sbatch tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/cpu_sweep.sbatch
```

After all array tasks finish:

```bash
python tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_full_sweep.py \
  --out tracks/qcs/results/YueYuan/attempt-004/full \
  --exclude-adaptive \
  --combine-tasks
python tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/make_figures.py \
  --results tracks/qcs/results/YueYuan/attempt-004/full
```

Do not run the combine command until all array tasks have finished. It refuses
missing or extra shards and also refuses any method profile whose aggregate
record count is not 1,656.

Expected aggregate sizes:

```text
runs.jsonl:               1,656 records
open_loop_history.jsonl:  5,121 records
hessian_spectra.json:       144 spectra
summary groups:              207
figures:                       8 PNG files
summary tables:                5 CSV files
```

## 6. Reported Adaptive-Focus Sweep

The focused recovery study keeps both systems, all three gaps, eight seeds, and
only the 2048-shot setting. The `--adaptive-focus` profile fixes this exact
configuration.

### Local sequential run

```bash
python tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_full_sweep.py \
  --out tracks/qcs/results/YueYuan/attempt-004/focus_adaptive_reproduction \
  --adaptive-focus
```

### Slurm array run

The committed script uses 48 tasks, 4 CPUs per task, `%8` concurrency, and at
most 32 CPU cores at once:

```bash
sbatch tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/adaptive_focus.sbatch
```

After all array tasks finish:

```bash
python tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_full_sweep.py \
  --out tracks/qcs/results/YueYuan/attempt-004/focus_adaptive \
  --adaptive-focus \
  --combine-tasks
```

Expected aggregate sizes:

```text
runs.jsonl:                 600 records
open_loop_history.jsonl:  1,707 records
hessian_spectra.json:        48 spectra
```

## 7. Independent Checks

Run the complete YueYuan attempt suite and validator:

```bash
python -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests -q
python tracks/qcs/solutions/YueYuan/research/validator/self_test.py
```

The fixed seeds make the finite-shot draws and method initialization
reproducible under the pinned environment. JAX runs with 64-bit arithmetic.
Small platform-level floating-point differences may change the last displayed
digits, but not the expected file counts, method coverage, or qualitative
success/failure conclusions.

## 8. Reading The Result

The concise argument is in
[`SUBMISSION.md`](../../../SUBMISSION.md). The full numerical interpretation,
failure analysis, and hardware claim boundary are in
[`REPORT.md`](REPORT.md).
