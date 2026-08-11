#!/bin/bash
#SBATCH --job-name=sh-deconf
#SBATCH --output=/work/home/mazhuijing/ed-project/results/spinon-holon/deconfinement/logs/deconf_%j.out
#SBATCH --error=/work/home/mazhuijing/ed-project/results/spinon-holon/deconfinement/logs/deconf_%j.err
#SBATCH --partition=xhacnormalb
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3900M
#SBATCH --time=24:00:00

# Process 2: Single-point deconfinement job.
# Parameters passed via --export: L, U, RD, T_VAL, K0

set -euo pipefail

EXPERIMENT_DIR="/work/home/mazhuijing/ed-project/experiments/spinon-holon-pump"
cd "$EXPERIMENT_DIR"

# Activate virtual environment with QuSpin
source /work/home/mazhuijing/ed-project/.venv/bin/activate

echo "=========================================="
echo "Process 2: Spinon-holon deconfinement"
echo "Job ${SLURM_JOB_ID}"
echo "L=$L U=$U Rd=$RD T=$T_VAL k0=$K0"
echo "Started: $(date)"
echo "=========================================="

python scripts/run_deconfinement.py \
    --L "$L" \
    --U "$U" \
    --Rd "$RD" \
    --T "$T_VAL" \
    --k0 "$K0"

echo "Finished: $(date)"
