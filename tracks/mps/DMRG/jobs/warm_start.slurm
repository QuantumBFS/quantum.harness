#!/bin/bash
#SBATCH --job-name=challenge28-warm-start
#SBATCH --partition=qdagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=4G
#SBATCH --time=04:00:00
#SBATCH --gres=gpu:A800:1
#SBATCH --output=slurm-warm-%j.out
#SBATCH --error=slurm-warm-%j.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
: "${LEVEL1_CHECKPOINT:?LEVEL1_CHECKPOINT is required}"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export NUMBA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export NUMBA_CACHE_DIR="$PWD/.numba-cache"
mkdir -p "$NUMBA_CACHE_DIR" results/challenge28-warm-start
PYTHON="${HARNESS_PYTHON:-$HOME/quantum.harness/.venv/bin/python}"
"$PYTHON" scripts/run_rg_warm_start.py \
  --config config/mps_warm_start.toml \
  --level1-checkpoint "$LEVEL1_CHECKPOINT" \
  --output results/challenge28-warm-start/seed-20260801 \
  --seed 20260801
