#!/bin/bash
#SBATCH --job-name=issue28-b0-formal
#SBATCH --output=slurm-%j.out

set -euo pipefail
: "${SLURM_SUBMIT_DIR:?Slurm must provide SLURM_SUBMIT_DIR}"

set +u
source "${HARNESS_SYSTEM_PROFILE:-/etc/profile}"
set -u
module load compiler/intel/2017.5.239
module load python/3.8.10

REPO_ROOT="${HARNESS_REPO_ROOT:-$SLURM_SUBMIT_DIR}"
TRACK_ROOT="$REPO_ROOT/tracks/mps/DMRG"
PYTHON="${HARNESS_PYTHON:-$HOME/quantum.harness/.venv-issue28/bin/python}"
[[ -x "$PYTHON" ]] || { echo "HARNESS_PYTHON is not executable: $PYTHON" >&2; exit 2; }

export PYTHONHASHSEED=0
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export NUMBA_NUM_THREADS="$OMP_NUM_THREADS"
export NUMBA_CACHE_DIR="${HARNESS_CACHE_ROOT:-$HOME/scratch/issue28-cache}/numba"
mkdir -p "$NUMBA_CACHE_DIR"

cd "$TRACK_ROOT"
exec "$PYTHON" -u scripts/issue28_baseline.py \
  --protocol config/issue28_easy_v1.json \
  --b0-config config/issue28_b0_v1.json \
  --preset formal \
  --output "$REPO_ROOT/results/issue28-b0-formal-hpc-20260729-01"
