#!/usr/bin/env bash
#SBATCH --job-name=occ71-tn-rank
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --array=0-15%16
#SBATCH --output=results/occam71/tensor-network/logs/rank-%A_%a.out

set -euo pipefail

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

REPO=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
CODE="$REPO/tracks/qcs/solutions/Genshin_Impact-71/tensor_network"
DATA="$REPO/results/occam71/occam-circuit/datasets"
ROOT="$REPO/results/occam71/tensor-network/full-seed42/rank-job-${SLURM_ARRAY_JOB_ID}"
PYTHON=/home/user_milksang/.conda/envs/crystalgpt/bin/python

instances=(mystery-A mystery-B mystery-C mystery-D)
orders=(blocked_lsb blocked_msb interleaved_lsb interleaved_msb)

task=${SLURM_ARRAY_TASK_ID}
if (( task < 0 || task >= 16 )); then
  echo "invalid task id: $task" >&2
  exit 2
fi
instance=${instances[$((task / 4))]}
order=${orders[$((task % 4))]}
cell=$(printf '%s/cells/%02d-%s-%s' "$ROOT" "$task" "$instance" "$order")
mkdir -p "$cell"
start=$SECONDS
cd "$CODE"

sha256sum \
  tn_common.py tn_truth.py rank_diag.py oracle_rank_audit.py \
  write_cell_manifest.py slurm_tn_rank_full.sh TN_FULL_DESIGN.md \
  > "$cell/code.sha256"
input_sha=$(sha256sum "$DATA/$instance/train.csv" | cut -d' ' -f1)
printf '%s  %s\n' "$input_sha" "$DATA/$instance/train.csv" > "$cell/input.sha256"

"$PYTHON" -u rank_diag.py \
  --instance "$instance" \
  --train-csv "$DATA/$instance/train.csv" \
  --order "$order" \
  --ranks 1,2,4,8,16 \
  --iterations 8 \
  --root-seed 42 \
  --report-out "$cell/rank.json"

"$PYTHON" -u oracle_rank_audit.py \
  --instance "$instance" \
  --order "$order" \
  --report-out "$cell/oracle-ranks.json"

"$PYTHON" -u write_cell_manifest.py \
  --cell-dir "$cell" \
  --kind rank \
  --job-id "$SLURM_ARRAY_JOB_ID" \
  --task-id "$task" \
  --instance "$instance" \
  --order "$order" \
  --elapsed-seconds "$((SECONDS - start))" \
  --input-sha256 "$input_sha" \
  --artifact "$cell/code.sha256" \
  --artifact "$cell/input.sha256" \
  --artifact "$cell/rank.json" \
  --artifact "$cell/oracle-ranks.json"
