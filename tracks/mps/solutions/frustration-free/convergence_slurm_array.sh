#!/usr/bin/env bash
set -euo pipefail
umask 077

: "${HARNESS_RUN_SPEC:?set HARNESS_RUN_SPEC to the convergence plan JSON}"
: "${HARNESS_RUN_DIR:?set HARNESS_RUN_DIR to the result directory}"
: "${HARNESS_RESOURCES:?set HARNESS_RESOURCES to the plan-bound resources JSON}"
: "${HARNESS_RESOURCE_ACK:?set HARNESS_RESOURCE_ACK to resources resource_sha256}"
: "${HARNESS_SOLUTION_DIR:?set HARNESS_SOLUTION_DIR to the deployed solution directory}"
: "${SLURM_ARRAY_TASK_ID:?submit this wrapper as a zero-based Slurm array}"
: "${JULIA_PROJECT:?set JULIA_PROJECT to the runtime Julia project directory}"

SOLUTION_DIR="$(cd -- "${HARNESS_SOLUTION_DIR}" && pwd)"
PYTHON="${PYTHON:-python3}"

exec "${PYTHON}" "${SOLUTION_DIR}/convergence.py" run-cell \
  --plan "${HARNESS_RUN_SPEC}" \
  --run-directory "${HARNESS_RUN_DIR}" \
  --resources "${HARNESS_RESOURCES}" \
  --acknowledge-resources "${HARNESS_RESOURCE_ACK}" \
  --cell-index "${SLURM_ARRAY_TASK_ID}" \
  --execution-target cluster \
  --julia-project "${JULIA_PROJECT}"
