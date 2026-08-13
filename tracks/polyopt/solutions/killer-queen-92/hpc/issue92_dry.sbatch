#!/bin/bash
#SBATCH --job-name=issue92-dry
#SBATCH --partition=wzacnormal03
#SBATCH --nodes=1
#SBATCH --cpus-per-task=40
#SBATCH --mem=64G
#SBATCH --time=06:00:00
#SBATCH --array=0-11,13-17%7
#SBATCH --output=results/slurm/issue92-dry-%A_%a.out
#SBATCH --error=results/slurm/issue92-dry-%A_%a.err

set -euo pipefail

SOLUTION_DIR=${SLURM_SUBMIT_DIR:?submit from the issue-92 solution directory}

cd "$SOLUTION_DIR"
mkdir -p results/slurm results/dry_levels results/dry_models
module load python/3.8.10
export PATH="$HOME/.juliaup/bin:$PATH"
export JULIA_NUM_THREADS=${SLURM_CPUS_PER_TASK}
export JULIA_DEPOT_PATH="$SOLUTION_DIR/.raw/julia-depot:$HOME/.julia"
export JULIA_PKG_OFFLINE=true

if [[ ${ISSUE92_DRY_BUILD_MODEL:-0} == 1 ]]; then
    python3 -u scripts/run_dry_level.py "$SLURM_ARRAY_TASK_ID" \
      --build-model --results results/dry_models
else
    python3 -u scripts/run_dry_level.py "$SLURM_ARRAY_TASK_ID"
fi
