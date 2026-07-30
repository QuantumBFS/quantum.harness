#!/usr/bin/env bash
#SBATCH --job-name=occ71-tn-bdd
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --array=0-3%4
#SBATCH --output=results/occam71/tensor-network/logs/distill-%A_%a.out

set -euo pipefail

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

REPO=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
CODE="$REPO/tracks/qcs/solutions/Genshin_Impact-71/tensor_network"
FULL="$REPO/results/occam71/tensor-network/full-seed42"
SUMMARY="$FULL/summary-rank42681-mps42698/summary.json"
MPS_ROOT="$FULL/mps-job-42698"
ROOT="$FULL/distill-job-${SLURM_ARRAY_JOB_ID}"
PYTHON=/home/user_milksang/.conda/envs/crystalgpt/bin/python

instances=(mystery-A mystery-B mystery-C mystery-D)
task=${SLURM_ARRAY_TASK_ID}
if (( task < 0 || task >= 4 )); then
  echo "invalid task id: $task" >&2
  exit 2
fi
instance=${instances[$task]}
cell=$(printf '%s/cells/%02d-%s' "$ROOT" "$task" "$instance")
mkdir -p "$cell"
start=$SECONDS
cd "$CODE"

sha256sum \
  tn_common.py tn_truth.py distill_mps_bdd.py write_distill_manifest.py \
  slurm_tn_distill.sh TN_DISTILL_DESIGN.md \
  > "$cell/code.sha256"
sha256sum "$SUMMARY" > "$cell/source-summary.sha256"

"$PYTHON" -u distill_mps_bdd.py \
  --instance "$instance" \
  --summary "$SUMMARY" \
  --mps-root "$MPS_ROOT" \
  --netlist-out "$cell/thresholded-mps-netlist.txt" \
  --report-out "$cell/report.json"

"$PYTHON" -u write_distill_manifest.py \
  --cell-dir "$cell" \
  --job-id "$SLURM_ARRAY_JOB_ID" \
  --task-id "$task" \
  --instance "$instance" \
  --elapsed-seconds "$((SECONDS - start))" \
  --artifact "$cell/code.sha256" \
  --artifact "$cell/source-summary.sha256" \
  --artifact "$cell/thresholded-mps-netlist.txt" \
  --artifact "$cell/report.json"
