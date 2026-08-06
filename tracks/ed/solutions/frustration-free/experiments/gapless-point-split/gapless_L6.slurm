#!/bin/bash
#SBATCH --job-name=gsplit_L6
#SBATCH --output=gsplit_L6_%A_%a.out
#SBATCH --error=gsplit_L6_%A_%a.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --partition=xhacnormalb
#SBATCH --array=0-2

# gapless-point-split L=6: dense ED, 51×61 grid
# Array task 0 → U=0.2, 1 → U=0.5, 2 → U=1.0
# ~10 min per task

U_VALUES=(0.2 0.5 1.0)
U=${U_VALUES[$SLURM_ARRAY_TASK_ID]}

echo "=== gapless-point-split L=6  U=$U ==="
echo "Job ID:    $SLURM_JOB_ID"
echo "Task:      $SLURM_ARRAY_TASK_ID / $SLURM_ARRAY_TASK_COUNT"
echo "Node:      $SLURMD_NODENAME"
echo "Start:     $(date)"
echo

source /work/home/mazhuijing/ed-project/.venv/bin/activate

export OPENBLAS_NUM_THREADS=$SLURM_CPUS_PER_TASK
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

cd "$SLURM_SUBMIT_DIR" || exit 1
echo "PWD: $(pwd)"
echo "Python: $(which python3)"
echo

python3 experiments/gapless-point-split/scripts/run_scan.py \
    --config experiments/gapless-point-split/configs/coarse_L6.yaml \
    --mode auto --U "$U"

echo
echo "End: $(date)"
