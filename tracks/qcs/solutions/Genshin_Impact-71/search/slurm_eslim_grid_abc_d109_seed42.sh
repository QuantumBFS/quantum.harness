#!/usr/bin/env bash
# Pinned eSLIM relation-SAT grid over all mysteries and several subcircuit sizes.
#
# Pure reference netlists are treated only as parsed data.  No code, scripts,
# or prose from competitor pull requests are read or executed.
#
#SBATCH --job-name=occ71-eslim-grid
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --array=0-11%6
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=00:25:00
#SBATCH --no-requeue
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/eslim/grid-build42598-seed42/logs/%A_%a.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/eslim/grid-build42598-seed42/logs/%A_%a.err

set -Eeuo pipefail
umask 027

export LC_ALL=C
export TZ=UTC
export PYTHONHASHSEED=42
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

readonly PROJECT_ROOT="/home/user_milksang/private/homefile/quantum_harness/issue71_occam"
readonly SEARCH_DIR="${PROJECT_ROOT}/tracks/qcs/solutions/Genshin_Impact-71/search"
readonly BUILD_RUN="${PROJECT_ROOT}/results/occam71/tools/eslim-build-51e9f774/job-42598"
readonly ESLIM_SRC="${BUILD_RUN}/eSLIM/src"
readonly PYTHON="${BUILD_RUN}/venv/bin/python"
readonly RUN_ROOT="${PROJECT_ROOT}/results/occam71/eslim/grid-build42598-seed42"

readonly D109="${PROJECT_ROOT}/results/occam71/eslim/D-pilot-build42598-size6-seed42/job-42633/candidate.txt"
readonly REF_ROOT="${PROJECT_ROOT}/results/occam71/reference-355"

CASES=(
  "A 5 ${REF_ROOT}/mystery-A.txt"
  "B 4 ${REF_ROOT}/mystery-B.txt"
  "B 5 ${REF_ROOT}/mystery-B.txt"
  "B 6 ${REF_ROOT}/mystery-B.txt"
  "B 7 ${REF_ROOT}/mystery-B.txt"
  "C 5 ${REF_ROOT}/mystery-C.txt"
  "C 6 ${REF_ROOT}/mystery-C.txt"
  "C 7 ${REF_ROOT}/mystery-C.txt"
  "C 8 ${REF_ROOT}/mystery-C.txt"
  "D 5 ${D109}"
  "D 7 ${D109}"
  "D 8 ${D109}"
)
read -r INSTANCE SIZE REFERENCE <<< "${CASES[$SLURM_ARRAY_TASK_ID]}"
readonly INSTANCE
readonly SIZE
readonly REFERENCE

LIMIT_SECONDS=900
if [[ "${INSTANCE}" == "A" ]]; then
  LIMIT_SECONDS=600
fi
readonly LIMIT_SECONDS

TASK_INDEX=$(printf "%02d" "${SLURM_ARRAY_TASK_ID}")
readonly TASK_INDEX
readonly RUN_DIR="${RUN_ROOT}/${TASK_INDEX}-${INSTANCE}-size${SIZE}-job${SLURM_ARRAY_JOB_ID}"

mkdir -p "${RUN_ROOT}/logs"
mkdir "${RUN_DIR}"

