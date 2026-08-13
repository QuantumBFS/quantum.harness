#!/bin/bash
#SBATCH --job-name=issue92-pilot
#SBATCH --partition=wzacnormal03
#SBATCH --nodes=1
#SBATCH --cpus-per-task=40
#SBATCH --mem=64G
#SBATCH --time=06:00:00
#SBATCH --array=4%1
#SBATCH --output=results/slurm/issue92-pilot-%A_%a.out
#SBATCH --error=results/slurm/issue92-pilot-%A_%a.err

set -euo pipefail

SOLUTION_DIR=${SLURM_SUBMIT_DIR:?submit from the issue-92 solution directory}

cd "$SOLUTION_DIR"
mkdir -p results/slurm results/clarabel_pilots
module load python/3.8.10
export PATH="$HOME/.juliaup/bin:$PATH"
export JULIA_NUM_THREADS=${SLURM_CPUS_PER_TASK}
export JULIA_DEPOT_PATH="$SOLUTION_DIR/.raw/julia-depot:$HOME/.julia"
export JULIA_PKG_OFFLINE=true
export ISSUE92_SOLVER=clarabel

python3 -u scripts/run_campaign_cell.py "$SLURM_ARRAY_TASK_ID" \
  --results results/clarabel_pilots
