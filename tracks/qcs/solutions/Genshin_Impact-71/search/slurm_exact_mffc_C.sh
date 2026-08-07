#!/usr/bin/env bash
#SBATCH --job-name=occ71-mffc-C
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/logs/mffc-C-%j.out

set -euo pipefail
umask 027

readonly PROJECT_ROOT="/home/user_milksang/private/homefile/quantum_harness/issue71_occam"
readonly SEARCH_DIR="${PROJECT_ROOT}/tracks/qcs/solutions/Genshin_Impact-71/search"
readonly INPUT_NETLIST="${PROJECT_ROOT}/results/occam71/reference-355/mystery-C.txt"
readonly CUT_LIMIT="${1:-6}"
readonly RUN_ROOT="${PROJECT_ROOT}/results/occam71/search/mffc-C-seed42-cut${CUT_LIMIT}"
readonly RUN_DIR="${RUN_ROOT}/job-${SLURM_JOB_ID}"

mkdir -p "${RUN_DIR}"
{
  printf 'job_id=%s\n' "${SLURM_JOB_ID}"
  printf 'node=%s\n' "$(hostname)"
  printf 'start_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'seed=42\n'
  printf 'max_cut_leaves=%s\n' "${CUT_LIMIT}"
  printf 'python=%s\n' "$(python3 --version 2>&1)"
} > "${RUN_DIR}/metadata.txt"

sha256sum \
  "${SEARCH_DIR}/exact_mffc.py" \
  "${SEARCH_DIR}/reduce_netlist.py" \
  "${INPUT_NETLIST}" > "${RUN_DIR}/input_sha256.txt"

SECONDS=0
python3 -u "${SEARCH_DIR}/exact_mffc.py" \
  "${INPUT_NETLIST}" \
  --out-dir "${RUN_DIR}/candidate" \
  --seed 42 \
  --max-cut-leaves "${CUT_LIMIT}"
printf 'elapsed_seconds=%s\n' "${SECONDS}" > "${RUN_DIR}/timing.txt"

printf 'end_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  >> "${RUN_DIR}/metadata.txt"
printf 'SUCCESS\n' > "${RUN_DIR}/COMPLETE"
