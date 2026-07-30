#!/usr/bin/env bash
#SBATCH --job-name=occ71-tn-mps
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=6G
#SBATCH --time=02:00:00
#SBATCH --array=0-63%16
#SBATCH --output=results/occam71/tensor-network/logs/mps-%A_%a.out

set -euo pipefail

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

REPO=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
CODE="$REPO/tracks/qcs/solutions/Genshin_Impact-71/tensor_network"
DATA="$REPO/results/occam71/occam-circuit/datasets"
ROOT="$REPO/results/occam71/tensor-network/full-seed42/mps-job-${SLURM_ARRAY_JOB_ID}"
PYTHON=/home/user_milksang/.conda/envs/crystalgpt/bin/python

instances=(mystery-A mystery-B mystery-C mystery-D)
orders=(blocked_lsb blocked_msb interleaved_lsb interleaved_msb)
bonds=(2 4 8 16)

task=${SLURM_ARRAY_TASK_ID}
if (( task < 0 || task >= 64 )); then
  echo "invalid task id: $task" >&2
  exit 2
fi
instance_index=$((task / 16))
within=$((task % 16))
order_index=$((within / 4))
bond_index=$((within % 4))
instance=${instances[$instance_index]}
order=${orders[$order_index]}
bond=${bonds[$bond_index]}
cell=$(printf '%s/cells/%02d-%s-%s-bond%d' \
  "$ROOT" "$task" "$instance" "$order" "$bond")
mkdir -p "$cell"
start=$SECONDS
cd "$CODE"

sha256sum \
  tn_common.py tn_truth.py train_mps.py audit_mps.py \
  write_cell_manifest.py slurm_tn_mps_full_v2.sh TN_FULL_DESIGN_V2.md \
  > "$cell/code.sha256"
input_sha=$(sha256sum "$DATA/$instance/train.csv" | cut -d' ' -f1)
printf '%s  %s\n' "$input_sha" "$DATA/$instance/train.csv" > "$cell/input.sha256"

"$PYTHON" -u train_mps.py \
  --instance "$instance" \
  --train-csv "$DATA/$instance/train.csv" \
  --order "$order" \
  --bond "$bond" \
  --ridge 1e-5 \
  --sweeps 6 \
  --patience 2 \
  --validation-fraction 0.2 \
  --root-seed 42 \
  --model-out "$cell/model.npz" \
  --report-out "$cell/train.json"

"$PYTHON" -u audit_mps.py \
  --model "$cell/model.npz" \
  --report-out "$cell/audit.json"

"$PYTHON" -u write_cell_manifest.py \
  --cell-dir "$cell" \
  --kind mps \
  --job-id "$SLURM_ARRAY_JOB_ID" \
  --task-id "$task" \
  --instance "$instance" \
  --order "$order" \
  --bond "$bond" \
  --elapsed-seconds "$((SECONDS - start))" \
  --input-sha256 "$input_sha" \
  --artifact "$cell/code.sha256" \
  --artifact "$cell/input.sha256" \
  --artifact "$cell/model.npz" \
  --artifact "$cell/train.json" \
  --artifact "$cell/audit.json"
