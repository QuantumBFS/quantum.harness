#!/usr/bin/env bash
# Pinned eSLIM continuation from the independently audited 152-gate multiplier.
#
#SBATCH --job-name=occ71-eslim-C152
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --array=0-4%5
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=00:25:00
#SBATCH --no-requeue
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/eslim/C-stage3-from152-grid-seed42/logs/%A_%a.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/eslim/C-stage3-from152-grid-seed42/logs/%A_%a.err

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
readonly REFERENCE="${PROJECT_ROOT}/results/occam71/eslim/C-stage2-from154-grid-seed42/03-size7-job43188/candidate.txt"
readonly RUN_ROOT="${PROJECT_ROOT}/results/occam71/eslim/C-stage3-from152-grid-seed42"

SIZES=(4 5 6 7 8)
readonly SIZE="${SIZES[$SLURM_ARRAY_TASK_ID]}"
readonly LIMIT_SECONDS=900
TASK_INDEX=$(printf "%02d" "${SLURM_ARRAY_TASK_ID}")
readonly TASK_INDEX
readonly RUN_DIR="${RUN_ROOT}/${TASK_INDEX}-size${SIZE}-job${SLURM_ARRAY_JOB_ID}"

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
  printf 'source_commit=%s\n' "51e9f77429627473db623058157b66a1192cbb59"
  printf 'build_job_id=%s\n' "42598"
  printf 'parent_job_id=%s\n' "43188_3"
  printf 'parent_gates=%s\n' "152"
  printf 'parent_sha256=%s\n' "67540307369fedfffdb2b1a6473eff5e0bbfeb0e4873d03fddbeceb653cd071c"
  printf 'seed=%s\n' "42"
  printf 'limit_seconds=%s\n' "${LIMIT_SECONDS}"
  printf 'initial_subcircuit_size=%s\n' "${SIZE}"
  printf 'max_subcircuit_inputs=%s\n' "10"
  printf 'synthesis_mode=%s\n' "relation_sat"
  printf 'solver_base_timeout_seconds=%s\n' "30"
  printf 'relation_timeout_seconds=%s\n' "30"
} > "${RUN_DIR}/metadata.txt"

CURRENT_STAGE="build-integrity-check"
grep -qx SUCCESS "${BUILD_RUN}/BUILD_READY"
test -x "${PYTHON}"
sha256sum --check "${BUILD_RUN}/built_modules_sha256.txt" \
  > "${RUN_DIR}/built_modules_check.txt"

CURRENT_STAGE="parent-integrity-and-formula-audit"
test -s "${REFERENCE}"
test "$(sha256sum "${REFERENCE}" | cut -d' ' -f1)" = \
  "67540307369fedfffdb2b1a6473eff5e0bbfeb0e4873d03fddbeceb653cd071c"
"${PYTHON}" -u "${SEARCH_DIR}/audit_c_formula.py" \
  "${REFERENCE}" \
  --report "${RUN_DIR}/parent-formula-audit.json" \
  > "${RUN_DIR}/parent-formula-audit.stdout.txt"

CURRENT_STAGE="input-integrity-check"
sha256sum \
  "${REFERENCE}" \
  "${SEARCH_DIR}/bridge.py" \
  "${SEARCH_DIR}/circuit.py" \
  "${SEARCH_DIR}/verify_candidate.py" \
  "${SEARCH_DIR}/audit_c_formula.py" \
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
  --model "mystery_C_152_stage3"
test -s "${RUN_DIR}/input.partial.blif"
mv "${RUN_DIR}/input.partial.blif" "${RUN_DIR}/input.blif"

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

CURRENT_STAGE="independent-reference-audit"
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

CURRENT_STAGE="independent-direct-formula-audit"
"${PYTHON}" -u "${SEARCH_DIR}/audit_c_formula.py" \
  "${RUN_DIR}/candidate.txt" \
  --report "${RUN_DIR}/formula-audit.json" \
  > "${RUN_DIR}/formula-audit.stdout.txt"
test -s "${RUN_DIR}/formula-audit.json"

CURRENT_STAGE="finalization"
sha256sum \
  "${RUN_DIR}/reduced.blif" \
  "${RUN_DIR}/candidate.txt" \
  "${RUN_DIR}/verification.json" \
  "${RUN_DIR}/formula-audit.json" \
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
