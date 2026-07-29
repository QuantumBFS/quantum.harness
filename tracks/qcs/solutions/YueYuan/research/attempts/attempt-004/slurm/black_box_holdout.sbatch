#!/bin/bash
#SBATCH --job-name=yueyuan-a004-bbox
#SBATCH --output=tracks/qcs/results/YueYuan/attempt-004/logs/black_box_holdout_%A_%a.out
#SBATCH --error=tracks/qcs/results/YueYuan/attempt-004/logs/black_box_holdout_%A_%a.err
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --array=0-47%8

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"
mkdir -p tracks/qcs/results/YueYuan/attempt-004/black_box_holdout_moderate/tasks
mkdir -p tracks/qcs/results/YueYuan/attempt-004/logs

if [ -f "$HOME/.venvs/quantum-harness-a004/bin/activate" ]; then
  . "$HOME/.venvs/quantum-harness-a004/bin/activate"
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
export XLA_FLAGS="--xla_force_host_platform_device_count=${SLURM_CPUS_PER_TASK:-4}"
"$PYTHON_BIN" tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_black_box_holdout.py \
  --out tracks/qcs/results/YueYuan/attempt-004/black_box_holdout_moderate \
  --task-index "${SLURM_ARRAY_TASK_ID}"
