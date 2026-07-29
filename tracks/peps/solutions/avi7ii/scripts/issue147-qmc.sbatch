#!/usr/bin/env bash
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=02:00:00
set -euo pipefail
: "${HARNESS_RUN_SPEC:?HARNESS_RUN_SPEC is required}"
: "${SLURM_ARRAY_TASK_ID:?submit this script as an array}"
cd "$HOME/quantum.harness"
source .venv/bin/activate
export PYTHONPATH="$PWD/tracks/peps/solutions/avi7ii${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
printf '{"event":"start","cell":%s,"host":"%s","kind":"qmc"}\n' \
  "$SLURM_ARRAY_TASK_ID" "$(hostname)"
python -u tracks/peps/solutions/avi7ii/scripts/run_cell.py --kind qmc
