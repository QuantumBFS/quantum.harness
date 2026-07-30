#!/bin/bash
#SBATCH --job-name=sh-deconf
#SBATCH --output=/work/home/mazhuijing/ed-project/results/spinon-holon/deconfinement/logs/deconf_%a_%A_%a.out
#SBATCH --error=/work/home/mazhuijing/ed-project/results/spinon-holon/deconfinement/logs/deconf_%a_%A_%a.err
#SBATCH --partition=xhacnormalb
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3900M
#SBATCH --time=24:00:00
#SBATCH --array=1-12%4

# Process 2: Spinon-holon deconfinement under RMH pump
# Reads parameter from array task ID.
#
# Grid (24 points for one L):
#   U   ∈ {6, 10, 14}        (3 values)
#   Rd  ∈ {0.2, 0.4}          (2 values)
#   T   ∈ {30, 60}            (2 values)
#   k0  ∈ {0, π/2}            (2 values)
#   Total: 3 × 2 × 2 × 2 = 24
#
# $SLURM_ARRAY_TASK_ID = 1..24 maps to (U, Rd, T, k0) combination.

set -euo pipefail

# --- Resolve L from sbatch --export=L=<value> ---
L=${L:-8}

# --- Paths ---
PROJECT_DIR="/work/home/mazhuijing/ed-project"
EXPERIMENT_DIR="$PROJECT_DIR/experiments/spinon-holon-pump"
RESULTS_DIR="$PROJECT_DIR/results/spinon-holon/deconfinement"
mkdir -p "$RESULTS_DIR/logs"

cd "$EXPERIMENT_DIR"

# --- Map array task ID to parameter combination ---
# Index 0-based: idx = OFFSET + $SLURM_ARRAY_TASK_ID - 1
OFFSET=${OFFSET:-0}
IDX=$((OFFSET + SLURM_ARRAY_TASK_ID - 1))

# 24 combinations: U (3) × Rd (2) × T (2) × k0 (2)
# Enumerate: for u in 0..2, for rd in 0..1, for t in 0..1, for k in 0..1
U_IDX=$(( IDX / 8 ))            # 0, 1, 2
REST=$(( IDX % 8 ))
RD_IDX=$(( REST / 4 ))          # 0, 1
REST=$(( REST % 4 ))
T_IDX=$(( REST / 2 ))           # 0, 1
K_IDX=$(( REST % 2 ))           # 0, 1

# Actual parameter values
U_VALS=(6 10 14)
RD_VALS=(0.2 0.4)
T_VALS=(30 60)
K0_VALS=(0 1.5707963267948966)  # 0 and π/2

U=${U_VALS[$U_IDX]}
RD=${RD_VALS[$RD_IDX]}
T=${T_VALS[$T_IDX]}
K0=${K0_VALS[$K_IDX]}

echo "=========================================="
echo "Process 2: Spinon-holon deconfinement"
echo "Job ${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
echo "L=$L U=$U Rd=$RD T=$T k0=$K0"
echo "Started: $(date)"
echo "=========================================="

python scripts/run_deconfinement.py \
    --L "$L" \
    --U "$U" \
    --Rd "$RD" \
    --T "$T" \
    --k0 "$K0"

echo "Finished: $(date)"
