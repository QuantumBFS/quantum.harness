# Attempt 004 Slurm Notes

These scripts are intentionally conservative.

- CPU sweep: `--cpus-per-task=4` and `--array=0-143%25`, at most 100 CPU cores at one time.
- GPU verification: `--gres=gpu:1` and `--array=0-3%1`, at most one GPU at one time.
- Generated logs and JSONL files are written under `tracks/qcs/results/YueYuan/attempt-004/`, which is ignored by git.
- Do not add usernames, hostnames, credentials, SSH commands, or private keys to these files.

Submit from the repository root after local tests pass:

```bash
sbatch tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/cpu_sweep.sbatch
sbatch tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/gpu_verify.sbatch
```
