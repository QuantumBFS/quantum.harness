#!/bin/bash
#SBATCH --job-name=yueyuan-a004-gpu
#SBATCH --output=tracks/qcs/results/YueYuan/attempt-004/logs/gpu_%A_%a.out
#SBATCH --error=tracks/qcs/results/YueYuan/attempt-004/logs/gpu_%A_%a.err
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --gres=gpu:1
#SBATCH --array=0-3%1

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"
mkdir -p tracks/qcs/results/YueYuan/attempt-004/gpu tracks/qcs/results/YueYuan/attempt-004/logs

python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_full_sweep.py \
  --out tracks/qcs/results/YueYuan/attempt-004/gpu \
  --task-index "${SLURM_ARRAY_TASK_ID}"
