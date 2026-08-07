#!/bin/bash
#SBATCH --job-name=challenge28-mps-scan
#SBATCH --partition=qdagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=4G
#SBATCH --time=04:00:00
#SBATCH --gres=gpu:A800:1
#SBATCH --output=slurm-scan-%A_%a.out
#SBATCH --error=slurm-scan-%A_%a.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
: "${HARNESS_RUN_SPEC:?HARNESS_RUN_SPEC is required}"
: "${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export NUMBA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export NUMBA_CACHE_DIR="$PWD/.numba-cache"
export MPLCONFIGDIR="$PWD/.matplotlib"
mkdir -p "$NUMBA_CACHE_DIR" "$MPLCONFIGDIR" results/challenge28-mps-formal
PYTHON="${HARNESS_PYTHON:-$HOME/quantum.harness/.venv/bin/python}"
"$PYTHON" scripts/run_scan_cell.py \
  --run-spec "$HARNESS_RUN_SPEC" \
  --array-index "$SLURM_ARRAY_TASK_ID" \
  --output-root results/challenge28-mps-formal
