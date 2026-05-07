#!/bin/bash
#SBATCH --job-name=tfim-fig4
#SBATCH --partition=i64m512u
#SBATCH --time=12:00:00
#SBATCH --array=1-28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --output=results/tfim_fig4_paper_grade/cells/slurm-%A_%a.out

# Paper-grade Fig 4 reproduction (Tarabunga et al., PRX Quantum 4, 040317).
# 28-cell array job: L ∈ {16, 32, 64, 128} × h ∈ {0.8, 0.9, 0.95, 1.0, 1.05, 1.1, 1.2}.
# χ=30, N_S=10⁶ — matches paper Fig 4 caption.
# Per-cell wall: ~4 hr at L=128 (timed locally); 12 hr walltime gives 3× headroom.
# After all cells finish: julia --project=julia-env scripts/tfim_fig4_aggregate.jl

set -euo pipefail
module load julia/1.10.9
cd "$SLURM_SUBMIT_DIR"

mkdir -p results/tfim_fig4_paper_grade/cells

# Map SLURM_ARRAY_TASK_ID (1-28) → (L, h).
LS=(16 32 64 128)
HS=(0.80 0.90 0.95 1.00 1.05 1.10 1.20)
N_HS=${#HS[@]}

idx=$((SLURM_ARRAY_TASK_ID - 1))
L_idx=$((idx / N_HS))
H_idx=$((idx % N_HS))
L=${LS[$L_idx]}
H=${HS[$H_idx]}

echo "Cell $SLURM_ARRAY_TASK_ID/28: L=$L  h=$H  N_S=10⁶  χ=30  (PBC)"
echo "Started:  $(date -u +%Y-%m-%dT%H:%M:%SZ)"

export FIG4_CELL_L=$L
export FIG4_CELL_H=$H
export FIG4_NSTEPS=1000000
export FIG4_CHI=30

stdbuf -oL julia --project=julia-env scripts/tfim_fig4_paper_grade.jl

echo "Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
