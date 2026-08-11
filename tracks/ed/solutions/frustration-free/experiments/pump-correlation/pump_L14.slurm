#!/bin/bash
#SBATCH --job-name=pump-L14
#SBATCH --partition=xhacnormalb
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=48:00:00
#SBATCH --output=/work/home/mazhuijing/ed-project/results/pump-correlation/L14/slurm-%j.out
#SBATCH --error=/work/home/mazhuijing/ed-project/results/pump-correlation/L14/slurm-%j.err

source /work/home/mazhuijing/ed-project/.venv/bin/activate

cd /work/home/mazhuijing/ed-project/tracks/ed/hubbard-pump-2/experiments/pump-correlation

echo "=== L=14 pump correlation ==="
echo "Host: $(hostname)"
echo "Date: $(date)"
echo "Python: $(which python3)"
echo ""

python3 scripts/run_pump_correlation.py --L 14

echo ""
echo "Done: $(date)"
