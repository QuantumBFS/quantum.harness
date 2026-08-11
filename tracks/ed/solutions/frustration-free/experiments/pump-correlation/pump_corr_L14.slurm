#!/bin/bash
#SBATCH --job-name=pump_corr_L14
#SBATCH --partition=xhacnormalb
#SBATCH --account=giggleliu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --mem=128G
#SBATCH --time=12:00:00

set -euo pipefail
module load anaconda3/2023.09
source /work/home/mazhuijing/ed-project/.venv/bin/activate

export OPENBLAS_NUM_THREADS=$SLURM_CPUS_PER_TASK
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

cd /work/home/mazhuijing/ed-project/tracks/ed/hubbard-pump-2/experiments/pump-correlation

echo "=== L=14 pump correlation dynamics ==="
echo "Started at $(date)"
python -u scripts/run_pump_correlation.py --L 14
echo "Finished at $(date)"
