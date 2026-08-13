#!/bin/bash
#SBATCH --job-name=issue92-nested
#SBATCH --partition=wzacnormal03
#SBATCH --nodes=1
#SBATCH --cpus-per-task=104
#SBATCH --mem=192G
#SBATCH --time=08:00:00
#SBATCH --array=0-1%1
#SBATCH --output=results/slurm/issue92-nested-%A_%a.out
#SBATCH --error=results/slurm/issue92-nested-%A_%a.err

set -euo pipefail

SOLUTION_DIR=${SLURM_SUBMIT_DIR:?submit from the issue-92 solution directory}
cd "$SOLUTION_DIR"
RESULTS_DIR=${ISSUE92_RESULTS_DIR:-results/deadline_nested}
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
export ISSUE92_CLARABEL_PROFILE=deadline-balanced
export ISSUE92_CLARABEL_MAX_ITER=${ISSUE92_CLARABEL_MAX_ITER:-100}
export ISSUE92_CLARABEL_TIME_LIMIT=${ISSUE92_CLARABEL_TIME_LIMIT:-900}
export ISSUE92_CLARABEL_DIRECT_SOLVER=${ISSUE92_CLARABEL_DIRECT_SOLVER:-mkl}
export ISSUE92_CLARABEL_MAX_THREADS=${ISSUE92_CLARABEL_MAX_THREADS:-104}
export ISSUE92_SOLVE_PROGRESS=1

python3 -u scripts/run_campaign_cell.py "$SLURM_ARRAY_TASK_ID" \
  --manifest results/deadline_nested_manifest.json \
  --results "$RESULTS_DIR"
