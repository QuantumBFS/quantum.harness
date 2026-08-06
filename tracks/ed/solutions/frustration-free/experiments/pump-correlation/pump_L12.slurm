#!/bin/bash
#SBATCH --job-name=pump-L12
#SBATCH --partition=xhacnormalb
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=24:00:00
#SBATCH --output=/work/home/mazhuijing/ed-project/results/pump-correlation/L12/slurm-%j.out
#SBATCH --error=/work/home/mazhuijing/ed-project/results/pump-correlation/L12/slurm-%j.err

source /work/home/mazhuijing/ed-project/.venv/bin/activate

cd /work/home/mazhuijing/ed-project/tracks/ed/hubbard-pump-2/experiments/pump-correlation

echo "=== L=12 pump correlation ==="
echo "Host: $(hostname)"
echo "Date: $(date)"
echo "Python: $(which python3)"
echo ""

python3 scripts/run_pump_correlation.py --L 12

echo ""
echo "Done: $(date)"
