#!/bin/bash
#SBATCH --job-name=challenge28-baseline
#SBATCH --partition=qdagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=4G
#SBATCH --time=02:00:00
#SBATCH --gres=gpu:A800:1
#SBATCH --output=slurm-baseline-%j.out
#SBATCH --error=slurm-baseline-%j.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export NUMBA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export NUMBA_CACHE_DIR="$PWD/.numba-cache"
mkdir -p "$NUMBA_CACHE_DIR" results/challenge28-baseline
PYTHON="${HARNESS_PYTHON:-$HOME/quantum.harness/.venv/bin/python}"
"$PYTHON" scripts/run_baseline.py \
  --config config/mps_baseline_45x45.toml \
  --seed 20260801 \
  --output results/challenge28-baseline/seed-20260801
test -f results/challenge28-baseline/seed-20260801/baseline.json
