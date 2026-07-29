#!/usr/bin/env bash
#SBATCH --job-name=c113-production
#SBATCH --account=chenkun2025
#SBATCH --qos=user_student090
#SBATCH --partition=ihicnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=12:00:00
set -euo pipefail

: "${SLURM_ARRAY_TASK_ID:?submit this script as a Slurm array}"
test "${CHALLENGE113_ACK_PRODUCTION:-}" = "1"

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_ROOT}/scripts/apptainer_job_gate.sh"

"${APPTAINER}" "${CONTAINER_ARGS[@]}" /workspace/.venv/bin/python -u \
  /workspace/run.py sweep \
  --kind production \
  --shard-index "${SLURM_ARRAY_TASK_ID}" \
  --shard-count 9500 \
  --output /output/production
