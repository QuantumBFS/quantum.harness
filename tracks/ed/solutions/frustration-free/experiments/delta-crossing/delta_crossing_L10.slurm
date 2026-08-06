#!/bin/bash
#SBATCH --job-name=delta_cross_L10
#SBATCH --output=delta_cross_L10_%A_%a.out
#SBATCH --error=delta_cross_L10_%A_%a.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=24:00:00
#SBATCH --partition=xhacnormalb
#SBATCH --array=0-6

# delta-crossing L=10: P_ex(T) scan, 7 T values across 7 array tasks
# Each task: 1 T + dt-convergence (if applicable)
# T=100 ~5000 steps, sparse expm_multiply, estimated 2-10h per task

echo "=== delta-crossing L=10 ==="
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

python3 experiments/delta-crossing/scripts/run_crossing_L10.py \
    --task-id $SLURM_ARRAY_TASK_ID --task-count 7

echo
echo "End: $(date)"
