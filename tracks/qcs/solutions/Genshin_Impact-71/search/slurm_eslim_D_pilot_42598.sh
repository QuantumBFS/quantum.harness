#!/usr/bin/env bash
# Reproducible eSLIM relation-SAT pilot for mystery D.
#
# This script is intentionally pinned to the successful, immutable build
# artifact from Slurm job 42598.  It creates one durable run directory per
# Slurm job and writes COMPLETE only after two independent exhaustive audits.
# It does not read or execute any competitor submission code.
#
#SBATCH --job-name=occ71-eslim-D-42598
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=00:25:00
#SBATCH --no-requeue
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/logs/eslim-D-42598-%j.out

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
readonly REFERENCE="${PROJECT_ROOT}/results/occam71/reference-355/mystery-D.txt"
readonly RUN_ROOT="${PROJECT_ROOT}/results/occam71/eslim/D-pilot-build42598-size6-seed42"
readonly RUN_DIR="${RUN_ROOT}/job-${SLURM_JOB_ID}"

mkdir -p "${RUN_ROOT}"
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
  printf 'job_id=%s\n' "${SLURM_JOB_ID}"
  printf 'node=%s\n' "$(hostname)"
  printf 'start_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'source_commit=%s\n' "51e9f77429627473db623058157b66a1192cbb59"
  printf 'build_job_id=%s\n' "42598"
  printf 'seed=%s\n' "42"
  printf 'python_hash_seed=%s\n' "${PYTHONHASHSEED}"
  printf 'limit_seconds=%s\n' "900"
  printf 'gate_size=%s\n' "2"
  printf 'initial_subcircuit_size=%s\n' "6"
  printf 'fixed_subcircuit_size=%s\n' "true"
  printf 'max_subcircuit_inputs=%s\n' "10"
  printf 'synthesis_mode=%s\n' "relation_sat"
  printf 'dynamic_timeouts=%s\n' "true"
  printf 'solver_base_timeout_seconds=%s\n' "30"
  printf 'relation_timeout_seconds=%s\n' "30"
  printf 'require_strict_local_reduction=%s\n' "true"
  printf 'windowing=%s\n' "false"
  printf 'abc=%s\n' "false"
  printf 'aig=%s\n' "false"
  printf 'restarts=%s\n' "0"
  printf 'python=%s\n' "$("${PYTHON}" --version 2>&1)"
} > "${RUN_DIR}/metadata.txt"

CURRENT_STAGE="build-integrity-check"
grep -qx 'SUCCESS' "${BUILD_RUN}/BUILD_READY"
test -x "${PYTHON}"
test -s "${ESLIM_SRC}/bindings/aiger.cpython-313-x86_64-linux-gnu.so"
test -s "${ESLIM_SRC}/bindings/cadical.cpython-313-x86_64-linux-gnu.so"
test -s \
  "${ESLIM_SRC}/bindings/relationSynthesiser.cpython-313-x86_64-linux-gnu.so"
sha256sum --check "${BUILD_RUN}/built_modules_sha256.txt" \
  > "${RUN_DIR}/built_modules_check.txt"

CURRENT_STAGE="input-integrity-check"
test -s "${REFERENCE}"
test -s "${SEARCH_DIR}/bridge.py"
test -s "${SEARCH_DIR}/circuit.py"
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
  --model "mystery_D_reference_355"
test -s "${RUN_DIR}/input.partial.blif"
mv "${RUN_DIR}/input.partial.blif" "${RUN_DIR}/input.blif"
sha256sum "${RUN_DIR}/input.blif" > "${RUN_DIR}/generated_input_sha256.txt"

cat > "${RUN_DIR}/eslim_command.txt" <<EOF
${PYTHON} -u reduce.py ${RUN_DIR}/input.blif ${RUN_DIR}/reduced.partial.blif 900 --gs 2 --seed 42 --syn-mode sat --size 6 --limit-inputs 10 --solverTO 30 --relTO 30 --require-reduction
EOF

CURRENT_STAGE="eslim-relation-sat"
SECONDS=0
(
  cd "${ESLIM_SRC}"
  "${PYTHON}" -u reduce.py \
    "${RUN_DIR}/input.blif" \
    "${RUN_DIR}/reduced.partial.blif" \
    900 \
    --gs 2 \
    --seed 42 \
    --syn-mode sat \
    --size 6 \
    --limit-inputs 10 \
    --solverTO 30 \
    --relTO 30 \
    --require-reduction
) > "${RUN_DIR}/eslim.stdout.txt" 2> "${RUN_DIR}/eslim.stderr.txt"
printf 'eslim_elapsed_seconds=%s\n' "${SECONDS}" \
  > "${RUN_DIR}/timing.txt"
test -s "${RUN_DIR}/reduced.partial.blif"
mv "${RUN_DIR}/reduced.partial.blif" "${RUN_DIR}/reduced.blif"

CURRENT_STAGE="blif-to-occam-audit"
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
if [[ ! "${SAVED_GATES}" =~ ^-?[0-9]+$ ]]; then
  record_failure 21 "${LINENO}"
fi
if (( SAVED_GATES < 0 )); then
  record_failure 22 "${LINENO}"
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
