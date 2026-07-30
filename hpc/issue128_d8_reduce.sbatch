#!/usr/bin/env bash
#SBATCH --job-name=issue128-d8-reduce
#SBATCH --partition=xhacnormalb
#SBATCH --account=giggleliu
#SBATCH --qos=user_acamtw70yu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=26
#SBATCH --mem=96G
#SBATCH --time=01:15:00
#SBATCH --output=results/slurm-%x-%j.out
#SBATCH --error=results/slurm-%x-%j.err

set -euo pipefail
: "${ISSUE128_RUN_ID:?ISSUE128_RUN_ID must name the result run}"
ISSUE128_ORDER="${ISSUE128_ORDER:-8}"

export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

REPOSITORY_ROOT="${SLURM_SUBMIT_DIR:?}"
ISSUE_ROOT="$REPOSITORY_ROOT/tracks/qcs/solutions/WangTheoPhys/issue128"
export PYTHONPATH="$ISSUE_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
RUN_ROOT="$REPOSITORY_ROOT/results/$ISSUE128_RUN_ID"
mkdir -p "$RUN_ROOT/reduced"
cd "$ISSUE_ROOT"
"$REPOSITORY_ROOT/.venv/bin/python" -u scripts/reduce_d8_shards.py \
  --input-root "$RUN_ROOT/cells" \
  --expected-stages 31 \
  --order "$ISSUE128_ORDER" \
  --output "$RUN_ROOT/reduced/degree-${ISSUE128_ORDER}.json.gz" \
  --summary "$RUN_ROOT/reduced/summary.json"
