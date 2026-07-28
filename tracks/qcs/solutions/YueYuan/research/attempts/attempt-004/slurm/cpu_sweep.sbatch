#!/bin/bash
#SBATCH --job-name=yueyuan-a004-cpu
#SBATCH --output=tracks/qcs/results/YueYuan/attempt-004/logs/cpu_%A_%a.out
#SBATCH --error=tracks/qcs/results/YueYuan/attempt-004/logs/cpu_%A_%a.err
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --array=0-143%25

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"
mkdir -p tracks/qcs/results/YueYuan/attempt-004/full tracks/qcs/results/YueYuan/attempt-004/logs

export XLA_FLAGS="--xla_force_host_platform_device_count=${SLURM_CPUS_PER_TASK:-4}"
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_full_sweep.py \
  --out tracks/qcs/results/YueYuan/attempt-004/full \
  --task-index "${SLURM_ARRAY_TASK_ID}"
