#!/bin/bash
#SBATCH --job-name=hg3d-stage7
#SBATCH --output=slurm-%A_%a.out

set -euo pipefail
umask 077

: "${HARNESS_RUN_SPEC:?Set HARNESS_RUN_SPEC to the immutable Stage 7 run spec}"
: "${HARNESS_APPROVED_RUN_SPEC_SHA256:?Set the explicitly approved run-spec SHA-256}"
: "${SLURM_ARRAY_TASK_ID:?Slurm must provide SLURM_ARRAY_TASK_ID}"
: "${HARNESS_PYTHON:?The active cluster profile must provide HARNESS_PYTHON}"

if [[ ! "$HARNESS_APPROVED_RUN_SPEC_SHA256" =~ ^[0-9a-f]{64}$ ]]; then
  echo "invalid approved run-spec SHA-256" >&2
  exit 2
fi
actual_run_spec_sha256="$(sha256sum -- "$HARNESS_RUN_SPEC" | awk '{print $1}')"
if [[ "$actual_run_spec_sha256" != "$HARNESS_APPROVED_RUN_SPEC_SHA256" ]]; then
  echo "approved run-spec SHA-256 does not match HARNESS_RUN_SPEC" >&2
  exit 2
fi

command_args=(
  -u
  scripts/hard_goal.py
  cell
  --run-spec "$HARNESS_RUN_SPEC"
  --selector "$SLURM_ARRAY_TASK_ID"
  --approved-run-spec-sha256 "$HARNESS_APPROVED_RUN_SPEC_SHA256"
)
if [[ "${HARNESS_RESUME:-0}" == "1" ]]; then
  command_args+=(--resume)
fi

exec "$HARNESS_PYTHON" "${command_args[@]}"
