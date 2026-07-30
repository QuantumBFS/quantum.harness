#!/bin/bash
#SBATCH --cpus-per-task=1
#SBATCH --mem=1800M
#SBATCH --time=00:40:00
set -euo pipefail

: "${HARNESS_RUN_SPEC:?Set HARNESS_RUN_SPEC to the immutable extension run_spec.json}"
: "${SLURM_ARRAY_TASK_ID:?Run as a Slurm array task}"
: "${HARNESS_ENTRYPOINT:?Set the exact deployed repository root}"
: "${HARNESS_COMMAND:?Set the exact offline Python executable}"
CHALLENGE_194_REPO_ROOT="${HARNESS_ENTRYPOINT}"
CHALLENGE_194_PYTHON="${HARNESS_COMMAND}"
if [[ ! "${SLURM_ARRAY_TASK_ID}" =~ ^[0-9]+$ ]] ||
   (( SLURM_ARRAY_TASK_ID < 1 || SLURM_ARRAY_TASK_ID > 96 )); then
    exit 64
fi
CELL_INDEX=$((SLURM_ARRAY_TASK_ID - 1))

if [[ "${SLURM_CPUS_PER_TASK:-1}" != "1" ]]; then
    echo "Challenge 194 P0 extension cells require exactly one CPU" >&2
    exit 64
fi
for job_id_name in SLURM_ARRAY_JOB_ID SLURM_JOB_ID; do
    if [[ -n "${!job_id_name:-}" && ! "${!job_id_name}" =~ ^[0-9]+$ ]]; then
        echo "${job_id_name} must be numeric" >&2
        exit 64
    fi
done

require_canonical_path() {
    local label="$1"
    local candidate="$2"
    local kind="$3"
    local canonical=""
    local resolved=""
    if [[ "${candidate}" != /* ]]; then
        echo "${label} must be an absolute path" >&2
        return 66
    fi
    canonical="$(realpath -s -- "${candidate}")" || return 66
    resolved="$(realpath -e -- "${candidate}")" || return 66
    if [[ "${candidate}" != "${canonical}" || "${canonical}" != "${resolved}" ]]; then
        echo "${label} must be canonical and contain no symlink components" >&2
        return 66
    fi
    if [[ "${kind}" == "directory" && ! -d "${resolved}" ]] ||
       [[ "${kind}" == "file" && ! -f "${resolved}" ]] ||
       [[ "${kind}" == "executable" && ( ! -f "${resolved}" || ! -x "${resolved}" ) ]]; then
        echo "${label} has the wrong path type" >&2
        return 66
    fi
}

require_canonical_path HARNESS_RUN_SPEC "${HARNESS_RUN_SPEC}" file
require_canonical_path HARNESS_ENTRYPOINT "${CHALLENGE_194_REPO_ROOT}" directory
require_canonical_path HARNESS_COMMAND "${CHALLENGE_194_PYTHON}" executable

SOLUTION_RELATIVE="tracks/qmc/solutions/frustration-free/challenge-194"
SOLUTION_ROOT="${CHALLENGE_194_REPO_ROOT}/${SOLUTION_RELATIVE}"
if [[ ! -f "${SOLUTION_ROOT}/scripts/run_pilot.py" ]]; then
    echo "Exact Challenge 194 solution path is invalid: ${SOLUTION_ROOT}" >&2
    exit 66
fi

# Eliminate inherited compiler/runtime controls before pinning the approved set.
while IFS= read -r variable; do
    unset "${variable}"
done < <(compgen -A variable NUMBA_)
unset PYTHONHOME PYTHONUSERBASE PYTHONPATH PYTHONSTARTUP PYTHONINSPECT \
    PYTHONWARNINGS PYTHONBREAKPOINT PYTHONSAFEPATH \
    LD_PRELOAD LD_LIBRARY_PATH LD_AUDIT LIBRARY_PATH

export NUMBA_DISABLE_JIT=0
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export NUMBA_NUM_THREADS=1
export PYTHONHASHSEED=0
export PYTHONUNBUFFERED=1
export PYTHONNOUSERSITE=1

NUMBA_CACHE_BASE="${SLURM_TMPDIR:-${TMPDIR:-/tmp}}"
if [[ "${NUMBA_CACHE_BASE}" != /* || -L "${NUMBA_CACHE_BASE}" || \
      ! -d "${NUMBA_CACHE_BASE}" || ! -w "${NUMBA_CACHE_BASE}" ]]; then
    echo "node-local temporary directory must be an absolute writable directory" >&2
    exit 73
fi
if [[ "$(realpath -s -- "${NUMBA_CACHE_BASE}")" != "$(realpath -e -- "${NUMBA_CACHE_BASE}")" ]]; then
    echo "node-local temporary directory must not contain symlink components" >&2
    exit 73
fi
NUMBA_CACHE_JOB_ID="${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID:-no-job-id}}"
if [[ "${NUMBA_CACHE_JOB_ID}" == "no-job-id" ]]; then
    echo "SLURM_ARRAY_JOB_ID or SLURM_JOB_ID is required" >&2
    exit 64
fi
export NUMBA_CACHE_DIR="${NUMBA_CACHE_BASE%/}/challenge-194-p0-extension-${NUMBA_CACHE_JOB_ID}-${SLURM_ARRAY_TASK_ID}"
case "$(realpath -m -- "${NUMBA_CACHE_DIR}")" in
    "$(realpath -e -- "${NUMBA_CACHE_BASE}")"/*) ;;
    *)
        echo "NUMBA cache path escapes node-local temporary directory" >&2
        exit 73
        ;;
esac
umask 077
if ! mkdir -- "${NUMBA_CACHE_DIR}"; then
    echo "NUMBA cache directory must be uniquely created by this task" >&2
    exit 73
fi
if [[ -L "${NUMBA_CACHE_DIR}" || ! -d "${NUMBA_CACHE_DIR}" || \
      ! -O "${NUMBA_CACHE_DIR}" || ! -w "${NUMBA_CACHE_DIR}" || \
      "$(realpath -e -- "${NUMBA_CACHE_DIR}")" != "${NUMBA_CACHE_DIR}" ]]; then
    echo "NUMBA cache directory is not a safe writable directory" >&2
    exit 73
fi
shopt -s nullglob dotglob
CACHE_ENTRIES=("${NUMBA_CACHE_DIR}"/*)
shopt -u nullglob dotglob
if (( ${#CACHE_ENTRIES[@]} != 0 )); then
    echo "new NUMBA cache directory is unexpectedly non-empty" >&2
    exit 73
fi

cd "${SOLUTION_ROOT}"
echo "P0 extension array task=${SLURM_ARRAY_TASK_ID} cell=${CELL_INDEX} host=$(hostname)"
echo "run_spec=${HARNESS_RUN_SPEC}"
export PYTHONPATH="${SOLUTION_ROOT}/src"
exec "${CHALLENGE_194_PYTHON}" scripts/run_pilot.py run-cell \
    --run-spec "${HARNESS_RUN_SPEC}" \
    --cell-index "${CELL_INDEX}"
