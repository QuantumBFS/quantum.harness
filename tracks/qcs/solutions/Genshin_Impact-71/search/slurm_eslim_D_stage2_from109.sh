#!/usr/bin/env bash
# Continue eSLIM from the independently audited 109-gate mystery-D candidate.
#
# The input was produced by job 42633 and is pinned by SHA-256 below.  COMPLETE
# is written only after reference equivalence and direct x*x+y*y audits pass.
#
#SBATCH --job-name=occ71-eslim-D-s2
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=00:25:00
#SBATCH --no-requeue
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/logs/eslim-D-stage2-%j.out

set -Eeuo pipefail
umask 027

export LC_ALL=C
export TZ=UTC
export PYTHONHASHSEED=42
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

readonly ROOT="/home/user_milksang/private/homefile/quantum_harness/issue71_occam"
readonly SEARCH="${ROOT}/tracks/qcs/solutions/Genshin_Impact-71/search"
readonly BUILD="${ROOT}/results/occam71/tools/eslim-build-51e9f774/job-42598"
readonly ESLIM="${BUILD}/eSLIM/src"
readonly PYTHON="${BUILD}/venv/bin/python"
readonly INPUT="${ROOT}/results/occam71/eslim/D-pilot-build42598-size6-seed42/job-42633/candidate.txt"
readonly EXPECTED_INPUT_SHA="cd3f317f4a0b88818e54869e40b4550fd67549f8eb4a5eb02c74db4ec6864dbd"
readonly RUN_ROOT="${ROOT}/results/occam71/eslim/D-stage2-from109-size6-seed42"
readonly RUN="${RUN_ROOT}/job-${SLURM_JOB_ID}"

mkdir -p "${RUN_ROOT}"
mkdir "${RUN}"

