#!/bin/bash
#SBATCH --job-name=u_scan_c
#SBATCH --output=u_scan_c_%j.out
#SBATCH --error=u_scan_c_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=24:00:00
#SBATCH --partition=xhacnormalb

# U_scan_C_solver: Rice-Mele-Hubbard many-body Chern number scan
# Coarse scan (L=6, 5x5) + refined scans (L=6,8, 9x9) + diagnostics

echo "=== U_scan_C_solver ==="
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

python3 u_scan_c_solver.py

echo
echo "End: $(date)"
