#!/usr/bin/env bash
#SBATCH --partition=xhacnormalb
#SBATCH --account=giggleliu
#SBATCH --nodes=1
#SBATCH --ntasks=1

set -euo pipefail
unset LC_ALL
export LANG=C

: "${KH_JOB_ID:?KH_JOB_ID must name one registered convergence job}"

source /usr/share/Modules/init/bash
module purge
module load anaconda3/2023.09

ROOT=/work/share/giggleliu/cfys01/kharkov_burgers_20260729
SOURCE="$ROOT/source"
PYTHON="$ROOT/env/tenpy-py311/bin/python"
OUTPUT="$ROOT/data/convergence/${KH_JOB_ID}.npz"
CHECKPOINT="${OUTPUT}.checkpoint.h5"

export PYTHONNOUSERSITE=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export NUMEXPR_NUM_THREADS="${SLURM_CPUS_PER_TASK}"

mkdir -p "$ROOT/data/convergence" "$ROOT/logs"
cd "$SOURCE"

"$PYTHON" hpc/scnet/check_convergence_source.py \
  --job-id "$KH_JOB_ID" \
  --submission "$ROOT/jobs/convergence_submission.json" \
  --manifest "$SOURCE/results_research_program/manifest.json" \
  --amendment "$SOURCE/results_research_program/hpc/convergence_source_20260729/amendment.json" \
  --runner "$SOURCE/scripts/run_tenpy_research_job.py" \
  --backend "$SOURCE/src/tenpy_research_backend.py"

RUN_ARGS=(
  scripts/run_tenpy_research_job.py
  --manifest "$SOURCE/results_research_program/manifest.json"
  --job-id "$KH_JOB_ID"
  --output "$OUTPUT"
  --checkpoint-every 10
)
if [[ -s "$CHECKPOINT" ]]; then
  RUN_ARGS+=(--resume)
fi

/usr/bin/time -v "$PYTHON" "${RUN_ARGS[@]}"
