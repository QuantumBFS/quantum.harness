# Attempt 004 Slurm Notes

These scripts are intentionally conservative.

- CPU sweep: `--cpus-per-task=4` and `--array=0-143%25`, at most 100 CPU cores at one time.
- Adaptive focus: `--cpus-per-task=4` and `--array=0-47%8`, at most 32 CPU cores at one time.
- Black-box holdout sweep: `--cpus-per-task=4` and `--array=0-47%8`, at most 32 CPU cores at one time.
- GPU verification: `--gres=gpu:1` and `--array=0-3%1`, at most one GPU at one time.
- If `$HOME/.venvs/quantum-harness-a004/bin/activate` exists, the scripts activate it before running Python.
- Generated logs and JSONL files are written under `tracks/qcs/results/YueYuan/attempt-004/`, which is ignored by git.
- Do not add usernames, hostnames, credentials, SSH commands, or private keys to these files.

Submit from the repository root after local tests pass:

```bash
sbatch tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/cpu_sweep.sbatch
sbatch tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/adaptive_focus.sbatch
sbatch tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/black_box_holdout.sbatch
sbatch tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/gpu_verify.sbatch
```

After the black-box holdout array finishes, combine task outputs from the
repository root. The combiner checks that all 48 expected shard files are
present before it writes aggregate outputs:

```bash
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_black_box_holdout.py \
  --out tracks/qcs/results/YueYuan/attempt-004/black_box_holdout_moderate \
  --combine-tasks
```

After the full CPU array finishes, combine its task outputs. The CPU script
uses `--exclude-adaptive` to reproduce the 1,656-record historical full-sweep
profile reported in `REPORT.md`. The combiner requires all 144 run, history,
and Hessian-spectrum shards before writing aggregate files:

```bash
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_full_sweep.py \
  --out tracks/qcs/results/YueYuan/attempt-004/full \
  --exclude-adaptive \
  --combine-tasks
```

After the adaptive-focus array finishes, require all 48 shards and the reported
600-record profile:

```bash
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_full_sweep.py \
  --out tracks/qcs/results/YueYuan/attempt-004/focus_adaptive \
  --adaptive-focus \
  --combine-tasks
```
