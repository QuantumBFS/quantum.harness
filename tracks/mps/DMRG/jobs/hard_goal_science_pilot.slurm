#!/bin/bash
#SBATCH --job-name=hg3d-stage6-science
#SBATCH --output=slurm-%A_%a.out

set -euo pipefail
umask 077

: "${HARNESS_RUN_SPEC:?Set HARNESS_RUN_SPEC to the immutable Stage 6 run spec}"
: "${HARNESS_TRACK_ROOT:?Set HARNESS_TRACK_ROOT to the DMRG track checkout}"
: "${HARNESS_PYTHON:?Set HARNESS_PYTHON to the environment Python}"
: "${HARNESS_REQUIRED_PLATFORM:?Set HARNESS_REQUIRED_PLATFORM to cpu or gpu}"

readonly SELECTOR="${SLURM_ARRAY_TASK_ID:-${HARNESS_CELL_SELECTOR:-}}"
[[ -n "$SELECTOR" ]] || { echo "missing Stage 6 cell selector" >&2; exit 2; }

command_args=(
  "$HARNESS_TRACK_ROOT/scripts/hard_goal_science_pilot_cell.py"
  --run-spec "$HARNESS_RUN_SPEC"
  --selector "$SELECTOR"
  --require-platform "$HARNESS_REQUIRED_PLATFORM"
  --checkpoint-every "${HARNESS_CHECKPOINT_EVERY:-256}"
  --measurement-cadence "${HARNESS_MEASUREMENT_CADENCE:-1}"
)
if [[ "${HG3D_RESUME:-0}" == "1" ]]; then
  command_args+=(--resume)
fi
if [[ "${HG3D_CALIBRATION_ONLY:-0}" == "1" ]]; then
  command_args+=(--calibration-only)
fi

exec "$HARNESS_PYTHON" -u "${command_args[@]}"
