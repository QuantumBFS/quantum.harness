#!/bin/bash
#SBATCH --job-name=dc_L8
#SBATCH --output=dc_L8_%A_%a.out
#SBATCH --error=dc_L8_%A_%a.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --partition=xhacnormalb
#SBATCH --array=0-6

echo "=== delta-crossing L=8 ==="
echo "Job ID: $SLURM_JOB_ID  Task: $SLURM_ARRAY_TASK_ID / $SLURM_ARRAY_TASK_COUNT"
echo "Node: $SLURMD_NODENAME  Start: $(date)"
echo

source /work/home/mazhuijing/ed-project/.venv/bin/activate
export OPENBLAS_NUM_THREADS=$SLURM_CPUS_PER_TASK
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

cd "$SLURM_SUBMIT_DIR" || exit 1
python3 experiments/delta-crossing/scripts/run_crossing_L10.py \
    --config crossing_L8.yaml --task-id $SLURM_ARRAY_TASK_ID --task-count 7

echo "End: $(date)"
