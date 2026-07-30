#!/bin/bash
#SBATCH --job-name=challenge28-mps-smoke
#SBATCH --partition=qdagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --gres=gpu:A800:1
#SBATCH --output=slurm-smoke-%j.out
#SBATCH --error=slurm-smoke-%j.err

set -euo pipefail

cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export NUMBA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export NUMBA_CACHE_DIR="$PWD/.numba-cache"
export MPLCONFIGDIR="$PWD/.matplotlib"
mkdir -p "$NUMBA_CACHE_DIR" "$MPLCONFIGDIR" results/challenge28-mps-smoke

PYTHON="${HARNESS_PYTHON:-$HOME/quantum.harness/.venv/bin/python}"
"$PYTHON" scripts/run_smoke.py \
  --config config/mps_smoke.toml \
  --output results/challenge28-mps-smoke/seed-20260801
test -f results/challenge28-mps-smoke/seed-20260801/summary.json
