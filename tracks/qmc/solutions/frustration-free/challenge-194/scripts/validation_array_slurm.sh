#!/bin/bash
set -euo pipefail

: "${HARNESS_RUN_SPEC:?Set HARNESS_RUN_SPEC to the immutable run_spec.json}"
: "${SLURM_ARRAY_TASK_ID:?Run as a Slurm array task}"

REPO_ROOT="${CHALLENGE_194_REPO_ROOT:-${HARNESS_ENTRYPOINT:-}}"
: "${REPO_ROOT:?Set CHALLENGE_194_REPO_ROOT or the harness entrypoint to the explicit shared repository path}"

if [[ "${SLURM_CPUS_PER_TASK:-1}" != "1" ]]; then
    echo "Challenge 194 validation cells require exactly one CPU" >&2
    exit 64
fi
if [[ ! "${SLURM_ARRAY_TASK_ID}" =~ ^[0-9]+$ ]]; then
    echo "SLURM_ARRAY_TASK_ID must be a nonnegative integer" >&2
    exit 64
fi

SOLUTION_RELATIVE="tracks/qmc/solutions/frustration-free/challenge-194"
SOLUTION_ROOT="${REPO_ROOT%/}/${SOLUTION_RELATIVE}"
if [[ ! -f "${SOLUTION_ROOT}/scripts/validation_shard.py" ]]; then
    echo "Explicit Challenge 194 solution path is invalid: ${SOLUTION_ROOT}" >&2
    exit 66
fi
if [[ ! -f "${HARNESS_RUN_SPEC}" ]]; then
    echo "HARNESS_RUN_SPEC is not a regular file: ${HARNESS_RUN_SPEC}" >&2
    exit 66
fi

OFFLINE_PYTHON=""
if [[ "${CHALLENGE_194_PYTHON+x}" == "x" ]]; then
    if [[ "${CHALLENGE_194_PYTHON}" != /* ]]; then
        echo "CHALLENGE_194_PYTHON must be an absolute path" >&2
        exit 66
    fi
    if ! OFFLINE_PYTHON="$(realpath -e -- "${CHALLENGE_194_PYTHON}" 2>/dev/null)"; then
        echo "CHALLENGE_194_PYTHON does not resolve to an existing path" >&2
        exit 66
    fi
    if [[ "${OFFLINE_PYTHON}" != /* || ! -f "${OFFLINE_PYTHON}" || ! -x "${OFFLINE_PYTHON}" ]]; then
        echo "CHALLENGE_194_PYTHON must resolve to a regular executable" >&2
        exit 66
    fi
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
if [[ -n "${OFFLINE_PYTHON}" ]]; then
    export PYTHONPATH="${SOLUTION_ROOT}/src"
    exec "${OFFLINE_PYTHON}" scripts/validation_shard.py run-cell \
        --run-spec "${HARNESS_RUN_SPEC}" \
        --case-index "${SLURM_ARRAY_TASK_ID}"
fi
exec uv run scripts/validation_shard.py run-cell \
    --run-spec "${HARNESS_RUN_SPEC}" \
    --case-index "${SLURM_ARRAY_TASK_ID}"
