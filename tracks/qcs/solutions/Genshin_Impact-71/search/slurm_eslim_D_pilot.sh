#!/usr/bin/env bash
#SBATCH --job-name=occ71-eslim-D
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=00:25:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/logs/eslim-D-%j.out

set -euo pipefail
umask 027

readonly PROJECT_ROOT="/home/user_milksang/private/homefile/quantum_harness/issue71_occam"
readonly SEARCH_DIR="${PROJECT_ROOT}/tracks/qcs/solutions/Genshin_Impact-71/search"
readonly BUILD_RUN="${PROJECT_ROOT}/results/occam71/tools/eslim-build-51e9f774/job-42566"
readonly ESLIM_SRC="${BUILD_RUN}/eSLIM/src"
readonly PYTHON="${BUILD_RUN}/venv/bin/python"
readonly REFERENCE="${PROJECT_ROOT}/results/occam71/reference-355/mystery-D.txt"
readonly INPUT_BLIF="${PROJECT_ROOT}/results/occam71/eslim/inputs/mystery-D.blif"
readonly RUN_ROOT="${PROJECT_ROOT}/results/occam71/eslim/D-size6-seed42"
readonly RUN_DIR="${RUN_ROOT}/job-${SLURM_JOB_ID}"

test -f "${BUILD_RUN}/BUILD_READY"
test -x "${PYTHON}"
test -s "${INPUT_BLIF}"
mkdir -p "${RUN_DIR}"
{
  printf 'job_id=%s\n' "${SLURM_JOB_ID}"
  printf 'node=%s\n' "$(hostname)"
  printf 'start_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'seed=42\n'
  printf 'limit_seconds=900\n'
  printf 'gate_size=2\n'
  printf 'initial_subcircuit_size=6\n'
  printf 'max_subcircuit_inputs=10\n'
  printf 'synthesis_mode=relation_sat\n'
  printf 'solver_timeout=30\n'
  printf 'relation_timeout=30\n'
} > "${RUN_DIR}/metadata.txt"
sha256sum \
  "${REFERENCE}" \
  "${INPUT_BLIF}" \
  "${SEARCH_DIR}/bridge.py" \
  "${SEARCH_DIR}/verify_candidate.py" \
  "${ESLIM_SRC}/reduce.py" \
  > "${RUN_DIR}/input_sha256.txt"

SECONDS=0
(
  cd "${ESLIM_SRC}"
  "${PYTHON}" -u reduce.py \
    "${INPUT_BLIF}" \
    "${RUN_DIR}/reduced.blif" \
    900 \
    --gs 2 \
    --seed 42 \
    --syn-mode sat \
    --size 6 \
    --limit-inputs 10 \
    --solverTO 30 \
    --relTO 30 \
    --require-reduction
)
printf 'elapsed_seconds=%s\n' "${SECONDS}" > "${RUN_DIR}/timing.txt"

python3 -u "${SEARCH_DIR}/bridge.py" to-occam \
  "${RUN_DIR}/reduced.blif" \
  "${RUN_DIR}/candidate.txt"
PYTHONPATH="${SEARCH_DIR}" python3 -u "${SEARCH_DIR}/verify_candidate.py" \
  "${REFERENCE}" \
  "${RUN_DIR}/candidate.txt" \
  --report "${RUN_DIR}/verification.json"

printf 'end_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  >> "${RUN_DIR}/metadata.txt"
printf 'SUCCESS\n' > "${RUN_DIR}/COMPLETE"