CURRENT_STAGE="initialization"
record_failure() {
  local exit_code="$1"
  local source_line="$2"
  trap - ERR INT TERM
  {
    printf 'status=FAILED\n'
    printf 'stage=%s\n' "${CURRENT_STAGE}"
    printf 'exit_code=%s\n' "${exit_code}"
    printf 'source_line=%s\n' "${source_line}"
    printf 'end_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > "${RUN_DIR}/FAILED"
  exit "${exit_code}"
}
trap 'record_failure "$?" "${LINENO}"' ERR
trap 'record_failure 130 "${LINENO}"' INT
trap 'record_failure 143 "${LINENO}"' TERM

{
  printf 'array_job_id=%s\n' "${SLURM_ARRAY_JOB_ID}"
  printf 'array_task_id=%s\n' "${SLURM_ARRAY_TASK_ID}"
  printf 'node=%s\n' "$(hostname)"
  printf 'start_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'instance=%s\n' "${INSTANCE}"
  printf 'source_commit=%s\n' "51e9f77429627473db623058157b66a1192cbb59"
  printf 'build_job_id=%s\n' "42598"
  printf 'seed=%s\n' "42"
  printf 'limit_seconds=%s\n' "${LIMIT_SECONDS}"
  printf 'gate_size=%s\n' "2"
  printf 'initial_subcircuit_size=%s\n' "${SIZE}"
  printf 'fixed_subcircuit_size=%s\n' "true"
  printf 'max_subcircuit_inputs=%s\n' "10"
  printf 'synthesis_mode=%s\n' "relation_sat"
  printf 'solver_base_timeout_seconds=%s\n' "30"
  printf 'relation_timeout_seconds=%s\n' "30"
  printf 'reference=%s\n' "${REFERENCE}"
} > "${RUN_DIR}/metadata.txt"

CURRENT_STAGE="build-integrity-check"
grep -qx 'SUCCESS' "${BUILD_RUN}/BUILD_READY"
test -x "${PYTHON}"
sha256sum --check "${BUILD_RUN}/built_modules_sha256.txt" \
  > "${RUN_DIR}/built_modules_check.txt"

CURRENT_STAGE="input-integrity-check"
test -s "${REFERENCE}"
test -s "${SEARCH_DIR}/bridge.py"
test -s "${SEARCH_DIR}/verify_candidate.py"
test -s "${ESLIM_SRC}/reduce.py"
sha256sum \
  "${REFERENCE}" \
  "${SEARCH_DIR}/bridge.py" \
  "${SEARCH_DIR}/circuit.py" \
  "${SEARCH_DIR}/verify_candidate.py" \
  "${ESLIM_SRC}/reduce.py" \
  "${ESLIM_SRC}/synthesisManager.py" \
  "${ESLIM_SRC}/subcircuitSynthesiser.py" \
  "${ESLIM_SRC}/relationFromSubcircuit.py" \
  "${ESLIM_SRC}/blifIO.py" \
  > "${RUN_DIR}/input_sha256.txt"

CURRENT_STAGE="occam-to-blif"
"${PYTHON}" -u "${SEARCH_DIR}/bridge.py" to-blif \
  "${REFERENCE}" \
  "${RUN_DIR}/input.partial.blif" \
  --model "mystery_${INSTANCE}_grid"
test -s "${RUN_DIR}/input.partial.blif"
mv "${RUN_DIR}/input.partial.blif" "${RUN_DIR}/input.blif"

printf '%q ' \
  "${PYTHON}" -u reduce.py \
  "${RUN_DIR}/input.blif" "${RUN_DIR}/reduced.partial.blif" \
  "${LIMIT_SECONDS}" --gs 2 --seed 42 --syn-mode sat --size "${SIZE}" \
  --limit-inputs 10 --solverTO 30 --relTO 30 --require-reduction \
  > "${RUN_DIR}/eslim_command.txt"
printf '\n' >> "${RUN_DIR}/eslim_command.txt"

CURRENT_STAGE="eslim-relation-sat"
SECONDS=0
(
  cd "${ESLIM_SRC}"
  "${PYTHON}" -u reduce.py \
    "${RUN_DIR}/input.blif" \
    "${RUN_DIR}/reduced.partial.blif" \
    "${LIMIT_SECONDS}" \
    --gs 2 \
    --seed 42 \
    --syn-mode sat \
    --size "${SIZE}" \
    --limit-inputs 10 \
    --solverTO 30 \
    --relTO 30 \
    --require-reduction
) > "${RUN_DIR}/eslim.stdout.txt" 2> "${RUN_DIR}/eslim.stderr.txt"
printf 'eslim_elapsed_seconds=%s\n' "${SECONDS}" > "${RUN_DIR}/timing.txt"
test -s "${RUN_DIR}/reduced.partial.blif"
mv "${RUN_DIR}/reduced.partial.blif" "${RUN_DIR}/reduced.blif"

CURRENT_STAGE="blif-to-occam"
"${PYTHON}" -u "${SEARCH_DIR}/bridge.py" to-occam \
  "${RUN_DIR}/reduced.blif" \
  "${RUN_DIR}/candidate.partial.txt"
test -s "${RUN_DIR}/candidate.partial.txt"
mv "${RUN_DIR}/candidate.partial.txt" "${RUN_DIR}/candidate.txt"

CURRENT_STAGE="independent-full-domain-audit"
PYTHONPATH="${SEARCH_DIR}" "${PYTHON}" -u \
  "${SEARCH_DIR}/verify_candidate.py" \
  "${REFERENCE}" \
  "${RUN_DIR}/candidate.txt" \
  --report "${RUN_DIR}/verification.json" \
  > "${RUN_DIR}/verification.stdout.txt"
test -s "${RUN_DIR}/verification.json"

SAVED_GATES="$(
  "${PYTHON}" -c \
    'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["saved_gates"])' \
    "${RUN_DIR}/verification.json"
)"
if [[ ! "${SAVED_GATES}" =~ ^-?[0-9]+$ ]] || (( SAVED_GATES < 0 )); then
  record_failure 22 "${LINENO}"
fi

if [[ "${INSTANCE}" == "D" ]]; then
  CURRENT_STAGE="independent-direct-formula-audit"
  "${PYTHON}" -u "${SEARCH_DIR}/audit_d_formula.py" \
    "${RUN_DIR}/candidate.txt" \
    --report "${RUN_DIR}/formula-audit.json" \
    > "${RUN_DIR}/formula-audit.stdout.txt"
  test -s "${RUN_DIR}/formula-audit.json"
fi

CURRENT_STAGE="finalization"
sha256sum \
  "${RUN_DIR}/reduced.blif" \
  "${RUN_DIR}/candidate.txt" \
  "${RUN_DIR}/verification.json" \
  > "${RUN_DIR}/output_sha256.txt"
{
  printf 'end_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'saved_gates=%s\n' "${SAVED_GATES}"
  if (( SAVED_GATES > 0 )); then
    printf 'result=%s\n' "VALIDATED_IMPROVEMENT"
  else
    printf 'result=%s\n' "VALIDATED_NO_IMPROVEMENT"
  fi
} >> "${RUN_DIR}/metadata.txt"

if (( SAVED_GATES > 0 )); then
  printf 'VALIDATED_IMPROVEMENT saved_gates=%s\n' "${SAVED_GATES}" \
    > "${RUN_DIR}/COMPLETE"
else
  printf 'VALIDATED_NO_IMPROVEMENT saved_gates=0\n' \
    > "${RUN_DIR}/COMPLETE"
fi
trap - ERR INT TERM
