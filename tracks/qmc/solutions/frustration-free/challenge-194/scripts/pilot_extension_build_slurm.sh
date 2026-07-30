#!/bin/bash
#SBATCH --cpus-per-task=1
#SBATCH --mem=1800M
#SBATCH --time=00:10:00
set -euo pipefail

: "${HARNESS_RUN_SPEC:?Set HARNESS_RUN_SPEC to the exact canonical P0 analysis path}"
: "${HARNESS_ENTRYPOINT:?Set the exact deployed repository root}"
: "${HARNESS_COMMAND:?Set the exact offline Python executable}"
: "${SLURM_JOB_ID:?Run as a Slurm job}"
P0_ANALYSIS_PATH="${HARNESS_RUN_SPEC}"
CHALLENGE_194_REPO_ROOT="${HARNESS_ENTRYPOINT}"
CHALLENGE_194_PYTHON="${HARNESS_COMMAND}"

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

require_canonical_path HARNESS_RUN_SPEC "${P0_ANALYSIS_PATH}" file
require_canonical_path HARNESS_ENTRYPOINT "${CHALLENGE_194_REPO_ROOT}" directory
require_canonical_path HARNESS_COMMAND "${CHALLENGE_194_PYTHON}" executable
if [[ ! "${SLURM_JOB_ID}" =~ ^[0-9]+$ ]]; then
    echo "SLURM_JOB_ID must be numeric" >&2
    exit 64
fi
if [[ "${SLURM_CPUS_PER_TASK:-1}" != "1" ]]; then
    echo "Challenge 194 P0 extension construction requires exactly one CPU" >&2
    exit 64
fi

SOLUTION_RELATIVE="tracks/qmc/solutions/frustration-free/challenge-194"
SOLUTION_ROOT="${CHALLENGE_194_REPO_ROOT}/${SOLUTION_RELATIVE}"
if [[ ! -f "${SOLUTION_ROOT}/scripts/analyze_pilot.py" ||
      ! -f "${SOLUTION_ROOT}/scripts/run_pilot.py" ]]; then
    echo "Exact Challenge 194 solution path is invalid: ${SOLUTION_ROOT}" >&2
    exit 66
fi

RESULTS_ROOT="$(dirname "${P0_ANALYSIS_PATH}")"
EXTENSION_PROTOCOL_PATH="${RESULTS_ROOT}/p0_extension_v1_protocol.json"
VALIDATION_REPORT_PATH="${RESULTS_ROOT}/validation-prod-877ab93/report/report.json"
EXTENSION_ROOT="${RESULTS_ROOT}/pilot-p0-extension-v1"
require_canonical_path VALIDATION_REPORT_PATH "${VALIDATION_REPORT_PATH}" file

P0_ANALYSIS_SHA256="44083701db692304cd3aa054c8a9488b75674cead7cd6bf479c0a203cc1fa10b"
if [[ "$(sha256sum -- "${P0_ANALYSIS_PATH}" | awk '{print $1}')" != "${P0_ANALYSIS_SHA256}" ]]; then
    echo "P0 analysis SHA256 does not match the frozen canonical artifact" >&2
    exit 65
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
export NUMBA_CACHE_DIR="${NUMBA_CACHE_BASE%/}/challenge-194-p0-extension-build-${SLURM_JOB_ID}"
case "$(realpath -m -- "${NUMBA_CACHE_DIR}")" in
    "$(realpath -e -- "${NUMBA_CACHE_BASE}")"/*) ;;
    *)
        echo "NUMBA cache path escapes node-local temporary directory" >&2
        exit 73
        ;;
esac
umask 077
if ! mkdir -- "${NUMBA_CACHE_DIR}"; then
    echo "NUMBA cache directory must be uniquely created by this job" >&2
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
export PYTHONPATH="${SOLUTION_ROOT}/src"
"${CHALLENGE_194_PYTHON}" scripts/analyze_pilot.py build-p0-extension \
  --analysis "${P0_ANALYSIS_PATH}" \
  --output "${EXTENSION_PROTOCOL_PATH}"
"${CHALLENGE_194_PYTHON}" scripts/run_pilot.py build-extension-spec \
  --protocol "${EXTENSION_PROTOCOL_PATH}" \
  --validation-report "${VALIDATION_REPORT_PATH}" \
  --output-root "${EXTENSION_ROOT}" \
  --run-spec "${EXTENSION_ROOT}/run_spec.json"
