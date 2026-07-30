#!/usr/bin/env bash
#SBATCH --job-name=issue128-d8
#SBATCH --partition=xhacnormalb
#SBATCH --account=giggleliu
#SBATCH --qos=user_acamtw70yu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=16G
#SBATCH --time=04:30:00
#SBATCH --array=0-30%16
#SBATCH --output=results/slurm-%x-%A_%a.out
#SBATCH --error=results/slurm-%x-%A_%a.err

set -euo pipefail

: "${ISSUE128_RUN_ID:?ISSUE128_RUN_ID must name the result run}"
ISSUE128_ORDER="${ISSUE128_ORDER:-8}"

export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

REPOSITORY_ROOT="${SLURM_SUBMIT_DIR:?}"
ISSUE_ROOT="$REPOSITORY_ROOT/tracks/qcs/solutions/WangTheoPhys/issue128"
export PYTHONPATH="$ISSUE_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
CELL_ID=$(printf "stage-%02d" "$SLURM_ARRAY_TASK_ID")
CELL_DIR="$REPOSITORY_ROOT/results/$ISSUE128_RUN_ID/cells/$CELL_ID"
mkdir -p "$CELL_DIR"

cd "$ISSUE_ROOT"
"$REPOSITORY_ROOT/.venv/bin/python" -u scripts/build_d8_shard.py \
  --stage-index "$SLURM_ARRAY_TASK_ID" \
  --order "$ISSUE128_ORDER" \
  --output "$CELL_DIR/shard.json.gz" \
  --manifest "$CELL_DIR/manifest.json"
