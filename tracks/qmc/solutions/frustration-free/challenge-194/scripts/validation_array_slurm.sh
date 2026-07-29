#!/bin/bash
set -euo pipefail

: "${HARNESS_RUN_SPEC:?Set HARNESS_RUN_SPEC to the immutable run_spec.json}"
: "${SLURM_ARRAY_TASK_ID:?Run as a Slurm array task}"
: "${CHALLENGE_194_REPO_ROOT:?Set the explicit shared repository path}"

if [[ "${SLURM_CPUS_PER_TASK:-1}" != "1" ]]; then
    echo "Challenge 194 validation cells require exactly one CPU" >&2
    exit 64
fi
if [[ ! "${SLURM_ARRAY_TASK_ID}" =~ ^[0-9]+$ ]]; then
    echo "SLURM_ARRAY_TASK_ID must be a nonnegative integer" >&2
    exit 64
fi

SOLUTION_RELATIVE="tracks/qmc/solutions/frustration-free/challenge-194"
SOLUTION_ROOT="${CHALLENGE_194_REPO_ROOT%/}/${SOLUTION_RELATIVE}"
if [[ ! -f "${SOLUTION_ROOT}/scripts/validation_shard.py" ]]; then
    echo "Explicit Challenge 194 solution path is invalid: ${SOLUTION_ROOT}" >&2
    exit 66
fi
if [[ ! -f "${HARNESS_RUN_SPEC}" ]]; then
    echo "HARNESS_RUN_SPEC is not a regular file: ${HARNESS_RUN_SPEC}" >&2
    exit 66
fi

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export PYTHONUNBUFFERED=1

cd "${SOLUTION_ROOT}"
echo "validation array cell=${SLURM_ARRAY_TASK_ID} host=$(hostname)" 
echo "run_spec=${HARNESS_RUN_SPEC}"
exec uv run scripts/validation_shard.py run-cell \
    --run-spec "${HARNESS_RUN_SPEC}" \
    --case-index "${SLURM_ARRAY_TASK_ID}"
