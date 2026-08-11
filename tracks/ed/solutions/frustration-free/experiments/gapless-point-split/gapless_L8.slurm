#!/bin/bash
#SBATCH --job-name=gapsplit_L8
#SBATCH --output=gsplit_L8_%j.out
#SBATCH --error=gsplit_L8_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --partition=xhacnormalb

# Single job for all L=8 U values — no array, no chunking
# 4 U values, 41×51=2091 points each, ~20-30 min each

echo "=== gapless-point-split L=8 ==="
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
        --config experiments/gapless-point-split/configs/coarse_L8.yaml \
        --mode auto --U "$U"
done

echo
echo "End: $(date)"
