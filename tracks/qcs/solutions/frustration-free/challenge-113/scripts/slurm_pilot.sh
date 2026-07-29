#!/usr/bin/env bash
#SBATCH --job-name=c113-p80-pilot
#SBATCH --account=chenkun2025
#SBATCH --qos=user_student090
#SBATCH --partition=ihicnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=12:00:00
set -euo pipefail

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_ROOT}/scripts/apptainer_job_gate.sh"

/usr/bin/time -v "${APPTAINER}" "${CONTAINER_ARGS[@]}" \
  /workspace/.venv/bin/python -u /workspace/run.py trial \
  --kind production --system two_qubit --segments 20 --gap 0.05 --shots exact \
  --perturbation-seed 0 --method model_hessian --dimension 4 \
  --model-seed 5 --seed 0 \
  --output /output/pilot
"${APPTAINER}" "${CONTAINER_ARGS[@]}" /workspace/.venv/bin/python -u \
  /workspace/run.py validate --output /output/pilot