STAGE="initialization"
record_failure() {
  local code="$1"
  local line="$2"
  trap - ERR INT TERM
  {
    printf 'status=FAILED\n'
    printf 'stage=%s\n' "${STAGE}"
    printf 'exit_code=%s\n' "${code}"
    printf 'source_line=%s\n' "${line}"
    printf 'end_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > "${RUN}/FAILED"
  exit "${code}"
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
  printf 'parent_job_id=%s\n' "42633"
  printf 'parent_gates=%s\n' "109"
  printf 'seed=%s\n' "42"
  printf 'limit_seconds=%s\n' "900"
  printf 'gate_size=%s\n' "2"
  printf 'initial_subcircuit_size=%s\n' "6"
  printf 'fixed_subcircuit_size=%s\n' "true"
  printf 'max_subcircuit_inputs=%s\n' "10"
  printf 'synthesis_mode=%s\n' "relation_sat"
  printf 'solver_base_timeout_seconds=%s\n' "30"
  printf 'relation_timeout_seconds=%s\n' "30"
} > "${RUN}/metadata.txt"

STAGE="integrity-check"
grep -qx 'SUCCESS' "${BUILD}/BUILD_READY"
test -x "${PYTHON}"
test -s "${INPUT}"
test -s "${SEARCH}/bridge.py"
test -s "${SEARCH}/verify_candidate.py"
test -s "${SEARCH}/audit_d_formula.py"
printf '%s  %s\n' "${EXPECTED_INPUT_SHA}" "${INPUT}" \
  | sha256sum --check - > "${RUN}/parent_check.txt"
sha256sum --check "${BUILD}/built_modules_sha256.txt" \
  > "${RUN}/built_modules_check.txt"
sha256sum \
  "${INPUT}" \
  "${SEARCH}/bridge.py" \
  "${SEARCH}/verify_candidate.py" \
  "${SEARCH}/audit_d_formula.py" \
  "${ESLIM}/reduce.py" \
  > "${RUN}/input_sha256.txt"

STAGE="parent-formula-audit"
python3 "${SEARCH}/audit_d_formula.py" \
  "${INPUT}" \
  --report "${RUN}/parent-formula-audit.json" \
  > "${RUN}/parent-formula-audit.stdout.txt"

STAGE="occam-to-blif"
"${PYTHON}" -u "${SEARCH}/bridge.py" to-blif \
  "${INPUT}" \
  "${RUN}/input.partial.blif" \
  --model "mystery_D_stage2_parent_109"
test -s "${RUN}/input.partial.blif"
mv "${RUN}/input.partial.blif" "${RUN}/input.blif"

cat > "${RUN}/eslim_command.txt" <<EOF
${PYTHON} -u reduce.py ${RUN}/input.blif ${RUN}/reduced.partial.blif 900 --gs 2 --seed 42 --syn-mode sat --size 6 --limit-inputs 10 --solverTO 30 --relTO 30 --require-reduction
EOF

STAGE="eslim-relation-sat"
SECONDS=0
(
  cd "${ESLIM}"
  "${PYTHON}" -u reduce.py \
    "${RUN}/input.blif" \
    "${RUN}/reduced.partial.blif" \
    900 \
    --gs 2 \
    --seed 42 \
    --syn-mode sat \
    --size 6 \
    --limit-inputs 10 \
    --solverTO 30 \
    --relTO 30 \
    --require-reduction
) > "${RUN}/eslim.stdout.txt" 2> "${RUN}/eslim.stderr.txt"
printf 'eslim_elapsed_seconds=%s\n' "${SECONDS}" > "${RUN}/timing.txt"
test -s "${RUN}/reduced.partial.blif"
mv "${RUN}/reduced.partial.blif" "${RUN}/reduced.blif"

STAGE="blif-to-occam"
"${PYTHON}" -u "${SEARCH}/bridge.py" to-occam \
  "${RUN}/reduced.blif" \
  "${RUN}/candidate.partial.txt"
test -s "${RUN}/candidate.partial.txt"
mv "${RUN}/candidate.partial.txt" "${RUN}/candidate.txt"

STAGE="reference-equivalence-audit"
"${PYTHON}" -u "${SEARCH}/verify_candidate.py" \
  "${INPUT}" \
  "${RUN}/candidate.txt" \
  --report "${RUN}/verification.json" \
  > "${RUN}/verification.stdout.txt"
test -s "${RUN}/verification.json"

STAGE="direct-formula-audit"
python3 "${SEARCH}/audit_d_formula.py" \
  "${RUN}/candidate.txt" \
  --report "${RUN}/formula-audit.json" \
  > "${RUN}/formula-audit.stdout.txt"
test -s "${RUN}/formula-audit.json"

SAVED_GATES="$(
  "${PYTHON}" -c \
    'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["saved_gates"])' \
    "${RUN}/verification.json"
)"
CANDIDATE_GATES="$(
  "${PYTHON}" -c \
    'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["gates"])' \
    "${RUN}/formula-audit.json"
)"
if [[ ! "${SAVED_GATES}" =~ ^[0-9]+$ ]]; then
  record_failure 21 "${LINENO}"
fi
if [[ ! "${CANDIDATE_GATES}" =~ ^[0-9]+$ ]]; then
  record_failure 22 "${LINENO}"
fi

STAGE="finalization"
sha256sum \
  "${RUN}/reduced.blif" \
  "${RUN}/candidate.txt" \
  "${RUN}/verification.json" \
  "${RUN}/formula-audit.json" \
  > "${RUN}/output_sha256.txt"
{
  printf 'end_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'saved_gates=%s\n' "${SAVED_GATES}"
  printf 'candidate_gates=%s\n' "${CANDIDATE_GATES}"
  if (( SAVED_GATES > 0 )); then
    printf 'result=%s\n' "VALIDATED_IMPROVEMENT"
  else
    printf 'result=%s\n' "VALIDATED_NO_IMPROVEMENT"
  fi
} >> "${RUN}/metadata.txt"

if (( SAVED_GATES > 0 )); then
  printf 'VALIDATED_IMPROVEMENT candidate_gates=%s saved_gates=%s\n' \
    "${CANDIDATE_GATES}" "${SAVED_GATES}" > "${RUN}/COMPLETE"
else
  printf 'VALIDATED_NO_IMPROVEMENT candidate_gates=%s\n' \
    "${CANDIDATE_GATES}" > "${RUN}/COMPLETE"
fi
trap - ERR INT TERM
