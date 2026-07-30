#!/usr/bin/env bash
#SBATCH --job-name=occ71-tn-summary
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:15:00
#SBATCH --output=results/occam71/tensor-network/logs/summary-%j.out

set -euo pipefail

: "${RANK_JOB_ID:?RANK_JOB_ID is required}"
: "${MPS_JOB_ID:?MPS_JOB_ID is required}"

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

REPO=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
CODE="$REPO/tracks/qcs/solutions/Genshin_Impact-71/tensor_network"
ROOT="$REPO/results/occam71/tensor-network/full-seed42"
OUT="$ROOT/summary-rank${RANK_JOB_ID}-mps${MPS_JOB_ID}"
PYTHON=/home/user_milksang/.conda/envs/crystalgpt/bin/python

mkdir -p "$OUT"
cd "$CODE"
sha256sum \
  tn_common.py summarize_pilot.py summarize_full.py \
  slurm_tn_summarize_full.sh \
  > "$OUT/code.sha256"

"$PYTHON" -u summarize_full.py \
  --rank-root "$ROOT/rank-job-${RANK_JOB_ID}" \
  --mps-root "$ROOT/mps-job-${MPS_JOB_ID}" \
  --report-out "$OUT/summary.json"

sha256sum "$OUT/summary.json" > "$OUT/summary.sha256"
printf 'success\n' > "$OUT/SUCCESS"
