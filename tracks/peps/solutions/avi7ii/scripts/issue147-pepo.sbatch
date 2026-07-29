#!/usr/bin/env bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --gres=gpu:A800:1
#SBATCH --time=12:00:00
set -euo pipefail
: "${HARNESS_RUN_SPEC:?HARNESS_RUN_SPEC is required}"
: "${SLURM_ARRAY_TASK_ID:?submit this script as an array}"
cd "$HOME/quantum.harness"
source .venv/bin/activate
export PYTHONPATH="$PWD/tracks/peps/solutions/avi7ii${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export OPENBLAS_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export JAX_PLATFORM_NAME=gpu
export HARNESS_KIND="${HARNESS_KIND:-pepo}"
printf '{"event":"start","cell":%s,"host":"%s","kind":"%s"}\n' \
  "$SLURM_ARRAY_TASK_ID" "$(hostname)" "$HARNESS_KIND"
python -u tracks/peps/solutions/avi7ii/scripts/run_cell.py --kind "$HARNESS_KIND"
