#!/usr/bin/env bash
#SBATCH --cpus-per-task=32
#SBATCH --mem=128G
#SBATCH --time=06:00:00
set -euo pipefail
cd "$HOME/quantum.harness"
source .venv/bin/activate
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export OPENBLAS_NUM_THREADS="$SLURM_CPUS_PER_TASK"
: "${SLURM_ARRAY_TASK_ID:?submit this script with --array or set a task id}"
printf '{"event":"start","cell":%s,"host":"%s"}\n' \
  "$SLURM_ARRAY_TASK_ID" \
  "$(hostname)"
python -u -m qh147.run_ed \
  --config tracks/peps/solutions/avi7ii/configs/ed-4x4.json \
  --run-root tracks/peps/results/issue147-ed
