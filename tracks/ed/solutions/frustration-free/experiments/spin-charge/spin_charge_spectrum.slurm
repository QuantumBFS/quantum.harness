#!/bin/bash
#SBATCH --job-name=spin_charge
#SBATCH --output=spin_charge_%j.out
#SBATCH --error=spin_charge_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#SBATCH --partition=xhacnormalb

# Spin-charge spectrum separation: Rice-Mele-Hubbard model
# Scans dimerisation δ ∈ [-0.5, 0.5] at fixed U=12, Δ=2
# L=6 full ED (benchmark) + L=8 (full ED, D=4900 still feasible)

echo "=== Spin-Charge Spectrum Separation ==="
echo "Job ID:    $SLURM_JOB_ID"
echo "Node:      $SLURMD_NODENAME"
echo "Start:     $(date)"
echo

source /work/home/mazhuijing/ed-project/.venv/bin/activate

export OPENBLAS_NUM_THREADS=$SLURM_CPUS_PER_TASK
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

cd "$SLURM_SUBMIT_DIR" || exit 1

echo "Python: $(which python3)"
echo

# L=6: always full ED (D=400, instant)
echo "=== Phase 1: L=6 full ED ==="
python3 spin_charge_spectrum.py --L 6 --method full_ed
echo

# L=8: full ED is faster and more complete than sparse for D=4900
echo "=== Phase 2: L=8 full ED ==="
python3 spin_charge_spectrum.py --L 8 --method full_ed
echo

echo "End: $(date)"
