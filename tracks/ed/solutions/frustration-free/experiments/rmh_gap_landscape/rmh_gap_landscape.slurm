#!/bin/bash
#SBATCH --job-name=rmh_gap_L10
#SBATCH --output=rmh_gap_L10_%A_%a.out
#SBATCH --error=rmh_gap_L10_%A_%a.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=24:00:00
#SBATCH --partition=xhacnormalb
#SBATCH --array=0-9

# rmh_gap_landscape Phase B: L=10 sparse gap scan
# 100 array tasks, ~50 points per task, ~2-3h per task

echo "=== rmh_gap_landscape L=10 ==="
echo "Job ID:    $SLURM_JOB_ID"
echo "Task:      $SLURM_ARRAY_TASK_ID / $SLURM_ARRAY_TASK_COUNT"
echo "Node:      $SLURMD_NODENAME"
echo "Start:     $(date)"
echo

source /work/home/mazhuijing/ed-project/.venv/bin/activate

export OPENBLAS_NUM_THREADS=$SLURM_CPUS_PER_TASK
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

cd "$SLURM_SUBMIT_DIR" || exit 1
echo "Python: $(which python3)"
echo

python3 experiments/rmh_gap_landscape/scripts/scan_L10.py \
    --task-id $SLURM_ARRAY_TASK_ID --task-count 10

echo
echo "End: $(date)"
