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
python_pid=""

forward_signal() {
  local signal_name="$1"
  if [[ -n "${python_pid}" ]] && kill -0 "${python_pid}" 2>/dev/null; then
    kill "-${signal_name}" "${python_pid}"
  fi
}

trap 'forward_signal USR1' SIGUSR1
trap 'forward_signal TERM' SIGTERM

"${PYTHON}" "${SOLUTION_DIR}/convergence.py" run-cell \
  --plan "${HARNESS_RUN_SPEC}" \
  --run-directory "${HARNESS_RUN_DIR}" \
  --resources "${HARNESS_RESOURCES}" \
  --acknowledge-resources "${HARNESS_RESOURCE_ACK}" \
  --cell-index "${SLURM_ARRAY_TASK_ID}" \
  --execution-target cluster \
  --julia-project "${JULIA_PROJECT}" &
python_pid=$!

while true; do
  if wait "${python_pid}"; then
    status=0
    break
  else
    status=$?
    if kill -0 "${python_pid}" 2>/dev/null; then
      continue
    fi
    break
  fi
done
trap - SIGUSR1 SIGTERM
exit "${status}"
