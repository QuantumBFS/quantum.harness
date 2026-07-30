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

resolve_python_candidate() {
    local label="$1"
    local candidate="$2"
    local canonical=""
    local resolved=""
    if [[ "${candidate}" != /* ]]; then
        echo "${label} must be an absolute path" >&2
        return 66
    fi
    if ! canonical="$(realpath -s -- "${candidate}" 2>/dev/null)"; then
        echo "${label} is not a valid absolute path" >&2
        return 66
    fi
    if ! resolved="$(realpath -e -- "${candidate}" 2>/dev/null)"; then
        echo "${label} does not resolve to an existing path" >&2
        return 66
    fi
    if [[ "${resolved}" != /* || ! -f "${resolved}" || ! -x "${resolved}" ]]; then
        echo "${label} must resolve to a regular executable" >&2
        return 66
    fi
    printf '%s\n' "${canonical}"
}

CHALLENGE_PYTHON=""
HARNESS_PYTHON=""
if [[ "${CHALLENGE_194_PYTHON+x}" == "x" ]]; then
    CHALLENGE_PYTHON="$(
        resolve_python_candidate CHALLENGE_194_PYTHON "${CHALLENGE_194_PYTHON}"
    )" || exit $?
fi
if [[ "${HARNESS_COMMAND+x}" == "x" ]]; then
    HARNESS_PYTHON="$(
        resolve_python_candidate HARNESS_COMMAND "${HARNESS_COMMAND}"
    )" || exit $?
fi
if [[ -n "${CHALLENGE_PYTHON}" && -n "${HARNESS_PYTHON}" && "${CHALLENGE_PYTHON}" != "${HARNESS_PYTHON}" ]]; then
    echo "interpreter conflict: CHALLENGE_194_PYTHON and HARNESS_COMMAND resolve differently" >&2
    exit 66
fi
OFFLINE_PYTHON="${CHALLENGE_PYTHON:-${HARNESS_PYTHON}}"

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export PYTHONUNBUFFERED=1

NUMBA_CACHE_BASE="${SLURM_TMPDIR:-${TMPDIR:-/tmp}}"
if [[ "${NUMBA_CACHE_BASE}" != /* || ! -d "${NUMBA_CACHE_BASE}" || ! -w "${NUMBA_CACHE_BASE}" ]]; then
    echo "node-local temporary directory must be an absolute writable directory" >&2
    exit 73
fi
NUMBA_CACHE_JOB_ID="${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID:-no-job-id}}"
export NUMBA_CACHE_DIR="${NUMBA_CACHE_BASE%/}/challenge-194-numba-${NUMBA_CACHE_JOB_ID}-${SLURM_ARRAY_TASK_ID}"
mkdir -p -- "${NUMBA_CACHE_DIR}"

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
