#!/usr/bin/env bash
#SBATCH --job-name=occam71-div-C
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --array=0-3
#SBATCH --cpus-per-task=1
#SBATCH --mem=12G
#SBATCH --time=06:00:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/divisor-search/logs/C-%A_%a.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/divisor-search/logs/C-%A_%a.err

set -euo pipefail

readonly PROJECT=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
readonly SEARCH="${PROJECT}/tracks/qcs/solutions/Genshin_Impact-71/search"
readonly INPUT="${PROJECT}/results/occam71/reference-355/mystery-C.txt"
readonly RESULTS="${PROJECT}/results/occam71/divisor-search"
readonly ROOTS=(102 122 140 153)
readonly ROOT="${ROOTS[${SLURM_ARRAY_TASK_ID}]}"
readonly OUT="${RESULTS}/C/root-${ROOT}"

mkdir -p "${OUT}"
python3 -u "${SEARCH}/divisor_resynth.py" \
  "${INPUT}" \
  --out-dir "${OUT}" \
  --seed 42 \
  --deadline-seconds 21000 \
  --roots "${ROOT}"
test -s "${OUT}/report.json"
touch "${OUT}/COMPLETE"
