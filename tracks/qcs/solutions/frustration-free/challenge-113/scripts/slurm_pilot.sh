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

: "${CHALLENGE113_DEPLOYMENT:?set absolute canonical deployment directory}"
CANONICAL_DEPLOYMENT="$(realpath -e -- "${CHALLENGE113_DEPLOYMENT}")"
if [[ "${CHALLENGE113_DEPLOYMENT}" != "${CANONICAL_DEPLOYMENT}" ]]; then
  echo "CHALLENGE113_DEPLOYMENT must be an absolute canonical directory" >&2
  exit 2
fi
GATE="${CANONICAL_DEPLOYMENT}/scripts/apptainer_job_gate.sh"
if [[ ! -f "${GATE}" || -L "${GATE}" ]]; then
  echo "deployment job gate must be a regular non-symlink file" >&2
  exit 2
fi
source "${GATE}"

/usr/bin/time -v "${APPTAINER}" "${CONTAINER_ARGS[@]}" \
  /workspace/.venv/bin/python -u /workspace/run.py trial \
  --kind production --system two_qubit --segments 20 --gap 0.05 --shots exact \
  --perturbation-seed 0 --method model_hessian --dimension 4 \
  --model-seed 5 --seed 0 \
  --output /output/pilot
"${APPTAINER}" "${CONTAINER_ARGS[@]}" /workspace/.venv/bin/python -u \
  /workspace/run.py validate --output /output/pilot
