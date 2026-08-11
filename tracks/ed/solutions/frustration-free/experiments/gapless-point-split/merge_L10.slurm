#!/bin/bash
#SBATCH --job-name=merge_L10
#SBATCH --output=merge_L10_%j.out
#SBATCH --error=merge_L10_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --partition=xhacnormalb
#SBATCH --dependency=afterok:$ARRAY_PARENT

# Merge L10 chunks + refine — runs after all array tasks complete
# Submit with: sbatch --export=ARRAY_PARENT=<array_job_id>

echo "=== merge+refine L10 ==="
echo "Parent array: $ARRAY_PARENT"
echo "Start: $(date)"

source /work/home/mazhuijing/ed-project/.venv/bin/activate
cd "$SLURM_SUBMIT_DIR" || exit 1

for U in 0.0 0.2 0.5 1.0; do
    echo "--- Merge U=$U ---"
    python3 experiments/gapless-point-split/scripts/run_scan.py \
        --config experiments/gapless-point-split/configs/coarse_L10.yaml \
        --mode merge --U "$U"
done

echo "End: $(date)"
