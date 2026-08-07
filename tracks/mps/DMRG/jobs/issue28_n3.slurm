#!/bin/bash
#SBATCH --job-name=issue28-n3-pilot
#SBATCH --output=slurm-%A_%a.out

set -euo pipefail
: "${HARNESS_RUN_SPEC:?Set HARNESS_RUN_SPEC to the immutable N3 run spec}"
: "${SLURM_SUBMIT_DIR:?Slurm must provide SLURM_SUBMIT_DIR}"

if [[ "${HARNESS_SKIP_MODULES:-0}" != "1" ]]; then
  set +u
  source "${HARNESS_SYSTEM_PROFILE:-/etc/profile}"
  set -u
  module load compiler/intel/2017.5.239
  module load python/3.8.10
fi

REPO_ROOT="${HARNESS_REPO_ROOT:-$SLURM_SUBMIT_DIR}"
TRACK_ROOT="${HARNESS_TRACK_ROOT:-$REPO_ROOT/tracks/mps/DMRG}"
PYTHON="${HARNESS_PYTHON:-$HOME/quantum.harness/.venv-issue28/bin/python}"
[[ -x "$PYTHON" ]] || { echo "HARNESS_PYTHON is not executable: $PYTHON" >&2; exit 2; }
RUN_SPEC="$HARNESS_RUN_SPEC"
[[ "$RUN_SPEC" = /* ]] || RUN_SPEC="$REPO_ROOT/$RUN_SPEC"
SELECTOR="${SLURM_ARRAY_TASK_ID:-${HARNESS_CELL_INDEX:-1}}"

export HARNESS_REPO_ROOT="$REPO_ROOT"
export PYTHONHASHSEED=0
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export NUMBA_NUM_THREADS="$OMP_NUM_THREADS"
export NUMBA_CACHE_DIR="${HARNESS_CACHE_ROOT:-$HOME/scratch/issue28-cache}/numba"
export MPLCONFIGDIR="${HARNESS_CACHE_ROOT:-$HOME/scratch/issue28-cache}/matplotlib"
mkdir -p "$NUMBA_CACHE_DIR" "$MPLCONFIGDIR"
cd "$TRACK_ROOT"
exec "$PYTHON" -u scripts/issue28_cluster_cell.py \
  --stage N3 --run-spec "$RUN_SPEC" --selector "$SELECTOR"
