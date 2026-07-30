#!/bin/bash
#SBATCH --job-name=issue92
#SBATCH --partition=wzacnormal03
#SBATCH --nodes=1
#SBATCH --cpus-per-task=128
#SBATCH --mem=225G
#SBATCH --time=24:00:00
#SBATCH --array=0-199%1
#SBATCH --output=results/slurm/issue92-%A_%a.out
#SBATCH --error=results/slurm/issue92-%A_%a.err

set -euo pipefail

SOLUTION_DIR=${SLURM_SUBMIT_DIR:?submit from the issue-92 solution directory}
OFFSET=${ISSUE92_ARRAY_OFFSET:-0}
INDEX=$((OFFSET + SLURM_ARRAY_TASK_ID))

cd "$SOLUTION_DIR"
mkdir -p results/slurm results/hierarchy_cells
module load python/3.8.10
module unload compiler/devtoolset/7.3.1
module load compiler/gcc/12.2.0
export PATH="$HOME/.juliaup/bin:$PATH"
export JULIA_NUM_THREADS=${SLURM_CPUS_PER_TASK}
export JULIA_DEPOT_PATH="$SOLUTION_DIR/.raw/julia-depot:$HOME/.julia"
export JULIA_PKG_OFFLINE=true
export ISSUE92_SOLVER=mosek

python3 -u scripts/run_campaign_cell.py "$INDEX"
