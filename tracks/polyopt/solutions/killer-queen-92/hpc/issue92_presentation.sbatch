#!/bin/bash
#SBATCH --job-name=issue92-present
#SBATCH --partition=wzacnormal03
#SBATCH --nodes=1
#SBATCH --cpus-per-task=40
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --array=0-11%4
#SBATCH --output=results/slurm/issue92-present-%A_%a.out
#SBATCH --error=results/slurm/issue92-present-%A_%a.err

set -euo pipefail

SOLUTION_DIR=${SLURM_SUBMIT_DIR:?submit from the issue-92 solution directory}

cd "$SOLUTION_DIR"
MANIFEST=${ISSUE92_PRESENT_MANIFEST:-results/presentation_manifest.json}
RESULTS_DIR=${ISSUE92_PRESENT_RESULTS:-results/presentation_pilots}
mkdir -p results/slurm "$RESULTS_DIR"
module purge
module load compiler/intel/2021.3.0
module load python/3.8.10
export PATH="$HOME/.juliaup/bin:$PATH"
export JULIA_NUM_THREADS=${SLURM_CPUS_PER_TASK}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK}
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}
export JULIA_DEPOT_PATH="$SOLUTION_DIR/.raw/julia-depot:$HOME/.julia"
export JULIA_PKG_OFFLINE=true
export ISSUE92_SOLVER=clarabel
export ISSUE92_CLARABEL_PROFILE=presentation-fast
export ISSUE92_CLARABEL_MAX_ITER=${ISSUE92_CLARABEL_MAX_ITER:-60}
export ISSUE92_CLARABEL_TIME_LIMIT=${ISSUE92_CLARABEL_TIME_LIMIT:-600}
export ISSUE92_CLARABEL_DIRECT_SOLVER=${ISSUE92_CLARABEL_DIRECT_SOLVER:-mkl}
export ISSUE92_CLARABEL_MAX_THREADS=${ISSUE92_CLARABEL_MAX_THREADS:-40}
export ISSUE92_SOLVE_PROGRESS=1

python3 -u scripts/run_campaign_cell.py "$SLURM_ARRAY_TASK_ID" \
  --manifest "$MANIFEST" \
  --results "$RESULTS_DIR"
