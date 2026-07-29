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

"${APPTAINER}" "${CONTAINER_ARGS[@]}" /workspace/.venv/bin/python -u \
  /workspace/run.py sweep \
  --kind production \
  --shard-index "${SLURM_ARRAY_TASK_ID}" \
  --shard-count 9500 \
  --output /output/production
