#!/bin/bash
#SBATCH --job-name=gapsplit_L10
#SBATCH --output=gsplit_L10_%j.out
#SBATCH --error=gsplit_L10_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --partition=xhacnormalb

# Single job for all L=10 U values — no array, no chunking
# 4 U values, 31×41=1271 points each, ~1-3h each

echo "=== gapless-point-split L=10 ==="
echo "Job ID:    $SLURM_JOB_ID"
echo "Node:      $SLURMD_NODENAME"
echo "Start:     $(date)"
echo

source /work/home/mazhuijing/ed-project/.venv/bin/activate

export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export PYTHONUNBUFFERED=1

cd "$SLURM_SUBMIT_DIR" || exit 1
echo "PWD: $(pwd)"
echo "Python: $(which python3)"
echo

for U in 0.0 0.2 0.5 1.0; do
    echo "--- U=$U ---"
    python3 experiments/gapless-point-split/scripts/run_scan.py \
        --config experiments/gapless-point-split/configs/coarse_L10.yaml \
        --mode auto --U "$U"
done

echo
echo "End: $(date)"
